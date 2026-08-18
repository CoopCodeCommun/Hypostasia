"""
Couche d'abstraction unique pour les appels LLM directs (synthese).
Un seul point d'entree : appeler_llm(modele_ia, message_complet) -> str
/ Unified abstraction layer for direct LLM calls (synthesis).
Single entry point: appeler_llm(modele_ia, message_complet) -> str

LOCALISATION : core/llm_providers.py

Ce module ne gere PAS l'extraction structuree (LangExtract).
Pour l'extraction, voir hypostasis_extractor/services/__init__.py (resolve_model_params).
/ This module does NOT handle structured extraction (LangExtract).
For extraction, see hypostasis_extractor/services/__init__.py (resolve_model_params).

DEPENDENCIES :
- openai (SDK OpenAI) — sert AUSSI toutes les plateformes compatibles :
  OpenRouter, Mistral, Scaleway, un serveur Ollama local. C'est
  `base_url` qui les distingue, pas du code.
- google.generativeai (SDK Google Gemini) — deprecie en amont
- anthropic (SDK Anthropic Claude)
Les imports sont faits a l'interieur de chaque fonction pour ne charger
que le SDK necessaire au provider appele.
/ The openai SDK also serves every OpenAI-compatible platform; base_url
tells them apart, not code.
"""

import logging
import os
import time

from core.models import Provider

logger = logging.getLogger(__name__)

# LE TIMEOUT EST EXPLICITE, ET C'EST LE POINT. Les SDK `openai` et
# `anthropic` posent 600 s en lecture par defaut : dix minutes pendant
# lesquelles un worker Celery — il y en a DEUX, a concurrence 2 — ne
# fait rien du tout. Avec leurs deux tentatives, un seul appel pendu
# atteint la demi-heure de `CELERY_TASK_TIME_LIMIT` et la tache est tuee
# en plein milieu, laissant son job en « processing » et l'ecran a
# interroger dans le vide.
# La valeur couvre large : une redaction d'article genere quelques
# milliers de tokens, un lot de juge en rend vingt lignes.
# / Explicit timeout: the SDK default of 600 s would idle a Celery
# worker for ten minutes and reach the 30-minute task limit.
DELAI_D_ATTENTE_SECONDES = 180

# Le nombre de tentatives que le SDK fait lui-meme, avec son propre
# backoff exponentiel. On NE l'enveloppe PAS d'une seconde boucle : 3 × 3
# donnerait neuf tentatives reseau et depasserait la limite de Celery.
# / Retries performed by the SDK itself, with its own exponential
# backoff. Never wrap this in a second loop.
NOMBRE_DE_TENTATIVES = 2

# Ollama n'exige aucune cle, mais le SDK OpenAI en reclame une. Valeur
# factice, assumee comme telle. / Ollama needs no key; the SDK does.
CLE_FACTICE_D_OLLAMA = "ollama-sans-cle"

# L'adresse d'un Ollama local, quand la ligne n'en donne pas.
# / A local Ollama, when the row gives no base_url.
BASE_URL_OLLAMA_PAR_DEFAUT = "http://localhost:11434"


def appeler_llm(modele_ia, message_complet: str) -> str:
    """
    Appelle le LLM selon le provider du modele et retourne la reponse texte.
    / Calls the LLM based on the model's provider and returns the text response.

    LOCALISATION : core/llm_providers.py

    FLUX :
    1. Lit modele_ia.provider pour determiner le fournisseur
    2. Dispatche vers la fonction interne du provider (_appeler_google, _appeler_ollama, etc.)
    3. Chaque fonction interne importe son SDK, appelle l'API, retourne le texte brut
    / 1. Reads modele_ia.provider  2. Dispatches to internal function  3. Returns raw text

    Providers supportes : MOCK, GOOGLE, OPENAI, OLLAMA, ANTHROPIC.
    / Supported providers: MOCK, GOOGLE, OPENAI, OLLAMA, ANTHROPIC.

    COMMUNICATION :
    Appelants : front/tasks.py (synthetiser_page_task)
    / Callers: front/tasks.py (synthetiser_page_task)
    """
    provider = modele_ia.provider

    # POURQUOI IL N'Y A PAS DE GARDE « PAS D'APPEL REEL SOUS TEST » ICI.
    #
    # Une telle garde a ete posee puis RETIREE le 17 aout 2026 : son
    # critere etait faux. Elle levait des qu'un test employait un
    # provider non-MOCK — or `Phase24LlmProviders*Test` eprouve
    # legitimement ce dispatch, SDK moque, sans qu'aucun appel ne sorte.
    # Impossible de distinguer ici un SDK patche d'un appel accidentel.
    #
    # Ce qui protege reellement, et qui tient :
    # - `AIModel.provider` vaut MOCK par DEFAUT (core/models.py) : un
    #   modele de test n'appelle personne sans qu'on l'ait voulu ;
    # - `CELERY_TASK_ALWAYS_EAGER` sous test (settings.py) : aucune tache
    #   ne sort vers le broker, donc aucune ne s'execute contre une autre
    #   base que celle du test ;
    # - les suites LLM reelles sont sous DOUBLE verrou, tag Django et
    #   variable TESTS_LLM_REELS.
    # / A "no real call under test" guard was added then removed: its
    # criterion could not tell a patched SDK from an accidental call.

    if provider == Provider.MOCK:
        return _appeler_mock(message_complet)

    elif provider == Provider.GOOGLE:
        return _appeler_google(modele_ia, message_complet)

    elif provider == Provider.OPENAI:
        return _appeler_openai(modele_ia, message_complet)

    elif provider == Provider.OLLAMA:
        return _appeler_ollama(modele_ia, message_complet)

    elif provider == Provider.COMPATIBLE_OPENAI:
        return _appeler_par_api_compatible(modele_ia, message_complet)

    elif provider == Provider.ANTHROPIC:
        return _appeler_anthropic(modele_ia, message_complet)

    else:
        raise ValueError(f"Provider '{provider}' non supporte pour appeler_llm")


