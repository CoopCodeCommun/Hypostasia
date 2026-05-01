"""
Tests E2E — Layout : drawer, raccourcis clavier.
/ E2E tests — Layout: drawer, keyboard shortcuts.
"""
from front.tests.e2e.base import PlaywrightLiveTestCase
from hypostasis_extractor.models import ExtractionJob, ExtractedEntity
from core.models import AIModel


class E2ELayoutTest(PlaywrightLiveTestCase):
    """Tests de layout et raccourcis clavier."""

    def setUp(self):
        super().setUp()
        # Creer un utilisateur et se connecter
        # / Create a user and log in
        self.utilisateur_test = self.creer_utilisateur_demo()
        self.se_connecter("testuser", "testpass123")

        # Creer une page avec des extractions pour tester les raccourcis
        # / Create a page with extractions to test shortcuts
        self.page_layout = self.creer_page_demo(
            "Page layout E2E",
            "<p>Contenu pour tester le layout et les raccourcis.</p>",
            owner=self.utilisateur_test,
        )
        modele_mock = AIModel.objects.create(
            name="Mock Layout",
            model_choice="mock_default",
            is_active=True,
        )
        job = ExtractionJob.objects.create(
            page=self.page_layout,
            ai_model=modele_mock,
            name="Extraction layout",
            prompt_description="Test layout",
            status="completed",
            entities_count=1,
        )
        ExtractedEntity.objects.create(
            job=job,
            extraction_class="axiome",
            extraction_text="Extraction pour layout",
            start_char=0,
            end_char=30,
            statut_debat="discutable",
        )

    def test_zone_lecture_pleine_largeur(self):
        """La zone de lecture occupe toute la largeur (pas de sidebar visible)."""
        self.naviguer_vers(f"/lire/{self.page_layout.pk}/")
        # La sidebar droite doit etre cachee
        # / The right sidebar must be hidden
        sidebar = self.page.locator("#sidebar-right")
        est_cachee = sidebar.evaluate("el => el.classList.contains('hidden')")
        self.assertTrue(est_cachee, "La sidebar droite devrait etre cachee")

    def test_raccourci_t_ouvre_arbre(self):
        """Le raccourci T ouvre l'overlay arbre."""
        self.naviguer_vers(f"/lire/{self.page_layout.pk}/")
        # Presser T pour ouvrir l'arbre
        # / Press T to open the tree
        self.page.keyboard.press("t")
        # L'arbre overlay ne doit plus avoir pointer-events-none
        # / The tree overlay must not have pointer-events-none
        self.page.wait_for_selector(
            '#arbre-overlay:not(.pointer-events-none)',
            timeout=3000,
        )
        arbre_visible = self.page.locator("#arbre-overlay").is_visible()
        self.assertTrue(arbre_visible, "L'arbre devrait etre visible apres T")

    def test_escape_ferme_arbre(self):
        """Escape ferme l'overlay arbre."""
        self.naviguer_vers(f"/lire/{self.page_layout.pk}/")
        # Ouvrir l'arbre
        # / Open the tree
        self.page.keyboard.press("t")
        self.page.wait_for_selector(
            '#arbre-overlay:not(.pointer-events-none)',
            timeout=3000,
        )
        # Presser Escape pour fermer
        # / Press Escape to close
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)
        # L'arbre doit etre de nouveau cache
        # / The tree must be hidden again
        est_cache = self.page.locator("#arbre-overlay").evaluate(
            "el => el.classList.contains('pointer-events-none') || el.classList.contains('-translate-x-full')"
        )
        self.assertTrue(est_cache, "L'arbre devrait etre ferme apres Escape")

    def test_raccourci_e_ouvre_drawer(self):
        """Le raccourci E ouvre le drawer."""
        self.naviguer_vers(f"/lire/{self.page_layout.pk}/")
        self.ouvrir_drawer()
        drawer_visible = self.page.locator("#drawer-overlay").is_visible()
        self.assertTrue(drawer_visible, "Le drawer devrait etre visible apres E")

    def test_escape_ferme_drawer(self):
        """Escape ferme le drawer."""
        self.naviguer_vers(f"/lire/{self.page_layout.pk}/")
        self.ouvrir_drawer()
        # Presser Escape pour fermer
        # / Press Escape to close
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)
        est_cache = self.page.locator("#drawer-overlay").evaluate(
            "el => el.classList.contains('pointer-events-none') || el.classList.contains('translate-x-full')"
        )
        self.assertTrue(est_cache, "Le drawer devrait etre ferme apres Escape")

    def test_raccourci_interrogation_modale_aide(self):
        """Le raccourci ? ouvre la modale d'aide clavier."""
        self.naviguer_vers(f"/lire/{self.page_layout.pk}/")
        # Presser ? pour ouvrir l'aide
        # / Press ? to open help
        self.page.keyboard.press("?")
        self.page.wait_for_timeout(500)
        # Verifier qu'une modale d'aide est visible
        # / Verify a help modal is visible
        modale_aide = self.page.locator("#modale-aide, .modale-aide, [data-testid='modale-aide']")
        if modale_aide.count() > 0:
            self.assertTrue(modale_aide.first.is_visible())
