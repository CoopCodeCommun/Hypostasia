"""
Tests E2E PHASE-25c — Visibilite 3 niveaux, groupes, arbre restructure.
/ E2E tests PHASE-25c — 3-level visibility, groups, restructured tree.

Lancer avec : uv run python manage.py test front.tests.e2e.test_14_visibilite -v2

LOCALISATION : front/tests/e2e/test_14_visibilite.py
"""

from core.models import Dossier, DossierPartage, Page, VisibiliteDossier
from front.tests.e2e.base import PlaywrightLiveTestCase


class Phase25cVisibiliteE2ETest(PlaywrightLiveTestCase):
    """Tests E2E pour la visibilite, l'arbre restructure et les groupes.
    / E2E tests for visibility, restructured tree and groups."""

    # ====================================================================
    # Helpers
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

    def ouvrir_arbre(self):
        """
        Ouvre le panneau arbre overlay (hamburger).
        / Opens the tree overlay panel (hamburger).
        """
        self.page.click("#btn-hamburger-arbre")
        self.page.wait_for_selector("#arbre-overlay:not(.-translate-x-full)", timeout=3000)

    # ====================================================================
    # Test 1 : Anonyme voit uniquement les dossiers publics
    # / Test 1: Anonymous sees only public folders
    # ====================================================================

    def test_anonyme_voit_uniquement_publics(self):
        """L'arbre anonyme n'affiche que les dossiers publics.
        / Anonymous tree only shows public folders."""
        owner = self.creer_utilisateur_demo(username="owner_e2e", password="test1234")

        # Creer un dossier prive et un dossier public
        # / Create a private and a public folder
        Dossier.objects.create(name="Prive invisible", owner=owner)
        Dossier.objects.create(
            name="Public visible", owner=owner,
            visibilite=VisibiliteDossier.PUBLIC,
        )

        self.naviguer_vers("/")
        self.page.wait_for_selector('[data-testid="section-publics"]', timeout=5000)

        contenu_arbre = self.page.text_content("#arbre")
        self.assertIn("Public visible", contenu_arbre)
        self.assertNotIn("Prive invisible", contenu_arbre)

    # ====================================================================
    # Test 2 : Login → section "Mes dossiers" visible
    # / Test 2: Login → "My folders" section visible
    # ====================================================================

    def test_login_mes_dossiers_visible(self):
        """Apres login, la section 'Mes dossiers' est visible.
        / After login, the 'My folders' section is visible."""
        owner = self.creer_utilisateur_demo(username="owner_mes", password="test1234")
        Dossier.objects.create(name="Mon dossier perso", owner=owner)

        self.se_connecter("owner_mes", "test1234")
        self.naviguer_vers("/")

        self.page.wait_for_selector('[data-testid="section-mes-dossiers"]', timeout=5000)
        contenu_arbre = self.page.text_content("#arbre")
        self.assertIn("Mon dossier perso", contenu_arbre)
        self.assertIn("Mes dossiers", contenu_arbre)

    # ====================================================================
    # Test 3 : Changer visibilite via menu contextuel
    # / Test 3: Change visibility via context menu
    # ====================================================================

    def test_changer_visibilite_menu_ctx(self):
        """Le menu contextuel permet de changer la visibilite d'un dossier.
        / The context menu allows changing folder visibility."""
        owner = self.creer_utilisateur_demo(username="owner_ctx", password="test1234")
        dossier = Dossier.objects.create(name="Dossier ctx", owner=owner)

        self.se_connecter("owner_ctx", "test1234")
        self.naviguer_vers("/")
        self.ouvrir_arbre()
        self.page.wait_for_selector('[data-testid="section-mes-dossiers"]', timeout=5000)

        # Clic sur le kebab menu du dossier
        # / Click on the folder's kebab menu
        bouton_kebab = self.page.locator(
            f'[data-dossier-id="{dossier.pk}"] [data-testid="btn-ctx-dossier"]'
        )
        bouton_kebab.click()

        # Clic sur "Public" dans le sous-menu visibilite
        # / Click "Public" in the visibility sub-menu
        self.page.click('[data-visibilite="public"]')
        self.attendre_htmx()

        # Verifier que le dossier a change de visibilite en base
        # / Verify folder visibility changed in DB
        dossier.refresh_from_db()
        self.assertEqual(dossier.visibilite, VisibiliteDossier.PUBLIC)

    # ====================================================================
    # Test 4 : Partager avec user → apparait dans "Partages avec moi"
    # / Test 4: Share with user → appears in "Shared with me"
    # ====================================================================

    def test_partage_apparait_chez_destinataire(self):
        """Un dossier partage apparait dans 'Partages avec moi' du destinataire.
        / A shared folder appears in the recipient's 'Shared with me'."""
        owner = self.creer_utilisateur_demo(username="owner_part", password="test1234")
        destinataire = self.creer_utilisateur_demo(username="dest_part", password="test1234")
        dossier = Dossier.objects.create(name="Dossier partage e2e", owner=owner)

        # Partage via ORM / Share via ORM
        DossierPartage.objects.create(dossier=dossier, utilisateur=destinataire)
        dossier.visibilite = VisibiliteDossier.PARTAGE
        dossier.save()

        # Se connecter en tant que destinataire
        # / Log in as recipient
        self.se_connecter("dest_part", "test1234")
        self.naviguer_vers("/")
        self.ouvrir_arbre()

        # Ouvrir la section "Partages avec moi"
        # / Open "Shared with me" section
        bouton_section = self.page.locator('[data-testid="section-partages"] .arbre-section-toggle')
        bouton_section.click()

        contenu_arbre = self.page.text_content("#arbre")
        self.assertIn("Dossier partage e2e", contenu_arbre)

    # ====================================================================
    # Test 5 : Controle d'acces — 403 sur page privee via URL directe
    # / Test 5: Access control — 403 on private page via direct URL
    # ====================================================================

    def test_403_page_privee_url_directe(self):
        """L'acces direct a une page privee retourne 403 pour un non-owner.
        / Direct access to a private page returns 403 for non-owner."""
        owner = self.creer_utilisateur_demo(username="owner_403", password="test1234")
        intrus = self.creer_utilisateur_demo(username="intrus_403", password="test1234")
        dossier = Dossier.objects.create(name="Prive 403", owner=owner)
        page_privee = Page.objects.create(
            title="Page top secret",
            html_original="<html>secret</html>",
            html_readability="<p>secret</p>",
            text_readability="secret",
            dossier=dossier, owner=owner,
        )

        self.se_connecter("intrus_403", "test1234")
        reponse = self.page.goto(
            f"{self.live_server_url}/lire/{page_privee.pk}/",
            wait_until="networkidle",
        )
        self.assertEqual(reponse.status, 403)

    # ====================================================================
    # Test 6 : Auto-classement import dans "Mes imports"
    # / Test 6: Auto-classify import in "Mes imports"
    # ====================================================================

    def test_auto_classement_mes_imports(self):
        """Le helper _obtenir_ou_creer_dossier_imports cree le dossier.
        / The _obtenir_ou_creer_dossier_imports helper creates the folder."""
        from front.views import _obtenir_ou_creer_dossier_imports
        owner = self.creer_utilisateur_demo(username="import_e2e", password="test1234")
        dossier_imports = _obtenir_ou_creer_dossier_imports(owner)
        self.assertEqual(dossier_imports.name, "Mes imports")
        self.assertEqual(dossier_imports.owner, owner)

    # ====================================================================
    # Test 7 : Accordeon expand/collapse
    # / Test 7: Accordion expand/collapse
    # ====================================================================

    def test_accordeon_expand_collapse(self):
        """Les sections accordeon s'ouvrent et se ferment au clic.
        / Accordion sections open and close on click."""
        owner = self.creer_utilisateur_demo(username="owner_acc", password="test1234")
        Dossier.objects.create(name="Mon dossier acc", owner=owner)

        self.se_connecter("owner_acc", "test1234")
        self.naviguer_vers("/")
        self.ouvrir_arbre()
        self.page.wait_for_selector('[data-testid="section-mes-dossiers"]', timeout=5000)

        # La section "Mes dossiers" est ouverte par defaut (aria-expanded=true)
        # / "My folders" section is open by default (aria-expanded=true)
        bouton_section = self.page.locator('[data-testid="section-mes-dossiers"] .arbre-section-toggle')
        etat_ouvert = bouton_section.get_attribute("aria-expanded")
        self.assertEqual(etat_ouvert, "true")

        # Clic → ferme la section / Click → closes the section
        bouton_section.click()
        etat_ferme = bouton_section.get_attribute("aria-expanded")
        self.assertEqual(etat_ferme, "false")

        # Re-clic → rouvre la section / Re-click → reopens the section
        bouton_section.click()
        etat_rouvert = bouton_section.get_attribute("aria-expanded")
        self.assertEqual(etat_rouvert, "true")

    # ====================================================================
    # Test 8 : Owner dossier supprime commentaire d'un autre
    # / Test 8: Folder owner deletes another's comment
    # ====================================================================

    def test_owner_dossier_supprime_commentaire_autre(self):
        """L'owner du dossier peut supprimer un commentaire d'un autre user.
        / The folder owner can delete another user's comment."""
        from hypostasis_extractor.models import (
            CommentaireExtraction, ExtractionJob, ExtractedEntity,
        )

        owner = self.creer_utilisateur_demo(username="owner_mod_e2e", password="test1234")
        commenteur = self.creer_utilisateur_demo(username="comm_mod_e2e", password="test1234")
        dossier = Dossier.objects.create(name="Dossier mod e2e", owner=owner)
        page_test = Page.objects.create(
            title="Page mod e2e",
            html_original="<html>test</html>",
            html_readability="<p>test</p>",
            text_readability="test",
            dossier=dossier, owner=owner,
        )
        job_test = ExtractionJob.objects.create(
            page=page_test, name="Job mod e2e", status="completed", ai_model=None,
        )
        entite_test = ExtractedEntity.objects.create(
            job=job_test, extraction_class="argument",
            extraction_text="Test", start_char=0, end_char=4,
        )
        commentaire_test = CommentaireExtraction.objects.create(
            entity=entite_test, user=commenteur, commentaire="Commentaire a supprimer",
        )

        # L'owner peut supprimer via l'API (pas via UI — test de l'API)
        # / Owner can delete via API (not via UI — API test)
        self.se_connecter("owner_mod_e2e", "test1234")

        # Appel direct via fetch() dans le navigateur
        # / Direct call via fetch() in the browser
        resultat = self.page.evaluate(
            """async (args) => {
                const [url, commentaireId, csrfToken] = args;
                const resp = await fetch(url + '/extractions/supprimer_commentaire/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-CSRFToken': csrfToken,
                    },
                    body: 'commentaire_id=' + commentaireId,
                });
                return resp.status;
            }""",
            [
                self.live_server_url,
                str(commentaire_test.pk),
                self.page.evaluate("document.querySelector('body').getAttribute('hx-headers') ? JSON.parse(document.querySelector('body').getAttribute('hx-headers'))['X-CSRFToken'] : ''"),
            ],
        )
        self.assertIn(resultat, [200, 302])
