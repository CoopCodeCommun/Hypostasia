"""
Tests de la migration de donnees FK -> appartenances (phase A).
/ Data migration tests, FK -> memberships (phase A).

LOCALISATION : core/tests/test_corpus_migration.py

SPEC-corpus § 4.2, migration 2 : pour chaque Page dont dossier_id est non
nul, creer une AppartenancePageDossier(page, dossier,
integree_par=page.owner, integree_le=page.created_at). La migration est
REVERSIBLE : le rollback vide la table et laisse Page.dossier intacte.

Ces tests pilotent le MigrationExecutor : on redescend a l'etat d'avant la
migration, on cree des donnees avec les modeles historiques, on applique,
on verifie. C'est plus lourd qu'un test de modele, mais c'est le seul moyen
d'exercer la vraie migration — pas une reimplementation.
/ These tests drive the real migration through MigrationExecutor.
"""

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


ETAT_AVANT = [("core", "0040_appartenancedossierbase_appartenancepagedossier_and_more")]
ETAT_APRES = [("core", "0041_creer_les_appartenances_depuis_la_fk")]


class MigrationDesAppartenancesTest(TransactionTestCase):
    """Exerce la migration 0041 dans les deux sens. / Exercises 0041 both ways."""

    def _migrer_vers(self, cibles):
        """
        Applique les migrations jusqu'a l'etat demande et retourne les
        modeles historiques de cet etat.
        / Migrates to the requested state and returns its historical models.
        """
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(cibles)
        return executor.loader.project_state(cibles).apps

    def tearDown(self):
        # Toujours remonter a l'etat le plus recent, sinon les classes de
        # tests suivantes travailleraient sur un schema perime.
        # / Always migrate back to the latest state for the next tests.
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def _creer_le_jeu_de_donnees(self, apps_historiques):
        """
        Deux pages avec dossier, une page sans dossier.
        / Two pages with a folder, one page without.
        """
        Utilisateur = apps_historiques.get_model("auth", "User")
        Dossier = apps_historiques.get_model("core", "Dossier")
        Page = apps_historiques.get_model("core", "Page")

        proprietaire = Utilisateur.objects.create(username="migrateur_test")
        dossier = Dossier.objects.create(name="Carnet migre", owner_id=proprietaire.pk)

        page_avec_dossier = Page.objects.create(
            url="http://exemple.local/page-migree-1",
            html_original="<p>o</p>",
            html_readability="<p>l</p>",
            text_readability="texte",
            content_hash="hash-migration-1",
            dossier_id=dossier.pk,
            owner_id=proprietaire.pk,
        )
        page_avec_dossier_sans_owner = Page.objects.create(
            url="http://exemple.local/page-migree-2",
            html_original="<p>o</p>",
            html_readability="<p>l</p>",
            text_readability="texte",
            content_hash="hash-migration-2",
            dossier_id=dossier.pk,
        )
        page_sans_dossier = Page.objects.create(
            url="http://exemple.local/page-sans-dossier",
            html_original="<p>o</p>",
            html_readability="<p>l</p>",
            text_readability="texte",
            content_hash="hash-migration-3",
        )
        return {
            "proprietaire": proprietaire,
            "dossier": dossier,
            "page_avec_dossier": page_avec_dossier,
            "page_avec_dossier_sans_owner": page_avec_dossier_sans_owner,
            "page_sans_dossier": page_sans_dossier,
        }

    def test_migration_cree_une_appartenance_par_page(self):
        apps_avant = self._migrer_vers(ETAT_AVANT)
        jeu = self._creer_le_jeu_de_donnees(apps_avant)

        apps_apres = self._migrer_vers(ETAT_APRES)
        Appartenance = apps_apres.get_model("core", "AppartenancePageDossier")

        # Deux pages avec dossier -> deux appartenances. La page sans
        # dossier n'en produit aucune.
        # / Two pages with a folder -> two memberships; none for the third.
        self.assertEqual(Appartenance.objects.count(), 2)
        appartenance = Appartenance.objects.get(
            page_id=jeu["page_avec_dossier"].pk
        )
        self.assertEqual(appartenance.dossier_id, jeu["dossier"].pk)
        self.assertEqual(appartenance.integree_par_id, jeu["proprietaire"].pk)

        appartenance_sans_owner = Appartenance.objects.get(
            page_id=jeu["page_avec_dossier_sans_owner"].pk
        )
        self.assertIsNone(appartenance_sans_owner.integree_par_id)
        self.assertFalse(
            Appartenance.objects.filter(
                page_id=jeu["page_sans_dossier"].pk
            ).exists()
        )

    def test_migration_preserve_la_date_d_origine(self):
        # integree_le doit valoir page.created_at, pas la date de la
        # migration — c'est la raison d'etre du default=timezone.now
        # (au lieu d'auto_now_add) sur le champ.
        # / integree_le must equal page.created_at, not migration time.
        apps_avant = self._migrer_vers(ETAT_AVANT)
        jeu = self._creer_le_jeu_de_donnees(apps_avant)
        date_de_creation_d_origine = jeu["page_avec_dossier"].created_at

        apps_apres = self._migrer_vers(ETAT_APRES)
        Appartenance = apps_apres.get_model("core", "AppartenancePageDossier")

        appartenance = Appartenance.objects.get(
            page_id=jeu["page_avec_dossier"].pk
        )
        self.assertEqual(appartenance.integree_le, date_de_creation_d_origine)

    def test_le_controle_d_integrite_compte_les_lignes_creees_pas_la_table(self):
        # Retour de relecture (phase A) : si la table n'est pas vide au
        # moment de la migration (re-run apres --fake, etat partiel), un
        # comptage GLOBAL declarerait une fausse incoherence. Le controle
        # doit compter ce que la migration a cree, rien d'autre.
        # / The integrity check must count created rows, not the whole table.
        apps_avant = self._migrer_vers(ETAT_AVANT)
        jeu = self._creer_le_jeu_de_donnees(apps_avant)

        Appartenance_avant = apps_avant.get_model(
            "core", "AppartenancePageDossier"
        )
        # Une ligne preexistante, posee a la main sur la page sans dossier.
        # / A pre-existing row, on the folderless page.
        Appartenance_avant.objects.create(
            page_id=jeu["page_sans_dossier"].pk,
            dossier_id=jeu["dossier"].pk,
        )

        # La migration ne doit PAS lever : elle cree 2 lignes pour les
        # 2 pages avec dossier, et la ligne preexistante ne fausse rien.
        # / The migration must NOT raise.
        apps_apres = self._migrer_vers(ETAT_APRES)
        Appartenance = apps_apres.get_model("core", "AppartenancePageDossier")
        self.assertEqual(Appartenance.objects.count(), 3)

    def test_migration_est_reversible(self):
        apps_avant = self._migrer_vers(ETAT_AVANT)
        jeu = self._creer_le_jeu_de_donnees(apps_avant)

        self._migrer_vers(ETAT_APRES)
        apps_retour = self._migrer_vers(ETAT_AVANT)

        Appartenance = apps_retour.get_model("core", "AppartenancePageDossier")
        Page = apps_retour.get_model("core", "Page")

        # Rollback : table de liaison vide, FK Page.dossier intacte.
        # / Rollback: empty link table, Page.dossier FK untouched.
        self.assertEqual(Appartenance.objects.count(), 0)
        page_relue = Page.objects.get(pk=jeu["page_avec_dossier"].pk)
        self.assertEqual(page_relue.dossier_id, jeu["dossier"].pk)
