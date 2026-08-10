"""
La suppression du flag `Page.moteur` refuse de perdre des surlignages.
/ Removing Page.moteur refuses to silently drop highlights.

LOCALISATION : core/tests/test_moteur_flag.py

Ce fichier verifiait le CHAMP `Page.moteur` : son defaut, ses deux
valeurs, sa pose a l'ingestion, et le fait qu'une migration ne bascule
rien. Le champ a ete supprime le 10 aout 2026 avec l'ancien moteur — un
flag qui ne commande plus rien est une question sans objet.

Ce qui reste a prouver tient en une chose : la migration 0056 doit
S'ARRETER si elle est jouee sur une base ou des pages attendent encore
leur reconversion (la production, une sauvegarde restauree). Sans ce
controle, elles seraient affichees sans leurs surlignages, en silence.
/ What remains worth proving: migration 0056 must refuse to run where
pages still await reconversion.
"""

from django.test import TestCase

import importlib

module_de_migration = importlib.import_module(
    "core.migrations.0056_suppression_du_flag_moteur",
)


class GardeDeLaMigrationDuFlagTest(TestCase):
    """Le controle de la migration 0056. / Migration 0056's guard."""

    def test_elle_s_arrete_s_il_reste_des_pages_sur_l_ancien(self):
        garde = module_de_migration.refuser_si_des_pages_sont_encore_sur_l_ancien

        with self.assertRaises(RuntimeError) as leve:
            garde(_ApplicationsFeintes(nombre_de_pages_anciennes=7), None)

        message = str(leve.exception)
        self.assertIn("7", message)
        # Le message doit DIRE quoi faire, pas seulement refuser.
        # / The message must say what to do, not merely refuse.
        self.assertIn("basculer_vers_le_moteur_element", message)

    def test_elle_laisse_passer_une_base_entierement_reconvertie(self):
        garde = module_de_migration.refuser_si_des_pages_sont_encore_sur_l_ancien

        garde(_ApplicationsFeintes(nombre_de_pages_anciennes=0), None)


class _RequeteFeinte:
    def __init__(self, combien):
        self._combien = combien

    def count(self):
        return self._combien


class _ModeleFeint:
    def __init__(self, combien):
        self.objects = self
        self._combien = combien

    def filter(self, **_criteres):
        return _RequeteFeinte(self._combien)


class _ApplicationsFeintes:
    """
    Le champ `moteur` n'existe plus dans le modele : on ne peut donc pas
    creer de vraie page ANCIEN pour exercer la garde. On lui donne le
    registre historique qu'une migration recoit.
    / The field is gone from the model, so we feed the guard the kind of
    historical registry a migration receives.
    """

    def __init__(self, nombre_de_pages_anciennes):
        self._modele = _ModeleFeint(nombre_de_pages_anciennes)

    def get_model(self, _application, _modele):
        return self._modele
