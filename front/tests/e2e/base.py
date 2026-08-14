"""
Classe de base pour les tests E2E Playwright.
Utilise StaticLiveServerTestCase + Playwright sync API.
/ Base class for Playwright E2E tests.
Uses StaticLiveServerTestCase + Playwright sync API.

LOCALISATION : front/tests/e2e/base.py
"""
import atexit
import os

# Autoriser les appels ORM synchrones depuis le thread de test
# Django 6 detecte un contexte async dans LiveServerTestCase
# / Allow synchronous ORM calls from the test thread
# Django 6 detects an async context in LiveServerTestCase
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings, tag
from playwright.sync_api import sync_playwright

from core.models import Page, Dossier, Configuration, AIModel


# ======================================================================
# UN SEUL NAVIGATEUR POUR TOUTE LA SUITE
#
# POURQUOI. Chaque classe de test relancait Playwright ET Chromium dans
# son `setUpClass`. A 38 classes, c'est 38 demarrages de processus Node
# et 38 demarrages de Chromium — du temps depense a refaire une chose
# qui n'a aucune raison de changer entre deux classes.
#
# CE QUE CELA NE CHANGE PAS : l'isolation. Chaque test appelle
# `browser.new_page()`, et `new_page()` cree un contexte de navigation
# NEUF (cookies, stockage local, session) qu'il ferme ensuite. Deux
# tests ne partagent donc toujours aucun etat cote navigateur ; ils ne
# partagent que le processus qui les heberge.
# / One browser for the whole suite: 38 classes used to start Playwright
# and Chromium 38 times. Isolation is unchanged — new_page() still opens
# a fresh browsing context per test; only the host process is shared.
# ======================================================================

_instance_playwright_partagee = None
_navigateur_partage = None


def obtenir_le_navigateur_partage():
    """
    Rend le navigateur unique de la suite, en le demarrant au besoin.
    / Return the suite-wide browser, starting it on first use.
    """
    global _instance_playwright_partagee, _navigateur_partage
    if _navigateur_partage is None:
        mode_headed = os.environ.get("PLAYWRIGHT_HEADED", "0") == "1"
        _instance_playwright_partagee = sync_playwright().start()
        _navigateur_partage = _instance_playwright_partagee.chromium.launch(
            headless=not mode_headed,
        )
        # Ferme a la sortie du processus : plus aucune classe de test ne
        # sait quand elle est la derniere a s'executer.
        # / Closed at process exit: no single class knows it is the last.
        atexit.register(fermer_le_navigateur_partage)
    return _navigateur_partage


def fermer_le_navigateur_partage():
    """
    Ferme le navigateur partage a la fin du processus de test.
    / Close the shared browser at test process exit.
    """
    global _instance_playwright_partagee, _navigateur_partage
    # A la sortie du processus l'ordre de destruction n'est pas garanti :
    # un echec de fermeture ne doit pas maquiller le resultat des tests.
    # / At exit, teardown order is not guaranteed: a close failure must
    # never disguise the test results.
    try:
        if _navigateur_partage is not None:
            _navigateur_partage.close()
        if _instance_playwright_partagee is not None:
            _instance_playwright_partagee.stop()
    except Exception:
        pass
    _navigateur_partage = None
    _instance_playwright_partagee = None


