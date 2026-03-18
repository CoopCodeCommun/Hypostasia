# Migration : refactoring des statuts de debat (6 statuts)
# / Migration: refactoring debate statuses (6 statuses)
# Ajoute "nouveau" et "non_pertinent", change le default de "discutable" a "nouveau"
# Migre les donnees existantes : masquee=True → non_pertinent, discutable+0 commentaires → nouveau

from django.db import migrations, models


def migrer_statuts_existants(apps, schema_editor):
    """
    Migration de donnees :
    - masquee=True → statut_debat="non_pertinent"
    - statut_debat="discutable" + masquee=False + 0 commentaires → statut_debat="nouveau"
    / Data migration:
    - masquee=True → statut_debat="non_pertinent"
    - statut_debat="discutable" + masquee=False + 0 comments → statut_debat="nouveau"
    """
    ExtractedEntity = apps.get_model("hypostasis_extractor", "ExtractedEntity")
    CommentaireExtraction = apps.get_model("hypostasis_extractor", "CommentaireExtraction")

    # Masquees → non_pertinent / Hidden → non_pertinent
    ExtractedEntity.objects.filter(masquee=True).update(statut_debat="non_pertinent")

    # Discutables sans commentaires → nouveau / Discutable without comments → nouveau
    ids_entites_avec_commentaires = set(
        CommentaireExtraction.objects.values_list("entity_id", flat=True).distinct()
    )
    entites_discutables_sans_commentaires = ExtractedEntity.objects.filter(
        statut_debat="discutable",
        masquee=False,
    ).exclude(pk__in=ids_entites_avec_commentaires)
    entites_discutables_sans_commentaires.update(statut_debat="nouveau")


def inverser_migration(apps, schema_editor):
    """
    Rollback : nouveau → discutable, non_pertinent → discutable + masquee=True
    / Rollback: nouveau → discutable, non_pertinent → discutable + masquee=True
    """
    ExtractedEntity = apps.get_model("hypostasis_extractor", "ExtractedEntity")
    ExtractedEntity.objects.filter(statut_debat="non_pertinent").update(
        statut_debat="discutable", masquee=True,
    )
    ExtractedEntity.objects.filter(statut_debat="nouveau").update(
        statut_debat="discutable",
    )


class Migration(migrations.Migration):
    dependencies = [
        ("hypostasis_extractor", "0020_phase25_user_commentaire"),
    ]

    operations = [
        migrations.AlterField(
            model_name="extractedentity",
            name="statut_debat",
            field=models.CharField(
                choices=[
                    ("nouveau", "Nouveau"),
                    ("consensuel", "Consensuel"),
                    ("discutable", "Discutable"),
                    ("discute", "Discuté"),
                    ("controverse", "Controversé"),
                    ("non_pertinent", "Non pertinent"),
                ],
                default="nouveau",
                max_length=20,
            ),
        ),
        migrations.RunPython(migrer_statuts_existants, inverser_migration),
    ]
