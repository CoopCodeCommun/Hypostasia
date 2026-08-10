"""
Tests du routage de l'analyse selon le moteur de la page (BR-C).
/ Analysis routing by page engine tests (wiring phase BR-C).

LOCALISATION : front/tests/test_analyse_routage.py

SPEC-ancrage-par-element-v2 § 9 (double moteur) + cahier
PLAN/branchement-moteur-ancrage-cahier-des-charges.md, phase BR-C : la
vue `analyser` cree toujours le meme ExtractionJob, mais la tache
lancee depend du moteur de la page — `analyser_page_task` (offsets)
pour une page ANCIEN, `analyser_une_page_avec_le_moteur_element`
(portions) pour une page ELEMENT. Les deux tachent prennent la meme
cle de job : le routage est UNE decision, a UN endroit.
/ The view creates the same ExtractionJob; only the launched task
differs, chosen by the page's engine flag.
"""

import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (
    AIModel,
    Configuration,
    MoteurDePage,
    Page,
    Provider,
)
from hypostasis_extractor.models import (
    AnalyseurSyntaxique,
    ExtractionJob,
    PromptPiece,
)

Utilisateur = get_user_model()


class BaseAnalyseRoutageTest(TestCase):
    """
    Socle commun : utilisateur, config IA, analyseur.
    / Common ground: user, AI config, analyzer.
    """

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="analyste", password="motdepasse",
        )
        self.client.force_login(self.proprietaire)

        self.modele_ia = AIModel.objects.create(
            name="Mock BR-C", provider=Provider.MOCK,
            model_name="gemini-2.5-flash", is_active=True,
        )
        configuration = Configuration.get_solo()
        configuration.ai_active = True
        configuration.ai_model = self.modele_ia
        configuration.save()

        self.analyseur = AnalyseurSyntaxique.objects.create(
            name="Analyseur BR-C", type_analyseur="analyser",
        )
        PromptPiece.objects.create(
            analyseur=self.analyseur, name="Instruction",
            content="Extraire.", order=0,
        )

    def _creer_une_page(self, suffixe, moteur):
        return Page.objects.create(
            url=f"http://exemple.local/brc-{suffixe}",
            html_original="<p>o</p>", html_readability="<p>l</p>",
            text_readability="texte a analyser",
            content_hash=f"hash-brc-{suffixe}",
            owner=self.proprietaire, moteur=moteur,
        )

    def _analyser(self, page):
        return self.client.post(
            f"/lire/{page.pk}/analyser/",
            data={"analyseur_id": self.analyseur.pk},
            HTTP_HX_REQUEST="true",
        )

class RoutageDeLAnalyseTest(BaseAnalyseRoutageTest):
    """
    Le bouton « analyser » choisit la tache selon le moteur.
    / The "analyse" button picks the task from the engine flag.
    """

    @mock.patch(
        "hypostasis_extractor.tasks_element"
        ".analyser_une_page_avec_le_moteur_element.delay"
    )
    @mock.patch("front.tasks.analyser_page_task.delay")
    def test_une_page_ancienne_route_vers_l_ancien_moteur(
        self, ancien_delay, element_delay,
    ):
        # Aucune regression : une page ANCIEN part exactement comme
        # avant. / No regression: an OLD page goes exactly as before.
        page = self._creer_une_page("ancienne", MoteurDePage.ANCIEN)

        reponse = self._analyser(page)

        self.assertEqual(reponse.status_code, 200)
        job = ExtractionJob.objects.get(page=page)
        ancien_delay.assert_called_once_with(job.pk)
        element_delay.assert_not_called()

    @mock.patch(
        "hypostasis_extractor.tasks_element"
        ".analyser_une_page_avec_le_moteur_element.delay"
    )
    @mock.patch("front.tasks.analyser_page_task.delay")
    def test_une_page_element_route_vers_le_moteur_element(
        self, ancien_delay, element_delay,
    ):
        # La premiere vraie consequence du flag BR-A : la meme vue, le
        # meme job, mais la tache par ELEMENT (ancres par portions).
        # / Same view, same job, the ELEMENT task.
        page = self._creer_une_page("element", MoteurDePage.ELEMENT)

        reponse = self._analyser(page)

        self.assertEqual(reponse.status_code, 200)
        job = ExtractionJob.objects.get(page=page)
        element_delay.assert_called_once_with(job.pk)
        ancien_delay.assert_not_called()

        # Le retour utilisateur reste le meme toast (le moteur est un
        # detail d'implementation pour la personne qui lit).
        # / Same toast either way: the engine is an implementation detail.
        declencheurs = json.loads(reponse["HX-Trigger"])
        self.assertIn("showToast", declencheurs)


