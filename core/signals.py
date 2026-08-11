"""
Signaux de l'app core : filet de securite de la validation des categories.
/ Core app signals: safety net for category validation.

LOCALISATION : core/signals.py

Charges par CoreConfig.ready() (core/apps.py). Le serializer valide en
premiere ligne (erreur de formulaire propre) ; ces signaux garantissent
qu'un .add(), un .set() ou un chargement de fixture ne peut pas
introduire une categorie etrangere.
/ Loaded by CoreConfig.ready(). The serializer validates first; these
signals catch .add(), .set() and fixture loading.

LIMITE CONNUE : une ecriture DIRECTE sur la table de liaison
(categories.through.objects.create / bulk_create) ne declenche aucun
signal m2m_changed — limitation de Django, pas de ce code. Ne jamais
ecrire sur le through directement.
/ KNOWN LIMIT: direct through-table writes bypass m2m_changed signals
(Django limitation). Never write to the through table directly.
"""

from django.db.models.signals import m2m_changed, pre_delete
from django.dispatch import receiver

from .models import (
    AppartenanceDossierBase,
    AppartenancePageDossier,
    CategorieBase,
    CategorieDossier,
    Dossier,
    Page,
)
from .services.corpus import (
    retirer_une_note_d_un_carnet,
    valider_les_categories_d_une_appartenance,
    valider_les_categories_d_une_appartenance_de_base,
)


@receiver(
    m2m_changed,
    sender=AppartenancePageDossier.categories.through,
    dispatch_uid="corpus_refuser_categorie_d_un_autre_dossier",
)
def refuser_une_categorie_d_un_autre_dossier(
    sender, instance, action, pk_set, reverse, **kwargs
):
    """
    Filet de securite au niveau ORM, sens note-carnet.
    / ORM-level safety net, note-notebook side.

    LOCALISATION : core/signals.py

    LE KWARG reverse EST INDISPENSABLE (SPEC-corpus § 3.4, correction n°3).
    La v1.0 l'ignorait, ce qui cassait le sens inverse :
      - reverse=False : categories.add(cat) sur une appartenance
                        -> instance EST l'appartenance, pk_set = pks de categories
      - reverse=True  : categorie.appartenances.add(appartenance)
                        -> instance EST la categorie, pk_set = pks d'appartenances
    Sans distinguer les deux, on filtrerait des pks d'appartenances comme
    si c'etaient des pks de categories : validation erratique, ou qui
    laisse tout passer.
    / Without the reverse kwarg, membership pks would be filtered as if
    they were category pks.
    """
    if action != "pre_add":
        return

    if reverse:
        categorie_ajoutee = instance
        appartenances = AppartenancePageDossier.objects.filter(pk__in=pk_set)
        for appartenance in appartenances:
            valider_les_categories_d_une_appartenance(
                appartenance, [categorie_ajoutee]
            )
        return

    categories = CategorieDossier.objects.select_related("liste").filter(
        pk__in=pk_set
    )
    valider_les_categories_d_une_appartenance(instance, categories)


@receiver(
    m2m_changed,
    sender=AppartenanceDossierBase.categories.through,
    dispatch_uid="corpus_refuser_categorie_d_une_autre_base",
)
def refuser_une_categorie_d_une_autre_base(
    sender, instance, action, pk_set, reverse, **kwargs
):
    """
    Le symetrique, cote carnet-base. La v1.0 de la spec l'avait oublie :
    ni validateur, ni signal, ni test — le vocabulaire d'une base pouvait
    fuir dans une autre.
    / The symmetric one, notebook-base side. Spec v1.0 simply forgot it.

    LOCALISATION : core/signals.py
    """
    if action != "pre_add":
        return

    if reverse:
        categorie_ajoutee = instance
        appartenances = AppartenanceDossierBase.objects.filter(pk__in=pk_set)
        for appartenance in appartenances:
            valider_les_categories_d_une_appartenance_de_base(
                appartenance, [categorie_ajoutee]
            )
        return

    categories = CategorieBase.objects.select_related("liste").filter(
        pk__in=pk_set
    )
    valider_les_categories_d_une_appartenance_de_base(instance, categories)


@receiver(
    pre_delete,
    sender=Dossier,
    dispatch_uid="corpus_reaffecter_les_fk_avant_suppression_du_carnet",
)
def reaffecter_les_fk_avant_suppression_du_carnet(sender, instance, **kwargs):
    """
    Avant de supprimer un carnet, retire proprement chaque note dont la
    FK le designait : le service reaffecte la FK a un autre carnet de la
    note, ou la met a NULL.
    / Before deleting a notebook, properly remove each note whose FK
    pointed to it: the service reassigns the FK or nulls it.

    LOCALISATION : core/signals.py

    POURQUOI UN SIGNAL ET PAS SEULEMENT LA VUE (relecture D) : l'admin
    Django, une cascade ou un delete() en shell contournent la vue. Sans
    ce signal, le SET_NULL brut laisserait une note multi-carnets avec
    une FK NULL et des appartenances restantes — l'invariant « FK =
    premier carnet » serait casse par un chemin invisible.
    / Admin, cascades and shell deletes bypass the view; raw SET_NULL
    would break the "FK = first notebook" invariant silently.

    Le signal tourne DANS la transaction du delete() (le collecteur
    Django enveloppe la suppression dans atomic) : pas d'etat partiel.
    / Runs INSIDE the delete() transaction: no partial state.
    """
    for page_du_carnet in Page.objects.filter(dossier=instance):
        retirer_une_note_d_un_carnet(page_du_carnet, instance)


@receiver(
    pre_delete,
    sender="hypostasis_extractor.ExtractedEntity",
    dispatch_uid="synthese_arbitrer_la_suppression_d_une_source",
)
def arbitrer_la_suppression_d_une_source(sender, instance, **kwargs):
    """
    Une extraction citee ne peut pas disparaitre en silence
    (SPEC-synthese § 4.2). DEUX REGIMES, selon QUI cite :

    - une SYNTHESE DIRIGEE cite -> on REFUSE la suppression. C'est un
      acte date : sa preuve ne peut pas s'evaporer.
    - seuls des WIKIS citent -> on AUTORISE, et chaque citation bascule
      en SUPPRIMEE. Le wiki est vivant : sa prochaine mise a jour verra
      la source manquante. Le lecteur voit « source supprimee » au lieu
      d'un renvoi mort.

    Ce qui est interdit dans les deux cas : l'orphelinage silencieux.
    / Never silent orphaning; the regime depends on who cites.

    LOCALISATION : core/signals.py
    """
    from .models import EtatDeLaSource, SourceLink, TypeDeNote, TypeLien

    citations = SourceLink.objects.filter(
        extraction_source=instance, type_lien=TypeLien.CITE,
    )
    if citations.filter(
        page_cible__type_de_note=TypeDeNote.SYNTHESE
    ).exists():
        from .services.synthese import SuppressionRefuseeSourceCitee
        raise SuppressionRefuseeSourceCitee(instance, list(citations))

    citations.update(etat_de_la_source=EtatDeLaSource.SUPPRIMEE)