# ---------------------------------------------------------------------------
# Implementations internes par provider
# / Internal implementations per provider
# ---------------------------------------------------------------------------


def _appeler_mock(message_complet: str) -> str:
    """
    Retourne un texte factice pour les tests sans appeler d'API externe.
    / Returns dummy text for testing without calling any external API.

    LOCALISATION : core/llm_providers.py
    """
    return f"[MOCK] Reformulation de : {message_complet[:200]}..."


def _reessayer_avec_backoff(appel, nom_du_service):
    """
    Retente un appel qui a echoue, avec un backoff exponentiel.
    / Retries a failed call with exponential backoff.

    LOCALISATION : core/llm_providers.py

    RESERVE AUX SDK QUI NE RETENTENT PAS D'EUX-MEMES. Les SDK `openai` et
    `anthropic` font deja deux tentatives avec leur propre backoff :
    envelopper l'un d'eux ici donnerait 3 × 3 = neuf tentatives reseau,
    et un seul appel pendu atteindrait la demi-heure de
    `CELERY_TASK_TIME_LIMIT`.

    On retente sur N'IMPORTE QUELLE exception plutot que sur une liste
    de types : le SDK de Google leve des classes qui lui sont propres, et
    une liste incomplete laisserait passer justement le cas qu'on veut
    couvrir. Une erreur definitive (requete invalide) echoue de toute
    facon trois fois de suite, en quelques millisecondes.
    / For SDKs that do not retry on their own. Retrying on any exception
    beats an incomplete list of exception types; a permanent error just
    fails three times fast.
    """
    derniere_erreur = None
    for numero_de_tentative in range(NOMBRE_DE_TENTATIVES + 1):
        try:
            return appel()
        except Exception as erreur:
            derniere_erreur = erreur
            if numero_de_tentative == NOMBRE_DE_TENTATIVES:
                break
            delai_avant_la_suivante = 2 ** numero_de_tentative
            logger.warning(
                "appeler_llm: %s a échoué (tentative %s/%s) — nouvelle "
                "tentative dans %s s : %s",
                nom_du_service, numero_de_tentative + 1,
                NOMBRE_DE_TENTATIVES + 1, delai_avant_la_suivante, erreur,
            )
            time.sleep(delai_avant_la_suivante)
    raise derniere_erreur


def _appeler_google(modele_ia, message_complet: str) -> str:
    """
    Appelle Google Gemini via le SDK google-generativeai.
    Configure la cle API si presente, puis envoie le message complet.
    / Calls Google Gemini via the google-generativeai SDK.

    LOCALISATION : core/llm_providers.py

    Ce SDK ne retente pas et ne pose aucun timeout par defaut : les deux
    sont donc explicites ici. Il est par ailleurs DEPRECIE en amont
    (`google.genai` le remplace) — une raison de plus pour que les
    plateformes compatibles OpenAI deviennent le chemin principal.
    / This SDK neither retries nor times out by default, and is
    deprecated upstream.
    """
    import google.generativeai as genai

    # Cle API depuis .env uniquement / API key from .env only
    cle_api_google = os.environ.get("GOOGLE_API_KEY", "")
    if cle_api_google:
        genai.configure(api_key=cle_api_google)

    nom_modele = modele_ia.model_name or modele_ia.model_choice
    modele_genai = genai.GenerativeModel(nom_modele)

    logger.info("appeler_llm: Google %s — %d chars", nom_modele, len(message_complet))
    # Meme regle que sur le chemin partage : une temperature absente ne
    # se transmet pas. / Same rule: an absent temperature is not sent.
    parametres_de_generation = {}
    if modele_ia.temperature is not None:
        parametres_de_generation["generation_config"] = {
            "temperature": modele_ia.temperature,
        }
    reponse = _reessayer_avec_backoff(
        lambda: modele_genai.generate_content(
            message_complet,
            request_options={"timeout": DELAI_D_ATTENTE_SECONDES},
            **parametres_de_generation,
        ),
        "Google",
    )
    return reponse.text


