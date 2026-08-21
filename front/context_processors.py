"""
Les variables que `base.html` lit sur CHAQUE page, sans qu'une vue les pose.
/ The variables base.html reads on EVERY page, with no view posting them.

LOCALISATION : front/context_processors.py

POURQUOI UN CONTEXT PROCESSOR ET PAS UN CONTEXTE DE VUE

`base.html` est rendu par une quinzaine de vues, reparties sur six
fichiers. Le message d'accueil doit paraitre sur toutes : le poser dans
chaque contexte demanderait quinze ajouts, et le seizieme ecran ecrit
demain l'oublierait — en silence, puisqu'une variable absente vaut faux
dans un gabarit Django.

C'est exactement le cas d'usage d'un context processor : une valeur que
le SQUELETTE lit, jamais un ecran.
/ base.html is rendered by some fifteen views: a per-view context would
be forgotten by the sixteenth, silently.
"""

from front.views_accueil import le_message_d_accueil_doit_s_afficher


def message_d_accueil(request):
    """
    Dit a `base.html` s'il doit inclure la modale d'accueil.
    / Tell base.html whether to include the welcome modal.

    LOCALISATION : front/context_processors.py

    La decision entiere vit dans `views_accueil.py`, a cote de l'UUID
    qu'elle compare et de l'endpoint qui l'ecrit. Ce fichier-ci ne fait
    que la transporter jusqu'au gabarit : deux copies de la regle
    finiraient par diverger.

    :param request: la requete Django en cours
    :return: le dictionnaire ajoute au contexte de tout gabarit
    / The rule itself lives next to the UUID it compares.
    """
    return {
        "afficher_le_message_d_accueil": (
            le_message_d_accueil_doit_s_afficher(request)
        ),
    }
