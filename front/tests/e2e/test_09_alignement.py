"""
Tests E2E — Alignement : tableau, hypostases, gaps.
/ E2E tests — Alignment: table, hypostases, gaps.
"""
from front.tests.e2e.base import PlaywrightLiveTestCase
from hypostasis_extractor.models import ExtractionJob, ExtractedEntity
from core.models import AIModel, HypostasisTag


class E2EAlignementTest(PlaywrightLiveTestCase):
    """Tests du tableau d'alignement."""

    def setUp(self):
        super().setUp()
        # Creer un utilisateur et se connecter
        # / Create a user and log in
        self.utilisateur_test = self.creer_utilisateur_demo()
        self.se_connecter("testuser", "testpass123")

        # Creer 1 dossier avec 3 pages ayant des hypostases differentes
        # / Create 1 folder with 3 pages having different hypostases
        self.dossier_alignement = self.creer_dossier_demo("Dossier Alignement", owner=self.utilisateur_test)

        modele_mock = AIModel.objects.create(
            name="Mock Alignement",
            model_choice="mock_default",
            is_active=True,
        )

        # Creer les tags hypostase
        # / Create hypostasis tags
        tag_axiome, _ = HypostasisTag.objects.get_or_create(
            name="AXIOME", defaults={"description": "Axiome"},
        )
        tag_hypothese, _ = HypostasisTag.objects.get_or_create(
            name="HYPOTHESE", defaults={"description": "Hypothese"},
        )
        tag_probleme, _ = HypostasisTag.objects.get_or_create(
            name="PROBLEME", defaults={"description": "Probleme"},
        )

        # Page 1 : axiome + hypothese
        # / Page 1: axiom + hypothesis
        self.page_1 = self.creer_page_demo("Page Align 1", "<p>Contenu page 1 alignement.</p>", owner=self.utilisateur_test, dossier=self.dossier_alignement)
        job_1 = ExtractionJob.objects.create(
            page=self.page_1, ai_model=modele_mock, name="Job 1",
            prompt_description="Test", status="completed", entities_count=2,
        )
        ExtractedEntity.objects.create(
            job=job_1, extraction_class="axiome", extraction_text="Axiome de la page 1",
            start_char=0, end_char=20, hypostasis_tag=tag_axiome, attributes={"hypostase": "axiome"},
        )
        ExtractedEntity.objects.create(
            job=job_1, extraction_class="hypothese", extraction_text="Hypothese de la page 1",
            start_char=21, end_char=50, hypostasis_tag=tag_hypothese, attributes={"hypostase": "hypothese"},
        )

        # Page 2 : hypothese + probleme
        # / Page 2: hypothesis + problem
        self.page_2 = self.creer_page_demo("Page Align 2", "<p>Contenu page 2 alignement.</p>", owner=self.utilisateur_test, dossier=self.dossier_alignement)
        job_2 = ExtractionJob.objects.create(
            page=self.page_2, ai_model=modele_mock, name="Job 2",
            prompt_description="Test", status="completed", entities_count=2,
        )
        ExtractedEntity.objects.create(
            job=job_2, extraction_class="hypothese", extraction_text="Hypothese de la page 2",
            start_char=0, end_char=25, hypostasis_tag=tag_hypothese, attributes={"hypostase": "hypothese"},
        )
        ExtractedEntity.objects.create(
            job=job_2, extraction_class="probleme", extraction_text="Probleme de la page 2",
            start_char=26, end_char=50, hypostasis_tag=tag_probleme, attributes={"hypostase": "probleme"},
        )

        # Page 3 : axiome seulement (gap sur hypothese et probleme)
        # / Page 3: axiom only (gap on hypothesis and problem)
        self.page_3 = self.creer_page_demo("Page Align 3", "<p>Contenu page 3 alignement.</p>", owner=self.utilisateur_test, dossier=self.dossier_alignement)
        job_3 = ExtractionJob.objects.create(
            page=self.page_3, ai_model=modele_mock, name="Job 3",
            prompt_description="Test", status="completed", entities_count=1,
        )
        ExtractedEntity.objects.create(
            job=job_3, extraction_class="axiome", extraction_text="Axiome de la page 3",
            start_char=0, end_char=20, hypostasis_tag=tag_axiome, attributes={"hypostase": "axiome"},
        )

    def _deplier_dossier_et_aligner(self):
        """
        Ouvre le carnet et clique son onglet « Alignement ».
        / Open the notebook and click its "Alignment" tab.

        CE HELPER PASSAIT PAR L'ARBRE LATERAL : il ouvrait le tiroir
        (touche T), depliait le noeud du dossier, puis cliquait le
        bouton « Aligner (N pages) » qui n'existait que la. L'arbre est
        retire le 12 aout 2026.

        Le second point d'entree existait DEJA : l'onglet « Alignement »
        de la page d'un carnet, qui appelle le meme
        `window.alignement.ouvrirDossier`. C'est lui qu'on emprunte —
        aucune couverture perdue, le tableau teste est le meme.
        / The helper went through the removed tree; the notebook page's
        "Alignment" tab already called the same entry point.
        """
        self.naviguer_vers(f"/carnets/{self.dossier_alignement.pk}/")
        self.page.click('[data-testid="corpus-onglet-alignement"]')
        self.attendre_htmx(timeout_ms=10000)

    def test_alignement_tableau_affiche(self):
        """Le tableau d'alignement s'affiche pour un dossier avec 3 pages."""
        self._deplier_dossier_et_aligner()
        # Le conteneur du tableau d'alignement doit avoir du contenu
        # / The alignment table container must have content
        conteneur_alignement = self.page.locator("#alignement-modale-container")
        contenu = conteneur_alignement.text_content()
        self.assertTrue(len(contenu.strip()) > 0, "Le tableau d'alignement devrait s'afficher")

    def test_colonnes_pages_lignes_hypostases(self):
        """Le tableau a des colonnes = pages et des lignes = hypostases."""
        self._deplier_dossier_et_aligner()
        contenu_alignement = self.page.text_content("#alignement-modale-container")
        # Les noms de pages doivent etre dans le tableau
        # / Page names must be in the table
        self.assertIn("Page Align 1", contenu_alignement)
        self.assertIn("Page Align 2", contenu_alignement)

    def test_gaps_cellules_vides_identifiables(self):
        """Les gaps (cellules vides) sont identifiables dans le tableau."""
        self._deplier_dossier_et_aligner()
        # Chercher les cellules vides (marquees avec le tiret cadratin)
        # / Look for empty cells (marked with em dash)
        contenu_alignement = self.page.text_content("#alignement-modale-container")
        # Le tableau devrait contenir des tirets cadratins pour les gaps
        # / The table should contain em dashes for gaps
        self.assertIn("\u2014", contenu_alignement)
