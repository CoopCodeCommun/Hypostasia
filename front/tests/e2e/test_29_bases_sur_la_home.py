"""
Tests E2E — L'onglet « Bases de connaissances » de la page d'accueil.
/ E2E tests — The knowledge bases tab on the home page.

LOCALISATION : front/tests/e2e/test_29_bases_sur_la_home.py

CE QUE CES TESTS EPROUVENT

Demande du mainteneur, 12 aout : « sur la home, rajoute un onglet "Bases
de connaissances", avec deux zones definies : celles qu'on a cree et
celles qui sont publique / partagee ».

POURQUOI DEUX ZONES, ET NON UNE LISTE TRIEE

Les deux moities ne se lisent pas de la meme facon. Ce que j'ai cree,
j'y reviens — c'est un espace de travail. Ce qui est publie par
d'autres, je l'explore — c'est un catalogue. Une seule liste triee par
nom melangerait les deux intentions et obligerait a lire chaque ligne
pour savoir dans laquelle on est.

C'est aussi ce que fait le retrait de l'arbre lateral : la navigation
qui vivait dans un tiroir remonte a la surface, sur l'ecran d'accueil.
/ The two halves are read differently: mine is a workspace, theirs is a
catalogue. One sorted list would blur the two intents.
"""

from core.models import BaseDeConnaissances, VisibiliteDossier
from front.tests.e2e.base import PlaywrightLiveTestCase


class E2EBasesSurLaHomeTest(PlaywrightLiveTestCase):
    """
    LOCALISATION : front/tests/e2e/test_29_bases_sur_la_home.py
    """

    def setUp(self):
        super().setUp()
        self.utilisateur_test = self.creer_utilisateur_demo()
        self.quelqu_un_d_autre = self.creer_utilisateur_demo(
            username="autrui", password="motdepasse"
        )

        self.ma_base = BaseDeConnaissances.objects.create(
            nom="Ma base à moi",
            slug="ma-base-a-moi",
            description="Celle que j'ai créée.",
            owner=self.utilisateur_test,
            visibilite=VisibiliteDossier.PRIVE,
        )
        self.base_publique_d_autrui = BaseDeConnaissances.objects.create(
            nom="La base publique d'autrui",
            slug="base-publique-autrui",
            description="Publiée par quelqu'un d'autre.",
            owner=self.quelqu_un_d_autre,
            visibilite=VisibiliteDossier.PUBLIC,
        )
        self.base_privee_d_autrui = BaseDeConnaissances.objects.create(
            nom="La base privée d'autrui",
            slug="base-privee-autrui",
            owner=self.quelqu_un_d_autre,
            visibilite=VisibiliteDossier.PRIVE,
        )

    def ouvrir_l_onglet_des_bases(self):
        """
        Charge la home et bascule sur l'onglet des bases.
        / Load the home page and switch to the bases tab.
        """
        self.page.set_viewport_size({"width": 1600, "height": 1000})
        self.naviguer_vers("/")
        # Pas d'attente avant le clic : `click()` attend deja que la cible
        # soit presente, visible et immobile.
        # / No wait before the click: click() already waits for the target
        # to be present, visible and steady.
        self.page.click('[data-testid="onglet-bases"]')
        # L'onglet se contente de retirer `hidden` de sa zone : c'est
        # l'apparition de cette zone qu'on attend, et rien d'autre.
        # / The tab merely drops `hidden` from its zone; that appearance
        # is what we wait for.
        self.page.wait_for_selector("#zone-bases-accueil:not(.hidden)")

    def lire_les_deux_zones(self):
        """
        Rend les noms de base trouves dans chaque zone.
        / Return the base names found in each zone.
        """
        return self.page.evaluate(
            """() => {
                const nomsDeLaZone = (testid) => {
                    const zone = document.querySelector(`[data-testid="${testid}"]`);
                    if (!zone) return null;
                    return [...zone.querySelectorAll('[data-base-slug]')]
                        .map((carte) => carte.dataset.baseSlug);
                };
                return {
                    miennes: nomsDeLaZone('zone-mes-bases'),
                    partagees: nomsDeLaZone('zone-bases-partagees'),
                };
            }"""
        )

    # -------------------------------------------------------------------

    def test_l_onglet_des_bases_existe_sur_la_home(self):
        """
        Le troisieme onglet, a cote de « Decouvrir » et « Manifeste ».
        / The third tab, next to "Discover" and "Manifesto".
        """
        self.se_connecter("testuser", "testpass123")
        self.page.set_viewport_size({"width": 1600, "height": 1000})
        self.naviguer_vers("/")

        onglet_est_present = self.page.evaluate(
            """() => !!document.querySelector('[data-testid="onglet-bases"]')"""
        )
        self.assertTrue(
            onglet_est_present,
            "L'onglet « Bases de connaissances » manque sur l'accueil.",
        )

    def test_mes_bases_et_celles_des_autres_sont_dans_deux_zones(self):
        """
        Le coeur de la demande : deux zones distinctes, chacune nommee.
        / Two distinct, named zones.
        """
        self.se_connecter("testuser", "testpass123")
        self.ouvrir_l_onglet_des_bases()

        zones = self.lire_les_deux_zones()

        self.assertIsNotNone(zones["miennes"], "La zone « mes bases » manque.")
        self.assertIsNotNone(
            zones["partagees"], "La zone des bases publiques manque."
        )
        self.assertIn("ma-base-a-moi", zones["miennes"])
        self.assertIn("base-publique-autrui", zones["partagees"])

    def test_ma_base_n_apparait_pas_deux_fois(self):
        """
        Une base m'appartenant ET publique doit choisir son camp : la
        montrer des deux cotes ferait douter du sens des zones.
        / A base that is both mine and public must pick a side.
        """
        self.ma_base.visibilite = VisibiliteDossier.PUBLIC
        self.ma_base.save(update_fields=["visibilite"])

        self.se_connecter("testuser", "testpass123")
        self.ouvrir_l_onglet_des_bases()

        zones = self.lire_les_deux_zones()

        self.assertIn("ma-base-a-moi", zones["miennes"])
        self.assertNotIn("ma-base-a-moi", zones["partagees"])

    def test_la_base_privee_d_autrui_n_apparait_nulle_part(self):
        """
        La regle de non-fuite du corpus vaut ici comme ailleurs.
        / The corpus non-leak rule applies here too.
        """
        self.se_connecter("testuser", "testpass123")
        self.ouvrir_l_onglet_des_bases()

        zones = self.lire_les_deux_zones()

        self.assertNotIn("base-privee-autrui", zones["miennes"])
        self.assertNotIn("base-privee-autrui", zones["partagees"])

    def test_un_visiteur_anonyme_ne_voit_que_les_publiques(self):
        """
        Sans compte, il n'y a pas de « mes bases » : la zone s'efface au
        lieu d'afficher un vide sans explication.
        / Signed out, there is no "my bases": the zone steps aside.
        """
        self.ouvrir_l_onglet_des_bases()

        zones = self.lire_les_deux_zones()

        self.assertIn("base-publique-autrui", zones["partagees"] or [])
        self.assertFalse(
            zones["miennes"],
            "Un visiteur anonyme se voit proposer une zone « mes bases ».",
        )
