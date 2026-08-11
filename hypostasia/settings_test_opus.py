"""
Settings de test avec base DEDIEE — session Opus.
/ Test settings with a DEDICATED test database — Opus session.

LOCALISATION : hypostasia/settings_test_opus.py

Deux sessions Claude travaillent en parallele sur ce depot (byobu).
Quand chacune lance `manage.py test`, Django cree et DETRUIT la meme
base `test_hypostasia` : le run de l'une detruit la base de l'autre en
plein vol (« database test_hypostasia does not exist », deadlocks, ou
un EOFError sur la question « voulez-vous supprimer la base ? »).
Ce module donne a cette session SA base de test ; la session Fable a
la sienne dans settings_test_fable.py.
/ Two parallel sessions share the same default test DB and destroy each
other's runs; this module gives this session its own test database.

Rappel de la contrainte machine : le serveur a 8 Go et heberge aussi la
PROD. Deux bases de test coexistent sans probleme, mais deux runs
LOURDS simultanes, non — on se coordonne toujours avant un gros run.
/ Two test databases are fine; two heavy runs at once are not.

Usage :
    docker exec hypostasia_dev_web python manage.py test <cibles> \\
        --settings=hypostasia.settings_test_opus
"""

from hypostasia.settings import *  # noqa: F401,F403 — memes reglages, seule la base de test change
from hypostasia.settings import DATABASES

DATABASES["default"].setdefault("TEST", {})
DATABASES["default"]["TEST"]["NAME"] = "test_hypostasia_opus"
