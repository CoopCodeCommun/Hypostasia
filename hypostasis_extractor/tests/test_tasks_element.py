"""
Tests des taches Celery du moteur ELEMENT — phase H.
/ Tests for the ELEMENT engine's Celery tasks — phase H.

LOCALISATION : hypostasis_extractor/tests/test_tasks_element.py

Lancer avec :
    docker exec hypostasia_dev_web uv run python manage.py test \\
        hypostasis_extractor.tests.test_tasks_element

Les taches sont appelees directement, pas via Celery : on teste ce
qu'elles font, pas la file d'attente.
/ Tasks are called directly; we test what they do, not the queue.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (
    AIModel,
    Configuration,
    ElementDocument,
    Page,
    empreinte_du_texte,
)
from hypostasis_extractor.models import (
    ExtractedEntity,
    ExtractionJob,
    ExtractionJobStatus,
)
from hypostasis_extractor.tasks_element import (
    analyser_une_page_avec_le_moteur_element,
)


class BaseTacheTestCase(TestCase):
    """Socle commun. / Common ground."""

    def setUp(self):
        self.utilisateur_de_test = get_user_model().objects.create_user(
            username="testeur_taches", password="motdepasse_de_test_123",
        )
        self.page_de_test = Page.objects.create(
            url="http://exemple.local/page-tache",
            html_original="x", html_readability="x", text_readability="x",
            content_hash="empreinte_tache", owner=self.utilisateur_de_test,
        )
        self.modele = AIModel.objects.create(model_choice="gemini-2.5-flash")
        self.job = ExtractionJob.objects.create(
            page=self.page_de_test, ai_model=self.modele,
            name="Analyse par element", prompt_description="Extraire",
            status=ExtractionJobStatus.PENDING,
        )
        # L'IA est activee par defaut dans ces tests.
        # / AI is enabled by default in these tests.
        configuration = Configuration.get_solo()
        configuration.ai_active = True
        configuration.save()

    def _ajouter_un_element(self, texte, ordre=0, masque=False):
        return ElementDocument.objects.create(
            page=self.page_de_test, ordre=ordre, label="text", texte=texte,
            empreinte_contenu=empreinte_du_texte(texte), masque=masque,
        )


class KillSwitchIaTest(BaseTacheTestCase):
    """
    L'IA desactivee doit couper la depense.
    / A disabled AI must stop the spending.
    """

    def test_l_ia_desactivee_annule_l_analyse(self):
        """
        Sans cette verification, un job lance pendant que l'IA est coupee
        partirait quand meme appeler un fournisseur payant.
        / Without this, a job would spend money while the AI is off.
        """
        self._ajouter_un_element("Un passage a analyser.")
        configuration = Configuration.get_solo()
        configuration.ai_active = False
        configuration.save()

        resultat = analyser_une_page_avec_le_moteur_element(self.job.pk)

        self.job.refresh_from_db()
        self.assertEqual(resultat, {"erreur": "IA desactivee"})
        self.assertEqual(self.job.status, ExtractionJobStatus.ERROR)
        self.assertIn("desactivee", self.job.error_message)
        # Aucune extraction n'a ete creee.
        # / No extraction was created.
        self.assertEqual(ExtractedEntity.objects.count(), 0)

    def test_l_ia_desactivee_n_appelle_pas_le_service(self):
        """La verification arrive AVANT le moindre appel."""
        self._ajouter_un_element("Un passage.")
        configuration = Configuration.get_solo()
        configuration.ai_active = False
        configuration.save()

        with patch(
            "hypostasis_extractor.services.analyse_par_element."
            "lancer_l_analyse_d_une_page",
        ) as analyse_simulee:
            analyser_une_page_avec_le_moteur_element(self.job.pk)

        analyse_simulee.assert_not_called()


class PagesSansElementTest(BaseTacheTestCase):
    """
    Une page sans element n'a rien a analyser.
    / A page with no element has nothing to analyse.
    """

    def test_une_page_sans_element_est_signalee(self):
        """
        Rendre « 0 extraction » sans explication laisserait croire que la
        page ne contient rien d'interessant. La vraie raison est qu'elle
        n'a pas ete ingeree.
        / "0 extractions" without explanation would be misleading.
        """
        resultat = analyser_une_page_avec_le_moteur_element(self.job.pk)

        self.job.refresh_from_db()
        self.assertEqual(resultat, {"erreur": "page sans element"})
        self.assertEqual(self.job.status, ExtractionJobStatus.ERROR)
        self.assertIn("aucun element", self.job.error_message)

    def test_une_page_dont_tout_est_masque_est_signalee(self):
        """Tout masquer revient a n'avoir aucun element utile."""
        self._ajouter_un_element("Du bruit.", masque=True)

        resultat = analyser_une_page_avec_le_moteur_element(self.job.pk)

        self.assertEqual(resultat, {"erreur": "page sans element"})


