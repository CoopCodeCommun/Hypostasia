"""
Migration de donnees : les pages dont le decoupage est TERMINE (reussi ou
echoue) recoivent ingestion_notification_lue=True.
/ Data migration: pages whose ingestion has FINISHED (succeeded or
failed) get ingestion_notification_lue=True.

LOCALISATION : core/migrations/0058_estampiller_les_ingestions_deja_vues.py

Le champ ajoute en 0057 vaut False par defaut. Sans cette migration,
TOUTES les pages deja ingerees (donc deja vues par leur proprietaire,
bien avant l'existence de ce marqueur) apparaitraient d'un coup comme
des notifications non lues dans le dropdown des taches — un badge
alarmant sur un travail termine depuis longtemps. On estampille donc
l'existant comme deja lu ; seules les ingestions a venir demarreront
non lues. Reversible : le rollback remet tout a False. Bilan chiffre
obligatoire (patron des migrations 0042, 0047, 0050).
/ The field defaults to False; without this migration every already-
ingested page would surface as an unread notification. Stamp the
existing pages as read; only future ingestions start unread.

Restreint a reussie/echouee (revue adverse, tache 8) : en_attente et
en_cours ne sont PAS « deja vues », ce sont des ingestions a mi-parcours
au moment du deploiement — les estampiller aurait eteint leur badge
avant meme que l'utilisateur ait pu voir la fin du cycle. Les valeurs
sont ecrites en dur (reussie/echouee), comme le fait deja la migration
0042 pour ses roles : apps.get_model() ne donne pas acces a
EtatIngestion, et un import direct depuis core.models coupleraient
cette migration figee au code vivant.
/ Restricted to reussie/echouee: en_attente/en_cours are in-flight
ingestions at deploy time, not "already seen" ones.
"""

from django.db import migrations

ETATS_TERMINES = ("reussie", "echouee")


def estampiller_les_ingestions_deja_vues(apps, schema_editor):
    """
    Pose ingestion_notification_lue=True sur toutes les pages dont
    l'ingestion est terminee (reussie ou echouee) — pas celles encore
    en_attente/en_cours.
    / Stamps ingestion_notification_lue=True on every page whose
    ingestion has finished — not the still in-flight ones.
    """
    Page = apps.get_model("core", "Page")

    nombre_estampille = Page.objects.filter(
        ingestion_etat__in=ETATS_TERMINES,
    ).update(ingestion_notification_lue=True)

    print(
        f"\n[migration 0058] ingestions deja vues estampillees : "
        f"{nombre_estampille} page(s)"
    )


def desestampiller_les_ingestions(apps, schema_editor):
    """
    Rollback : remet ingestion_notification_lue a False partout.
    / Rollback: resets ingestion_notification_lue to False everywhere.
    """
    Page = apps.get_model("core", "Page")
    nombre = Page.objects.filter(
        ingestion_etat__in=ETATS_TERMINES,
    ).update(ingestion_notification_lue=False)
    print(f"\n[migration 0058 rollback] {nombre} estampille(s) retiree(s)")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0057_page_ingestion_notification_lue"),
    ]

    operations = [
        migrations.RunPython(
            estampiller_les_ingestions_deja_vues,
            reverse_code=desestampiller_les_ingestions,
        ),
    ]
