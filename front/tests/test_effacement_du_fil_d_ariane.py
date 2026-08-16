"""
Le fil d'Ariane s'efface quand l'ecran d'arrivee n'en a pas.
/ The breadcrumb clears itself on screens that have no path.

LOCALISATION : front/tests/test_effacement_du_fil_d_ariane.py

POURQUOI CES TESTS EXISTENT

Le fil ne vit PAS dans `#zone-lecture` : il est dans la bande de
contexte de `base.html`, au-dessus des deux colonnes, parce que
`#zone-lecture` porte `overflow-y: auto` et clipperait tout ce qui
depasse. Un swap HTMX qui remplace la zone de lecture ne le touche donc
jamais — c'est a la REPONSE de le redeposer, par un OOB swap.

Consequence : un ecran qui oublie `_fil_ariane_oob.html` n'affiche pas
une bande vide, il laisse en place LE CHEMIN DE L'ECRAN PRECEDENT. On
se retrouve sur la racine du corpus, ou sur l'accueil, avec un fil qui
annonce une note ou l'on n'est plus.

Sans `fil_carnet` au contexte, `_fil_ariane.html` ne rend rien : l'OOB
depose alors un conteneur VIDE, et c'est precisement ce vide qui efface
le fil precedent, puis escamote la bande entiere via
`.bande-de-contexte:not(:has(.fil-ariane))` (maquette.css).

Ces tests verrouillent la presence de l'OOB sur chaque ecran sans fil.
Ils ne peuvent pas verifier le rendu final (c'est le navigateur qui
applique le swap) — ils verifient que la REPONSE porte de quoi effacer.
/ The breadcrumb lives outside #zone-lecture, so an HTMX swap never
touches it: the response must redeposit it. A screen that omits the OOB
strands the previous screen's path. These tests lock the OOB's presence.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import BaseDeConnaissances, Dossier, VisibiliteDossier

User = get_user_model()

# Le fragment que HTMX applique pour remplacer le fil.
# / The fragment HTMX applies to replace the breadcrumb.
MARQUEUR_OOB = 'hx-swap-oob="innerHTML:#fil-ariane-conteneur"'


class EcransSansFilDeposentUnOobVideTest(TestCase):
    """
    LOCALISATION : front/tests/test_effacement_du_fil_d_ariane.py
    """

    def setUp(self):
        self.utilisateur = User.objects.create_user(
            username="lectrice", password="motdepasse"
        )
        self.client.force_login(self.utilisateur)
        self.base = BaseDeConnaissances.objects.create(
            nom="Une base", slug="une-base",
            owner=self.utilisateur, visibilite=VisibiliteDossier.PRIVE,
        )
        self.carnet = Dossier.objects.create(
            name="Un carnet", owner=self.utilisateur,
            visibilite=VisibiliteDossier.PRIVE,
        )

    def _reponse_htmx(self, url):
        return self.client.get(url, HTTP_HX_REQUEST="true").content.decode()

    def test_l_accueil_efface_le_fil(self):
        """
        Le cas le plus visible : le logo « Hypostasia » de la barre
        d'outils est un `hx-get="/"`, pas un rechargement. Sans l'OOB, le
        fil du carnet d'ou l'on vient reste AU-DESSUS DE L'ACCUEIL.
        / The wordmark is an hx-get: without the OOB the breadcrumb of
        the notebook you came from sits above the home screen.
        """
        self.assertIn(MARQUEUR_OOB, self._reponse_htmx("/"))

    def test_la_liste_des_bases_efface_le_fil(self):
        self.assertIn(MARQUEUR_OOB, self._reponse_htmx("/bases/"))

    def test_le_detail_d_une_base_efface_le_fil(self):
        """Une base n'est pas dans un carnet : elle n'a pas de chemin."""
        self.assertIn(MARQUEUR_OOB, self._reponse_htmx(f"/bases/{self.base.slug}/"))

    def test_la_liste_des_carnets_efface_le_fil(self):
        self.assertIn(MARQUEUR_OOB, self._reponse_htmx("/carnets/"))

    def test_ces_ecrans_deposent_un_conteneur_VIDE(self):
        """
        C'est le vide qui efface. Un OOB qui porterait un fil ne
        remplacerait qu'un chemin par un autre.
        / The emptiness is what clears: an OOB carrying a path would
        merely swap one trail for another.
        """
        contenu = self._reponse_htmx("/bases/")

        debut = contenu.find(MARQUEUR_OOB)
        fragment = contenu[debut:debut + 400]
        self.assertNotIn("<nav", fragment)
        self.assertNotIn("fil-carnet", fragment)


class UnEcranAvecFilLeDeposeTest(TestCase):
    """
    Le pendant du test precedent : la ou un chemin EXISTE, l'OOB le
    porte. Sans ce test, vider le fil partout passerait pour un succes.
    / The counterpart: where a path exists, the OOB carries it.

    LOCALISATION : front/tests/test_effacement_du_fil_d_ariane.py
    """

    def setUp(self):
        self.utilisateur = User.objects.create_user(
            username="lecteur", password="motdepasse"
        )
        self.client.force_login(self.utilisateur)
        self.carnet = Dossier.objects.create(
            name="Carnet de bord", owner=self.utilisateur,
            visibilite=VisibiliteDossier.PRIVE,
        )

    def test_un_carnet_depose_son_propre_fil(self):
        contenu = self.client.get(
            f"/carnets/{self.carnet.pk}/", HTTP_HX_REQUEST="true",
        ).content.decode()

        self.assertIn(MARQUEUR_OOB, contenu)
        self.assertIn("Carnet de bord", contenu)
        self.assertIn('data-testid="fil-ariane"', contenu)


class LeChargementDirectNeDoublePasLeFilTest(TestCase):
    """
    HTMX n'applique ses OOB que sur SES reponses. Au chargement direct
    (F5), c'est `base.html` qui rend le fil dans la bande ; rendre l'OOB
    en plus y afficherait un SECOND fil, inerte, au milieu du texte.
    C'est la garde `{% if request.htmx %}` de `_fil_ariane_oob.html`.
    / HTMX only applies OOB swaps to its own responses: on a direct load
    the OOB would paint a second, inert breadcrumb into the page.

    LOCALISATION : front/tests/test_effacement_du_fil_d_ariane.py
    """

    def setUp(self):
        self.utilisateur = User.objects.create_user(
            username="visiteuse", password="motdepasse"
        )
        self.client.force_login(self.utilisateur)
        self.carnet = Dossier.objects.create(
            name="Carnet direct", owner=self.utilisateur,
            visibilite=VisibiliteDossier.PRIVE,
        )

    def test_sans_entete_htmx_aucun_oob_n_est_rendu(self):
        contenu = self.client.get(f"/carnets/{self.carnet.pk}/").content.decode()

        self.assertNotIn(MARQUEUR_OOB, contenu)
        # Le fil est bien la, mais une seule fois — pose par base.html.
        # / The breadcrumb is there, once, placed by base.html.
        self.assertEqual(contenu.count('data-testid="fil-ariane"'), 1)
