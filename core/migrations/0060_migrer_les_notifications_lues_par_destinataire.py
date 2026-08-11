"""
Migration de donnees : reprend les trois booleens partages
(ExtractionJob.notification_lue, TranscriptionJob.notification_lue,
Page.ingestion_notification_lue) deja a True et cree les lignes
NotificationTacheLue equivalentes pour CHAQUE destinataire — le
proprietaire de la note ET les proprietaires des carnets qui la
contiennent.
/ Data migration: backfills the three legacy shared booleans already
True into per-recipient NotificationTacheLue rows, for the note owner
AND the owners of any containing notebook.

LOCALISATION : core/migrations/0060_migrer_les_notifications_lues_par_destinataire.py

Correction 1 (revue de cloture du 11 aout 2026, tache "drapeau par
destinataire"). CORRIGE apres relecture (meme jour) : la version
initiale de cette migration attribuait chaque booleen a True au seul
PROPRIETAIRE DE LA NOTE, en partant du principe qu'avant l'elargissement
du perimetre de lecture, lui seul pouvait avoir clique "marquer lue".
FAUX — verifie sur `core/migrations/0032` (`ExtractionJob.objects.
update(notification_lue=True)`, TOUS les jobs, sans destinataire) et
`core/migrations/0058` (meme estampillage en masse sur toutes les
ingestions terminees) : ces booleens ne temoignent PAS d'un clic d'un
destinataire precis, ce sont des estampillages en masse poses
precisement pour EVITER qu'un compteur enorme s'allume au deploiement.
Attribuer False uniquement a l'auteur de la note aurait fait
apparaitre au proprietaire d'un carnet, au premier chargement, tout
l'historique de son carnet comme "non lu" — le meme compteur enorme
que 0032/0058 existaient pour eviter, ressuscite par cette correction.

La regle retenue est donc desormais IDENTIQUE a
`_destinataires_de_notification` (`front/tasks.py:50`) — proprietaire
de la note PLUS proprietaires des carnets qui la contiennent — la
meme notion que `_filtre_proprietaire_page` reproduit cote lecture
(front/views.py). Les trois doivent parler du meme ensemble de
personnes.

Cout : 2 requetes SELECT par type (une via `page__owner`, une via
`page__appartenances_dossiers__dossier__owner`, jointure bornee, pas
une requete par tache) + 1 requete de comptage "sans destinataire" par
type, puis UN SEUL bulk_create() pour toutes les lignes calculees.
Aucune boucle Python n'emet de requete par tache.

Patron des migrations 0042, 0047, 0050, 0058 : bilan chiffre imprime,
reversible. Le rollback recalcule EXACTEMENT le meme ensemble de
triples (utilisateur, type_tache, tache_id) et ne supprime que CEUX-LA
— jamais un DELETE total de la table, qui effacerait aussi des lectures
reelles posees apres cette migration.
/ Follows the 0042/0047/0050/0058 pattern. Rollback recomputes the
exact same triple set and deletes only those — never a blanket delete.
"""

from django.db import migrations
from django.db.models import Q


def _calculer_les_triples_a_migrer(apps):
    """
    Calcule l'ensemble des triples (type_tache, tache_id, utilisateur_id)
    que cette migration doit creer — et donc, au retour arriere,
    exactement ce qu'elle doit supprimer. Partagee entre forward et
    reverse pour que les deux parlent du MEME ensemble.
    / Computes the exact triple set to create — and, on rollback, to
    delete. Shared between forward and reverse so both agree.

    Un `set()` Python deduplique le cas ou un meme utilisateur est a la
    fois proprietaire de la note ET d'un carnet qui la contient.
    / A Python set dedupes the case where the same user is both note
    owner and containing-notebook owner.
    """
    ExtractionJob = apps.get_model("hypostasis_extractor", "ExtractionJob")
    TranscriptionJob = apps.get_model("core", "TranscriptionJob")
    Page = apps.get_model("core", "Page")

    triples = set()

    # --- extraction : ExtractionJob.page a un owner et/ou des carnets ---
    for tache_id, utilisateur_id in ExtractionJob.objects.filter(
        notification_lue=True, page__owner__isnull=False,
    ).values_list("pk", "page__owner_id"):
        triples.add(("extraction", tache_id, utilisateur_id))
    for tache_id, utilisateur_id in ExtractionJob.objects.filter(
        notification_lue=True,
        page__appartenances_dossiers__dossier__owner__isnull=False,
    ).values_list(
        "pk", "page__appartenances_dossiers__dossier__owner_id",
    ):
        triples.add(("extraction", tache_id, utilisateur_id))

    # --- transcription : meme logique via TranscriptionJob.page ---
    for tache_id, utilisateur_id in TranscriptionJob.objects.filter(
        notification_lue=True, page__owner__isnull=False,
    ).values_list("pk", "page__owner_id"):
        triples.add(("transcription", tache_id, utilisateur_id))
    for tache_id, utilisateur_id in TranscriptionJob.objects.filter(
        notification_lue=True,
        page__appartenances_dossiers__dossier__owner__isnull=False,
    ).values_list(
        "pk", "page__appartenances_dossiers__dossier__owner_id",
    ):
        triples.add(("transcription", tache_id, utilisateur_id))

    # --- ingestion : la Page EST la tache, pas de job intermediaire ---
    for tache_id, utilisateur_id in Page.objects.filter(
        ingestion_notification_lue=True, owner__isnull=False,
    ).values_list("pk", "owner_id"):
        triples.add(("ingestion", tache_id, utilisateur_id))
    for tache_id, utilisateur_id in Page.objects.filter(
        ingestion_notification_lue=True,
        appartenances_dossiers__dossier__owner__isnull=False,
    ).values_list(
        "pk", "appartenances_dossiers__dossier__owner_id",
    ):
        triples.add(("ingestion", tache_id, utilisateur_id))

    return triples


