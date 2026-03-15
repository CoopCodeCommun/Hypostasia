"""
PHASE-25 — Remplace prenom par user FK sur CommentaireExtraction.
/ PHASE-25 — Replace prenom with user FK on CommentaireExtraction.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def supprimer_commentaires_existants(apps, schema_editor):
    """
    Supprime les commentaires existants car le champ prenom ne peut pas
    etre migre automatiquement vers un user FK.
    App pas en production — reset_demo les recree proprement.
    / Delete existing comments because the prenom field cannot be
    automatically migrated to a user FK.
    App not in production — reset_demo recreates them properly.
    """
    CommentaireExtraction = apps.get_model("hypostasis_extractor", "CommentaireExtraction")
    CommentaireExtraction.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("hypostasis_extractor", "0019_ajouter_updated_at_extracted_entity"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Supprimer les commentaires existants (prenom non migrable)
        # / Delete existing comments (prenom not migratable)
        migrations.RunPython(supprimer_commentaires_existants, migrations.RunPython.noop),
        # 2. Supprimer prenom et ajouter user FK
        # / Remove prenom and add user FK
        migrations.RemoveField(model_name="commentaireextraction", name="prenom"),
        migrations.AddField(
            model_name="commentaireextraction",
            name="user",
            field=models.ForeignKey(
                default=1,
                help_text="Auteur du commentaire / Comment author",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="commentaires_extraction",
                to=settings.AUTH_USER_MODEL,
            ),
            preserve_default=False,
        ),
    ]
