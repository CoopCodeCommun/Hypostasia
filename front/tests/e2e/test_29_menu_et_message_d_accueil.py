"""
Tests E2E — le menu a quatre entrees, et le message d'accueil.
/ E2E tests — the four-entry menu, and the welcome message.

LOCALISATION : front/tests/e2e/test_29_menu_et_message_d_accueil.py

CE QUE CE MODULE FAIT, ET QUE LES TESTS SERVEUR NE PEUVENT PAS FAIRE

`front/tests/test_le_menu_et_le_message_d_accueil.py` verifie le
BALISAGE : les quatre liens sont la, dans le bon ordre, la modale est
rendue, l'UUID part en session. Rien de tout cela ne dit si l'utilisateur
VOIT les quatre entrees.

Trois choses ne se prouvent qu'au navigateur :

1. LES QUATRE ENTREES TIENNENT SUR UN TELEPHONE. Leur conteneur porte
   `overflow-hidden` : un lien qui deborde n'est pas replie, il est
   ROGNE — et aucune erreur ne le dit. C'est le defaut exact qu'un
   commentaire de l'ancien ecran d'accueil signalait deja : « son
   conteneur gauche est en overflow-hidden, et deux liens de plus y
   etaient rognes sans qu'aucune erreur ne le dise ». On en ajoute
   justement deux. On MESURE donc, en 360px comme en 1600px, que chaque
   entree est entierement dans la boite de la barre.

2. LA MODALE SE FERME. Son script vit dans le gabarit ; un test serveur
   ne l'execute pas.

3. LA CASE « J'AI COMPRIS » SURVIT A UN RECHARGEMENT, ce qui est tout
   son objet — et c'est le `hx-post` de la case, donc HTMX, donc un
   navigateur.
/ The server tests check the markup; only a browser can prove the four
entries are actually VISIBLE on a phone, that the modal closes, and that
the checkbox survives a reload.
"""

from core.models import BaseDeConnaissances, Dossier, VisibiliteDossier

from .base import PlaywrightLiveTestCase

# Les quatre entrees, dans l'ordre demande par le mainteneur.
# / The four entries, in the maintainer's order.
ENTREES_DU_MENU = [
    ("lien-nav-carnets", "Carnets"),
    ("lien-nav-bases", "Bases"),
    ("lien-nav-aide", "Aide"),
    ("lien-nav-manifeste", "Manifeste"),
]

# Les deux largeurs qui comptent : un telephone etroit, et un ecran large.
# 360px est la largeur d'un Android d'entree de gamme — celle sous
# laquelle la barre casse en premier.
# / A low-end Android and a desktop: 360px is where the bar breaks first.
TELEPHONE = {"width": 360, "height": 740}
ORDINATEUR = {"width": 1600, "height": 1000}


