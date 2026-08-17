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
        statut_debat="commente",
    )

    entite_controversee = ExtractedEntity.objects.create(
        job=job_analyse,
        extraction_class="hypothese",
        extraction_text="Les communs sont une alternative.",
        start_char=25,
        end_char=57,
        statut_debat="nouveau",
    )

    # « Non pertinent » n'existe plus comme statut : la migration
    # extractor 0029 l'a fusionne dans masquee=True. Le fixture reflete
    # la realite post-migration. / non_pertinent merged into masquee.
    entite_non_pertinente = ExtractedEntity.objects.create(
        job=job_analyse,
        extraction_class="indice",
        extraction_text="Bruit de fond non pertinent.",
        start_char=58,
        end_char=85,
    )
    ExtractedEntity.objects.filter(pk=entite_non_pertinente.pk).update(
        masquee=True,
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



def mock_qui_cite_vraiment(corps="Synthese test."):
    """
    Une reponse mockee qui CITE, plutot que d'annoncer « aucune ».
    / A mocked response that actually cites, instead of "none".

    LOCALISATION : front/tests/test_phase28_light.py

    Depuis que `synthetiser_page_task` passe par le tronc commun
    d'ecriture, un article sans AUCUN marqueur sur un perimetre non
    vide est REFUSE — un texte sans preuve n'est pas un succes
    (constat reel du 9 aout 2026). Ces tests-ci n'eprouvent pas cette
    garde : ils eprouvent le typage de la note, l'echappement XSS et le
    version_label. Leur reponse doit donc etre CONFORME au contrat.

    Les pk des extractions n'existent pas au moment ou le decorateur
    @patch est evalue : la reponse relit donc le PREMIER
    « Identifiant : ext:N » du prompt reellement transmis, et pose son
    marqueur. Aucun pk code en dur, aucune dependance a l'ordre de
    creation de la fixture.
    / The extraction pks do not exist when @patch is evaluated, so the
    response reads the first id back out of the prompt it receives.
    """
    import re as re_module

    def _repondre(_modele_ia, message_complet):
        correspondance = re_module.search(
            r"Identifiant : ext:(\d+)", message_complet or "",
        )
        if correspondance is None:
            # Perimetre vide : la garde ne s'applique pas, et annoncer
            # « aucune » est alors la reponse juste.
            # / Empty scope: "none" is the correct answer.
            return f"{corps}\n\nCITATIONS_USED: aucune"
        identifiant = correspondance.group(1)
        return (
            f"{corps}[[ext:{identifiant}]]\n\n"
            f"CITATIONS_USED: {identifiant}"
        )

    return _repondre


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
        """A.8 : statut binaire — le prompt contient [COMMENTE] ou [NOUVEAU]."""
        from front.tasks import _construire_prompt_synthese
        prompt = _construire_prompt_synthese(
            self.fixtures["page_source"], self.fixtures["job_analyse"],
            self.fixtures["analyseur"],
        )
        self.assertTrue(
            "[COMMENTE]" in prompt or "[NOUVEAU]" in prompt,
            "Le prompt doit contenir au moins un statut binaire",
        )

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

    # A.8 : test_prompt_tri_par_statut retire — le tri par statut riche
    # (CONSENSUEL avant CONTROVERSE) n'a plus de sens avec 2 valeurs binaires.
    # / A.8: test removed — sorting by rich status no longer makes sense
    # / with binary values.

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


# =============================================================================
# Tests tache Celery synthetiser_page_task()
# / Celery task synthetiser_page_task() tests
# =============================================================================


class SynthetiserTaskTest(TestCase):
    """Tests pour synthetiser_page_task() avec LLM mocke.
    / Tests for synthetiser_page_task() with mocked LLM.

    SPEC-synthese phase C : la reponse mockee DOIT finir par la ligne
    CITATIONS_USED (contrat anti-troncature), et la synthese est une
    note typee — plus une version. Les tests du versionnage sont
    remplaces par leurs inverses ; le contrat complet est exerce dans
    front/tests/test_synthese_phase_c.py.
    / Mocks must honor the CITATIONS_USED contract; version tests are
    replaced by their phase C inverses.
    """

    def setUp(self):
        self.fixtures = creer_fixtures_synthese()

    @patch(
        "core.llm_providers.appeler_llm",
        side_effect=mock_qui_cite_vraiment("Paragraphe 1.\n\nParagraphe 2."),
    )
    def test_task_cree_note_typee(self, mock_llm):
        """La tache cree une note typee SYNTHESE avec le texte produit."""
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
        self.assertEqual(page_synthese.type_de_note, "synthese")

    @patch(
        "core.llm_providers.appeler_llm",
        side_effect=mock_qui_cite_vraiment("Synthese test."),
    )
    def test_task_la_synthese_n_est_plus_une_version(self, mock_llm):
        """Phase C : plus de parent_page, plus de numero incremente."""
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
        self.assertIsNone(page_synthese.parent_page)
        self.assertEqual(page_synthese.version_number, 1)

    @patch("core.llm_providers.appeler_llm", side_effect=Exception("LLM error"))
    def test_task_erreur_marque_job_error(self, mock_llm):
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

    @patch(
        "core.llm_providers.appeler_llm",
        side_effect=mock_qui_cite_vraiment(
            "Premier.\n\nDeuxieme <script>alert('xss')</script>."
        ),
    )
    def test_task_html_echappe_xss(self, mock_llm):
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

    @patch(
        "core.llm_providers.appeler_llm",
        side_effect=mock_qui_cite_vraiment("Synthese."),
    )
    def test_task_version_label_correcte(self, mock_llm):
        """La page creee a le version_label = nom de l'analyseur (PHASE-29).
        Permet de distinguer V2-Mathemagique de V3-Charte si analyseurs differents.
        / Page version_label = analyzer name (PHASE-29) — distinguishes different analyzers."""
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
        # version_label = nom de l'analyseur utilise / version_label = analyzer name
        self.assertEqual(page_synthese.version_label, self.fixtures["analyseur"].name)

    @patch("core.llm_providers.appeler_llm", return_value="Synthese sans analyse.")
    def test_task_sans_job_analyse_erreur(self, mock_llm):
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
# Tests du pied de panneau : etat du debat et bouton de synthese
# / Panel footer tests: debate state and synthesis button
# =============================================================================


class PiedDePanneauSyntheseTest(TestCase):
    """
    Le bouton de synthese et l'etat du debat, dans le PANNEAU.
    / The synthesis button and debate state, in the PANEL.

    LOCALISATION : front/tests/test_phase28_light.py

    Ces tests visaient `/extractions/dashboard/`, l'endpoint du dashboard
    de la barre d'outils, retire le 12 aout a la demande du mainteneur.
    L'intention qu'ils portaient reste valide — le bouton de synthese doit
    exister quelque part, et l'etat du debat avec lui. Ils sont donc
    REDIRIGES vers le panneau, ou les deux ont demenage, plutot que
    supprimes avec l'endpoint : c'est la couverture qu'on garde, pas la
    route. / Redirected to the panel, where both moved.
    """

    def setUp(self):
        self.fixtures = creer_fixtures_synthese()
        self.client.login(username="testeur_synthese", password="test1234")

    def _lire_le_panneau(self):
        """Rend le HTML du panneau d'analyse. / Return the panel HTML."""
        reponse = self.client.get(
            f"/extractions/drawer_contenu/?page_id={self.fixtures['page_source'].pk}",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 200)
        return reponse.content.decode("utf-8")

    def test_le_bouton_de_synthese_est_dans_le_panneau(self):
        """
        Son SEUL point d'entree etait le dashboard : le retirer sans le
        deplacer aurait supprime l'acces a la synthese.
        / Its only entry point was the dashboard.
        """
        contenu = self._lire_le_panneau()

        self.assertIn("btn-lancer-synthese", contenu)
        self.assertIn("/previsualiser_synthese/", contenu)

    def test_le_bouton_de_synthese_est_cliquable(self):
        """Pas d'attribut `disabled` : on lance quand on veut (A.8, Q1=B)."""
        contenu = self._lire_le_panneau()

        balise_du_bouton = contenu.split("btn-lancer-synthese")[1].split(">")[0]
        self.assertNotIn("disabled", balise_du_bouton)

    def test_le_panneau_montre_l_etat_du_debat_quand_il_y_a_des_idees(self):
        """Le compteur binaire « commentees / total » suit les cartes."""
        ExtractedEntity.objects.filter(
            job=self.fixtures["job_analyse"],
        ).update(statut_debat="nouveau", masquee=False)

        contenu = self._lire_le_panneau()

        self.assertIn("etat-du-debat", contenu)
        self.assertIn("commentée", contenu)

    def test_sans_aucune_idee_le_pied_de_panneau_disparait(self):
        """
        Un etat du debat sans debat, et un bouton de synthese sans rien a
        synthetiser, n'apprennent rien : le pied s'efface.
        / No ideas, no footer.
        """
        ExtractedEntity.objects.filter(job=self.fixtures["job_analyse"]).delete()

        contenu = self._lire_le_panneau()

        self.assertNotIn("btn-lancer-synthese", contenu)
        self.assertNotIn("pied-de-panneau", contenu)
