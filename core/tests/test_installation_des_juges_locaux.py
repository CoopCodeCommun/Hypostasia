"""
Les quatre juges locaux doivent pouvoir tourner dans le conteneur.
/ The four local judges must be able to run inside the container.

LOCALISATION : core/tests/test_installation_des_juges_locaux.py

CE QUE CE TEST PROTEGE, ET CE QU'IL A DEJA COUTE. Le dossier des juges
locaux annoncait « quatre juges branches en production ». Il en tournait
TROIS : `distilcamembert` exige `sentencepiece` — son depot n'a pas de
`tokenizer.json`, donc son tokeniseur ne peut pas etre charge sans lui —
et ce paquet ne vivait que dans `/tmp/banc_deps`, hors du venv, atteint
par un `PYTHONPATH` que le worker ne portait pas.

CE QUE CA PRODUISAIT : le juge levait `ModuleNotFoundError` a chaque
paquet, son tour de role notait ZERO paire, et la garde
`arret_sans_progres` stoppait TOUTE la campagne — y compris pour les
trois juges sains. Une campagne exigeait donc un geste manuel par
arret, et le quatrieme juge ne notait jamais rien.

CE TEST NE CHARGE AUCUN MODELE : les quatre pesent 5,13 Go residents. Il
verifie ce dont ils ont besoin, pas ce qu'ils rendent.
"""

import importlib.util
import tomllib
from pathlib import Path

from django.test import SimpleTestCase

RACINE_DU_DEPOT = Path(__file__).resolve().parents[2]


def _dependances_declarees():
    """Les dependances de `pyproject.toml`. / Declared dependencies."""
    with open(RACINE_DU_DEPOT / "pyproject.toml", "rb") as fichier:
        projet = tomllib.load(fichier)
    return [
        ligne.split(">=")[0].split("[")[0].strip().lower()
        for ligne in projet["project"]["dependencies"]
    ]


class LesDependancesDesJugesLocauxSontDeclarees(SimpleTestCase):
    """
    DECLAREES, pas seulement presentes. C'est la lecon de Pillow, ecrite
    dans `pyproject.toml` : un paquet utilise directement mais installe
    seulement comme dependance TRANSITIVE disparait le jour ou l'on
    allege celui qui l'apportait — et la panne ne nomme jamais sa cause.
    / Declared, not merely present: the Pillow lesson.
    """

    def test_sentencepiece_est_declare(self):
        """
        `distilcamembert` ne peut pas charger son tokeniseur sans lui.
        / distilcamembert cannot load its tokenizer without it.
        """
        self.assertIn("sentencepiece", _dependances_declarees())

    def test_transformers_est_declare(self):
        """
        Les quatre juges l'importent directement. Il n'arrivait ici que
        par `docling` : alleger Docling les aurait tous fait tomber.
        / All four import it directly; it only arrived via docling.
        """
        self.assertIn("transformers", _dependances_declarees())

    def test_sentencepiece_est_importable_dans_le_conteneur(self):
        """
        Declare ne suffit pas : le venv doit le porter. Sans lui, le
        worker leve `ModuleNotFoundError` a chaque paquet.
        / Declared is not enough: the venv must carry it.
        """
        self.assertIsNotNone(
            importlib.util.find_spec("sentencepiece"),
            "sentencepiece est déclaré mais absent du venv : "
            "relancer `uv sync`.",
        )

    def test_les_quatre_juges_sont_declares(self):
        """
        Le compte fait foi partout ailleurs — README, CHANGELOG,
        supervisord, celery.py annoncent « quatre juges ».
        / The count is asserted everywhere else.
        """
        from core.services.juges_locaux import JUGES

        self.assertEqual(len(JUGES), 4)

    def test_chaque_juge_nomme_son_depot_et_son_cadrage(self):
        """
        Un avis dont on ignore le depot ou le cadrage n'est pas
        relisable : ni rejouable, ni comparable.
        / An opinion without repo and framing is not reviewable.
        """
        from core.services.juges_locaux import JUGES

        for nom, definition in JUGES.items():
            with self.subTest(juge=nom):
                self.assertIn("depot", definition)
                self.assertIn("libelle", definition)
                self.assertIn("contradiction", definition)
