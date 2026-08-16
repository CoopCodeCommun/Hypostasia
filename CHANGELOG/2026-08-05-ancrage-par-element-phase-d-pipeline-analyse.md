# Ancrage par element, phase D : pipeline d'analyse + garde d'edition

**Date :** 2026-08-05
**Migration :** Non

**Quoi / What :** `services/analyse_par_element.py` (chunks -> LangExtract ->
ancres) et `services/garde_edition.py` (interdire l'edition pendant une analyse).

**Pourquoi / Why :** c'est la piece qui relie tout le reste. Le chunking (phase C)
decoupe sur les frontieres d'elements, le LLM analyse chaque chunk seul,
l'intersection (phase B) traduit les positions rendues en portions d'ancrage.
Verifie contre Gemini 2.5 Flash : sur une liste a puces de trois elements, le
modele rend un span qui les traverse tous les trois, et le pipeline produit trois
portions ordonnees pointant chacune le bon texte.

### Fichiers ajoutes / Added files
| Fichier / File | Role / Purpose |
|---|---|
| `hypostasis_extractor/services/analyse_par_element.py` | Pipeline d'analyse du moteur ELEMENT |
| `hypostasis_extractor/services/garde_edition.py` | Refus d'editer pendant une analyse |
| `hypostasis_extractor/tests/test_analyse_par_element.py` | 19 tests, LLM simule |
| `hypostasis_extractor/tests/test_analyse_llm_reel.py` | 3 tests d'integration, appels LLM reels |
| `hypostasis_extractor/tests/test_garde_edition.py` | 24 tests |

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `front/tasks.py` | `"updated_at"` ajoute aux `update_fields` des jobs (battement de coeur pour la garde d'edition) |
| `front/views.py` | `_refuser_si_une_analyse_tourne()` + garde sur `renommer_locuteur`, `editer_bloc`, `supprimer_bloc` |
| `services/reconciliation.py`, `moteur_structure.py`, `masquage.py`, `reingestion.py` | Appel de la garde en tete de chaque operation d'edition |

### Deux decisions du proprietaire / Two owner decisions
1. **Les gros elements partent entiers**, sans decoupage. `max_char_buffer` est
   calcule plus grand que le chunk pour que LangExtract le recoive tel quel.
   A noter : ca ne protege pas les positions (LangExtract les re-base de toute
   facon), ca garantit que le modele lit chaque element ENTIER, dans son
   contexte.
2. **L'edition est bloquee pendant une analyse.** Un delai de grace de 90 minutes
   empeche qu'un worker Celery interrompu condamne une page pour toujours — cas
   documente dans le CHANGELOG du 19 juin 2026.

### Defauts corriges apres relecture adverse / Fixed after adversarial review
| Defaut / Defect | Correction |
|---|---|
| `lx.extract` telecharge le texte s'il ressemble a une URL (`fetch_urls=True` par defaut) : un element qui est un lien nu aurait fait analyser la page distante, avec des ancres fausses et une requete sortante pilotee par le document ingere | `fetch_urls=False` |
| Une analyse dont TOUS les chunks echouent finissait `COMPLETED`, indiscernable d'une page sans rien a extraire | Passage en `ERROR`, et bilan persiste dans `raw_result` |
| Une extraction incoherente (span a l'envers) faisait tomber toute l'analyse | Attrapee par extraction, comptee dans `extractions_refusees` |
| Relancer un job dupliquait toutes ses extractions | Purge des entites du job avant analyse |
| Un JSON tronque par `max_output_tokens` perdait le chunk entier | `resolver_params={"suppress_parse_errors": True}` |
| `updated_at` n'etait jamais rafraichi : le delai de grace mesurait l'age depuis la creation, pas la vie du job | Battement de coeur dans `front/tasks.py`, et la garde regarde les deux dates |
| La garde ne protegeait que la couche elements, qu'aucun code n'appelle encore, alors que les vraies editions passent par `front/views.py` | Garde ajoutee sur les trois vues d'edition |

### Tests avec appels LLM reels / Real LLM tests
Ils coutent de l'argent et dependent de ce que le modele repond. Double verrou :
le tag `llm_reel` **et** la variable `TESTS_LLM_REELS`. Django n'excluant pas les
tags par defaut, le tag seul ne protegerait pas.

```bash
docker exec -e TESTS_LLM_REELS=1 hypostasia_dev_web \
    uv run python manage.py test hypostasis_extractor --tag=llm_reel
```

### Migration
- **Migration necessaire / Migration required :** Non.

### Ce qui reste avant utilisation / Remaining before use
Le pipeline n'est appele par aucune tache Celery ni vue. Il manque : la tache
Celery (avec `_check_ia_active`, notifications, progression), le bouton dans
l'interface, et le compteur de tokens que la spec section 4.2 declare necessaire.

