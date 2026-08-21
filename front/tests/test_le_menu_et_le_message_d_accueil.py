"""
Le menu a quatre entrees, et le message d'accueil qui les explique.
/ The four-entry menu, and the welcome message that explains it.

LOCALISATION : front/tests/test_le_menu_et_le_message_d_accueil.py

CE QUE CES TESTS EPROUVENT

Trois choses, decidees par le mainteneur le 21 aout 2026.

1. LA RACINE N'EST PLUS UN ECRAN. Elle menait a un onboarding portant
   trois onglets, dont l'un — « Bases de connaissances » — montrait une
   SECONDE vue des bases, a cote de `/bases/`. Deux ecrans pour la meme
   chose derivent : celui de l'accueil ignorait la description, les
   compteurs et la creation. La racine redirige donc vers `/carnets/`,
   et il ne reste qu'une seule vue des bases.

2. LES ONGLETS DEVIENNENT DES ENTREES DE MENU. Un onglet ne s'atteint
   qu'en passant par l'ecran qui le porte, et n'a pas d'adresse. Les
   quatre entrees en ont une, et sont visibles sur telephone comme sur
   ordinateur.

3. LE MESSAGE D'ACCUEIL EXPLIQUE LES QUATRE ENTREES, et reparait tant
   que personne n'a coche « j'ai compris ». Ce que la session retient
   n'est pas un booleen mais un UUID : changer l'UUID republie le
   message a tout le monde, y compris a ceux qui avaient coche. C'est
   le mecanisme prevu pour annoncer une mise a jour.
/ The root redirects to /carnets/, the tabs became addressable menu
entries, and the welcome modal is gated by a UUID, not a boolean.
"""

import pathlib

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from core.models import BaseDeConnaissances, Dossier, VisibiliteDossier
from front.views_accueil import (
    CLE_DE_SESSION_DU_MESSAGE_VU,
    UUID_DU_MESSAGE_D_ACCUEIL,
)

User = get_user_model()

GABARITS = (
    pathlib.Path(__file__).resolve().parent.parent / "templates" / "front"
)

# Les deux fragments que HTMX applique hors de `#zone-lecture` : le fil
# d'Ariane et la barre du lecteur audio. Un ecran qui les omet n'affiche
# pas du vide — il laisse en place ceux de l'ecran PRECEDENT.
# / The two OOB fragments a screen must redeposit: omitting them strands
# the previous screen's breadcrumb and audio player.
MARQUEUR_OOB_DU_FIL = 'hx-swap-oob="innerHTML:#fil-ariane-conteneur"'
MARQUEUR_OOB_DU_LECTEUR = 'hx-swap-oob="innerHTML:#lecteur-audio-conteneur"'


class LaRacineMeneAuxCarnetsTest(TestCase):
    """
    LOCALISATION : front/tests/test_le_menu_et_le_message_d_accueil.py
    """

    def test_un_acces_direct_a_la_racine_redirige_vers_les_carnets(self):
        """
        La barre d'adresse doit VRAIMENT afficher `/carnets/`. Rendre la
        liste des carnets sous l'URL `/` laisserait deux adresses pour un
        seul ecran. / The address bar must really read /carnets/.
        """
        reponse = self.client.get("/")

        self.assertEqual(reponse.status_code, 302)
        self.assertEqual(reponse["Location"], "/carnets/")

    def test_la_redirection_aboutit_a_la_liste_des_carnets(self):
        """
        Le bout du chemin, et non seulement son premier pas.
        / The end of the path, not just its first step.
        """
        reponse = self.client.get("/", follow=True)

        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode()
        self.assertIn('data-testid="corpus-carnets-liste"', contenu)

    def test_la_racine_redirige_aussi_une_requete_htmx(self):
        """
        Une seule regle pour les deux chemins : le XHR de HTMX suit la
        redirection tout seul et recoit le partial des carnets.
        / One rule for both paths: HTMX's XHR follows the redirect.
        """
        reponse = self.client.get("/", HTTP_HX_REQUEST="true", follow=True)

        contenu = reponse.content.decode()
        self.assertIn('data-testid="corpus-carnets-liste"', contenu)
        # Le fil d'Ariane de l'ecran precedent doit etre efface.
        # / The previous screen's breadcrumb must be cleared.
        self.assertIn(MARQUEUR_OOB_DU_FIL, contenu)


