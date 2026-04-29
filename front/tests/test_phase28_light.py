"""
Tests de validation pour la PHASE-28-light : Synthese deliberative.
/ Validation tests for PHASE-28-light: Deliberative synthesis.

Lancer avec : uv run python manage.py test front.tests.test_phase28_light -v2
/ Run with:    uv run python manage.py test front.tests.test_phase28_light -v2
"""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, RequestFactory, override_settings

from core.models import AIModel, Configuration, Dossier, Page
from hypostasis_extractor.models import (
    AnalyseurSyntaxique, CommentaireExtraction, ExtractedEntity,
    ExtractionJob, PromptPiece,
)


# =============================================================================
# Helpers pour creer les fixtures de test
# / Helpers to create test fixtures
# =============================================================================


def creer_fixtures_synthese():
    """
    Cree les fixtures minimales pour tester la synthese deliberative.
    Retourne un dictionnaire avec tous les objets crees.
    / Creates minimal fixtures to test deliberative synthesis.
    Returns a dict with all created objects.
    """
    utilisateur_test = User.objects.create_user(
        username="testeur_synthese", password="test1234",
    )

    dossier_test = Dossier.objects.create(
        name="Dossier synthese test", owner=utilisateur_test,
    )

    page_source = Page.objects.create(
        title="Page source synthese",
        text_readability="L'IA est une revolution. Les communs sont une alternative.",
        html_readability="<p>L'IA est une revolution.</p><p>Les communs sont une alternative.</p>",
        html_original="<p>L'IA est une revolution.</p><p>Les communs sont une alternative.</p>",
        content_hash="abc123",
        dossier=dossier_test,
        source_type="web",
        owner=utilisateur_test,
    )

    modele_ia_test = AIModel.objects.create(
        name="Mock Synthese",
        model_choice="mock_default",
        is_active=True,
    )

    Configuration.objects.all().delete()
    Configuration.objects.create(
        ai_active=True,
        ai_model=modele_ia_test,
    )

    analyseur_synthese = AnalyseurSyntaxique.objects.create(
        name="Synthese deliberative test",
        is_active=True,
        type_analyseur="synthetiser",
        # PHASE-29 : les deux bool actifs pour que le prompt contienne TEXTE + HYPOSTASES
        # / PHASE-29: both bools active so prompt contains TEXT + HYPOSTASES
        inclure_extractions=True,
        inclure_texte_original=True,
    )

    PromptPiece.objects.create(
        analyseur=analyseur_synthese,
        name="Contexte test",
        role="context",
        content="Tu es un moteur de synthese deliberative.",
        order=0,
    )

    # Job d'analyse complete avec des entites / Completed analysis job with entities
    job_analyse = ExtractionJob.objects.create(
        page=page_source,
        ai_model=modele_ia_test,
        name="Analyse test",
        prompt_description="Test prompt",
        status="completed",
        raw_result={"analyseur_id": 1},
    )

    entite_consensuelle = ExtractedEntity.objects.create(
        job=job_analyse,
        extraction_class="donnee",
        extraction_text="L'IA est une revolution.",
        start_char=0,
        end_char=24,
        statut_debat="consensuel",
    )

    entite_controversee = ExtractedEntity.objects.create(
        job=job_analyse,
        extraction_class="hypothese",
        extraction_text="Les communs sont une alternative.",
        start_char=25,
        end_char=57,
        statut_debat="controverse",
    )

    entite_non_pertinente = ExtractedEntity.objects.create(
        job=job_analyse,
        extraction_class="indice",
        extraction_text="Bruit de fond non pertinent.",
        start_char=58,
        end_char=85,
        statut_debat="non_pertinent",
    )

    entite_masquee = ExtractedEntity.objects.create(
        job=job_analyse,
        extraction_class="mode",
        extraction_text="Entite masquee invisible.",
        start_char=86,
        end_char=110,
        statut_debat="discutable",
    )
    # Forcer masquee=True via update() car save() synchronise avec statut_debat
    # / Force masquee=True via update() because save() syncs with statut_debat
    ExtractedEntity.objects.filter(pk=entite_masquee.pk).update(masquee=True)

    # Commentaires sur les entites / Comments on entities
    commentaire_alice = CommentaireExtraction.objects.create(
        entity=entite_consensuelle,
        user=utilisateur_test,
        commentaire="Point solide et bien argumente.",
    )

    return {
        "utilisateur": utilisateur_test,
        "dossier": dossier_test,
        "page_source": page_source,
        "modele_ia": modele_ia_test,
        "analyseur": analyseur_synthese,
        "job_analyse": job_analyse,
        "entite_consensuelle": entite_consensuelle,
        "entite_controversee": entite_controversee,
        "entite_non_pertinente": entite_non_pertinente,
        "entite_masquee": entite_masquee,
        "commentaire_alice": commentaire_alice,
    }


# =============================================================================
# Tests construction du prompt
# / Prompt construction tests
# =============================================================================