def migrer_les_notifications_lues(apps, schema_editor):
    """
    Cree une ligne NotificationTacheLue par (type, tache, destinataire)
    deja lu — un seul bulk_create, aucune requete par tache.
    / Creates one NotificationTacheLue row per already-read
    (type, task, recipient) — a single bulk_create, no per-task query.
    """
    ExtractionJob = apps.get_model("hypostasis_extractor", "ExtractionJob")
    TranscriptionJob = apps.get_model("core", "TranscriptionJob")
    Page = apps.get_model("core", "Page")
    NotificationTacheLue = apps.get_model("core", "NotificationTacheLue")

    triples = _calculer_les_triples_a_migrer(apps)

    NotificationTacheLue.objects.bulk_create(
        [
            NotificationTacheLue(
                utilisateur_id=utilisateur_id, type_tache=type_tache,
                tache_id=tache_id,
            )
            for (type_tache, tache_id, utilisateur_id) in triples
        ],
        ignore_conflicts=True,
    )

    # Bilan par type : lignes creees (destinataires distincts touches)
    # + taches sans AUCUN destinataire (ni owner, ni carnet possede) —
    # celles-la restent legitimement sans ligne, personne a qui
    # attribuer la lecture. / Per-type tally, plus tasks with nobody
    # to attribute the read to.
    ids_extraction_couverts = {
        tid for (t, tid, _u) in triples if t == "extraction"
    }
    ids_transcription_couverts = {
        tid for (t, tid, _u) in triples if t == "transcription"
    }
    ids_ingestion_couverts = {
        tid for (t, tid, _u) in triples if t == "ingestion"
    }

    nombre_extractions_sans_destinataire = ExtractionJob.objects.filter(
        notification_lue=True,
    ).exclude(pk__in=ids_extraction_couverts).count()
    nombre_transcriptions_sans_destinataire = TranscriptionJob.objects.filter(
        notification_lue=True,
    ).exclude(pk__in=ids_transcription_couverts).count()
    nombre_ingestions_sans_destinataire = Page.objects.filter(
        ingestion_notification_lue=True,
    ).exclude(pk__in=ids_ingestion_couverts).count()

    print(
        f"\n[migration 0060] notifications lues migrees par destinataire "
        f"(note + carnets contenants) :\n"
        f"  extraction    : {len(ids_extraction_couverts)} tache(s) couverte(s), "
        f"{nombre_extractions_sans_destinataire} sans destinataire\n"
        f"  transcription : {len(ids_transcription_couverts)} tache(s) couverte(s), "
        f"{nombre_transcriptions_sans_destinataire} sans destinataire\n"
        f"  ingestion     : {len(ids_ingestion_couverts)} tache(s) couverte(s), "
        f"{nombre_ingestions_sans_destinataire} sans destinataire\n"
        f"  total lignes NotificationTacheLue creees : {len(triples)}"
    )


def retirer_les_notifications_migrees(apps, schema_editor):
    """
    Rollback : recalcule le MEME ensemble de triples et ne supprime que
    ceux-la — une ligne posee par une lecture reelle posterieure a
    cette migration, sur un couple different, n'est jamais touchee.
    / Rollback: recomputes the same triple set and deletes only that —
    a real post-migration read on a different triple survives.
    """
    NotificationTacheLue = apps.get_model("core", "NotificationTacheLue")
    triples = _calculer_les_triples_a_migrer(apps)

    # Regroupe par type pour limiter a UNE requete DELETE par type
    # (grand OR de paires tache/utilisateur), pas une requete par
    # triple. / Grouped by type: one DELETE per type (a big OR of
    # task/user pairs), not one query per triple.
    paires_par_type = {}
    for type_tache, tache_id, utilisateur_id in triples:
        paires_par_type.setdefault(type_tache, []).append(
            (tache_id, utilisateur_id),
        )

    nombre_total_supprime = 0
    for type_tache, paires in paires_par_type.items():
        condition = Q()
        for tache_id, utilisateur_id in paires:
            condition |= Q(tache_id=tache_id, utilisateur_id=utilisateur_id)
        nombre_supprime, _detail = NotificationTacheLue.objects.filter(
            type_tache=type_tache,
        ).filter(condition).delete()
        nombre_total_supprime += nombre_supprime

    print(f"\n[migration 0060 rollback] {nombre_total_supprime} ligne(s) supprimee(s)")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0059_creer_notification_tache_lue"),
        ("hypostasis_extractor", "0033_simplification_element_parent_et_etats"),
    ]

    operations = [
        migrations.RunPython(
            migrer_les_notifications_lues,
            reverse_code=retirer_les_notifications_migrees,
        ),
    ]
