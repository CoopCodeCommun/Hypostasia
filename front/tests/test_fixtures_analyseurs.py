"""
Tests du service de fixtures des modeles IA et des analyseurs.
/ Tests for the AI models and analyzers fixtures service.

LOCALISATION : front/tests/test_fixtures_analyseurs.py

CE QUE CES TESTS PROTEGENT

Une base fraichement installee doit proposer au moins un analyseur
d'extraction UTILISABLE : sans lui, le bouton « Lancer une analyse »
n'ouvre aucun selecteur et l'application est inutilisable pour sa
fonction principale. Le critere n'est donc pas « il existe un
AnalyseurSyntaxique en base » — un analyseur sans exemple few-shot
complet est ecarte par `_analyseurs_extraction_utilisables()`. Les tests
passent donc par cette fonction, jamais par un simple `count()`.
/ A freshly installed database must offer at least one USABLE extraction
analyzer, checked through `_analyseurs_extraction_utilisables()` rather
than a bare count: an analyzer without a complete few-shot example is
filtered out and would leave the analysis button empty.
"""

import os
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from core.models import AIModel, Configuration
from front.management.commands.charger_fixtures_sample import (
    Command as CommandeDeFixturesSample,
)
from front.services.fixtures_analyseurs import (
    MODELES_IA_PAR_CLE_D_ENVIRONNEMENT,
    NOM_DE_L_ANALYSEUR_D_EXTRACTION,
    NOM_DE_L_ANALYSEUR_DE_SYNTHESE,
    creer_les_modeles_ia_et_les_analyseurs,
)
from front.views import _analyseurs_extraction_utilisables
from hypostasis_extractor.models import (
    AnalyseurExample,
    AnalyseurSyntaxique,
    ExampleExtraction,
    PromptPiece,
)

# Les trois cles lues par le service. Les neutraliser d'un bloc evite
# qu'un .env local (le conteneur de dev en porte deux) ne change le
# resultat des tests qui parlent d'absence de cle.
# / The three keys read by the service, neutralized together so a local
# .env cannot change the outcome of the "no key" tests.
# TOUTES les cles du referentiel, neutralisees — DERIVEES de la liste,
# jamais recopiees.
#
# POURQUOI PAS UNE LISTE EN DUR. Elle en etait une, avec trois cles. Le
# jour ou `MODELES_IA_PAR_CLE_D_ENVIRONNEMENT` a gagne Mistral
# (18 aout 2026), la copie est devenue incomplete : `MISTRAL_API_KEY`
# etant reellement presente dans l'environnement, deux tests qui
# croyaient partir SANS AUCUNE cle en avaient une — et ils sont tombes.
# Deriver la liste rend cette derive impossible.
# / Derived, never copied: a hardcoded list silently went stale the day
#   a fourth model was added.
CLES_API_NEUTRALISEES = {
    definition["cle_env"]: ""
    for definition in MODELES_IA_PAR_CLE_D_ENVIRONNEMENT
}


def charger_les_fixtures_sample(*arguments_supplementaires):
    """
    Lance charger_fixtures_sample sans jamais toucher a Docling.
    / Runs charger_fixtures_sample without ever invoking Docling.

    LOCALISATION : front/tests/test_fixtures_analyseurs.py

    `_charger_les_documents` convertit deux PDF : ~180 s et plusieurs Gio
    de memoire. Aucun test de ce fichier ne parle des documents etalons,
    seulement des analyseurs — on neutralise donc la partie couteuse.
    / The document loading step converts two PDF (~180s); none of these
    tests care about documents, only analyzers, so it is neutralized.
    """
    sortie = StringIO()
    with patch.object(
        CommandeDeFixturesSample, "_charger_les_documents", return_value=None,
    ):
        call_command(
            "charger_fixtures_sample", *arguments_supplementaires, stdout=sortie,
        )
    return sortie.getvalue()


