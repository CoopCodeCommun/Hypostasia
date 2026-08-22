"""
L'etat de la passe de nuit, lu par les deux commandes.
/ The nightly pass state, read by both commands.

LOCALISATION : core/services/passe_de_nuit.py

DEUX PANNES QUE CE MODULE EXISTE POUR EMPECHER, et qui ne levent
aucune erreur :

1. **Deux passes en meme temps.** Une passe qui dure plus longtemps
   que prevu et un cron qui repart : deux passes appellent le redacteur
   sur les MEMES wikis. La facture double, et deux tours concurrents se
   disputent le meme article.

2. **Une passe morte qui bloque tout.** `terminee_le` reste NULL quand
   une tache est tuee net — SIGKILL, OOM, plafond de 30 minutes : le
   `finally` qui rend la main ne s'execute pas, et le compteur n'atteint
   jamais son total. Le recapitulatif du matin, qui attend la fin de la
   passe, attendrait alors POUR TOUJOURS — et personne ne recevrait plus
   rien, sans un message. UN SEUL wiki tue couterait le mail de TOUT LE
   MONDE. Une passe trop vieille est donc declaree ABANDONNEE, et le
   delai est calcule pour qu'elle le soit AVANT le mail du matin.
/ Two silent failures: concurrent passes, and a dead pass blocking the
morning mail forever.
"""

from datetime import timedelta

from django.utils import timezone

from core.models import PasseDeNuit

# Au-dela, une passe « en cours » est tenue pour morte.
#
# TROIS HEURES, ET LE CHIFFRE EST CONTRAINT PAR LE MATIN. Une tache
# tuee net (SIGKILL, OOM, plafond de 30 minutes) ne rend jamais la
# main : `finally` ne s'execute pas sous SIGKILL, et le compteur
# n'atteint donc jamais son total. La passe reste ouverte, et le
# recapitulatif — qui attend sa fin — refuse d'envoyer. UN SEUL wiki
# tue coute alors le mail de TOUT LE MONDE pour la journee.
#
# Avec une peremption a douze heures, une passe morte a 2 h 05 bloquait
# encore le matin de 6 h. A trois heures, elle est fauchee a 5 h 05 : le
# recapitulatif la trouve fermee et part. Le fan-out rend ce delai
# large — chaque tache est un appel de quelques dizaines de secondes,
# et le plafond Celery est de 30 minutes par tache.
# / Three hours, and the number is set by the morning: a pass killed at
# 2:05 must be reaped before the 6:00 mail, or one dead task costs
# everyone's daily mail.
DUREE_MAXIMALE_D_UNE_PASSE = timedelta(hours=3)


def fermer_les_passes_abandonnees():
    """
    Marque comme terminees les passes trop vieilles pour etre vivantes.
    / Closes passes too old to still be running.

    LOCALISATION : core/services/passe_de_nuit.py

    :return: le nombre de passes fermees / how many were closed
    """
    limite = timezone.now() - DUREE_MAXIMALE_D_UNE_PASSE
    passes_mortes = PasseDeNuit.objects.filter(
        terminee_le__isnull=True, lancee_le__lt=limite,
    )
    nombre = passes_mortes.count()
    if nombre:
        passes_mortes.update(terminee_le=timezone.now())
    return nombre


def passe_en_cours():
    """
    La passe qui tourne vraiment, ou None.
    / The pass that is really running, or None.

    LOCALISATION : core/services/passe_de_nuit.py

    Ferme d'abord les passes abandonnees : sans ce nettoyage, un
    conteneur tue une fois suffirait a bloquer toutes les nuits et
    tous les matins suivants.
    / Closes dead passes first: one kill would otherwise block
    every following night.
    """
    fermer_les_passes_abandonnees()
    return PasseDeNuit.objects.filter(terminee_le__isnull=True).first()
