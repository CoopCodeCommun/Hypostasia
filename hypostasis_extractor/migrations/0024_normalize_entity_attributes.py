"""
Migration RunPython : normalise les attributs de toutes les ExtractedEntity existantes.
/ RunPython migration: normalize attributes of all existing ExtractedEntity records.

Idempotent : si les cles sont deja canoniques, le dict ne change pas.
/ Idempotent: if keys are already canonical, the dict is unchanged.
"""
from django.db import migrations


def normaliser_attributs_existants(apps, schema_editor):
    """
    Itere sur toutes les ExtractedEntity en batches de 500,
    normalise les attributs et bulk_update.
    / Iterate all ExtractedEntity in batches of 500,
    / normalize attributes and bulk_update.
    """
    # Import ici pour eviter les problemes d'etat des apps pendant la migration
    # / Import here to avoid app state issues during migration
    from front.normalisation import normaliser_attributs_entite

    ExtractedEntity = apps.get_model('hypostasis_extractor', 'ExtractedEntity')

    # Traiter par batches de 500 pour limiter la consommation memoire
    # / Process in batches of 500 to limit memory usage
    taille_batch = 500
    toutes_les_entites = ExtractedEntity.objects.exclude(attributes={}).exclude(attributes__isnull=True)
    nombre_total = toutes_les_entites.count()
    nombre_modifiees = 0

    for offset in range(0, nombre_total, taille_batch):
        batch = list(toutes_les_entites[offset:offset + taille_batch])
        entites_a_mettre_a_jour = []

        for entite in batch:
            attributs_originaux = entite.attributes or {}
            attributs_normalises = normaliser_attributs_entite(attributs_originaux)

            # Ne mettre a jour que si les attributs ont change
            # / Only update if attributes actually changed
            if attributs_normalises != attributs_originaux:
                entite.attributes = attributs_normalises
                entites_a_mettre_a_jour.append(entite)

        if entites_a_mettre_a_jour:
            ExtractedEntity.objects.bulk_update(entites_a_mettre_a_jour, ['attributes'])
            nombre_modifiees += len(entites_a_mettre_a_jour)

    if nombre_modifiees:
        print(f"\n  Normalisation : {nombre_modifiees}/{nombre_total} entites mises a jour")
    else:
        print(f"\n  Normalisation : {nombre_total} entites deja a jour")


def reverse_noop(apps, schema_editor):
    """
    Pas de retour en arriere : les donnees sont meilleures normalisees.
    / No rollback: data is better normalized.
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('hypostasis_extractor', '0023_extractionjob_tokens_reels_analyseur_version'),
    ]

    operations = [
        migrations.RunPython(
            normaliser_attributs_existants,
            reverse_noop,
        ),
    ]
