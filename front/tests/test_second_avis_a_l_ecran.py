"""
Tests de l'AFFICHAGE du second avis, et de son declenchement.
/ Tests of how the second opinion is displayed and queued.

LOCALISATION : front/tests/test_second_avis_a_l_ecran.py

QUATRE ETATS QUI NE DOIVENT PAS SE CONFONDRE :
1. les deux avis presents -> accord ou desaccord, deux barres, DEUX SEUILS ;
2. le juge de production sans degre -> « comparaison impossible » — et
   c'est l'etat de TOUTE citation verifiee avant le 18 aout 2026 ;
3. le second avis EN COURS -> il est annonce ;
4. le second avis jamais demande -> rien du tout.

Plus deux gardes sur le declenchement : le chemin d'INSTALLATION ne doit
jamais mettre le juge local en file (il tourne a chaque demarrage de
conteneur, et couterait une heure de processeur a chaque fois), et un
re-clic ne doit pas empiler deux lots.
/ Four display states that must not look alike, plus the install-path
and re-click guards.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from core.models import Page, SourceLink, TypeDeNote, TypeLien
from core.services.synthese import indexer_les_citations
from core.services.verification import poser_un_avis_local
from hypostasis_extractor.models import AIModel, ExtractedEntity, ExtractionJob

Utilisateur = get_user_model()

TEXTE_DE_LA_SOURCE = (
    "Le compte rendu note que le seuil de dix mille euros déclenche le "
    "passage en assemblée."
)
# DEUX JUGES, PAS UN. Depuis le 19 août 2026 le second avis est
# PLURIEL : quatre encodeurs à moins d'une demi-seconde ont remplacé
# ShieldStral (24 s la paire). Ces tests en jouent deux, ce qui suffit à
# éprouver le pluriel — un seul ne distinguerait pas « tous d'accord »
# de « partagés ».
# / The second opinion is plural since 19 August; two judges suffice to
# exercise the plural.
METHODE_LOCALE = "xnli-directe v1 — CamemBERTa v2"
AUTRE_METHODE = "xnli-directe v1 — mDeBERTa v3"


class BaseDuSecondAvisAffiche(TestCase):
    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            username="lecteur_second_avis", password="motdepasse",
        )
        self.client = Client()
        self.client.force_login(self.utilisateur)
        self.modele_ia = AIModel.objects.create(
            name="Juge de production", model_choice="mock_default",
            is_active=True,
        )
        note_source = Page.objects.create(
            url="http://exemple.local/2avis-source",
            html_original="<p>o</p>", html_readability="<p>l</p>",
            text_readability=TEXTE_DE_LA_SOURCE,
            content_hash="hash-2avis-source", title="Compte rendu",
        )
        job = ExtractionJob.objects.create(
            page=note_source, name="Analyse 2 avis", status="completed",
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
            url="http://exemple.local/2avis-article",
            html_original="<p>a</p>", html_readability="<p>a</p>",
            text_readability="provisoire", content_hash="hash-2avis-article",
            title="Synthèse à deux juges", type_de_note=TypeDeNote.SYNTHESE,
        )
        bilan = indexer_les_citations(
            self.article,
            f"Affirmation numéro 1.[[ext:{self.extraction.pk}]]\n", None,
        )
        self.article.text_readability = bilan["texte_nettoye"]
        self.article.save(update_fields=["text_readability"])

    def _lien(self):
        return SourceLink.objects.filter(
            page_cible=self.article, type_lien=TypeLien.CITE,
        ).get()

    def _juger_en_production(self, reponse):
        from core.services.verification import (
            verifier_les_citations_d_un_article,
        )
        with patch("core.llm_providers.appeler_llm", return_value=reponse):
            verifier_les_citations_d_un_article(self.article, self.modele_ia)

    def _preuve(self):
        return self.client.get(
            f"/citations/{self._lien().pk}/preuve/",
        ).content.decode()


class LePanneauMontreLesDeuxAvisTest(BaseDuSecondAvisAffiche):

    def test_les_deux_barres_portent_deux_seuils_differents(self):
        # LA RÈGLE QUI EMPÊCHE UNE COMPARAISON FAUSSE : chaque juge est
        # lu avec SON seuil. / Each judge read with ITS threshold.
        self._juger_en_production("1: 70")
        poser_un_avis_local(
            self._lien(), score=41.0, methode=METHODE_LOCALE, seuil=38.0,
        )

        contenu = self._preuve()

        self.assertIn('data-testid="synthese-degre"', contenu)
        self.assertIn('data-testid="synthese-barre-avis-local"', contenu)
        self.assertIn('data-seuil="45"', contenu)
        self.assertIn('data-seuil="38"', contenu)

    def test_deux_juges_au_dessus_de_leur_seuil_sont_annonces_d_accord(self):
        self._juger_en_production("1: 70")
        poser_un_avis_local(
            self._lien(), score=41.0, methode=METHODE_LOCALE, seuil=38.0,
        )

        contenu = self._preuve()

        self.assertIn('data-accord="accord"', contenu)
        # Le radical, pas la forme flechie : le gabarit accorde le verbe
        # au nombre de juges qui tranchent, et ce nombre varie.
        # / The stem, not the inflected form: the template agrees in number.
        self.assertIn("confirme", contenu)

    def test_un_desaccord_est_annonce_en_toutes_lettres(self):
        # Le mot, pas seulement la couleur : un filet coloré ne se lit
        # pas tout seul. / The word, not just the colour.
        self._juger_en_production("1: 70")
        poser_un_avis_local(
            self._lien(), score=12.0, methode=METHODE_LOCALE, seuil=38.0,
        )

        contenu = self._preuve()

        self.assertIn('data-accord="desaccord"', contenu)
        self.assertIn("diverge", contenu)

    def test_des_juges_partages_sont_comptes_et_non_arrondis(self):
        """
        CE QUE LES COLONNES NE SAVAIENT PAS DIRE. Avec un seul second
        juge, l'accord etait binaire. Avec plusieurs, « deux sur quatre »
        est une information en soi — et l'arrondir a « d'accord » ou
        « divergent » effacerait exactement ce que la campagne cherche.
        / With several judges, "two out of four" is the information.
        """
        self._juger_en_production("1: 70")
        poser_un_avis_local(
            self._lien(), score=81.0, methode=METHODE_LOCALE, seuil=50.0,
        )
        poser_un_avis_local(
            self._lien(), score=12.0, methode=AUTRE_METHODE, seuil=50.0,
        )

        contenu = self._preuve()

        self.assertIn('data-accord="partage"', contenu)
        self.assertIn("sur 2", contenu)

    def test_chaque_juge_a_sa_propre_barre(self):
        self._juger_en_production("1: 70")
        poser_un_avis_local(
            self._lien(), score=81.0, methode=METHODE_LOCALE, seuil=50.0,
        )
        poser_un_avis_local(
            self._lien(), score=12.0, methode=AUTRE_METHODE, seuil=55.0,
        )

        contenu = self._preuve()

        self.assertEqual(
            contenu.count('data-testid="synthese-barre-avis-local"'), 2,
        )
        self.assertIn('data-seuil="50"', contenu)
        self.assertIn('data-seuil="55"', contenu)

    def test_un_juge_qui_ne_tranche_pas_est_dit_tel_quel(self):
        """
        LE DEFAUT QUE CET ETAT EMPECHE. Mesure du 19 août sur les avis
        réels : la moitié des scores tombent à moins de deux points du
        seuil. Les afficher comme « confirme » ou « diverge » ferait
        passer la troisième décimale pour un verdict.
        / Half the real scores sit within two points of the threshold.
        """
        self._juger_en_production("1: 70")
        poser_un_avis_local(
            self._lien(), score=50.1, methode=METHODE_LOCALE, seuil=50.0,
        )

        contenu = self._preuve()

        self.assertIn('data-accord="sans-avis"', contenu)
        # Le radical : le gabarit accorde le verbe au nombre de juges.
        # / The stem: the template agrees in number.
        self.assertIn("ne tranche", contenu)
        self.assertIn("Ne tranche pas", contenu)
        self.assertIn('data-cote="neutre"', contenu)

    def test_le_second_avis_nomme_son_juge(self):
        self._juger_en_production("1: 70")
        poser_un_avis_local(
            self._lien(), score=41.0, methode=METHODE_LOCALE, seuil=38.0,
        )

        self.assertIn("CamemBERTa v2", self._preuve())


class LesEtatsQuiNeSeConfondentPasTest(BaseDuSecondAvisAffiche):

    def test_sans_degre_de_production_la_comparaison_est_dite_impossible(self):
        # L'ÉTAT DE TOUTE LA BASE au 18 août 2026 : 145 citations avec un
        # verdict, zéro avec un degré. Ce n'est pas un cas limite.
        # / The state of the whole base: verdicts, but no degrees.
        lien = self._lien()
        lien.etat_de_verification = "verifie"
        lien.verifie_par = "verbatim+nli-lot v2 — un juge d'avant"
        lien.save(update_fields=["etat_de_verification", "verifie_par"])
        poser_un_avis_local(lien, score=41.0, methode=METHODE_LOCALE, seuil=38.0)

        contenu = self._preuve()

        self.assertIn('data-accord="incalculable"', contenu)
        self.assertIn("Comparaison impossible", contenu)

    def test_un_second_avis_en_cours_est_annonce(self):
        self._juger_en_production("1: 70")
        ExtractionJob.objects.create(
            page=self.article, ai_model=None, name="Second avis",
            prompt_description="second avis", status="pending",
            raw_result={"est_second_avis": True},
        )

        contenu = self._preuve()

        self.assertIn('data-testid="synthese-avis-locaux-en-cours"', contenu)
        self.assertNotIn('data-testid="synthese-barre-avis-local"', contenu)

    def test_sans_second_avis_ni_tache_le_panneau_n_annonce_rien(self):
        self._juger_en_production("1: 70")

        contenu = self._preuve()

        self.assertNotIn('data-testid="synthese-avis-locaux"', contenu)
        self.assertNotIn(
            'data-testid="synthese-avis-locaux-en-cours"', contenu,
        )

    def test_sous_un_verdict_humain_le_second_avis_est_subordonne(self):
        # § 7.2 : un verdict humain n'est jamais écrasé. L'avis
        # automatique est montré — cacher une information dans un outil
        # de délibération est un choix fort — mais il est explicitement
        # dit qu'il ne remplace rien.
        # / Shown, but explicitly subordinated to the human verdict.
        lien = self._lien()
        lien.etat_de_verification = "conteste"
        lien.verifie_par = "Jonas"
        lien.score_de_verification = 70.0
        lien.save(update_fields=[
            "etat_de_verification", "verifie_par", "score_de_verification",
        ])
        poser_un_avis_local(lien, score=41.0, methode=METHODE_LOCALE, seuil=38.0)

        contenu = self._preuve()

        self.assertIn(
            'data-testid="synthese-avis-locaux-subordonne"', contenu,
        )
        self.assertIn("ils ne le remplacent pas", contenu)


class LeDeclenchementDuSecondAvisTest(BaseDuSecondAvisAffiche):

    def test_le_geste_utilisateur_met_le_second_avis_en_file(self):
        from front.views_synthese import _lancer_un_second_avis

        with patch(
            "front.tasks.noter_avec_le_juge_local_task.delay",
        ) as mock_tache:
            job = _lancer_un_second_avis(self.utilisateur.pk, self.article)

        self.assertIsNotNone(job)
        mock_tache.assert_called_once_with(job.pk)
        self.assertTrue(job.raw_result["est_second_avis"])

    def test_un_second_clic_n_empile_pas_un_second_lot(self):
        # Le juge de production coûte des secondes ; le juge local, des
        # dizaines de minutes dans une file à concurrence 1.
        # / Seconds for the API judge, tens of minutes here.
        from front.views_synthese import _lancer_un_second_avis

        with patch("front.tasks.noter_avec_le_juge_local_task.delay"):
            premier = _lancer_un_second_avis(self.utilisateur.pk, self.article)
            second = _lancer_un_second_avis(self.utilisateur.pk, self.article)

        self.assertIsNotNone(premier)
        self.assertIsNone(second)
        self.assertEqual(
            ExtractionJob.objects.filter(
                page=self.article,
                raw_result__contains={"est_second_avis": True},
            ).count(),
            1,
        )

    def test_le_chemin_d_installation_ne_met_rien_en_file(self):
        # `bin/install.sh` appelle `verifier_les_citations_etalons` à
        # CHAQUE démarrage de conteneur, et cette commande lance la tâche
        # de vérification DIRECTEMENT. Si le fan-out vivait dans la
        # tâche, chaque redémarrage coûterait ~1 h de processeur.
        # / The install path calls the task directly at every start.
        import front.tasks as taches

        source = taches.verifier_les_citations_task.__wrapped__.__code__
        noms_appeles = source.co_names

        self.assertNotIn("noter_avec_le_juge_local_task", noms_appeles)
