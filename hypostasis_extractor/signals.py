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

from core.models import ElementDocument, EtatElement

from .models import (
    AncrageExtraction,
    CommentaireExtraction,
    EtatAncrage,
    ExtractedEntity,
)


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


# =============================================================================
# ETAT DES ELEMENTS — moteur ELEMENT (SPEC v2, phase A)
# / Element state — ELEMENT engine (SPEC v2, phase A)
#
# ElementDocument.etat n'est jamais saisi a la main. Il est recalcule ici,
# a chaque fois qu'une portion d'ancrage ou un commentaire bouge.
# / ElementDocument.etat is never set by hand, always recomputed here.
# =============================================================================


def _portions_actives_de_l_element(element_id):
    """
    Donne les portions d'ancrage qui comptent pour l'etat d'un element.
    / Returns the anchor portions that count towards an element's state.

    LOCALISATION : hypostasis_extractor/signals.py

    UNE PORTION COMPTE seulement si les deux conditions sont vraies :

    1. Son extraction n'est PAS masquee. Une extraction masquee par la
       curation ne se voit plus : elle ne doit pas imposer un regime
       d'edition contraint sur l'element.

    2. Son ancrage n'est PAS detache. Une portion detachee a perdu son
       passage source : il n'y a plus rien a reconcilier ni a notifier.
       C'est ce qui permet a un element masque de redevenir LIBRE, donc
       librement editable, une fois toutes ses portions detachees.

    / A portion counts only if its extraction is not hidden AND its anchor
    is not detached.

    :param element_id: Cle primaire de l'element / Element primary key
    :return: Un QuerySet de AncrageExtraction / A QuerySet of AncrageExtraction
    """
    return AncrageExtraction.objects.filter(
        element_id=element_id,
        extraction__masquee=False,
    ).exclude(
        etat_ancrage=EtatAncrage.DETACHEE,
    )


def recalculer_etat_de_l_element(element_id):
    """
    Recalcule ElementDocument.etat a partir de ce qui y est attache.
    / Recomputes ElementDocument.etat from what is attached to it.

    LOCALISATION : hypostasis_extractor/signals.py

    LES TROIS ETATS POSSIBLES :

    - LIBRE   : aucune portion active. L'element s'edite sans ceremonie.
    - ANALYSE : des portions actives, mais aucun commentaire. L'edition
                demande une reconciliation des ancres.
    - DEBATTU : au moins une extraction active porte un commentaire.
                L'edition demande une justification et une notification.

    Il n'y a PAS d'etat SCELLE : le scellement a ete abandonne. Il n'y a
    donc ni verrou, ni course entre le signal et un descellement.
    / There is no SCELLE state: sealing was dropped, so no lock, no race.

    On ecrit avec update() et non save(), comme synchroniser_statut_debat
    juste au-dessus : save() redeclencherait les signaux post_save de
    ElementDocument pour rien.
    / We write with update(), not save(), to avoid retriggering signals.

    :param element_id: Cle primaire de l'element a recalculer / Element PK
    :return: None
    """
    if not element_id:
        return

    portions_actives = _portions_actives_de_l_element(element_id)

    # Aucune portion active : l'element est libre.
    # / No active portion: the element is free.
    element_a_des_portions_actives = portions_actives.exists()
    if not element_a_des_portions_actives:
        nouvel_etat = EtatElement.LIBRE
    else:
        # Au moins une portion active. Reste a savoir si l'une des
        # extractions concernees porte un commentaire.
        # / At least one active portion. Does any extraction carry a comment?
        identifiants_des_extractions = portions_actives.values_list(
            "extraction_id", flat=True,
        )
        au_moins_un_commentaire = CommentaireExtraction.objects.filter(
            entity_id__in=identifiants_des_extractions,
        ).exists()

        if au_moins_un_commentaire:
            nouvel_etat = EtatElement.DEBATTU
        else:
            nouvel_etat = EtatElement.ANALYSE

    # On n'ecrit que si l'etat change vraiment, pour ne pas toucher la
    # ligne (et son updated_at) sans raison.
    # / Write only if the state actually changes.
    ElementDocument.objects.filter(
        pk=element_id,
    ).exclude(
        etat=nouvel_etat,
    ).update(etat=nouvel_etat)


