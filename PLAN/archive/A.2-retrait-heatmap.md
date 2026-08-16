# Plan A.2 — Retrait Heat map

> **Pour les workers agentiques :** ce plan suit la skill `superpowers:writing-plans`. Les étapes utilisent la syntaxe checkbox `- [ ]` pour le suivi. Voir [PLAN/REVUE_YAGNI_2026-05-01.md](REVUE_YAGNI_2026-05-01.md) pour le contexte.

**Goal :** retirer entièrement la feature Heat map du débat (PHASE-19) — code Python, CSS, 4 fichiers JavaScript, tests Django et E2E. La couche thermique au-dessus du dashboard de consensus n'apporte pas de valeur observée, et la section CSS/JS associée pèse ~250 lignes.

**Architecture :**
- Suppression complète de la fonction `_interpoler_couleur_heatmap()` dans `utils.py` et de l'injection `data-heat-color` sur les spans d'extraction
- Suppression de la section CSS `body.mode-heatmap`, des variables `--heatmap-*` et du calque `#heatmap-underlay`
- Refactor de `marginalia.js` : suppression de l'API publique `basculerHeatmap`/`heatmapEstActive`, du localStorage, du calque dynamique, des branches conditionnelles
- Refactor du cycle mobile dans `keyboard.js` : passe de **3 modes** (surlignage → lecture → heatmap) à **2 modes** (surlignage → lecture) — voir Q1 plus bas
- Suppression du raccourci `H` desktop dans `keyboard.js`
- Suppression du bouton `#btn-toolbar-heatmap` dans `base.html`
- Suppression des refs `mode-heatmap-mobile` dans `bottom_sheet.js` et `drawer_vue_liste.js`
- Suppression de **8 classes de tests** Django `Phase19*` dans `test_phases.py`
- Adaptation du test E2E mobile pour le cycle 2 modes au lieu de 3, mise à jour du docstring de `test_07_layout.py`

**Tech stack :** Django 6 + DRF + HTMX + Tailwind subset + JavaScript vanilla. Stack-ccc / skill djc. Conventions FR/EN bilingues, noms verbeux.

**Hors périmètre :**
- Mode focus / mode lecture pleine page (raccourci `L`) → A.3
- Stripe / crédits prépayés → A.4
- Bibliothèque analyseurs → A.5
- Onboarding `onboarding_vide.html` raccourci `H` : déjà retiré préemptivement en A.1 step 5.3 ✅

**Préférences user :**
- Aucune commande git automatique (commit géré par Jonas — chaque tâche se termine par un message de commit suggéré, pas par un `git commit`)
- Pas de `Co-Authored-By` dans les messages de commit
- Stack-ccc / djc respecté pour tout nouveau code (très peu dans ce plan, on supprime)

---

## Décision à valider en début de plan

### Q1 — Cycle mobile : 3 modes ou 2 modes ?

`keyboard.js:580-633` implémente un cycle mobile sur le bouton oeil dans la toolbar :

```
surlignage → lecture pure → heat map → surlignage
```

Si on retire la heatmap :
- **(A) Cycle 2 modes** : `surlignage → lecture pure → surlignage`. Le bouton oeil bascule juste entre afficher / masquer le surlignage. Code allégé, comportement intuitif.
- **(B) Retirer le bouton mobile** entièrement : pas de toggle, le surlignage est toujours actif. Encore plus simple, mais perd la possibilité de lire sans surlignage sur mobile (utile si l'utilisateur trouve les couleurs distrayantes).

**Hypothèse retenue dans ce plan : (A) cycle 2 modes.** C'est le moins perturbant pour les utilisateurs déjà habitués au bouton, et le mode lecture pure garde une utilité indépendante de la heatmap. Si tu préfères (B), inverse-moi avant qu'on lance la Task 3.

---

## Cartographie des changements

### Fichiers supprimés (0)

Aucun fichier n'est supprimé entièrement (la heatmap est intégrée à des fichiers qui contiennent d'autres features).

### Fichiers créés (0)

### Fichiers modifiés (10)

| Fichier | Refs | Changement |
|---|---|---|
| `front/utils.py` | 7 | Retrait `_interpoler_couleur_heatmap()` (l. 30-95 environ) + retrait des variables `couleur_heatmap`, `attribut_heatmap` et de l'injection `data-heat-color` dans la fonction d'annotation HTML (l. 513-541) |
| `front/templates/front/base.html` | 4 | Retrait du bouton `#btn-toolbar-heatmap` (l. 67-78) + ajustement commentaire mode mobile (l. 78-80) |
| `front/static/front/js/marginalia.js` | 47 | Retrait constante `CLE_LOCALSTORAGE_HEATMAP`, fonctions `heatmapEstActive()`/`basculerHeatmap()`, layer `#heatmap-underlay` (création/suppression/init), branches conditionnelles, init au load, export `heatmapEstActive` |
| `front/static/front/js/keyboard.js` | 19 | Retrait `case 'h'` (l. 524-531) + refactor cycle mobile en 2 modes (l. 580-633) |
| `front/static/front/js/bottom_sheet.js` | 5 | Retrait branches `mode-heatmap-mobile` (l. 77-78, 89, 123-124) |
| `front/static/front/js/drawer_vue_liste.js` | 5 | Retrait des 3 conditions `if (window.marginalia && window.marginalia.heatmapEstActive())` (l. 379-382, 394-397, 415-420) |
| `front/static/front/css/hypostasia.css` | 21 | Retrait section `/* === 22. Heat map === */` (l. 1336-1374) + retrait sélecteurs `#btn-toolbar-heatmap`, `body.mode-heatmap-mobile` dans le bloc responsive (l. 1675, 1702-1707) |
| `front/tests/test_phases.py` | 79 | Retrait de **8 classes Phase19*** (l. 4758-5289 environ, juste avant `Phase20ModelUpdatedAtTest`) + ajustement commentaire de section (l. 4758-4759) |
| `front/tests/e2e/test_07_layout.py` | 2 | Mise à jour docstring (l. 2-3) — retirer "heatmap" de la description |
| `front/tests/e2e/test_10_mobile.py` | 4 | Adaptation du test mobile (l. 368-390) — cycle 2 clics au lieu de 3, retirer assertion `heatmap` |

