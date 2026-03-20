"""
Tests E2E — Confirmation analyse : tokens, cout, prompt, selecteur analyseur.
/ E2E tests — Analysis confirmation: tokens, cost, prompt, analyzer selector.

DESACTIVE (2026-03-20) : le bouton btn-toolbar-analyser n'existe plus dans la toolbar.
Le workflow d'analyse a ete refonde en PHASE-26g (Hub d'analyse via le drawer).
Ces tests doivent etre reecrits pour le nouveau workflow (analyser depuis le drawer).
/ DISABLED (2026-03-20): btn-toolbar-analyser no longer exists in the toolbar.
The analysis workflow was redesigned in PHASE-26g (analysis hub via drawer).
These tests must be rewritten for the new workflow (analyze from the drawer).
"""
import unittest

from front.tests.e2e.base import PlaywrightLiveTestCase
from core.models import AIModel, Configuration
from hypostasis_extractor.models import (
    AnalyseurSyntaxique,
    PromptPiece,
    AnalyseurExample,
    ExampleExtraction,
    ExtractionAttribute,
)


@unittest.skip("PHASE-26g a supprime btn-toolbar-analyser — tests a reecrire pour le workflow drawer")
class E2EConfirmationAnalyseTest(PlaywrightLiveTestCase):
    """Tests de la boite de confirmation avant analyse IA."""

    def setUp(self):
        super().setUp()
        # Creer un utilisateur et se connecter
        # / Create a user and log in
        self.utilisateur_test = self.creer_utilisateur_demo()
        self.se_connecter("testuser", "testpass123")

        # Creer une page avec du contenu pour l'analyse
        # / Create a page with content for analysis
        self.page_analyse = self.creer_page_demo(
            "Page analyse E2E",
            "<p>L'intelligence artificielle est une revolution technologique majeure.</p>"
            "<p>Les enjeux ethiques restent a debattre.</p>",
            owner=self.utilisateur_test,
        )

        # Creer un modele IA actif
        # / Create an active AI model
        self.modele_ia = AIModel.objects.create(
            name="Gemini Test E2E",
            model_choice="gemini-2.5-flash",
            is_active=True,
        )

        # Configurer la configuration singleton avec IA activee
        # / Configure the singleton configuration with AI enabled
        configuration = Configuration.get_solo()
        configuration.ai_active = True
        configuration.ai_model = self.modele_ia
        configuration.save()

        # Creer un analyseur avec pieces de prompt et exemple few-shot
        # / Create an analyzer with prompt pieces and few-shot example
        self.analyseur = AnalyseurSyntaxique.objects.create(
            name="Hypostasia Test",
            type_analyseur="analyser",
            is_active=True,
        )
        PromptPiece.objects.create(
            analyseur=self.analyseur,
            name="Instruction principale",
            role="instruction",
            content="Tu es Hypostasia, un expert en analyse argumentative.",
            order=0,
        )
        PromptPiece.objects.create(
            analyseur=self.analyseur,
            name="Format de sortie",
            role="format",
            content="Chaque extraction a une classe et un texte.",
            order=1,
        )

        # Creer un exemple few-shot avec attributs
        # / Create a few-shot example with attributes
        exemple_fewshot = AnalyseurExample.objects.create(
            analyseur=self.analyseur,
            name="Exemple debat IA",
            example_text="L'IA va changer le monde. C'est une certitude.",
            order=0,
        )
        extraction_exemple = ExampleExtraction.objects.create(
            example=exemple_fewshot,
            extraction_class="hypostase",
            extraction_text="L'IA va changer le monde",
            order=0,
        )
        ExtractionAttribute.objects.create(
            extraction=extraction_exemple,
            key="Hypostases",
            value="conjecture",
            order=0,
        )

    def test_bouton_analyser_ouvre_confirmation(self):
        """Cliquer le bouton Analyser affiche la boite de confirmation."""
        self.naviguer_vers(f"/lire/{self.page_analyse.pk}/")
        # Cliquer le bouton Analyser dans la toolbar
        # / Click the Analyser button in the toolbar
        self.page.click('[data-testid="btn-toolbar-analyser"]')
        # Attendre que la confirmation apparaisse dans #zone-lecture
        # / Wait for the confirmation to appear in #zone-lecture
        self.page.wait_for_selector(
            '[data-testid="confirmation-analyse"]',
            timeout=10000,
        )
        # La confirmation doit etre visible
        # / The confirmation must be visible
        confirmation = self.page.locator('[data-testid="confirmation-analyse"]')
        self.assertTrue(confirmation.is_visible())

    def test_confirmation_affiche_tokens_input(self):
        """La confirmation affiche l'estimation des tokens input."""
        self.naviguer_vers(f"/lire/{self.page_analyse.pk}/")
        self.page.click('[data-testid="btn-toolbar-analyser"]')
        self.page.wait_for_selector('[data-testid="estimation-tokens"]', timeout=10000)
        # La zone d'estimation doit contenir "Tokens input"
        # / The estimation zone must contain "Tokens input"
        contenu_estimation = self.page.text_content('[data-testid="estimation-tokens"]')
        self.assertIn("Tokens input", contenu_estimation)

    def test_confirmation_affiche_tokens_output(self):
        """La confirmation affiche l'estimation des tokens output."""
        self.naviguer_vers(f"/lire/{self.page_analyse.pk}/")
        self.page.click('[data-testid="btn-toolbar-analyser"]')
        self.page.wait_for_selector('[data-testid="estimation-tokens"]', timeout=10000)
        contenu_estimation = self.page.text_content('[data-testid="estimation-tokens"]')
        self.assertIn("Tokens output", contenu_estimation)

    def test_confirmation_affiche_cout_estime(self):
        """La confirmation affiche le cout estime en euros."""
        self.naviguer_vers(f"/lire/{self.page_analyse.pk}/")
        self.page.click('[data-testid="btn-toolbar-analyser"]')
        self.page.wait_for_selector('[data-testid="estimation-tokens"]', timeout=10000)
        contenu_estimation = self.page.text_content('[data-testid="estimation-tokens"]')
        self.assertIn("Cout estime", contenu_estimation)
        # Le cout doit contenir le symbole euro
        # / Cost must contain the euro symbol
        self.assertIn("\u20ac", contenu_estimation)

    def test_confirmation_affiche_nom_analyseur(self):
        """La confirmation affiche le nom de l'analyseur."""
        self.naviguer_vers(f"/lire/{self.page_analyse.pk}/")
        self.page.click('[data-testid="btn-toolbar-analyser"]')
        self.page.wait_for_selector('[data-testid="confirmation-analyse"]', timeout=10000)
        contenu_confirmation = self.page.text_content('[data-testid="confirmation-analyse"]')
        self.assertIn("Hypostasia Test", contenu_confirmation)

    def test_confirmation_affiche_nom_modele_ia(self):
        """La confirmation affiche le nom du modele IA."""
        self.naviguer_vers(f"/lire/{self.page_analyse.pk}/")
        self.page.click('[data-testid="btn-toolbar-analyser"]')
        self.page.wait_for_selector('[data-testid="confirmation-analyse"]', timeout=10000)
        contenu_confirmation = self.page.text_content('[data-testid="confirmation-analyse"]')
        # Le modele mock_default n'a pas de display_name, mais "Gemini" ou le nom doit etre present
        # / The mock_default model has no display_name, but "Gemini" or the name must be present
        self.assertTrue(
            "Gemini" in contenu_confirmation or "gemini" in contenu_confirmation.lower(),
            f"Le nom du modele IA devrait etre present dans la confirmation",
        )

    def test_bouton_voir_prompt_complet(self):
        """Le bouton 'Voir le prompt complet' affiche le prompt."""
        self.naviguer_vers(f"/lire/{self.page_analyse.pk}/")
        self.page.click('[data-testid="btn-toolbar-analyser"]')
        self.page.wait_for_selector('[data-testid="btn-voir-prompt"]', timeout=10000)
        # La zone prompt doit etre cachee au depart
        # / The prompt zone must be hidden initially
        zone_prompt = self.page.locator("#zone-prompt-complet")
        est_cachee = zone_prompt.evaluate("el => el.classList.contains('hidden')")
        self.assertTrue(est_cachee, "Le prompt doit etre cache au depart")
        # Cliquer le bouton pour voir le prompt
        # / Click the button to view the prompt
        self.page.click('[data-testid="btn-voir-prompt"]')
        self.page.wait_for_timeout(300)
        # La zone prompt doit etre visible maintenant
        # / The prompt zone must be visible now
        est_visible = zone_prompt.evaluate("el => !el.classList.contains('hidden')")
        self.assertTrue(est_visible, "Le prompt doit etre visible apres le clic")
        # Le prompt doit contenir le texte de la piece de prompt
        # / The prompt must contain the prompt piece text
        contenu_prompt = zone_prompt.text_content()
        self.assertIn("Hypostasia", contenu_prompt)

    def test_prompt_complet_contient_texte_source(self):
        """Le prompt complet contient le texte source de la page analysee."""
        self.naviguer_vers(f"/lire/{self.page_analyse.pk}/")
        self.page.click('[data-testid="btn-toolbar-analyser"]')
        self.page.wait_for_selector('[data-testid="btn-voir-prompt"]', timeout=10000)
        # Ouvrir le prompt complet
        # / Open the full prompt
        self.page.click('[data-testid="btn-voir-prompt"]')
        self.page.wait_for_timeout(300)
        contenu_prompt = self.page.locator("#zone-prompt-complet").text_content()
        # Le texte source de la page doit etre dans le prompt
        # / The page's source text must be in the prompt
        self.assertIn("intelligence artificielle", contenu_prompt.lower())

    def test_prompt_complet_contient_exemples_fewshot(self):
        """Le prompt complet contient les exemples few-shot."""
        self.naviguer_vers(f"/lire/{self.page_analyse.pk}/")
        self.page.click('[data-testid="btn-toolbar-analyser"]')
        self.page.wait_for_selector('[data-testid="btn-voir-prompt"]', timeout=10000)
        self.page.click('[data-testid="btn-voir-prompt"]')
        self.page.wait_for_timeout(300)
        contenu_prompt = self.page.locator("#zone-prompt-complet").text_content()
        # L'exemple few-shot doit etre mentionne
        # / The few-shot example must be mentioned
        self.assertIn("EXEMPLES FEW-SHOT", contenu_prompt)
        self.assertIn("L'IA va changer le monde", contenu_prompt)

    def test_bouton_annuler_recharge_page(self):
        """Le bouton Annuler recharge la page de lecture."""
        self.naviguer_vers(f"/lire/{self.page_analyse.pk}/")
        self.page.click('[data-testid="btn-toolbar-analyser"]')
        self.page.wait_for_selector('[data-testid="btn-annuler-analyse"]', timeout=10000)
        # Cliquer Annuler
        # / Click Cancel
        self.page.click('[data-testid="btn-annuler-analyse"]')
        self.attendre_htmx()
        # La zone de lecture doit afficher le contenu de la page (pas la confirmation)
        # / The reading zone must display the page content (not the confirmation)
        contenu_lecture = self.page.text_content('[data-testid="bibliotheque-colonne-lecture"]')
        self.assertIn("intelligence artificielle", contenu_lecture.lower())

    def test_confirmation_affiche_nombre_exemples(self):
        """La confirmation affiche le nombre d'exemples few-shot."""
        self.naviguer_vers(f"/lire/{self.page_analyse.pk}/")
        self.page.click('[data-testid="btn-toolbar-analyser"]')
        self.page.wait_for_selector('[data-testid="confirmation-analyse"]', timeout=10000)
        contenu_confirmation = self.page.text_content('[data-testid="confirmation-analyse"]')
        # Doit mentionner "1" comme nombre d'exemples
        # / Must mention "1" as number of examples
        self.assertIn("1", contenu_confirmation)

    def test_confirmation_affiche_nombre_pieces(self):
        """La confirmation affiche le nombre de pieces de prompt."""
        self.naviguer_vers(f"/lire/{self.page_analyse.pk}/")
        self.page.click('[data-testid="btn-toolbar-analyser"]')
        self.page.wait_for_selector('[data-testid="confirmation-analyse"]', timeout=10000)
        contenu_confirmation = self.page.text_content('[data-testid="confirmation-analyse"]')
        # Doit mentionner "2" comme nombre de pieces
        # / Must mention "2" as number of pieces
        self.assertIn("2", contenu_confirmation)
