"""
Tests de la commande d'affectation d'un modele a un role.
/ Tests of the role-assignment command.

LOCALISATION : front/tests/test_affectation_d_un_modele_a_un_role.py

C'est le SEUL levier pour choisir un juge : l'admin Django est desactive
et l'ecran de configuration IA ne sait poser qu'un modele, celui de la
`Configuration`.

CE QUE CES TESTS VERROUILLENT :
- un modele cree pour un role nait `is_active=False`. L'ecran de
  configuration IA propose au clic tout modele ACTIF et le pose dans
  `Configuration.ai_model`, qui est le modele d'EXTRACTION — or
  LangExtract ne sait pas piloter une plateforme compatible OpenAI. Un
  modele de role laisse actif eteindrait l'extraction d'un seul clic ;
- un role affecte a un modele inactif fonctionne quand meme :
  `modele_du_role` ne filtre pas sur `is_active`, et c'est voulu ;
- la cle API n'est JAMAIS ecrite en base : seule la variable est nommee ;
- retirer une affectation rend le role a son repli, sans rien casser.
/ A role model is created inactive so it can never be clicked into the
extraction slot; the resolver ignores is_active on purpose; the key
itself is never stored.
"""

from io import StringIO
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import TestCase

from core.models import (
    AIModel, Configuration, ModeleParRole, Provider, RoleDeModele,
)
from core.services.modeles_par_role import modele_du_role


class AffectationParPlateformeTest(TestCase):
    """Creer et affecter un modele servi par une API compatible."""

    def setUp(self):
        self.modele_de_la_configuration = AIModel.objects.create(
            name="Modèle générique", model_choice="mock", is_active=True,
        )
        configuration = Configuration.get_solo()
        configuration.ai_model = self.modele_de_la_configuration
        configuration.ai_active = True
        configuration.save()

    def _affecter_le_juge(self):
        sortie = StringIO()
        with patch.dict(
            "os.environ", {"OPENROUTER_API_KEY": "cle-de-test"},
        ):
            call_command(
                "affecter_un_modele_a_un_role",
                role=RoleDeModele.JUGE_DE_VERIFICATION,
                plateforme="https://openrouter.ai/api/v1",
                modele_technique="mistralai/mistral-small-3.2-24b-instruct",
                variable_de_cle="OPENROUTER_API_KEY",
                stdout=sortie,
            )
        return sortie.getvalue()

    def test_le_modele_est_cree_et_affecte_au_role(self):
        """Une seule commande crée le modèle et le pose sur le rôle."""
        self._affecter_le_juge()

        juge = modele_du_role(RoleDeModele.JUGE_DE_VERIFICATION)
        self.assertEqual(
            juge.technical_model_name,
            "mistralai/mistral-small-3.2-24b-instruct",
        )
        self.assertEqual(juge.provider, Provider.COMPATIBLE_OPENAI)
        self.assertEqual(juge.base_url, "https://openrouter.ai/api/v1")

    def test_le_modele_de_role_nait_inactif(self):
        """
        Un modèle actif est proposable dans l'écran de configuration IA,
        qui pose le modèle d'EXTRACTION. Un modèle de plateforme y
        éteindrait l'extraction d'un clic.
        """
        self._affecter_le_juge()

        juge = modele_du_role(RoleDeModele.JUGE_DE_VERIFICATION)
        self.assertFalse(juge.is_active)
        self.assertNotIn(
            juge, list(AIModel.objects.filter(is_active=True)),
        )

    def test_le_role_fonctionne_avec_un_modele_inactif(self):
        """
        `modele_du_role` ne filtre pas sur `is_active` : « inactif » veut
        dire « pas proposable au choix », pas « inutilisable ».
        """
        self._affecter_le_juge()

        self.assertIsNotNone(
            modele_du_role(RoleDeModele.JUGE_DE_VERIFICATION),
        )

    def test_la_cle_api_n_est_jamais_ecrite_en_base(self):
        """Seul le NOM de la variable est stocké."""
        self._affecter_le_juge()

        juge = modele_du_role(RoleDeModele.JUGE_DE_VERIFICATION)
        self.assertEqual(juge.variable_de_cle_api, "OPENROUTER_API_KEY")
        valeurs_en_base = " ".join(
            str(valeur) for valeur in AIModel.objects.filter(
                pk=juge.pk,
            ).values()[0].values()
        )
        self.assertNotIn("cle-de-test", valeurs_en_base)

    def test_le_redacteur_reste_sur_son_repli(self):
        """Affecter le juge ne touche pas au rédacteur."""
        self._affecter_le_juge()

        self.assertEqual(
            modele_du_role(RoleDeModele.REDACTEUR_D_ARTICLE),
            self.modele_de_la_configuration,
        )

    def test_une_variable_de_cle_absente_est_signalee(self):
        """
        La commande ne bloque pas — la clé peut arriver plus tard — mais
        elle le dit, sinon l'échec n'arrive qu'au premier appel, dans un
        worker, loin d'ici.
        """
        sortie = StringIO()
        with patch.dict("os.environ", {}, clear=True):
            call_command(
                "affecter_un_modele_a_un_role",
                role=RoleDeModele.JUGE_DE_VERIFICATION,
                plateforme="https://openrouter.ai/api/v1",
                modele_technique="openai/gpt-4o-mini",
                variable_de_cle="OPENROUTER_API_KEY",
                stdout=sortie,
            )
        self.assertIn("OPENROUTER_API_KEY", sortie.getvalue())


