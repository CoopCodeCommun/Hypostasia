"""
Classe de base pour les tests E2E Playwright.
Utilise StaticLiveServerTestCase + Playwright sync API.
/ Base class for Playwright E2E tests.
Uses StaticLiveServerTestCase + Playwright sync API.
"""
import os

# Autoriser les appels ORM synchrones depuis le thread de test
# Django 6 detecte un contexte async dans LiveServerTestCase
# / Allow synchronous ORM calls from the test thread
# Django 6 detects an async context in LiveServerTestCase
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from playwright.sync_api import sync_playwright

from core.models import Page, Dossier, Configuration, AIModel


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class PlaywrightLiveTestCase(StaticLiveServerTestCase):
    """
    Classe de base pour tous les tests E2E Playwright.
    Lance Chromium une fois par classe, ouvre un onglet par test.
    / Base class for all Playwright E2E tests.
    Launches Chromium once per class, opens a tab per test.
    """

    @classmethod
    def setUpClass(cls):
        # Appel au parent pour demarrer le serveur live
        # / Call parent to start the live server
        super().setUpClass()
        # Lancement de Playwright et du navigateur Chromium
        # / Launch Playwright and the Chromium browser
        mode_headed = os.environ.get("PLAYWRIGHT_HEADED", "0") == "1"
        cls.playwright_instance = sync_playwright().start()
        cls.browser = cls.playwright_instance.chromium.launch(
            headless=not mode_headed,
        )

    @classmethod
    def tearDownClass(cls):
        # Fermeture du navigateur et de Playwright
        # / Close the browser and Playwright
        cls.browser.close()
        cls.playwright_instance.stop()
        super().tearDownClass()

    def setUp(self):
        # Ouverture d'un nouvel onglet pour chaque test
        # / Open a new tab for each test
        super().setUp()
        self.page = self.browser.new_page()

    def tearDown(self):
        # Fermeture de l'onglet apres chaque test
        # / Close the tab after each test
        self.page.close()
        super().tearDown()

    # ====================================================================
    # Helpers
    # ====================================================================

    def naviguer_vers(self, chemin="/"):
        """
        Navigue vers un chemin relatif sur le serveur live.
        / Navigate to a relative path on the live server.
        """
        url_complete = f"{self.live_server_url}{chemin}"
        self.page.goto(url_complete, wait_until="networkidle")

    def attendre_htmx(self, timeout_ms=5000):
        """
        Attend que HTMX ait fini ses swaps (plus de classe .htmx-request).
        / Wait for HTMX to finish its swaps (no more .htmx-request class).
        """
        self.page.wait_for_function(
            "() => document.querySelectorAll('.htmx-request').length === 0",
            timeout=timeout_ms,
        )

    def creer_page_demo(self, titre="Page de test", texte="<p>Contenu de test.</p>"):
        """
        Cree une Page via l'ORM pour les tests.
        / Create a Page via ORM for tests.
        """
        page_demo = Page.objects.create(
            title=titre,
            html_readability=texte,
            text_readability=texte,
            source_type="file",
            status="completed",
        )
        return page_demo

    def creer_dossier_demo(self, nom="Dossier test"):
        """
        Cree un Dossier via l'ORM pour les tests.
        / Create a Dossier via ORM for tests.
        """
        dossier_demo = Dossier.objects.create(name=nom)
        return dossier_demo

    def ouvrir_arbre(self):
        """
        Clique le hamburger et attend que l'arbre-overlay soit visible.
        / Click the hamburger and wait for the tree-overlay to be visible.
        """
        self.page.click('[data-testid="btn-hamburger-arbre"]')
        self.page.wait_for_selector(
            '#arbre-overlay:not(.pointer-events-none)',
            timeout=3000,
        )
        self.attendre_htmx()

    def ouvrir_drawer(self):
        """
        Presse E et attend que le drawer-overlay soit visible.
        / Press E and wait for the drawer-overlay to be visible.
        """
        self.page.keyboard.press("e")
        self.page.wait_for_selector(
            '#drawer-overlay:not(.pointer-events-none)',
            timeout=3000,
        )
        self.attendre_htmx()

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
