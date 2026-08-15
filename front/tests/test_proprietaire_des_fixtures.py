"""
A qui appartiennent les notes de demonstration.
/ Who owns the demonstration notes.

LOCALISATION : front/tests/test_proprietaire_des_fixtures.py

Lancer avec :
    docker exec -w /app hypostasia_web python manage.py test \\
        front.tests.test_proprietaire_des_fixtures \\
        --settings=hypostasia.settings_test_opus

POURQUOI CELA COMPTE

Les analyses de la demonstration partent dans la file Celery, et se
suivent depuis le menu des taches — un menu qui ne montre a chacun que
SES notes (`_filtre_proprietaire_page`). Le proprietaire des fixtures
decide donc de qui voit l'installation travailler.

Constate le 15 aout 2026 sur une base reelle : `marie` voyait douze
notifications, l'administrateur `jonas` aucune. La regle etait « le
premier superuser, sinon le premier utilisateur par cle primaire » —
or aucun compte n'est superuser dans ce projet, et le premier par pk
est un compte de demonstration ordinaire.
/ The task menu only shows each user their own notes, so fixture
ownership decides who sees the install working. In practice a demo
account owned everything and the administrator saw nothing.

LA REGLE VOULUE

Un compte d'administration d'abord (superuser, puis staff), et seulement
a defaut le premier venu. Sur une base neuve, aucun compte n'existe :
c'est `jonas` qui est cree, en staff.
/ An admin account first, and only failing that the first user.
"""

from django.contrib.auth.models import User
from django.test import TestCase

from front.management.commands.charger_fixtures_sample import (
    Command as CommandeDesDocuments,
)


class LeProprietaireEstUnCompteDAdministrationTest(TestCase):
    """
    LOCALISATION : front/tests/test_proprietaire_des_fixtures.py
    """

    def _proprietaire_choisi(self):
        commande = CommandeDesDocuments()
        commande.a_blanc = True
        return commande._proprietaire()

    def test_le_superuser_est_preferé_au_premier_venu(self):
        User.objects.create_user(username="marie")
        administrateur = User.objects.create_superuser(
            username="admin-du-site", password="x",
        )

        self.assertEqual(self._proprietaire_choisi(), administrateur)

    def test_a_defaut_de_superuser_le_compte_staff_est_choisi(self):
        # Le cas REEL de ce projet : aucun superuser, un seul compte
        # staff (jonas), et des comptes de demonstration crees avant lui.
        # / The real case here: no superuser, one staff account, and demo
        # accounts created before it.
        User.objects.create_user(username="marie")
        User.objects.create_user(username="thomas")
        administrateur = User.objects.create_user(
            username="jonas", is_staff=True,
        )

        self.assertEqual(
            self._proprietaire_choisi(), administrateur,
            "Les fixtures appartiennent a un compte de demonstration : "
            "l'administrateur ne verrait aucune tache dans son menu.",
        )

    def test_sans_aucun_compte_d_administration_on_prend_le_premier(self):
        # Repli : mieux vaut un proprietaire que pas de fixtures du tout.
        # / Fallback: better an owner than no fixtures at all.
        premier = User.objects.create_user(username="marie")
        User.objects.create_user(username="thomas")

        self.assertEqual(self._proprietaire_choisi(), premier)

    def test_sur_une_base_neuve_le_proprietaire_est_a_creer(self):
        # En mode a blanc, la commande annonce la creation sans l'ecrire.
        # / In dry-run the command announces the creation without writing.
        self.assertIsNone(self._proprietaire_choisi())
        self.assertEqual(User.objects.count(), 0)
