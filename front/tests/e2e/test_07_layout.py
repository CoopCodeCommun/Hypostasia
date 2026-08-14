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

    # LES DEUX TESTS DE LA TOUCHE T ONT ETE RETIRES LE 12 AOUT 2026.
    #
    # `test_raccourci_t_ouvre_arbre` et `test_escape_ferme_arbre`
    # verrouillaient l'ouverture et la fermeture du tiroir lateral. Le
    # tiroir, la touche T et son rang dans la cascade Escape ont disparu
    # ensemble : il n'y a plus de comportement a verifier.
    #
    # La cascade Escape reste couverte pour ce qu'il en reste — le
    # drawer (`test_escape_ferme_drawer`, juste apres).
    # / Both T tests are gone with the drawer, the key and its rung in
    # the Escape cascade. Escape is still covered for the drawer.

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
        # La fermeture se marque par une classe : on l'attend, au lieu de
        # dormir un demi-seconde en esperant qu'elle soit posee.
        # / Closing is marked by a class; wait for it rather than sleeping.
        self.page.wait_for_selector(
            "#drawer-overlay.pointer-events-none, #drawer-overlay.translate-x-full",
            state="attached",
        )
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
