# Plan A.5 — Retrait Bibliothèque d'analyseurs (vue front)

> **Pour les workers agentiques :** ce plan suit la skill `superpowers:writing-plans`. Les étapes utilisent la syntaxe checkbox `- [ ]` pour le suivi. Voir [PLAN/REVUE_YAGNI_2026-05-01.md](REVUE_YAGNI_2026-05-01.md) pour le contexte.

**Goal :** retirer la **vue front** `/analyseurs/` (`BibliothequeAnalyseursViewSet` HTMX et ses 3 templates de grille/détail/dashboard). Conserver intégralement l'**API DRF JSON** `/api/analyseurs/` côté `hypostasis_extractor/` (éditeur admin) et toutes les queries `AnalyseurSyntaxique` dans `front/views.py`.

**Architecture :**
- Suppression du fichier `front/views_analyseurs.py` (173 lignes, 1 ViewSet `BibliothequeAnalyseursViewSet` avec `list`, `retrieve`, `dashboard_couts`)
- Suppression de la route `/analyseurs/` dans `front/urls.py`
- Suppression de 4 templates : `bibliotheque_analyseurs.html`, `detail_analyseur_readonly.html`, `carte_analyseur.html`, `dashboard_couts.html`
- Retrait du lien toolbar `/analyseurs/` dans `base.html` + 3 includes conditionnels
- Suppression des 4 classes `Phase26b*` dans `test_phases.py`
- Suppression du fichier E2E `test_18_bibliotheque_analyseurs.py` + son import dans `__init__.py`

**Tech stack :** Django 6 + DRF + HTMX + PostgreSQL. Stack-ccc / skill djc.

**Hors périmètre :**
- L'API DRF JSON `/api/analyseurs/` côté `hypostasis_extractor/` (conservée intégralement)
- L'éditeur DRF admin (`hypostasis_extractor/templates/`) — conservé
- Toutes les queries `AnalyseurSyntaxique.objects.filter(...)` et variables `analyseurs_actifs` dans `front/views.py` — conservées
- 3 messages d'erreur user-friendly mentionnant "/api/analyseurs/" comme hint admin (l. 1823, 2012, 2052) — conservés

**Préférences user :**
- Aucune commande git automatique
- Pas de `Co-Authored-By` dans les messages de commit
- Tests Django dans Docker via `docker exec hypostasia_web uv run python manage.py test --noinput`

---

## Décision actée (pas de question à valider)

**`dashboard_couts` retiré aussi** : vit dans le même ViewSet (`BibliothequeAnalyseursViewSet.dashboard_couts`), accessible via `/analyseurs/dashboard-couts/`, template dédié `dashboard_couts.html` sans autre usage. La donnée brute (`cout_reel_euros` sur `ExtractionJob`) reste accessible via Django admin si besoin.

---

## Cartographie des changements

### Fichiers supprimés (6)

| Fichier | Rôle |
|---|---|
| `front/views_analyseurs.py` | 1 ViewSet `BibliothequeAnalyseursViewSet` (3 actions) |
| `front/templates/front/includes/bibliotheque_analyseurs.html` | Grille de cartes |
| `front/templates/front/includes/detail_analyseur_readonly.html` | Détail readonly d'un analyseur |
| `front/templates/front/includes/carte_analyseur.html` | Card d'analyseur (utilisé par bibliotheque uniquement) |
| `front/templates/front/includes/dashboard_couts.html` | Tableau coûts staff-only |
| `front/tests/e2e/test_18_bibliotheque_analyseurs.py` | 362 lignes de tests E2E |

### Fichiers créés (0)

### Fichiers modifiés (4)

