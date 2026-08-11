"""
Tests de la garde d'edition pendant une analyse.
/ Tests for the edit guard during an analysis.

LOCALISATION : hypostasis_extractor/tests/test_garde_edition.py

Lancer avec :
    docker exec hypostasia_dev_web uv run python manage.py test \\
        hypostasis_extractor.tests.test_garde_edition
"""

import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.models import (
    ElementDocument,
    Page,
    TranscriptionJob,
    TranscriptionJobStatus,
    empreinte_du_texte,
)
from hypostasis_extractor.models import ExtractionJob, ExtractionJobStatus
from hypostasis_extractor.services.garde_edition import (
    DELAI_AVANT_DE_CONSIDERER_UN_JOB_MORT,
    EditionBloqueePendantAnalyse,
    une_analyse_tourne_sur_la_page,
    verifier_qu_aucune_analyse_ne_tourne,
)
from hypostasis_extractor.services.masquage import (
    demasquer_un_element,
    masquer_un_element,
)
from hypostasis_extractor.services.moteur_structure import (
    fusionner_deux_elements,
    scinder_un_element,
)
from hypostasis_extractor.services.reconciliation import (
    reconcilier_les_portions_de_l_element,
)
from hypostasis_extractor.services.reingestion import (
    reconcilier_les_elements_par_empreinte,
)


class BaseGardeTestCase(TestCase):
    """Socle commun. / Common ground."""

    def setUp(self):
        self.utilisateur_de_test = get_user_model().objects.create_user(
            username="testeur_garde", password="motdepasse_de_test_123",
        )
        self.page_de_test = Page.objects.create(
            url="http://exemple.local/page-garde",
            html_original="<p>o</p>", html_readability="<p>l</p>",
            text_readability="texte", content_hash="empreinte_page_garde",
        )
        self.premier_element = self._ajouter_un_element(0, "Premier passage.")
        self.second_element = self._ajouter_un_element(1, "Second passage.")

    def _ajouter_un_element(self, ordre, texte):
        return ElementDocument.objects.create(
            page=self.page_de_test, ordre=ordre, label="text", texte=texte,
            empreinte_contenu=empreinte_du_texte(texte),
        )

    def _creer_un_job(self, status):
        return ExtractionJob.objects.create(
            page=self.page_de_test, name="Job de test garde",
            prompt_description="Extraire", status=status,
        )

    def _vieillir_le_job(self, job, age):
        """
        Force les DEUX dates dans le passe.
        / Pushes BOTH dates into the past.

        auto_now et auto_now_add empechent de les ecrire par save() : il
        faut passer par update(). On vieillit les deux parce que c'est ce
        qui arrive en vrai a un job dont le worker est mort — il n'a plus
        touche a rien depuis sa creation.
        / A job whose worker died is old on both dates.
        """
        date_dans_le_passe = timezone.now() - age
        ExtractionJob.objects.filter(pk=job.pk).update(
            created_at=date_dans_le_passe,
            updated_at=date_dans_le_passe,
        )