class LeMenuTientSurLesDeuxEcransTest(PlaywrightLiveTestCase):
    """
    LOCALISATION : front/tests/e2e/test_29_menu_et_message_d_accueil.py
    """

    def setUp(self):
        super().setUp()
        self.utilisateur_test = self.creer_utilisateur_demo()

    def _mesurer_les_entrees(self):
        """
        Pour chaque entree : sa boite, et QUI repond a son point central.
        / For each entry: its box, and WHAT answers at its centre point.

        `elementFromPoint` est la seule mesure qui prouve qu'une entree
        est reellement atteignable. Comparer sa boite a celle de la barre
        ne suffit pas : une boite peut etre correcte et l'element
        neanmoins rogne par l'`overflow-hidden` d'un ancetre — c'est
        exactement ce qui arrivait avant le 21 aout, sans qu'aucune
        assertion de boite ne le voie.
        / Only elementFromPoint proves reachability: a box can be right
        while an ancestor's overflow-hidden clips the element.
        """
        return self.page.evaluate(
            """() => {
                const mesures = {};
                for (const lien of document.querySelectorAll('[data-testid^="lien-nav-"]')) {
                    const boite = lien.getBoundingClientRect();
                    const x = boite.left + boite.width / 2;
                    const y = boite.top + boite.height / 2;
                    const auPoint = document.elementFromPoint(x, y);
                    mesures[lien.dataset.testid] = {
                        largeur: boite.width,
                        droite: boite.right,
                        texte: lien.textContent.trim(),
                        // Le texte est-il complet, ou coupe par une
                        // ellipse ? / Is the label complete or ellipsed?
                        tronque: lien.scrollWidth > lien.clientWidth + 1,
                        // L'entree repond-elle a son propre centre ?
                        atteignable: auPoint !== null && (
                            auPoint === lien || lien.contains(auPoint)
                        ),
                        dansLaFenetre: (
                            boite.left >= 0 && boite.right <= window.innerWidth
                            && boite.top >= 0 && boite.bottom <= window.innerHeight
                        ),
                    };
                }
                return {
                    entrees: mesures,
                    debordementDeLaPage: document.documentElement.scrollWidth
                        - document.documentElement.clientWidth,
                };
            }"""
        )

    def _verifier_les_quatre_entrees(self, largeur_d_ecran):
        mesures = self._mesurer_les_entrees()

        for identifiant, libelle in ENTREES_DU_MENU:
            entree = mesures["entrees"].get(identifiant)
            self.assertIsNotNone(
                entree,
                f"En {largeur_d_ecran}px, l'entree « {libelle} » est absente "
                f"du document.",
            )
            self.assertEqual(entree["texte"], libelle)
            self.assertGreater(
                entree["largeur"], 0,
                f"En {largeur_d_ecran}px, « {libelle} » a une boite nulle : "
                f"elle est masquee.",
            )
            self.assertFalse(
                entree["tronque"],
                f"En {largeur_d_ecran}px, « {libelle} » est tronquee par une "
                f"ellipse : le mot n'est plus lisible en entier.",
            )
            self.assertTrue(
                entree["dansLaFenetre"],
                f"En {largeur_d_ecran}px, « {libelle} » sort de la fenetre "
                f"(bord droit a {entree['droite']:.0f}px).",
            )
            # LE POINT DU TEST. Une entree peut avoir une boite parfaite
            # et rester invisible, rognee par l'`overflow-hidden` d'un
            # ancetre — sans la moindre erreur. Seul « qui repond a ce
            # point de l'ecran » le demasque.
            # / A perfect box can still be clipped by an ancestor.
            self.assertTrue(
                entree["atteignable"],
                f"En {largeur_d_ecran}px, rien ne repond au centre de "
                f"« {libelle} » : l'entree est ROGNEE ou recouverte.",
            )

        self.assertLessEqual(
            mesures["debordementDeLaPage"], 0,
            f"En {largeur_d_ecran}px, la page deborde de "
            f"{mesures['debordementDeLaPage']}px horizontalement.",
        )

    def test_les_quatre_entrees_sont_entieres_sur_ordinateur(self):
        self.page.set_viewport_size(ORDINATEUR)
        self.naviguer_vers("/carnets/")

        self._verifier_les_quatre_entrees(ORDINATEUR["width"])

    def test_les_quatre_entrees_sont_entieres_sur_telephone(self):
        """
        Le cas qui casse. Le mot « Hypostasia » s'efface sous 768px, ce
        qui libere la place ; il faut verifier que ca suffit.
        / The breaking case: the wordmark hides under 768px.
        """
        self.page.set_viewport_size(TELEPHONE)
        self.naviguer_vers("/carnets/")

        self._verifier_les_quatre_entrees(TELEPHONE["width"])

    def test_les_quatre_entrees_sont_entieres_sur_telephone_connecte(self):
        """
        Connecte, la barre porte EN PLUS le bouton des taches et l'avatar
        du menu utilisateur : c'est la configuration la plus chargee, et
        celle ou le rognage arrive.
        / Signed in, the bar also carries the tasks button and the avatar.
        """
        self.se_connecter("testuser", "testpass123")
        self.page.set_viewport_size(TELEPHONE)
        self.naviguer_vers("/carnets/")

        self._verifier_les_quatre_entrees(TELEPHONE["width"])

    def test_chaque_entree_mene_a_son_ecran(self):
        """
        Un lien qui ne mene nulle part est pire qu'un lien absent.
        / A link that leads nowhere is worse than no link.
        """
        self.page.set_viewport_size(ORDINATEUR)
        self.naviguer_vers("/carnets/")

        ecrans_attendus = {
            "lien-nav-carnets": "corpus-carnets-liste",
            "lien-nav-bases": "corpus-bases-liste",
            "lien-nav-aide": "onboarding-guide",
            "lien-nav-manifeste": "manifeste-article",
        }

        for identifiant, marqueur_de_l_ecran in ecrans_attendus.items():
            self.page.click(f'[data-testid="{identifiant}"]')
            self.attendre_htmx()
            self.page.wait_for_selector(
                f'[data-testid="{marqueur_de_l_ecran}"]', timeout=5000,
            )

    def test_l_adresse_suit_la_navigation(self):
        """
        `hx-push-url` : sans lui, on ne peut ni recharger, ni mettre en
        signet, ni revenir en arriere — c'est ce qui separe un ecran d'un
        onglet. / Without hx-push-url there is no reload, no bookmark and
        no back button: that is what separated a screen from a tab.
        """
        self.page.set_viewport_size(ORDINATEUR)
        self.naviguer_vers("/carnets/")

        self.page.click('[data-testid="lien-nav-manifeste"]')
        self.attendre_htmx()

        self.assertTrue(
            self.page.url.endswith("/manifeste/"),
            f"L'adresse est restee « {self.page.url} » apres un clic sur "
            f"« Manifeste ».",
        )

    def test_la_racine_aboutit_aux_carnets(self):
        """
        Ce que voit quelqu'un qui tape le domaine seul.
        / What someone typing the bare domain gets.
        """
        Dossier.objects.create(
            name="Carnet visible", owner=self.utilisateur_test,
            visibilite=VisibiliteDossier.PUBLIC,
        )
        self.page.set_viewport_size(ORDINATEUR)
        self.naviguer_vers("/")

        self.assertTrue(
            self.page.url.endswith("/carnets/"),
            f"La racine n'a pas mene aux carnets : « {self.page.url} ».",
        )
        self.page.wait_for_selector('[data-testid="corpus-carnets-liste"]')