class AffectationEtRetraitTest(TestCase):
    """Affecter un modele existant, puis retirer l'affectation."""

    def setUp(self):
        self.modele_de_la_configuration = AIModel.objects.create(
            name="Modèle générique", model_choice="mock", is_active=True,
        )
        self.autre_modele = AIModel.objects.create(
            name="Petit juge", model_choice="mock", is_active=True,
        )
        configuration = Configuration.get_solo()
        configuration.ai_model = self.modele_de_la_configuration
        configuration.save()

    def test_affecter_un_modele_existant_par_son_identifiant(self):
        """`--modele <id>` suffit quand la ligne existe déjà."""
        call_command(
            "affecter_un_modele_a_un_role",
            role=RoleDeModele.JUGE_DE_VERIFICATION,
            modele=self.autre_modele.pk, stdout=StringIO(),
        )

        self.assertEqual(
            modele_du_role(RoleDeModele.JUGE_DE_VERIFICATION),
            self.autre_modele,
        )

    def test_reaffecter_remplace_sans_dupliquer(self):
        """Un rôle ne porte qu'un modèle, même après réaffectation."""
        call_command(
            "affecter_un_modele_a_un_role",
            role=RoleDeModele.JUGE_DE_VERIFICATION,
            modele=self.autre_modele.pk, stdout=StringIO(),
        )
        call_command(
            "affecter_un_modele_a_un_role",
            role=RoleDeModele.JUGE_DE_VERIFICATION,
            modele=self.modele_de_la_configuration.pk, stdout=StringIO(),
        )

        self.assertEqual(
            ModeleParRole.objects.filter(
                role=RoleDeModele.JUGE_DE_VERIFICATION,
            ).count(),
            1,
        )

    def test_retirer_rend_le_role_a_son_repli(self):
        """Sans affectation, le rôle reprend le modèle de la Configuration."""
        call_command(
            "affecter_un_modele_a_un_role",
            role=RoleDeModele.JUGE_DE_VERIFICATION,
            modele=self.autre_modele.pk, stdout=StringIO(),
        )
        call_command(
            "affecter_un_modele_a_un_role",
            role=RoleDeModele.JUGE_DE_VERIFICATION,
            retirer=True, stdout=StringIO(),
        )

        self.assertEqual(
            modele_du_role(RoleDeModele.JUGE_DE_VERIFICATION),
            self.modele_de_la_configuration,
        )

    def test_lister_dit_d_ou_vient_chaque_modele(self):
        """La liste distingue « affecté » de « repli »."""
        call_command(
            "affecter_un_modele_a_un_role",
            role=RoleDeModele.JUGE_DE_VERIFICATION,
            modele=self.autre_modele.pk, stdout=StringIO(),
        )
        sortie = StringIO()
        call_command("affecter_un_modele_a_un_role", lister=True, stdout=sortie)

        texte = sortie.getvalue()
        self.assertIn("affecté", texte)
        self.assertIn("repli sur la Configuration", texte)

    def test_un_modele_inexistant_est_refuse(self):
        """Affecter un identifiant qui n'existe pas doit échouer fort."""
        with self.assertRaises(CommandError):
            call_command(
                "affecter_un_modele_a_un_role",
                role=RoleDeModele.JUGE_DE_VERIFICATION,
                modele=999999, stdout=StringIO(),
            )

    def test_sans_role_la_commande_refuse(self):
        """Il n'y a pas de rôle par défaut : le choix est explicite."""
        with self.assertRaises(CommandError):
            call_command(
                "affecter_un_modele_a_un_role",
                modele=self.autre_modele.pk, stdout=StringIO(),
            )