def _appeler_le_chemin_compatible(nom_modele, message_complet, cle_api,
                                  base_url, nom_du_service,
                                  temperature) -> str:
    """
    L'appel `POST {base_url}/chat/completions`, partage par toutes les
    plateformes qui l'exposent.
    / The shared OpenAI-compatible call.

    LOCALISATION : core/llm_providers.py

    UN SEUL CHEMIN, PARAMETRE PAR `base_url` : OpenAI, OpenRouter,
    Mistral, Scaleway, un Ollama local. Ecrire une implementation par
    plateforme, c'est ecrire N fois le meme timeout et la meme detection
    d'erreur — et n'en corriger qu'une le jour ou l'une des N est fausse.

    LE « HTTP 200 AVEC CORPS D'ERREUR » EST TRAITE ICI. Un routeur peut
    repondre 200 en portant l'echec dans le corps. Rendre alors une
    chaine vide ferait lire une PANNE comme un verdict manquant : le
    juge compterait des paires « sans verdict » alors que personne ne
    les a jamais vues.
    / A router may answer 200 with the failure in the body; returning ""
    would make a breakdown look like a missing verdict.

    :param nom_du_service: ce qu'on nomme dans les journaux et les erreurs
    """
    import openai

    client = openai.OpenAI(
        api_key=cle_api,
        base_url=base_url,
        timeout=DELAI_D_ATTENTE_SECONDES,
        max_retries=NOMBRE_DE_TENTATIVES,
    )

    logger.info(
        "appeler_llm: %s %s @ %s — %d chars",
        nom_du_service, nom_modele, base_url or "défaut du SDK",
        len(message_complet),
    )
    # Une temperature ABSENTE ne se transmet pas : les modeles de
    # raisonnement d'OpenAI refusent toute valeur autre que la leur, et
    # envoyer 0 leur arrache un 400. / An absent temperature is not sent.
    parametres_de_l_appel = {
        "model": nom_modele,
        "messages": [{"role": "user", "content": message_complet}],
    }
    if temperature is not None:
        parametres_de_l_appel["temperature"] = temperature

    reponse = client.chat.completions.create(**parametres_de_l_appel)

    erreur_dans_le_corps = getattr(reponse, "error", None)
    if erreur_dans_le_corps:
        raise RuntimeError(
            f"{nom_du_service} a répondu 200 avec une erreur dans le "
            f"corps : {erreur_dans_le_corps}"
        )
    if not reponse.choices:
        raise RuntimeError(
            f"{nom_du_service} n'a rendu aucun choix — réponse "
            f"inexploitable pour le modèle {nom_modele}."
        )
    texte_de_la_reponse = reponse.choices[0].message.content
    if texte_de_la_reponse is None:
        # ABSENCE de contenu, et non contenu vide : la reponse est
        # malformee. Rendre "" la ferait lire comme un modele qui n'a
        # rien a dire — et, pour le juge, comme vingt paires qu'il aurait
        # examinees sans conclure.
        # / A MISSING content field, not an empty one: returning ""
        # would read as twenty pairs examined without conclusion.
        raise RuntimeError(
            f"{nom_du_service} a rendu un choix sans contenu pour le "
            f"modèle {nom_modele}."
        )
    return texte_de_la_reponse


def _appeler_par_api_compatible(modele_ia, message_complet: str) -> str:
    """
    Appelle la plateforme designee par `base_url` (OpenRouter, Mistral,
    Scaleway…). / Calls the platform named by base_url.

    LOCALISATION : core/llm_providers.py

    LA CLE RESTE DANS L'ENVIRONNEMENT : la ligne en base dit seulement
    LAQUELLE lire, par `variable_de_cle_api`. Deviner la variable
    d'apres l'URL serait un piege de plus, et une regle a rallonger a
    chaque plateforme.
    / The key stays in the environment; the row only names which one.
    """
    nom_de_la_variable = (modele_ia.variable_de_cle_api or "").strip()
    if not nom_de_la_variable:
        raise ValueError(
            f"Le modèle « {modele_ia} » ne dit pas quelle variable "
            f"d'environnement porte sa clé : renseignez "
            f"`variable_de_cle_api` (ex: OPENROUTER_API_KEY)."
        )
    cle_api = os.environ.get(nom_de_la_variable, "")
    if not cle_api:
        raise ValueError(
            f"Clé API manquante : la variable {nom_de_la_variable} est "
            f"vide ou absente du .env."
        )
    if not modele_ia.base_url:
        raise ValueError(
            f"Le modèle « {modele_ia} » n'a pas de `base_url` : c'est "
            f"elle qui désigne la plateforme à appeler."
        )

    return _appeler_le_chemin_compatible(
        nom_modele=modele_ia.technical_model_name,
        message_complet=message_complet,
        cle_api=cle_api,
        base_url=modele_ia.base_url,
        nom_du_service=f"API compatible ({modele_ia.base_url})",
        temperature=modele_ia.temperature,
    )


