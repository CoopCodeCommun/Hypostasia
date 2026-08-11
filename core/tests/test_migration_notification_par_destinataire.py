"""
Migration 0060 — reprise des booleens partages "notification_lue" en
lignes NotificationTacheLue par destinataire.
/ Migration 0060 — backfilling the legacy shared "notification_lue"
booleans into per-recipient NotificationTacheLue rows.

LOCALISATION : core/tests/test_migration_notification_par_destinataire.py

Corrige une premisse fausse decouverte en relecture : la version
initiale de 0060 attribuait chaque booleen a True au seul PROPRIETAIRE
DE LA NOTE, en supposant que lui seul avait pu le poser. Faux — voir
`core/migrations/0032` et `0058` : ces booleens sont des estampillages
en MASSE (`.update(notification_lue=True)` sur TOUS les jobs, sans
distinction de destinataire), poses precisement pour eviter qu'un
compteur enorme s'allume au deploiement. Ce test simule ce cas —
booleen a True sans qu'aucun clic n'ait jamais eu lieu — et verifie
que la migration attribue la lecture a la fois au proprietaire de la
note ET au proprietaire d'un carnet qui la contient (meme ensemble que
`_destinataires_de_notification`, front/tasks.py).
"""

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

User = get_user_model()

ETAT_AVANT_MIGRATION_0060 = [("core", "0059_creer_notification_tache_lue")]
ETAT_APRES_MIGRATION_0060 = [
    ("core", "0060_migrer_les_notifications_lues_par_destinataire"),
]