class LeMenuPorteQuatreEntreesTest(TestCase):
    """
    LOCALISATION : front/tests/test_le_menu_et_le_message_d_accueil.py
    """

    ENTREES_DANS_L_ORDRE = [
        "lien-nav-carnets",
        "lien-nav-bases",
        "lien-nav-aide",
        "lien-nav-manifeste",
    ]

    def test_les_quatre_entrees_sont_dans_la_barre(self):
        contenu = self.client.get("/carnets/").content.decode()

        for identifiant in self.ENTREES_DANS_L_ORDRE:
            self.assertIn(
                f'data-testid="{identifiant}"',
                contenu,
                f"L'entree de menu « {identifiant} » manque dans la barre.",
            )

    def test_les_entrees_sont_dans_l_ordre_demande(self):
        """
        Carnets, Bases, Aide, Manifeste. L'ordre est une demande du
        mainteneur, pas un hasard de redaction.
        / The order is a maintainer decision, not an accident.
        """
        contenu = self.client.get("/carnets/").content.decode()

        positions = [
            contenu.find(f'data-testid="{identifiant}"')
            for identifiant in self.ENTREES_DANS_L_ORDRE
        ]

        self.assertEqual(
            positions,
            sorted(positions),
            "Les entrees du menu ne sont pas dans l'ordre « Carnets, "
            "Bases, Aide, Manifeste ».",
        )

    def test_aucune_entree_n_est_reservee_au_desktop(self):
        """
        `btn-desktop-only` efface l'element sous 768px. Une entree de
        navigation qui le porte n'existe pas sur telephone — et il n'y a
        plus de tiroir pour la rattraper.
        / btn-desktop-only hides the element on phones, and no drawer is
        left to make up for it.
        """
        contenu = self.client.get("/carnets/").content.decode()

        for identifiant in self.ENTREES_DANS_L_ORDRE:
            debut = contenu.find(f'data-testid="{identifiant}"')
            # La balise ouvrante de ce lien, remontee depuis son testid.
            # / The opening tag of that link, walked back from its testid.
            balise = contenu[contenu.rfind("<a", 0, debut):debut]
            self.assertNotIn(
                "btn-desktop-only",
                balise,
                f"« {identifiant} » est masque sur mobile alors que c'est "
                f"l'un des quatre points d'entree de la navigation.",
            )


