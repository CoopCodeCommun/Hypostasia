"""
Migration de donnees : les Pages issues d'une synthese passent en
type_de_note=SYNTHESE (SPEC-synthese § 2.1).
/ Data migration: existing synthesis pages get typed SYNTHESE.

LOCALISATION : core/migrations/0047_typer_les_syntheses_existantes.py

Critere de reperage : ExtractionJob.raw_result porte est_synthese=True et
page_synthese_id (front/tasks.py). En repli, parent_page non nul suffit —
c'est aujourd'hui la SEULE ecriture de ce champ en production
(front/tasks.py, versions de synthese). Rien n'est detruit : ni
parent_page, ni extractions, ni commentaires. Reversible (retour a NOTE).
/ Detection via raw_result, fallback parent_page; nothing destroyed.
"""

from django.db import migrations


def typer_les_syntheses(apps, schema_editor):
    """
    Marque SYNTHESE toute page reperee comme production d'une synthese.
    / Marks as SYNTHESE every page produced by a synthesis run.
    """
    Page = apps.get_model("core", "Page")
    ExtractionJob = apps.get_model("hypostasis_extractor", "ExtractionJob")

    # Chemin principal : les jobs de synthese portent page_synthese_id.
    # / Main path: synthesis jobs carry page_synthese_id.
    identifiants_par_raw_result = set()
    jobs_de_synthese = ExtractionJob.objects.filter(
        raw_result__est_synthese=True,
    ).values_list("raw_result", flat=True)
    for resultat in jobs_de_synthese:
        identifiant = (resultat or {}).get("page_synthese_id")
        if identifiant:
            identifiants_par_raw_result.add(identifiant)

    # Repli : toute version (parent_page non nul) est une synthese —
    # seule ecriture de ce champ en production.
    # / Fallback: any version is a synthesis.
    nombre_via_versions = Page.objects.filter(
        parent_page__isnull=False,
    ).update(type_de_note="synthese")
    nombre_via_jobs = Page.objects.filter(
        pk__in=identifiants_par_raw_result,
    ).exclude(type_de_note="synthese").update(type_de_note="synthese")

    print(
        f"\n[migration 0047] syntheses typees : {nombre_via_versions} par "
        f"versionnage + {nombre_via_jobs} par raw_result"
    )


def detyper_les_syntheses(apps, schema_editor):
    """Rollback : tout redevient NOTE. / Rollback: everything back to NOTE."""
    Page = apps.get_model("core", "Page")
    nombre = Page.objects.exclude(type_de_note="note").update(type_de_note="note")
    print(f"\n[migration 0047 rollback] {nombre} page(s) redevenue(s) note")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0046_page_type_de_note"),
        ("hypostasis_extractor", "0033_simplification_element_parent_et_etats"),
    ]

    operations = [
        migrations.RunPython(typer_les_syntheses, reverse_code=detyper_les_syntheses),
    ]