### Cas particuliers

**Pas de fichier `test_phase19*.py` séparé** : tous les tests Phase19 sont dans `test_phases.py` (8 classes, lignes 4763-5289).

**Aucune ref dans `front/views.py`** : le scan grep n'a rien trouvé. La heatmap n'a pas de flag dans `LectureViewSet` — le score est calculé dans `utils.py` et appliqué dans le HTML via `data-heat-color`.

**Modale d'aide raccourcis** (`aide_desktop.html`, `aide_mobile.html`) : aucune ref H/heatmap trouvée, déjà clean.

**Onboarding** (`onboarding_vide.html`) : raccourci H déjà retiré préemptivement en A.1 step 5.3.

---

## Tâches

### Task 1 : Retrait CSS heat map

**Files:**
- Modify: `front/static/front/css/hypostasia.css` (lignes 1336-1374 + lignes 1673-1707 ajustement responsive)

- [ ] **Step 1.1 — Supprimer la section principale heat map (lignes 1336-1374)**

Supprimer le bloc complet :
```css
/* === 22. Heat map du debat (PHASE-19) ===
   Coloration du fond selon l'intensite du debat.
   Activee via body.mode-heatmap + inline style data-heat-color (JS).
   / Debate heat map — background color by debate intensity.
   / Activated via body.mode-heatmap + inline style data-heat-color (JS).
   ========================================================================== */

:root {
    --heatmap-froid: #f0fdf4;      /* vert pale — consensus */
    --heatmap-tiede: #fefce8;      /* jaune pale — discussion moderee */
    --heatmap-chaud: #fff7ed;      /* orange pale — debat actif */
    --heatmap-brulant: #fef2f2;    /* rouge pale — controverse forte */
}

/* Calque underlay : nappe de halos radiaux derriere le texte */
/* / Underlay layer: radial halo sheet behind the text */
#heatmap-underlay {
    transition: opacity 0.4s ease;
}

/* En mode heatmap, les blocs de contenu deviennent transparents
   pour laisser voir le calque de halos derriere eux.
   / In heatmap mode, content blocks become transparent
   / to let the halo layer show through. */
body.mode-heatmap .speaker-block {
    background: transparent !important;
}
body.mode-heatmap #readability-content p,
body.mode-heatmap #readability-content div,
body.mode-heatmap #readability-content blockquote,
body.mode-heatmap #readability-content li {
    background: transparent;
}

/* Mode focus : masque le calque heat map (lecture pure sans bruit visuel) */
/* / Focus mode: hide heat map overlay (pure reading without visual noise) */
body.mode-focus #heatmap-underlay {
    opacity: 0 !important;
}
```

Garder un seul saut de ligne entre le bloc précédent (avant `/* === 22. Heat map */`) et le bloc suivant (probablement `/* Responsive : modale plein ecran sur mobile ... */` à la ligne 1376).

- [ ] **Step 1.2 — Modifier le bloc responsive mobile (lignes 1673-1707)**

Avant (extrait) :
```css
    /* Sur mobile on masque Focus et Heatmap (remplaces par le toggle mode) */
    /* / On mobile hide Focus and Heatmap (replaced by mode toggle) */
    #btn-toolbar-focus, #btn-toolbar-heatmap { display: none; }
```
Après :
```css
    /* Sur mobile on masque Focus (remplace par le toggle mode) */
    /* / On mobile hide Focus (replaced by mode toggle) */
    #btn-toolbar-focus { display: none; }
```

Et supprimer entièrement le bloc :
```css
    /* Mode heatmap mobile : masque le surlignage individuel, la heatmap prend le relais */
    /* / Mobile heatmap mode: hide individual highlighting, heatmap takes over */
    body.mode-heatmap-mobile .hl-extraction[data-extraction-id] {
        background-color: transparent !important;
        border-bottom: none !important;
    }
```
(garder le bloc `body.mode-lecture-mobile` qui le précède juste avant — c'est utilisé par le mode lecture pure mobile qu'on conserve)

- [ ] **Step 1.3 — Vérifier qu'aucune ref `heatmap` ne subsiste dans le CSS**

```bash
rg "heatmap|HEATMAP|--heatmap|mode-heatmap" /home/jonas/Gits/Hypostasia/front/static/front/css/hypostasia.css
```
Attendu : 0 résultat.

- [ ] **Step 1.4 — Commit suggéré**

```
A.2 (1/9) — Retrait CSS heat map (PHASE-19)

Supprime la section CSS heat map (variables --heatmap-*, calque
#heatmap-underlay, sélecteurs body.mode-heatmap), et le bloc
responsive body.mode-heatmap-mobile. Premier commit du retrait
heat map (session A.2 de la revue YAGNI 2026-05-01).
```

---

### Task 2 : Retrait JS marginalia (cœur de la heat map)

**Files:**
- Modify: `front/static/front/js/marginalia.js` (47 refs sur ~600 lignes)

C'est la task la plus délicate car `marginalia.js` contient l'API publique `window.marginalia.basculerHeatmap()` / `window.marginalia.heatmapEstActive()` consommée par 3 autres fichiers JS (keyboard, bottom_sheet, drawer_vue_liste). Il faut donc faire les modifications **dans cet ordre** : d'abord retirer toute la mécanique heatmap dans marginalia.js, puis nettoyer les consumers (Tasks 3, 4).

**ATTENTION** : si on lance le runserver entre Task 2 et Task 3, le bouton `H` du clavier appellera `window.marginalia.basculerHeatmap()` qui n'existera plus → erreur JS. Faire Task 2 et Task 3 d'affilée sans tester en navigateur entre les deux.

- [ ] **Step 2.1 — Lire le fichier `marginalia.js` pour repérer toutes les bornes des blocs heatmap**

