"""
Migration de donnees : cree une AppartenancePageDossier par Page ayant un
dossier (SPEC-corpus § 4.2, migration 2).
/ Data migration: one AppartenancePageDossier per Page with a folder.

LOCALISATION : core/migrations/0041_creer_les_appartenances_depuis_la_fk.py

Passer d'une ForeignKey a une table de liaison est un ELARGISSEMENT PUR :
chaque page a 0 ou 1 dossier, donc devient exactement 0 ou 1 ligne
d'appartenance. Zero information perdue, zero decision par ligne.

REVERSIBLE : le rollback vide la table de liaison. Page.dossier reste en
place et intacte pendant toute la coexistence (le retrait de la FK est la
migration 3, apres recette — pas celle-ci).
/ Reversible: rollback empties the link table; Page.dossier is untouched.
"""

from django.db import migrations


def creer_les_appartenances(apps, schema_editor):
    """
    Pour chaque Page avec dossier_id non nul, cree l'appartenance avec
    la date et l'auteur d'origine.
    / For each Page with a folder, create the membership with the
    original date and author.

    Controle d'integrite obligatoire en fin de migration : le nombre
    d'appartenances creees doit egaler le nombre de pages avec dossier.
    Il n'y a aucune raison legitime qu'ils different — on leve plutot
    que de continuer sur une base incoherente.
    / Mandatory integrity check: counts must match, otherwise raise.
    """
    Page = apps.get_model("core", "Page")
    AppartenancePageDossier = apps.get_model("core", "AppartenancePageDossier")

    pages_avec_dossier = Page.objects.filter(dossier__isnull=False)
    nombre_de_pages_avec_dossier = pages_avec_dossier.count()
    nombre_de_pages_sans_dossier = Page.objects.filter(
        dossier__isnull=True
    ).count()

    # values_list : on ne charge que les 4 champs utiles, jamais les
    # documents complets (html_original et text_readability pesent des
    # centaines de Ko par page — retour de relecture, serveur a 8 Go).
    # / Only the 4 useful fields, never the full documents.
    appartenances_a_creer = [
        AppartenancePageDossier(
            page_id=identifiant_page,
            dossier_id=identifiant_dossier,
            integree_par_id=identifiant_owner,
            # integree_le est ecrivable parce que le champ n'est PAS
            # auto_now_add (spec § 3.2) — c'est sa raison d'etre.
            # / integree_le is writable because the field is NOT
            # auto_now_add.
            integree_le=date_de_creation,
        )
        for identifiant_page, identifiant_dossier, identifiant_owner,
            date_de_creation in pages_avec_dossier.values_list(
                "pk", "dossier_id", "owner_id", "created_at"
            ).iterator()
    ]
    lignes_creees = AppartenancePageDossier.objects.bulk_create(
        appartenances_a_creer, batch_size=500,
    )

    # On compte ce que CETTE migration a cree, pas la table entiere :
    # un comptage global declarerait une fausse incoherence si la table
    # n'etait pas vide (re-run apres --fake, etat partiel).
    # / Count what THIS migration created, not the whole table.
    nombre_d_appartenances_creees = len(lignes_creees)

    print(
        f"\n[migration 0041] pages avec un dossier         : "
        f"{nombre_de_pages_avec_dossier}\n"
        f"                 appartenances creees          : "
        f"{nombre_d_appartenances_creees}\n"
        f"                 pages sans dossier (ignorees) : "
        f"{nombre_de_pages_sans_dossier}"
    )

    if nombre_d_appartenances_creees != nombre_de_pages_avec_dossier:
        raise RuntimeError(
            f"[migration 0041] INCOHERENT : {nombre_de_pages_avec_dossier} "
            f"pages avec dossier mais {nombre_d_appartenances_creees} "
            f"appartenances creees. Migration annulee."
        )
    print("                 -> COHERENT")


def supprimer_les_appartenances(apps, schema_editor):
    """
    Rollback : vide la table de liaison. Page.dossier n'a jamais bouge,
    donc aucune information n'est perdue.
    / Rollback: empty the link table. Page.dossier never moved.
    """
    AppartenancePageDossier = apps.get_model("core", "AppartenancePageDossier")
    nombre_supprime, _detail = AppartenancePageDossier.objects.all().delete()
    print(f"\n[migration 0041 rollback] appartenances supprimees : {nombre_supprime}")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0040_appartenancedossierbase_appartenancepagedossier_and_more"),
    ]

    operations = [
        migrations.RunPython(
            creer_les_appartenances,
            reverse_code=supprimer_les_appartenances,
        ),
    ]
