"""
Tests E2E — PHASE-24 : Providers IA unifies.
Verifie que les nouveaux modeles Ollama et Anthropic apparaissent correctement
dans le partial config-ia, et que le mapping provider est correct en BDD.
/ E2E tests — PHASE-24: Unified AI providers.
Verifies new Ollama and Anthropic models appear correctly in the config-ia partial,
and that provider mapping is correct in DB.

LOCALISATION : front/tests/e2e/test_12_providers_ia.py

NOTE : Le partial config-ia est charge via GET /config-ia/status/.
Les tests d'interaction (click toggle, select-model) sont deja couverts
par test_05_config_ia.py. Ici on verifie uniquement le contenu specifique
a la PHASE-24 (nouveaux providers dans le dropdown).
/ The config-ia partial is loaded via GET /config-ia/status/.
Interaction tests (click toggle, select-model) are already covered by
test_05_config_ia.py. Here we only verify PHASE-24-specific content
(new providers in dropdown).
"""
from front.tests.e2e.base import PlaywrightLiveTestCase
from core.models import AIModel, Configuration


class E2EProvidersIADropdownTest(PlaywrightLiveTestCase):
    """Tests E2E : le dropdown config-ia affiche les modeles des nouveaux providers.
    / E2E tests: config-ia dropdown displays models from new providers."""

    def setUp(self):
        super().setUp()
        # Creer une page de test / Create a test page
        self.page_test = self.creer_page_demo(
            "Page test providers", "<p>Contenu pour test providers.</p>",
        )

        # Creer des modeles pour chaque provider
        # / Create models for each provider
        self.modele_mock = AIModel.objects.create(
            name="Mock Ref",
            model_choice="mock",
            is_active=True,
        )
        self.modele_ollama = AIModel.objects.create(
            name="Llama 3 Local",
            model_choice="llama3",
            base_url="http://localhost:11434",
            is_active=True,
        )
        self.modele_anthropic = AIModel.objects.create(
            name="Claude Sonnet 4",
            model_choice="claude-sonnet-4-20250514",
            api_key="sk-test-e2e",
            is_active=True,
        )

    def test_dropdown_contient_modeles_ollama_et_anthropic(self):
        """Le partial /config-ia/status/ doit lister les 3 modeles dans un select.
        Quand il y a 3 modeles actifs, le template affiche un dropdown (cas 'else').
        / The /config-ia/status/ partial must list all 3 models in a select."""
        # Naviguer vers le partial config-ia directement
        # / Navigate to the config-ia partial directly
        self.naviguer_vers("/config-ia/status/")

        # Le select doit etre present car on a 3 modeles actifs
        # / The select must be present since we have 3 active models
        select_modele = self.page.locator('[data-testid="config-ia-model-select"]')
        self.assertTrue(select_modele.is_visible(), "Le select config-ia devrait etre visible avec 3 modeles")

        # Recuperer toutes les options du select
        # / Get all select options
        options_texte = select_modele.locator("option").all_text_contents()

        # Verifier que les 3 modeles sont dans le dropdown
        # / Verify all 3 models are in the dropdown
        self.assertTrue(
            any("Mock Ref" in option for option in options_texte),
            f"Mock Ref manquant dans {options_texte}",
        )
        self.assertTrue(
            any("Llama 3 Local" in option for option in options_texte),
            f"Llama 3 Local (Ollama) manquant dans {options_texte}",
        )
        self.assertTrue(
            any("Claude Sonnet 4" in option for option in options_texte),
            f"Claude Sonnet 4 (Anthropic) manquant dans {options_texte}",
        )

    def test_dropdown_nombre_options_correct(self):
        """Le dropdown doit avoir exactement 3 options (1 par modele actif).
        / The dropdown must have exactly 3 options (1 per active model)."""
        self.naviguer_vers("/config-ia/status/")
        select_modele = self.page.locator('[data-testid="config-ia-model-select"]')
        nombre_options = select_modele.locator("option").count()
        self.assertEqual(nombre_options, 3, f"Attendu 3 options, trouve {nombre_options}")

    def test_bouton_toggle_affiche_nom_anthropic_quand_actif(self):
        """Si l'IA est active avec un modele Anthropic, le bouton affiche son nom.
        / If AI is active with an Anthropic model, the button displays its name."""
        # Configurer l'IA avec le modele Anthropic
        # / Configure AI with the Anthropic model
        config = Configuration.get_solo()
        config.ai_active = True
        config.ai_model = self.modele_anthropic
        config.save()

        # Charger le partial / Load the partial
        self.naviguer_vers("/config-ia/status/")

        # Le bouton toggle vert doit afficher le nom du modele
        # / The green toggle button must display the model name
        bouton_toggle = self.page.locator('[data-testid="config-ia-toggle-button"]')
        self.assertTrue(bouton_toggle.is_visible(), "Le bouton toggle devrait etre visible")
        texte_bouton = bouton_toggle.text_content()
        self.assertIn("Claude Sonnet 4", texte_bouton)

    def test_bouton_toggle_affiche_nom_ollama_quand_actif(self):
        """Si l'IA est active avec un modele Ollama, le bouton affiche son nom.
        / If AI is active with an Ollama model, the button displays its name."""
        config = Configuration.get_solo()
        config.ai_active = True
        config.ai_model = self.modele_ollama
        config.save()

        self.naviguer_vers("/config-ia/status/")

        bouton_toggle = self.page.locator('[data-testid="config-ia-toggle-button"]')
        self.assertTrue(bouton_toggle.is_visible())
        texte_bouton = bouton_toggle.text_content()
        self.assertIn("Llama 3 Local", texte_bouton)