class GardePendantUneAnalyseTest(BaseGardeTestCase):
    """Ce qui bloque, et ce qui ne bloque pas.
    / What blocks, and what does not."""

    def test_un_job_en_attente_bloque(self):
        self._creer_un_job(ExtractionJobStatus.PENDING)

        with self.assertRaises(EditionBloqueePendantAnalyse):
            verifier_qu_aucune_analyse_ne_tourne(self.page_de_test)

    def test_un_job_en_cours_bloque(self):
        self._creer_un_job(ExtractionJobStatus.PROCESSING)

        with self.assertRaises(EditionBloqueePendantAnalyse):
            verifier_qu_aucune_analyse_ne_tourne(self.page_de_test)

    def test_un_job_termine_ne_bloque_pas(self):
        self._creer_un_job(ExtractionJobStatus.COMPLETED)

        verifier_qu_aucune_analyse_ne_tourne(self.page_de_test)

    def test_un_job_en_erreur_ne_bloque_pas(self):
        """
        Un job en erreur n'ecrira plus rien : il n'y a plus de raison de
        bloquer l'edition. / A failed job will write nothing more.
        """
        self._creer_un_job(ExtractionJobStatus.ERROR)

        verifier_qu_aucune_analyse_ne_tourne(self.page_de_test)

    def test_une_transcription_en_cours_bloque(self):
        """
        Une transcription remplace le texte de TOUS les elements de la
        page : l'editer pendant ce temps n'aurait aucun sens.
        / A transcription replaces the text of every element.
        """
        TranscriptionJob.objects.create(
            page=self.page_de_test,
            status=TranscriptionJobStatus.PROCESSING,
        )

        with self.assertRaises(EditionBloqueePendantAnalyse):
            verifier_qu_aucune_analyse_ne_tourne(self.page_de_test)

    def test_un_job_sur_une_autre_page_ne_bloque_pas(self):
        """Le blocage est par page, pas global."""
        autre_page = Page.objects.create(
            url="http://exemple.local/autre-page-garde",
            html_original="<p>o</p>", html_readability="<p>l</p>",
            text_readability="t", content_hash="autre_empreinte_garde",
        )
        ExtractionJob.objects.create(
            page=autre_page, name="Job ailleurs",
            prompt_description="Extraire",
            status=ExtractionJobStatus.PROCESSING,
        )

        verifier_qu_aucune_analyse_ne_tourne(self.page_de_test)


class DelaiDeGraceTest(BaseGardeTestCase):
    """
    Un worker mort ne doit pas condamner une page.
    / A dead worker must not condemn a page.

    LOCALISATION : hypostasis_extractor/tests/test_garde_edition.py

    Quand un worker Celery est interrompu, son job reste en base au
    statut pending ou processing, pour toujours : personne ne le repassera
    jamais en erreur. Sans delai de grace, l'edition de cette page serait
    bloquee definitivement, sans explication.

    Ce n'est pas une hypothese : le CHANGELOG du 19 juin 2026 documente
    ce cas exact, avec un nettoyage manuel a faire en shell.
    """

    def test_un_job_trop_vieux_ne_bloque_plus(self):
        job_orphelin = self._creer_un_job(ExtractionJobStatus.PROCESSING)
        self._vieillir_le_job(
            job_orphelin,
            DELAI_AVANT_DE_CONSIDERER_UN_JOB_MORT + datetime.timedelta(minutes=1),
        )

        verifier_qu_aucune_analyse_ne_tourne(self.page_de_test)

    def test_un_job_juste_sous_le_delai_bloque_encore(self):
        """Contre-epreuve : une analyse longue mais vivante bloque bien."""
        job_en_cours = self._creer_un_job(ExtractionJobStatus.PROCESSING)
        self._vieillir_le_job(
            job_en_cours,
            DELAI_AVANT_DE_CONSIDERER_UN_JOB_MORT - datetime.timedelta(minutes=1),
        )

        with self.assertRaises(EditionBloqueePendantAnalyse):
            verifier_qu_aucune_analyse_ne_tourne(self.page_de_test)

    def test_un_battement_de_coeur_garde_le_job_vivant(self):
        """
        Le cas qui compte vraiment : un job CREE il y a longtemps, mais
        qui donne encore signe de vie.

        Une analyse peut attendre en file avant de commencer. Si on ne
        regardait que la date de creation, un job qui a attendu puis qui
        tourne serait declare mort en pleine analyse — et l'edition
        passerait pendant qu'il ecrit ses ancres.
        / A job created long ago but still beating must keep blocking.
        """
        job_en_cours = self._creer_un_job(ExtractionJobStatus.PROCESSING)
        tres_vieux = timezone.now() - (
            DELAI_AVANT_DE_CONSIDERER_UN_JOB_MORT + datetime.timedelta(hours=2)
        )
        # Cree il y a longtemps, mais le dernier chunk vient d'etre traite.
        # / Created long ago, but the last chunk was just processed.
        ExtractionJob.objects.filter(pk=job_en_cours.pk).update(
            created_at=tres_vieux, updated_at=timezone.now(),
        )

        with self.assertRaises(EditionBloqueePendantAnalyse):
            verifier_qu_aucune_analyse_ne_tourne(self.page_de_test)

    def test_une_creation_recente_suffit_si_le_battement_manque(self):
        """
        L'autre sens : un job tout juste cree n'a pas encore battu.
        Regarder les deux dates evite de le declarer mort avant meme
        qu'il ait commence.
        / A brand-new job has not beaten yet; creation date covers it.
        """
        job_tout_neuf = self._creer_un_job(ExtractionJobStatus.PENDING)
        # updated_at artificiellement ancien, created_at recent.
        # / Artificially old updated_at, recent created_at.
        ExtractionJob.objects.filter(pk=job_tout_neuf.pk).update(
            updated_at=timezone.now() - datetime.timedelta(days=1),
        )

        with self.assertRaises(EditionBloqueePendantAnalyse):
            verifier_qu_aucune_analyse_ne_tourne(self.page_de_test)

    def test_une_transcription_trop_vieille_ne_bloque_plus(self):
        """Le delai de grace vaut aussi pour les transcriptions."""
        job_de_transcription = TranscriptionJob.objects.create(
            page=self.page_de_test,
            status=TranscriptionJobStatus.PROCESSING,
        )
        date_dans_le_passe = timezone.now() - (
            DELAI_AVANT_DE_CONSIDERER_UN_JOB_MORT + datetime.timedelta(minutes=1)
        )
        TranscriptionJob.objects.filter(pk=job_de_transcription.pk).update(
            created_at=date_dans_le_passe, updated_at=date_dans_le_passe,
        )

        verifier_qu_aucune_analyse_ne_tourne(self.page_de_test)