class AnalyseursApresChargementSampleTest(TestCase):
    """Le test central : après `charger_fixtures_sample`, on peut analyser."""

    def test_un_analyseur_d_extraction_est_utilisable(self):
        # Une base neuve ne propose rien : c'est le bug de depart.
        # / A fresh database offers nothing: that is the starting bug.
        self.assertEqual(_analyseurs_extraction_utilisables(), [])

        charger_les_fixtures_sample()

        analyseurs_utilisables = _analyseurs_extraction_utilisables()
        self.assertTrue(
            analyseurs_utilisables,
            "Aucun analyseur utilisable après charger_fixtures_sample : "
            "le sélecteur « Lancer une analyse » resterait vide.",
        )
        self.assertIn(
            NOM_DE_L_ANALYSEUR_D_EXTRACTION,
            [analyseur.name for analyseur in analyseurs_utilisables],
        )

    def test_le_mode_a_blanc_ne_cree_aucun_analyseur(self):
        # --a-blanc annonce sans ecrire : la promesse vaut aussi pour les
        # analyseurs. / A dry run announces without writing, analyzers too.
        sortie = charger_les_fixtures_sample("--a-blanc")

        self.assertEqual(AnalyseurSyntaxique.objects.count(), 0)
        self.assertIn("Analyseurs IA", sortie)

    def test_deux_chargements_ne_dupliquent_pas_les_analyseurs(self):
        charger_les_fixtures_sample()
        charger_les_fixtures_sample()

        self.assertEqual(
            AnalyseurSyntaxique.objects.filter(
                name=NOM_DE_L_ANALYSEUR_D_EXTRACTION,
            ).count(),
            1,
        )
        self.assertEqual(
            AnalyseurSyntaxique.objects.filter(
                name=NOM_DE_L_ANALYSEUR_DE_SYNTHESE,
            ).count(),
            1,
        )
        # Ni les pieces ni les exemples ne doivent doubler non plus.
        # / Neither prompt pieces nor examples may double either.
        self.assertEqual(AnalyseurExample.objects.count(), 1)
        self.assertEqual(ExampleExtraction.objects.count(), 30)


