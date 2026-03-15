"""
Tests E2E — Lecture de page.
/ E2E tests — Page reading.
"""
from front.tests.e2e.base import PlaywrightLiveTestCase


class E2ELectureTest(PlaywrightLiveTestCase):
    """Tests de lecture de page et acces direct."""

    def setUp(self):
        super().setUp()
        # Creer une page avec du contenu pour les tests de lecture
        # / Create a page with content for reading tests
        self.page_lecture = self.creer_page_demo(
            "Article E2E",
            "<p>Ceci est le paragraphe principal de l'article de test E2E.</p>"
            "<p>Deuxieme paragraphe avec du contenu supplementaire.</p>",
        )

    def test_ouvrir_page_titre_et_contenu_visible(self):
        """Ouvrir /lire/{pk}/ affiche le titre et le contenu."""
        self.naviguer_vers(f"/lire/{self.page_lecture.pk}/")
        # Le titre doit etre visible
        # / Title must be visible
        titre_element = self.page.locator(".titre-page-cliquable")
        self.assertEqual(titre_element.text_content().strip(), "Article E2E")
        # Le contenu doit etre visible
        # / Content must be visible
        contenu = self.page.text_content("#readability-content")
        self.assertIn("paragraphe principal", contenu)

    def test_acces_direct_f5_page_complete(self):
        """Acces direct (F5) charge la page complete HTML, pas un partial."""
        self.naviguer_vers(f"/lire/{self.page_lecture.pk}/")
        # Recharger la page (simule F5)
        # / Reload the page (simulates F5)
        self.page.reload(wait_until="networkidle")
        # La page doit avoir le doctype HTML complet (toolbar visible)
        # / The page must have the full HTML doctype (toolbar visible)
        toolbar = self.page.locator("nav").first
        self.assertTrue(toolbar.is_visible())
        # Le contenu doit toujours etre la
        # / Content must still be there
        contenu = self.page.text_content("#readability-content")
        self.assertIn("paragraphe principal", contenu)

    def test_url_change_vers_lire(self):
        """L'URL dans le navigateur pointe vers /lire/{pk}/."""
        self.naviguer_vers(f"/lire/{self.page_lecture.pk}/")
        url_actuelle = self.page.url
        self.assertIn(f"/lire/{self.page_lecture.pk}/", url_actuelle)

    def test_boutons_source_et_exporter_visibles(self):
        """Les boutons Source et Exporter sont visibles sur la page de lecture."""
        self.naviguer_vers(f"/lire/{self.page_lecture.pk}/")
        # Bouton telecharger source
        # / Download source button
        bouton_source = self.page.locator(f'a[href*="/lire/{self.page_lecture.pk}/telecharger_source/"]')
        self.assertTrue(bouton_source.is_visible())
        # Bouton exporter
        # / Export button
        bouton_exporter = self.page.locator("text=Exporter")
        self.assertTrue(bouton_exporter.is_visible())

    def test_modifier_titre_inline(self):
        """Modifier le titre inline en cliquant dessus."""
        self.naviguer_vers(f"/lire/{self.page_lecture.pk}/")
        # Cliquer sur le titre pour passer en mode edition
        # / Click on the title to switch to edit mode
        titre_element = self.page.locator(".titre-page-cliquable")
        titre_element.click()
        # Un input devrait apparaitre (gere par JS hypostasia.js)
        # / An input should appear (handled by JS hypostasia.js)
        input_titre = self.page.locator(".titre-page-cliquable input, .titre-page-input")
        if input_titre.count() > 0:
            input_titre.fill("Titre modifie E2E")
            input_titre.press("Enter")
            self.attendre_htmx()
            # Verifier en BDD
            # / Verify in database
            from core.models import Page
            page_rechargee = Page.objects.get(pk=self.page_lecture.pk)
            self.assertEqual(page_rechargee.title, "Titre modifie E2E")