class JobAIgnorerTest(BaseGardeTestCase):
    """
    Le pipeline ne doit pas se bloquer lui-meme.
    / The pipeline must not block itself.

    LOCALISATION : hypostasis_extractor/tests/test_garde_edition.py

    Le patron du projet est : creer le job, puis lancer la tache Celery
    qui fait le travail. Une tache qui re-ingere la page avant d'analyser
    verrait donc SON PROPRE job et refuserait de travailler.
    """

    def test_le_job_ignore_ne_bloque_pas(self):
        job_du_pipeline = self._creer_un_job(ExtractionJobStatus.PROCESSING)

        verifier_qu_aucune_analyse_ne_tourne(
            self.page_de_test, job_a_ignorer=job_du_pipeline.pk,
        )

    def test_un_autre_job_bloque_malgre_l_exception(self):
        """
        On n'ignore QUE le job designe : un second job, lui, bloque
        toujours. / Only the named job is ignored.
        """
        job_du_pipeline = self._creer_un_job(ExtractionJobStatus.PROCESSING)
        self._creer_un_job(ExtractionJobStatus.PROCESSING)

        with self.assertRaises(EditionBloqueePendantAnalyse):
            verifier_qu_aucune_analyse_ne_tourne(
                self.page_de_test, job_a_ignorer=job_du_pipeline.pk,
            )

    def test_une_transcription_bloque_malgre_l_exception(self):
        """
        job_a_ignorer ne concerne que les jobs d'extraction : une
        transcription en cours reste bloquante.
        / job_a_ignorer only covers extraction jobs.
        """
        job_du_pipeline = self._creer_un_job(ExtractionJobStatus.PROCESSING)
        TranscriptionJob.objects.create(
            page=self.page_de_test,
            status=TranscriptionJobStatus.PROCESSING,
        )

        with self.assertRaises(EditionBloqueePendantAnalyse):
            verifier_qu_aucune_analyse_ne_tourne(
                self.page_de_test, job_a_ignorer=job_du_pipeline.pk,
            )


