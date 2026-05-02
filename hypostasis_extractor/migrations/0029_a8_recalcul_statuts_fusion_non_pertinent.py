"""
Recalcul des statuts existants et fusion non_pertinent -> masquee=True.

Doit etre execute AVANT le AlterField qui retrecit l'enum, sinon Django
rejette les anciennes valeurs (consensuel, discutable, etc.) au moment
de l'AlterField check.

/ Recalculate existing statuses and fold non_pertinent -> masquee=True.
Must run BEFORE the AlterField that shrinks the enum, otherwise Django
rejects old values when AlterField runs validation.
"""
from django.db import migrations


def recalculer_statuts(apps, schema_editor):
    """
    Etape 1 : non_pertinent -> masquee=True (statut sera ecrase a l'etape 2)
    Etape 2 : recalcul depuis les commentaires
    / Step 1: non_pertinent -> masquee=True (status overwritten in step 2)
    / Step 2: recalculate statuses from comments
    """
    ExtractedEntity = apps.get_model('hypostasis_extractor', 'ExtractedEntity')
    CommentaireExtraction = apps.get_model('hypostasis_extractor', 'CommentaireExtraction')

    # Etape 1 : non_pertinent -> masquee=True
    # / Step 1: non_pertinent -> masquee=True
    nb_non_pertinent = ExtractedEntity.objects.filter(
        statut_debat='non_pertinent',
    ).update(masquee=True)
    if nb_non_pertinent:
        print(f"  -> A.8 : {nb_non_pertinent} entites non_pertinent fusionnees dans masquee=True")

    # Etape 2 : recalcul des statuts depuis les commentaires
    # / Step 2: recalculate statuses from comments
    ids_commentees = set(CommentaireExtraction.objects.values_list(
        'entity_id', flat=True,
    ).distinct())

    nb_commente = ExtractedEntity.objects.filter(
        pk__in=ids_commentees,
    ).exclude(statut_debat='commente').update(statut_debat='commente')

    nb_nouveau = ExtractedEntity.objects.exclude(
        pk__in=ids_commentees,
    ).exclude(statut_debat='nouveau').update(statut_debat='nouveau')

    print(f"  -> A.8 : {nb_commente} entites passees a 'commente', "
          f"{nb_nouveau} entites repassees a 'nouveau'")


def restaurer_statuts(apps, schema_editor):
    """Reverse no-op : valeurs riches perdues. / Reverse no-op: rich values lost."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('hypostasis_extractor', '0028_a7_retrait_reformulation_restitution_fields'),
    ]

    operations = [
        migrations.RunPython(recalculer_statuts, reverse_code=restaurer_statuts),
    ]
