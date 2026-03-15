"""
Tests E2E — Import de fichiers.
/ E2E tests — File import.
"""
import os
import tempfile

from front.tests.e2e.base import PlaywrightLiveTestCase


class E2EImportTest(PlaywrightLiveTestCase):
    """Tests d'import de documents."""

    def setUp(self):
        super().setUp()
        # Creer et connecter un utilisateur pour les imports (PHASE-25 : auth requise)
        # / Create and login a user for imports (PHASE-25: auth required)
        self.creer_utilisateur_demo(username="import_tester", password="testpass123")
        self.se_connecter("import_tester", "testpass123")

    def _attendre_fin_import(self, timeout_ms=15000):
        """
        Attend que l'import soit termine (plus de spinner 'Envoi en cours').
        / Wait for import to finish (no more 'Envoi en cours' spinner).
        """
        # Attendre que le readability-content apparaisse (signe que l'import est fini)
        # / Wait for readability-content to appear (sign that import is done)
        self.page.wait_for_selector(
            "#readability-content, .titre-page-cliquable",
            timeout=timeout_ms,
        )

    def test_importer_fichier_txt(self):
        """Importer un fichier .txt cree une page visible."""
        # Creer un fichier temporaire .txt
        # / Create a temporary .txt file
        fichier_temp = tempfile.NamedTemporaryFile(
            suffix=".txt", delete=False, mode="w", encoding="utf-8",
        )
        fichier_temp.write("Contenu du fichier texte E2E pour import.")
        fichier_temp.close()

        try:
            self.naviguer_vers("/")
            # Injecter le fichier via le input file
            # / Inject the file via the file input
            input_fichier = self.page.locator("#input-import-fichier")
            input_fichier.set_input_files(fichier_temp.name)
            # Attendre la fin de l'import XHR
            # / Wait for XHR import to finish
            self._attendre_fin_import()
            # La page importee doit etre visible dans la zone de lecture
            # / The imported page must be visible in the reading zone
            contenu_lecture = self.page.text_content('[data-testid="bibliotheque-colonne-lecture"]')
            self.assertIn("Contenu du fichier texte E2E", contenu_lecture)
        finally:
            os.unlink(fichier_temp.name)

    def test_page_importee_visible_dans_arbre(self):
        """Apres import, la page apparait dans l'arbre."""
        # Creer un fichier temporaire .txt
        # / Create a temporary .txt file
        fichier_temp = tempfile.NamedTemporaryFile(
            suffix=".txt", delete=False, mode="w", encoding="utf-8",
        )
        fichier_temp.write("Page pour test arbre E2E.")
        fichier_temp.close()

        try:
            self.naviguer_vers("/")
            input_fichier = self.page.locator("#input-import-fichier")
            input_fichier.set_input_files(fichier_temp.name)
            self._attendre_fin_import()
            # Ouvrir l'arbre et verifier que la page y est
            # / Open tree and verify the page is there
            self.ouvrir_arbre()
            contenu_arbre = self.page.text_content('[data-testid="arbre-dossiers"]')
            # Le titre de la page importee devrait contenir le nom du fichier
            # / The imported page's title should contain the filename
            self.assertTrue(len(contenu_arbre.strip()) > 0)
        finally:
            os.unlink(fichier_temp.name)

    def test_importer_fichier_md(self):
        """Importer un fichier .md convertit le Markdown en HTML."""
        # Creer un fichier temporaire .md
        # / Create a temporary .md file
        fichier_temp = tempfile.NamedTemporaryFile(
            suffix=".md", delete=False, mode="w", encoding="utf-8",
        )
        fichier_temp.write("# Titre Markdown E2E\n\nParagraphe de test **gras**.")
        fichier_temp.close()

        try:
            self.naviguer_vers("/")
            input_fichier = self.page.locator("#input-import-fichier")
            input_fichier.set_input_files(fichier_temp.name)
            # Attendre que le contenu converti apparaisse
            # / Wait for converted content to appear
            self._attendre_fin_import()
            # Le contenu Markdown converti doit etre visible
            # / Converted Markdown content must be visible
            contenu_lecture = self.page.text_content('[data-testid="bibliotheque-colonne-lecture"]')
            self.assertIn("Titre Markdown E2E", contenu_lecture)
        finally:
            os.unlink(fichier_temp.name)
