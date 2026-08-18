"""
Tests de l'extraction par une API compatible OpenAI.
/ Tests of extraction through an OpenAI-compatible API.

LOCALISATION : hypostasis_extractor/tests/test_extraction_par_api_compatible.py

LE PIEGE QUE CES TESTS FERMENT. LangExtract choisit son moteur par
EXPRESSION REGULIERE sur le nom du modele (`providers/patterns.py`) :
`^mistral`, `^qwen`, `^llama`, `^gemma`, `^phi`, `^deepseek` partent tous
vers `OllamaLanguageModel`, qui parle l'API PROPRIETAIRE d'Ollama
(`POST {base}/api/generate`). Pointe sur `https://api.mistral.ai/v1`, ce
moteur echoue — et rien dans le nom du modele ne le laissait deviner.

LA PARADE N'EST PAS UN FORK. `lx.extract` accepte un parametre `config`
(`ModelConfig`) qui resout le provider par son NOM et court-circuite la
table de motifs. C'est une API publique et documentee de la
bibliotheque : rien a surcharger, rien a maintenir a la prochaine montee
de version.
/ LangExtract routes by regex on the model name; `config=ModelConfig`
resolves by provider name instead, and is public API — no fork needed.

AUCUN APPEL RESEAU ICI. La construction du client OpenAI est locale : il
ne se connecte qu'au premier POST. On peut donc construire le modele
LangExtract reel et verifier sa classe sans rien payer.
/ No network: the OpenAI client only connects on the first POST.
"""

import os
from unittest import mock

from django.test import TestCase

from core.models import AIModel, Provider
from hypostasis_extractor.services import resolve_model_params

BASE_URL_DE_MISTRAL = "https://api.mistral.ai/v1"


class ParametresPourUneApiCompatibleTest(TestCase):
    """Ce que `resolve_model_params` rend. / What it returns."""

    def setUp(self):
        self.modele = AIModel.objects.create(
            name="Mistral Small", model_choice="mistral-small-latest",
            provider=Provider.COMPATIBLE_OPENAI,
            base_url=BASE_URL_DE_MISTRAL,
            variable_de_cle_api="MISTRAL_API_KEY",
        )

    @mock.patch.dict(os.environ, {"MISTRAL_API_KEY": "cle-de-test"})
    def test_le_provider_est_designe_par_son_nom_pas_par_le_modele(self):
        """
        C'est `config` qui décide, et il nomme le provider. Sans lui,
        « mistral-small-latest » partirait vers Ollama.
        """
        parametres = resolve_model_params(self.modele)

        self.assertIn("config", parametres)
        self.assertEqual(
            parametres["config"].provider, "OpenAILanguageModel",
        )
        self.assertEqual(
            parametres["config"].model_id, "mistral-small-latest",
        )

    @mock.patch.dict(os.environ, {"MISTRAL_API_KEY": "cle-de-test"})
    def test_la_base_url_et_la_cle_partent_dans_le_provider(self):
        """La plateforme est décidée par `base_url`, la clé vient du .env."""
        parametres = resolve_model_params(self.modele)

        arguments = parametres["config"].provider_kwargs
        self.assertEqual(arguments["base_url"], BASE_URL_DE_MISTRAL)
        self.assertEqual(arguments["api_key"], "cle-de-test")
        # Jamais au premier niveau : `lx.extract` les ignorerait, et la
        # cle se retrouverait dans un log de parametres.
        # / Never top-level: they would be ignored, and logged.
        self.assertNotIn("api_key", parametres)
        self.assertNotIn("model_url", parametres)

    @mock.patch.dict(os.environ, {"MISTRAL_API_KEY": "cle-de-test"})
    def test_les_contraintes_de_schema_sont_desactivees(self):
        """
        Ce provider n'a pas de schéma structuré : le laisser actif
        n'apporte rien et fait émettre un avertissement à CHAQUE chunk.
        """
        parametres = resolve_model_params(self.modele)

        self.assertIs(parametres["use_schema_constraints"], False)

    @mock.patch.dict(os.environ, {"MISTRAL_API_KEY": "cle-de-test"})
    def test_le_config_construit_bien_un_moteur_openai(self):
        """
        Le test qui compte : on construit le moteur LangExtract RÉEL et
        on vérifie sa classe. Aucun appel réseau — le client OpenAI ne se
        connecte qu'au premier POST.
        """
        from langextract import factory
        from langextract.providers.openai import OpenAILanguageModel

        parametres = resolve_model_params(self.modele)
        moteur = factory.create_model(parametres["config"])

        self.assertIsInstance(moteur, OpenAILanguageModel)

    def test_sans_variable_de_cle_la_resolution_leve(self):
        """Une ligne qui ne dit pas où est sa clé ne peut pas extraire."""
        modele_muet = AIModel.objects.create(
            name="Sans clé", model_choice="mistral-small-latest",
            provider=Provider.COMPATIBLE_OPENAI,
            base_url=BASE_URL_DE_MISTRAL,
        )
        with self.assertRaises(ValueError):
            resolve_model_params(modele_muet)

    @mock.patch.dict(os.environ, {}, clear=True)
    def test_une_cle_absente_leve_en_la_nommant(self):
        """Le message dit QUELLE variable manque."""
        with self.assertRaises(ValueError) as contexte:
            resolve_model_params(self.modele)
        self.assertIn("MISTRAL_API_KEY", str(contexte.exception))

    @mock.patch.dict(os.environ, {"MISTRAL_API_KEY": "cle-de-test"})
    def test_sans_base_url_la_resolution_leve(self):
        """Sans `base_url`, aucune plateforme n'est désignée."""
        modele_sans_url = AIModel.objects.create(
            name="Sans URL", model_choice="mistral-small-latest",
            provider=Provider.COMPATIBLE_OPENAI,
            variable_de_cle_api="MISTRAL_API_KEY",
        )
        with self.assertRaises(ValueError):
            resolve_model_params(modele_sans_url)


