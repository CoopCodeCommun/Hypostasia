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
CLES_API_NEUTRALISEES = {
    "GOOGLE_API_KEY": "",
    "OPENAI_API_KEY": "",
    "ANTHROPIC_API_KEY": "",
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


