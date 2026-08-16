# Plan A.3 — Retrait Mode focus

> **Pour les workers agentiques :** ce plan suit la skill `superpowers:writing-plans`. Les étapes utilisent la syntaxe checkbox `- [ ]` pour le suivi. Voir [PLAN/REVUE_YAGNI_2026-05-01.md](REVUE_YAGNI_2026-05-01.md) pour le contexte.

**Goal :** retirer entièrement le mode focus desktop (PHASE-17 partielle), ses fonctions JS dans `marginalia.js`, le raccourci `L` dans `keyboard.js`, le bouton `#btn-toolbar-focus` dans `base.html`, la section CSS `.mode-focus`, la ligne `L Mode focus lecture` dans la modale d'aide raccourcis, et les 5 classes de tests `Phase17*`. Fonctionnalité **déléguée à Firefox Reader View** (icône native dans la barre d'URL).

**Architecture :**
- Suppression complète des fonctions `activerModeFocus()`, `desactiverModeFocus()`, `basculerModeFocus()`, `modeFocusEstActif()` et de la constante `CLE_LOCALSTORAGE_FOCUS` dans `marginalia.js`
- Retrait du `case 'l'` dans `keyboard.js` (3 lignes)
- Suppression du bouton `#btn-toolbar-focus` dans `base.html` (1 bloc)
- Retrait de la section CSS `body.mode-focus` (14 refs sur ~30 lignes) et du sélecteur `#btn-toolbar-focus { display: none; }` dans le bloc responsive mobile
- Suppression de l'entrée `("L", "Mode focus lecture")` dans la liste des raccourcis affichée par la modale d'aide (`front/views.py:1756`)
- Retrait de **5 classes de tests** Django `Phase17*` dans `test_phases.py`
- Adaptation des tests E2E `test_07_layout.py` (4 refs au mode focus)
- Vérification visuelle que **Firefox Reader View** s'active toujours sur `/lire/{id}/`

**Tech stack :** Django 6 + DRF + HTMX + Tailwind subset + JavaScript vanilla. Stack-ccc / skill djc. Conventions FR/EN bilingues.

**Hors périmètre :**
- Stripe / crédits prépayés → A.4
- Bibliothèque analyseurs → A.5
- Onboarding `onboarding_vide.html` raccourci `L` : déjà retiré préemptivement en A.1 step 5.3 ✅
- Modale d'aide HTML `aide_desktop.html` / `aide_mobile.html` : pas de ref `L` ou `mode-focus` (déjà clean) ✅

**Préférences user :**
- Aucune commande git automatique (commit géré par Jonas)
- Pas de `Co-Authored-By` dans les messages de commit
- Tests Django dans Docker via `docker exec hypostasia_web uv run python manage.py test --noinput`

---

## Cartographie des changements

### Fichiers supprimés (0)

Aucun fichier n'est supprimé entièrement.

### Fichiers créés (0)

### Fichiers modifiés (6)

| Fichier | Refs | Changement |
|---|---|---|
| `front/static/front/js/marginalia.js` | 23 | Retrait `CLE_LOCALSTORAGE_FOCUS`, fonctions `activerModeFocus`/`desactiverModeFocus`/`basculerModeFocus`/`modeFocusEstActif`, branche init au load, init bouton, exports publics, alias compatibilité, mention dans le header de fichier |
| `front/static/front/js/keyboard.js` | 3 | Retrait `case 'l'` (lignes 466-472 environ) |
| `front/static/front/css/hypostasia.css` | 14 | Retrait section `body.mode-focus` (~30 lignes) + sélecteur `#btn-toolbar-focus { display: none; }` dans le bloc responsive |
| `front/templates/front/base.html` | 1 | Retrait bouton `#btn-toolbar-focus` (l. 59 environ) |
| `front/views.py` | 1 | Retrait ligne `("L", "Mode focus lecture")` dans la liste raccourcis modale aide (l. 1756) |
| `front/tests/test_phases.py` | 15 | Retrait 5 classes `Phase17*` (l. 3574-3741 environ) + commentaire de section |
| `front/tests/e2e/test_07_layout.py` | 4 | Retrait des tests E2E focus mode + références dans le docstring si présentes |

### Cas particuliers

