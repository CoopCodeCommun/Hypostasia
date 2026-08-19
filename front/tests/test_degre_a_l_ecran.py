"""
Tests de l'AFFICHAGE du degre de verification (addendum du 18 aout 2026).
/ Tests of how the verification degree is DISPLAYED.

LOCALISATION : front/tests/test_degre_a_l_ecran.py

DEUX CHOSES A VERROUILLER, ET LA SECONDE EST UN INTERDIT.

1. Le panneau de preuve montre le degre ET le seuil ensemble. Un
   « soutenu a 45 sur 100 » ne veut rien dire sans la barre a partir de
   laquelle on compte ; et un degre sans le nom du juge qui l'a rendu
   redevient l'argument d'autorite que le § 7.2 interdit — deux juges
   n'ont pas la meme echelle.

2. LE CORPS DE L'ARTICLE NE PORTE AUCUN CHIFFRE. `PRESENTATION-V3.md
   § 3.6` a arbitre en connaissance de cause, sur une correlation
   mesuree de r = −0,96 entre la precision des citations et l'utilite
   percue : « trois etats visuellement discrets, pas un score par
   phrase — la rigueur est disponible AU CLIC, pas imposee a la
   lecture. » Ce test existe pour qu'une bonne intention future ne
   defasse pas cet arbitrage sans le savoir.
/ The proof panel shows degree + threshold + judge; the article body
carries no number at all (a governance decision, not an oversight).
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from core.models import (
    Configuration, Page, SourceLink, TypeDeNote, TypeLien,
)
from core.services.synthese import indexer_les_citations
from hypostasis_extractor.models import AIModel, ExtractedEntity, ExtractionJob

Utilisateur = get_user_model()

TEXTE_DE_LA_SOURCE = (
    "Le compte rendu note que le seuil de dix mille euros déclenche le "
    "passage en assemblée."
)


class BaseDeLAffichageDuDegre(TestCase):
    """Un article verifie, et un client connecte pour le lire."""

    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            username="lecteur_du_degre", password="motdepasse",
        )
        self.client = Client()
        self.client.force_login(self.utilisateur)
        self.modele_ia = AIModel.objects.create(
            name="Juge à degré", model_choice="mock_default", is_active=True,
        )
        note_source = Page.objects.create(
            url="http://exemple.local/degre-source",
            html_original="<p>o</p>", html_readability="<p>l</p>",
            text_readability=TEXTE_DE_LA_SOURCE,
            content_hash="hash-degre-source", title="Compte rendu",
        )
        job = ExtractionJob.objects.create(
            page=note_source, name="Analyse degré", status="completed",
            ai_model=None,
        )
        self.extraction = ExtractedEntity.objects.create(
            job=job, extraction_class="donnee",
            extraction_text=(
                "le seuil de dix mille euros déclenche le passage en assemblée"
            ),
            start_char=0, end_char=60,
        )
        self.article = Page.objects.create(
            url="http://exemple.local/degre-article",
            html_original="<p>a</p>", html_readability="<p>a</p>",
            text_readability="provisoire", content_hash="hash-degre-article",
            title="Synthèse à degré", type_de_note=TypeDeNote.SYNTHESE,
        )
        bilan = indexer_les_citations(
            self.article,
            f"Affirmation numéro 1.[[ext:{self.extraction.pk}]]\n",
            None,
        )
        self.article.text_readability = bilan["texte_nettoye"]
        self.article.save(update_fields=["text_readability"])

    def _juger(self, reponse):
        from core.services.verification import (
            verifier_les_citations_d_un_article,
        )
        with patch("core.llm_providers.appeler_llm", return_value=reponse):
            verifier_les_citations_d_un_article(self.article, self.modele_ia)

    def _lien(self):
        return SourceLink.objects.filter(
            page_cible=self.article, type_lien=TypeLien.CITE,
        ).get()


class LePanneauDePreuveMontreLeDegreTest(BaseDeLAffichageDuDegre):
    """Le degre, son seuil et son juge, dans la meme phrase."""

    def test_le_degre_et_le_seuil_sont_affiches_ensemble(self):
        self._juger("1: 70")

        reponse = self.client.get(f"/citations/{self._lien().pk}/preuve/")

        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode()
        self.assertIn('data-testid="synthese-degre"', contenu)
        self.assertIn('data-score="70"', contenu)
        self.assertIn('data-seuil="45"', contenu)

    def test_le_degre_nomme_le_juge_qui_l_a_rendu(self):
        # Deux juges n'ont pas la meme echelle : un chiffre nu n'est pas
        # comparable, et redevient un argument d'autorite.
        # / Judges do not share a scale; a bare number is not comparable.
        self._juger("1: 70")

        reponse = self.client.get(f"/citations/{self._lien().pk}/preuve/")

        self.assertIn("Juge à degré", reponse.content.decode())

    def test_le_seuil_affiche_suit_la_configuration(self):
        self._juger("1: 70")
        configuration = Configuration.objects.first() \
            or Configuration.objects.create()
        configuration.seuil_de_verification = 80.0
        configuration.save(update_fields=["seuil_de_verification"])

        reponse = self.client.get(f"/citations/{self._lien().pk}/preuve/")

        self.assertIn('data-seuil="80"', reponse.content.decode())

    def test_une_citation_sans_degre_n_affiche_aucune_barre(self):
        # INTROUVABLE est pose par le verbatim seul : il n'y a pas de
        # degre a montrer, et une barre a zero mentirait.
        # / No judge, no degree: showing a bar at zero would lie.
        ExtractedEntity.objects.filter(pk=self.extraction.pk).update(
            extraction_text="un texte qui n'apparait nulle part",
        )
        self._juger("")

        reponse = self.client.get(f"/citations/{self._lien().pk}/preuve/")

        contenu = reponse.content.decode()
        self.assertNotIn('data-testid="synthese-degre"', contenu)
        self.assertIn('data-testid="synthese-etat-verification"', contenu)


class LeSeuilSeRegleDepuisLEcranTest(BaseDeLAffichageDuDegre):
    """
    Le geste sans lequel « visible et modifiable » n'est pas tenu.
    / The gesture without which "visible and modifiable" is a promise only.
    """

    def test_deplacer_le_seuil_relabellise_sans_appeler_le_juge(self):
        self._juger("1: 70")
        self.assertEqual(self._lien().etat_de_verification, "verifie")

        with patch("core.llm_providers.appeler_llm") as mock_llm:
            reponse = self.client.post("/config-ia/seuil/", {"seuil": 80})

        mock_llm.assert_not_called()
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(self._lien().etat_de_verification, "faible")
        self.assertEqual(
            Configuration.get_solo().seuil_de_verification, 80.0,
        )

    def test_l_ecran_dit_combien_de_renvois_ont_change(self):
        # Un recalcul muet laisserait l'ecran identique a celui d'avant
        # le clic. / A silent re-label looks exactly like doing nothing.
        self._juger("1: 70")

        reponse = self.client.post("/config-ia/seuil/", {"seuil": 80})

        contenu = reponse.content.decode()
        self.assertIn('data-testid="config-seuil-resultat"', contenu)
        self.assertIn("1 renvoi", contenu)

    def test_un_seuil_hors_bornes_est_refuse(self):
        self._juger("1: 70")

        reponse = self.client.post("/config-ia/seuil/", {"seuil": 140})

        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(
            Configuration.get_solo().seuil_de_verification, 45.0,
        )
        self.assertEqual(self._lien().etat_de_verification, "verifie")

    def test_un_visiteur_anonyme_ne_deplace_pas_le_seuil(self):
        self._juger("1: 70")
        client_anonyme = Client()

        reponse = client_anonyme.post("/config-ia/seuil/", {"seuil": 80})

        self.assertNotEqual(reponse.status_code, 200)
        self.assertEqual(
            Configuration.get_solo().seuil_de_verification, 45.0,
        )


class LeCorpsDeLArticleNePorteAucunChiffreTest(BaseDeLAffichageDuDegre):
    """
    L'INTERDIT DE `PRESENTATION-V3.md § 3.6`, verrouille.

    Le corps garde trois etats visuellement discrets. Le degre vit dans
    le panneau, disponible au clic. Ce test tombera si quelqu'un porte
    le chiffre dans le texte — ce qui partirait d'une bonne intention et
    deferait un arbitrage pris sur une mesure.
    / The § 3.6 arbitration, locked.
    """

    def test_le_html_de_l_article_ne_contient_pas_le_degre(self):
        from front.views_synthese import _html_avec_renvois

        self._juger("1: 70")

        html = _html_avec_renvois(self.article)

        self.assertIn('data-verification="verifie"', html)
        self.assertNotIn("data-score", html)
        self.assertNotIn("sur 100", html)
        self.assertNotIn("score_de_verification", html)
