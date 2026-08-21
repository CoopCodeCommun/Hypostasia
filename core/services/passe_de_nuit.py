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
   le conteneur est tue en plein travail. Le recapitulatif du matin,
   qui attend la fin de la passe, attendrait alors POUR TOUJOURS — et
   personne ne recevrait plus rien, sans un message. Une passe trop
   vieille est donc declaree ABANDONNEE, et dite comme telle.
/ Two silent failures: concurrent passes, and a dead pass blocking the
morning mail forever.
"""

from datetime import timedelta

from django.utils import timezone

from core.models import PasseDeNuit

# Au-dela, une passe « en cours » est tenue pour morte. Douze heures :
# largement plus qu'une nuit de travail reel (un appel au redacteur par
# wiki, sequentiels), et bien moins que le prochain cycle quotidien —
# une passe abandonnee ne doit jamais survivre a la nuit suivante.
# / Beyond this, a "running" pass is presumed dead.
DUREE_MAXIMALE_D_UNE_PASSE = timedelta(hours=12)


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
