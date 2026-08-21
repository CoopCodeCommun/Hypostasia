"""
La verification s'enchaine, et ne rejuge que ce qui a bouge.
/ Verification is chained, and re-judges only what changed.

LOCALISATION : core/tests/test_verification_enchainee.py

CE QUE CE CHANTIER CORRIGE. Verifier les citations etait un GESTE : un
bouton, un clic, et rien avant. Un article produit restait donc sans
verdict tant que personne n'y pensait — et le lecteur decouvrait un
texte dont aucune phrase n'etait qualifiee, sans savoir que c'etait a
lui de le demander.

LE JUGEMENT S'ENCHAINE MAINTENANT LA OU L'ARTICLE S'ECRIT :
`_ecrire_le_corps_d_un_article` est le SEUL endroit ou un corps
d'article s'ecrit et ou ses citations s'indexent — la production comme
la mise a jour appliquee y passent.

ET IL NE REJUGE QUE CE QUI N'A PAS DE VERDICT. C'est ce qui rend
l'enchainement tenable : une mise a jour qui ne touche qu'un paragraphe
ne repaie pas le jugement des soixante autres citations. « Non
verifie » suffit a dire « modifiee » — l'indexation remet les citations
touchees dans cet etat, et les neuves y naissent.

⚠️ CE QUI EST EN JEU EST UNE FACTURE : le juge de production est un vrai
modele, appele a chaque production. Le regime incremental est ce qui
borne la depense.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (
    AIModel, Configuration, EtatDeVerification, Page, SourceLink, TypeDeNote,
    TypeLien,
)


class BaseDeLEnchainement(TestCase):
    """Un article, deux citations, un juge affecte au role."""

    def setUp(self):
        from hypostasis_extractor.models import ExtractedEntity, ExtractionJob

        self.utilisateur = get_user_model().objects.create_user(
            username="redacteur", password="motdepasse",
        )
        self.note = Page.objects.create(
            title="Note source", owner=self.utilisateur,
            type_de_note=TypeDeNote.NOTE,
            text_readability="Le seuil de convocation est fixé à trois voix.",
        )
        job = ExtractionJob.objects.create(page=self.note, status="completed")
        self.extractions = [
            ExtractedEntity.objects.create(
                job=job, extraction_class="hypostase",
                extraction_text=texte, start_char=0, end_char=len(texte),
            )
            for texte in (
                "Le seuil de convocation est fixé à trois voix.",
                "Le seuil de convocation est fixé à trois voix.",
            )
        ]
        self.article = Page.objects.create(
            title="Article", owner=self.utilisateur, type_de_note=TypeDeNote.WIKI,
        )
        self.modele = AIModel.objects.create(
            name="juge-de-test", model_choice="mistral-small-latest",
            is_active=True,
        )
        Configuration.get_solo()

    def _poser_deux_citations(self):
        from core.services.synthese import indexer_les_citations

        marqueurs = "".join(
            f"Affirmation {rang}.[[ext:{extraction.pk}]]\n\n"
            for rang, extraction in enumerate(self.extractions)
        )
        bilan = indexer_les_citations(self.article, marqueurs, None)
        self.article.text_readability = bilan["texte_nettoye"]
        self.article.save(update_fields=["text_readability"])
        return list(
            SourceLink.objects.filter(
                page_cible=self.article, type_lien=TypeLien.CITE,
            ).order_by("start_char_cible")
        )


class LeRegimeIncrementalNeRejugeQueCeQuiABouge(BaseDeLEnchainement):
    """
    Une mise a jour qui touche un paragraphe ne doit pas repayer le
    jugement des soixante autres citations.
    / An update touching one paragraph must not re-pay for sixty others.
    """

    def _juger(self, seulement_les_non_jugees):
        """Rend la liste des affirmations REELLEMENT posees au juge."""
        from core.services.verification import (
            verifier_les_citations_d_un_article,
        )

        vues = []

        def _juge_feint(modele, message_complet, *args, **kwargs):
            vues.append(message_complet)
            # Une note par paire, dans l'ordre : le format attendu.
            # / One score per pair, in order.
            return "\n".join(
                f"{rang}: 70"
                for rang in range(1, message_complet.count("---") + 2)
            )

        with patch("core.llm_providers.appeler_llm", side_effect=_juge_feint):
            verifier_les_citations_d_un_article(
                self.article, self.modele, seulement_les_non_jugees,
            )
        return "\n".join(vues)

    def test_sans_filtre_les_deux_citations_partent_au_juge(self):
        liens = self._poser_deux_citations()
        liens[0].etat_de_verification = EtatDeVerification.VERIFIE
        liens[0].save(update_fields=["etat_de_verification"])

        pose_au_juge = self._juger(seulement_les_non_jugees=False)

        self.assertIn("Affirmation 0", pose_au_juge)
        self.assertIn("Affirmation 1", pose_au_juge)

    def test_avec_le_filtre_la_citation_DEJA_JUGEE_ne_repart_pas(self):
        """
        LE CŒUR DE L'AFFAIRE, ET C'EST UNE FACTURE. Sans ce filtre,
        chaque mise a jour repaierait le jugement de tout l'article.
        / Without this filter, every update re-pays for the whole article.
        """
        liens = self._poser_deux_citations()
        liens[0].etat_de_verification = EtatDeVerification.VERIFIE
        liens[0].save(update_fields=["etat_de_verification"])

        pose_au_juge = self._juger(seulement_les_non_jugees=True)

        self.assertNotIn("Affirmation 0", pose_au_juge)
        self.assertIn("Affirmation 1", pose_au_juge)

    def test_un_verdict_deja_pose_n_est_pas_efface_par_le_filtre(self):
        """
        Ne pas rejuger n'est pas la meme chose que remettre a zero.
        / Not re-judging is not the same as resetting.
        """
        liens = self._poser_deux_citations()
        liens[0].etat_de_verification = EtatDeVerification.VERIFIE
        liens[0].save(update_fields=["etat_de_verification"])

        self._juger(seulement_les_non_jugees=True)

        liens[0].refresh_from_db()
        self.assertEqual(
            liens[0].etat_de_verification, EtatDeVerification.VERIFIE,
        )

    def test_un_verdict_HUMAIN_n_est_rejuge_dans_aucun_des_deux_regimes(self):
        """
        § 7.2 : un verdict humain n'est jamais ecrase. Il est
        `conteste`, donc hors du filtre — et la cascade l'ecarte de
        toute facon. Les deux gardes valent mieux qu'une.
        / A human verdict is never overwritten; both guards hold.
        """
        liens = self._poser_deux_citations()
        liens[0].etat_de_verification = EtatDeVerification.CONTESTE
        liens[0].verifie_par = "Jonas"
        liens[0].save(update_fields=["etat_de_verification", "verifie_par"])

        for regime in (True, False):
            self._juger(seulement_les_non_jugees=regime)
            liens[0].refresh_from_db()
            self.assertEqual(
                liens[0].etat_de_verification, EtatDeVerification.CONTESTE,
                f"regime seulement_les_non_jugees={regime}",
            )
            self.assertEqual(liens[0].verifie_par, "Jonas")


class LEnchainementSeDeclencheOuLArticleSEcrit(BaseDeLEnchainement):
    """
    `_ecrire_le_corps_d_un_article` est le SEUL endroit ou un corps
    s'ecrit et ou ses citations s'indexent : la production comme la mise
    a jour appliquee y passent.
    / The one place a body is written and its citations indexed.
    """

    def test_ecrire_un_article_met_la_verification_en_file(self):
        from front.tasks import _ecrire_le_corps_d_un_article

        with patch("front.tasks.enchainer_la_verification") as enchainement:
            _ecrire_le_corps_d_un_article(
                self.article,
                f"Une affirmation.[[ext:{self.extractions[0].pk}]]\n",
                None,
            )

        enchainement.assert_called_once()
        self.assertEqual(
            enchainement.call_args[0][0].pk, self.article.pk,
        )

    def test_le_destinataire_est_le_PROPRIETAIRE_de_l_article(self):
        """
        Les cinq appelants ne connaissent pas tous un utilisateur ;
        l'article, lui, en a toujours un.
        / The five callers do not all know a user; the article does.
        """
        from front.tasks import _ecrire_le_corps_d_un_article

        with patch("front.tasks.enchainer_la_verification") as enchainement:
            _ecrire_le_corps_d_un_article(
                self.article,
                f"Une affirmation.[[ext:{self.extractions[0].pk}]]\n",
                None,
            )

        self.assertEqual(
            enchainement.call_args[0][1], self.utilisateur.pk,
        )

    def test_le_job_enchaine_porte_le_REGIME_incremental(self):
        """
        Le bilan est relu apres coup : « 3 vérifiées » ne veut pas dire
        la meme chose selon qu'on a jugé tout l'article ou ses seules
        citations neuves. Le régime doit donc être écrit sur le job.
        / The regime is recorded: the same count means two things.
        """
        from front.tasks import enchainer_la_verification

        with patch(
            "core.services.modeles_par_role.modele_du_role",
            return_value=self.modele,
        ), patch("front.tasks.verifier_les_citations_task.delay"):
            job = enchainer_la_verification(self.article, self.utilisateur.pk)

        self.assertIsNotNone(job)
        self.assertTrue(job.raw_result["est_verification"])
        self.assertTrue(job.raw_result["seulement_les_non_jugees"])

    def test_les_quatre_juges_locaux_partent_AVEC_la_verification(self):
        """
        Sans eux, un article fraichement produit porte des verdicts mais
        AUCUN controleur : le renvoi ne peut jamais s'ambrer, la fiche
        annonce « comparaison impossible », et tout le signal de tension
        reste mort sur les articles neufs — sur les seuls, justement,
        qu'on vient de lire.
        / Without them a fresh article has verdicts but no controllers,
        and the tension signal is dead on the very articles just read.
        """
        from front.tasks import enchainer_la_verification

        with patch(
            "core.services.modeles_par_role.modele_du_role",
            return_value=self.modele,
        ), patch("front.tasks.verifier_les_citations_task.delay"), patch(
            "front.views_synthese._lancer_un_second_avis",
        ) as second_avis:
            enchainer_la_verification(self.article, self.utilisateur.pk)

        second_avis.assert_called_once_with(
            self.utilisateur.pk, self.article,
        )

    def test_sans_juge_affecte_RIEN_n_est_mis_en_file(self):
        """
        Un job qui echouerait faute de modele ferait un bandeau
        d'erreur a CHAQUE production.
        / A job doomed to fail would raise a banner at every production.
        """
        from front.tasks import enchainer_la_verification

        with patch(
            "core.services.modeles_par_role.modele_du_role", return_value=None,
        ), patch("front.tasks.verifier_les_citations_task.delay") as mise_en_file:
            job = enchainer_la_verification(self.article, self.utilisateur.pk)

        self.assertIsNone(job)
        mise_en_file.assert_not_called()