class PromptSyntheseTest(TestCase):
    """Tests pour _construire_prompt_synthese().
    / Tests for _construire_prompt_synthese()."""

    def setUp(self):
        self.fixtures = creer_fixtures_synthese()

    def test_prompt_contient_texte_original(self):
        """Le prompt contient le texte original de la page source."""
        from front.tasks import _construire_prompt_synthese
        prompt = _construire_prompt_synthese(
            self.fixtures["page_source"], self.fixtures["job_analyse"],
            self.fixtures["analyseur"],
        )
        self.assertIn("L'IA est une revolution", prompt)
        self.assertIn("=== TEXTE ORIGINAL ===", prompt)

    def test_prompt_contient_statuts(self):
        """Le prompt contient les statuts des entites (CONSENSUEL, CONTROVERSE)."""
        from front.tasks import _construire_prompt_synthese
        prompt = _construire_prompt_synthese(
            self.fixtures["page_source"], self.fixtures["job_analyse"],
            self.fixtures["analyseur"],
        )
        self.assertIn("[CONSENSUEL]", prompt)
        self.assertIn("[CONTROVERSE]", prompt)

    def test_prompt_exclut_non_pertinent(self):
        """Les entites non_pertinent sont exclues du prompt."""
        from front.tasks import _construire_prompt_synthese
        prompt = _construire_prompt_synthese(
            self.fixtures["page_source"], self.fixtures["job_analyse"],
            self.fixtures["analyseur"],
        )
        self.assertNotIn("Bruit de fond non pertinent", prompt)

    def test_prompt_exclut_masquees(self):
        """Les entites masquees sont exclues du prompt."""
        from front.tasks import _construire_prompt_synthese
        prompt = _construire_prompt_synthese(
            self.fixtures["page_source"], self.fixtures["job_analyse"],
            self.fixtures["analyseur"],
        )
        self.assertNotIn("Entite masquee invisible", prompt)

    def test_prompt_tri_par_statut(self):
        """Les entites consensuelles apparaissent avant les controversees."""
        from front.tasks import _construire_prompt_synthese
        prompt = _construire_prompt_synthese(
            self.fixtures["page_source"], self.fixtures["job_analyse"],
            self.fixtures["analyseur"],
        )
        position_consensuel = prompt.index("[CONSENSUEL]")
        position_controverse = prompt.index("[CONTROVERSE]")
        self.assertLess(position_consensuel, position_controverse)

    def test_prompt_contient_commentaires(self):
        """Le prompt contient les commentaires des contributeurs."""
        from front.tasks import _construire_prompt_synthese
        prompt = _construire_prompt_synthese(
            self.fixtures["page_source"], self.fixtures["job_analyse"],
            self.fixtures["analyseur"],
        )
        self.assertIn("testeur_synthese", prompt)
        self.assertIn("Point solide et bien argumente", prompt)

    def test_prompt_contient_resume_ia_depuis_attributes(self):
        """Le prompt inclut le resume IA stocke dans le JSONField attributes."""
        # Ajouter un resume IA a l'entite consensuelle / Add AI summary to consensual entity
        entite = self.fixtures["entite_consensuelle"]
        entite.attributes = {"resume": "L'IA transforme le monde durablement."}
        entite.save(update_fields=["attributes"])

        from front.tasks import _construire_prompt_synthese
        prompt = _construire_prompt_synthese(
            self.fixtures["page_source"], self.fixtures["job_analyse"],
            self.fixtures["analyseur"],
        )
        self.assertIn("L'IA transforme le monde durablement.", prompt)
        self.assertIn("Résumé IA", prompt)

    def test_prompt_contient_section_consigne(self):
        """Le prompt contient la section CONSIGNE finale."""
        from front.tasks import _construire_prompt_synthese
        prompt = _construire_prompt_synthese(
            self.fixtures["page_source"], self.fixtures["job_analyse"],
            self.fixtures["analyseur"],
        )
        self.assertIn("=== CONSIGNE ===", prompt)
        self.assertIn("synthèse délibérative", prompt)

    def test_prompt_sans_entites_affiche_message(self):
        """Si aucune entite valide, le prompt contient un message explicite."""
        # Supprimer toutes les entites du job / Delete all entities from the job
        ExtractedEntity.objects.filter(job=self.fixtures["job_analyse"]).delete()

        from front.tasks import _construire_prompt_synthese
        prompt = _construire_prompt_synthese(
            self.fixtures["page_source"], self.fixtures["job_analyse"],
            self.fixtures["analyseur"],
        )
        self.assertIn("(aucune hypostase extraite)", prompt)


# =============================================================================
# Tests action synthetiser()
# / synthetiser() action tests
# =============================================================================


