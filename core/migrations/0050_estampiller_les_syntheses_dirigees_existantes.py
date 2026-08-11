"""
Migration de donnees : chaque page deja typee SYNTHESE recoit son
enregistrement SyntheseDirigee (SPEC-synthese § 13, phase C).
/ Data migration: every SYNTHESE-typed page gets its SyntheseDirigee row.

LOCALISATION : core/migrations/0050_estampiller_les_syntheses_dirigees_existantes.py

Les syntheses historiques etaient des VERSIONS de page : leur perimetre
reel etait la note racine (parent_page), leur date de production le
created_at de la page, leur carnet la FK dossier. On fige exactement ces
faits-la — rien n'est invente, rien n'est detruit. Reversible : le
rollback supprime les enregistrements (la table meurt de toute facon au
rollback de 0049 qui suit). Bilan chiffre obligatoire.
/ Historical syntheses were page versions: freeze exactly those facts.
"""

from django.db import migrations


def estampiller_les_dirigees(apps, schema_editor):
    """
    Cree un SyntheseDirigee par page typee SYNTHESE qui n'en a pas.
    / One SyntheseDirigee per SYNTHESE-typed page lacking one.
    """
    Page = apps.get_model("core", "Page")
    SyntheseDirigee = apps.get_model("core", "SyntheseDirigee")

    pages_de_synthese = Page.objects.filter(type_de_note="synthese").exclude(
        synthese_dirigee__isnull=False,
    )

    nombre_crees = 0
    nombre_avec_perimetre = 0
    nombre_sans_carnet = 0
    for page in pages_de_synthese.iterator():
        # Le carnet : la FK « premier carnet », et a defaut la premiere
        # appartenance (depuis la phase D corpus, la FK peut etre NULL
        # alors que la note appartient a des carnets).
        # / The notebook: the FK, else the first membership.
        identifiant_de_carnet = page.dossier_id
        if identifiant_de_carnet is None:
            premiere_appartenance = page.appartenances_dossiers.order_by(
                "integree_le",
            ).first()
            if premiere_appartenance is not None:
                identifiant_de_carnet = premiere_appartenance.dossier_id

        enregistrement = SyntheseDirigee.objects.create(
            page=page,
            dossier_id=identifiant_de_carnet,
            produite_le=page.created_at,
            produite_par_id=page.owner_id,
        )
        # Le perimetre historique : la note dont elle etait la version.
        # parent_page pointe toujours la racine (front/tasks.py).
        # / Historical scope: the root note it versioned.
        if page.parent_page_id is not None:
            enregistrement.notes_du_perimetre.add(page.parent_page_id)
            nombre_avec_perimetre += 1
        if identifiant_de_carnet is None:
            nombre_sans_carnet += 1
        nombre_crees += 1

    print(
        f"\n[migration 0050] syntheses dirigees estampillees : {nombre_crees} "
        f"({nombre_avec_perimetre} avec perimetre racine, "
        f"{nombre_sans_carnet} sans carnet)"
    )


def desestampiller_les_dirigees(apps, schema_editor):
    """
    Rollback : ne supprime QUE ce que la migration a cree — les
    syntheses historiques etaient des versions (parent_page non nul) ;
    une dirigee nee de l'application (phase C, sans parent) survit.
    Le compteur affiche est celui de la table elle-meme, pas le total
    cascade (relecture C, M1/M2).
    / Deletes only migration-created rows; app-born records survive.
    """
    SyntheseDirigee = apps.get_model("core", "SyntheseDirigee")
    _total, details = SyntheseDirigee.objects.filter(
        page__parent_page__isnull=False,
    ).delete()
    nombre = details.get("core.SyntheseDirigee", 0)
    print(f"\n[migration 0050 rollback] {nombre} enregistrement(s) supprime(s)")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0049_wiki_et_synthese_dirigee"),
    ]

    operations = [
        migrations.RunPython(
            estampiller_les_dirigees,
            reverse_code=desestampiller_les_dirigees,
        ),
    ]