class NettoyageDesJobsBloquesTest(TestCase):
    """
    Le juge de blocage distingue un job EN FILE d'un job FIGE
    (relecture BR-C, defaut n°1). / The staleness judge tells a queued
    job from a stalled one.
    """

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="juge", password="motdepasse",
        )
        self.page = Page.objects.create(
            url="http://exemple.local/brc-juge",
            html_original="<p>o</p>", html_readability="<p>l</p>",
            text_readability="texte", content_hash="hash-brc-juge",
            owner=self.proprietaire,
        )

    def _creer_un_job(self, status, anciennete):
        from django.utils import timezone

        job = ExtractionJob.objects.create(page=self.page, status=status)
        ExtractionJob.objects.filter(pk=job.pk).update(
            updated_at=timezone.now() - anciennete,
        )
        job.refresh_from_db()
        return job

    def test_un_job_pending_en_file_n_est_pas_tue(self):
        # Un seul worker : attendre 10 minutes en file est NORMAL. Le
        # tuer annulait un job parfaitement sain (et la transition
        # atomique de la tache ELEMENT ne le ressuscite pas).
        # / Waiting 10 min in queue is normal with one worker.
        from datetime import timedelta

        from front.views import _verifier_et_nettoyer_job_bloque

        job = self._creer_un_job("pending", timedelta(minutes=10))

        self.assertFalse(_verifier_et_nettoyer_job_bloque(job))
        job.refresh_from_db()
        self.assertEqual(job.status, "pending")

    def test_un_job_pending_abandonne_est_tue(self):
        # Au-dela du delai de la garde d'edition (90 min), le job est
        # vraiment mort. / Beyond the edit-guard ceiling, it is dead.
        from datetime import timedelta

        from front.views import _verifier_et_nettoyer_job_bloque

        job = self._creer_un_job("pending", timedelta(minutes=120))

        self.assertTrue(_verifier_et_nettoyer_job_bloque(job))
        job.refresh_from_db()
        self.assertEqual(job.status, "error")

    def test_un_job_processing_fige_est_tue(self):
        # PROCESSING sans battement depuis 10 minutes : mort (les deux
        # moteurs battent le coeur a chaque chunk).
        # / PROCESSING with no heartbeat for 10 min: dead.
        from datetime import timedelta

        from front.views import _verifier_et_nettoyer_job_bloque

        job = self._creer_un_job("processing", timedelta(minutes=10))

        self.assertTrue(_verifier_et_nettoyer_job_bloque(job))
        job.refresh_from_db()
        self.assertEqual(job.status, "error")