class SynthetiserActionTest(TestCase):
    """Tests pour l'action synthetiser() du LectureViewSet.
    / Tests for the synthetiser() action on LectureViewSet."""

    def setUp(self):
        self.fixtures = creer_fixtures_synthese()
        self.client.login(username="testeur_synthese", password="test1234")

    def test_synthetiser_requiert_authentification(self):
        """Un utilisateur non connecte recoit un 403."""
        self.client.logout()
        reponse = self.client.post(
            f"/lire/{self.fixtures['page_source'].pk}/synthetiser/",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 403)

    @patch("front.tasks.synthetiser_page_task.delay")
    def test_synthetiser_cree_job(self, mock_delay):
        """L'action cree un ExtractionJob en status pending avec est_synthese=True."""
        reponse = self.client.post(
            f"/lire/{self.fixtures['page_source'].pk}/synthetiser/",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 200)

        job_cree = ExtractionJob.objects.filter(
            page=self.fixtures["page_source"],
            raw_result__est_synthese=True,
        ).first()
        self.assertIsNotNone(job_cree)
        self.assertEqual(job_cree.status, "pending")
        self.assertTrue(mock_delay.called)

    @patch("front.tasks.synthetiser_page_task.delay")
    def test_synthetiser_anti_doublon(self, mock_delay):
        """Si un job de synthese est deja en cours, pas de re-lancement."""
        # Creer un job pending existant / Create an existing pending job
        ExtractionJob.objects.create(
            page=self.fixtures["page_source"],
            ai_model=self.fixtures["modele_ia"],
            name="Synthese en cours",
            prompt_description="test",
            status="pending",
            raw_result={"est_synthese": True},
        )

        reponse = self.client.post(
            f"/lire/{self.fixtures['page_source'].pk}/synthetiser/",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 200)
        # Le delay ne doit pas etre appele (anti-doublon)
        # / delay should not be called (anti-duplicate)
        self.assertFalse(mock_delay.called)

    def test_synthetiser_sans_analyseur_actif(self):
        """Sans analyseur de type synthetiser actif, retourne un toast d'erreur 400."""
        # Desactiver l'analyseur / Deactivate the analyzer
        AnalyseurSyntaxique.objects.filter(type_analyseur="synthetiser").update(is_active=False)

        reponse = self.client.post(
            f"/lire/{self.fixtures['page_source'].pk}/synthetiser/",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 400)
        self.assertIn("showToast", reponse["HX-Trigger"])

    def test_synthetiser_sans_modele_ia(self):
        """Sans modele IA selectionne, retourne un toast d'erreur 400."""
        # Retirer le modele IA de la configuration / Remove AI model from configuration
        Configuration.objects.all().update(ai_model=None)

        reponse = self.client.post(
            f"/lire/{self.fixtures['page_source'].pk}/synthetiser/",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 400)
        self.assertIn("showToast", reponse["HX-Trigger"])

    @patch("front.tasks.synthetiser_page_task.delay")
    def test_synthetiser_retourne_toast_et_spinner(self, mock_delay):
        """L'action retourne le spinner de polling + un toast 'Synthese lancee'."""
        reponse = self.client.post(
            f"/lire/{self.fixtures['page_source'].pk}/synthetiser/",
            HTTP_HX_REQUEST="true",
        )
        contenu = reponse.content.decode("utf-8")
        # Verifie le spinner de polling / Check the polling spinner
        self.assertIn("hx-get", contenu)
        self.assertIn("synthese_status", contenu)
        self.assertIn("every 3s", contenu)
        # Verifie le toast (JSON encode les accents en \u00e8)
        # / Check the toast (JSON encodes accents as \u00e8)
        self.assertIn("Synth", reponse["HX-Trigger"])
        self.assertIn("lanc", reponse["HX-Trigger"])


# =============================================================================
# Tests endpoint synthese_status()
# / synthese_status() endpoint tests
# =============================================================================


