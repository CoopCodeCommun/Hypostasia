"""
La commande qui vide la base doit savoir la remplir ensuite.
/ The command that empties the database must know how to refill it.

LOCALISATION : front/tests/test_reset_demo.py

Lancer avec :
    docker exec -w /app hypostasia_web python manage.py test \\
        front.tests.test_reset_demo --settings=hypostasia.settings_test_opus

LE DEFAUT QUE CES TESTS FERMENT

`reset_demo` faisait `flush` puis `loaddata demo_completes.json`. Or
cette fixture ne se chargeait plus depuis le 21 mars 2026 — cinq mois —
a cause de deux migrations qui ont change le schema sous elle
(`updated_at` sur ExtractedEntity, puis le remplacement de `prenom` par
une cle etrangere sur CommentaireExtraction).

La commande vidait donc la base et ECHOUAIT a la recharger : quiconque
la lancait perdait tout sans rien recuperer. Ironie de l'affaire, la
migration 0020 porte le commentaire « App pas en production —
reset_demo les recree proprement » : le filet de securite invoque etait
lui-meme rompu.
/ It flushed the database then failed to reload it: whoever ran it lost
everything and got nothing back. The migration that relied on this
safety net had been broken for five months.

CE QUE CES TESTS VERROUILLENT

La commande recharge par le MEME chemin que l'installation
(`install.sh`), et jamais par une fixture JSON — c'est precisement en
divergeant de ce chemin qu'elle est morte sans que personne ne le voie.
/ It refills through the same path as the installer, never a JSON
fixture: diverging from that path is exactly how it died unnoticed.

Le `flush` n'est jamais execute ici : il est remplace par un mock. Un
test qui vide vraiment la base de test la sort de la transaction
d'isolation et contamine les tests suivants.
/ The flush is mocked, never run: truncating breaks test isolation.
"""

from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

COMMANDE_DES_DOCUMENTS = "charger_fixtures_sample"
COMMANDE_DES_EXTRACTIONS = "charger_extractions_demo"


def _noms_des_commandes_appelees(appels):
    """
    Rend les noms des commandes passees a call_command, dans l'ordre.
    / Returns the command names passed to call_command, in order.

    LOCALISATION : front/tests/test_reset_demo.py
    """
    return [appel.args[0] for appel in appels.call_args_list if appel.args]


class ResetDemoRechargeCeQuIlVideTest(TestCase):
    """
    LOCALISATION : front/tests/test_reset_demo.py
    """

    def _lancer_reset_demo(self):
        with patch(
            "front.management.commands.reset_demo.call_command",
        ) as appels:
            call_command("reset_demo", "--no-input")
        return appels

    def test_la_base_est_videe_puis_rechargee(self):
        appels = self._lancer_reset_demo()
        noms = _noms_des_commandes_appelees(appels)

        self.assertIn("flush", noms)
        self.assertIn(
            COMMANDE_DES_DOCUMENTS, noms,
            "reset_demo vide la base sans recharger les documents : "
            "elle laisserait une base VIDE, ce qu'elle a fait pendant "
            "cinq mois.",
        )
        self.assertIn(
            COMMANDE_DES_EXTRACTIONS, noms,
            "reset_demo recharge les documents mais pas les extractions : "
            "la demo reviendrait nue.",
        )

    def test_le_rechargement_suit_le_vidage(self):
        # Recharger avant de vider effacerait ce qu'on vient de charger.
        # / Reloading before flushing would erase what was just loaded.
        noms = _noms_des_commandes_appelees(self._lancer_reset_demo())

        self.assertLess(noms.index("flush"), noms.index(COMMANDE_DES_DOCUMENTS))
        self.assertLess(
            noms.index(COMMANDE_DES_DOCUMENTS),
            noms.index(COMMANDE_DES_EXTRACTIONS),
        )

    def test_aucune_fixture_json_n_est_recharge(self):
        # C'est la divergence qui a tue cette commande : elle rechargeait
        # par un chemin que personne n'empruntait plus, donc que personne
        # ne testait. / This divergence is what killed the command.
        appels = self._lancer_reset_demo()
        noms = _noms_des_commandes_appelees(appels)

        self.assertNotIn(
            "loaddata", noms,
            "reset_demo recharge par une fixture JSON : c'est le chemin "
            "qui a casse en silence pendant cinq mois. Elle doit "
            "recharger comme install.sh.",
        )

    def test_sans_confirmation_la_commande_ne_touche_a_rien(self):
        # La confirmation interactive est le dernier garde-fou avant un
        # flush. Repondre « non » doit tout arreter.
        # / Answering "no" must stop everything.
        with patch(
            "front.management.commands.reset_demo.call_command",
        ) as appels, patch("builtins.input", return_value="n"):
            call_command("reset_demo")

        self.assertEqual(_noms_des_commandes_appelees(appels), [])