class LesEcransAideEtManifesteTest(TestCase):
    """
    LOCALISATION : front/tests/test_le_menu_et_le_message_d_accueil.py
    """

    def test_l_aide_repond_en_page_complete(self):
        contenu = self.client.get("/aide/").content.decode()

        self.assertIn("<html", contenu)
        self.assertIn('data-testid="onboarding-guide"', contenu)
        self.assertIn('data-testid="lien-nav-aide"', contenu)

    def test_le_manifeste_repond_en_page_complete(self):
        contenu = self.client.get("/manifeste/").content.decode()

        self.assertIn("<html", contenu)
        self.assertIn('data-testid="manifeste-article"', contenu)
        self.assertIn('data-testid="lien-nav-manifeste"', contenu)

    def test_en_htmx_l_aide_ne_renvoie_que_son_partial(self):
        contenu = self.client.get(
            "/aide/", HTTP_HX_REQUEST="true",
        ).content.decode()

        self.assertNotIn("<html", contenu)
        self.assertIn('data-testid="onboarding-guide"', contenu)

    def test_en_htmx_le_manifeste_ne_renvoie_que_son_partial(self):
        contenu = self.client.get(
            "/manifeste/", HTTP_HX_REQUEST="true",
        ).content.decode()

        self.assertNotIn("<html", contenu)
        self.assertIn('data-testid="manifeste-article"', contenu)

    def test_les_deux_ecrans_effacent_la_barre_du_lecteur_audio(self):
        """
        La barre du lecteur vit hors de `#zone-lecture`, comme le fil :
        un swap HTMX ne la touche jamais. Sans l'OOB, la barre d'une note
        audio SURVIT a la navigation vers l'aide ou le manifeste, et
        propose de lire un enregistrement que l'ecran n'affiche plus.
        / The player lives outside #zone-lecture: without the OOB it
        outlives the note it plays.
        """
        for adresse in ("/aide/", "/manifeste/"):
            contenu = self.client.get(
                adresse, HTTP_HX_REQUEST="true",
            ).content.decode()
            self.assertIn(
                MARQUEUR_OOB_DU_LECTEUR,
                contenu,
                f"« {adresse} » ne depose pas de quoi effacer la barre du "
                f"lecteur audio.",
            )

    def test_les_deux_ecrans_effacent_le_fil_d_ariane(self):
        """
        Ni l'aide ni le manifeste ne sont dans un carnet : sans cet OOB,
        le chemin de la note d'ou l'on vient reste affiche au-dessus.
        / Neither screen sits in a notebook; without the OOB the previous
        trail stays on screen.
        """
        for adresse in ("/aide/", "/manifeste/"):
            contenu = self.client.get(
                adresse, HTTP_HX_REQUEST="true",
            ).content.decode()
            self.assertIn(
                MARQUEUR_OOB_DU_FIL,
                contenu,
                f"« {adresse} » ne depose pas de quoi effacer le fil.",
            )


class LeMessageDAccueilTest(TestCase):
    """
    LOCALISATION : front/tests/test_le_menu_et_le_message_d_accueil.py
    """

    def test_il_s_affiche_sur_un_chargement_direct(self):
        contenu = self.client.get("/carnets/").content.decode()

        self.assertIn('data-testid="message-d-accueil"', contenu)

    def test_il_ne_s_infiltre_pas_dans_un_partial_htmx(self):
        """
        `base.html` seul le porte. Une reponse partielle qui l'emporterait
        le rejouerait a chaque navigation, sur un ecran qui en a deja un.
        / Only base.html carries it: a partial would replay it on every
        navigation.
        """
        contenu = self.client.get(
            "/carnets/", HTTP_HX_REQUEST="true",
        ).content.decode()

        self.assertNotIn('data-testid="message-d-accueil"', contenu)

    def test_cocher_j_ai_compris_ecrit_l_uuid_en_session(self):
        reponse = self.client.post("/aide/j-ai-compris/", {"j_ai_compris": "oui"})

        self.assertEqual(reponse.status_code, 204)
        self.assertEqual(
            self.client.session.get(CLE_DE_SESSION_DU_MESSAGE_VU),
            UUID_DU_MESSAGE_D_ACCUEIL,
        )

    def test_une_fois_coche_le_message_ne_reparait_plus(self):
        self.client.post("/aide/j-ai-compris/", {"j_ai_compris": "oui"})

        contenu = self.client.get("/carnets/").content.decode()

        self.assertNotIn('data-testid="message-d-accueil"', contenu)

    def test_decocher_le_fait_revenir(self):
        """
        La case va dans les deux sens : sans quoi un clic malheureux
        supprimerait le message pour toujours, sans aucun moyen de le
        rappeler. / The checkbox works both ways.
        """
        self.client.post("/aide/j-ai-compris/", {"j_ai_compris": "oui"})
        self.client.post("/aide/j-ai-compris/", {})

        contenu = self.client.get("/carnets/").content.decode()

        self.assertIn('data-testid="message-d-accueil"', contenu)

    def test_un_uuid_perime_en_session_fait_revenir_le_message(self):
        """
        LE POINT DE TOUT LE MECANISME. La session ne retient pas « vu »
        mais « vu QUOI ». Changer `UUID_DU_MESSAGE_D_ACCUEIL` republie le
        message a tous, y compris a ceux qui avaient coche — c'est ainsi
        qu'une mise a jour s'annoncera.
        / The session remembers WHAT was seen, not THAT something was:
        changing the UUID republishes the message to everyone.
        """
        session = self.client.session
        session[CLE_DE_SESSION_DU_MESSAGE_VU] = "un-uuid-d-un-message-plus-ancien"
        session.save()

        contenu = self.client.get("/carnets/").content.decode()

        self.assertIn('data-testid="message-d-accueil"', contenu)

    def test_il_nomme_les_quatre_entrees_du_menu(self):
        """
        Sa seule raison d'etre : dire ou menent les quatre boutons.
        / Its only purpose: say where the four buttons lead.
        """
        contenu = self.client.get("/carnets/").content.decode()
        debut = contenu.find('data-testid="message-d-accueil"')
        modale = contenu[debut:debut + 4000]

        for entree in ("Carnets", "Bases", "Aide", "Manifeste"):
            self.assertIn(
                entree,
                modale,
                f"Le message d'accueil n'explique pas l'entree « {entree} ».",
            )