class SyntheseStatusTest(TestCase):
    """Tests pour l'endpoint de polling synthese_status().
    / Tests for the synthese_status() polling endpoint."""

    def setUp(self):
        self.fixtures = creer_fixtures_synthese()
        self.client.login(username="testeur_synthese", password="test1234")

    def test_status_pending_retourne_spinner(self):
        """Un job pending retourne le partial avec le spinner de polling."""
        ExtractionJob.objects.create(
            page=self.fixtures["page_source"],
            ai_model=self.fixtures["modele_ia"],
            name="Synthese",
            prompt_description="test",
            status="pending",
            raw_result={"est_synthese": True},
        )

        reponse = self.client.get(
            f"/lire/{self.fixtures['page_source'].pk}/synthese_status/",
            HTTP_HX_REQUEST="true",
        )
        contenu = reponse.content.decode("utf-8")
        self.assertEqual(reponse.status_code, 200)
        self.assertIn("hx-get", contenu)
        self.assertIn("every 3s", contenu)
        # PHASE-29 : le template drawer ne passe plus par les HTML entities
        # / PHASE-29: drawer template no longer uses HTML entities
        self.assertIn("Synthèse en cours", contenu)

    def test_status_completed_retourne_lien_vers_synthese(self):
        """Un job completed retourne le bouton 'Voir la synthese'."""
        # Creer la page synthese / Create the synthesis page
        page_synthese = Page.objects.create(
            parent_page=self.fixtures["page_source"],
            title="Synthese V2",
            text_readability="Texte synthetise.",
            html_readability="<p>Texte synthetise.</p>",
            html_original="<p>Texte synthetise.</p>",
            content_hash="def456",
            version_number=2,
            version_label="Synthèse délibérative",
            dossier=self.fixtures["dossier"],
            source_type="web",
            owner=self.fixtures["utilisateur"],
        )

        ExtractionJob.objects.create(
            page=self.fixtures["page_source"],
            ai_model=self.fixtures["modele_ia"],
            name="Synthese",
            prompt_description="test",
            status="completed",
            raw_result={
                "est_synthese": True,
                "page_synthese_id": page_synthese.pk,
                "version_number": 2,
            },
        )

        reponse = self.client.get(
            f"/lire/{self.fixtures['page_source'].pk}/synthese_status/",
            HTTP_HX_REQUEST="true",
        )
        contenu = reponse.content.decode("utf-8")
        self.assertEqual(reponse.status_code, 200)
        # PHASE-29 : la reponse est un OOB qui recharge zone-lecture vers la V2
        # + HX-Trigger fermerDrawer + pill V2 dans le switcher.
        # / PHASE-29: response is an OOB that reloads zone-lecture to V2
        # / + HX-Trigger fermerDrawer + V2 pill in the switcher.
        self.assertIn(f"/lire/{page_synthese.pk}/", contenu)
        self.assertIn("indicateur-synthese", contenu)
        self.assertIn("V2", contenu)
        # HX-Trigger doit fermer le drawer / HX-Trigger must close the drawer
        trigger = reponse.headers.get("HX-Trigger", "")
        self.assertIn("fermerDrawer", trigger)
        # Pas de polling (plus de hx-trigger every) / No polling (no hx-trigger every)
        self.assertNotIn("every 3s", contenu)

    def test_status_error_retourne_message_et_retry(self):
        """Un job error retourne le message d'erreur et un bouton retry."""
        ExtractionJob.objects.create(
            page=self.fixtures["page_source"],
            ai_model=self.fixtures["modele_ia"],
            name="Synthese",
            prompt_description="test",
            status="error",
            error_message="Timeout LLM apres 30s",
            raw_result={"est_synthese": True},
        )

        reponse = self.client.get(
            f"/lire/{self.fixtures['page_source'].pk}/synthese_status/",
            HTTP_HX_REQUEST="true",
        )
        contenu = reponse.content.decode("utf-8")
        self.assertEqual(reponse.status_code, 200)
        self.assertIn("Timeout LLM", contenu)
        self.assertIn("btn-retry-synthese", contenu)

    def test_status_sans_job_retourne_erreur(self):
        """Sans aucun job de synthese, retourne un message d'erreur."""
        reponse = self.client.get(
            f"/lire/{self.fixtures['page_source'].pk}/synthese_status/",
            HTTP_HX_REQUEST="true",
        )
        contenu = reponse.content.decode("utf-8")
        self.assertEqual(reponse.status_code, 200)
        self.assertIn("Aucun job", contenu)


# =============================================================================
# Tests tache Celery synthetiser_page_task()
# / Celery task synthetiser_page_task() tests
# =============================================================================


