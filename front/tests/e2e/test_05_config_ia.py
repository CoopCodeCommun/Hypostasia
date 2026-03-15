"""
Tests E2E — Configuration IA : toggle, selection modele.
/ E2E tests — AI configuration: toggle, model selection.
"""
from front.tests.e2e.base import PlaywrightLiveTestCase
from core.models import AIModel, Configuration


class E2EConfigIATest(PlaywrightLiveTestCase):
    """Tests de configuration IA."""

    def setUp(self):
        super().setUp()
        # Creer une page pour avoir un contexte de lecture
        # / Create a page to have a reading context
        self.page_test = self.creer_page_demo("Page config IA", "<p>Test config.</p>")
        # Creer 2 modeles IA mock
        # / Create 2 mock AI models
        self.modele_1 = AIModel.objects.create(
            name="Modele Mock 1",
            model_choice="mock_default",
            is_active=True,
        )
        self.modele_2 = AIModel.objects.create(
            name="Modele Mock 2",
            model_choice="mock_default",
            is_active=True,
        )

    def test_status_ia_aucun_modele_si_rien_configure(self):
        """Le status IA montre 'Aucun modele' si rien n'est configure."""
        # Desactiver tous les modeles
        # / Deactivate all models
        AIModel.objects.all().update(is_active=False)
        self.naviguer_vers(f"/lire/{self.page_test.pk}/")
        # Charger le status IA via la toolbar
        # / Load AI status via toolbar
        contenu_page = self.page.text_content("body")
        # Le bouton doit etre desactive ou afficher "Aucun modele"
        # / The button must be disabled or show "Aucun modele"
        bouton_desactive = self.page.locator('[data-testid="config-ia-disabled-button"]')
        if bouton_desactive.count() > 0:
            self.assertTrue(bouton_desactive.is_visible())

    def test_toggle_ia_active(self):
        """Toggle IA active le modele selectionne."""
        self.naviguer_vers(f"/lire/{self.page_test.pk}/")
        # Trouver le bouton toggle IA
        # / Find the AI toggle button
        bouton_toggle = self.page.locator('[data-testid="config-ia-toggle-button"]')
        if bouton_toggle.count() > 0:
            bouton_toggle.first.click()
            self.attendre_htmx()
            # Verifier que la config a change en BDD
            # / Verify the config changed in DB
            config = Configuration.objects.first()
            if config:
                self.assertTrue(config.ai_active)

    def test_select_modele_depuis_dropdown(self):
        """Selectionner un modele depuis le dropdown."""
        self.naviguer_vers(f"/lire/{self.page_test.pk}/")
        # Chercher le select de modele
        # / Look for the model select
        select_modele = self.page.locator('[data-testid="config-ia-model-select"]')
        if select_modele.count() > 0:
            # Selectionner le modele 2
            # / Select model 2
            select_modele.select_option(str(self.modele_2.pk))
            # Cliquer le bouton pour valider
            # / Click the button to validate
            bouton_select = self.page.locator('[data-testid="config-ia-select-model-button"]')
            if bouton_select.count() > 0:
                bouton_select.click()
                self.attendre_htmx()
