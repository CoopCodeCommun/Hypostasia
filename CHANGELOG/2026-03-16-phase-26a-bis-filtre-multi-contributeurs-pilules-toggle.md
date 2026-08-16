# PHASE-26a-bis : Filtre multi-contributeurs (pilules toggle)

**Date :** 2026-03-16
**Migration :** Non

**Quoi / What:** Remplacement du `<select>` mono-sélection contributeur par des pilules toggle
réutilisant le pattern `.pilule-locuteur` existant (PHASE-15). Supporte la sélection multiple :
cliquer plusieurs pilules → union des commentaires. Le paramètre `?contributeur=` accepte
désormais une liste séparée par virgules (`?contributeur=1,2,3`), rétro-compatible avec le
format single (`?contributeur=42`).

**Pourquoi / Why:** Le facilitateur veut comparer 2+ contributeurs ("qu'est-ce que Marie ET
Thomas ont dit ?"). Les pilules toggle survivent au swap HTMX, zéro JS custom fragile,
mobile-friendly, FALC.

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `front/views.py` | `drawer_contenu()` : parsing multi-IDs virgule-séparée, `user_id__in`, HX-Trigger `contributeurs_ids` (plural). Renommage `_calculer_scores_temperature_par_contributeurs()`. `LectureViewSet.retrieve()` : parsing multi-IDs. |
| `front/templates/front/includes/drawer_vue_liste.html` | Select+chip → pilules `.pilule-locuteur` toggle + bouton "Tous ×". Conditions `contributeur_actif` → `contributeurs_actifs` (set). |
| `front/static/front/js/drawer_vue_liste.js` | `getContributeursActuels()` (lecture pilules actives), handler clic pilule toggle, suppression handler select/chip. |
| `front/static/front/js/marginalia.js` | `contributeursFiltresActuels = []`, `appliquerFiltreContributeurs()` (array), listener `contributeurs_ids`. |
| `front/static/front/css/hypostasia.css` | +`.pilule-reset-contributeurs`, suppression `.chip-contributeur-actif` et `.btn-retirer-filtre-contributeur`. |
| `front/tests/test_phases.py` | 4 tests existants adaptés + 5 nouveaux tests PHASE-26a-bis (multi-filtre, HX-Trigger multi, pilules, heatmap union, rétro-compat). |

