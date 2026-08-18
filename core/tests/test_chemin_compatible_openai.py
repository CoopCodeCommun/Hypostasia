"""
Tests du chemin d'appel « compatible OpenAI », partage par toutes les
plateformes qui l'exposent. / Tests of the shared OpenAI-compatible path.

LOCALISATION : core/tests/test_chemin_compatible_openai.py

UN SEUL CHEMIN, PARAMETRE PAR `base_url`. OpenRouter, Mistral, Scaleway,
un serveur Ollama local : tous exposent `POST {base_url}/chat/completions`.
Ecrire une implementation par plateforme, c'est ecrire N fois le meme
retry, le meme timeout, et la meme detection d'erreur — et n'en corriger
qu'une le jour ou l'un des trois est faux.

CE QUE CES TESTS VERROUILLENT :
- un identifiant de la forme `vendor/modele` ne peut PAS retomber en
  MOCK ni en OLLAMA en silence ;
- un provider pose EXPLICITEMENT n'est jamais reecrit par la table de
  prefixes — `mistral-small-latest` y matche « mistral » et partirait
  vers un Ollama local qui n'existe pas ;
- la cle API reste dans l'ENVIRONNEMENT ; la ligne en base dit seulement
  LAQUELLE ;
- un « HTTP 200 avec corps d'erreur » LEVE au lieu de rendre une reponse
  vide qui serait lue comme un verdict manquant ;
- le timeout et le nombre de tentatives sont poses EXPLICITEMENT — le
  defaut du SDK est de 600 s en lecture, soit dix minutes pendant
  lesquelles un worker Celery a concurrence 2 ne fait rien.
/ One path parameterized by base_url; explicit provider wins over the
prefix table; keys stay in the environment; a 200-with-error-body
raises; timeout and retries are set explicitly.
"""

from unittest.mock import MagicMock, patch

from django.test import TestCase

from core.models import AIModel, Provider


def _reponse_de_chat(texte):
    """Une reponse de l'API, telle que le SDK la rend. / An SDK reply."""
    message = MagicMock()
    message.content = texte
    choix = MagicMock()
    choix.message = message
    reponse = MagicMock()
    reponse.choices = [choix]
    reponse.error = None
    return reponse


class ProviderCompatibleOpenAITest(TestCase):
    """Le provider existe et se deduit sans piege. / The provider exists."""

    def test_le_provider_compatible_openai_existe(self):
        """La valeur est dans l'enum, sinon rien ne peut la porter."""
        self.assertIn("compatible_openai", Provider.values)

    def test_un_identifiant_vendor_modele_ne_retombe_pas_en_mock(self):
        """
        `openai/gpt-4o-mini` ne matche aucun préfixe de la table : sans
        règle dédiée, le provider resterait MOCK et `appeler_llm`
        répondrait « [MOCK] … » sans lever la moindre erreur.
        """
        modele = AIModel.objects.create(
            name="Par un routeur", model_choice="openai/gpt-4o-mini",
        )
        modele.refresh_from_db()
        self.assertEqual(modele.provider, Provider.COMPATIBLE_OPENAI)

    def test_un_identifiant_vendor_modele_ne_part_pas_vers_ollama(self):
        """
        `mistralai/…`, `qwen/…` et `deepseek/…` matchent les préfixes
        « mistral », « qwen » et « deepseek » de la table, qui les
        envoient vers un Ollama local. La règle « vendor/modèle » doit
        donc passer AVANT elle.
        """
        for identifiant in (
            "mistralai/mistral-small-3.2-24b-instruct",
            "qwen/qwen3-8b",
            "deepseek/deepseek-chat",
        ):
            modele = AIModel.objects.create(
                name=identifiant, model_choice=identifiant,
            )
            modele.refresh_from_db()
            self.assertEqual(
                modele.provider, Provider.COMPATIBLE_OPENAI,
                f"{identifiant} devrait être servi par une API compatible",
            )

    def test_un_provider_explicite_survit_a_la_table_de_prefixes(self):
        """
        Chez Mistral en direct, l'identifiant n'a pas de barre oblique :
        `mistral-small-latest` matche le préfixe « mistral » et partirait
        vers Ollama. Un provider posé explicitement doit gagner.
        """
        modele = AIModel.objects.create(
            name="Mistral en direct", model_choice="mistral-small-latest",
            provider=Provider.COMPATIBLE_OPENAI,
            base_url="https://api.mistral.ai/v1",
            variable_de_cle_api="MISTRAL_API_KEY",
        )
        modele.refresh_from_db()
        self.assertEqual(modele.provider, Provider.COMPATIBLE_OPENAI)
        self.assertEqual(modele.technical_model_name, "mistral-small-latest")


