# PHASE-24 — Providers IA unifies

**Complexite** : L | **Mode** : Plan then normal | **Prerequis** : PHASE-03

> **Note PHASE-26g (2026-03-18)** : le `NotificationConsumer` WebSocket gere maintenant
> 3 types de messages pour l'analyse : `analyse_progression` (barre par chunk),
> `extraction_carte` (carte temps reel + texte annote OOB), et `analyse_terminee`
> (signal de fin qui declenche le chargement du drawer final via `hx-trigger="load"`).
> Le pattern est extensible pour d'autres taches Celery (reformulation, restitution).
> Le `MULTIPLICATEUR_THINKING` dans `AIModel` est configurable par modele — a etendre
> quand de nouveaux providers avec thinking seront ajoutes.

---

## 1. Contexte

Actuellement les appels LLM sont disperses dans plusieurs fichiers avec des implementations ad hoc par provider (Gemini, OpenAI, Mock pour l'extraction ; Voxtral/Mock pour la transcription). Cette phase cree une couche d'abstraction unique pour tous les appels LLM (extraction, reformulation, restitution, transcription), etend le modele AIModel pour les nouveaux providers (Ollama, Anthropic), et unifie la transcription audio en multi-provider.

## 2. Prerequis

PHASE-03 (config IA et toggle provider) doit etre terminee — elle pose le modele `AIModel` de base et le mecanisme de selection de provider.

## 3. Objectifs precis

> **Attention** : LangExtract ne supporte que Gemini et OpenAI pour l'extraction. Les nouveaux backends (Ollama, Anthropic) ne peuvent etre utilises que pour la reformulation, la restitution et la transcription, pas pour l'extraction LangExtract.

### Etape 3.1 — Couche d'abstraction LLM

- [ ] Creer `core/llm_providers.py` avec une interface commune : `appeler_llm(modele, messages, **kwargs) -> str`
- [ ] Implementer les backends : `GoogleGeminiBackend`, `OpenAIBackend`, `OllamaBackend`, `AnthropicBackend`, `MockBackend`
- [ ] Pour Ollama : utiliser l'API compatible OpenAI (`base_url` parametrable)
- [ ] Pour Anthropic : utiliser le SDK `anthropic`
- [ ] Migrer `_appeler_llm_reformulation` (front/tasks.py) vers cette couche
- [ ] Migrer `resolve_model_params` (hypostasis_extractor/services.py) vers cette couche

### Etape 3.2 — Modele AIModel etendu

- [ ] Ajouter les providers Ollama et Anthropic dans `Provider` TextChoices
- [ ] Ajouter les modeles Ollama (llama3, mistral, etc.) et Anthropic (claude-sonnet, claude-haiku) dans `AIModelChoices`
- [ ] Ajouter un champ `base_url` sur `AIModel` pour Ollama et endpoints custom
- [ ] Mettre a jour le mapping `prefix_to_provider` dans `AIModel.save()`

### Etape 3.3 — Transcription audio multi-provider

- [ ] Ajouter Whisper (OpenAI) comme provider de transcription
- [ ] Ajouter un backend local (whisper.cpp ou faster-whisper via Ollama)
- [ ] Unifier la transcription avec la couche d'abstraction

### Tests

- [ ] Analyse IA avec chaque provider (mock) : verifier extractions
- [ ] Reformulation avec provider alterne
- [ ] Transcription audio avec Whisper mock

## 4. Fichiers a modifier

- `core/llm_providers.py` — nouveau fichier, couche d'abstraction LLM
- `core/models.py` — extension du modele `AIModel` (providers, base_url) + migration
- `hypostasis_extractor/services.py` — migration de `resolve_model_params` vers la couche d'abstraction
- `front/tasks.py` — migration de `_appeler_llm_reformulation` vers la couche d'abstraction
- `front/services/transcription_audio.py` — ajout Whisper + backend local + unification
- `core/models.py` — ajout `TranscriptionConfig` si necessaire
- `pyproject.toml` — ajout de la dependance `anthropic`

## 5. Criteres de validation

- [ ] `appeler_llm()` fonctionne avec chaque backend (teste avec MockBackend au minimum)
- [ ] Les providers Ollama et Anthropic apparaissent dans le choix de modele IA
- [ ] Le champ `base_url` est disponible pour Ollama dans le modele AIModel
- [ ] `_appeler_llm_reformulation` n'existe plus en tant que code ad hoc — tout passe par `core/llm_providers.py`
- [ ] `resolve_model_params` est simplifie ou supprime — la resolution passe par la couche d'abstraction
- [ ] La transcription audio fonctionne avec Voxtral (existant) et Whisper (nouveau)
- [ ] `uv run python manage.py check` passe
- [ ] Les tests unitaires et mock passent pour tous les providers

## 5b. Verification navigateur

> Lancer `uv run python manage.py runserver` et ouvrir http://localhost:8000/

1. **Configurer un provider Ollama local (si disponible) ou simuler avec un mock**
   - **Attendu** : le provider est reconnu par le systeme
2. **Ouvrir la config IA (toggle dans l'interface)**
   - **Attendu** : les providers disponibles sont listes (OpenAI, Anthropic, Ollama, Gemini)
3. **Selectionner un provider different — lancer une extraction**
   - **Attendu** : elle fonctionne avec le nouveau provider
4. **Verifier la transcription : si Whisper est configure, importer un audio**
   - **Attendu** : la transcription utilise Whisper au lieu de Voxtral

## 6. Extraits du PLAN.md

> ## 4. Phase 3 — Providers IA unifies
>
> Objectif : une couche d'abstraction unique pour tous les appels LLM (extraction, reformulation, restitution, transcription).
>
> ### Etat actuel des providers
>
> | Fonctionnalite | Providers supportes | Code |
> |----------------|---------------------|------|
> | Extraction LangExtract | Google Gemini, OpenAI GPT | `hypostasis_extractor/services.py:resolve_model_params` |
> | Reformulation | Google Gemini, OpenAI GPT, Mock | `front/tasks.py:_appeler_llm_reformulation` |
> | Restitution | idem reformulation | `front/tasks.py:restituer_debat_task` |
> | Transcription audio | Voxtral (Mistral), Mock | `front/services/transcription_audio.py` |
>
> ### Etape 3.1 — Couche d'abstraction LLM
>
> **Actions** :
> - [ ] Creer `core/llm_providers.py` avec une interface commune : `appeler_llm(modele, messages, **kwargs) -> str`
> - [ ] Implementer les backends : `GoogleGeminiBackend`, `OpenAIBackend`, `OllamaBackend`, `AnthropicBackend`, `MockBackend`
> - [ ] Pour Ollama : utiliser l'API compatible OpenAI (`base_url` parametrable)
> - [ ] Pour Anthropic : utiliser le SDK `anthropic`
> - [ ] Migrer `_appeler_llm_reformulation` et `resolve_model_params` vers cette couche
>
> **Strategie LangExtract** : LangExtract est la dependance structurante pour l'extraction. Elle ne supporte que Gemini et OpenAI.
> - Court terme : garder LangExtract tel quel, ca fonctionne
> - Moyen terme : contribuer au repo open-source pour ajouter les providers Ollama et Anthropic (PR upstream)
> - Si le merge est refuse : forker la lib et maintenir notre version
> - La couche d'abstraction LLM (`core/llm_providers.py`) est concue pour que ce remplacement soit possible sans toucher au reste du code
>
> ### Etape 3.2 — Modele AIModel etendu
>
> **Actions** :
> - [ ] Ajouter les providers Ollama et Anthropic dans `Provider` TextChoices
> - [ ] Ajouter les modeles Ollama (llama3, mistral, etc.) et Anthropic (claude-sonnet, claude-haiku) dans `AIModelChoices`
> - [ ] Ajouter un champ `base_url` sur `AIModel` pour Ollama et endpoints custom
> - [ ] Mettre a jour le mapping `prefix_to_provider` dans `AIModel.save()`
>
> ### Etape 3.3 — Transcription audio multi-provider
>
> **Actions** :
> - [ ] Ajouter Whisper (OpenAI) comme provider de transcription
> - [ ] Ajouter un backend local (whisper.cpp ou faster-whisper via Ollama)
> - [ ] Unifier avec la couche d'abstraction
>
> ### Tests E2E Phase 3
>
> - [ ] Analyse IA avec chaque provider (mock) : verifier extractions
> - [ ] Reformulation avec provider alterne
> - [ ] Transcription audio avec Whisper mock
