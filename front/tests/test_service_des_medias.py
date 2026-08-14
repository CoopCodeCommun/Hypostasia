"""
Test : nginx sert les medias, en dev comme en prod.
/ Test: nginx serves media, in dev as in prod.

LOCALISATION : front/tests/test_service_des_medias.py

LE BUG QUI A MENE A CE TEST — 14 aout 2026

Le mainteneur : « si je clique sur un play dans le texte, l'audio se
lance depuis le debut ».

Cause, mesuree : en dev, `/media/` tombait dans le `location /` de
`nginx/dev.conf`, donc sur `django.views.static.serve`. Cette vue NE
GERE PAS les requetes `Range` — verifie sur Django 6.0.2, `FileResponse`
n'en contient aucune trace. Elle repond `200 OK` avec le fichier ENTIER
la ou le navigateur demande un morceau.

Or un navigateur IGNORE SILENCIEUSEMENT une affectation de
`currentTime` qu'il ne peut pas atteindre : ni erreur, ni exception, la
valeur retombe simplement. Le « play » d'un tour de parole demandait
donc 1,9s, n'obtenait rien, et la lecture partait de zero.

CE QU'IL NE FALLAIT PAS FAIRE, ET QUI A ETE FAIT D'ABORD

Contourner cote client : rejouer le positionnement a chaque `canplay`,
et forcer `preload="auto"` + `load()`. Le mainteneur a entendu « un
gresillement dans l'oreille a la place de l'audio » — `load()` vide le
tampon sous une lecture en cours, et le repositionnement rejoue faisait
sauter le decodeur plusieurs fois par seconde. Un bricolage cote client
ne repare pas un serveur qui ne sait pas envoyer un morceau de fichier :
il ajoute un defaut au premier.

CE QUE CE TEST GARDE

Que `/media/` reste servi par nginx dans les DEUX configurations. C'est
la correction elle-meme, et aucun test e2e ne peut la couvrir :
`StaticLiveServerTestCase` est un serveur Django, nginx n'est pas dans
sa boucle. Ce test lit donc la CONFIGURATION, faute de pouvoir lire le
comportement.
/ A client-side workaround cannot fix a server that will not send a byte
range — it only adds a defect. This test guards the real fix, by reading
the config: no e2e test can, since nginx is not in its loop.
"""

import pathlib

from django.conf import settings
from django.test import SimpleTestCase

CONFIGURATIONS_NGINX = pathlib.Path(settings.BASE_DIR) / "nginx"


class ServiceDesMediasTest(SimpleTestCase):
    """
    LOCALISATION : front/tests/test_service_des_medias.py
    """

    def test_les_medias_sont_servis_par_nginx(self):
        """
        Les deux configurations, et pour la meme raison : nginx repond
        `206 Partial Content`, Django repond 200 avec tout le fichier.
        / Both configs: nginx answers 206, Django answers 200 with the
        whole file.
        """
        for nom_de_la_configuration in ("dev.conf", "default.conf"):
            with self.subTest(configuration=nom_de_la_configuration):
                contenu = (CONFIGURATIONS_NGINX / nom_de_la_configuration).read_text(
                    encoding="utf-8",
                )

                self.assertIn(
                    "location /media/",
                    contenu,
                    f"{nom_de_la_configuration} ne sert plus /media/ : les "
                    f"requêtes tombent sur django.views.static, qui ignore "
                    f"les requêtes Range. Se déplacer dans un audio "
                    f"redeviendrait impossible, en silence.",
                )
                self.assertIn(
                    "alias /app/media/",
                    contenu,
                    f"{nom_de_la_configuration} déclare /media/ sans le "
                    f"faire pointer sur le dossier des médias.",
                )

    def test_django_ne_sert_les_medias_qu_en_secours(self):
        """
        `hypostasia/urls.py` garde une route `/media/` pour le cas ou
        l'application tourne SANS nginx — un `manage.py runserver` nu,
        un test. C'est un secours, pas le chemin normal : ce test
        s'assure qu'il reste conditionne a DEBUG, pour qu'aucune
        production ne se mette a servir ses medias par Django sans que
        personne ne s'en apercoive.
        / Django's media route is a fallback for running without nginx;
        it must stay behind DEBUG so no production quietly falls back to
        it.
        """
        urls = (pathlib.Path(settings.BASE_DIR) / "hypostasia" / "urls.py").read_text(
            encoding="utf-8",
        )

        position_du_if_debug = urls.find("settings.DEBUG")
        position_du_static = urls.find("static(settings.MEDIA_URL")

        self.assertNotEqual(position_du_static, -1)
        self.assertNotEqual(position_du_if_debug, -1)
        self.assertLess(
            position_du_if_debug,
            position_du_static,
            "La route /media/ de Django n'est plus derrière un test sur "
            "DEBUG : une production pourrait servir ses médias par "
            "Django, donc sans support des requêtes Range.",
        )