class ToutesLesOperationsSontGardeesTest(BaseGardeTestCase):
    """
    Les cinq operations d'edition refusent de travailler pendant une
    analyse. / All five edit operations refuse to run during an analysis.
    """

    def setUp(self):
        super().setUp()
        self._creer_un_job(ExtractionJobStatus.PROCESSING)

    def test_la_correction_de_texte_est_bloquee(self):
        with self.assertRaises(EditionBloqueePendantAnalyse):
            reconcilier_les_portions_de_l_element(
                self.premier_element, "Un texte corrige.",
            )

    def test_la_scission_est_bloquee(self):
        with self.assertRaises(EditionBloqueePendantAnalyse):
            scinder_un_element(self.premier_element, 5)

    def test_la_fusion_est_bloquee(self):
        with self.assertRaises(EditionBloqueePendantAnalyse):
            fusionner_deux_elements(self.premier_element, self.second_element)

    def test_le_masquage_est_bloque(self):
        with self.assertRaises(EditionBloqueePendantAnalyse):
            masquer_un_element(self.premier_element)

    def test_le_demasquage_est_bloque(self):
        """
        Demasquer rattache des portions d'ancrage : c'est une ecriture
        comme une autre, elle doit attendre elle aussi.
        / Unhiding reattaches portions: it is a write like any other.
        """
        # On masque AVANT que le job ne tourne, sinon le masquage lui-meme
        # serait refuse. / Hide before the job starts.
        ExtractionJob.objects.filter(page=self.page_de_test).update(
            status=ExtractionJobStatus.COMPLETED,
        )
        masquer_un_element(self.premier_element)
        ExtractionJob.objects.filter(page=self.page_de_test).update(
            status=ExtractionJobStatus.PROCESSING,
        )

        with self.assertRaises(EditionBloqueePendantAnalyse):
            demasquer_un_element(self.premier_element)

    def test_la_reingestion_est_bloquee(self):
        with self.assertRaises(EditionBloqueePendantAnalyse):
            reconcilier_les_elements_par_empreinte(
                self.page_de_test,
                [{"texte": "Un nouveau contenu.", "label": "text"}],
            )

    def test_rien_n_a_ete_modifie_par_une_tentative_bloquee(self):
        """
        Le refus arrive AVANT toute ecriture : une tentative bloquee ne
        laisse aucune trace.
        / The refusal comes BEFORE any write.
        """
        texte_avant = self.premier_element.texte

        with self.assertRaises(EditionBloqueePendantAnalyse):
            reconcilier_les_portions_de_l_element(
                self.premier_element, "Un texte corrige.",
            )

        self.premier_element.refresh_from_db()
        self.assertEqual(self.premier_element.texte, texte_avant)
        self.assertEqual(self.page_de_test.elements.count(), 2)


class InterrogationSansLeverTest(BaseGardeTestCase):
    """
    Pour l'interface : savoir sans declencher d'erreur.
    / For the UI: knowing without raising.
    """

    def test_repond_vrai_pendant_une_analyse(self):
        self._creer_un_job(ExtractionJobStatus.PROCESSING)

        self.assertTrue(une_analyse_tourne_sur_la_page(self.page_de_test))

    def test_repond_faux_quand_tout_est_termine(self):
        self._creer_un_job(ExtractionJobStatus.COMPLETED)

        self.assertFalse(une_analyse_tourne_sur_la_page(self.page_de_test))

    def test_le_message_d_erreur_est_comprehensible(self):
        """
        Ce n'est pas une erreur technique : c'est une situation normale et
        passagere, le message doit le dire.
        / Not a technical error: a normal, temporary situation.
        """
        self._creer_un_job(ExtractionJobStatus.PROCESSING)

        with self.assertRaises(EditionBloqueePendantAnalyse) as contexte:
            verifier_qu_aucune_analyse_ne_tourne(self.page_de_test)

        message = str(contexte.exception)
        self.assertIn("analyse est en cours", message)
        self.assertIn("bloquee le temps", message)