class CourseDuFlagMoteurTest(BaseAnalyseRoutageTest):
    """
    La tache ANCIENNE revalide le moteur a l'execution (relecture BR-C,
    defaut n°2) : un job lance pendant l'ingestion Docling peut
    s'executer APRES qu'elle a pose le flag ELEMENT.
    / The old task re-checks the engine at run time.
    """

    @mock.patch(
        "hypostasis_extractor.services.analyse_par_element"
        ".lancer_l_analyse_d_une_page",
        return_value={
            "chunks": 1, "extractions": 0, "portions": 0,
            "chunks_en_erreur": 0, "extractions_refusees": 0,
        },
    )
    def test_la_tache_ancienne_reroute_une_page_devenue_element(
        self, analyse_element,
    ):
        from core.models import ElementDocument, empreinte_du_texte

        page = self._creer_une_page("course", MoteurDePage.ANCIEN)
        job = ExtractionJob.objects.create(
            page=page, ai_model=self.modele_ia, name="Analyse",
            prompt_description="Extraire.", status="pending",
        )

        # L'ingestion Docling termine entre le clic et l'execution :
        # la page devient ELEMENT. / Docling finishes in between.
        ElementDocument.objects.create(
            page=page, ordre=0, label="text", texte="un element",
            empreinte_contenu=empreinte_du_texte("un element"),
        )
        page.moteur = MoteurDePage.ELEMENT
        page.save(update_fields=["moteur"])

        from front.tasks import analyser_page_task
        analyser_page_task(job.pk)

        # Le chemin ELEMENT a ete pris, avec la bonne page et le bon
        # job : jamais d'extractions a offsets sans portions sur une
        # page ELEMENT. (COMPLETED est pose par le service mocke ici —
        # on ne peut donc pas l'asserter.)
        # / The ELEMENT path ran with the right page and job; COMPLETED
        # is set by the mocked service, so it cannot be asserted here.
        analyse_element.assert_called_once()
        page_recue, job_recu = analyse_element.call_args.args
        self.assertEqual(page_recue.pk, page.pk)
        self.assertEqual(job_recu.pk, job.pk)


class ProtectionsDeLaVueAnalyserTest(BaseAnalyseRoutageTest):
    """
    Protections de la vue pour une page ELEMENT (relecture BR-C, n°6).
    / View protections for an ELEMENT page.
    """

    @mock.patch(
        "hypostasis_extractor.tasks_element"
        ".analyser_une_page_avec_le_moteur_element.delay"
    )
    @mock.patch("front.tasks.analyser_page_task.delay")
    def test_un_job_en_cours_ne_relance_rien(
        self, ancien_delay, element_delay,
    ):
        page = self._creer_une_page("encours", MoteurDePage.ELEMENT)
        ExtractionJob.objects.create(page=page, status="processing")

        reponse = self._analyser(page)

        self.assertEqual(reponse.status_code, 200)
        ancien_delay.assert_not_called()
        element_delay.assert_not_called()
        self.assertEqual(ExtractionJob.objects.filter(page=page).count(), 1)

    @mock.patch(
        "hypostasis_extractor.tasks_element"
        ".analyser_une_page_avec_le_moteur_element.delay"
    )
    @mock.patch("front.tasks.analyser_page_task.delay")
    def test_nettoyer_ia_purge_extractions_et_ancres(
        self, ancien_delay, element_delay,
    ):
        # La purge d'une extraction ELEMENT emporte ses ancres (CASCADE)
        # mais jamais l'element (PROTECT). / Purging an ELEMENT
        # extraction cascades its anchors, never the element.
        from core.models import ElementDocument, empreinte_du_texte
        from hypostasis_extractor.models import (
            AncrageExtraction, ExtractedEntity,
        )

        page = self._creer_une_page("purge", MoteurDePage.ELEMENT)
        element = ElementDocument.objects.create(
            page=page, ordre=0, label="text",
            texte="Le jugement des personnes compte.",
            empreinte_contenu=empreinte_du_texte(
                "Le jugement des personnes compte.",
            ),
        )
        vieux_job = ExtractionJob.objects.create(page=page, status="completed")
        extraction = ExtractedEntity.objects.create(
            job=vieux_job, extraction_class="principe",
            extraction_text="jugement", start_char=3, end_char=11,
        )
        AncrageExtraction.objects.create(
            extraction=extraction, element=element,
            ordre_dans_extraction=0,
            debut_dans_element=3, fin_dans_element=11,
        )

        reponse = self.client.post(
            f"/lire/{page.pk}/analyser/",
            data={"analyseur_id": self.analyseur.pk, "nettoyer_ia": "1"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(
            ExtractedEntity.objects.filter(pk=extraction.pk).exists(),
        )
        self.assertEqual(AncrageExtraction.objects.count(), 0)
        self.assertTrue(ElementDocument.objects.filter(pk=element.pk).exists())
        element_delay.assert_called_once()