class AppelCompatibleOpenAITest(TestCase):
    """L'appel lui-meme. / The call itself."""

    def setUp(self):
        self.modele = AIModel.objects.create(
            name="Juge par routeur",
            model_choice="mistralai/mistral-small-3.2-24b-instruct",
            base_url="https://openrouter.ai/api/v1",
            variable_de_cle_api="OPENROUTER_API_KEY",
        )

    def _appeler(self, reponse, cles=None):
        from core.llm_providers import appeler_llm

        client = MagicMock()
        client.chat.completions.create.return_value = reponse
        environnement = cles if cles is not None else {
            "OPENROUTER_API_KEY": "cle-de-test",
        }
        with patch("openai.OpenAI", return_value=client) as fabrique, \
             patch.dict("os.environ", environnement):
            texte = appeler_llm(self.modele, "Une question")
        return texte, fabrique, client

    def test_l_appel_part_vers_la_base_url_de_la_ligne(self):
        """La plateforme est décidée par `base_url`, pas par du code."""
        _texte, fabrique, client = self._appeler(_reponse_de_chat("ok"))

        arguments = fabrique.call_args[1]
        self.assertEqual(arguments["base_url"], "https://openrouter.ai/api/v1")
        self.assertEqual(arguments["api_key"], "cle-de-test")
        self.assertEqual(
            client.chat.completions.create.call_args[1]["model"],
            "mistralai/mistral-small-3.2-24b-instruct",
        )

    def test_le_timeout_et_les_tentatives_sont_explicites(self):
        """
        Le défaut du SDK est de 600 s en lecture, et il retente deux
        fois : une tâche pendue mobiliserait un worker une demi-heure,
        soit la limite de temps de Celery.
        """
        _texte, fabrique, _client = self._appeler(_reponse_de_chat("ok"))

        arguments = fabrique.call_args[1]
        self.assertIn("timeout", arguments)
        self.assertLess(arguments["timeout"], 600)
        self.assertIn("max_retries", arguments)

    def test_le_texte_de_la_reponse_est_rendu(self):
        """Le contrat de `appeler_llm` reste : du texte, rien d'autre."""
        texte, _fabrique, _client = self._appeler(
            _reponse_de_chat("La réponse du juge"),
        )
        self.assertEqual(texte, "La réponse du juge")

    def test_un_corps_d_erreur_en_200_leve(self):
        """
        Un routeur peut répondre 200 avec un corps d'erreur. Rendre une
        chaîne vide ferait lire une panne comme un verdict manquant.
        """
        reponse = MagicMock()
        reponse.choices = []
        reponse.error = {"message": "upstream indisponible", "code": 502}

        with self.assertRaises(RuntimeError) as contexte:
            self._appeler(reponse)
        self.assertIn("upstream indisponible", str(contexte.exception))

    def test_une_reponse_sans_choix_leve(self):
        """Zéro choix, c'est une panne, pas une réponse vide."""
        reponse = MagicMock()
        reponse.choices = []
        reponse.error = None

        with self.assertRaises(RuntimeError):
            self._appeler(reponse)

    def test_un_choix_sans_contenu_leve(self):
        """
        Un contenu ABSENT n'est pas un contenu vide : rendre « » ferait
        lire une réponse malformée comme vingt paires examinées sans
        conclusion.
        """
        message = MagicMock()
        message.content = None
        choix = MagicMock()
        choix.message = message
        reponse = MagicMock()
        reponse.choices = [choix]
        reponse.error = None

        with self.assertRaises(RuntimeError):
            self._appeler(reponse)

    def test_une_cle_absente_de_l_environnement_leve_en_la_nommant(self):
        """Le message dit QUELLE variable manque, pas « clé manquante »."""
        from core.llm_providers import appeler_llm

        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ValueError) as contexte:
                appeler_llm(self.modele, "Une question")
        self.assertIn("OPENROUTER_API_KEY", str(contexte.exception))

    def test_une_ligne_sans_variable_de_cle_leve(self):
        """
        Une ligne qui ne dit pas où est sa clé ne peut pas appeler :
        deviner la variable d'environnement d'après l'URL serait un
        piège de plus.
        """
        from core.llm_providers import appeler_llm

        modele_muet = AIModel.objects.create(
            name="Sans clé nommée", model_choice="openai/gpt-4o-mini",
            base_url="https://openrouter.ai/api/v1",
        )
        with self.assertRaises(ValueError):
            appeler_llm(modele_muet, "Une question")