class MigrationNotificationParDestinataireTest(TransactionTestCase):
    """
    La migration de donnees 0060.
    / The 0060 data migration.
    """

    def _migrer_vers(self, cibles):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(cibles)
        return executor.loader.project_state(cibles).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def _construire_le_jeu_de_donnees_historique(self, apps_avant):
        """
        Reproduit un estampillage en MASSE (patron 0032/0058) : les
        trois booleens sont a True sans qu'aucun destinataire precis
        n'ait clique — c'est la premisse a corriger. La note appartient
        a `auteur` ET est rangee dans un carnet possede par `prof`.
        / Reproduces a MASS stamp: the booleens are True with no real
        clicker. The note is owned by `auteur` AND filed in a notebook
        owned by `prof`.
        """
        UtilisateurHistorique = apps_avant.get_model("auth", "User")
        Page = apps_avant.get_model("core", "Page")
        Dossier = apps_avant.get_model("core", "Dossier")
        AppartenancePageDossier = apps_avant.get_model(
            "core", "AppartenancePageDossier",
        )
        ExtractionJob = apps_avant.get_model(
            "hypostasis_extractor", "ExtractionJob",
        )
        TranscriptionJob = apps_avant.get_model("core", "TranscriptionJob")

        auteur = UtilisateurHistorique.objects.create(
            username="auteur-migration-0060",
        )
        prof = UtilisateurHistorique.objects.create(
            username="prof-migration-0060",
        )
        carnet = Dossier.objects.create(
            name="Carnet migration 0060", owner_id=prof.pk,
        )
        page = Page.objects.create(
            title="Note historique", source_type="file",
            html_original="", html_readability="", text_readability="",
            content_hash="hash-migration-0060", owner_id=auteur.pk,
            ingestion_etat="reussie", ingestion_notification_lue=True,
        )
        AppartenancePageDossier.objects.create(page_id=page.pk, dossier_id=carnet.pk)

        job_extraction = ExtractionJob.objects.create(
            page_id=page.pk, name="Analyse historique",
            prompt_description="extraire", notification_lue=True,
        )
        job_transcription = TranscriptionJob.objects.create(
            page_id=page.pk, notification_lue=True,
        )

        return {
            "auteur": auteur, "prof": prof, "page": page,
            "job_extraction": job_extraction,
            "job_transcription": job_transcription,
        }

    def test_le_proprietaire_de_la_note_et_celui_du_carnet_sont_tous_deux_migres(self):
        apps_avant = self._migrer_vers(ETAT_AVANT_MIGRATION_0060)
        donnees = self._construire_le_jeu_de_donnees_historique(apps_avant)

        apps_apres = self._migrer_vers(ETAT_APRES_MIGRATION_0060)
        NotificationTacheLue = apps_apres.get_model("core", "NotificationTacheLue")

        for type_tache, tache_id in (
            ("extraction", donnees["job_extraction"].pk),
            ("transcription", donnees["job_transcription"].pk),
            ("ingestion", donnees["page"].pk),
        ):
            with self.subTest(type_tache=type_tache):
                self.assertTrue(
                    NotificationTacheLue.objects.filter(
                        utilisateur_id=donnees["auteur"].pk,
                        type_tache=type_tache, tache_id=tache_id,
                    ).exists(),
                    f"le proprietaire de la note n'a pas ete migre pour {type_tache}",
                )
                self.assertTrue(
                    NotificationTacheLue.objects.filter(
                        utilisateur_id=donnees["prof"].pk,
                        type_tache=type_tache, tache_id=tache_id,
                    ).exists(),
                    f"le proprietaire du carnet n'a pas ete migre pour {type_tache}",
                )

    def test_une_page_sans_owner_ni_carnet_possede_n_est_pas_migree(self):
        # Personne a qui attribuer la lecture : aucune ligne creee, et
        # aucune erreur. / Nobody to attribute the read to: no row, no
        # crash.
        apps_avant = self._migrer_vers(ETAT_AVANT_MIGRATION_0060)
        Page = apps_avant.get_model("core", "Page")
        page_orpheline = Page.objects.create(
            title="Orpheline", source_type="file",
            html_original="", html_readability="", text_readability="",
            content_hash="hash-orpheline-0060",
            ingestion_etat="reussie", ingestion_notification_lue=True,
        )

        apps_apres = self._migrer_vers(ETAT_APRES_MIGRATION_0060)
        NotificationTacheLue = apps_apres.get_model("core", "NotificationTacheLue")

        self.assertFalse(
            NotificationTacheLue.objects.filter(
                type_tache="ingestion", tache_id=page_orpheline.pk,
            ).exists()
        )

    def test_le_rollback_ne_supprime_que_ce_qu_il_a_cree(self):
        # Le defaut signale : un .all().delete() effacerait aussi une
        # lecture REELLE posee apres la migration, sur un couple sans
        # rapport. / The reported defect: a blanket delete would also
        # wipe an unrelated real read created after the migration.
        apps_avant = self._migrer_vers(ETAT_AVANT_MIGRATION_0060)
        donnees = self._construire_le_jeu_de_donnees_historique(apps_avant)

        apps_apres = self._migrer_vers(ETAT_APRES_MIGRATION_0060)
        NotificationTacheLue = apps_apres.get_model("core", "NotificationTacheLue")
        UtilisateurApres = apps_apres.get_model("auth", "User")

        tiers = UtilisateurApres.objects.create(username="tiers-migration-0060")
        ligne_reelle_posterieure = NotificationTacheLue.objects.create(
            utilisateur_id=tiers.pk, type_tache="ingestion", tache_id=999999,
        )

        # Redescend a l'etat AVANT-0060 : la table existe toujours (creee
        # en 0059), seules les lignes posees par 0060 doivent disparaitre.
        # / Rolls back to pre-0060: the table still exists (created in
        # 0059), only 0060's own rows should vanish.
        apps_avant_de_nouveau = self._migrer_vers(ETAT_AVANT_MIGRATION_0060)
        NotificationTacheLue_avant = apps_avant_de_nouveau.get_model(
            "core", "NotificationTacheLue",
        )

        # La ligne reelle, posterieure, a survecu.
        # / The real, later row survived.
        self.assertTrue(
            NotificationTacheLue_avant.objects.filter(
                pk=ligne_reelle_posterieure.pk,
            ).exists()
        )
        # Les lignes creees par la migration ont disparu.
        # / The migration-created rows are gone.
        self.assertFalse(
            NotificationTacheLue_avant.objects.filter(
                utilisateur_id=donnees["auteur"].pk,
                type_tache="extraction", tache_id=donnees["job_extraction"].pk,
            ).exists()
        )
        self.assertFalse(
            NotificationTacheLue_avant.objects.filter(
                utilisateur_id=donnees["prof"].pk,
                type_tache="ingestion", tache_id=donnees["page"].pk,
            ).exists()
        )
