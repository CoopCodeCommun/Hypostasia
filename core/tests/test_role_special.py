"""
La migration qui a estampille les carnets « magiques » historiques.
/ The migration that stamped the historical "magic" notebooks.

LOCALISATION : core/tests/test_role_special.py

SPEC-corpus § 6.3 : « A ranger » et « Mes imports » etaient retrouves par
leur NOM. Un utilisateur qui renommait son carnet cassait les flux qui
s'en servaient. La migration 0042 leur a donc pose un ROLE technique,
independant du nom.

CE FICHIER TESTAIT AUSSI LES DEUX RESOLVEURS, `_resoudre_dossier` et
`_obtenir_ou_creer_dossier_imports`, qui creaient ces carnets a la
demande. Ils ont ete supprimes le 21 aout 2026 avec les fourre-tout
eux-memes : une note appartient toujours a un carnet, et ce carnet est
cree par quelqu'un, jamais par le code. Restent ici les trois tests de
la MIGRATION, qui gardent tout leur sens — les carnets estampilles
existent en base et continuent de vivre comme des carnets ordinaires.
/ This file also tested the two resolvers that created those notebooks
on demand; they were removed on 21 August 2026 along with the catch-alls
themselves. The migration tests remain valid.

Voir CHANGELOG/2026-08-21-une-note-appartient-toujours-a-un-carnet.md
"""

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from core.models import Dossier, RoleSpecialDossier

Utilisateur = get_user_model()

# L'etat de migration JUSTE AVANT celle qui estampille : c'est de la
# qu'on rejoue 0042 pour verifier ce qu'elle fait.
# / The migration state right BEFORE the stamping one.
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
