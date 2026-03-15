"""
Couche d'abstraction unique pour les appels LLM directs (reformulation, restitution).
Un seul point d'entree : appeler_llm(modele_ia, message_complet) -> str
/ Unified abstraction layer for direct LLM calls (reformulation, restitution).
Single entry point: appeler_llm(modele_ia, message_complet) -> str

LOCALISATION : core/llm_providers.py

Ce module ne gere PAS l'extraction structuree (LangExtract).
Pour l'extraction, voir hypostasis_extractor/services.py (resolve_model_params).
/ This module does NOT handle structured extraction (LangExtract).
For extraction, see hypostasis_extractor/services.py (resolve_model_params).

DEPENDENCIES :
- google.generativeai (SDK Google Gemini)
- openai (SDK OpenAI)
- requests (appels HTTP vers Ollama)
- anthropic (SDK Anthropic Claude)
Les imports sont faits a l'interieur de chaque fonction pour ne charger
que le SDK necessaire au provider appele.
/ Imports are inside each function to load only the needed SDK.
"""

import logging

from core.models import Provider

logger = logging.getLogger(__name__)


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
    Appelants : front/tasks.py (reformuler_entite_task, restituer_debat_task)
    / Callers: front/tasks.py (reformuler_entite_task, restituer_debat_task)
    """
    provider = modele_ia.provider

    if provider == Provider.MOCK:
        return _appeler_mock(message_complet)

    elif provider == Provider.GOOGLE:
        return _appeler_google(modele_ia, message_complet)

    elif provider == Provider.OPENAI:
        return _appeler_openai(modele_ia, message_complet)

    elif provider == Provider.OLLAMA:
        return _appeler_ollama(modele_ia, message_complet)

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


def _appeler_google(modele_ia, message_complet: str) -> str:
    """
    Appelle Google Gemini via le SDK google-generativeai.
    Configure la cle API si presente, puis envoie le message complet.
    / Calls Google Gemini via the google-generativeai SDK.

    LOCALISATION : core/llm_providers.py
    """
    import google.generativeai as genai

    if modele_ia.api_key:
        genai.configure(api_key=modele_ia.api_key)

    nom_modele = modele_ia.model_name or modele_ia.model_choice
    modele_genai = genai.GenerativeModel(nom_modele)

    logger.info("appeler_llm: Google %s — %d chars", nom_modele, len(message_complet))
    reponse = modele_genai.generate_content(message_complet)
    return reponse.text


def _appeler_openai(modele_ia, message_complet: str) -> str:
    """
    Appelle OpenAI via le SDK openai.
    Envoie le message dans un chat.completions.create avec role=user.
    / Calls OpenAI via the openai SDK.

    LOCALISATION : core/llm_providers.py
    """
    from openai import OpenAI

    client = OpenAI(api_key=modele_ia.api_key)
    nom_modele = modele_ia.model_name or modele_ia.model_choice

    logger.info("appeler_llm: OpenAI %s — %d chars", nom_modele, len(message_complet))
    reponse = client.chat.completions.create(
        model=nom_modele,
        messages=[{"role": "user", "content": message_complet}],
    )
    return reponse.choices[0].message.content


def _appeler_ollama(modele_ia, message_complet: str) -> str:
    """
    Appelle un serveur Ollama local via son API REST (POST /api/generate).
    Utilise base_url du modele ou localhost:11434 par defaut.
    Le mode stream est desactive pour recevoir la reponse complete en une fois.
    / Calls a local Ollama server via its REST API (POST /api/generate).

    LOCALISATION : core/llm_providers.py
    """
    import requests

    base_url_ollama = modele_ia.base_url or "http://localhost:11434"
    nom_modele = modele_ia.model_name or modele_ia.model_choice
    url_generate = f"{base_url_ollama}/api/generate"

    logger.info("appeler_llm: Ollama %s @ %s — %d chars", nom_modele, base_url_ollama, len(message_complet))

    reponse_http = requests.post(
        url_generate,
        json={
            "model": nom_modele,
            "prompt": message_complet,
            "stream": False,
        },
        timeout=120,
    )
    reponse_http.raise_for_status()

    donnees_reponse = reponse_http.json()
    return donnees_reponse.get("response", "")


def _appeler_anthropic(modele_ia, message_complet: str) -> str:
    """
    Appelle Anthropic Claude via le SDK anthropic.
    Envoie un message unique avec max_tokens=4096 et extrait le premier bloc texte.
    / Calls Anthropic Claude via the anthropic SDK.

    LOCALISATION : core/llm_providers.py
    """
    import anthropic

    client = anthropic.Anthropic(api_key=modele_ia.api_key)
    nom_modele = modele_ia.model_name or modele_ia.model_choice

    logger.info("appeler_llm: Anthropic %s — %d chars", nom_modele, len(message_complet))

    reponse = client.messages.create(
        model=nom_modele,
        max_tokens=4096,
        messages=[{"role": "user", "content": message_complet}],
    )

    # Extraire le texte du premier bloc de contenu
    # / Extract text from the first content block
    return reponse.content[0].text
