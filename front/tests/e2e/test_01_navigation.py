"""
Tests E2E — Navigation : carnets, notes.
/ E2E tests — Navigation: notebooks, notes.

LOCALISATION : front/tests/e2e/test_01_navigation.py

CE MODULE PASSAIT PAR L'ARBRE LATERAL, RETIRE LE 12 AOUT 2026.

Cinq de ses tests ouvraient le tiroir (touche T) puis cliquaient dans
son menu contextuel : creer un carnet, en renommer un, en supprimer un,
deplacer une note, ouvrir une note. Le tiroir n'existe plus.

Leurs INTENTIONS restent valides — ce sont elles qu'on garde, pas la
route. Elles ont ete reparties ainsi :

    ouvrir une note  ..........  ici, depuis la page d'un carnet
                                 (`/carnets/<id>/`), qui est desormais
                                 le chemin normal
    creer un carnet  ..........  test_27_actions_du_carnet
    renommer, supprimer  ......  test_27_actions_du_carnet
    deplacer une note  ........  le bloc « Dans N carnets » de la page
                                 d'une note, couvert par test_22_corpus

Les deux tests marques `@unittest.skip` en A.8 ne le sont plus : ils
echouaient sur des clics dans l'arbre HTMX. Le chemin qui les remplace
n'a pas ce probleme — il est verifie ici.
/ Five tests went through the side drawer, now removed. Their intents
survive; only the route changed.
"""

from front.tests.e2e.base import PlaywrightLiveTestCase
from core.models import Page


class E2ENavigationTest(PlaywrightLiveTestCase):
    """Navigation entre la collection, un carnet et ses notes.
    / Navigating from the collection to a notebook and its notes."""

    def setUp(self):
        super().setUp()
        # Creer un utilisateur et se connecter pour les actions d'ecriture
        # / Create a user and log in for write actions
        self.utilisateur_test = self.creer_utilisateur_demo()
        self.se_connecter("testuser", "testpass123")
        # Creer 2 carnets et 3 notes (1 rangee, 2 orphelines)
        # / Create 2 notebooks and 3 notes (1 filed, 2 orphans)
        self.dossier_alpha = self.creer_dossier_demo("Alpha")
        self.dossier_alpha.owner = self.utilisateur_test
        self.dossier_alpha.save()
        self.dossier_beta = self.creer_dossier_demo("Beta")
        self.dossier_beta.owner = self.utilisateur_test
        self.dossier_beta.save()
        # La note est rangee PAR LE HELPER, qui synchronise la FK et la
        # table de liaison : la page d'un carnet lit la table de liaison,
        # poser la FK seule ne l'y ferait pas apparaitre.
        # / The helper syncs FK and link table; the notebook page reads
        # the link table.
        self.page_classee = self.creer_page_demo(
            "Page classee",
            "<p>Contenu page classee dans Alpha.</p>",
            owner=self.utilisateur_test,
            dossier=self.dossier_alpha,
        )
        self.page_orpheline_1 = self.creer_page_demo(
            "Orpheline 1",
            "<p>Contenu orpheline 1.</p>",
            owner=self.utilisateur_test,
        )
        self.page_orpheline_2 = self.creer_page_demo(
            "Orpheline 2",
            "<p>Contenu orpheline 2.</p>",
            owner=self.utilisateur_test,
        )

    def test_onboarding_affiche_si_aucune_page(self):
        """L'onboarding s'affiche quand il n'y a aucune page."""
        # Supprimer toutes les pages pour voir l'onboarding
        # / Delete all pages to see onboarding
        Page.objects.all().delete()
        self.naviguer_vers("/")
        contenu_onboarding = self.page.text_content('[data-testid="bibliotheque-colonne-lecture"]')
        self.assertIn("Importer", contenu_onboarding)

    def test_la_collection_liste_les_carnets(self):
        """
        `/carnets/` montre les carnets — c'est le point de depart de la
        navigation depuis le retrait du tiroir.
        / /carnets/ lists the notebooks: the navigation starting point.
        """
        self.naviguer_vers("/carnets/")
        contenu = self.page.text_content('[data-testid="corpus-carnets-liste"]')
        self.assertIn("Alpha", contenu)
        self.assertIn("Beta", contenu)

    def test_ouvrir_un_carnet_depuis_la_collection(self):
        """
        Cliquer un carnet dans la collection ouvre sa page.
        / Clicking a notebook opens its page.
        """
        self.naviguer_vers("/carnets/")
        self.page.click(
            f'[data-carnet-id="{self.dossier_alpha.pk}"] '
            f'[data-testid="corpus-carnet-lien"]'
        )
        self.attendre_htmx()
        self.page.wait_for_selector(
            '[data-testid="corpus-carnet-detail"]', timeout=5000,
        )

    def test_naviguer_vers_une_note_depuis_son_carnet(self):
        """
        Cliquer une note dans la page d'un carnet charge son contenu.

        C'est le remplacant direct de `test_naviguer_vers_page_depuis_arbre`,
        qui etait desactive (A.8) faute de pouvoir cliquer un lien dans
        l'arbre HTMX. Ce chemin-ci, lui, marche.
        / Direct replacement for the disabled tree-click test.
        """
        self.naviguer_vers(f"/carnets/{self.dossier_alpha.pk}/")
        self.page.click(
            f'[data-page-id="{self.page_classee.pk}"] '
            f'[data-testid="corpus-note-lien"]'
        )
        self.attendre_htmx()
        contenu_lecture = self.page.text_content(
            '[data-testid="bibliotheque-colonne-lecture"]'
        )
        self.assertIn("Contenu page classee", contenu_lecture)

    def test_les_liens_de_la_barre_menent_aux_deux_collections(self):
        """
        La barre porte les deux entrees de navigation qui remplacent le
        tiroir : « Bases » et « Carnets ».
        / The toolbar carries the two entries that replace the drawer.
        """
        self.naviguer_vers("/")
        for identifiant in ["lien-nav-bases", "lien-nav-carnets"]:
            self.assertTrue(
                self.page.locator(f'[data-testid="{identifiant}"]').is_visible(),
                f"« {identifiant} » doit rester visible : c'est l'un des "
                f"deux seuls points d'entree de la navigation depuis le "
                f"retrait du tiroir lateral.",
            )
