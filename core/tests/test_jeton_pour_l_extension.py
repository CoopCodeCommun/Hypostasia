"""
Connecter l'extension en un clic : le jeton se recupere, il ne se recopie plus.
/ One-click extension connection: the token is fetched, not copied by hand.

LOCALISATION : core/tests/test_jeton_pour_l_extension.py

LE GESTE QU'ON SUPPRIME. Pour utiliser l'extension il fallait ouvrir
`/auth/token/`, selectionner 40 caracteres hexadecimaux, les copier,
ouvrir les options de l'extension, les coller. Cinq gestes et un
presse-papier, pour une valeur qu'aucun humain ne peut relire.

POURQUOI PAS LA SESSION DIRECTEMENT. Mesure du 21 aout 2026 : une requete
d'ECRITURE authentifiee par session est refusee des que l'origine de
l'appelant n'est pas dans `CSRF_TRUSTED_ORIGINS` — et Firefox donne a
chaque INSTALLATION d'une extension un UUID aleatoire
(`moz-extension://<uuid>`), qu'aucune liste blanche serveur ne peut
contenir. La session ne peut donc jamais ecrire depuis Firefox.

Elle peut en revanche LIRE : un GET n'est pas soumis au controle CSRF.
C'est exactement ce qu'il faut pour aller chercher le jeton une fois, et
n'utiliser que lui ensuite.
/ Session auth can never WRITE from a Firefox extension (random
per-install origin, un-whitelistable), but it can READ: a GET is not
CSRF-checked. Enough to fetch the token once.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.authtoken.models import Token

Utilisateur = get_user_model()


class JetonPourLExtensionTest(TestCase):
    """`GET /api/pages/mon_jeton/` — le jeton du compte connecte."""

    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            username="lecteur_de_jeton", password="motdepasse",
        )
        self.autre = Utilisateur.objects.create_user(
            username="autre_lecteur_de_jeton", password="motdepasse",
        )

    def test_sans_authentification_c_est_refuse(self):
        reponse = self.client.get("/api/pages/mon_jeton/")
        self.assertEqual(reponse.status_code, 401)

    def test_la_session_du_site_suffit_a_recuperer_son_jeton(self):
        """
        C'EST TOUT LE MECANISME. L'utilisateur est connecte au site dans
        son navigateur ; l'extension lit son jeton avec ce cookie, une
        seule fois, et ne se sert plus que du jeton ensuite.
        / The whole mechanism: the site session fetches the token once.
        """
        self.client.force_login(self.utilisateur)
        reponse = self.client.get("/api/pages/mon_jeton/")

        self.assertEqual(reponse.status_code, 200)
        jeton_en_base = Token.objects.get(user=self.utilisateur)
        self.assertEqual(reponse.json()["token"], jeton_en_base.key)
        self.assertEqual(reponse.json()["username"], "lecteur_de_jeton")

    def test_le_jeton_est_cree_s_il_n_existe_pas_encore(self):
        """
        Sans cela, un compte qui n'a jamais ouvert `/auth/token/`
        recevrait « pas de jeton » — et il faudrait aller le creer a la
        main, c'est-a-dire refaire le geste qu'on supprime.
        / Otherwise an account that never opened /auth/token/ would have
        to go and create one by hand: the very gesture being removed.
        """
        self.assertFalse(Token.objects.filter(user=self.utilisateur).exists())

        self.client.force_login(self.utilisateur)
        reponse = self.client.get("/api/pages/mon_jeton/")

        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(Token.objects.filter(user=self.utilisateur).exists())

    def test_appeler_deux_fois_rend_le_MEME_jeton(self):
        """
        LE POINT QUI CASSERAIT TOUT SI ON L'OUBLIAIT. Regenerer le jeton
        a chaque appel invaliderait celui des AUTRES installations :
        connecter l'extension sur son portable deconnecterait celle du
        poste fixe, sans que rien ne le dise. Ce geste connecte une
        machine de plus, il n'en deconnecte aucune.
        / Regenerating on each call would silently disconnect every other
        installation. Connecting one machine must not disconnect others.
        """
        self.client.force_login(self.utilisateur)
        premier_appel = self.client.get("/api/pages/mon_jeton/").json()["token"]
        second_appel = self.client.get("/api/pages/mon_jeton/").json()["token"]

        self.assertEqual(premier_appel, second_appel)
        self.assertEqual(Token.objects.filter(user=self.utilisateur).count(), 1)

    def test_on_ne_recupere_jamais_le_jeton_d_un_autre(self):
        jeton_de_l_autre = Token.objects.create(user=self.autre)

        self.client.force_login(self.utilisateur)
        reponse = self.client.get("/api/pages/mon_jeton/")

        self.assertNotEqual(reponse.json()["token"], jeton_de_l_autre.key)

    def test_un_jeton_deja_en_main_marche_aussi(self):
        """
        Utile pour reverifier une configuration : l'extension qui a deja
        un jeton peut confirmer qu'il est le bon.
        / Useful to re-check a configuration.
        """
        jeton = Token.objects.create(user=self.utilisateur)
        reponse = self.client.get(
            "/api/pages/mon_jeton/", HTTP_AUTHORIZATION=f"Token {jeton.key}",
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.json()["token"], jeton.key)
