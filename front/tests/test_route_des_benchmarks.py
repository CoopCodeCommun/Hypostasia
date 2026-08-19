"""
La route qui sert les mesures de `benchmarks/`.
/ The route serving the `benchmarks/` notes.

LOCALISATION : front/tests/test_route_des_benchmarks.py

DEUX CHOSES A VERROUILLER :

1. **La traversee de chemin.** La vue prend un chemin dans l'URL. Sans
   verification d'appartenance APRES resolution, `../../.env` serait
   servi — la cle d'API de chaque plateforme avec.
2. **L'authentification.** Ces comptes rendus nomment des modeles, des
   tarifs et des defauts du produit. Rien de secret, rien de public non
   plus.
"""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase


class LaRouteDesMesuresTest(TestCase):

    def setUp(self):
        self.utilisateur = get_user_model().objects.create_user(
            username="lecteur_mesures", password="motdepasse",
        )
        self.client = Client()
        self.client.force_login(self.utilisateur)

    def test_l_index_liste_les_mesures(self):
        reponse = self.client.get("/benchmarks/")

        self.assertEqual(reponse.status_code, 200)
        self.assertIn('data-testid="benchmarks-index"', reponse.content.decode())

    def test_une_mesure_est_rendue_en_html(self):
        reponse = self.client.get(
            "/benchmarks/voir/redaction/"
            "2026-08-19_trois-redacteurs-a-perimetre-fige.md",
        )

        contenu = reponse.content.decode()
        self.assertEqual(reponse.status_code, 200)
        self.assertIn('data-testid="benchmarks-mesure"', contenu)
        # Le markdown est bien RENDU, pas affiche brut.
        # / The markdown is rendered, not shown raw.
        self.assertIn("<table", contenu)

    def test_une_traversee_de_chemin_est_refusee(self):
        # SANS CE REFUS, le `.env` du dépôt serait servi — et avec lui
        # toutes les clés d'API. / Without this, .env would be served.
        # Django normalise certains chemins avant la vue (301) ; ce qui
        # compte est qu'AUCUN ne rende 200 avec du contenu.
        # / Django normalises some paths before the view; what matters is
        # that none returns 200 with content.
        for chemin in ("../.env", "../../etc/passwd", "../manage.py",
                       "..%2F.env", "juge_de_verification/../../.env"):
            with self.subTest(chemin=chemin):
                reponse = self.client.get(f"/benchmarks/voir/{chemin}")
                self.assertNotEqual(reponse.status_code, 200)
                self.assertNotIn("API_KEY", reponse.content.decode())

    def test_un_fichier_qui_n_est_pas_un_markdown_est_refuse(self):
        reponse = self.client.get(
            "/benchmarks/voir/juge_de_verification/etalon-du-juge.json",
        )

        self.assertNotEqual(reponse.status_code, 200)

    def test_un_visiteur_anonyme_n_y_accede_pas(self):
        reponse = Client().get("/benchmarks/")

        self.assertNotEqual(reponse.status_code, 200)