class DeroulementNominalTest(BaseTacheTestCase):
    """
    Le chemin normal, avec un LLM simule.
    / The normal path, with a simulated LLM.
    """

    def test_l_analyse_cree_les_extractions_et_les_ancres(self):
        """
        Le chemin complet, avec un LLM simule injecte dans le service.
        / The full path, with a simulated LLM injected in the service.
        """
        element = self._ajouter_un_element("Le jugement des personnes compte.")

        def faux_llm(texte_du_chunk, job):
            return [{
                "extraction_class": "principe", "extraction_text": "jugement",
                "debut": 3, "fin": 11, "attributes": {},
            }]

        # On remplace l'appel au LLM, pas l'analyse elle-meme : tout le
        # reste du chemin est donc reellement exerce.
        # / Only the LLM call is replaced; the rest really runs.
        import hypostasis_extractor.services.analyse_par_element as module_analyse
        appel_d_origine = module_analyse.appeler_langextract_sur_un_chunk
        module_analyse.appeler_langextract_sur_un_chunk = faux_llm
        try:
            bilan = analyser_une_page_avec_le_moteur_element(self.job.pk)
        finally:
            module_analyse.appeler_langextract_sur_un_chunk = appel_d_origine

        self.job.refresh_from_db()
        self.assertEqual(self.job.status, ExtractionJobStatus.COMPLETED)
        self.assertEqual(bilan["extractions"], 1)
        extraction = ExtractedEntity.objects.get()
        portion = extraction.ancrages.get()
        self.assertEqual(portion.element, element)
        self.assertEqual(portion.texte_de_la_portion(), "jugement")

    def test_la_duree_est_enregistree(self):
        """Pour suivre le cout et reperer les analyses anormalement longues."""
        self._ajouter_un_element("Un passage.")

        with patch(
            "hypostasis_extractor.services.analyse_par_element."
            "lancer_l_analyse_d_une_page",
            return_value={
                "chunks": 1, "extractions": 0, "portions": 0,
                "chunks_en_erreur": 0, "extractions_refusees": 0,
            },
        ):
            analyser_une_page_avec_le_moteur_element(self.job.pk)

        self.job.refresh_from_db()
        self.assertIsNotNone(self.job.processing_time_seconds)
        self.assertGreaterEqual(self.job.processing_time_seconds, 0)