class AffectationParChoixDuReferentielTest(TestCase):
    """
    Affecter un modele du referentiel `AIModelChoices`.
    / Assigning a model from the built-in choices.

    LOCALISATION : front/tests/test_affectation_d_un_modele_a_un_role.py

    Les lignes d'`AIModel` ne sont creees qu'a l'installation, UNE PAR
    CLE D'API trouvee — `gemini-2.5-flash` pour Google. Basculer le juge
    sur `gemini-2.5-flash-lite`, qui est pourtant dans le referentiel,
    exigeait donc d'ouvrir un shell Django. En production, ce geste doit
    etre une commande comme les autres.
    / Model rows are only created at install, one per API key; switching
    the judge to another listed model must not require a Django shell.
    """

    def setUp(self):
        self.modele_de_la_configuration = AIModel.objects.create(
            name="Gemini 2.5 Flash", model_choice="gemini-2.5-flash",
            is_active=True,
        )
        configuration = Configuration.get_solo()
        configuration.ai_model = self.modele_de_la_configuration
        configuration.ai_active = True
        configuration.save()

    def test_le_modele_du_referentiel_est_cree_et_affecte(self):
        """Une commande suffit : la ligne est créée, le rôle est posé."""
        call_command(
            "affecter_un_modele_a_un_role",
            role=RoleDeModele.JUGE_DE_VERIFICATION,
            choix="gemini-2.5-flash-lite", stdout=StringIO(),
        )

        juge = modele_du_role(RoleDeModele.JUGE_DE_VERIFICATION)
        self.assertEqual(juge.model_choice, "gemini-2.5-flash-lite")
        self.assertEqual(juge.provider, Provider.GOOGLE)

    def test_le_tarif_du_modele_cree_est_connu(self):
        """
        Un modèle du référentiel a son tarif dans la table : l'écran de
        confirmation annoncera un montant, pas « non mesuré ».
        """
        call_command(
            "affecter_un_modele_a_un_role",
            role=RoleDeModele.JUGE_DE_VERIFICATION,
            choix="gemini-2.5-flash-lite", stdout=StringIO(),
        )

        juge = modele_du_role(RoleDeModele.JUGE_DE_VERIFICATION)
        self.assertIsNotNone(juge.cout_par_million_tokens())

    def test_un_choix_absent_du_referentiel_est_refuse(self):
        """
        Un modèle hors référentiel n'a ni tarif ni provider déductible :
        il passe par `--plateforme`, qui exige une `base_url` et une
        variable de clé.
        """
        with self.assertRaises(CommandError):
            call_command(
                "affecter_un_modele_a_un_role",
                role=RoleDeModele.JUGE_DE_VERIFICATION,
                choix="un-modele-qui-n-existe-pas", stdout=StringIO(),
            )

    def test_reaffecter_le_meme_choix_ne_duplique_pas_la_ligne(self):
        """Deux passages, un seul modèle en base."""
        for _ in range(2):
            call_command(
                "affecter_un_modele_a_un_role",
                role=RoleDeModele.JUGE_DE_VERIFICATION,
                choix="gemini-2.5-flash-lite", stdout=StringIO(),
            )

        self.assertEqual(
            AIModel.objects.filter(
                model_choice="gemini-2.5-flash-lite",
            ).count(),
            1,
        )


class LaTemperatureSeRegleParCommandeTest(TestCase):
    """
    La temperature d'un juge se pose par commande.
    / A judge's temperature is set by command.

    LOCALISATION : front/tests/test_affectation_d_un_modele_a_un_role.py

    Un juge se compare a un autre juge : si les deux ne tournent pas a la
    meme temperature, la mesure oppose deux reglages, pas deux modeles.
    Et le reglage doit etre REJOUABLE en production — l'admin Django est
    desactive, il n'y a pas d'ecran, et un `manage.py shell` n'est pas un
    geste qu'on documente.
    / Comparing two judges at different temperatures compares settings,
    not models; and the setting must be replayable in production.
    """

    def test_la_temperature_est_posee_a_la_creation(self):
        """Le modèle naît avec la température demandée."""
        call_command(
            "affecter_un_modele_a_un_role",
            role=RoleDeModele.JUGE_DE_VERIFICATION,
            choix="gemini-2.5-flash", temperature=0.0, stdout=StringIO(),
        )

        self.assertEqual(
            modele_du_role(RoleDeModele.JUGE_DE_VERIFICATION).temperature,
            0.0,
        )

    def test_la_temperature_se_change_sur_un_modele_existant(self):
        """Réaffecter avec une autre température la met à jour."""
        modele = AIModel.objects.create(
            name="Juge tiède", model_choice="mock", temperature=0.7,
        )
        call_command(
            "affecter_un_modele_a_un_role",
            role=RoleDeModele.JUGE_DE_VERIFICATION,
            modele=modele.pk, temperature=0.0, stdout=StringIO(),
        )

        modele.refresh_from_db()
        self.assertEqual(modele.temperature, 0.0)

    def test_sans_option_la_temperature_du_modele_est_laissee_telle_quelle(self):
        """Ne rien demander ne change rien : pas d'effet de bord."""
        modele = AIModel.objects.create(
            name="Juge tiède", model_choice="mock", temperature=0.7,
        )
        call_command(
            "affecter_un_modele_a_un_role",
            role=RoleDeModele.JUGE_DE_VERIFICATION,
            modele=modele.pk, stdout=StringIO(),
        )

        modele.refresh_from_db()
        self.assertEqual(modele.temperature, 0.7)