**Mention "Mode focus lecture immersive (PHASE-17)" dans le header de `marginalia.js`** : à retirer (similaire à ce qu'on a fait en A.2 pour `+ Heat map du debat (PHASE-19)`).

**Pas de fichier `test_phase17*.py` séparé** : tous les tests Phase17 sont dans `test_phases.py`.

**Onboarding `onboarding_vide.html`** : raccourci L déjà retiré en A.1 ✅.

**Aucune ref dans `front/views.py`** sauf la ligne de la modale d'aide.

---

## Tâches

### Task 1 : Retrait CSS `body.mode-focus`

**Files:**
- Modify: `front/static/front/css/hypostasia.css` (section `mode-focus` + sélecteur responsive)

- [ ] **Step 1.1 — Localiser la section CSS mode focus**

```bash
rg -n "mode-focus|btn-toolbar-focus" /home/jonas/Gits/Hypostasia/front/static/front/css/hypostasia.css
```
Identifier les bornes exactes du bloc principal et du sélecteur responsive.

- [ ] **Step 1.2 — Lire le bloc principal et le contexte responsive**

```python
Read /home/jonas/Gits/Hypostasia/front/static/front/css/hypostasia.css offset=<début bloc> limit=40
Read /home/jonas/Gits/Hypostasia/front/static/front/css/hypostasia.css offset=<bloc responsive> limit=15
```

- [ ] **Step 1.3 — Supprimer le bloc principal `body.mode-focus`**

Le bloc contient les sélecteurs CSS qui :
- Masquent les pastilles en marge (`body.mode-focus .pastilles-marge { display: none; }`)
- Centrent le texte (max-width sur `#readability-content`)
- Désactivent le surlignage individuel (`body.mode-focus .hl-extraction { ... }`)

À l'exécution : utiliser `Edit` avec `old_string` = le bloc complet (40 lignes environ) et `new_string` = "" (ou ajustement minimal).

- [ ] **Step 1.4 — Modifier le bloc responsive mobile (sélecteur `#btn-toolbar-focus`)**

Avant (ajusté en A.2) :
```css
    /* Sur mobile on masque Focus (remplace par le toggle mode) */
    /* / On mobile hide Focus (replaced by mode toggle) */
    #btn-toolbar-focus { display: none; }
```
Après : supprimer entièrement les 3 lignes (le bouton focus n'existant plus, plus besoin de le masquer).

- [ ] **Step 1.5 — Vérifier l'absence de ref résiduelle**

```bash
rg "mode-focus|btn-toolbar-focus|\.mode-focus" /home/jonas/Gits/Hypostasia/front/static/front/css/hypostasia.css
```
Attendu : 0 résultat.

- [ ] **Step 1.6 — Commit suggéré**

```
A.3 (1/7) — Retrait CSS mode focus (PHASE-17 partielle)

Supprime la section CSS body.mode-focus et le sélecteur responsive
#btn-toolbar-focus. Premier commit du retrait mode focus
(session A.3 de la revue YAGNI 2026-05-01). Fonctionnalité déléguée
à Firefox Reader View (icône native dans la barre d'URL).
```

---

### Task 2 : Retrait JS mode focus dans `marginalia.js`

**Files:**
- Modify: `front/static/front/js/marginalia.js` (23 refs sur ~600 lignes)

**ATTENTION** : `marginalia.js` expose `window.marginalia.basculerModeFocus()` qui est appelé par `keyboard.js` (Task 3). Faire Task 2 + Task 3 + Task 4 d'affilée sans test navigateur entre, pour éviter une erreur JS intermédiaire (comme A.2 Tasks 2+3+4).

- [ ] **Step 2.1 — Mettre à jour le header de fichier (l. 1-26 environ)**

Avant :
```js
// ==========================================================================
// marginalia.js — Pastilles en marge droite + cartes inline (PHASE-09)
//                 + Mode focus lecture immersive (PHASE-17)
// / Right margin dots + inline cards (PHASE-09)
// / + Immersive focus reading mode (PHASE-17)
//
// LOCALISATION : front/static/front/js/marginalia.js
//
// Ce fichier gere les pastilles colorees en marge droite du texte.
// Chaque pastille represente une extraction. Sa couleur reflete le statut de debat.
// Un clic sur une pastille charge une carte inline via HTMX (endpoint carte_inline).
// La carte s'insere sous le paragraphe concerne avec une animation.
// Le mode focus (PHASE-17) masque les pastilles et centre le texte.
//
// COMMUNICATION :
// Recoit : htmx:afterSwap sur #zone-lecture -> reconstruit les pastilles
// Recoit : HX-Trigger contributeurFiltreChange -> filtre pastilles (PHASE-26a-bis)
//          avec mode_filtre 'inclure'|'exclure' pour inverser le dimming (PHASE-26a UX)
// Appelle : GET /extractions/carte_inline/?entity_id=N (front/views.py ExtractionViewSet)
// Exporte : window.marginalia = { construirePastillesMarginales, fermerCarteInline,
//           basculerModeFocus, desactiverModeFocus, modeFocusEstActif,
//           getContributeurFiltre, resetContributeurFiltre }
// Exporte : window.construirePastillesMarginales (alias global, utilise par drawer_vue_liste.js)
// ==========================================================================
```
Après :
```js
// ==========================================================================
// marginalia.js — Pastilles en marge droite + cartes inline (PHASE-09)
// / Right margin dots + inline cards (PHASE-09)
//
// LOCALISATION : front/static/front/js/marginalia.js
//
// Ce fichier gere les pastilles colorees en marge droite du texte.
// Chaque pastille represente une extraction. Sa couleur reflete le statut de debat.
// Un clic sur une pastille charge une carte inline via HTMX (endpoint carte_inline).
// La carte s'insere sous le paragraphe concerne avec une animation.
//
// COMMUNICATION :
// Recoit : htmx:afterSwap sur #zone-lecture -> reconstruit les pastilles
// Recoit : HX-Trigger contributeurFiltreChange -> filtre pastilles (PHASE-26a-bis)
//          avec mode_filtre 'inclure'|'exclure' pour inverser le dimming (PHASE-26a UX)
// Appelle : GET /extractions/carte_inline/?entity_id=N (front/views.py ExtractionViewSet)
// Exporte : window.marginalia = { construirePastillesMarginales, fermerCarteInline,
//           getContributeurFiltre, resetContributeurFiltre }
// Exporte : window.construirePastillesMarginales (alias global, utilise par drawer_vue_liste.js)
// ==========================================================================
```

- [ ] **Step 2.2 — Retirer la constante `CLE_LOCALSTORAGE_FOCUS`**

Localiser et supprimer entièrement :
```js
    // Cle localStorage pour persister le mode focus entre rechargements
    // / localStorage key to persist focus mode between reloads
    var CLE_LOCALSTORAGE_FOCUS = 'hypostasia-mode-focus';
```

- [ ] **Step 2.3 — Retirer le bloc complet "=== Mode focus (PHASE-17) ==="**

Localiser le bloc qui contient les 4 fonctions :
```js
    // === Mode focus (PHASE-17) ===
    // / === Focus mode (PHASE-17) ===

    // Active le mode focus : masque pastilles, desactive surlignage, centre le texte
    function activerModeFocus() { ... }

    function desactiverModeFocus() { ... }

    function basculerModeFocus() { ... }

    function modeFocusEstActif() { ... }
```

Supprimer entièrement le bloc (de "=== Mode focus" jusqu'à la fin de `modeFocusEstActif()`).

- [ ] **Step 2.4 — Retirer la branche d'init au DOMContentLoaded**

Localiser et supprimer :
```js
        // Restaurer le mode focus si actif dans localStorage (PHASE-17)
        // / Restore focus mode if active in localStorage (PHASE-17)
        if (localStorage.getItem(CLE_LOCALSTORAGE_FOCUS) === 'actif') {
            activerModeFocus();
        }

        // Clic sur le bouton focus dans la toolbar (PHASE-17)
        // / Click on focus button in toolbar (PHASE-17)
        var boutonFocus = document.getElementById('btn-toolbar-focus');
        if (boutonFocus) {
            boutonFocus.addEventListener('click', basculerModeFocus);
        }
```

- [ ] **Step 2.5 — Retirer les exports publics dans `window.marginalia`**

Avant :
```js
    window.marginalia = {
        construirePastillesMarginales: construirePastillesMarginales,
        fermerCarteInline: fermerCarteInline,
        basculerModeFocus: basculerModeFocus,
        desactiverModeFocus: desactiverModeFocus,
        modeFocusEstActif: modeFocusEstActif,
        getContributeurFiltre: getContributeurFiltre,
        resetContributeurFiltre: resetContributeurFiltre,
    };
```
Après :
```js
    window.marginalia = {
        construirePastillesMarginales: construirePastillesMarginales,
        fermerCarteInline: fermerCarteInline,
        getContributeurFiltre: getContributeurFiltre,
        resetContributeurFiltre: resetContributeurFiltre,
    };
```

- [ ] **Step 2.6 — Vérifier l'absence de ref résiduelle**

```bash
rg "mode-focus|mode_focus|modeFocus|CLE_LOCALSTORAGE_FOCUS|basculerModeFocus|modeFocusEstActif|activerModeFocus|desactiverModeFocus|btn-toolbar-focus" /home/jonas/Gits/Hypostasia/front/static/front/js/marginalia.js
```
Attendu : 0 résultat.

- [ ] **Step 2.7 — NE PAS commiter** — enchaîner Task 3 immédiatement (sinon `keyboard.js` `case 'l'` appelle `window.marginalia.basculerModeFocus()` qui n'existe plus → erreur JS).

---

### Task 3 : Retrait raccourci `L` dans `keyboard.js`

**Files:**
- Modify: `front/static/front/js/keyboard.js` (lignes 466-472 environ)

- [ ] **Step 3.1 — Localiser le `case 'l'`**

```bash
rg -n "case 'l'|case \"l\"|basculerModeFocus" /home/jonas/Gits/Hypostasia/front/static/front/js/keyboard.js
```

- [ ] **Step 3.2 — Lire le contexte**

```python
Read /home/jonas/Gits/Hypostasia/front/static/front/js/keyboard.js offset=460 limit=20
```

- [ ] **Step 3.3 — Supprimer le `case 'l'`**

Avant (à confirmer en lecture) :
```js
            // L → Toggle mode focus lecture (PHASE-17)
            // / L → Toggle focus reading mode (PHASE-17)
            case 'l':
                if (window.marginalia) {
                    window.marginalia.basculerModeFocus();
                }
                evenement.preventDefault();
                break;
```
Supprimer entièrement les ~7 lignes.

- [ ] **Step 3.4 — Vérifier l'absence de ref résiduelle**

```bash
rg "mode-focus|modeFocus|basculerModeFocus" /home/jonas/Gits/Hypostasia/front/static/front/js/keyboard.js
```
Attendu : 0 résultat.

- [ ] **Step 3.5 — NE PAS commiter** — enchaîner Task 4 (bouton toolbar à retirer dans `base.html`).

---

### Task 4 : Retrait bouton `#btn-toolbar-focus` dans `base.html`

**Files:**
- Modify: `front/templates/front/base.html` (ligne 59 environ)

- [ ] **Step 4.1 — Localiser le bouton**

```bash
rg -n "btn-toolbar-focus" /home/jonas/Gits/Hypostasia/front/templates/front/base.html
```

- [ ] **Step 4.2 — Lire le contexte**

```python
Read /home/jonas/Gits/Hypostasia/front/templates/front/base.html offset=55 limit=15
```

- [ ] **Step 4.3 — Supprimer le bouton focus**

Avant (à confirmer en lecture) :
```html
            <!-- Bouton mode focus lecture (PHASE-17) -->
            <!-- / Focus reading mode button (PHASE-17) -->
            <button id="btn-toolbar-focus" class="btn-toolbar" title="Mode focus lecture (L)" data-testid="btn-toolbar-focus">
                <svg ...>
                    ...
                </svg>
                <span class="btn-toolbar-label">Lecture</span>
            </button>
```
Supprimer entièrement le bloc.

- [ ] **Step 4.4 — Vérifier l'absence de ref résiduelle**

```bash
rg "btn-toolbar-focus|mode-focus|Mode focus" /home/jonas/Gits/Hypostasia/front/templates/front/base.html
```
Attendu : 0 résultat.

- [ ] **Step 4.5 — Tester en navigateur (premier point de contrôle visuel)**

```bash
docker exec hypostasia_web uv run python manage.py runserver 0.0.0.0:8123
```
- Ouvrir http://localhost:8123/, naviguer vers `/lire/{id}/`
- **Vérifier console JS** : aucune erreur `basculerModeFocus is not a function`
- **Tester le raccourci `L`** : doit ne rien faire (pas d'erreur)
- **Toolbar desktop** : pas de bouton "Lecture" (icône livre)
- Le clavier `T`, `E`, `J/K`, `C`, `S`, `X`, `A`, `Z` doivent toujours fonctionner

- [ ] **Step 4.6 — Commit suggéré (groupé Tasks 2+3+4)**

```
A.3 (2+3+4/7) — Retrait JS mode focus (marginalia, keyboard, base.html)

Supprime les fonctions activerModeFocus/desactiverModeFocus/
basculerModeFocus/modeFocusEstActif et la constante
CLE_LOCALSTORAGE_FOCUS dans marginalia.js. Retire le case 'l' dans
keyboard.js. Supprime le bouton #btn-toolbar-focus de base.html.
Tasks regroupees pour eviter un etat intermediaire ou keyboard.js
appelle une API qui n'existe plus.
```

---

### Task 5 : Retrait ligne `L` dans la modale d'aide (`views.py`)

**Files:**
- Modify: `front/views.py` (ligne 1756 environ)

- [ ] **Step 5.1 — Lire le contexte de la liste de raccourcis**

```python
Read /home/jonas/Gits/Hypostasia/front/views.py offset=1750 limit=20
```

- [ ] **Step 5.2 — Supprimer la ligne `("L", "Mode focus lecture")`**

Avant :
```python
            ("J", "Extraction suivante"),
            ("K", "Extraction precedente"),
            ("L", "Mode focus lecture"),
            ("C", "Commenter l'extraction selectionnee"),
```
Après :
```python
            ("J", "Extraction suivante"),
            ("K", "Extraction precedente"),
            ("C", "Commenter l'extraction selectionnee"),
```

À l'exécution : utiliser le pattern exact lu en step 5.1 (les apostrophes peuvent être Unicode `’`).

- [ ] **Step 5.3 — Django check**

```bash
docker exec hypostasia_web uv run python manage.py check 2>&1 | tail -3
```
Attendu : `System check identified no issues (0 silenced).`

- [ ] **Step 5.4 — Commit suggéré**

```
A.3 (5/7) — Retrait ligne L dans la modale d'aide raccourcis

Supprime l'entrée ("L", "Mode focus lecture") de la liste des
raccourcis affichee par la modale d'aide accessible via le
raccourci `?` (front/views.py l. 1756).
```

---

### Task 6 : Retrait des 5 classes de tests Django `Phase17*`

**Files:**
- Modify: `front/tests/test_phases.py` (lignes 3574-3741 environ)

- [ ] **Step 6.1 — Identifier les bornes exactes**

```bash
rg -n "^class Phase17|^class Phase18" /home/jonas/Gits/Hypostasia/front/tests/test_phases.py | head -10
```
Confirmer : 5 classes Phase17* + première classe Phase18 à conserver.

- [ ] **Step 6.2 — Lire le commentaire de section et la fin de la dernière classe**

```python
Read /home/jonas/Gits/Hypostasia/front/tests/test_phases.py offset=3565 limit=15
Read /home/jonas/Gits/Hypostasia/front/tests/test_phases.py offset=3770 limit=15
```

Le commentaire de section "PHASE-17 — Mode focus" est avant la première classe (vers l. 3568). Identifier la dernière ligne de `Phase17BaseHTMLTest` et la première ligne de `Phase18FichiersStatiquesTest` (ligne 3777 vue dans le scan A.2).

- [ ] **Step 6.3 — Supprimer le bloc Phase17 entier via sed**

```bash
sed -i '<début>,<fin>d' /home/jonas/Gits/Hypostasia/front/tests/test_phases.py
```
où `<début>` = ligne du commentaire de section `# PHASE-17 — Mode focus` (vers 3568), `<fin>` = dernière ligne avant `# PHASE-18 ...` (vers 3775).

À l'exécution : utiliser les valeurs exactes lues en step 6.2.

- [ ] **Step 6.4 — Vérifier l'absence de ref résiduelle**

```bash
rg "Phase17|mode-focus|modeFocus|basculerModeFocus|btn-toolbar-focus|CLE_LOCALSTORAGE_FOCUS" /home/jonas/Gits/Hypostasia/front/tests/test_phases.py
```
Attendu : 0 résultat.

- [ ] **Step 6.5 — Vérifier qu'aucun autre test Phase18+ ne dépende du mode focus**

```bash
rg "mode-focus|modeFocus|basculerModeFocus|btn-toolbar-focus|CLE_LOCALSTORAGE_FOCUS" /home/jonas/Gits/Hypostasia/front/tests/
```
Attendu : seulement les 4 refs dans `test_07_layout.py` (E2E, Task 7).

Si un test Phase18+ dépend du mode focus (improbable mais possible), le supprimer / l'adapter dans cette task.

- [ ] **Step 6.6 — Lancer les tests Django dans Docker**

```bash
docker exec hypostasia_web uv run python manage.py test front.tests.test_phases --noinput -v 0 2>&1 | tail -10
```
Attendu : tous les tests restants passent. Aucune erreur d'import.

- [ ] **Step 6.7 — Commit suggéré**

```
A.3 (6/7) — Retrait des 5 classes de tests Phase17* (mode focus)

Supprime les 5 classes Phase17* dans test_phases.py
(FichierKeyboardJSTest, MarginaliaModeFocusTest,
ListenersSupprimesDansModulesTest, CSSStylesTest, BaseHTMLTest)
et le commentaire de section. Fonctionnalite deleguee a
Firefox Reader View.
```

---

### Task 7 : Adapter le test E2E `test_07_layout.py` (4 refs mode focus)

**Files:**
- Modify: `front/tests/e2e/test_07_layout.py` (4 refs à retirer)

- [ ] **Step 7.1 — Localiser les refs**

```bash
rg -n "mode-focus|modeFocus|btn-toolbar-focus|focus mode|Focus mode" /home/jonas/Gits/Hypostasia/front/tests/e2e/test_07_layout.py
```

- [ ] **Step 7.2 — Lire les zones concernées**

Lire le docstring d'en-tête (qui mentionne "focus mode" depuis A.2 step 8.1) et chaque test qui utilise le mode focus.

- [ ] **Step 7.3 — Mettre à jour le docstring d'en-tête**

Avant (déjà ajusté en A.2 step 8.1) :
```python
"""
Tests E2E — Layout : drawer, focus mode, raccourcis clavier.
/ E2E tests — Layout: drawer, focus mode, keyboard shortcuts.
"""
```
Après :
```python
"""
Tests E2E — Layout : drawer, raccourcis clavier.
/ E2E tests — Layout: drawer, keyboard shortcuts.
"""
```

- [ ] **Step 7.4 — Supprimer les méthodes de test E2E mode focus**

Identifier les méthodes `test_*` qui testent le mode focus (vraisemblablement 1-3 méthodes : ouverture du focus, fermeture, persistance). Les supprimer entièrement.

À l'exécution : pour chaque méthode trouvée, utiliser `Edit` avec `old_string` = la méthode complète et `new_string` = "".

- [ ] **Step 7.5 — Vérifier l'absence de ref résiduelle**

```bash
rg "mode-focus|modeFocus|btn-toolbar-focus|focus mode|Focus mode|basculerModeFocus" /home/jonas/Gits/Hypostasia/front/tests/e2e/test_07_layout.py
```
Attendu : 0 résultat.

- [ ] **Step 7.6 — Commit suggéré**

```
A.3 (7/7) — Adaptation du test E2E layout (retrait mode focus)

Retire les tests E2E du mode focus dans test_07_layout.py et met
a jour le docstring. Fonctionnalite deleguee a Firefox Reader View.
```

---

### Task 8 : Vérification finale + test Reader View

**Files:** aucun (verification uniquement)

- [ ] **Step 8.1 — Grep complet : aucune ref `mode-focus` ne doit subsister**

```bash
rg "mode-focus|mode_focus|modeFocus|btn-toolbar-focus|CLE_LOCALSTORAGE_FOCUS|basculerModeFocus|modeFocusEstActif|activerModeFocus|desactiverModeFocus|Mode focus|Phase17" /home/jonas/Gits/Hypostasia/ \
   --type-add 'web:*.{py,html,js,css}' -t web \
   -g '!PLAN/**' \
   -g '!CHANGELOG.md' 2>&1
```
Attendu : 0 résultat.

- [ ] **Step 8.2 — Django check**

```bash
docker exec hypostasia_web uv run python manage.py check 2>&1 | tail -3
```
Attendu : `System check identified no issues (0 silenced).`

- [ ] **Step 8.3 — Lancer la suite de tests Django dans Docker**

```bash
docker exec hypostasia_web uv run python manage.py test --noinput -v 0 2>&1 | tail -5
```
Attendu : tous les tests passent (~680 tests, baisse vs A.2 car ~5-9 tests Phase17 retirés).

- [ ] **Step 8.4 — Test manuel UI complet (Firefox)**

1. `docker exec hypostasia_web uv run python manage.py runserver 0.0.0.0:8123` (ou via Traefik)
2. **Page de lecture** http://localhost:8123/lire/{id}/ :
   - **Toolbar desktop** : pas de bouton focus (icône livre "Lecture")
   - **Raccourci `L`** : aucun effet, aucune erreur console
   - **Modale d'aide** (raccourci `?`) : plus de ligne `L Mode focus lecture`
   - **Raccourcis fonctionnels** : `T`, `E`, `J/K`, `C`, `S`, `X`, `A`, `Z`, `?`, `Esc`
3. **Console JS** : aucune erreur `is not a function` ou similaire

- [ ] **Step 8.5 — Vérification Firefox Reader View (le remplacement)**

1. Toujours sur `/lire/{id}/` dans Firefox
2. **Icône Reader View** (livre ouvert) doit apparaître dans la barre d'URL
3. Cliquer dessus → Mozilla Readability extrait le texte de `<article id="readability-content">`
4. La page Reader View affiche :
   - Le titre `<h1>` de la page
   - Le contenu de l'article épuré (pas de toolbar, pas de pastilles, pas de surlignage)
   - L'utilisateur peut basculer en/hors Reader View librement (F9 ou clic icône)

**Si l'icône n'apparaît pas** :
- Vérifier que `<article id="readability-content">` est bien présent dans le DOM (inspecter)
- Vérifier que le contenu fait > 250 caractères (seuil Mozilla Readability)
- Si toujours absent : noter pour ajuster `<meta name="description">` ou `<meta name="author">` dans `base.html` lors d'une session ultérieure

- [ ] **Step 8.6 — Vérification raccourcis restants**

Modale d'aide (`?`) doit afficher uniquement les raccourcis encore actifs : `T`, `E`, `J`, `K`, `C`, `S`, `X`, `A`, `Z`, `?`, `Esc`. Plus de `L` ni `H` (retiré en A.2).

- [ ] **Step 8.7 — Pas de commit final si la vérification est OK** (les commits ont été suggérés à chaque task).

---

## Sortie attendue à la fin de la session A.3

- 6 fichiers modifiés (~80-150 lignes nettes supprimées)
- 0 fichier créé
- 0 fichier supprimé
- 5 classes Django Phase17* supprimées
- 1-3 tests E2E focus mode supprimés + docstring mis à jour
- 5 commits proposés à Jonas (1, 2+3+4 groupé, 5, 6, 7)
- Mode focus délégué à Firefox Reader View (vérifié visuellement)

## Risques identifiés et mitigation

| Risque | Mitigation |
|---|---|
| État JS intermédiaire entre Task 2 et Task 3 (keyboard appelle une API qui n'existe plus) | Tasks 2+3+4 enchaînées sans test navigateur entre, commit groupé |
| Firefox Reader View ne détecte pas la page de lecture | Step 8.5 vérifie ; si problème, ajouter `<meta name="description">` (hors périmètre A.3, à scoper séparément) |
| Tests Phase18+ utilisent indirectement le mode focus | Step 6.5 fait un grep exhaustif |
| Documentation `marginalia.js` mentionne PHASE-17 ailleurs que le header | Step 2.6 fait un grep exhaustif sur tous les patterns |

## Auto-revue

- ✅ Toutes les sections de la spec YAGNI 2026-05-01 §2 (Mode focus) sont couvertes
- ✅ Tous les fichiers du scan ripgrep (6 fichiers, 60 refs) ont une task associée
- ✅ Aucun placeholder, aucun "TODO"
- ✅ Chemins exacts pour chaque modification
- ✅ Ordre Task 2→3→4 enchaîné pour éviter état JS intermédiaire
- ✅ Tous les commits suggérés respectent la préférence "pas de Co-Authored-By"
- ✅ Aucune commande git automatique
- ✅ Onboarding `L` déjà retiré en A.1 — pas de double traitement
- ✅ Sélecteur CSS responsive `#btn-toolbar-focus { display: none; }` (laissé en A.2 step 1.2) sera retiré en A.3 Task 1.4

## Références

- Spec validée : [PLAN/REVUE_YAGNI_2026-05-01.md](REVUE_YAGNI_2026-05-01.md)
- Décisions YAGNI matin : [PLAN/discussions/YAGNI 2026-05-01.md](discussions/YAGNI%202026-05-01.md) §2 (Mode focus)
- Plans précédents : [PLAN/A.1-retrait-explorer.md](A.1-retrait-explorer.md), [PLAN/A.2-retrait-heatmap.md](A.2-retrait-heatmap.md)
- Skill obligatoire pour exécution : `superpowers:executing-plans`
