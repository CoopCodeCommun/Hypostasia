# PHASE-26a UX : 5 ameliorations filtre multi-contributeurs

**Date :** 2026-03-16
**Migration :** Non

**Quoi / What:** 5 ameliorations UX du filtre multi-contributeurs :
1. **Scroll-to-first** : le drawer scrolle en haut apres activation/desactivation d'un filtre
2. **Noms dans compteur** : "2 sur 78 (marie)" au lieu de "2 sur 78"
3. **Badge entites** : la pilule active affiche le nombre d'entites distinctes (pas de commentaires)
4. **Couleur HSL** : chaque contributeur a une couleur deterministe (hash MD5 du username)
5. **Mode Sauf** : bouton "Sauf" pour inverser le filtre (exclure au lieu d'inclure)

**Pourquoi / Why:** Le facilitateur utilise le filtre pour preparer ses reunions de consensus.
Ces ameliorations rendent l'outil plus lisible (couleurs distinctes, noms), plus precis
(entites vs commentaires), et plus flexible (mode exclure pour voir "tout sauf X").

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `front/views.py` | Helper `_calculer_teinte_contributeur()`, enrichissement contributeurs (nombre_entites + couleur_hsl), mode `exclure` avec `.exclude()` |
| `front/templates/front/includes/drawer_vue_liste.html` | Compteur avec noms + sauf, pilule-exclue/pilule-active, bouton Sauf, badge entites, commentaires mode inversé |
| `front/static/front/js/drawer_vue_liste.js` | Scroll-to-first, variable `modeFiltre`, handler bouton Sauf, `getContributeursActuels` inclut pilule-exclue |
| `front/static/front/js/marginalia.js` | `appliquerFiltreContributeurs` supporte `modeFiltre` pour inverser le dimming pastilles |
| `front/static/front/css/hypostasia.css` | `.pilule-contributeur.pilule-active` HSL, `.pilule-exclue` hachures, `.pilule-toggle-mode` |
| `front/tests/test_phases.py` | 8 tests : compteur noms, entites count, couleur HSL (3), exclure, compteur sauf, HX-Trigger mode |

### Migration
- **Migration necessaire / Migration required:** Non

