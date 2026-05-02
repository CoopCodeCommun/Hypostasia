"""
Signaux pour la synchronisation automatique du statut de debat.
Le statut est auto-derive de l'existence d'au moins un commentaire :
- "nouveau" si zero commentaire
- "commente" si >= 1 commentaire

Utilise update() plutot que save() pour eviter de redeclencher les signaux
post_save d'ExtractedEntity (recursion potentielle, et inutile ici).

/ Signals for automatic debate status synchronization.
Status is auto-derived from comment existence:
- "nouveau" if zero comments
- "commente" if >= 1 comment

Uses update() instead of save() to avoid retriggering ExtractedEntity
post_save signals (potential recursion, unnecessary here).

LOCALISATION : hypostasis_extractor/signals.py
"""
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import CommentaireExtraction, ExtractedEntity


@receiver([post_save, post_delete], sender=CommentaireExtraction)
def synchroniser_statut_debat(sender, instance, **kwargs):
    """
    Met a jour ExtractedEntity.statut_debat selon l'existence de commentaires.
    Declenche apres save (creation/modification) ou delete d'un CommentaireExtraction.
    / Updates ExtractedEntity.statut_debat based on comment existence.
    Triggered after save or delete of a CommentaireExtraction.
    """
    entite_id = instance.entity_id
    if not entite_id:
        return
    a_des_commentaires = CommentaireExtraction.objects.filter(
        entity_id=entite_id,
    ).exists()
    nouveau_statut = "commente" if a_des_commentaires else "nouveau"
    ExtractedEntity.objects.filter(
        pk=entite_id,
    ).exclude(statut_debat=nouveau_statut).update(statut_debat=nouveau_statut)