class LeMessageDAccueilTest(PlaywrightLiveTestCase):
    """
    LOCALISATION : front/tests/e2e/test_29_menu_et_message_d_accueil.py

    LA SEULE CLASSE QUI VOIT LA MODALE. Toutes les autres partent d'une
    session ou « j'ai compris » est deja coche (voir
    `PlaywrightLiveTestCase.le_message_d_accueil_est_deja_compris`) :
    sinon un voile en `position: fixed` intercepterait leurs clics.
    / The only class that sees the modal; everywhere else the session
    already carries the acknowledgement.
    """

    le_message_d_accueil_est_deja_compris = False

    def setUp(self):
        super().setUp()
        self.creer_utilisateur_demo()
        self.page.set_viewport_size(ORDINATEUR)

    def test_il_parait_au_premier_chargement(self):
        self.naviguer_vers("/carnets/")

        self.page.wait_for_selector('[data-testid="message-d-accueil"]')

    def test_le_bouton_c_est_parti_le_ferme(self):
        self.naviguer_vers("/carnets/")
        self.page.wait_for_selector('[data-testid="message-d-accueil"]')

        self.page.click('[data-testid="btn-c-est-parti"]')

        self.page.wait_for_selector(
            '[data-testid="message-d-accueil"]', state="detached", timeout=3000,
        )

    def test_la_croix_le_ferme(self):
        self.naviguer_vers("/carnets/")
        self.page.wait_for_selector('[data-testid="message-d-accueil"]')

        self.page.click('[data-testid="btn-fermer-message-accueil"]')

        self.page.wait_for_selector(
            '[data-testid="message-d-accueil"]', state="detached", timeout=3000,
        )

    def test_la_touche_echap_le_ferme(self):
        self.naviguer_vers("/carnets/")
        self.page.wait_for_selector('[data-testid="message-d-accueil"]')

        self.page.keyboard.press("Escape")

        self.page.wait_for_selector(
            '[data-testid="message-d-accueil"]', state="detached", timeout=3000,
        )

    def test_ferme_sans_cocher_il_revient(self):
        """
        C'est le comportement demande : fermer sans cocher est le geste
        de qui veut juste passer, et le message respecte ce choix EN
        REVENANT. / Closing without ticking is a "let me through", and
        the message honours it by coming back.
        """
        self.naviguer_vers("/carnets/")
        self.page.click('[data-testid="btn-c-est-parti"]')

        self.naviguer_vers("/carnets/")

        self.page.wait_for_selector('[data-testid="message-d-accueil"]')

    def test_coche_il_ne_revient_plus(self):
        """
        Le tour complet : la case poste en HTMX, la session retient
        l'UUID, et le rechargement ne montre plus rien.
        / The full round trip: HTMX post, session, reload.
        """
        self.naviguer_vers("/carnets/")
        self.page.check('[data-testid="case-j-ai-compris"]')
        self.attendre_htmx()
        self.page.click('[data-testid="btn-c-est-parti"]')

        self.naviguer_vers("/carnets/")

        self.assertEqual(
            self.page.locator('[data-testid="message-d-accueil"]').count(),
            0,
            "Le message d'accueil reparait alors que « j'ai compris » a "
            "ete coche.",
        )

    def test_il_nomme_les_quatre_entrees(self):
        """
        Sa seule raison d'etre. / Its only purpose.
        """
        self.naviguer_vers("/carnets/")
        self.page.wait_for_selector('[data-testid="entrees-du-menu"]')

        noms = self.page.evaluate(
            """() => [...document.querySelectorAll(
                '[data-testid="entrees-du-menu"] .nom-entree'
            )].map((n) => n.textContent.trim())"""
        )

        self.assertEqual(noms, [libelle for _, libelle in ENTREES_DU_MENU])

    def test_il_ne_deborde_pas_sur_un_telephone(self):
        """
        Une modale plus haute que l'ecran, sans defilement, cache son
        propre bouton de fermeture. / A modal taller than the screen with
        no scroll hides its own close button.
        """
        self.page.set_viewport_size(TELEPHONE)
        self.naviguer_vers("/carnets/")
        self.page.wait_for_selector('[data-testid="message-d-accueil"]')

        debordement = self.page.evaluate(
            """() => {
                const carte = document.querySelector('.carte-message-accueil');
                const boite = carte.getBoundingClientRect();
                return {
                    aDroite: boite.right - window.innerWidth,
                    plusHauteQueLEcran: boite.height > window.innerHeight,
                    boutonVisible: document.querySelector(
                        '[data-testid="btn-c-est-parti"]'
                    ).getBoundingClientRect().bottom <= window.innerHeight,
                };
            }"""
        )

        self.assertLessEqual(round(debordement["aDroite"]), 0)
        self.assertFalse(debordement["plusHauteQueLEcran"])
        self.assertTrue(
            debordement["boutonVisible"],
            "Le bouton « C'est parti » est sous la ligne de flottaison sur "
            "un telephone : la modale cache son propre moyen de sortie.",
        )


