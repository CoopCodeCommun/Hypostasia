"""
Le troisième type d'analyseur, et la COPIE qui le garnit.
/ The third analyzer type, and the COPY that fills it.

LOCALISATION : hypostasis_extractor/migrations/0038_le_type_rediger_un_article.py

ELLE COPIE, ELLE NE BASCULE PAS — et c'est une correction délibérée de la
note qui a commandé ce chantier
(`PLAN/TODO/2026-08-23-typer-les-analyseurs-par-action.md`, addendum du
1er septembre 2026).

L'analyseur de synthèse sert DEUX métiers aujourd'hui : la rédaction
d'article (par `_prompt_systeme_de_synthese`) et la synthèse d'UNE note
(par trois vues qui résolvent `type_analyseur="synthetiser"`). Le
basculer laisserait ces trois vues sans aucun analyseur — HTTP 400,
« Aucun analyseur de synthèse actif » — et le remède que ce toast affiche
(`docker compose down -v && make install`) ne réparerait RIEN : les
fixtures retrouvent l'analyseur PAR SON NOM et ne recréeraient jamais de
`synthetiser`. La casse serait permanente, et le message mensonger.
/ It copies rather than moves: moving would permanently break note
synthesis, and the on-screen remedy would not repair it.

CE QUE LA COPIE PRÉSERVE : le texte du mainteneur. Si « Synthèse
délibérative » a été éditée à la main, le rédacteur naît avec CE
texte-là, jamais avec celui des fixtures. C'est l'intention de la note —
le prompt personnalisé ne devient pas orphelin — obtenue sans casser un
geste.
/ It preserves the maintainer's own text, which is the note's intent.

CE QU'ELLE NE PEUT PAS FAIRE, et pourquoi les fixtures font aussi le
travail : `bin/install.sh` migre AVANT de poser les fixtures. Sur un
clone neuf, « Synthèse délibérative » n'existe pas encore quand cette
migration passe — elle ne copie alors rien, et c'est
`creer_les_modeles_ia_et_les_analyseurs()` qui crée le rédacteur.
/ On a fresh clone there is nothing to copy yet: the seeding does it.
"""

from django.db import migrations, models

# LE MÊME NOM QUE LES FIXTURES, au caractère près. S'ils divergeaient, le
# démarrage suivant créerait un SECOND rédacteur garni du texte par défaut
# qui, naissant `est_par_defaut=True`, décocherait celui-ci — le prompt
# copié cesserait de servir sans qu'aucune erreur ne le dise.
# Verrouillé par `test_la_migration_et_les_fixtures_nomment_le_MEME_analyseur`.
# / The very name the fixtures use: a mismatch would steal the default.
NOM_DE_L_ANALYSEUR_DE_REDACTION = "Rédacteur d'article"


def copier_la_synthese_vers_un_redacteur(apps, schema_editor):
    """
    Donne au type neuf une copie du préambule qui servait déjà.
    / Gives the new type a copy of the preamble already in use.

    IDEMPOTENTE : si un rédacteur existe déjà, elle ne touche à rien.
    / Idempotent: an existing writer is left alone.
    """
    AnalyseurSyntaxique = apps.get_model(
        "hypostasis_extractor", "AnalyseurSyntaxique",
    )
    PromptPiece = apps.get_model("hypostasis_extractor", "PromptPiece")

    deja_pose = AnalyseurSyntaxique.objects.filter(
        type_analyseur="rediger_un_article",
    ).exists()
    if deja_pose:
        return

    # ON COPIE CELUI QUI SERVAIT, pas celui qui porte le bon nom. Avant
    # ce chantier, le preambule d'un article se resolvait PAR TYPE —
    # actif, `synthetiser`, trie `-est_par_defaut, name`. Copier par nom
    # laisserait sans rien un mainteneur qui a renomme son analyseur ou
    # qui en tient un autre par defaut : les fixtures lui poseraient
    # alors un redacteur garni du texte PAR DEFAUT, et ses articles
    # cesseraient d'utiliser son prompt — sans erreur, sans repli, sans
    # un mot.
    # / Copy the one that served, resolved as the code resolved it, not
    # the one bearing the expected name.
    source = AnalyseurSyntaxique.objects.filter(
        is_active=True, type_analyseur="synthetiser",
    ).order_by("-est_par_defaut", "name").first()
    if source is None:
        # Base fraîche : les fixtures créeront le rédacteur après le
        # `migrate`. / Fresh base: the seeding will create it.
        return

    redacteur = AnalyseurSyntaxique.objects.create(
        name=NOM_DE_L_ANALYSEUR_DE_REDACTION,
        description=(
            "Le préambule des ARTICLES : création d'un wiki, synthèse "
            "dirigée de carnet, et mise à jour d'un wiki. Copié le "
            "1er septembre 2026 depuis l'analyseur de synthèse qui "
            "servait déjà ; les deux peuvent désormais diverger."
        ),
        type_analyseur="rediger_un_article",
        is_active=source.is_active,
        inclure_extractions=source.inclure_extractions,
        inclure_texte_original=source.inclure_texte_original,
        est_par_defaut=True,
    )
    # `bulk_create` et pas une boucle de `save()` : le modèle historique
    # n'a de toute façon pas le `save()` custom, et l'ordre des pièces est
    # ce qui fait le prompt.
    # / The historical model has no custom save(); piece order makes the prompt.
    PromptPiece.objects.bulk_create([
        PromptPiece(
            analyseur=redacteur,
            name=piece.name,
            role=piece.role,
            content=piece.content,
            order=piece.order,
        )
        for piece in PromptPiece.objects.filter(
            analyseur=source,
        ).order_by("order")
    ])
    print(
        f"[migration 0038] « {NOM_DE_L_ANALYSEUR_DE_REDACTION} » créé "
        f"depuis « {source.name} » : {redacteur.pieces.count()} "
        f"pièce(s) copiée(s). Les deux préambules sont désormais "
        f"distincts et peuvent diverger."
    )


def retirer_le_redacteur(apps, schema_editor):
    """
    Le retrait n'efface QUE la copie de cette migration.
    / The reverse deletes only this migration's copy.

    Un rédacteur édité depuis, ou créé à la main sous un autre nom, n'est
    pas de son ressort : une migration inverse qui supprimerait tout un
    type effacerait du travail qu'elle n'a pas produit.
    / A reverse that dropped a whole type would erase work it never made.
    """
    AnalyseurSyntaxique = apps.get_model(
        "hypostasis_extractor", "AnalyseurSyntaxique",
    )
    AnalyseurSyntaxique.objects.filter(
        name=NOM_DE_L_ANALYSEUR_DE_REDACTION,
        type_analyseur="rediger_un_article",
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('hypostasis_extractor', '0037_la_provenance_d_une_production'),
    ]

    operations = [
        migrations.AlterField(
            model_name='analyseursyntaxique',
            name='type_analyseur',
            field=models.CharField(choices=[('analyser', 'Analyser'), ('synthetiser', 'Synthétiser'), ('rediger_un_article', 'Rédiger un article')], default='analyser', help_text="Type d'analyseur : analyser, synthetiser ou rediger_un_article / Analyzer type: analyser, synthetiser or rediger_un_article", max_length=20),
        ),
        migrations.RunPython(
            copier_la_synthese_vers_un_redacteur,
            reverse_code=retirer_le_redacteur,
        ),
    ]