```bash
rg -n "heatmap|HEATMAP" /home/jonas/Gits/Hypostasia/front/static/front/js/marginalia.js
```
Confirmer les positions de :
- En-tête API publique (ligne ~24) : `//           basculerHeatmap, heatmapEstActive, ...`
- `var CLE_LOCALSTORAGE_HEATMAP = 'hypostasia-heatmap-actif';` (l. 48)
- Branche `if (heatmapEstActive())` dans une fonction (l. 59)
- Fonction `function heatmapEstActive()` (l. 112-114)
- Construction du calque `#heatmap-underlay` (lignes 133-167)
- Suppression du calque (l. 255+)
- Fonction `function basculerHeatmap()` ou similaire (autour des lignes 260-285 vu le contenu)
- Bloc init au DOMContentLoaded (l. 502-515)
- Export public (l. 597) : `heatmapEstActive: heatmapEstActive,`

- [ ] **Step 2.2 — Retirer la constante `CLE_LOCALSTORAGE_HEATMAP` (l. 48)**

Avant :
```js
    var CLE_LOCALSTORAGE_HEATMAP = 'hypostasia-heatmap-actif';
```
Supprimer entièrement la ligne.

- [ ] **Step 2.3 — Retirer la fonction `heatmapEstActive()`**

Trouver et supprimer entièrement le bloc :
```js
    function heatmapEstActive() {
        return document.body.classList.contains('mode-heatmap');
    }
```
(typiquement 3 lignes)

- [ ] **Step 2.4 — Retirer la fonction qui crée et active le calque `#heatmap-underlay`**

Trouver la fonction (probablement `function activerHeatmap()` ou `function calculerEtAfficherHeatmap()`) qui :
- Crée un `<div id="heatmap-underlay">`
- Calcule des positions de halos radiaux
- Ajoute la classe `mode-heatmap` au body
- Sauvegarde dans localStorage `CLE_LOCALSTORAGE_HEATMAP`
- Met à jour le titre du bouton `#btn-toolbar-heatmap`

Et la fonction symétrique de désactivation. Probablement `function basculerHeatmap()` qui combine les deux.

À l'exécution : utiliser `rg -n -B2 -A20 "heatmap-underlay" marginalia.js` pour cartographier les bornes exactes.

- [ ] **Step 2.5 — Retirer toutes les branches `if (heatmapEstActive())` dans le fichier**

Chercher toutes les occurrences :
```bash
rg -n "heatmapEstActive\(\)" /home/jonas/Gits/Hypostasia/front/static/front/js/marginalia.js
```
Pour chaque occurrence, supprimer le bloc `if (...) { ... }` entier (probablement 3-5 lignes chacun). Si la branche `else` reste isolée, la garder telle quelle.

- [ ] **Step 2.6 — Retirer le bloc d'init au load**

Lignes ~500-515 (à confirmer en lecture) :
```js
        if (localStorage.getItem(CLE_LOCALSTORAGE_HEATMAP) === 'actif') {
            // ... activer heatmap au load
        }
```
À supprimer entièrement.

Aussi retirer la mise à jour du bouton `#btn-toolbar-heatmap` dans le bloc init si présente :
```js
        var boutonHeatmap = document.getElementById('btn-toolbar-heatmap');
        if (boutonHeatmap) { ... }
```

- [ ] **Step 2.7 — Retirer le commentaire en-tête API publique (l. ~24)**

Avant :
```js
//           basculerHeatmap, heatmapEstActive, getContributeurFiltre, resetContributeurFiltre }
```
Après :
```js
//           getContributeurFiltre, resetContributeurFiltre }
```
(garder les autres APIs)

- [ ] **Step 2.8 — Retirer l'export public**

Dans le bloc final `window.marginalia = { ... }`, retirer la ligne :
```js
        heatmapEstActive: heatmapEstActive,
```
Et tout autre export `basculerHeatmap` éventuellement présent.

- [ ] **Step 2.9 — Vérifier l'absence de réf résiduelle dans marginalia.js**

```bash
rg "heatmap|HEATMAP|CLE_LOCALSTORAGE_HEATMAP|basculerHeatmap|heatmapEstActive|heatmap-underlay|mode-heatmap|btn-toolbar-heatmap" /home/jonas/Gits/Hypostasia/front/static/front/js/marginalia.js
```
Attendu : 0 résultat.

- [ ] **Step 2.10 — NE PAS commiter ni tester en navigateur** — enchaîner immédiatement Task 3 (sinon erreurs JS sur appel à `window.marginalia.basculerHeatmap()` depuis keyboard.js).

Le commit groupé sera fait à la fin de Task 4.

---

### Task 3 : Retrait raccourci `H` desktop + refactor cycle mobile en 2 modes

**Files:**
- Modify: `front/static/front/js/keyboard.js` (lignes 524-531 + lignes 580-633)

- [ ] **Step 3.1 — Retirer le `case 'h'` du switch desktop (lignes 524-531)**

Avant :
```js
            // H → Toggle heat map du debat (PHASE-19)
            // / H → Toggle debate heat map (PHASE-19)
            case 'h':
                if (window.marginalia) {
                    window.marginalia.basculerHeatmap();
                }
                evenement.preventDefault();
                break;
```
Supprimer entièrement les 8 lignes.

- [ ] **Step 3.2 — Refactor du cycle mobile : passer de 3 modes à 2 modes**

