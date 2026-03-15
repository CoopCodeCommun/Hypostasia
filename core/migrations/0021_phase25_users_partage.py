"""
PHASE-25 — Users et partage : modeles core.
Ajoute owner (nullable) sur Dossier et Page, remplace prenom par user FK
sur Question et ReponseQuestion, cree DossierPartage.
/ PHASE-25 — Users & sharing: core models.
Adds nullable owner to Dossier and Page, replaces prenom with user FK
on Question and ReponseQuestion, creates DossierPartage.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def supprimer_questions_et_reponses(apps, schema_editor):
    """
    Supprime les questions et reponses existantes car le champ prenom
    ne peut pas etre migre automatiquement vers un user FK.
    App pas en production — reset_demo les recree proprement.
    / Delete existing questions and answers because the prenom field
    cannot be automatically migrated to a user FK.
    App not in production — reset_demo recreates them properly.
    """
    Question = apps.get_model("core", "Question")
    Question.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0020_aimodel_base_url_alter_aimodel_model_choice_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Ajouter owner nullable sur Dossier et Page
        # / Add nullable owner to Dossier and Page
        migrations.AddField(
            model_name="dossier",
            name="owner",
            field=models.ForeignKey(
                blank=True,
                help_text="Proprietaire du dossier (null = legacy) / Folder owner",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="dossiers_possedes",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="page",
            name="owner",
            field=models.ForeignKey(
                blank=True,
                help_text="Proprietaire de la page (null = legacy) / Page owner",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="pages_possedees",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        # 2. Supprimer les questions/reponses existantes (prenom non migrable)
        # / Delete existing questions/answers (prenom not migratable)
        migrations.RunPython(supprimer_questions_et_reponses, migrations.RunPython.noop),
        # 3. Supprimer prenom et ajouter user FK sur Question
        # / Remove prenom and add user FK on Question
        migrations.RemoveField(model_name="question", name="prenom"),
        migrations.AddField(
            model_name="question",
            name="user",
            field=models.ForeignKey(
                default=1,  # Temporaire, toutes les lignes sont supprimees
                help_text="Auteur de la question / Question author",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="questions",
                to=settings.AUTH_USER_MODEL,
            ),
            preserve_default=False,
        ),
        # 4. Supprimer prenom et ajouter user FK sur ReponseQuestion
        # / Remove prenom and add user FK on ReponseQuestion
        migrations.RemoveField(model_name="reponsequestion", name="prenom"),
        migrations.AddField(
            model_name="reponsequestion",
            name="user",
            field=models.ForeignKey(
                default=1,
                help_text="Auteur de la reponse / Answer author",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="reponses_questions",
                to=settings.AUTH_USER_MODEL,
            ),
            preserve_default=False,
        ),
        # 5. Creer DossierPartage
        # / Create DossierPartage
        migrations.CreateModel(
            name="DossierPartage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("dossier", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="partages",
                    to="core.dossier",
                )),
                ("utilisateur", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="dossiers_partages",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "verbose_name": "Partage de dossier",
                "unique_together": {("dossier", "utilisateur")},
            },
        ),
    ]