@receiver([post_save, post_delete], sender=AncrageExtraction)
def recalculer_etat_apres_changement_d_ancrage(sender, instance, **kwargs):
    """
    Recalcule l'etat de l'element quand une portion d'ancrage bouge.
    / Recomputes the element state when an anchor portion changes.

    LOCALISATION : hypostasis_extractor/signals.py

    Declenche quand une portion est creee (une extraction vient d'etre
    ancree), modifiee (une reconciliation l'a repositionnee ou detachee),
    ou supprimee.
    / Triggered when a portion is created, modified or deleted.
    """
    recalculer_etat_de_l_element(instance.element_id)


@receiver([post_save, post_delete], sender=CommentaireExtraction)
def recalculer_etat_apres_changement_de_commentaire(sender, instance, **kwargs):
    """
    Recalcule l'etat des elements ou l'extraction commentee est ancree.
    / Recomputes the state of elements where the commented extraction is anchored.

    LOCALISATION : hypostasis_extractor/signals.py

    Une extraction peut etre ancree dans plusieurs elements (ancre M2M).
    Un seul commentaire fait donc basculer en DEBATTU TOUS les elements
    que cette extraction traverse.
    / One comment switches to DEBATTU every element the extraction spans.
    """
    entite_id = instance.entity_id
    if not entite_id:
        return

    identifiants_des_elements = AncrageExtraction.objects.filter(
        extraction_id=entite_id,
    ).values_list("element_id", flat=True)

    for element_id in set(identifiants_des_elements):
        recalculer_etat_de_l_element(element_id)


@receiver(post_save, sender=ExtractedEntity)
def recalculer_etat_apres_masquage_d_extraction(sender, instance, created, **kwargs):
    """
    Recalcule l'etat des elements quand une extraction est masquee ou remontree.
    / Recomputes element states when an extraction is hidden or shown again.

    LOCALISATION : hypostasis_extractor/signals.py

    Masquer une extraction par la curation peut faire retomber un element
    de DEBATTU a ANALYSE, ou de ANALYSE a LIBRE. Sans ce signal, l'element
    garderait un regime d'edition contraint par une extraction que plus
    personne ne voit.
    / Without this, an element would stay constrained by a hidden extraction.

    DEUX GARDES AVANT DE TRAVAILLER, ET POURQUOI :

    Ce signal se declenche a CHAQUE sauvegarde d'une ExtractedEntity. Une
    analyse produit des dizaines d'extractions d'un coup. Sans garde, on
    ferait une requete inutile a chaque ligne creee, y compris pour les
    pages de l'ANCIEN moteur qui n'ont aucune portion d'ancrage.
    / Without guards, one useless query per saved row, old engine included.

    Garde 1 — creation : une extraction qui vient de naitre n'a encore
    aucune portion. Le recalcul viendra quand la portion sera creee, via
    le signal sur AncrageExtraction.

    Garde 2 — update_fields : si l'appelant a precise quels champs il
    sauvegarde et que masquee n'en fait pas partie, l'etat des elements
    ne peut pas avoir change.
    """
    # Garde 1 : a la creation, aucune portion n'existe encore.
    # / Guard 1: at creation time, no portion exists yet.
    if created:
        return

    # Garde 2 : sauvegarde ciblee qui ne touche pas au masquage.
    # / Guard 2: targeted save that does not touch masquee.
    champs_sauvegardes = kwargs.get("update_fields")
    if champs_sauvegardes is not None and "masquee" not in champs_sauvegardes:
        return

    identifiants_des_elements = AncrageExtraction.objects.filter(
        extraction_id=instance.pk,
    ).values_list("element_id", flat=True)

    for element_id in set(identifiants_des_elements):
        recalculer_etat_de_l_element(element_id)