class SynthetiserTaskTest(TestCase):
    """Tests pour synthetiser_page_task() avec LLM mocke.
    / Tests for synthetiser_page_task() with mocked LLM."""

    def setUp(self):
        self.fixtures = creer_fixtures_synthese()

    @patch("core.llm_providers.appeler_llm", return_value="Paragraphe 1.\n\nParagraphe 2.")
    @patch("front.tasks.envoyer_progression_websocket")
    def test_task_cree_page_enfant(self, mock_ws, mock_llm):
        """La tache cree une Page enfant avec le texte synthetise."""
        job_synthese = ExtractionJob.objects.create(
            page=self.fixtures["page_source"],
            ai_model=self.fixtures["modele_ia"],
            name="Synthese deliberative",
            prompt_description="test prompt",
            status="pending",
            raw_result={
                "analyseur_id": self.fixtures["analyseur"].pk,
                "est_synthese": True,
            },
        )

        from front.tasks import synthetiser_page_task
        synthetiser_page_task(job_synthese.pk)

        job_synthese.refresh_from_db()
        self.assertEqual(job_synthese.status, "completed")

        page_synthese_id = job_synthese.raw_result.get("page_synthese_id")
        self.assertIsNotNone(page_synthese_id)

        page_synthese = Page.objects.get(pk=page_synthese_id)
        self.assertIn("Paragraphe 1.", page_synthese.text_readability)
        self.assertIn("Paragraphe 2.", page_synthese.text_readability)

    @patch("core.llm_providers.appeler_llm", return_value="Synthese test.")
    @patch("front.tasks.envoyer_progression_websocket")
    def test_task_parent_page_est_racine(self, mock_ws, mock_llm):
        """La page enfant a pour parent_page la page racine."""
        job_synthese = ExtractionJob.objects.create(
            page=self.fixtures["page_source"],
            ai_model=self.fixtures["modele_ia"],
            name="Synthese deliberative",
            prompt_description="test",
            status="pending",
            raw_result={
                "analyseur_id": self.fixtures["analyseur"].pk,
                "est_synthese": True,
            },
        )

        from front.tasks import synthetiser_page_task
        synthetiser_page_task(job_synthese.pk)

        job_synthese.refresh_from_db()
        page_synthese = Page.objects.get(pk=job_synthese.raw_result["page_synthese_id"])
        self.assertEqual(page_synthese.parent_page, self.fixtures["page_source"].page_racine)

    @patch("core.llm_providers.appeler_llm", return_value="V2 synthese.")
    @patch("front.tasks.envoyer_progression_websocket")
    def test_task_version_number_incrementee(self, mock_ws, mock_llm):
        """Le version_number est incremente correctement."""
        job_synthese = ExtractionJob.objects.create(
            page=self.fixtures["page_source"],
            ai_model=self.fixtures["modele_ia"],
            name="Synthese deliberative",
            prompt_description="test",
            status="pending",
            raw_result={
                "analyseur_id": self.fixtures["analyseur"].pk,
                "est_synthese": True,
            },
        )

        from front.tasks import synthetiser_page_task
        synthetiser_page_task(job_synthese.pk)

        job_synthese.refresh_from_db()
        page_synthese = Page.objects.get(pk=job_synthese.raw_result["page_synthese_id"])
        self.assertEqual(page_synthese.version_number, 2)

    @patch("core.llm_providers.appeler_llm", side_effect=Exception("LLM error"))
    @patch("front.tasks.envoyer_progression_websocket")
    def test_task_erreur_marque_job_error(self, mock_ws, mock_llm):
        """En cas d'erreur LLM, le job passe en status error."""
        job_synthese = ExtractionJob.objects.create(
            page=self.fixtures["page_source"],
            ai_model=self.fixtures["modele_ia"],
            name="Synthese deliberative",
            prompt_description="test",
            status="pending",
            raw_result={
                "analyseur_id": self.fixtures["analyseur"].pk,
                "est_synthese": True,
            },
        )

        from front.tasks import synthetiser_page_task
        synthetiser_page_task(job_synthese.pk)

        job_synthese.refresh_from_db()
        self.assertEqual(job_synthese.status, "error")
        self.assertIn("LLM error", job_synthese.error_message)

    @patch("core.llm_providers.appeler_llm", return_value="Premier.\n\nDeuxieme <script>alert('xss')</script>.")
    @patch("front.tasks.envoyer_progression_websocket")
    def test_task_html_echappe_xss(self, mock_ws, mock_llm):
        """Le HTML genere echappe les balises dangereuses (XSS)."""
        job_synthese = ExtractionJob.objects.create(
            page=self.fixtures["page_source"],
            ai_model=self.fixtures["modele_ia"],
            name="Synthese deliberative",
            prompt_description="test",
            status="pending",
            raw_result={
                "analyseur_id": self.fixtures["analyseur"].pk,
                "est_synthese": True,
            },
        )

        from front.tasks import synthetiser_page_task
        synthetiser_page_task(job_synthese.pk)

        job_synthese.refresh_from_db()
        page_synthese = Page.objects.get(pk=job_synthese.raw_result["page_synthese_id"])
        # Le HTML doit contenir des balises <p> mais pas de <script>
        # / HTML must contain <p> tags but not <script>
        self.assertIn("<p>", page_synthese.html_readability)
        self.assertNotIn("<script>", page_synthese.html_readability)
        self.assertIn("&lt;script&gt;", page_synthese.html_readability)

    @patch("core.llm_providers.appeler_llm", return_value="Synthese.")
    @patch("front.tasks.envoyer_progression_websocket")
    def test_task_version_label_correcte(self, mock_ws, mock_llm):
        """La page creee a le version_label 'Synthese deliberative'."""
        job_synthese = ExtractionJob.objects.create(
            page=self.fixtures["page_source"],
            ai_model=self.fixtures["modele_ia"],
            name="Synthese deliberative",
            prompt_description="test",
            status="pending",
            raw_result={
                "analyseur_id": self.fixtures["analyseur"].pk,
                "est_synthese": True,
            },
        )

        from front.tasks import synthetiser_page_task
        synthetiser_page_task(job_synthese.pk)

        job_synthese.refresh_from_db()
        page_synthese = Page.objects.get(pk=job_synthese.raw_result["page_synthese_id"])
        self.assertEqual(page_synthese.version_label, "Synthèse délibérative")

    @patch("core.llm_providers.appeler_llm", return_value="Synthese sans analyse.")
    @patch("front.tasks.envoyer_progression_websocket")
    def test_task_sans_job_analyse_erreur(self, mock_ws, mock_llm):
        """Sans job d'analyse complete, la tache passe en erreur."""
        # Supprimer le job d'analyse / Delete the analysis job
        ExtractionJob.objects.filter(page=self.fixtures["page_source"]).delete()

        job_synthese = ExtractionJob.objects.create(
            page=self.fixtures["page_source"],
            ai_model=self.fixtures["modele_ia"],
            name="Synthese deliberative",
            prompt_description="test",
            status="pending",
            raw_result={
                "analyseur_id": self.fixtures["analyseur"].pk,
                "est_synthese": True,
            },
        )

        from front.tasks import synthetiser_page_task
        synthetiser_page_task(job_synthese.pk)

        job_synthese.refresh_from_db()
        self.assertEqual(job_synthese.status, "error")
        self.assertIn("analyse", job_synthese.error_message.lower())


