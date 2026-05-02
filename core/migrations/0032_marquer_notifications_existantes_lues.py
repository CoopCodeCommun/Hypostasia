"""
Marque tous les ExtractionJob et TranscriptionJob existants comme deja lus
au moment de la migration A.6. Sinon le bouton 'taches en cours'
apparaitrait en vert avec un compteur enorme au premier login post-migration.
/ Mark all existing jobs as 'already read' at A.6 migration time.
Otherwise the button would show a huge unread counter on first post-migration login.
"""
from django.db import migrations


def marquer_jobs_existants_lus(apps, schema_editor):
    ExtractionJob = apps.get_model('hypostasis_extractor', 'ExtractionJob')
    TranscriptionJob = apps.get_model('core', 'TranscriptionJob')

    nb_extractions = ExtractionJob.objects.update(notification_lue=True)
    nb_transcriptions = TranscriptionJob.objects.update(notification_lue=True)

    if nb_extractions or nb_transcriptions:
        print(
            f"  -> A.6 data migration : "
            f"{nb_extractions} extractions + {nb_transcriptions} transcriptions "
            f"marquees comme deja lues."
        )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0031_transcriptionjob_notification_lue'),
        ('hypostasis_extractor', '0027_extractionjob_notification_lue'),
    ]

    operations = [
        migrations.RunPython(
            marquer_jobs_existants_lus,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
