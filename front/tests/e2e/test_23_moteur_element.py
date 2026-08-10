"""
Tests E2E — parcours complet du moteur ELEMENT (BR-F, SPEC § 9.4).
/ E2E tests — full ELEMENT engine journey.

LOCALISATION : front/tests/e2e/test_23_moteur_element.py

Le parcours REEL de bout en bout, au navigateur : importer un fichier
markdown par le bouton d'import, puis rouvrir la note et verifier que
la lecture vient des ELEMENTS (blocs BR-D), pas du HTML readability.

En E2E, Celery est en mode EAGER : l'ingestion Docling tourne
SYNCHRONE pendant le POST d'import — le premier import de la classe
paie donc le chargement de Docling (~30-60 s), les timeouts sont
larges expres. / Celery is eager here: Docling runs inside the import
POST; generous timeouts on purpose.
"""

import os
import tempfile

from .base import PlaywrightLiveTestCase


class MoteurElementE2ETest(PlaywrightLiveTestCase):
    """Import → ingestion → lecture par blocs. / Import → blocks."""

    def setUp(self):
        super().setUp()
        # L'import exige d'etre connecte (PHASE-25).
        # / Importing requires being logged in.
        self.creer_utilisateur_demo(
            username="testeur_element", password="motdepasse123",
        )
        self.se_connecter("testeur_element", "motdepasse123")

    def test_un_import_markdown_se_lit_par_elements(self):
        contenu_du_pad = (
            "# Rapport E2E du moteur element\n\n"
            "## Premiere section\n\n"
            "Un paragraphe que la lecture doit afficher en bloc.\n\n"
            "- premiere puce du parcours\n"
            "- seconde puce du parcours\n"
        )
        fichier_temp = tempfile.NamedTemporaryFile(
            suffix=".md", delete=False, mode="w", encoding="utf-8")
        fichier_temp.write(contenu_du_pad)
        fichier_temp.close()

        try:
            self.naviguer_vers("/",
            )
            input_fichier = self.page.locator("#input-import-fichier")
            input_fichier.set_input_files(fichier_temp.name,

            )

            # L'import + l'ingestion Docling (EAGER) tournent dans le
            # POST : delai large pour absorber le premier chargement de
            # Docling dans ce processus (~10-15 s mesurees).
            # / Import + eager Docling run inside the POST; generous
            # timeout for Docling's first load in this process.
            self.page.wait_for_selector(
                "#readability-content, .titre-page-cliquable",
                timeout=120_000,

            )

            # La note est nee ELEMENT en base.
            # / The note was born ELEMENT in the database.
            from core.models import Page
            note = Page.objects.filter(
                original_filename__endswith=".md").latest("id",
            )
            self.assertTrue(note.elements.exists())
            self.assertGreaterEqual(note.elements.count(), 4,

            )

            # On ROUVRE la note : la lecture doit venir des blocs
            # elements (BR-D), pas du HTML readability.
            # / Reopen the note: reading comes from element blocks.
            self.naviguer_vers(f"/lire/{note.pk}/",
            )
            self.page.wait_for_selector(
                '[data-testid="blocs-elements"]', timeout=30_000,

            )

            zone = self.page.locator('[data-testid="blocs-elements"]')
            texte_de_la_zone = zone.text_content()
            self.assertIn("Premiere section", texte_de_la_zone,
            )
            self.assertIn("premiere puce du parcours", texte_de_la_zone)

            # Le titre est un vrai bloc de titre, la puce un vrai <li>.
            # / The heading is a real heading block, the bullet a <li>.
            self.assertGreaterEqual(
                self.page.locator(
                    '[data-testid="blocs-elements"] h3, '
                    '[data-testid="blocs-elements"] h2').count(),
                1,
            )
            self.assertEqual(
                self.page.locator(
                    '[data-testid="blocs-elements"] ul li').count(),
                2)
        finally:
            os.unlink(fichier_temp.name)
