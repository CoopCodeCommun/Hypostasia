from front.tests.e2e.test_01_navigation import *  # noqa: F401,F403
from front.tests.e2e.test_02_lecture import *  # noqa: F401,F403
from front.tests.e2e.test_03_import import *  # noqa: F401,F403
from front.tests.e2e.test_04_extractions import *  # noqa: F401,F403
from front.tests.e2e.test_05_config_ia import *  # noqa: F401,F403
from front.tests.e2e.test_06_charte_visuelle import *  # noqa: F401,F403
from front.tests.e2e.test_07_layout import *  # noqa: F401,F403
from front.tests.e2e.test_08_curation import *  # noqa: F401,F403
from front.tests.e2e.test_09_alignement import *  # noqa: F401,F403
from front.tests.e2e.test_10_mobile import *  # noqa: F401,F403
from front.tests.e2e.test_11_confirmation_analyse import *  # noqa: F401,F403
from front.tests.e2e.test_12_providers_ia import *  # noqa: F401,F403
from front.tests.e2e.test_13_auth import *  # noqa: F401,F403
# test_14 et test_17 manquaient de cette liste : leurs 15 tests etaient
# ECRITS mais jamais collectes par `manage.py test front.tests.e2e`.
# Verifies le 12 aout avant de les ajouter — les 15 passent.
# Cette liste est explicite : un module e2e qui n'y figure pas ne tourne
# JAMAIS dans la suite, et rien ne le signale.
# / test_14 and test_17 were written but never collected. This list is
# explicit: a module missing from it silently never runs.
from front.tests.e2e.test_14_visibilite import *  # noqa: F401,F403
from front.tests.e2e.test_15_token import *  # noqa: F401,F403
from front.tests.e2e.test_16_invitation import *  # noqa: F401,F403
from front.tests.e2e.test_17_filtre_contributeur import *  # noqa: F401,F403
from front.tests.e2e.test_18_panneau_integre import *  # noqa: F401,F403
from front.tests.e2e.test_19_toast_sombre import *  # noqa: F401,F403
# test_20, test_22 et test_23 manquaient de cette liste (13 aout).
# Ils n'etaient pas morts pour autant : `manage.py test` sans etiquette
# les trouve par decouverte de fichiers, et ils y passent au vert. Mais
# `manage.py test front.tests.e2e` — la commande du quotidien — passe par
# CE fichier, et n'en voyait aucun. Un test qui ne tourne que dans la
# commande qu'on ne lance jamais ne protege rien.
# / test_20, 22 and 23 were missing here. Not dead — `manage.py test`
# finds them by file discovery and they pass — but the daily command
# goes through this file and saw none of them.
from front.tests.e2e.test_20_tracabilite import *  # noqa: F401,F403
from front.tests.e2e.test_21_carte_du_panneau import *  # noqa: F401,F403
from front.tests.e2e.test_22_corpus import *  # noqa: F401,F403
from front.tests.e2e.test_23_moteur_element import *  # noqa: F401,F403
# test_24 : la liste des carnets confrontee a l'etalon (12 aout).
# / test_24: the notebook list against the reference mockup.
from front.tests.e2e.test_24_liste_des_carnets import *  # noqa: F401,F403
# test_25 : la liste des bases de connaissances en cartes (12 aout).
# / test_25: the knowledge-base directory as a card grid.
from front.tests.e2e.test_25_liste_des_bases import *  # noqa: F401,F403
# test_26 (« le burger mene aux bases ») a ete supprime le 12 aout 2026 :
# le burger lui-meme n'existe plus. Un test qui verrouille un controle
# retire ne protege rien, il empeche le retrait.
# / test_26 is gone with the hamburger it locked down.
# test_27 : les gestes que l'arbre lateral portait SEUL, relogés sur
# /carnets/ et /carnets/<id>/ avant que l'arbre disparaisse.
# / test_27: the gestures the side tree alone hosted, rehoused before
# the tree goes away.
from front.tests.e2e.test_27_actions_du_carnet import *  # noqa: F401,F403
from front.tests.e2e.test_28_couverture_de_base import *  # noqa: F401,F403
from front.tests.e2e.test_29_bases_sur_la_home import *  # noqa: F401,F403
# test_30 (« l'en-tete du panneau ») a ete supprime le 12 aout : cet
# en-tete a FUSIONNE avec le fil d'Ariane dans une bande unique
# (test_31). Un test qui verrouille un element supprime ne protege
# rien, il empeche le changement.
# / test_30 is gone with the header it locked down: it merged into
# the context strip.
from front.tests.e2e.test_31_bande_de_contexte import *  # noqa: F401,F403
from front.tests.e2e.test_32_lecteur_audio import *  # noqa: F401,F403