class L_uniqueVueDesBasesTest(TestCase):
    """
    L'unification demandee : l'accueil ne montre plus les bases, et
    `/bases/` a repris les deux zones que l'onglet portait.
    / The requested unification: the home no longer lists bases, and
    /bases/ took over the two zones the tab used to hold.

    LOCALISATION : front/tests/test_le_menu_et_le_message_d_accueil.py
    """

    def setUp(self):
        self.moi = User.objects.create_user(username="moi", password="mdp")
        self.autrui = User.objects.create_user(username="autrui", password="mdp")
        self.client.force_login(self.moi)

        self.ma_base = BaseDeConnaissances.objects.create(
            nom="Ma base", slug="ma-base", owner=self.moi,
            visibilite=VisibiliteDossier.PRIVE,
        )
        self.base_d_autrui = BaseDeConnaissances.objects.create(
            nom="Base d'autrui", slug="base-autrui", owner=self.autrui,
            visibilite=VisibiliteDossier.PUBLIC,
        )
        self.base_privee_d_autrui = BaseDeConnaissances.objects.create(
            nom="Base privee d'autrui", slug="base-privee-autrui",
            owner=self.autrui, visibilite=VisibiliteDossier.PRIVE,
        )

    def _zones_de_la_liste(self):
        """
        Rend les slugs trouves dans chacune des deux zones de `/bases/`.
        / Return the slugs found in each of the two zones of /bases/.
        """
        contenu = self.client.get("/bases/").content.decode()

        decoupe = {}
        for nom_de_zone in ("zone-mes-bases", "zone-bases-partagees"):
            debut = contenu.find(f'data-testid="{nom_de_zone}"')
            if debut == -1:
                decoupe[nom_de_zone] = None
                continue
            fin = contenu.find("</section>", debut)
            decoupe[nom_de_zone] = contenu[debut:fin]
        return decoupe

    def test_l_onglet_des_bases_de_l_accueil_a_disparu(self):
        """
        Le doublon qu'on est venu supprimer. / The duplicate we removed.
        """
        contenu_de_tous_les_gabarits = "\n".join(
            gabarit.read_text(encoding="utf-8")
            for gabarit in GABARITS.rglob("*.html")
        )

        self.assertNotIn("zone-bases-accueil", contenu_de_tous_les_gabarits)
        self.assertNotIn("onglets-accueil", contenu_de_tous_les_gabarits)

    def test_mes_bases_et_celles_des_autres_restent_dans_deux_zones(self):
        """
        La distinction du 12 aout survit a l'unification : ce que j'ai
        cree, j'y REVIENS ; ce que d'autres publient, je l'EXPLORE.
        / The 12 August split survives the merge.
        """
        zones = self._zones_de_la_liste()

        self.assertIsNotNone(zones["zone-mes-bases"], "La zone « mes bases » manque.")
        self.assertIsNotNone(
            zones["zone-bases-partagees"], "La zone des bases publiques manque."
        )
        self.assertIn("ma-base", zones["zone-mes-bases"])
        self.assertIn("base-autrui", zones["zone-bases-partagees"])

    def test_une_base_a_moi_et_publique_ne_parait_qu_une_fois(self):
        self.ma_base.visibilite = VisibiliteDossier.PUBLIC
        self.ma_base.save(update_fields=["visibilite"])

        zones = self._zones_de_la_liste()

        self.assertIn("ma-base", zones["zone-mes-bases"])
        self.assertNotIn("ma-base", zones["zone-bases-partagees"])

    def test_la_base_privee_d_autrui_ne_parait_nulle_part(self):
        contenu = self.client.get("/bases/").content.decode()

        self.assertNotIn("base-privee-autrui", contenu)

    def test_la_liste_garde_ce_que_l_onglet_n_avait_pas(self):
        """
        L'unification ne se fait pas a perte : l'explication, les
        compteurs et la carte de creation restent.
        / The merge loses nothing: explanation, counters and the creation
        card all stay.
        """
        contenu = self.client.get("/bases/").content.decode()

        self.assertIn('data-testid="corpus-bases-intro"', contenu)
        self.assertIn('data-testid="corpus-bases-compteur"', contenu)
        self.assertIn("cellule-creation", contenu)

    def test_un_visiteur_anonyme_n_a_pas_de_zone_mes_bases(self):
        self.client.logout()

        zones = self._zones_de_la_liste()

        self.assertIsNone(
            zones["zone-mes-bases"],
            "Un visiteur anonyme se voit proposer une zone « mes bases ».",
        )
        self.assertIsNotNone(zones["zone-bases-partagees"])