class E2EProvidersIAModelesBDDTest(PlaywrightLiveTestCase):
    """Tests E2E : les modeles des nouveaux providers sont corrects en BDD.
    / E2E tests: models from new providers are correct in DB."""

    def test_provider_ollama_deduit_automatiquement(self):
        """Un AIModel avec model_choice='llama3' doit avoir provider='ollama' apres save().
        / An AIModel with model_choice='llama3' must have provider='ollama' after save()."""
        modele_ollama = AIModel.objects.create(
            name="Ollama E2E",
            model_choice="llama3",
            base_url="http://gpu:11434",
            is_active=True,
        )
        modele_ollama.refresh_from_db()
        self.assertEqual(modele_ollama.provider, "ollama")
        self.assertEqual(modele_ollama.model_name, "llama3")
        self.assertEqual(modele_ollama.base_url, "http://gpu:11434")

    def test_provider_anthropic_deduit_automatiquement(self):
        """Un AIModel avec model_choice Claude doit avoir provider='anthropic' apres save().
        / An AIModel with Claude model_choice must have provider='anthropic' after save()."""
        modele_anthropic = AIModel.objects.create(
            name="Anthropic E2E",
            model_choice="claude-sonnet-4-20250514",
            api_key="sk-e2e-test",
            is_active=True,
        )
        modele_anthropic.refresh_from_db()
        self.assertEqual(modele_anthropic.provider, "anthropic")
        self.assertEqual(modele_anthropic.model_name, "claude-sonnet-4-20250514")

    def test_tarifs_ollama_gratuits(self):
        """Les modeles Ollama doivent etre gratuits (0.0, 0.0).
        / Ollama models must be free (0.0, 0.0)."""
        modele_ollama = AIModel.objects.create(
            name="Ollama Tarifs", model_choice="llama3", is_active=True,
        )
        cout_input, cout_output = modele_ollama.cout_par_million_tokens()
        self.assertEqual(cout_input, 0.0)
        self.assertEqual(cout_output, 0.0)

    def test_tarifs_anthropic_non_nuls(self):
        """Les modeles Anthropic doivent avoir des tarifs non nuls.
        / Anthropic models must have non-zero pricing."""
        modele_sonnet = AIModel.objects.create(
            name="Sonnet Tarifs", model_choice="claude-sonnet-4-20250514", is_active=True,
        )
        cout_input, cout_output = modele_sonnet.cout_par_million_tokens()
        self.assertGreater(cout_input, 0.0)
        self.assertGreater(cout_output, 0.0)

    def test_core_services_supprime(self):
        """Le fichier core/services.py ne doit plus exister (code mort supprime).
        / core/services.py must no longer exist (dead code deleted)."""
        from pathlib import Path
        from django.conf import settings
        chemin_services = Path(settings.BASE_DIR) / "core" / "services.py"
        self.assertFalse(chemin_services.exists(), "core/services.py devrait etre supprime")