class ServiceDeFixturesDesAnalyseursTest(TestCase):
    """Le service lui-même, appelé hors de toute commande."""

    def test_il_cree_l_analyseur_d_extraction_et_celui_de_synthese(self):
        rapport = creer_les_modeles_ia_et_les_analyseurs()

        self.assertTrue(rapport["analyseur_extraction_cree"])
        self.assertTrue(rapport["analyseur_synthese_cree"])
        self.assertEqual(
            rapport["analyseur_extraction"].type_analyseur, "analyser",
        )
        self.assertEqual(
            rapport["analyseur_synthese"].type_analyseur, "synthetiser",
        )
        # 4 pieces pour l'extraction, 3 pour la synthese.
        # / 4 prompt pieces for extraction, 3 for synthesis.
        self.assertEqual(
            PromptPiece.objects.filter(
                analyseur=rapport["analyseur_extraction"],
            ).count(),
            4,
        )
        self.assertEqual(
            PromptPiece.objects.filter(
                analyseur=rapport["analyseur_synthese"],
            ).count(),
            3,
        )

    def test_l_exemple_few_shot_rend_l_analyseur_utilisable(self):
        creer_les_modeles_ia_et_les_analyseurs()

        analyseur = AnalyseurSyntaxique.objects.get(
            name=NOM_DE_L_ANALYSEUR_D_EXTRACTION,
        )
        from hypostasis_extractor.services import verifier_utilisabilite_analyseur

        est_utilisable, problemes = verifier_utilisabilite_analyseur(analyseur)
        self.assertTrue(est_utilisable, problemes)

    def test_un_analyseur_homonyme_incomplet_est_complete_sans_etre_duplique(self):
        # Le cas qui casse en silence : quelqu'un a deja un analyseur
        # nomme « Hypostasia », mais vide. Un get_or_create seul le
        # laisserait vide, donc inutilisable, et le bouton resterait mort.
        # / The silently broken case: an existing but empty homonym.
        analyseur_deja_la = AnalyseurSyntaxique.objects.create(
            name=NOM_DE_L_ANALYSEUR_D_EXTRACTION, type_analyseur="analyser",
        )

        rapport = creer_les_modeles_ia_et_les_analyseurs()

        self.assertFalse(rapport["analyseur_extraction_cree"])
        self.assertEqual(
            AnalyseurSyntaxique.objects.filter(
                name=NOM_DE_L_ANALYSEUR_D_EXTRACTION,
            ).count(),
            1,
        )
        self.assertEqual(rapport["analyseur_extraction"].pk, analyseur_deja_la.pk)
        self.assertIn(
            NOM_DE_L_ANALYSEUR_D_EXTRACTION,
            [analyseur.name for analyseur in _analyseurs_extraction_utilisables()],
        )

    def test_un_analyseur_homonyme_complet_n_est_pas_retouche(self):
        # A l'inverse : un analyseur deja garni appartient a son auteur.
        # Le service n'ajoute rien par-dessus son exemple a lui.
        # / Conversely, an already-furnished analyzer is left untouched.
        analyseur_deja_la = AnalyseurSyntaxique.objects.create(
            name=NOM_DE_L_ANALYSEUR_D_EXTRACTION, type_analyseur="analyser",
        )
        exemple_maison = AnalyseurExample.objects.create(
            analyseur=analyseur_deja_la,
            name="Mon exemple à moi",
            example_text="Un texte source bien réel.",
        )
        ExampleExtraction.objects.create(
            example=exemple_maison,
            extraction_class="hypostase",
            extraction_text="Un texte source bien réel.",
        )

        creer_les_modeles_ia_et_les_analyseurs()

        self.assertEqual(
            AnalyseurExample.objects.filter(analyseur=analyseur_deja_la).count(), 1,
        )
        self.assertEqual(
            AnalyseurExample.objects.get(analyseur=analyseur_deja_la).pk,
            exemple_maison.pk,
        )

    def test_sans_cle_api_aucun_modele_ia_n_est_cree(self):
        # Pas de Mock : soit une vraie cle, soit pas d'IA. Un modele
        # fantoche donnerait l'illusion d'une chaine branchee.
        # / No mock model: a phantom one would fake a working chain.
        with patch.dict(os.environ, CLES_API_NEUTRALISEES):
            rapport = creer_les_modeles_ia_et_les_analyseurs()

        self.assertEqual(AIModel.objects.count(), 0)
        self.assertTrue(rapport["aucune_cle_api_detectee"])
        self.assertFalse(rapport["configuration_ia_activee"])
        # Les analyseurs, eux, sont crees quand meme : la cle peut
        # arriver plus tard dans le .env.
        # / Analyzers are still created: the key may arrive later.
        self.assertTrue(rapport["analyseur_extraction_cree"])

    def test_mistral_est_le_modele_d_extraction_et_porte_sa_plateforme(self):
        """
        L'ORDRE DE LA LISTE DECIDE : le premier modele disponible devient
        celui de la Configuration, donc le modele d'EXTRACTION. Et c'est
        cette fonction, et elle seule, qui reconstruit le referentiel
        apres un `docker compose down -v` — un choix pose a la main n'y
        survit pas.
        / The list's order decides which model extracts, and this
        function is what rebuilds the referential after a `down -v`.
        """
        cles = dict(CLES_API_NEUTRALISEES)
        cles["MISTRAL_API_KEY"] = "une-cle-de-test"
        cles["GOOGLE_API_KEY"] = "une-autre-cle"

        with patch.dict(os.environ, cles):
            creer_les_modeles_ia_et_les_analyseurs()

        configuration = Configuration.get_solo()
        self.assertEqual(
            configuration.ai_model.model_choice, "mistral-small-latest",
        )
        modele = configuration.ai_model
        # La plateforme est designee par `base_url`, et la cle n'est
        # JAMAIS en base — seul son nom de variable l'est.
        # / base_url names the platform; the key itself is never stored.
        self.assertEqual(modele.provider, "compatible_openai")
        self.assertEqual(modele.base_url, "https://api.mistral.ai/v1")
        self.assertEqual(modele.variable_de_cle_api, "MISTRAL_API_KEY")

    def test_le_modele_recree_est_a_temperature_zero(self):
        """
        TOUS les bancs de `benchmarks/` mesurent a 0 — « a armes
        egales ». Le defaut du champ vaut 0,7 : sans cette valeur dans
        les fixtures, une base reconstruite repartirait a 0,7 et AUCUNE
        mesure ne serait plus comparable aux precedentes, sans qu'un
        seul message ne le dise.
        / Every bench measures at 0; the field defaults to 0.7.
        """
        cles = dict(CLES_API_NEUTRALISEES)
        cles["MISTRAL_API_KEY"] = "une-cle-de-test"

        with patch.dict(os.environ, cles):
            creer_les_modeles_ia_et_les_analyseurs()

        modele = AIModel.objects.get(model_choice="mistral-small-latest")
        self.assertEqual(modele.temperature, 0.0)

    def test_les_roles_sont_poses_a_l_installation(self):
        """
        Sans eux, `ModeleParRole` repart vide apres un `down -v` et
        chaque role retombe sur la Configuration : le repli fonctionne,
        mais l'affectation choisie est perdue en silence.
        / Otherwise the chosen assignment silently vanishes.
        """
        from core.models import ModeleParRole, RoleDeModele

        cles = dict(CLES_API_NEUTRALISEES)
        cles["MISTRAL_API_KEY"] = "une-cle-de-test"

        with patch.dict(os.environ, cles):
            creer_les_modeles_ia_et_les_analyseurs()

        # DEUX ROLES, DEUX MODELES, ET LA DIFFERENCE EST MESUREE.
        # La campagne des neuf passes du 19 aout 2026 a montre que le
        # « % de citations verifiees » ne departage pas les redacteurs
        # (11 points d'amplitude d'un modele avec lui-meme). Ce qui
        # tranche, c'est la PROSE SANS SOURCE : Medium en laisse 10 %,
        # Small 18,8 %, Large 26,2 %. Pour un outil dont la promesse est
        # la tracabilite, c'est ce critere qui decide.
        # / Nine repeated passes: the verified-rate does not
        #   discriminate; unsourced prose does. Medium wins there.
        attendus = {
            RoleDeModele.REDACTEUR_D_ARTICLE: "mistral-medium-latest",
            RoleDeModele.JUGE_DE_VERIFICATION: "mistral-small-latest",
        }
        for role, model_choice_attendu in attendus.items():
            with self.subTest(role=role):
                affectation = ModeleParRole.objects.get(role=role)
                self.assertEqual(
                    affectation.modele.model_choice, model_choice_attendu,
                )

    def test_le_redacteur_est_cree_meme_s_il_n_est_pas_le_premier(self):
        """
        LE PIEGE DE L'ORDRE. Le PREMIER modele de la liste devient celui
        de la Configuration, donc le modele d'EXTRACTION — c'est Small,
        et il doit le rester. Medium vient donc APRES, et il faut
        verifier qu'il est bien cree quand meme : un role qui designe un
        modele absent est saute en silence, et le redacteur retomberait
        sur la Configuration sans qu'un mot ne le dise.
        / Medium comes second on purpose; a role naming an absent model
        is silently skipped.
        """
        from core.models import AIModel, Configuration

        cles = dict(CLES_API_NEUTRALISEES)
        cles["MISTRAL_API_KEY"] = "une-cle-de-test"

        with patch.dict(os.environ, cles):
            creer_les_modeles_ia_et_les_analyseurs()

        self.assertTrue(
            AIModel.objects.filter(
                model_choice="mistral-medium-latest",
            ).exists(),
        )
        # L'extraction reste sur Small : c'est LangExtract qui l'appelle.
        # / Extraction stays on Small.
        self.assertEqual(
            Configuration.get_solo().ai_model.model_choice,
            "mistral-small-latest",
        )

    def test_le_redacteur_recree_est_aussi_a_temperature_zero(self):
        """
        Tous les bancs mesurent a 0. Le defaut du champ vaut 0,7 : sans
        la ligne explicite, une base reconstruite apres un `down -v`
        repartirait a 0,7 et aucune mesure ne serait plus comparable.
        / Every bench measures at 0; the field defaults to 0.7.
        """
        from core.models import AIModel

        cles = dict(CLES_API_NEUTRALISEES)
        cles["MISTRAL_API_KEY"] = "une-cle-de-test"

        with patch.dict(os.environ, cles):
            creer_les_modeles_ia_et_les_analyseurs()

        redacteur = AIModel.objects.get(model_choice="mistral-medium-latest")
        self.assertEqual(redacteur.temperature, 0.0)

    def test_un_role_choisi_a_la_main_survit_a_une_reinstallation(self):
        """
        CETTE FONCTION TOURNE A CHAQUE DEMARRAGE DE CONTENEUR. Avec un
        `update_or_create`, un role change par
        `affecter_un_modele_a_un_role` — le geste que la conception
        prevoit — retomberait sur Mistral au redemarrage suivant, sans
        un mot. C'est la meme regle que celle deja appliquee a la
        Configuration : un choix pose a la main survit.
        / This runs at every container start: a hand-picked role must
        survive it.
        """
        from core.models import ModeleParRole, RoleDeModele

        cles = dict(CLES_API_NEUTRALISEES)
        cles["MISTRAL_API_KEY"] = "une-cle-de-test"
        cles["GOOGLE_API_KEY"] = "une-autre-cle"

        with patch.dict(os.environ, cles):
            creer_les_modeles_ia_et_les_analyseurs()

            # Le mainteneur change le juge a la main.
            gemini = AIModel.objects.get(model_choice="gemini-2.5-flash")
            ModeleParRole.objects.filter(
                role=RoleDeModele.JUGE_DE_VERIFICATION,
            ).update(modele=gemini)

            # Le conteneur redemarre.
            creer_les_modeles_ia_et_les_analyseurs()

        affectation = ModeleParRole.objects.get(
            role=RoleDeModele.JUGE_DE_VERIFICATION,
        )
        self.assertEqual(affectation.modele.model_choice, "gemini-2.5-flash")

    def test_une_cle_api_cree_le_modele_et_active_la_configuration(self):
        cles_avec_google = dict(CLES_API_NEUTRALISEES)
        cles_avec_google["GOOGLE_API_KEY"] = "une-cle-de-test"

        with patch.dict(os.environ, cles_avec_google):
            rapport = creer_les_modeles_ia_et_les_analyseurs()

        self.assertEqual(
            [nom for nom, _cle_env in rapport["modeles_ia_crees"]],
            ["Gemini 2.5 Flash"],
        )
        self.assertTrue(rapport["configuration_ia_activee"])
        configuration = Configuration.get_solo()
        self.assertTrue(configuration.ai_active)
        self.assertEqual(
            configuration.ai_model.model_choice, "gemini-2.5-flash",
        )


