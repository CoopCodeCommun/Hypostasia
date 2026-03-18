"""
Tests E2E PHASE-25b — Page Mon token API.
/ E2E tests PHASE-25b — My API token page.

Lancer avec : uv run python manage.py test front.tests.e2e.test_15_token -v2
"""

from front.tests.e2e.base import PlaywrightLiveTestCase


class Phase25bTokenE2ETest(PlaywrightLiveTestCase):
    """Tests E2E pour la page Mon token API.
    / E2E tests for the My API token page."""

    # ====================================================================
    # Helpers auth
    # ====================================================================

    def creer_et_connecter(self, username="token_e2e", password="testpass123"):
        """
        Cree un utilisateur, navigue vers login, remplit le formulaire.
        / Create user, navigate to login, fill form.
        """
        from django.contrib.auth.models import User
        User.objects.create_user(username=username, password=password)

        self.page.goto(f"{self.live_server_url}/auth/login/")
        self.page.fill('[data-testid="input-username"]', username)
        self.page.fill('[data-testid="input-password"]', password)
        self.page.click('[data-testid="btn-submit-login"]')
        self.page.wait_for_url(f"{self.live_server_url}/")

    # ====================================================================
    # Tests
    # ====================================================================

    def test_page_token_affiche_token_et_boutons(self):
        """La page /auth/token/ affiche le token, le bouton copier et le bouton regenerer.
        / Page /auth/token/ shows token, copy button and regenerate button."""
        self.creer_et_connecter()
        self.page.goto(f"{self.live_server_url}/auth/token/")

        # Verifie que la page s'affiche correctement
        # / Check page renders correctly
        self.assertIn("Mon token API", self.page.content())

        # Verifie le champ token et les boutons
        # / Check token field and buttons
        champ_token = self.page.locator('[data-testid="token-value"]')
        self.assertTrue(champ_token.is_visible())
        valeur_token = champ_token.input_value()
        self.assertTrue(len(valeur_token) > 10, "Le token doit etre non vide")

        bouton_copier = self.page.locator('[data-testid="btn-copier-token"]')
        self.assertTrue(bouton_copier.is_visible())

        bouton_regenerer = self.page.locator('[data-testid="btn-regenerer-token"]')
        self.assertTrue(bouton_regenerer.is_visible())

    def test_regeneration_token(self):
        """La regeneration du token change la valeur affichee.
        / Token regeneration changes the displayed value."""
        self.creer_et_connecter()
        self.page.goto(f"{self.live_server_url}/auth/token/")

        # Recuperer le token initial
        # / Get initial token
        token_initial = self.page.locator('[data-testid="token-value"]').input_value()

        # Regenerer
        # / Regenerate
        self.page.click('[data-testid="btn-regenerer-token"]')
        self.page.wait_for_load_state("networkidle")

        # Verifier que le token a change
        # / Check token changed
        nouveau_token = self.page.locator('[data-testid="token-value"]').input_value()
        self.assertNotEqual(token_initial, nouveau_token)
        self.assertIn("regenere", self.page.content().lower())

    def test_lien_menu_utilisateur(self):
        """Le lien 'Mon token API' existe dans le menu utilisateur.
        / 'Mon token API' link exists in user menu."""
        self.creer_et_connecter()

        # Ouvrir le menu utilisateur
        # / Open user menu
        self.page.click('[data-testid="btn-user-menu"]')
        self.page.wait_for_selector('[data-testid="user-menu-dropdown"]:not(.hidden)')

        # Verifier le lien
        # / Check link
        lien_token = self.page.locator('[data-testid="btn-token-api"]')
        self.assertTrue(lien_token.is_visible())
        self.assertEqual(lien_token.get_attribute("href"), "/auth/token/")