# =============================================================================
# Tests debit credits apres analyse et synthese (PHASE-26h)
# / Credit debit tests after analysis and synthesis (PHASE-26h)
# =============================================================================


@override_settings(STRIPE_ENABLED=True)
class DebitCreditsSyntheseTest(TestCase):
    """Tests que le solde est debite apres une synthese LLM mockee.
    / Tests that balance is debited after a mocked LLM synthesis."""

    def setUp(self):
        self.fixtures = creer_fixtures_synthese()
        # Creer un compte credits pour l'utilisateur
        # / Create a credit account for the user
        from core.models import CreditAccount
        self.compte = CreditAccount.objects.create(
            user=self.fixtures["utilisateur"],
            solde_euros=10.00,
        )

    @patch("core.llm_providers.appeler_llm", return_value="Texte synthetise.")
    @patch("front.tasks.envoyer_progression_websocket")
    @patch("core.models.AIModel.estimer_cout_euros", return_value=0.05)
    def test_synthese_debite_le_compte(self, mock_cout, mock_ws, mock_llm):
        """Apres une synthese reussie, le solde est debite et une transaction DEBIT_ANALYSE existe."""
        # / After a successful synthesis, balance is debited and a DEBIT_ANALYSE transaction exists
        from core.models import CreditTransaction
        from front.tasks import synthetiser_page_task

        solde_avant = self.compte.solde_euros

        job_synthese = ExtractionJob.objects.create(
            page=self.fixtures["page_source"],
            ai_model=self.fixtures["modele_ia"],
            name="Synthese test debit",
            prompt_description="test",
            status="pending",
            raw_result={
                "analyseur_id": self.fixtures["analyseur"].pk,
                "est_synthese": True,
            },
        )

        synthetiser_page_task(job_synthese.pk)

        # Le solde doit avoir diminue / Balance must have decreased
        self.compte.refresh_from_db()
        self.assertLess(self.compte.solde_euros, solde_avant)

        # Une transaction DEBIT_ANALYSE doit exister / A DEBIT_ANALYSE transaction must exist
        transaction_debit = CreditTransaction.objects.filter(
            compte=self.compte,
            type_transaction="DEBIT_ANALYSE",
            extraction_job=job_synthese,
        ).first()
        self.assertIsNotNone(transaction_debit)
        self.assertLess(transaction_debit.montant_euros, 0)

    @patch("core.llm_providers.appeler_llm", return_value="Texte synthetise.")
    @patch("front.tasks.envoyer_progression_websocket")
    @patch("core.models.AIModel.estimer_cout_euros", return_value=0.05)
    def test_synthese_superuser_pas_debite(self, mock_cout, mock_ws, mock_llm):
        """Un superuser n'est pas debite apres une synthese."""
        # / A superuser is not debited after a synthesis
        from core.models import CreditTransaction
        from front.tasks import synthetiser_page_task

        self.fixtures["utilisateur"].is_superuser = True
        self.fixtures["utilisateur"].save(update_fields=["is_superuser"])

        job_synthese = ExtractionJob.objects.create(
            page=self.fixtures["page_source"],
            ai_model=self.fixtures["modele_ia"],
            name="Synthese superuser",
            prompt_description="test",
            status="pending",
            raw_result={
                "analyseur_id": self.fixtures["analyseur"].pk,
                "est_synthese": True,
            },
        )

        synthetiser_page_task(job_synthese.pk)

        # Pas de transaction debit / No debit transaction
        self.assertFalse(
            CreditTransaction.objects.filter(
                type_transaction="DEBIT_ANALYSE",
                extraction_job=job_synthese,
            ).exists()
        )

        # Solde inchange / Balance unchanged
        self.compte.refresh_from_db()
        self.assertEqual(self.compte.solde_euros, 10.00)

    @patch("core.llm_providers.appeler_llm", return_value="Texte synthetise.")
    @patch("front.tasks.envoyer_progression_websocket")
    def test_synthese_sans_compte_pas_erreur(self, mock_ws, mock_llm):
        """Si l'utilisateur n'a pas de compte credits, pas d'erreur."""
        # / If user has no credit account, no error
        from front.tasks import synthetiser_page_task

        # Supprimer le compte / Delete the account
        self.compte.delete()

        job_synthese = ExtractionJob.objects.create(
            page=self.fixtures["page_source"],
            ai_model=self.fixtures["modele_ia"],
            name="Synthese sans compte",
            prompt_description="test",
            status="pending",
            raw_result={
                "analyseur_id": self.fixtures["analyseur"].pk,
                "est_synthese": True,
            },
        )

        # Ne doit pas lever d'exception / Must not raise an exception
        synthetiser_page_task(job_synthese.pk)

        job_synthese.refresh_from_db()
        self.assertEqual(job_synthese.status, "completed")