class LeCarnetResteAtteignableTest(TestCase):
    """
    Garde-fou : la redirection de la racine ne doit pas casser l'ecran
    vers lequel elle mene. / Guard: the redirect must not break its own
    destination.

    LOCALISATION : front/tests/test_le_menu_et_le_message_d_accueil.py
    """

    def test_un_carnet_public_parait_pour_un_anonyme_sur_la_racine(self):
        proprietaire = User.objects.create_user(username="pro", password="mdp")
        Dossier.objects.create(
            name="Carnet ouvert", owner=proprietaire,
            visibilite=VisibiliteDossier.PUBLIC,
        )

        contenu = self.client.get("/", follow=True).content.decode()

        self.assertIn("Carnet ouvert", contenu)


class AucunEmojiDansLeMessageDAccueilTest(SimpleTestCase):
    """
    La meme regle que le corpus, appliquee au gabarit neuf : un emoji
    couleur ignore `color`, donc le mode sombre, et change d'aspect d'une
    plateforme a l'autre.
    / Same rule as the corpus screens, applied to the new template.

    LOCALISATION : front/tests/test_le_menu_et_le_message_d_accueil.py
    """

    def test_le_gabarit_de_la_modale_n_a_pas_d_emoji(self):
        import re

        motif_emoji = re.compile(
            "[\U0001F300-\U0001FAFF\U0001F1E6-\U0001F1FF\U0000FE0F]"
        )
        gabarit = GABARITS / "includes" / "message_d_accueil.html"

        trouves = motif_emoji.findall(gabarit.read_text(encoding="utf-8"))

        self.assertEqual(
            trouves, [], f"Emoji trouve(s) dans le message d'accueil : {trouves}"
        )