def _appeler_openai(modele_ia, message_complet: str) -> str:
    """
    Appelle OpenAI par le chemin compatible, sans `base_url` : le SDK
    prend alors la sienne. / Calls OpenAI through the shared path.

    LOCALISATION : core/llm_providers.py
    """
    # Cle API depuis .env uniquement / API key from .env only
    cle_api_openai = os.environ.get("OPENAI_API_KEY", "")
    if not cle_api_openai:
        raise ValueError("Clé API OpenAI manquante. Renseignez OPENAI_API_KEY dans .env.")

    return _appeler_le_chemin_compatible(
        nom_modele=modele_ia.technical_model_name,
        message_complet=message_complet,
        cle_api=cle_api_openai,
        base_url=None,
        nom_du_service="OpenAI",
        temperature=modele_ia.temperature,
    )


def _appeler_ollama(modele_ia, message_complet: str) -> str:
    """
    Appelle un serveur Ollama par son endpoint COMPATIBLE `{base}/v1`,
    et non par l'API proprietaire `/api/generate`.
    / Calls an Ollama server through its OpenAI-compatible endpoint.

    LOCALISATION : core/llm_providers.py

    Passer par le chemin partage SUPPRIME du code au lieu d'en ajouter :
    le timeout, les tentatives et la detection d'erreur sont ceux de
    toutes les autres plateformes, et un serveur local devient un
    `base_url` comme un autre.
    / The shared path removes code instead of adding it.
    """
    base_url_ollama = modele_ia.base_url or BASE_URL_OLLAMA_PAR_DEFAUT

    return _appeler_le_chemin_compatible(
        nom_modele=modele_ia.technical_model_name,
        message_complet=message_complet,
        # Ollama n'exige aucune cle ; le SDK en reclame une.
        # / Ollama needs no key; the SDK does.
        cle_api=os.environ.get("OLLAMA_API_KEY") or CLE_FACTICE_D_OLLAMA,
        base_url=f"{base_url_ollama.rstrip('/')}/v1",
        nom_du_service="Ollama",
        temperature=modele_ia.temperature,
    )


def _appeler_anthropic(modele_ia, message_complet: str) -> str:
    """
    Appelle Anthropic Claude via le SDK anthropic.
    Envoie un message unique avec max_tokens=4096 et extrait le premier bloc texte.
    / Calls Anthropic Claude via the anthropic SDK.

    LOCALISATION : core/llm_providers.py
    """
    import anthropic

    # Cle API depuis .env uniquement / API key from .env only
    cle_api_anthropic = os.environ.get("ANTHROPIC_API_KEY", "")
    if not cle_api_anthropic:
        raise ValueError("Clé API Anthropic manquante. Renseignez ANTHROPIC_API_KEY dans .env.")
    # Le SDK retente deja deux fois avec son propre backoff ; seul le
    # timeout est a corriger, son defaut valant 600 s en lecture.
    # / The SDK already retries twice; only the 600 s default read
    # timeout needs correcting.
    client = anthropic.Anthropic(
        api_key=cle_api_anthropic,
        timeout=DELAI_D_ATTENTE_SECONDES,
        max_retries=NOMBRE_DE_TENTATIVES,
    )
    nom_modele = modele_ia.model_name or modele_ia.model_choice

    logger.info("appeler_llm: Anthropic %s — %d chars", nom_modele, len(message_complet))

    # Meme regle que partout : une temperature absente ne se transmet
    # pas. / Same rule: an absent temperature is not sent.
    parametres_de_l_appel = {
        "model": nom_modele,
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": message_complet}],
    }
    if modele_ia.temperature is not None:
        parametres_de_l_appel["temperature"] = modele_ia.temperature

    reponse = client.messages.create(**parametres_de_l_appel)

    # Extraire le texte du premier bloc de contenu
    # / Extract text from the first content block
    return reponse.content[0].text