class UnePlateformeSansBarreObliqueTest(TestCase):
    """
    Une plateforme dont les identifiants n'ont PAS de barre oblique.
    / A platform whose model ids carry no slash.

    LOCALISATION : core/tests/test_chemin_compatible_openai.py

    C'est le cas d'orq.ai (`https://api.orq.ai/v3/router`, modèles nommés
    `gpt-4`, `mistral-large`…) et de Mistral en direct. La règle
    « `vendor/modele` » ne les rattrape donc PAS : c'est le provider posé
    explicitement qui les sauve. Sans lui, un identifiant commençant par
    « mistral », « qwen », « deepseek » ou « phi » matcherait la table de
    préfixes et partirait vers un Ollama local qui n'existe pas — en
    silence, et le juge rendrait « connexion refusée » pour toute réponse.
    / Slash-less ids are saved by the explicit provider, not by the
    `vendor/model` rule.
    """

    def test_un_identifiant_sans_barre_oblique_reste_sur_sa_plateforme(self):
        """L'appel part vers la plateforme, pas vers un Ollama local."""
        from core.llm_providers import appeler_llm

        modele = AIModel.objects.create(
            name="Juge par orq", model_choice="mistral-large",
            provider=Provider.COMPATIBLE_OPENAI,
            base_url="https://api.orq.ai/v3/router",
            variable_de_cle_api="ORQ_API_KEY",
        )
        modele.refresh_from_db()
        self.assertEqual(modele.provider, Provider.COMPATIBLE_OPENAI)

        client = MagicMock()
        client.chat.completions.create.return_value = _reponse_de_chat("ok")
        with patch("openai.OpenAI", return_value=client) as fabrique, \
             patch.dict("os.environ", {"ORQ_API_KEY": "cle-orq"}):
            appeler_llm(modele, "Une question")

        arguments = fabrique.call_args[1]
        self.assertEqual(arguments["base_url"], "https://api.orq.ai/v3/router")
        self.assertEqual(arguments["api_key"], "cle-orq")
        self.assertEqual(
            client.chat.completions.create.call_args[1]["model"],
            "mistral-large",
        )


class OllamaPasseParLeMemeCheminTest(TestCase):
    """
    Ollama expose lui aussi une API compatible : il n'a pas besoin de
    son propre code. / Ollama exposes the same API; no code of its own.
    """

    def setUp(self):
        self.modele_ollama = AIModel.objects.create(
            name="Ollama local", model_choice="llama3",
            base_url="http://gpu-maison:11434",
        )

    def test_ollama_appelle_l_endpoint_compatible(self):
        """`{base_url}/v1`, et non l'API propriétaire `/api/generate`."""
        from core.llm_providers import appeler_llm

        client = MagicMock()
        client.chat.completions.create.return_value = _reponse_de_chat("ok")
        with patch("openai.OpenAI", return_value=client) as fabrique, \
             patch.dict("os.environ", {}, clear=True):
            appeler_llm(self.modele_ollama, "Une question")

        self.assertEqual(
            fabrique.call_args[1]["base_url"], "http://gpu-maison:11434/v1",
        )

    def test_ollama_recoit_une_cle_factice(self):
        """
        Ollama n'exige aucune clé, mais le SDK en réclame une : on lui
        en donne une fausse, et on le dit.
        """
        from core.llm_providers import appeler_llm

        client = MagicMock()
        client.chat.completions.create.return_value = _reponse_de_chat("ok")
        with patch("openai.OpenAI", return_value=client) as fabrique, \
             patch.dict("os.environ", {}, clear=True):
            appeler_llm(self.modele_ollama, "Une question")

        self.assertTrue(fabrique.call_args[1]["api_key"])