class LesDeuxZonesDeLaListeDesBasesTest(PlaywrightLiveTestCase):
    """
    L'unification vue de l'ecran : `/bases/` a repris les deux zones que
    l'onglet de l'accueil portait, sans perdre ce qu'elle avait deja.
    / The merge, seen from the screen.

    LOCALISATION : front/tests/e2e/test_29_menu_et_message_d_accueil.py
    """

    def setUp(self):
        super().setUp()
        self.utilisateur_test = self.creer_utilisateur_demo()
        self.quelqu_un_d_autre = self.creer_utilisateur_demo(
            username="autrui", password="motdepasse"
        )
        self.page.set_viewport_size(ORDINATEUR)

        BaseDeConnaissances.objects.create(
            nom="Ma base à moi", slug="ma-base-a-moi",
            description="Celle que j'ai créée.",
            owner=self.utilisateur_test, visibilite=VisibiliteDossier.PRIVE,
        )
        BaseDeConnaissances.objects.create(
            nom="La base publique d'autrui", slug="base-publique-autrui",
            description="Publiée par quelqu'un d'autre.",
            owner=self.quelqu_un_d_autre, visibilite=VisibiliteDossier.PUBLIC,
        )
        BaseDeConnaissances.objects.create(
            nom="La base privée d'autrui", slug="base-privee-autrui",
            owner=self.quelqu_un_d_autre, visibilite=VisibiliteDossier.PRIVE,
        )

    def lire_les_deux_zones(self):
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

    def test_mes_bases_et_celles_des_autres_sont_dans_deux_zones(self):
        self.se_connecter("testuser", "testpass123")
        self.naviguer_vers("/bases/")

        zones = self.lire_les_deux_zones()

        self.assertIsNotNone(zones["miennes"], "La zone « mes bases » manque.")
        self.assertIsNotNone(
            zones["partagees"], "La zone des bases publiques manque."
        )
        self.assertIn("ma-base-a-moi", zones["miennes"])
        self.assertIn("base-publique-autrui", zones["partagees"])

    def test_la_base_privee_d_autrui_n_apparait_nulle_part(self):
        self.se_connecter("testuser", "testpass123")
        self.naviguer_vers("/bases/")

        zones = self.lire_les_deux_zones()

        self.assertNotIn("base-privee-autrui", zones["miennes"])
        self.assertNotIn("base-privee-autrui", zones["partagees"])

    def test_un_visiteur_anonyme_ne_voit_que_les_publiques(self):
        self.naviguer_vers("/bases/")

        zones = self.lire_les_deux_zones()

        self.assertIn("base-publique-autrui", zones["partagees"] or [])
        self.assertFalse(
            zones["miennes"],
            "Un visiteur anonyme se voit proposer une zone « mes bases ».",
        )
