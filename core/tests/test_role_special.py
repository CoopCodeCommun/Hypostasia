"""
Tests des carnets « magiques » retrouves par role_special (phase A).
/ Tests for "magic" notebooks found by role_special (phase A).

LOCALISATION : core/tests/test_role_special.py

SPEC-corpus § 6.3 : « A ranger » et « Mes imports » etaient retrouves par
get_or_create(name=...). Un utilisateur qui renommait son carnet cassait
ces flux. Les resolveurs filtrent desormais sur role_special ; le nom
n'est plus qu'un affichage.
/ The resolvers now filter on role_special; the name is display only.
"""

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase

from core.models import Dossier, RoleSpecialDossier
from core.views import _resoudre_dossier
from front.views import _obtenir_ou_creer_dossier_imports

Utilisateur = get_user_model()


class ResoudreDossierARangerTest(TestCase):
    """Le resolveur du fourre-tout de l'extension. / The extension's inbox resolver."""

    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            username="capteur_test", password="motdepasse"
        )

    def test_retrouve_le_a_ranger_meme_renomme(self):
        # LE CAS QUI CASSAIT : l'utilisateur a renomme son carnet.
        # Avec la recherche par nom, un nouveau « A ranger » serait cree.
        # / THE BREAKING CASE: the user renamed the notebook. Name-based
        # lookup would create a duplicate.
        fourre_tout_renomme = Dossier.objects.create(
            name="Mon vrac à moi",
            owner=self.utilisateur,
            role_special=RoleSpecialDossier.A_RANGER,
        )

        dossier_resolu = _resoudre_dossier(self.utilisateur, None)

        self.assertEqual(dossier_resolu.pk, fourre_tout_renomme.pk)
        self.assertEqual(
            Dossier.objects.filter(owner=self.utilisateur).count(), 1
        )

    def test_cree_le_a_ranger_avec_son_role(self):
        # Premiere capture d'un utilisateur : le fourre-tout est cree avec
        # son role technique, pas seulement son nom.
        # / First capture: the inbox is created with its technical role.
        dossier_resolu = _resoudre_dossier(self.utilisateur, None)

        self.assertEqual(dossier_resolu.name, "A ranger")
        self.assertEqual(
            dossier_resolu.role_special, RoleSpecialDossier.A_RANGER
        )

    def test_un_carnet_ordinaire_nomme_a_ranger_n_est_pas_confondu(self):
        # Un carnet que l'utilisateur a NOMME « A ranger » sans role
        # technique n'est pas le fourre-tout : le resolveur en cree un vrai.
        # / A notebook merely NAMED "A ranger" is not the inbox.
        homonyme_sans_role = Dossier.objects.create(
            name="A ranger", owner=self.utilisateur,
        )

        dossier_resolu = _resoudre_dossier(self.utilisateur, None)

        self.assertNotEqual(dossier_resolu.pk, homonyme_sans_role.pk)
        self.assertEqual(
            dossier_resolu.role_special, RoleSpecialDossier.A_RANGER
        )


class ObtenirDossierImportsTest(TestCase):
    """Le resolveur de « Mes imports ». / The "Mes imports" resolver."""

    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            username="importeur_test", password="motdepasse"
        )

    def test_retrouve_mes_imports_meme_renomme(self):
        imports_renomme = Dossier.objects.create(
            name="Fichiers déposés",
            owner=self.utilisateur,
            role_special=RoleSpecialDossier.MES_IMPORTS,
        )

        dossier_resolu = _obtenir_ou_creer_dossier_imports(self.utilisateur)

        self.assertEqual(dossier_resolu.pk, imports_renomme.pk)
        self.assertEqual(
            Dossier.objects.filter(owner=self.utilisateur).count(), 1
        )

    def test_cree_mes_imports_avec_son_role(self):
        dossier_resolu = _obtenir_ou_creer_dossier_imports(self.utilisateur)

        self.assertEqual(dossier_resolu.name, "Mes imports")
        self.assertEqual(
            dossier_resolu.role_special, RoleSpecialDossier.MES_IMPORTS
        )


ETAT_AVANT_ESTAMPILLAGE = [("core", "0041_creer_les_appartenances_depuis_la_fk")]
ETAT_APRES_ESTAMPILLAGE = [("core", "0042_estampiller_les_dossiers_speciaux")]