@override_settings(STRIPE_ENABLED=True)
class DebitCreditsAnalyseTest(TestCase):
    """Tests que le solde est debite apres une analyse LLM mockee.
    / Tests that balance is debited after a mocked LLM analysis."""

    def setUp(self):
        self.fixtures = creer_fixtures_synthese()
        from core.models import CreditAccount
        self.compte = CreditAccount.objects.create(
            user=self.fixtures["utilisateur"],
            solde_euros=10.00,
        )
        # Creer un analyseur de type "analyser" / Create an "analyser" type analyzer
        self.analyseur_analyse = AnalyseurSyntaxique.objects.create(
            name="Test analyse debit",
            is_active=True,
            type_analyseur="analyser",
        )
        PromptPiece.objects.create(
            analyseur=self.analyseur_analyse,
            name="Test", role="context",
            content="Analyse le texte.", order=0,
        )

    def test_debiter_cree_transaction_et_diminue_solde(self):
        """La methode debiter() cree une CreditTransaction et diminue le solde."""
        # / The debiter() method creates a CreditTransaction and decreases the balance
        from decimal import Decimal
        from core.models import CreditTransaction

        self.compte.refresh_from_db()
        solde_avant = self.compte.solde_euros
        self.compte.debiter(montant=Decimal("0.05"), description="Test analyse debit")

        self.compte.refresh_from_db()
        self.assertEqual(self.compte.solde_euros, Decimal("9.95"))

        transaction = CreditTransaction.objects.filter(
            compte=self.compte,
            type_transaction="DEBIT_ANALYSE",
        ).first()
        self.assertIsNotNone(transaction)
        self.assertLess(transaction.montant_euros, 0)

    def test_debiter_solde_insuffisant_leve_erreur(self):
        """Debiter plus que le solde leve SoldeInsuffisantError."""
        # / Debiting more than balance raises SoldeInsuffisantError
        from core.models import SoldeInsuffisantError
        with self.assertRaises(SoldeInsuffisantError):
            self.compte.debiter(montant=999.99, description="Test solde insuffisant")


@override_settings(STRIPE_ENABLED=False)
class DebitCreditsDesactiveTest(TestCase):
    """Tests que le debit est ignore quand STRIPE_ENABLED=False.
    / Tests that debit is skipped when STRIPE_ENABLED=False."""

    def setUp(self):
        self.fixtures = creer_fixtures_synthese()
        from core.models import CreditAccount
        self.compte = CreditAccount.objects.create(
            user=self.fixtures["utilisateur"],
            solde_euros=10.00,
        )

    @patch("core.llm_providers.appeler_llm", return_value="Texte synthetise.")
    @patch("front.tasks.envoyer_progression_websocket")
    def test_synthese_stripe_desactive_pas_de_debit(self, mock_ws, mock_llm):
        """Avec STRIPE_ENABLED=False, pas de debit meme si le compte existe."""
        # / With STRIPE_ENABLED=False, no debit even if account exists
        from core.models import CreditTransaction
        from front.tasks import synthetiser_page_task

        job_synthese = ExtractionJob.objects.create(
            page=self.fixtures["page_source"],
            ai_model=self.fixtures["modele_ia"],
            name="Synthese stripe off",
            prompt_description="test",
            status="pending",
            raw_result={
                "analyseur_id": self.fixtures["analyseur"].pk,
                "est_synthese": True,
            },
        )

        synthetiser_page_task(job_synthese.pk)

        # Pas de transaction / No transaction
        self.assertFalse(
            CreditTransaction.objects.filter(type_transaction="DEBIT_ANALYSE").exists()
        )
        # Solde inchange / Balance unchanged
        self.compte.refresh_from_db()
        self.assertEqual(self.compte.solde_euros, 10.00)