Avant (lignes 580-633 environ) :
```js
        // Toggle mode mobile : cycle entre 3 modes d'affichage
        // Le bouton oeil dans la toolbar change le mode a chaque tap :
        //   surlignage → lecture pure → heat map → retour au surlignage
        // - surlignage : le texte extrait a un fond colore (par statut de debat)
        // - lecture pure : pas de surlignage, texte brut pour lire sans distraction
        // - heat map : couleurs d'intensite du debat (rouge = beaucoup de commentaires)
        // / Mobile mode toggle: cycles between 3 display modes
        // The eye button in the toolbar changes mode on each tap:
        //   highlight → reading → heatmap → back to highlight
        var modeActuel = 'surlignage'; // surlignage | lecture | heatmap
        var boutonModeMobile = document.getElementById('btn-toolbar-mode-mobile');
        if (boutonModeMobile) {
            boutonModeMobile.addEventListener('click', function() {
                // Passer au mode suivant / Switch to next mode
                // Nettoyer les classes du mode precedent
                // / Clean classes from previous mode
                document.body.classList.remove('mode-lecture-mobile', 'mode-heatmap-mobile');

                if (modeActuel === 'surlignage') {
                    // Surlignage → Lecture : masquer le surlignage, eteindre la heatmap
                    // / Highlight → Reading: hide highlighting, turn off heatmap
                    modeActuel = 'lecture';
                    document.body.classList.add('mode-lecture-mobile');
                    if (window.marginalia && window.marginalia.heatmapEstActive()) {
                        window.marginalia.basculerHeatmap();
                    }
                } else if (modeActuel === 'lecture') {
                    // Lecture → Heatmap : activer la heatmap, masquer le surlignage individuel
                    // / Reading → Heatmap: activate heatmap, hide individual highlighting
                    modeActuel = 'heatmap';
                    document.body.classList.add('mode-heatmap-mobile');
                    if (window.marginalia && !window.marginalia.heatmapEstActive()) {
                        window.marginalia.basculerHeatmap();
                    }
                } else {
                    // Heatmap → Surlignage : eteindre la heatmap, remettre le surlignage
                    // / Heatmap → Highlight: turn off heatmap, restore highlighting
                    modeActuel = 'surlignage';
                    if (window.marginalia && window.marginalia.heatmapEstActive()) {
                        window.marginalia.basculerHeatmap();
                    }
                }

                // Mettre a jour le title du bouton pour indiquer le mode actif
                // / Update button title to indicate active mode
                var titresParMode = {
                    'surlignage': 'Mode : Surlignage (tap pour changer)',
                    'lecture': 'Mode : Lecture pure (tap pour changer)',
                    'heatmap': 'Mode : Heat map (tap pour changer)',
                };
                boutonModeMobile.title = titresParMode[modeActuel];
            });
        }
```

Après :
```js
        // Toggle mode mobile : cycle entre 2 modes d'affichage (refonte A.2 — heatmap retiree)
        // Le bouton oeil dans la toolbar change le mode a chaque tap :
        //   surlignage → lecture pure → retour au surlignage
        // - surlignage : le texte extrait a un fond colore (par statut de debat)
        // - lecture pure : pas de surlignage, texte brut pour lire sans distraction
        // / Mobile mode toggle: cycles between 2 display modes (A.2 refactor — heatmap removed)
        // The eye button in the toolbar changes mode on each tap:
        //   highlight → reading → back to highlight
        var modeActuel = 'surlignage'; // surlignage | lecture
        var boutonModeMobile = document.getElementById('btn-toolbar-mode-mobile');
        if (boutonModeMobile) {
            boutonModeMobile.addEventListener('click', function() {
                // Passer au mode suivant — toggle simple
                // / Switch to next mode — simple toggle
                if (modeActuel === 'surlignage') {
                    // Surlignage → Lecture : masquer le surlignage
                    // / Highlight → Reading: hide highlighting
                    modeActuel = 'lecture';
                    document.body.classList.add('mode-lecture-mobile');
                } else {
                    // Lecture → Surlignage : remettre le surlignage
                    // / Reading → Highlight: restore highlighting
                    modeActuel = 'surlignage';
                    document.body.classList.remove('mode-lecture-mobile');
                }

                // Mettre a jour le title du bouton pour indiquer le mode actif
                // / Update button title to indicate active mode
                var titresParMode = {
                    'surlignage': 'Mode : Surlignage (tap pour changer)',
                    'lecture': 'Mode : Lecture pure (tap pour changer)',
                };
                boutonModeMobile.title = titresParMode[modeActuel];
            });
        }
```

- [ ] **Step 3.3 — Vérifier l'absence de ref résiduelle dans keyboard.js**

```bash
rg "heatmap|HEATMAP|mode-heatmap|basculerHeatmap|heatmapEstActive" /home/jonas/Gits/Hypostasia/front/static/front/js/keyboard.js
```
Attendu : 0 résultat.

- [ ] **Step 3.4 — NE PAS commiter** — enchaîner Task 4 directement.

---

### Task 4 : Nettoyage `bottom_sheet.js` et `drawer_vue_liste.js`

**Files:**
- Modify: `front/static/front/js/bottom_sheet.js` (lignes 77-78, 89, 123-124)
- Modify: `front/static/front/js/drawer_vue_liste.js` (lignes 379-382, 394-397, 415-420)

- [ ] **Step 4.1 — `bottom_sheet.js` : retirer les branches `mode-heatmap-mobile`**

Lire le fichier :
```bash
rg -n -B3 -A3 "heatmap" /home/jonas/Gits/Hypostasia/front/static/front/js/bottom_sheet.js
```

Identifier le bloc qui sauvegarde le mode actuel (vers ligne 77-78) :
```js
            } else if (document.body.classList.contains('mode-heatmap-mobile')) {
                classeModeSauvegardee = 'mode-heatmap-mobile';
```
À supprimer (juste les 2 lignes).

Identifier le bloc qui restaure le mode (vers ligne 89) :
```js
        document.body.classList.remove('mode-lecture-mobile', 'mode-heatmap-mobile');
```
À remplacer par :
```js
        document.body.classList.remove('mode-lecture-mobile');
```

Identifier le bloc qui restaure heatmap (vers ligne 123-124) :
```js
        } else if (classeModeSauvegardee === 'mode-heatmap-mobile') {
            document.body.classList.add('mode-heatmap-mobile');
```
À supprimer (juste les 2 lignes).

- [ ] **Step 4.2 — `drawer_vue_liste.js` : retirer les 3 conditions `heatmapEstActive()`**

Bloc 1 (lignes 379-382) :
```js
            if (window.marginalia && window.marginalia.heatmapEstActive()) {
                var pageId = getPageId();
                rechargerZoneLecture(pageId, '');
            }
```
À supprimer entièrement (4 lignes).

Bloc 2 (lignes 394-397) :
```js
            if (window.marginalia && window.marginalia.heatmapEstActive()) {
                var pageId = getPageId();
                rechargerZoneLecture(pageId, contributeursActuels);
            }
```
À supprimer entièrement (4 lignes).