class ProtectionsDeLaTacheTest(BaseTacheTestCase):
    """
    Double execution, modele absent, enregistrement Celery.
    / Double run, missing model, Celery registration.
    """

    def test_un_job_deja_en_cours_n_est_pas_relance(self):
        """
        Celery peut redelivrer un message : worker tue, reessai, double
        envoi. Deux taches sur le meme job purgeraient puis insereraient
        chacune leurs extractions — doublons et compteur faux.
        / Two tasks on one job would duplicate everything.
        """
        self._ajouter_un_element("Un passage.")
        self.job.status = ExtractionJobStatus.PROCESSING
        self.job.save(update_fields=["status"])

        resultat = analyser_une_page_avec_le_moteur_element(self.job.pk)

        self.assertEqual(resultat, {"erreur": "job deja en cours ou termine"})

    def test_un_job_deja_termine_n_est_pas_relance(self):
        """Une redelivrance apres coup ne doit pas tout refaire."""
        self._ajouter_un_element("Un passage.")
        self.job.status = ExtractionJobStatus.COMPLETED
        self.job.save(update_fields=["status"])

        resultat = analyser_une_page_avec_le_moteur_element(self.job.pk)

        self.assertEqual(resultat, {"erreur": "job deja en cours ou termine"})

    def test_un_job_sans_modele_est_signale_clairement(self):
        """
        Sans modele, chaque chunk echouerait et le job finirait avec
        « les N chunks ont echoue » — un message qui fait croire a une
        panne du fournisseur alors que c'est une configuration incomplete.
        / The failure would look like a provider outage.
        """
        self._ajouter_un_element("Un passage.")
        self.job.ai_model = None
        self.job.save(update_fields=["ai_model"])

        resultat = analyser_une_page_avec_le_moteur_element(self.job.pk)

        self.job.refresh_from_db()
        self.assertEqual(resultat, {"erreur": "modele absent"})
        self.assertIn("modele d'IA", self.job.error_message)

    def test_les_taches_sont_enregistrees_aupres_de_celery(self):
        """
        autodiscover_tasks ne charge que <app>/tasks.py. Les taches du
        moteur ELEMENT vivent ailleurs : sans l'import explicite, un
        worker repondrait « Received unregistered task », le message
        serait jete, et le job resterait PENDING pour toujours — bloquant
        l'edition de sa page pendant 90 minutes.
        / Without the explicit import, the worker silently drops the task.
        """
        from hypostasia.celery import celery_app

        celery_app.loader.import_default_modules()
        taches_enregistrees = set(celery_app.tasks)

        self.assertIn(
            "hypostasis_extractor.tasks_element."
            "analyser_une_page_avec_le_moteur_element",
            taches_enregistrees,
        )
        self.assertIn(
            "hypostasis_extractor.tasks_element.ingerer_un_fichier_avec_docling",
            taches_enregistrees,
        )


class JobIntrouvableTest(BaseTacheTestCase):
    """Robustesse : un job supprime entre-temps. / A job deleted meanwhile."""

    def test_un_job_inexistant_ne_fait_pas_planter_le_worker(self):
        resultat = analyser_une_page_avec_le_moteur_element(999999)

        self.assertEqual(resultat, {"erreur": "job introuvable"})


class NotificationTest(BaseTacheTestCase):
    """
    L'utilisateur est prevenu, et une notification qui echoue ne casse
    rien. / The user is notified, and a failed notification breaks nothing.
    """

    def test_l_utilisateur_est_prevenu_a_la_fin(self):
        self._ajouter_un_element("Un passage.")

        with patch(
            "hypostasis_extractor.services.analyse_par_element."
            "lancer_l_analyse_d_une_page",
            return_value={
                "chunks": 1, "extractions": 0, "portions": 0,
                "chunks_en_erreur": 0, "extractions_refusees": 0,
            },
        ), patch("front.tasks.notifier_tache_terminee") as notification:
            analyser_une_page_avec_le_moteur_element(self.job.pk)

        notification.assert_called_once()
        arguments = notification.call_args.kwargs
        self.assertEqual(arguments["user_pk"], self.utilisateur_de_test.pk)
        self.assertEqual(arguments["tache_type"], "analyse")

    def test_une_notification_qui_echoue_ne_fait_pas_echouer_l_analyse(self):
        """
        L'analyse a reussi et couté de l'argent. Une panne du canal de
        notification ne doit pas la transformer en echec.
        / A notification failure must not undo a successful, paid analysis.
        """
        self._ajouter_un_element("Un passage.")

        with patch(
            "hypostasis_extractor.services.analyse_par_element."
            "lancer_l_analyse_d_une_page",
            return_value={
                "chunks": 1, "extractions": 0, "portions": 0,
                "chunks_en_erreur": 0, "extractions_refusees": 0,
            },
        ), patch(
            "front.tasks.notifier_tache_terminee",
            side_effect=RuntimeError("canal indisponible"),
        ):
            # Le point du test : la panne de notification ne remonte pas.
            # Sans le try/except de _prevenir_l_utilisateur, cette ligne
            # leverait RuntimeError et la tache serait comptee en echec.
            # / The point: the notification failure does not bubble up.
            bilan = analyser_une_page_avec_le_moteur_element(self.job.pk)

        self.assertEqual(bilan["chunks"], 1)
        self.assertEqual(bilan["chunks_en_erreur"], 0)

    def test_une_page_sans_proprietaire_ne_notifie_personne(self):
        """Pas de destinataire, pas de notification, pas d'erreur."""
        self.page_de_test.owner = None
        self.page_de_test.save(update_fields=["owner"])
        self._ajouter_un_element("Un passage.")

        with patch(
            "hypostasis_extractor.services.analyse_par_element."
            "lancer_l_analyse_d_une_page",
            return_value={
                "chunks": 1, "extractions": 0, "portions": 0,
                "chunks_en_erreur": 0, "extractions_refusees": 0,
            },
        ), patch("front.tasks.notifier_tache_terminee") as notification:
            analyser_une_page_avec_le_moteur_element(self.job.pk)

        notification.assert_not_called()