| Fichier | Changement |
|---|---|
| `front/urls.py` | Retirer ligne 8 (import `BibliothequeAnalyseursViewSet`) + ligne 28 (`router.register(r"analyseurs", ...)`) |
| `front/templates/front/base.html` | Retirer le bloc lien toolbar (l. 114-127 environ) + 3 includes conditionnels (`bibliotheque_analyseurs_preloaded` l. 285-286, `detail_analyseur_preloaded` l. 287-288, `dashboard_couts_preloaded` l. 293-294) |
| `front/tests/test_phases.py` | Retirer 4 classes Phase26b* (l. 8172 à fin du bloc) + commentaire de section |
| `front/tests/e2e/__init__.py` | Retirer ligne `from front.tests.e2e.test_18_bibliotheque_analyseurs import *` |

### Cas particuliers

**`carte_analyseur.html`** : utilisé UNIQUEMENT par `bibliotheque_analyseurs.html:60`. Confirmé via grep. Donc supprimé sans hésitation.

**`dashboard_couts_preloaded`** dans `base.html` : injecté uniquement par `BibliothequeAnalyseursViewSet.dashboard_couts()` (ligne 170 de `views_analyseurs.py`). Disparaît avec le ViewSet.

**Bornes Phase26b** : 4 classes (`Phase26bPermissionsTest` l. 8172, `Phase26bModelsTest` l. 8224, `Phase26bSnapshotTest` l. 8264, `Phase26bTemplatesTest` l. 8306). Fin du bloc à confirmer en lecture (avant la prochaine section, qui pourrait être un commentaire `# === PHASE-26X` ou une autre classe).

---

## Tâches

### Task 1 : Retrait `views_analyseurs.py` + route `/analyseurs/`

**Files:**
- Modify: `front/urls.py` (l. 8 import + l. 28 register)
- Delete: `front/views_analyseurs.py`

- [ ] **Step 1.1 — Modifier `front/urls.py`**

Retirer l'import :
```python
from .views_analyseurs import BibliothequeAnalyseursViewSet
```

Retirer le register :
```python
router.register(r"analyseurs", BibliothequeAnalyseursViewSet, basename="analyseur-biblio")
```

- [ ] **Step 1.2 — Supprimer `front/views_analyseurs.py`**

```bash
rm /home/jonas/Gits/Hypostasia/front/views_analyseurs.py
```

- [ ] **Step 1.3 — Vérifier qu'aucun autre fichier n'importe `BibliothequeAnalyseursViewSet`**

```bash
rg "BibliothequeAnalyseursViewSet|from front\.views_analyseurs|from \.views_analyseurs" /home/jonas/Gits/Hypostasia/
```
Attendu : 0 résultat (sauf PLAN/).

- [ ] **Step 1.4 — Django check**

```bash
docker exec hypostasia_web uv run python manage.py check 2>&1 | tail -3
```
Attendu : OK.

- [ ] **Step 1.5 — Commit suggéré**

```
A.5 (1/5) — Retrait ViewSet Bibliotheque + route /analyseurs/

Supprime front/views_analyseurs.py (BibliothequeAnalyseursViewSet
avec list/retrieve/dashboard_couts) et la route /analyseurs/ dans
front/urls.py. L'API DRF JSON /api/analyseurs/ cote
hypostasis_extractor/ reste intacte.
```

---

### Task 2 : Suppression des 4 templates + refs `base.html`

**Files:**
- Delete: 4 templates `front/templates/front/includes/`
- Modify: `front/templates/front/base.html`

- [ ] **Step 2.1 — Supprimer les 4 templates**

```bash
rm /home/jonas/Gits/Hypostasia/front/templates/front/includes/bibliotheque_analyseurs.html \
   /home/jonas/Gits/Hypostasia/front/templates/front/includes/detail_analyseur_readonly.html \
   /home/jonas/Gits/Hypostasia/front/templates/front/includes/carte_analyseur.html \
   /home/jonas/Gits/Hypostasia/front/templates/front/includes/dashboard_couts.html
```

- [ ] **Step 2.2 — Lire la zone du lien toolbar dans `base.html`**

```bash
Read /home/jonas/Gits/Hypostasia/front/templates/front/base.html offset=110 limit=20
```