@override_settings(STRIPE_ENABLED=True)
class DebitCreditsTranscriptionTest(TestCase):
    """Tests que la transcription audio debite le solde.
    / Tests that audio transcription debits the balance."""

    def setUp(self):
        self.utilisateur = User.objects.create_user("test_audio_debit", password="test1234")
        self.dossier = Dossier.objects.create(name="Audio test", owner=self.utilisateur)
        from core.models import CreditAccount
        self.compte = CreditAccount.objects.create(
            user=self.utilisateur, solde_euros=10.00,
        )

    @patch("front.tasks.envoyer_progression_websocket")
    @patch("front.services.transcription_audio.transcrire_audio_mock",
           return_value=[{"speaker": "A", "text": "Bonjour"}])
    @patch("front.services.transcription_audio.construire_html_diarise",
           return_value=("<p>Bonjour</p>", "Bonjour"))
    @patch("core.models.TranscriptionConfig.estimer_cout_euros", return_value=0.10)
    def test_transcription_debite_le_compte(self, mock_cout, mock_html, mock_transcr, mock_ws):
        """Apres une transcription audio reussie, le solde est debite."""
        # / After a successful audio transcription, balance is debited
        import tempfile, os
        from core.models import TranscriptionConfig, TranscriptionJob, CreditTransaction

        # Creer la config transcription et le job
        # / Create transcription config and job
        config = TranscriptionConfig.objects.create(
            model_name="mock", provider="mock", is_active=True,
        )
        page = Page.objects.create(
            title="Audio test debit", status="processing",
            source_type="audio", dossier=self.dossier, owner=self.utilisateur,
        )
        job = TranscriptionJob.objects.create(
            page=page, transcription_config=config, status="pending",
        )

        # Creer un fichier audio temporaire vide / Create empty temp audio file
        fichier_temp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        fichier_temp.close()

        try:
            from front.tasks import transcrire_audio_task
            transcrire_audio_task(job.pk, fichier_temp.name)

            # Le solde doit avoir diminue / Balance must have decreased
            self.compte.refresh_from_db()
            self.assertLess(self.compte.solde_euros, 10.00)

            # Une transaction doit exister / A transaction must exist
            transaction = CreditTransaction.objects.filter(
                compte=self.compte,
                type_transaction="DEBIT_ANALYSE",
            ).first()
            self.assertIsNotNone(transaction)
        finally:
            if os.path.exists(fichier_temp.name):
                os.unlink(fichier_temp.name)


# =============================================================================
# Tests template dashboard bouton
# / Dashboard button template tests
# =============================================================================


class DashboardBoutonTest(TestCase):
    """Tests pour le bouton synthese dans le dashboard consensus.
    / Tests for the synthesis button in the consensus dashboard."""

    def setUp(self):
        self.fixtures = creer_fixtures_synthese()
        self.client.login(username="testeur_synthese", password="test1234")

    def test_bouton_est_cliquable(self):
        """Le bouton synthese n'a plus l'attribut disabled."""
        reponse = self.client.get(
            f"/extractions/dashboard/?page_id={self.fixtures['page_source'].pk}",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode("utf-8")
        # PHASE-29 : le bouton ouvre maintenant la confirmation drawer via HTMX
        # / PHASE-29: button now opens confirmation drawer via HTMX
        self.assertIn("/previsualiser_synthese/", contenu)
        self.assertNotIn('disabled', contenu.split("btn-lancer-synthese")[1].split(">")[0])

    def test_bouton_variante_avertissement(self):
        """Si le seuil n'est pas atteint, le bouton a la classe avertissement."""
        # Passer toutes les entites visibles en "controverse" pour faire baisser le consensus
        # / Set all visible entities to "controverse" to lower consensus
        ExtractedEntity.objects.filter(
            job=self.fixtures["job_analyse"],
            masquee=False,
        ).update(statut_debat="controverse")

        reponse = self.client.get(
            f"/extractions/dashboard/?page_id={self.fixtures['page_source'].pk}",
            HTTP_HX_REQUEST="true",
        )
        contenu = reponse.content.decode("utf-8")
        self.assertIn("btn-synthese-avertissement", contenu)

    def test_zone_btn_synthese_presente(self):
        """Le div #zone-btn-synthese est present dans le dashboard."""
        reponse = self.client.get(
            f"/extractions/dashboard/?page_id={self.fixtures['page_source'].pk}",
            HTTP_HX_REQUEST="true",
        )
        contenu = reponse.content.decode("utf-8")
        self.assertIn('id="zone-btn-synthese"', contenu)

    def test_dashboard_entites_nouveau_ne_montre_pas_etat_vide(self):
        """Des entites en statut 'nouveau' ne declenchent pas 'Aucune extraction'."""
        # Passer toutes les entites visibles en "nouveau" / Set all visible entities to "nouveau"
        ExtractedEntity.objects.filter(
            job=self.fixtures["job_analyse"],
        ).update(statut_debat="nouveau", masquee=False)

        reponse = self.client.get(
            f"/extractions/dashboard/?page_id={self.fixtures['page_source'].pk}",
            HTTP_HX_REQUEST="true",
        )
        contenu = reponse.content.decode("utf-8")
        # Ne doit PAS afficher l'etat vide / Must NOT show the empty state
        self.assertNotIn("Aucune extraction pour cette page", contenu)
        # Doit afficher la grille de compteurs / Must show the counters grid
        self.assertIn("compteur-nouveau", contenu)

    def test_dashboard_aucune_entite_montre_etat_vide(self):
        """Sans aucune entite, le dashboard affiche bien 'Aucune extraction'."""
        # Supprimer toutes les entites / Delete all entities
        ExtractedEntity.objects.filter(job=self.fixtures["job_analyse"]).delete()

        reponse = self.client.get(
            f"/extractions/dashboard/?page_id={self.fixtures['page_source'].pk}",
            HTTP_HX_REQUEST="true",
        )
        contenu = reponse.content.decode("utf-8")
        self.assertIn("Aucune extraction pour cette page", contenu)