class LeReferentielEtSesTarifsTest(TestCase):
    """
    Tout modele du referentiel a un tarif connu.
    / Every listed model has a known price.

    LOCALISATION : core/tests/test_chemin_compatible_openai.py

    `cout_par_million_tokens()` rend None quand le tarif est inconnu, et
    l'ecran de confirmation affiche alors « non mesuré ». C'est le bon
    comportement pour un identifiant de plateforme — mais pour un modele
    QU'ON PROPOSE dans le referentiel, c'est un oubli : on offre au clic
    un modele dont on ne sait pas dire le prix avant de lancer.
    / A listed model with no price means offering a model whose cost we
    cannot state before launching it.
    """

    def test_chaque_choix_du_referentiel_a_un_tarif(self):
        """Un modèle proposé sans tarif est un prix qu'on ne peut pas dire."""
        from core.models import AIModelChoices

        sans_tarif = [
            choix.value for choix in AIModelChoices
            if choix.value.lower() not in AIModel.TARIFS_PAR_MILLION_TOKENS
        ]
        self.assertEqual(
            sans_tarif, [],
            f"Ces choix n'ont pas de tarif dans "
            f"TARIFS_PAR_MILLION_TOKENS : {sans_tarif}",
        )

    def test_les_modeles_gemini_de_troisieme_generation_sont_proposables(self):
        """
        Le référentiel doit suivre le catalogue servi. `gemini-2.5-flash-lite`
        répond 404 « no longer available to new users » depuis Google, qui
        renvoie vers la génération 3.x : un référentiel figé propose au
        clic des modèles qui n'existent plus.
        """
        from core.models import AIModelChoices

        valeurs = {choix.value for choix in AIModelChoices}
        for modele_attendu in (
            "gemini-3.1-flash-lite", "gemini-3.5-flash-lite",
            "gemini-3.5-flash",
        ):
            self.assertIn(modele_attendu, valeurs)


class LaTemperatureEstTransmiseTest(TestCase):
    """
    La temperature de la ligne arrive jusqu'a l'appel.
    / The row's temperature reaches the call.

    LOCALISATION : core/tests/test_chemin_compatible_openai.py

    POURQUOI CE TEST EXISTE. `AIModel.temperature` etait declare depuis
    l'origine et n'etait passe A AUCUN appel : tous les modeles
    tournaient a la temperature par defaut de leur fournisseur, celle de
    Gemini valant 1,0. Mesure du 17 aout 2026 : le juge de reference
    rejouant SES PROPRES 145 paires n'a retrouve que **128** de ses
    verdicts — 88 %, et **16 des 17 desaccords** faisaient passer un
    « faible » en « soutient ».

    Un verdict oppposable qui ne se reproduit pas n'est pas opposable.
    Un juge se regle donc a 0, et pour cela il faut d'abord que le champ
    SERVE.
    / The field was declared and never passed: every call ran at the
    provider's default (1.0 for Gemini). Re-judging its own 145 pairs,
    the reference judge reproduced only 128 of its verdicts.
    """

    def test_le_chemin_compatible_transmet_la_temperature(self):
        """La température de la ligne part avec la requête."""
        from core.llm_providers import appeler_llm

        modele = AIModel.objects.create(
            name="Juge à froid", model_choice="openai/gpt-4o-mini",
            base_url="https://openrouter.ai/api/v1",
            variable_de_cle_api="OPENROUTER_API_KEY",
            temperature=0.0,
        )
        client = MagicMock()
        client.chat.completions.create.return_value = _reponse_de_chat("ok")
        with patch("openai.OpenAI", return_value=client), \
             patch.dict("os.environ", {"OPENROUTER_API_KEY": "cle"}):
            appeler_llm(modele, "Une question")

        self.assertEqual(
            client.chat.completions.create.call_args[1]["temperature"], 0.0,
        )

    def test_google_transmet_la_temperature(self):
        """Le SDK de Google la reçoit dans sa configuration de génération."""
        from core.llm_providers import appeler_llm

        modele = AIModel.objects.create(
            name="Juge Gemini à froid", model_choice="gemini-2.5-flash",
            temperature=0.0,
        )
        reponse = MagicMock()
        reponse.text = "1: soutient"
        modele_genai = MagicMock()
        modele_genai.generate_content.return_value = reponse

        with patch("google.generativeai.configure"), \
             patch("google.generativeai.GenerativeModel",
                   return_value=modele_genai), \
             patch.dict("os.environ", {"GOOGLE_API_KEY": "cle"}):
            appeler_llm(modele, "Une question")

        configuration = modele_genai.generate_content.call_args[1][
            "generation_config"
        ]
        self.assertEqual(configuration["temperature"], 0.0)

    def test_anthropic_transmet_la_temperature(self):
        """Le SDK d'Anthropic aussi."""
        from core.llm_providers import appeler_llm

        modele = AIModel.objects.create(
            name="Juge Claude à froid",
            model_choice="claude-haiku-4-20250414", temperature=0.0,
        )
        bloc = MagicMock()
        bloc.text = "1: soutient"
        reponse = MagicMock()
        reponse.content = [bloc]
        client = MagicMock()
        client.messages.create.return_value = reponse

        with patch("anthropic.Anthropic", return_value=client), \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "cle"}):
            appeler_llm(modele, "Une question")

        self.assertEqual(
            client.messages.create.call_args[1]["temperature"], 0.0,
        )


