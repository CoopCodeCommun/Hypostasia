# PHASE-24 : Providers IA unifies

**Date :** 2026-03-15
**Migration :** Oui

**Quoi / What:** Couche d'abstraction unique `core/llm_providers.py` pour les appels LLM directs.
Ajout de 2 nouveaux providers : Ollama (local) et Anthropic (Claude).
Suppression du code mort `core/services.py`.

**Pourquoi / Why:** 3 chemins d'appel LLM disperses dans le code. Cette phase les unifie
en un seul point d'entree `appeler_llm()` et ajoute le support Ollama (gratuit, local)
et Anthropic Claude (reformulation/restitution uniquement).

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `pyproject.toml` | Ajout dependance `anthropic>=0.40` |
| `core/models.py` | Provider +2 (OLLAMA, ANTHROPIC), AIModelChoices +9 modeles, champ `base_url`, prefix_to_provider etendu, tarifs |
| `core/llm_providers.py` | **Nouveau** — fonction unique `appeler_llm()` dispatche vers 5 providers |
| `core/migrations/0020_*.py` | **Nouveau** — migration auto (base_url + choices) |
| `front/tasks.py` | Supprime `_appeler_llm_reformulation()`, remplace par `appeler_llm()` |
| `hypostasis_extractor/services.py` | Ajout Ollama (model_url) et Anthropic (ValueError) dans `resolve_model_params()` |
| `core/services.py` | **Supprime** — code mort (dispatch legacy) |
| `front/tests/test_phases.py` | +10 tests unitaires PHASE-24 |
| `PLAN/PHASES/INDEX.md` | PHASE-24 cochee |

### Migration
- **Migration necessaire / Migration required:** Oui
- `uv run python manage.py migrate` — ajoute `base_url` sur `AIModel`, etend les choices

