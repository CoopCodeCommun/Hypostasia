"""
Rattache le journal des operations de structure a la Page.
/ Attaches the structural operations journal to the Page.

LOCALISATION : core/migrations/0038_journal_operations_rattache_a_la_page.py

POURQUOI CETTE MIGRATION

ElementOperation ne tenait qu'a son ElementDocument, en CASCADE. Or une
scission et une fusion suppriment toujours leurs elements sources : la
premiere operation suivante effacait donc l'histoire de la precedente.
Scinder puis refusionner ne laissait aucune trace de la scission.

Le journal tient desormais a la PAGE, qui survit aux operations. La
reference a l'element devient indicative (SET_NULL), et
identifiant_stable_element garde de quoi reconnaitre l'element meme apres
sa disparition.
/ The journal now hangs off the Page, which survives the operations.

Ecrite a la main plutot que generee : le champ page est non-nullable et
la table est vide, donc aucune valeur par defaut n'est necessaire —
PostgreSQL accepte d'ajouter une colonne NOT NULL sans defaut sur une
table vide. La generation automatique aurait exige un defaut factice.
/ Hand-written: the table is empty, so no bogus default is needed.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0037_remove_elementdocument_unicite_ordre_dans_la_page_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="elementoperation",
            name="page",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="operations_sur_elements",
                to="core.page",
                help_text=(
                    "Page ou l'operation a eu lieu / Page where the "
                    "operation happened"
                ),
                # null=True le temps de l'ajout, puis rendu non-nullable
                # juste apres : la table est vide, aucune ligne a remplir.
                # / Nullable during the add, then made non-nullable.
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="elementoperation",
            name="page",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="operations_sur_elements",
                to="core.page",
                help_text=(
                    "Page ou l'operation a eu lieu / Page where the "
                    "operation happened"
                ),
            ),
        ),
        migrations.AlterField(
            model_name="elementoperation",
            name="element",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="operations",
                to="core.elementdocument",
                help_text=(
                    "Element concerne, s'il existe encore / Element "
                    "affected, if it still exists"
                ),
            ),
        ),
        migrations.AddField(
            model_name="elementoperation",
            name="identifiant_stable_element",
            field=models.UUIDField(
                blank=True,
                db_index=True,
                null=True,
                help_text=(
                    "L'identifiant de l'element au moment de l'operation. "
                    "Survit a sa suppression / The element's id at "
                    "operation time"
                ),
            ),
        ),
        migrations.AddField(
            model_name="elementoperation",
            name="donnees",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text=(
                    "Contexte de l'operation : position de coupe, elements "
                    "sources, etc. Meme role que PageEdit.donnees_avant "
                    "/ Operation context: cut position, source elements..."
                ),
            ),
        ),
    ]