class UneTemperatureAbsenteNEstPasTransmiseTest(TestCase):
    """
    `temperature = None` veut dire « ne transmets rien ».
    / `temperature = None` means "do not send the parameter".

    LOCALISATION : core/tests/test_chemin_compatible_openai.py

    POURQUOI CE BESOIN EXISTE. Les modeles de raisonnement d'OpenAI
    REFUSENT toute temperature autre que leur defaut. Mesure du 17 aout
    2026, `gpt-5-mini` et `gpt-5-nano` :

        400 — Unsupported value: 'temperature' does not support 0.0 with
        this model. Only the default (1) value is supported.

    Transmettre systematiquement le champ rendait donc ces modeles
    INUTILISABLES par `appeler_llm`. Un `None` distinct de `0.0` est la
    seule facon d'exprimer « laisse le fournisseur decider » — et il ne
    se confond pas avec « je veux zero », qui est le reglage d'un juge.
    / OpenAI reasoning models reject any temperature but their default;
    None is the only way to express "let the provider decide", and it
    must not be confused with 0.0, which is a judge's setting.
    """

    def test_une_temperature_nulle_n_est_pas_envoyee(self):
        """Le paramètre est absent de la requête, pas mis à zéro."""
        from core.llm_providers import appeler_llm

        modele = AIModel.objects.create(
            name="Modèle de raisonnement", model_choice="gpt-5-mini",
            provider=Provider.COMPATIBLE_OPENAI,
            base_url="https://api.openai.com/v1",
            variable_de_cle_api="OPENAI_API_KEY",
            temperature=None,
        )
        client = MagicMock()
        client.chat.completions.create.return_value = _reponse_de_chat("ok")
        with patch("openai.OpenAI", return_value=client), \
             patch.dict("os.environ", {"OPENAI_API_KEY": "cle"}):
            appeler_llm(modele, "Une question")

        self.assertNotIn(
            "temperature", client.chat.completions.create.call_args[1],
        )

    def test_zero_reste_transmis(self):
        """« Je veux zéro » n'est pas « laisse le fournisseur décider »."""
        from core.llm_providers import appeler_llm

        modele = AIModel.objects.create(
            name="Juge à froid", model_choice="openai/gpt-4o-mini",
            base_url="https://openrouter.ai/api/v1",
            variable_de_cle_api="OPENROUTER_API_KEY", temperature=0.0,
        )
        client = MagicMock()
        client.chat.completions.create.return_value = _reponse_de_chat("ok")
        with patch("openai.OpenAI", return_value=client), \
             patch.dict("os.environ", {"OPENROUTER_API_KEY": "cle"}):
            appeler_llm(modele, "Une question")

        self.assertEqual(
            client.chat.completions.create.call_args[1]["temperature"], 0.0,
        )

    def test_google_n_envoie_pas_de_configuration_vide(self):
        """Chez Google aussi, None veut dire « ne transmets rien »."""
        from core.llm_providers import appeler_llm

        modele = AIModel.objects.create(
            name="Gemini sans température", model_choice="gemini-2.5-flash",
            temperature=None,
        )
        reponse = MagicMock()
        reponse.text = "ok"
        modele_genai = MagicMock()
        modele_genai.generate_content.return_value = reponse

        with patch("google.generativeai.configure"), \
             patch("google.generativeai.GenerativeModel",
                   return_value=modele_genai), \
             patch.dict("os.environ", {"GOOGLE_API_KEY": "cle"}):
            appeler_llm(modele, "Une question")

        self.assertNotIn(
            "generation_config",
            modele_genai.generate_content.call_args[1],
        )
