"""
Tests E2E — Visibilite 3 niveaux, partages, groupes.
/ E2E tests — 3-level visibility, shares, groups.

Lancer avec : uv run python manage.py test front.tests.e2e.test_14_visibilite -v2

LOCALISATION : front/tests/e2e/test_14_visibilite.py

CE MODULE LISAIT L'ARBRE LATERAL, RETIRE LE 12 AOUT 2026.

Il ouvrait le tiroir (touche T) puis lisait le texte de `#arbre` pour
savoir ce qu'un compte voit. La QUESTION reste entiere — « qu'est-ce
qu'un anonyme voit ? qu'est-ce qu'un destinataire de partage voit ? » —
mais l'ecran qui y repond est desormais `/carnets/`, ou la meme regle
d'acces est appliquee (`carnets_visibles_par`, views_corpus.py).

UN TEST A DISPARU SANS REMPLACANT : `test_accordeon_expand_collapse`.
Il verifiait que les trois sections repliables de l'arbre (« Mes
dossiers », « Partages avec moi », « Dossiers publics ») s'ouvraient et
se fermaient. Cet accordeon etait un dispositif de l'arbre, pas une
regle du produit : la liste des carnets n'a pas de sections repliables,
et n'en a pas besoin — elle montre tout d'un coup.
/ The module read the side tree to answer "what does this account
see?". The question stands; /carnets/ now answers it. One test had no
successor: the tree's accordion was a device of the tree, not a rule.
"""

from core.models import Dossier, DossierPartage, Page, VisibiliteDossier
from front.tests.e2e.base import PlaywrightLiveTestCase


class Phase25cVisibiliteE2ETest(PlaywrightLiveTestCase):
    """Ce qu'un compte voit, selon la visibilite et les partages.
    / What an account sees, by visibility and shares."""

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

    def texte_de_la_collection(self):
        """
        Le texte de la liste des carnets — l'ecran qui repond desormais
        a « qu'est-ce que ce compte voit ? ».
        / The notebook list's text: the screen that now answers "what
        does this account see?".
        """
        self.naviguer_vers("/carnets/")
        return self.page.text_content('[data-testid="corpus-carnets-liste"]')

    # ====================================================================
    # Test 1 : Anonyme voit uniquement les dossiers publics
    # / Test 1: Anonymous sees only public folders
    # ====================================================================

    def test_anonyme_voit_uniquement_publics(self):
        """La collection anonyme n'affiche que les carnets publics.
        / The anonymous collection shows public notebooks only."""
        owner = self.creer_utilisateur_demo(username="owner_e2e", password="test1234")

        # Creer un carnet prive et un carnet public
        # / Create a private and a public notebook
        Dossier.objects.create(name="Prive invisible", owner=owner)
        Dossier.objects.create(
            name="Public visible", owner=owner,
            visibilite=VisibiliteDossier.PUBLIC,
        )

        contenu = self.texte_de_la_collection()
        self.assertIn("Public visible", contenu)
        self.assertNotIn("Prive invisible", contenu)

    # ====================================================================
    # Test 2 : Login → section "Mes dossiers" visible
    # / Test 2: Login → "My folders" section visible
    # ====================================================================

    def test_login_mes_dossiers_visible(self):
        """Apres login, mes carnets prives apparaissent dans la collection.
        / After login, my private notebooks appear in the collection."""
        owner = self.creer_utilisateur_demo(username="owner_mes", password="test1234")
        Dossier.objects.create(name="Mon dossier perso", owner=owner)

        self.se_connecter("owner_mes", "test1234")
        contenu = self.texte_de_la_collection()
        self.assertIn("Mon dossier perso", contenu)

    # ====================================================================
    # Test 3 : Changer visibilite via menu contextuel
    # / Test 3: Change visibility via context menu
    # ====================================================================

    def test_changer_visibilite_menu_ctx(self):
        """
        Le proprietaire change la visibilite depuis la page du carnet.

        Le geste vivait dans le sous-menu « Visibilite » du menu
        contextuel de l'arbre. Il vit maintenant dans « Gerer ce
        carnet », sur la page du carnet.
        / The gesture moved from the tree's context sub-menu to the
        notebook page's "Manage this notebook" block.
        """
        owner = self.creer_utilisateur_demo(username="owner_ctx", password="test1234")
        dossier = Dossier.objects.create(name="Dossier ctx", owner=owner)

        self.se_connecter("owner_ctx", "test1234")
        self.naviguer_vers(f"/carnets/{dossier.pk}/")

        # « Gerer ce carnet » est un <details> REPLIE : on vient sur cette
        # page pour lire le carnet, pas pour l'administrer. Il faut donc
        # le deplier, comme le ferait la personne — un clic sur un bouton
        # enferme dans un <details> ferme n'atteint rien.
        # / The governance block is a collapsed <details>: unfold it
        # first, as a person would.
        self.page.click('[data-testid="corpus-carnet-gouvernance"] summary')
        self.page.click('[data-testid="corpus-carnet-visibilite-choix-public"]')
        self.attendre_htmx()

        # Verifier que le carnet a change de visibilite en base
        # / Verify notebook visibility changed in DB
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

        # L'arbre rangeait les partages dans une section repliee ; la
        # collection les montre avec les autres, la ligne portant sa
        # propre marque de visibilite.
        # / The tree filed shares in a collapsed section; the collection
        # shows them inline, each row carrying its visibility mark.
        contenu = self.texte_de_la_collection()
        self.assertIn("Dossier partage e2e", contenu)

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
        # Ce test lit un code HTTP, pas un ecran : `goto` le rend des la
        # reponse recue. Attendre le silence reseau par-dessus n'ajoute
        # rien a un 403.
        # / This test reads an HTTP code, not a screen.
        reponse = self.page.goto(
            f"{self.live_server_url}/lire/{page_privee.pk}/",
            wait_until="commit",
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