class LaTemperaturePeutEtreLaisseeAuFournisseurTest(TestCase):
    """
    `--temperature-du-fournisseur` vide le champ.
    / The flag clears the field.

    LOCALISATION : front/tests/test_affectation_d_un_modele_a_un_role.py

    Les modeles de raisonnement d'OpenAI refusent toute temperature autre
    que la leur : `gpt-5-mini` rend « 400 — Unsupported value:
    'temperature' does not support 0.0 ». Il faut donc pouvoir dire « ne
    transmets rien » depuis la commande, et pas seulement depuis un
    shell.
    / OpenAI's reasoning models reject any temperature but their own.
    """

    def test_le_champ_est_vide_et_ce_n_est_pas_zero(self):
        """Vider n'est pas mettre à zéro : « aucune » ≠ « je veux 0 »."""
        modele = AIModel.objects.create(
            name="Raisonnement", model_choice="gpt-5-mini", temperature=0.7,
        )
        call_command(
            "affecter_un_modele_a_un_role",
            role=RoleDeModele.REDACTEUR_D_ARTICLE, modele=modele.pk,
            temperature_du_fournisseur=True, stdout=StringIO(),
        )

        modele.refresh_from_db()
        self.assertIsNone(modele.temperature)


class UnModeleDeRaisonnementNaitSansTemperatureTest(TestCase):
    """
    Un modele qui refuse toute temperature nait sans temperature.
    / A model that rejects any temperature is born without one.

    LOCALISATION : front/tests/test_affectation_d_un_modele_a_un_role.py

    Le champ `temperature` vaut 0,7 par defaut. Or les modeles de
    raisonnement d'OpenAI refusent toute valeur autre que la leur :
    creer `gpt-5-mini` sans y penser fabrique une ligne qui rend un
    **400 systematique**, et l'echec n'eclate que plus tard, dans un
    worker, loin de la commande qui l'a cree.
    / The field defaults to 0.7, which these models reject with a 400
    that only surfaces later, inside a worker.
    """

    def setUp(self):
        modele_generique = AIModel.objects.create(
            name="Générique", model_choice="mock", is_active=True,
        )
        configuration = Configuration.get_solo()
        configuration.ai_model = modele_generique
        configuration.save()

    def test_un_modele_de_raisonnement_nait_sans_temperature(self):
        """`gpt-5-mini` créé par la commande ne porte aucune température."""
        call_command(
            "affecter_un_modele_a_un_role",
            role=RoleDeModele.JUGE_DE_VERIFICATION,
            choix="gpt-5-mini", stdout=StringIO(),
        )

        self.assertIsNone(
            modele_du_role(RoleDeModele.JUGE_DE_VERIFICATION).temperature,
        )

    def test_la_commande_le_dit(self):
        """Le choix est expliqué, pas subi en silence."""
        sortie = StringIO()
        call_command(
            "affecter_un_modele_a_un_role",
            role=RoleDeModele.JUGE_DE_VERIFICATION,
            choix="gpt-5-nano", stdout=sortie,
        )

        self.assertIn("température", sortie.getvalue().lower())

    def test_une_temperature_demandee_explicitement_est_respectee(self):
        """
        La garde ne confisque rien : si on demande une température, on
        l'obtient — l'appel échouera, et c'est le choix de qui le fait.
        """
        call_command(
            "affecter_un_modele_a_un_role",
            role=RoleDeModele.JUGE_DE_VERIFICATION,
            choix="gpt-5-mini", temperature=0.3, stdout=StringIO(),
        )

        self.assertEqual(
            modele_du_role(RoleDeModele.JUGE_DE_VERIFICATION).temperature,
            0.3,
        )

    def test_un_modele_ordinaire_garde_sa_temperature_par_defaut(self):
        """La garde ne touche pas aux autres modèles."""
        call_command(
            "affecter_un_modele_a_un_role",
            role=RoleDeModele.JUGE_DE_VERIFICATION,
            choix="gemini-2.5-flash", stdout=StringIO(),
        )

        self.assertIsNotNone(
            modele_du_role(RoleDeModele.JUGE_DE_VERIFICATION).temperature,
        )