class LeRoutageParDefautDeLangExtractTest(TestCase):
    """
    Le piège que `config` court-circuite, documenté par un test.
    / The trap that `config` bypasses, pinned by a test.
    """

    def test_sans_config_un_modele_mistral_partirait_vers_ollama(self):
        """
        Si ce test tombe à une montée de version, c'est que la table de
        motifs de LangExtract a changé — et le commentaire de
        `resolve_model_params` est à revérifier.
        """
        from langextract import providers
        from langextract.providers import router

        providers.load_builtins_once()
        moteur_par_defaut = router.resolve("mistral-small-latest")

        self.assertEqual(moteur_par_defaut.__name__, "OllamaLanguageModel")


class LesParametresArriventJusquALangExtractTest(TestCase):
    """
    Le verrou de bout en bout : ce que la production passe vraiment.
    / End to end: what production actually passes.
    """

    @mock.patch.dict(os.environ, {"MISTRAL_API_KEY": "cle-de-test"})
    def test_l_appel_de_production_porte_le_config(self):
        """
        `appeler_langextract_sur_un_chunk` doit transmettre `config` —
        c'est lui qui empêche le départ silencieux vers Ollama.
        """
        from core.models import Page
        from hypostasis_extractor.models import ExtractionJob
        from hypostasis_extractor.services import analyse_par_element

        modele = AIModel.objects.create(
            name="Mistral Small", model_choice="mistral-small-latest",
            provider=Provider.COMPATIBLE_OPENAI,
            base_url=BASE_URL_DE_MISTRAL,
            variable_de_cle_api="MISTRAL_API_KEY",
        )
        note = Page.objects.create(
            title="Note à analyser", text_readability="Un texte à analyser.",
            html_readability="", html_original="",
            content_hash="hash-compatible-openai",
        )
        job = ExtractionJob.objects.create(
            page=note, name="Analyse", status="pending", ai_model=modele,
            prompt_description="Extrais les hypostases.",
        )

        with mock.patch.object(
            analyse_par_element, "_construire_les_exemples_du_job",
            return_value=["un exemple"],
        ), mock.patch("langextract.extract") as extraction_moquee:
            extraction_moquee.return_value = mock.MagicMock(extractions=[])
            analyse_par_element.appeler_langextract_sur_un_chunk(
                "Un texte à analyser.", job,
            )

        arguments = extraction_moquee.call_args[1]
        self.assertEqual(
            arguments["config"].provider, "OpenAILanguageModel",
        )
        self.assertIs(arguments["use_schema_constraints"], False)
        # Les garde-fous de production ne bougent pas.
        # / The production guards are untouched.
        self.assertIs(arguments["fetch_urls"], False)
        self.assertTrue(
            arguments["resolver_params"]["suppress_parse_errors"],
        )