Bloc 3 (lignes 415-420) :
```js
        // Si heatmap active, recharger la zone de lecture (PHASE-26a-bis)
        // / If heatmap is active, reload reading zone (PHASE-26a-bis)
        if (window.marginalia && window.marginalia.heatmapEstActive()) {
            var pageId = getPageId();
            rechargerZoneLecture(pageId, contributeursActuels);
        }
```
À supprimer entièrement (6 lignes).

- [ ] **Step 4.3 — Vérifier l'absence de ref résiduelle dans les 4 fichiers JS**

```bash
rg "heatmap|HEATMAP|mode-heatmap|basculerHeatmap|heatmapEstActive|heatmap-underlay" /home/jonas/Gits/Hypostasia/front/static/front/js/
```
Attendu : 0 résultat.

- [ ] **Step 4.4 — Tester en navigateur (premier point de contrôle visuel)**

```bash
uv run python manage.py runserver 0.0.0.0:8123
```
- Ouvrir http://localhost:8123/, naviguer vers une page de lecture (`/lire/{id}/`)
- **Vérifier console JS** : aucune erreur `basculerHeatmap is not a function` ou `heatmapEstActive is not a function`
- **Tester le raccourci `H`** : doit ne rien faire (pas d'erreur)
- **Sur mobile (DevTools responsive)** : taper le bouton oeil → bascule entre surlignage et lecture pure (pas de mode heatmap)
- Le clavier `T`, `E`, `J/K`, `C`, `S`, `X`, `A` doivent toujours fonctionner

- [ ] **Step 4.5 — Commit suggéré (groupé Tasks 2+3+4)**

```
A.2 (2+3+4/9) — Retrait JS heat map (marginalia, keyboard, bottom_sheet, drawer)

Retire l'API publique window.marginalia.basculerHeatmap /
heatmapEstActive et toutes les branches conditionnelles dans
keyboard.js, bottom_sheet.js, drawer_vue_liste.js.
Le cycle mobile passe de 3 modes (surlignage / lecture / heatmap)
a 2 modes (surlignage / lecture). Raccourci H desktop retire.
Tasks regroupees pour eviter un etat intermediaire ou les
consumers JS appellent une API qui n'existe plus.
```

---

### Task 5 : Retrait du bouton `#btn-toolbar-heatmap` dans `base.html`

**Files:**
- Modify: `front/templates/front/base.html` (lignes 67-78 environ)

- [ ] **Step 5.1 — Lire la zone du bouton heatmap**

```bash
rg -n -B2 -A12 "btn-toolbar-heatmap" /home/jonas/Gits/Hypostasia/front/templates/front/base.html
```
Identifier les bornes exactes du bloc à supprimer.

- [ ] **Step 5.2 — Supprimer le bouton + commentaires associés**

Lignes 67-78 (à confirmer en lecture) :
```html
            <button id="btn-toolbar-heatmap" class="btn-toolbar"
                    title="Heat map du débat (H)" data-testid="btn-toolbar-heatmap">
                <!-- ... SVG ... -->
            </button>
```
À supprimer entièrement.

- [ ] **Step 5.3 — Ajuster le commentaire mode mobile (ligne 78-80)**

Avant :
```html
            <!-- Bouton toggle mode mobile : surlignage → lecture → heatmap (PHASE-21) -->
            <!-- / Mobile mode toggle button: highlight → reading → heatmap (PHASE-21) -->
```
Après :
```html
            <!-- Bouton toggle mode mobile : surlignage → lecture (PHASE-21, refonte A.2) -->
            <!-- / Mobile mode toggle button: highlight → reading (PHASE-21, A.2 refactor) -->
```

- [ ] **Step 5.4 — Vérifier l'absence de ref résiduelle**

```bash
rg "heatmap|HEATMAP|btn-toolbar-heatmap" /home/jonas/Gits/Hypostasia/front/templates/front/base.html
```
Attendu : 0 résultat.

- [ ] **Step 5.5 — Vérifier visuellement la toolbar**

Recharger http://localhost:8123/, vérifier que le bouton heatmap (icône thermomètre) a disparu de la toolbar desktop. Les autres boutons (import, alignement, focus, aide) sont toujours là.

- [ ] **Step 5.6 — Commit suggéré**

```
A.2 (5/9) — Retrait bouton toolbar heat map

Supprime le bouton #btn-toolbar-heatmap de la toolbar desktop dans
base.html et ajuste le commentaire du toggle mobile (qui est passe
de 3 modes a 2 modes en Task 3).
```

---

### Task 6 : Retrait Python `utils.py`

**Files:**
- Modify: `front/utils.py` (fonction `_interpoler_couleur_heatmap` + bloc d'injection `data-heat-color`)

- [ ] **Step 6.1 — Lire le contexte de la fonction `_interpoler_couleur_heatmap`**

```bash
rg -n -B3 -A50 "_interpoler_couleur_heatmap" /home/jonas/Gits/Hypostasia/front/utils.py | head -80
```
Identifier les bornes de la fonction (ligne 30 jusqu'à la fin de son bloc, probablement ligne 80-95).

- [ ] **Step 6.2 — Supprimer la fonction `_interpoler_couleur_heatmap()`**

Supprimer entièrement le bloc :
```python
def _interpoler_couleur_heatmap(score_normalise):
    """
    ... (docstring)
    """
    # ... corps de la fonction
    return ...
```

- [ ] **Step 6.3 — Lire le contexte de l'injection `data-heat-color` (lignes 510-545)**

```bash
rg -n -B3 -A2 "couleur_heatmap|attribut_heatmap|data-heat-color|scores_temperature" /home/jonas/Gits/Hypostasia/front/utils.py
```

- [ ] **Step 6.4 — Retirer le bloc de calcul de `couleur_heatmap`**

Lignes 513-541 (à confirmer) :
```python
        couleur_heatmap = None
        if entite_pk in scores_temperature_normalises:
            couleur_heatmap = _interpoler_couleur_heatmap(scores_temperature_normalises[entite_pk])

        insertions_spans.append((html_pos_debut, html_pos_fin, entite_pk, a_commentaire, statut_debat, couleur_heatmap))
```

À adapter :
```python
        insertions_spans.append((html_pos_debut, html_pos_fin, entite_pk, a_commentaire, statut_debat))
```
(retirer la 6e valeur du tuple)

- [ ] **Step 6.5 — Adapter le déballage du tuple et l'injection HTML**

Avant (ligne 530-541) :
```python
    for (html_pos_debut, html_pos_fin, entite_pk, a_commentaire, statut_debat, couleur_heatmap) in insertions_spans:
        # ...
        attribut_heatmap = f' data-heat-color="{couleur_heatmap}"' if couleur_heatmap else ''
        # ...
        span_ouvrant = f'<span class="{classe_span}" data-extraction-id="{entite_pk}" data-statut="{statut_debat}"{attribut_heatmap}>'
```
Après :
```python
    for (html_pos_debut, html_pos_fin, entite_pk, a_commentaire, statut_debat) in insertions_spans:
        # ...
        span_ouvrant = f'<span class="{classe_span}" data-extraction-id="{entite_pk}" data-statut="{statut_debat}">'
```

- [ ] **Step 6.6 — Vérifier si `scores_temperature_normalises` est encore utilisé ailleurs**

```bash
rg "scores_temperature_normalises|scores_temperature|calculer_scores_temperature" /home/jonas/Gits/Hypostasia/front/utils.py
```

Si la variable n'est plus utilisée nulle part, retirer aussi la fonction `_calculer_scores_temperature()` et son appel dans la fonction d'annotation. Si elle est utilisée par autre chose (improbable), la garder.

À l'exécution : faire le grep, lire le contexte, décider en fonction. Si suppression nécessaire, ajouter un step 6.7 dédié.

- [ ] **Step 6.7 — Vérifier que les paramètres de la fonction d'annotation sont cohérents**

La fonction qui contient le bloc d'annotation prend probablement un paramètre `scores_temperature_normalises` ou `entites_avec_temperature`. Si plus utilisé, le retirer aussi.

```bash
rg -n -B30 "couleur_heatmap = None" /home/jonas/Gits/Hypostasia/front/utils.py | head -40
```

À adapter au contexte exact lu sur place.

- [ ] **Step 6.8 — Vérifier l'absence de ref résiduelle**

```bash
rg "heatmap|HEATMAP|data-heat-color|interpoler_couleur|scores_temperature" /home/jonas/Gits/Hypostasia/front/utils.py
```
Attendu : 0 résultat.

- [ ] **Step 6.9 — Lancer Django check**

```bash
uv run python manage.py check
```
Attendu : `System check identified no issues (0 silenced).`

- [ ] **Step 6.10 — Tester visuellement la zone de lecture**

Recharger http://localhost:8123/lire/{id}/ — la page doit s'afficher normalement, les surlignages d'extraction doivent apparaître avec leurs couleurs de statut (vert/orange/rouge), aucun attribut `data-heat-color` dans le HTML inspecté.

- [ ] **Step 6.11 — Commit suggéré**

```
A.2 (6/9) — Retrait fonction _interpoler_couleur_heatmap dans utils.py

Supprime la fonction d'interpolation de couleur heat map et le bloc
d'injection data-heat-color sur les spans d'extraction. La zone de
lecture conserve les surlignages par statut de debat (consensuel /
discutable / discute / controverse), mais sans la couche thermique.
```

---

### Task 7 : Retrait des 8 classes de tests Django Phase19*

**Files:**
- Modify: `front/tests/test_phases.py` (lignes 4758-5289 environ)

- [ ] **Step 7.1 — Identifier les bornes exactes**

```bash
rg -n "^class Phase19|^class Phase20" /home/jonas/Gits/Hypostasia/front/tests/test_phases.py | head -10
```
Confirmer la dernière classe Phase19 et la première classe Phase20 (qu'on conserve).

D'après le scan préalable : 8 classes de `Phase19InterpolerCouleurHeatmapTest` (l. 4763) à `Phase19EndpointLectureHeatmapTest` (l. 5232+), puis `Phase20ModelUpdatedAtTest` (l. 5290) commence.

- [ ] **Step 7.2 — Modifier le commentaire de section (l. 4758-4759)**

Avant :
```python
# =============================================================================
# PHASE-19 — Heat map du debat sur le texte
# / PHASE-19 — Debate heat map on text
# =============================================================================
```
À supprimer entièrement (4 lignes du commentaire de section).

- [ ] **Step 7.3 — Lire le bloc des 8 classes pour confirmer les bornes**

```bash
sed -n '4756,4770p; 5285,5295p' /home/jonas/Gits/Hypostasia/front/tests/test_phases.py
```
ou
```python
Read file_path="/home/jonas/Gits/Hypostasia/front/tests/test_phases.py" offset=4755 limit=20
Read file_path="/home/jonas/Gits/Hypostasia/front/tests/test_phases.py" offset=5285 limit=15
```

Vérifier la borne haute (avant `Phase19InterpolerCouleurHeatmapTest`, juste après une classe Phase18) et la borne basse (avant `Phase20ModelUpdatedAtTest`).

- [ ] **Step 7.4 — Supprimer en bloc les 8 classes + le commentaire de section**

Utiliser un Edit sur le bloc complet, en remplaçant tout par juste la classe suivante (`class Phase20ModelUpdatedAtTest(...):`). Garder un saut de ligne propre entre la classe précédente (avant Phase19) et `Phase20`.

À l'exécution : utiliser le pattern `old_string` qui inclut le commentaire de section + les 8 classes + `class Phase20ModelUpdatedAtTest`, et `new_string` qui contient juste `class Phase20ModelUpdatedAtTest`.

- [ ] **Step 7.5 — Vérifier l'absence de ref résiduelle**

```bash
rg "heatmap|HEATMAP|Phase19|_interpoler_couleur|data-heat-color|scores_temperature" /home/jonas/Gits/Hypostasia/front/tests/test_phases.py
```
Attendu : 0 résultat.

- [ ] **Step 7.6 — Lancer Django check**

```bash
uv run python manage.py check
```
Attendu : `System check identified no issues (0 silenced).`

- [ ] **Step 7.7 — Commit suggéré**

```
A.2 (7/9) — Retrait des tests Django Phase19* (heat map)

Supprime 8 classes de tests Phase19* dans test_phases.py
(InterpolerCouleurHeatmap, AnnotationDataHeatColor,
CalculerScoresTemperature, BaseHTML, MarginaliaJS, KeyboardJS,
CSSStyles, EndpointLectureHeatmap) et le commentaire de section.
```

---

### Task 8 : Adapter les tests E2E

**Files:**
- Modify: `front/tests/e2e/test_07_layout.py` (lignes 2-3 docstring)
- Modify: `front/tests/e2e/test_10_mobile.py` (lignes 368-390 cycle mobile)

- [ ] **Step 8.1 — Mettre à jour le docstring de `test_07_layout.py`**

Avant :
```python
"""
Tests E2E — Layout : drawer, focus mode, raccourcis clavier, heatmap.
/ E2E tests — Layout: drawer, focus mode, keyboard shortcuts, heatmap.
"""
```
Après :
```python
"""
Tests E2E — Layout : drawer, focus mode, raccourcis clavier.
/ E2E tests — Layout: drawer, focus mode, keyboard shortcuts.
"""
```

(retirer juste la mention "heatmap" du docstring)

- [ ] **Step 8.2 — Vérifier qu'il n'y a pas de test heatmap dans `test_07_layout.py`**

```bash
rg -n "heatmap|HEATMAP|Heat map|btn-toolbar-heatmap" /home/jonas/Gits/Hypostasia/front/tests/e2e/test_07_layout.py
```
Attendu : 0 résultat (le docstring vient d'être nettoyé). Si un test entier mentionne heatmap, le supprimer.

- [ ] **Step 8.3 — Lire le test mobile lignes 365-395**

```bash
sed -n '360,395p' /home/jonas/Gits/Hypostasia/front/tests/e2e/test_10_mobile.py
```
ou Read avec offset 360, limit 40.

Identifier la structure du test : il y a probablement une assertion sur 3 clics (surlignage → lecture → heatmap → surlignage) qu'il faut adapter en 2 clics (surlignage → lecture → surlignage).

- [ ] **Step 8.4 — Adapter le test mobile**

Avant (extrait probable) :
```python
    # 5. Toggle mode (surlignage → lecture → heatmap)
    # / 5. Mode toggle (highlight → reading → heatmap)
    ...
        # 3 clics : surlignage → lecture → heatmap → surlignage
        # / 3 clicks: highlight → reading → heatmap → highlight
        bouton_mode.click()
        # ... assertion mode lecture ...
        bouton_mode.click()
        # ... assertion mode heatmap ...
        bouton_mode.click()
        # ... assertion mode surlignage ...
```

Après :
```python
    # 5. Toggle mode (surlignage → lecture, refonte A.2)
    # / 5. Mode toggle (highlight → reading, A.2 refactor)
    ...
        # 2 clics : surlignage → lecture → surlignage
        # / 2 clicks: highlight → reading → highlight
        bouton_mode.click()
        # ... assertion mode lecture ...
        bouton_mode.click()
        # ... assertion mode surlignage ...
```

À l'exécution : adapter en lisant le test exact, en retirant le 2e clic (qui passait à heatmap) et l'assertion sur `mode-heatmap-mobile`.

- [ ] **Step 8.5 — Vérifier l'absence de ref résiduelle**

```bash
rg "heatmap|HEATMAP|mode-heatmap" /home/jonas/Gits/Hypostasia/front/tests/e2e/
```
Attendu : 0 résultat.

- [ ] **Step 8.6 — Commit suggéré**

```
A.2 (8/9) — Adaptation des tests E2E (layout + mobile)

Retire la mention "heatmap" du docstring de test_07_layout.py
et adapte test_10_mobile.py pour le cycle mobile 2 modes
(surlignage → lecture → surlignage) au lieu de 3 modes.
```

---

### Task 9 : Vérification finale

**Files:** aucun (verification uniquement)

- [ ] **Step 9.1 — Grep final : aucune ref `heatmap` ne doit subsister hors PLAN/ et CHANGELOG**

```bash
rg "heatmap|HEATMAP|Heat map|--heatmap-|btn-toolbar-heatmap|mode-heatmap|basculerHeatmap|heatmapEstActive|interpoler_couleur_heatmap|data-heat-color|Phase19" /home/jonas/Gits/Hypostasia/ \
   --type-add 'web:*.{py,html,js,css}' -t web \
   -g '!PLAN/**' \
   -g '!CHANGELOG.md' 2>&1
```
Attendu : 0 résultat.

- [ ] **Step 9.2 — Django check final**

```bash
uv run python manage.py check
```
Attendu : `System check identified no issues (0 silenced).`

- [ ] **Step 9.3 — Lancer la suite de tests Django (Docker requis pour DB)**

```bash
docker exec <container_django> uv run python manage.py test front.tests.test_phases 2>&1 | tail -10
```
Attendu : tous les tests passent, aucune erreur d'import liée à `_interpoler_couleur_heatmap` ou autre symbole heatmap.

Si environnement Docker non actif, noter dans le commit final que cette vérif doit être faite par Jonas.

- [ ] **Step 9.4 — Test manuel UI complet (Firefox)**

1. `uv run python manage.py runserver 0.0.0.0:8123` (ou via Docker)
2. **Home anonyme** http://localhost:8123/ : onboarding s'affiche normalement
3. **Page de lecture** http://localhost:8123/lire/{id}/ :
   - Le contenu s'affiche, les surlignages par statut sont là (couleurs vert/orange/rouge)
   - Inspecter un span d'extraction : aucun `data-heat-color` n'apparaît
   - **Toolbar desktop** : pas de bouton heat map (icône thermomètre)
   - **Raccourci `H`** : aucun effet, aucune erreur console
   - **Raccourcis fonctionnels** : `T`, `E`, `J/K`, `C`, `S`, `X`, `A`, `Z`, `?`, `Esc`
4. **Mobile (DevTools responsive)** :
   - Bouton oeil dans la toolbar : 1er clic → mode lecture (pas de surlignage), 2e clic → retour mode surlignage
   - Pas de 3e mode heatmap
5. **Console JS** : aucune erreur `is not a function` ou similaire

- [ ] **Step 9.5 — Vérifier le cycle drawer vue liste / changement de filtre contributeurs**

Dans la zone de lecture, ouvrir le drawer vue liste (raccourci `E`), changer le filtre de contributeurs. Le contenu doit se recharger normalement, sans erreur JS (les 3 conditions `if (heatmapEstActive())` retirées en Task 4 ne doivent pas avoir cassé le flux).

- [ ] **Step 9.6 — (optionnel) CHANGELOG.md**

Si le projet maintient un CHANGELOG.md à la racine, ajouter une entrée :
```markdown
## A.2 — Retrait Heat map (PHASE-19) / Heat map removal

**Quoi / What:** Retrait complet de la feature heat map du débat (couche thermique au-dessus du dashboard de consensus).
**Pourquoi / Why:** YAGNI — personne ne s'en sert (décision YAGNI 2026-05-01). La géométrie du débat passe déjà par le dashboard de consensus, la palette Wong, l'alignement et les pastilles.

### Fichiers modifiés / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `front/utils.py` | Retrait `_interpoler_couleur_heatmap()` + injection `data-heat-color` |
| `front/templates/front/base.html` | Retrait bouton `#btn-toolbar-heatmap` |
| `front/static/front/js/marginalia.js` | Retrait API publique `basculerHeatmap`/`heatmapEstActive` + calque underlay |
| `front/static/front/js/keyboard.js` | Retrait raccourci `H` + cycle mobile passe de 3 à 2 modes |
| `front/static/front/js/bottom_sheet.js` | Retrait branches `mode-heatmap-mobile` |
| `front/static/front/js/drawer_vue_liste.js` | Retrait 3 conditions `heatmapEstActive()` |
| `front/static/front/css/hypostasia.css` | Retrait section heat map (variables, calque, body.mode-heatmap) |
| `front/tests/test_phases.py` | Retrait 8 classes `Phase19*` |
| `front/tests/e2e/test_07_layout.py` | Mise à jour docstring |
| `front/tests/e2e/test_10_mobile.py` | Adaptation cycle mobile 2 modes |

### Migration
- **Migration nécessaire / Migration required:** Non
```

Sinon, sauter ce step.

- [ ] **Step 9.7 — Pas de commit final si la vérification est OK** (les commits ont été suggérés à chaque task).

Si le CHANGELOG a été mis à jour en step 9.6, commit suggéré :
```
A.2 (cleanup) — CHANGELOG entry

Documente la session A.2 dans CHANGELOG.md.
```

---

## Sortie attendue à la fin de la session A.2

- 10 fichiers modifiés (~250 lignes nettes supprimées)
- 0 fichier créé
- 0 fichier supprimé
- 8 classes Django supprimées
- 1 test E2E adapté (cycle mobile 3→2 modes)
- 1 docstring mis à jour (test_07_layout.py)
- 7 commits proposés à Jonas (1, 2+3+4 groupé, 5, 6, 7, 8, éventuel 9 cleanup)
- L'arbre, l'extension navigateur, le drawer vue liste, le mode lecture mobile, l'alignement, le dashboard de consensus, le mode focus desktop : tous **inchangés**

## Risques identifiés et mitigation

| Risque | Mitigation |
|---|---|
| État JS intermédiaire entre Task 2 et Task 3 (consumers appellent une API qui n'existe plus) | Tasks 2+3+4 enchaînées sans test navigateur entre, commit groupé |
| Fonction `_calculer_scores_temperature()` non détectée dans le scan initial | Step 6.6 fait le grep avant suppression |
| Test E2E `test_10_mobile.py` casse à cause de l'adaptation 3→2 modes | Step 8.4 réécrit explicitement la séquence de clics ; runserver + DevTools mobile vérifie en step 9.4 |
| Tests d'autres phases utilisent indirectement `_interpoler_couleur_heatmap` ou la classe CSS `mode-heatmap` | Step 9.1 fait un grep exhaustif sur tous les patterns |
| Le subset Tailwind `tailwind.css` contient encore des refs heatmap | À vérifier : `rg "heatmap" /home/jonas/Gits/Hypostasia/static/css/tailwind.css` (si fichier existe). Le subset est généré, donc régénération nécessaire si refs trouvées |
| Cycle mobile 2-modes trouvé inutile par Jonas → veut option B (retirer le bouton) | Avant Task 3, vérifier la décision Q1 ; si option B, simplifier encore plus |

## Auto-revue

- ✅ Toutes les sections de la spec YAGNI 2026-05-01 §1 (Heat map) sont couvertes
- ✅ Tous les fichiers du scan ripgrep (10 fichiers, 240 refs) ont une task associée
- ✅ Décision Q1 (cycle mobile) explicitement flaggée en haut, option par défaut argumentée
- ✅ Aucun placeholder, aucun "TODO", aucun "fill in details"
- ✅ Chemins exacts pour chaque modification
- ✅ Ordre Task 2→3→4 enchaîné pour éviter état intermédiaire JS cassé
- ✅ Tous les commits suggérés respectent la préférence "pas de Co-Authored-By"
- ✅ Aucune commande git automatique — Jonas commit lui-même
- ✅ Onboarding `H` déjà retiré en A.1 — pas de double traitement

## Références

- Spec validée : [PLAN/REVUE_YAGNI_2026-05-01.md](REVUE_YAGNI_2026-05-01.md)
- Décisions YAGNI matin : [PLAN/discussions/YAGNI 2026-05-01.md](discussions/YAGNI%202026-05-01.md) §1 (Heat map)
- Plan A.1 (référence pour le format) : [PLAN/A.1-retrait-explorer.md](A.1-retrait-explorer.md)
- Skill obligatoire pour exécution : `superpowers:executing-plans`