import shutil
import tempfile

from django.test import override_settings

MEDIA_JETABLE_INGESTION = tempfile.mkdtemp(prefix="test-taches-ingestion-")


@override_settings(MEDIA_ROOT=MEDIA_JETABLE_INGESTION)
class IngestionResoutLeCheminTest(BaseTacheTestCase):
    """
    La tache d'ingestion resout le chemin depuis page.source_file
    (relecture BR-B, defaut n°5 : la vue ne connait pas le stockage).
    / The ingestion task resolves the path from page.source_file.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Media jetable : rien ne s'accumule hors du run.
        # / Throwaway media dir, removed after the class runs.
        cls.addClassCleanup(
            shutil.rmtree, MEDIA_JETABLE_INGESTION, ignore_errors=True,
        )

    def test_l_ingestion_resout_le_chemin_depuis_source_file(self):
        from django.core.files.base import ContentFile

        from hypostasis_extractor.tasks_element import (
            ingerer_un_fichier_avec_docling,
        )

        self.page_de_test.source_file.save(
            "resolution.md", ContentFile(b"# Titre\n\nTexte."), save=True,
        )

        with patch(
            "hypostasis_extractor.services.ingestion_docling"
            ".ingerer_un_fichier",
            return_value=[],
        ) as ingestion:
            resultat = ingerer_un_fichier_avec_docling(self.page_de_test.pk)

        self.assertEqual(resultat, {"elements": 0})
        ingestion.assert_called_once_with(
            self.page_de_test, self.page_de_test.source_file.path,
        )

    def test_une_page_sans_fichier_source_est_signalee(self):
        # Pas de chemin explicite ET pas de source_file : la tache le
        # dit proprement au lieu de lever en plein worker.
        # / No explicit path and no source file: clean error, no crash.
        from hypostasis_extractor.tasks_element import (
            ingerer_un_fichier_avec_docling,
        )

        resultat = ingerer_un_fichier_avec_docling(self.page_de_test.pk)

        self.assertIn("erreur", resultat)


class QueueDedieeDoclingTest(TestCase):
    """
    L'ingestion Docling part sur une file dediee a concurrence 1
    (relecture BR-B, defaut n°1) : jamais deux conversions en meme
    temps sur le serveur 8 Go partage avec la production.
    / Docling ingestion goes to a dedicated concurrency-1 queue.
    """

    def test_l_ingestion_est_routee_vers_la_file_dediee(self):
        from hypostasia.celery import celery_app

        routes = celery_app.conf.task_routes or {}
        route = routes.get(
            "hypostasis_extractor.tasks_element.ingerer_un_fichier_avec_docling",
        )
        self.assertIsNotNone(route, "aucune route pour l'ingestion Docling")
        self.assertEqual(route.get("queue"), "ingestion_docling")
