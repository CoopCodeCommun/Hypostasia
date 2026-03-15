"""
Tests E2E PHASE-25 — Authentification, ownership, partage.
/ E2E tests PHASE-25 — Authentication, ownership, sharing.

Lancer avec : uv run python manage.py test front.tests.e2e.test_13_auth -v2
"""

from front.tests.e2e.base import PlaywrightLiveTestCase


class Phase25AuthE2ETest(PlaywrightLiveTestCase):
    """Tests E2E pour l'authentification et le partage."""

    # ====================================================================
    # Helpers auth
    # ====================================================================

    def creer_utilisateur_demo(self, username="testuser", password="testpass123"):
        """
        Cree un utilisateur via l'ORM pour les tests.
        / Create a user via ORM for tests.
        """
        from django.contrib.auth.models import User
        return User.objects.create_user(username=username, password=password)

    def se_connecter(self, username, password):
        """
        Navigue vers /auth/login/, remplit le formulaire et se connecte.
        / Navigate to /auth/login/, fill form and log in.
        """
        self.naviguer_vers("/auth/login/")
        self.page.fill('[data-testid="input-username"]', username)
        self.page.fill('[data-testid="input-password"]', password)
        self.page.click('[data-testid="btn-submit-login"]')
        self.page.wait_for_url("**/")

    # ====================================================================
    # Tests
    # ====================================================================

    def test_page_racine_accessible_anonyme(self):
        """La page racine est accessible sans authentification."""
        self.naviguer_vers("/")
        # Verifier que la page se charge (titre Hypostasia present)
        self.page.wait_for_selector("text=Hypostasia", timeout=5000)

    def test_lecture_accessible_anonyme(self):
        """La lecture d'une page est accessible anonymement."""
        page_demo = self.creer_page_demo()
        self.naviguer_vers(f"/lire/{page_demo.pk}/")
        self.page.wait_for_selector("#zone-lecture", timeout=5000)

    def test_page_login_affiche_formulaire(self):
        """La page /auth/login/ affiche un formulaire avec username et password."""
        self.naviguer_vers("/auth/login/")
        self.page.wait_for_selector('[data-testid="input-username"]', timeout=5000)
        self.page.wait_for_selector('[data-testid="input-password"]', timeout=5000)
        self.page.wait_for_selector('[data-testid="btn-submit-login"]', timeout=5000)

    def test_login_redirect_apres_connexion(self):
        """Un login reussi redirige vers /."""
        self.creer_utilisateur_demo(username="loginuser", password="testpass123")
        self.se_connecter("loginuser", "testpass123")
        # Doit etre redirige vers /
        self.assertIn("/", self.page.url)

    def test_register_cree_user_et_connecte(self):
        """L'inscription cree un user et connecte automatiquement."""
        self.naviguer_vers("/auth/register/")
        self.page.fill('[data-testid="input-username"]', "nouveau_user")
        self.page.fill('[data-testid="input-email"]', "test@example.com")
        self.page.fill('[data-testid="input-password"]', "monmotdepasse123")
        self.page.fill('[data-testid="input-password-confirm"]', "monmotdepasse123")
        self.page.click('[data-testid="btn-submit-register"]')
        self.page.wait_for_url("**/")
        # Verifier que le menu utilisateur est visible
        self.page.wait_for_selector('[data-testid="btn-user-menu"]', timeout=5000)

    def test_ecriture_403_si_anonyme_htmx(self):
        """Une tentative de creation de dossier anonyme via HTMX retourne 403."""
        from django.test import Client
        client = Client()
        reponse = client.post(
            "/dossiers/",
            {"name": "Test anon"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 403)

    def test_login_puis_creer_dossier_avec_owner(self):
        """Apres login, la creation d'un dossier assigne l'owner."""
        from core.models import Dossier
        user = self.creer_utilisateur_demo(username="dossier_owner", password="testpass123")
        self.se_connecter("dossier_owner", "testpass123")
        # Ouvrir l'arbre et creer un dossier
        self.ouvrir_arbre()
        self.page.click('[data-testid="btn-creer-dossier-overlay"]')
        self.page.wait_for_timeout(500)
        # Verifier que le dossier a l'owner via ORM
        # (le JS du SweetAlert gere la creation, on verifie le resultat cote serveur)
        # On va utiliser le client HTTP directement
        from django.test import Client
        client = Client()
        client.login(username="dossier_owner", password="testpass123")
        client.post("/dossiers/", {"name": "Dossier Test Owner"}, HTTP_HX_REQUEST="true")
        dossier_cree = Dossier.objects.filter(name="Dossier Test Owner").first()
        self.assertIsNotNone(dossier_cree)
        self.assertEqual(dossier_cree.owner, user)

    def test_menu_utilisateur_visible_apres_login(self):
        """Le menu utilisateur est visible apres connexion."""
        self.creer_utilisateur_demo(username="menuuser", password="testpass123")
        self.se_connecter("menuuser", "testpass123")
        bouton_menu = self.page.wait_for_selector('[data-testid="btn-user-menu"]', timeout=5000)
        self.assertIsNotNone(bouton_menu)

    def test_bouton_connexion_visible_anonyme(self):
        """Le bouton Connexion est visible quand non connecte."""
        self.naviguer_vers("/")
        bouton_login = self.page.wait_for_selector('[data-testid="btn-login"]', timeout=5000)
        self.assertIsNotNone(bouton_login)

    def test_deconnexion(self):
        """La deconnexion redirige vers la page login."""
        self.creer_utilisateur_demo(username="logoutuser", password="testpass123")
        self.se_connecter("logoutuser", "testpass123")
        # Ouvrir le menu et cliquer deconnexion
        self.page.click('[data-testid="btn-user-menu"]')
        self.page.click('[data-testid="btn-logout"]')
        self.page.wait_for_url("**/auth/login/", timeout=5000)