# Le tag « e2e » est pose ICI, sur la classe de base, et se propage aux
# 37 classes des 30 fichiers e2e — un seul endroit a tenir. Il rend
# possible `--exclude-tag=e2e`, dont depend la cible `make test-rapide` :
# sans lui, `manage.py test` sans argument lance TOUT, navigateur
# compris, et il n'existe aucun moyen d'obtenir la suite rapide seule.
# / Tagged on the base class: it propagates to all 37 e2e classes and
# makes `--exclude-tag=e2e` possible, which `make test-rapide` needs.
@tag("e2e")
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
        # Reprend le navigateur de la suite au lieu d'en lancer un
        # / Reuse the suite-wide browser instead of launching one
        cls.browser = obtenir_le_navigateur_partage()

    @classmethod
    def tearDownClass(cls):
        # Le navigateur n'est PAS ferme ici : il sert aux classes
        # suivantes et se ferme a la sortie du processus (atexit).
        # / The browser is NOT closed here: later classes still need it;
        # it closes at process exit (atexit).
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

        POURQUOI PLUS `networkidle`

        `networkidle` ne rend la main qu'apres 500 ms SANS aucune requete
        reseau. Ces 500 ms sont payes a chaque navigation, meme quand la
        page est prete depuis longtemps : c'est un plancher, pas une
        mesure. Sur 192 navigations, le plancher seul pese une minute et
        demie.

        Ce qui le remplace dit la meme chose, mais en le verifiant :
        `load` attend que le document et ses sous-ressources soient
        charges, puis `attendre_htmx()` attend qu'aucune requete HTMX ne
        soit en vol. Les `hx-trigger="load"` de l'application partent
        pendant l'initialisation de HTMX, c'est-a-dire au
        `DOMContentLoaded` — donc AVANT l'evenement `load`. Quand
        `goto()` rend la main, la classe `.htmx-request` est deja posee
        si une requete est partie : l'attente qui suit la voit.
        / `networkidle` waits 500 ms of network silence on every single
        navigation — a floor, not a measurement. `load` + `attendre_htmx()`
        checks the same thing instead of sleeping through it: HTMX fires
        its load triggers at DOMContentLoaded, before the load event, so
        the `.htmx-request` class is already set when goto() returns.
        """
        url_complete = f"{self.live_server_url}{chemin}"
        self.page.goto(url_complete, wait_until="load")
        self.attendre_htmx()

    def attendre_htmx(self, timeout_ms=5000):
        """
        Attend que HTMX ait fini ses swaps (plus de classe .htmx-request).
        / Wait for HTMX to finish its swaps (no more .htmx-request class).
        """
        self.page.wait_for_function(
            "() => document.querySelectorAll('.htmx-request').length === 0",
            timeout=timeout_ms,
        )

    def attendre_la_mise_en_page(self, selecteur):
        """
        Attend qu'un element ait fini de bouger avant de le mesurer.
        / Wait for an element to stop moving before measuring it.

        POURQUOI CE HELPER EXISTE

        Cinq modules mesurent une geometrie (`getBoundingClientRect`,
        `getComputedStyle`) juste apres avoir charge une page, et se
        protegeaient d'une mesure prematuree par un `wait_for_timeout`
        de 400 a 1200 ms. Une duree fixe est le pire des deux mondes :
        trop courte, elle mesure un panneau en pleine transition et rend
        le test instable ; trop longue, elle dort pour rien.

        Ce que la mesure attend vraiment tient en deux faits :
          1. les polices sont chargees — une substitution de police
             deplace tout le texte, donc toutes les boites ;
          2. l'element ne bouge plus — deux images consecutives ou sa
             boite est identique.

        `wait_for_function` scrute par defaut a chaque `requestAnimation-
        Frame` : la comparaison porte donc bien sur deux images voisines,
        et la main est rendue des la premiere immobile.
        / A fixed delay is the worst of both worlds: too short it measures
        mid-transition, too long it sleeps for nothing. What the
        measurement waits for is fonts loaded + the box unchanged across
        two consecutive animation frames.
        """
        self.page.wait_for_function(
            """(selecteur) => {
                if (document.fonts && document.fonts.status !== 'loaded') return false;
                const element = document.querySelector(selecteur);
                if (!element) return false;
                const boite = element.getBoundingClientRect();
                const empreinte = [
                    boite.top, boite.left, boite.width, boite.height,
                ].join('|');
                const precedentes = window.__empreintesDeMesure
                    || (window.__empreintesDeMesure = {});
                const precedente = precedentes[selecteur];
                precedentes[selecteur] = empreinte;
                return precedente === empreinte;
            }""",
            arg=selecteur,
            timeout=5000,
        )

    def creer_page_demo(self, titre="Page de test", texte="<p>Contenu de test.</p>", owner=None, dossier=None):
        """
        Cree une Page via l'ORM pour les tests.
        Si owner est fourni, la page lui appartient (necessaire pour l'acces /lire/).
        / Create a Page via ORM for tests.
        If owner is provided, the page belongs to them (required for /lire/ access).
        """
        page_demo = Page.objects.create(
            title=titre,
            html_readability=texte,
            text_readability=texte,
            source_type="file",
            status="completed",
            owner=owner,
            dossier=dossier,
        )
        # Appartenance N-N alignee sur la FK (phase D corpus) : l'arbre,
        # l'alignement et les permissions lisent la table de liaison.
        # / N-N membership aligned with the FK (corpus phase D).
        if dossier is not None:
            from core.services.corpus import ranger_une_note_dans_un_carnet
            ranger_une_note_dans_un_carnet(page_demo, dossier, owner)
        return page_demo

    def creer_dossier_demo(self, nom="Dossier test", owner=None):
        """
        Cree un Dossier via l'ORM pour les tests.
        Si owner est fourni, le dossier lui appartient.
        / Create a Dossier via ORM for tests.
        If owner is provided, the folder belongs to them.
        """
        dossier_demo = Dossier.objects.create(name=nom, owner=owner)
        return dossier_demo

    # LE HELPER `ouvrir_arbre()` A ETE SUPPRIME LE 12 AOUT 2026.
    #
    # Il cliquait le hamburger, puis — le temps d'une journee — pressait
    # la touche T. Le tiroir lateral, le hamburger et la touche T ont
    # tous les trois disparu ; un helper qui ouvre un panneau inexistant
    # ne peut que faire attendre 3 secondes avant d'echouer.
    #
    # Les modules qui l'appelaient ont ete rediriges vers le chemin
    # reel : `/carnets/` pour la collection, `/carnets/<id>/` pour un
    # carnet et ses gestes (test_27_actions_du_carnet).
    # / The ouvrir_arbre() helper is gone with the drawer, the hamburger
    # and the T key. Callers now go through /carnets/.

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

    def assertTrueWithRetry(self, condition_callable, message="", timeout_ms=5000, interval_ms=200):
        """
        Reassaye une condition jusqu'a ce qu'elle soit vraie ou que le timeout expire.
        Utile pour attendre qu'un element HTMX apparaisse apres un swap.
        / Retry a condition until true or timeout. Useful for HTMX swaps.
        """
        import time
        debut = time.time()
        limite = timeout_ms / 1000.0
        intervalle = interval_ms / 1000.0
        while time.time() - debut < limite:
            try:
                if condition_callable():
                    return
            except Exception:
                pass
            time.sleep(intervalle)
        self.assertTrue(False, message or "Condition non remplie apres timeout")

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
