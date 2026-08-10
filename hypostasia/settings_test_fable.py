"""
Settings de test avec base DEDIEE — session Fable.
/ Test settings with a DEDICATED test database — Fable session.

LOCALISATION : hypostasia/settings_test_fable.py

Deux sessions Claude travaillent en parallele sur ce depot (byobu).
Quand chacune lance `manage.py test`, Django cree et DETRUIT la meme
base `test_hypostasia` : le run de l'une detruit la base de l'autre en
plein vol (« database test_hypostasia does not exist », deadlocks).
Ce module donne a cette session SA base de test. L'autre session peut
faire pareil avec son propre suffixe.
/ Two parallel sessions share the same default test DB and destroy each
other's runs; this module gives this session its own test database.

Usage :
    docker exec hypostasia_dev_web python manage.py test <cibles> \\
        --settings=hypostasia.settings_test_fable
"""

from hypostasia.settings import *  # noqa: F401,F403 — memes reglages, seule la base de test change
from hypostasia.settings import DATABASES

DATABASES["default"].setdefault("TEST", {})
DATABASES["default"]["TEST"]["NAME"] = "test_hypostasia_fable"