class MigrationEstampillageTest(TransactionTestCase):
    """
    La migration qui pose role_special sur les carnets existants.
    / The migration stamping role_special on existing notebooks.

    Sans elle, la conversion des resolveurs creerait un DOUBLON du
    fourre-tout pour chaque utilisateur existant.
    / Without it, converting the resolvers would duplicate every existing
    user's inbox.
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

    def test_les_dossiers_historiques_sont_estampilles(self):
        apps_avant = self._migrer_vers(ETAT_AVANT_ESTAMPILLAGE)
        UtilisateurHistorique = apps_avant.get_model("auth", "User")
        DossierHistorique = apps_avant.get_model("core", "Dossier")

        proprietaire = UtilisateurHistorique.objects.create(
            username="ancien_utilisateur_test"
        )
        a_ranger = DossierHistorique.objects.create(
            name="A ranger", owner_id=proprietaire.pk,
        )
        mes_imports = DossierHistorique.objects.create(
            name="Mes imports", owner_id=proprietaire.pk,
        )
        carnet_ordinaire = DossierHistorique.objects.create(
            name="Veille", owner_id=proprietaire.pk,
        )
        sans_proprietaire = DossierHistorique.objects.create(
            name="A ranger",
        )

        apps_apres = self._migrer_vers(ETAT_APRES_ESTAMPILLAGE)
        Dossier_apres = apps_apres.get_model("core", "Dossier")

        self.assertEqual(
            Dossier_apres.objects.get(pk=a_ranger.pk).role_special, "a_ranger"
        )
        self.assertEqual(
            Dossier_apres.objects.get(pk=mes_imports.pk).role_special,
            "mes_imports",
        )
        # Un carnet ordinaire et un « A ranger » sans proprietaire ne sont
        # pas touches : impossible de savoir a qui rattacher ce dernier.
        # / Ordinary and ownerless notebooks are left alone.
        self.assertEqual(
            Dossier_apres.objects.get(pk=carnet_ordinaire.pk).role_special, ""
        )
        self.assertEqual(
            Dossier_apres.objects.get(pk=sans_proprietaire.pk).role_special, ""
        )

    def test_la_migration_est_idempotente_sur_une_base_deja_estampillee(self):
        # Retour de relecture (phase A) : si la migration s'arrete apres
        # 0041 et que le nouveau code sert du trafic, un resolveur peut
        # avoir DEJA cree un fourre-tout estampille. Relancer 0042 ne doit
        # pas tenter d'estampiller l'homonyme historique — la contrainte
        # d'unicite exploserait et la migration resterait plantee.
        # / Re-running 0042 on a partially stamped base must not violate
        # the unique constraint.
        apps_avant = self._migrer_vers(ETAT_AVANT_ESTAMPILLAGE)
        UtilisateurHistorique = apps_avant.get_model("auth", "User")
        DossierHistorique = apps_avant.get_model("core", "Dossier")

        proprietaire = UtilisateurHistorique.objects.create(
            username="utilisateur_mi_migre_test"
        )
        # L'historique, jamais estampille. / The historical one, unstamped.
        fourre_tout_historique = DossierHistorique.objects.create(
            name="A ranger", owner_id=proprietaire.pk,
        )
        # Celui que le resolveur a cree entre les deux migrations.
        # / The one the resolver created between the two migrations.
        fourre_tout_du_resolveur = DossierHistorique.objects.create(
            name="Mon vrac", owner_id=proprietaire.pk,
            role_special="a_ranger",
        )

        # Ne doit pas lever. / Must not raise.
        apps_apres = self._migrer_vers(ETAT_APRES_ESTAMPILLAGE)
        Dossier_apres = apps_apres.get_model("core", "Dossier")

        self.assertEqual(
            Dossier_apres.objects.get(pk=fourre_tout_du_resolveur.pk).role_special,
            "a_ranger",
        )
        self.assertEqual(
            Dossier_apres.objects.get(pk=fourre_tout_historique.pk).role_special,
            "",
        )

    def test_les_doublons_historiques_ne_cassent_pas_la_migration(self):
        # Deux carnets nommes « A ranger » chez le meme proprietaire :
        # seul le plus ancien recoit le role, sinon la contrainte
        # d'unicite exploserait.
        # / Two same-named notebooks for one owner: only the oldest gets
        # the role, or the unique constraint would blow up.
        apps_avant = self._migrer_vers(ETAT_AVANT_ESTAMPILLAGE)
        UtilisateurHistorique = apps_avant.get_model("auth", "User")
        DossierHistorique = apps_avant.get_model("core", "Dossier")

        proprietaire = UtilisateurHistorique.objects.create(
            username="collectionneur_test"
        )
        premier = DossierHistorique.objects.create(
            name="A ranger", owner_id=proprietaire.pk,
        )
        second = DossierHistorique.objects.create(
            name="A ranger", owner_id=proprietaire.pk,
        )

        apps_apres = self._migrer_vers(ETAT_APRES_ESTAMPILLAGE)
        Dossier_apres = apps_apres.get_model("core", "Dossier")

        self.assertEqual(
            Dossier_apres.objects.get(pk=premier.pk).role_special, "a_ranger"
        )
        self.assertEqual(
            Dossier_apres.objects.get(pk=second.pk).role_special, ""
        )