Identifier le bloc :
```html
            <!-- Lien Bibliotheque analyseurs (PHASE-26b) -->
            <!-- / Analyzer library link (PHASE-26b) -->
            <a href="/analyseurs/"
               hx-get="/analyseurs/"
               hx-target="#zone-lecture"
               hx-swap="innerHTML"
               hx-push-url="/analyseurs/"
               class="..."
               title="Bibliothèque d'analyseurs" data-testid="btn-toolbar-analyseurs" aria-label="Bibliothèque d'analyseurs">
                <svg ...>
                    ...
                </svg>
            </a>
```

- [ ] **Step 2.3 — Supprimer le lien toolbar**

Edit : utiliser le bloc complet identifié en step 2.2 comme `old_string`, `new_string` = "" (ou minimum nécessaire).

- [ ] **Step 2.4 — Lire la zone des includes conditionnels dans `base.html`**

```bash
Read /home/jonas/Gits/Hypostasia/front/templates/front/base.html offset=280 limit=20
```

Identifier les blocs :
```html
            {% elif bibliotheque_analyseurs_preloaded %}
                {% include "front/includes/bibliotheque_analyseurs.html" %}
            {% elif detail_analyseur_preloaded %}
                {% include "front/includes/detail_analyseur_readonly.html" %}
            ...
            {% elif dashboard_couts_preloaded %}
                {% include "front/includes/dashboard_couts.html" %}
```

- [ ] **Step 2.5 — Retirer les 3 includes conditionnels**

Edit : retirer les 3 blocs `{% elif ... %} {% include ... %}` (6 lignes au total). Vérifier que la chaîne `{% if %} ... {% elif %} ... {% endif %}` reste cohérente après suppression.

- [ ] **Step 2.6 — Vérifier l'absence de ref résiduelle dans `base.html`**

```bash
rg "/analyseurs/|bibliotheque_analyseurs|detail_analyseur_readonly|dashboard_couts|carte_analyseur|btn-toolbar-analyseurs" /home/jonas/Gits/Hypostasia/front/templates/front/base.html
```
Attendu : 0 résultat.

- [ ] **Step 2.7 — Django check + test serveur**

```bash
docker exec hypostasia_web uv run python manage.py check 2>&1 | tail -3
```

- [ ] **Step 2.8 — Commit suggéré**

```
A.5 (2/5) — Retrait 4 templates Bibliotheque + refs base.html

Supprime bibliotheque_analyseurs.html, detail_analyseur_readonly.html,
carte_analyseur.html, dashboard_couts.html. Retire le lien toolbar
"/analyseurs/" et les 3 includes conditionnels
(bibliotheque_analyseurs_preloaded, detail_analyseur_preloaded,
dashboard_couts_preloaded) dans base.html.
```

---

### Task 3 : Retrait des 4 classes Phase26b* dans `test_phases.py`

**Files:**
- Modify: `front/tests/test_phases.py` (l. 8172 à fin du bloc Phase26b)

- [ ] **Step 3.1 — Identifier les bornes exactes**

```bash
rg -n "^class Phase26b|^class Phase|^# PHASE-26" /home/jonas/Gits/Hypostasia/front/tests/test_phases.py | head -10
```

