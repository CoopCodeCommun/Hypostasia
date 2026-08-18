"""
Tests de la table des roles : un modele par usage.
/ Model-per-role table tests.

LOCALISATION : core/tests/test_modeles_par_role.py

Le redacteur d'article et le juge de verification sont deux metiers
opposes : l'un redige long et doit etre bon, l'autre repond
« soutient / ne_soutient_pas » et doit etre petit et peu cher. Tant
qu'un seul champ les porte, un juge specialise est impossible.

CE QUE CES TESTS VERROUILLENT :
- un role SANS ligne retombe sur `Configuration.ai_model` — c'est ce
  repli qui garantit qu'aucun comportement ne change le jour du
  deploiement, avant qu'aucun role ne soit affecte ;
- un role INCONNU leve. Sans cette garde, une faute de frappe dans un
  nom de role retomberait en silence sur le modele generique, et
  personne ne verrait que le juge specialise n'a jamais ete appele ;
- un role est UNIQUE en base : deux modeles pour un meme usage, c'est
  un tirage au sort.
/ A role with no row falls back to Configuration.ai_model; an unknown
role raises (a typo must never silently degrade); one row per role.
"""

from django.db import IntegrityError, transaction
from django.test import TestCase

from core.models import AIModel, Configuration, ModeleParRole, RoleDeModele
from core.services.modeles_par_role import modele_du_role


class RepliSurLaConfigurationTest(TestCase):
    """
    Sans ligne de role, chaque role rend le modele de la Configuration.
    / With no role row, every role yields the Configuration's model.
    """

    def setUp(self):
        self.modele_generique = AIModel.objects.create(
            name="Modèle générique", model_choice="mock",
        )
        configuration = Configuration.get_solo()
        configuration.ai_model = self.modele_generique
        configuration.ai_active = True
        configuration.save()

    def test_le_juge_sans_ligne_retombe_sur_la_configuration(self):
        """Aucune ligne de role : le juge est le modele de la Configuration."""
        self.assertEqual(
            modele_du_role(RoleDeModele.JUGE_DE_VERIFICATION),
            self.modele_generique,
        )

    def test_le_redacteur_sans_ligne_retombe_sur_la_configuration(self):
        """Aucune ligne de role : le redacteur est celui de la Configuration."""
        self.assertEqual(
            modele_du_role(RoleDeModele.REDACTEUR_D_ARTICLE),
            self.modele_generique,
        )

    def test_sans_ligne_ni_configuration_rend_none(self):
        """
        Ni ligne de role ni modele configure : on rend None, on ne leve
        pas. C'est le comportement d'aujourd'hui — la vue stampe un job
        sans modele, et c'est la tache qui echoue avec son message.
        Lever ici transformerait un job en erreur 500 sur l'endpoint.
        / None, not an exception: today's behaviour, preserved.
        """
        configuration = Configuration.get_solo()
        configuration.ai_model = None
        configuration.save()
        self.assertIsNone(modele_du_role(RoleDeModele.JUGE_DE_VERIFICATION))


class LaLigneDeRolePrimeTest(TestCase):
    """
    Une ligne de role prime sur la Configuration, role par role.
    / A role row wins over the Configuration, one role at a time.
    """

    def setUp(self):
        self.modele_generique = AIModel.objects.create(
            name="Modèle générique", model_choice="mock",
        )
        self.petit_juge = AIModel.objects.create(
            name="Petit juge", model_choice="mock",
        )
        configuration = Configuration.get_solo()
        configuration.ai_model = self.modele_generique
        configuration.save()

    def test_le_role_affecte_prime_sur_la_configuration(self):
        """La ligne du juge decide, pas la Configuration."""
        ModeleParRole.objects.create(
            role=RoleDeModele.JUGE_DE_VERIFICATION, modele=self.petit_juge,
        )
        self.assertEqual(
            modele_du_role(RoleDeModele.JUGE_DE_VERIFICATION),
            self.petit_juge,
        )

    def test_affecter_un_role_ne_touche_pas_l_autre(self):
        """
        Affecter le juge laisse le redacteur sur son repli. C'est tout
        l'objet de la table : les deux metiers se reglent separement.
        / Assigning the judge leaves the writer on its fallback.
        """
        ModeleParRole.objects.create(
            role=RoleDeModele.JUGE_DE_VERIFICATION, modele=self.petit_juge,
        )
        self.assertEqual(
            modele_du_role(RoleDeModele.REDACTEUR_D_ARTICLE),
            self.modele_generique,
        )

    def test_deux_roles_peuvent_pointer_deux_modeles_differents(self):
        """Le redacteur et le juge sont deux modeles distincts."""
        ModeleParRole.objects.create(
            role=RoleDeModele.REDACTEUR_D_ARTICLE,
            modele=self.modele_generique,
        )
        ModeleParRole.objects.create(
            role=RoleDeModele.JUGE_DE_VERIFICATION, modele=self.petit_juge,
        )
        self.assertNotEqual(
            modele_du_role(RoleDeModele.REDACTEUR_D_ARTICLE),
            modele_du_role(RoleDeModele.JUGE_DE_VERIFICATION),
        )


class RoleInconnuTest(TestCase):
    """
    Un nom de role inconnu leve, il ne retombe pas.
    / An unknown role name raises; it never falls back.
    """

    def test_un_role_inconnu_leve_et_nomme_le_role(self):
        """
        Une faute de frappe doit se voir. Si elle retombait sur la
        Configuration, le juge specialise ne serait jamais appele et
        rien ne le dirait.
        / A typo must be loud, not a silent fallback.
        """
        with self.assertRaises(ValueError) as contexte:
            modele_du_role("juge_de_verifikation")
        self.assertIn("juge_de_verifikation", str(contexte.exception))


class UniciteDuRoleTest(TestCase):
    """
    Un role ne porte qu'un modele. / One model per role.
    """

    def test_deux_lignes_pour_un_meme_role_sont_refusees(self):
        """
        Deux modeles pour un meme usage, ce serait un tirage au sort a
        chaque appel. / Two models for one role would be a coin toss.
        """
        premier = AIModel.objects.create(name="Premier", model_choice="mock")
        second = AIModel.objects.create(name="Second", model_choice="mock")
        ModeleParRole.objects.create(
            role=RoleDeModele.JUGE_DE_VERIFICATION, modele=premier,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ModeleParRole.objects.create(
                    role=RoleDeModele.JUGE_DE_VERIFICATION, modele=second,
                )


class SuppressionDuModeleAffecteTest(TestCase):
    """
    Supprimer un modele affecte a un role est refuse.
    / Deleting a model bound to a role is refused.
    """

    def test_le_modele_affecte_est_protege(self):
        """
        Sans PROTECT, la suppression emporterait l'affectation en
        silence et le role repartirait sur son repli sans que personne
        ne l'ait decide.
        / Without PROTECT the assignment would vanish silently.
        """
        from django.db.models import ProtectedError

        modele = AIModel.objects.create(name="Juge", model_choice="mock")
        ModeleParRole.objects.create(
            role=RoleDeModele.JUGE_DE_VERIFICATION, modele=modele,
        )
        with self.assertRaises(ProtectedError):
            modele.delete()