Confirmer la première ligne (commentaire de section `# PHASE-26b ...` juste avant `Phase26bPermissionsTest`) et la dernière ligne (avant la prochaine section qui n'est pas Phase26b).

- [ ] **Step 3.2 — Lire le commentaire de section et la fin de Phase26bTemplatesTest**

```bash
Read /home/jonas/Gits/Hypostasia/front/tests/test_phases.py offset=8166 limit=12
Read /home/jonas/Gits/Hypostasia/front/tests/test_phases.py offset=8330 limit=15
```

- [ ] **Step 3.3 — Supprimer le bloc Phase26b via sed**

```bash
sed -i '<début>,<fin>d' /home/jonas/Gits/Hypostasia/front/tests/test_phases.py
```

À l'exécution : utiliser les valeurs exactes lues en step 3.2. Du commentaire de section `# PHASE-26b ...` jusqu'à la dernière ligne de `Phase26bTemplatesTest` (incluse).

- [ ] **Step 3.4 — Vérifier l'absence de ref résiduelle**

```bash
rg "Phase26b|bibliotheque_analyseurs|detail_analyseur_readonly|dashboard_couts|carte_analyseur|BibliothequeAnalyseursViewSet" /home/jonas/Gits/Hypostasia/front/tests/test_phases.py
```
Attendu : 0 résultat.

- [ ] **Step 3.5 — Lancer les tests Django**

```bash
docker exec hypostasia_web uv run python manage.py test front.tests.test_phases --noinput -v 0 2>&1 | tail -3
```
Attendu : OK.

- [ ] **Step 3.6 — Commit suggéré**

```
A.5 (3/5) — Retrait des 4 classes Phase26b* (Bibliotheque)

Supprime les 4 classes Phase26b* dans test_phases.py
(PermissionsTest, ModelsTest, SnapshotTest, TemplatesTest) et le
commentaire de section.
```

---

### Task 4 : Suppression test E2E `test_18_bibliotheque_analyseurs.py`

**Files:**
- Delete: `front/tests/e2e/test_18_bibliotheque_analyseurs.py`
- Modify: `front/tests/e2e/__init__.py` (retrait de l'import)

- [ ] **Step 4.1 — Supprimer le fichier**

```bash
rm /home/jonas/Gits/Hypostasia/front/tests/e2e/test_18_bibliotheque_analyseurs.py
```

- [ ] **Step 4.2 — Retirer l'import dans `__init__.py`**

```bash
Read /home/jonas/Gits/Hypostasia/front/tests/e2e/__init__.py
```

Retirer la ligne :
```python
from front.tests.e2e.test_18_bibliotheque_analyseurs import *  # noqa: F401,F403
```

- [ ] **Step 4.3 — Vérifier l'absence de ref**

```bash
rg "test_18_bibliotheque_analyseurs" /home/jonas/Gits/Hypostasia/
```
Attendu : 0 résultat hors PLAN/.

- [ ] **Step 4.4 — Commit suggéré**

```
A.5 (4/5) — Retrait test E2E test_18_bibliotheque_analyseurs.py

Supprime le fichier de tests E2E (362 lignes) et retire l'import
correspondant dans front/tests/e2e/__init__.py.
```

---

### Task 5 : Vérification finale

**Files:** aucun (verification uniquement)

- [ ] **Step 5.1 — Grep complet**

```bash
rg "BibliothequeAnalyseursViewSet|bibliotheque_analyseurs|detail_analyseur_readonly|dashboard_couts|dashboard-couts|carte_analyseur|btn-toolbar-analyseurs|Phase26b|test_18_bibliotheque_analyseurs|/analyseurs/|hx-get=\"/analyseurs|href=\"/analyseurs" /home/jonas/Gits/Hypostasia/ \
   --type-add 'web:*.{py,html,js,css}' -t web \
   -g '!PLAN/**' \
   -g '!CHANGELOG.md' \
   -g '!PLAN_TEST.md' 2>&1 | head -10
```

Attendu : 0 résultat. Les seules refs `/api/analyseurs/` doivent rester (intactes).

- [ ] **Step 5.2 — Vérifier que `/api/analyseurs/` reste intact**

```bash
rg "/api/analyseurs/" /home/jonas/Gits/Hypostasia/ --type-add 'web:*.{py,html,js,css}' -t web -g '!PLAN/**' | head -10
```

Attendu : refs dans `hypostasis_extractor/templates/`, `hypostasis_extractor/views.py`, `hypostasis_extractor/admin.py`, `hypostasia.js`, `front/views.py` (3 messages d'erreur), `test_phase29_synthese_drawer.py`. Toutes valides.

- [ ] **Step 5.3 — Django check**

```bash
docker exec hypostasia_web uv run python manage.py check 2>&1 | tail -3
```
Attendu : `System check identified no issues (0 silenced).`

- [ ] **Step 5.4 — Suite tests Django dans Docker**

```bash
docker exec hypostasia_web uv run python manage.py test front.tests.test_phases front.tests.test_phase28_light front.tests.test_phase29_normalize front.tests.test_phase29_synthese_drawer front.tests.test_phase27a front.tests.test_phase27b front.tests.test_analyse_drawer_unifie front.tests.test_langextract_overrides --noinput -v 0 2>&1 | tail -5
```
Attendu : tous les tests passent.

- [ ] **Step 5.5 — Test manuel UI complet (Firefox)**

1. `docker exec hypostasia_web uv run python manage.py runserver 0.0.0.0:8123` (ou via Traefik)
2. **Toolbar desktop** : pas de bouton "Bibliothèque d'analyseurs" (icône livre)
3. **URL `/analyseurs/`** : doit renvoyer 404 (route retirée)
4. **URL `/api/analyseurs/`** : doit toujours fonctionner et afficher l'éditeur DRF (zone admin)
5. **Lancer une analyse** : le sélecteur d'analyseur dans `confirmation_analyse.html` (utilisant `analyseurs_actifs` dans `front/views.py`) doit toujours fonctionner
6. **Bouton "Nouvel analyseur"** dans l'éditeur DRF (`hypostasia.js` POST `/api/analyseurs/`) doit toujours fonctionner

- [ ] **Step 5.6 — Pas de commit final si la vérification est OK**

---

## Sortie attendue à la fin de la session A.5

- 6 fichiers supprimés (1 ViewSet + 4 templates + 1 test E2E)
- 4 fichiers modifiés
- 4 classes Django supprimées
- ~5 commits proposés à Jonas
- L'API DRF `/api/analyseurs/` reste intacte
- Plus de bouton "Bibliothèque d'analyseurs" dans la toolbar
- L'admin/staff accède aux analyseurs via `/api/analyseurs/` directement (URL bookmarkable)

## Risques identifiés et mitigation

| Risque | Mitigation |
|---|---|
| Un test Django ailleurs utilise `BibliothequeAnalyseursViewSet` ou les templates | Step 1.3 + Step 5.1 grep exhaustif |
| Un autre template référence `bibliotheque_analyseurs_preloaded` ou `dashboard_couts_preloaded` | Step 5.1 grep exhaustif |
| `dashboard_couts.html` utilisé par un autre ViewSet | Confirmé non — seul `BibliothequeAnalyseursViewSet.dashboard_couts()` le rend |
| Un test E2E hors `test_18_bibliotheque_analyseurs.py` clique sur le bouton toolbar | Step 5.1 grep `btn-toolbar-analyseurs` ; si présent, supprimer l'usage |

## Auto-revue

- ✅ Toutes les sections de la spec YAGNI 2026-05-01 §3 (Bibliothèque analyseurs) sont couvertes
- ✅ Tous les fichiers du scan ripgrep ont une task associée
- ✅ Aucun placeholder
- ✅ Chemins exacts pour chaque modification
- ✅ Pas de modèle ni de migration (tout est front + tests)
- ✅ Décision dashboard_couts retiré documentée explicitement
- ✅ Tous les commits suggérés respectent la préférence "pas de Co-Authored-By"
- ✅ Aucune commande git automatique
- ✅ L'API DRF `/api/analyseurs/` est explicitement conservée (vérification step 5.2)

## Références

- Spec validée : [PLAN/REVUE_YAGNI_2026-05-01.md](REVUE_YAGNI_2026-05-01.md) §Q3
- Plans précédents : [PLAN/A.1-retrait-explorer.md](A.1-retrait-explorer.md), [PLAN/A.2-retrait-heatmap.md](A.2-retrait-heatmap.md), [PLAN/A.3-retrait-mode-focus.md](A.3-retrait-mode-focus.md), [PLAN/A.4-retrait-stripe.md](A.4-retrait-stripe.md)
- Skill obligatoire pour exécution : `superpowers:executing-plans`
