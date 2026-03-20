# Plan de tests — Hypostasia

> Document de reference pour l'architecture, la philosophie et l'inventaire des tests.
> A relire en debut de session quand on travaille sur les tests ou quand on ajoute une phase.
> Derniere mise a jour : 2026-03-20

---

## 1. Philosophie des tests

### Pourquoi les tests sont rapides (~800 tests en ~20s)

**Regle 1 — `TestCase` avec transactions, pas de vraie DB a chaque test**

Django `TestCase` wrappe chaque test dans une transaction SQL annulee a la fin (`ROLLBACK`).
Aucun `INSERT` ne persiste — c'est quasi instantane. Le gros du temps (~12s) c'est la
creation de la base de test + les migrations au debut. Les tests eux-memes tournent en ~5s.

**Regle 2 — Pas de serveur HTTP pour les tests unitaires**

`TestCase` utilise `self.client` — un client HTTP in-process qui appelle les vues Django
directement sans passer par le reseau. Zero latence TCP, zero serveur.

**Regle 3 — Tests purs sans I/O externe**

Aucun test n'appelle une API externe, ne lit un fichier sur disque, ni n'attend un timeout.
Les helpers diff (27b) sont des fonctions pures Python testees sans ORM.

**Regle 4 — Donnees minimales**

Chaque test ne cree que les objets dont il a besoin. Pas de `loaddata` d'un gros JSON.
`setUp` cree 2-3 objets max. Jamais de fixtures Django formelles.

**Regle 5 — Un navigateur par classe (E2E)**

`PlaywrightLiveTestCase` lance Chromium une fois par classe (`setUpClass`), ouvre un onglet
par test (`setUp`). Les tests E2E partagent le meme processus navigateur.

### Anti-patterns a eviter

| Symptome | Cause probable | Solution |
|----------|---------------|----------|
| Tests lents en base | `TransactionTestCase` au lieu de `TestCase` | `TestCase` partout sauf besoin reel de commit |
| Migrations longues | Beaucoup de migrations jouees a chaque run | `--keepdb` pour reutiliser la base de test |
| Appels reseau | Tests qui appellent des APIs ou services externes | Mocker les I/O externes |
| Fixtures lourdes | `loaddata` d'un gros JSON a chaque test | `setUp` minimal |
| Playwright lent | Un navigateur par test | Un navigateur par classe (`setUpClass`) |

### Choix de TestCase

| Type | Quand l'utiliser |
|------|-----------------|
| `SimpleTestCase` | Fonctions pures Python, pas d'acces DB (ex: parsing JSON, diff texte) |
| `TestCase` | Tout test qui touche l'ORM — transactions auto-rollback |
| `TransactionTestCase` | JAMAIS sauf si on a besoin de `on_commit()` ou de signaux post-transaction |
| `PlaywrightLiveTestCase` | Tests E2E navigateur — herite de `StaticLiveServerTestCase` |

### Convention de nommage

- Fichier : `test_phase{XX}{lettre}.py` (ex: `test_phase27b.py`)
- Classe : `{Concept}Test` (ex: `DiffParagraphesTest`, `ComparerActionTest`)
- Methode : `test_{ce_qui_est_verifie}` (ex: `test_paragraphe_modifie`)
- Docstring : une phrase en francais qui decrit le comportement attendu

---

## 2. Infrastructure

### Framework

- **Runner** : Django built-in test runner (`manage.py test`)
- **Pas de pytest** — pas de conftest.py, pytest.ini, tox.ini, setup.cfg
- **Decouverte** : auto (classes heritant de TestCase)

### Quand lancer quoi

| Moment | Quoi lancer | Temps | Commande |
|--------|-------------|-------|----------|
| Apres chaque modification | Tests unitaires de la phase en cours | ~5s | `test front.tests.test_phase27b` |
| Avant de valider une phase | Tous les tests unitaires | ~20s | `test front.tests --keepdb` |
| Verification ciblee E2E | Tests E2E du fichier concerne | ~40s | `test front.tests.e2e.test_20_tracabilite` |
| Avant un commit important | Suite E2E complete | ~19min | `test front.tests.e2e --keepdb` |
| Debug d'un test precis | Un seul test | ~3s | `test front.tests.e2e.test_20_tracabilite.E2ETracabiliteTest.test_bouton_historique_visible_dans_lecture` |

> **Regle d'or** : les unitaires tournent a chaque changement. Les E2E se lancent en cible
> ou en suite complete uniquement avant un jalon.

### Commandes

```bash
# === FREQUENTS (a chaque modification) ===

# Tests unitaires d'une phase (rapide, ~5s apres premiere run)
docker exec hypostasia_web uv run python manage.py test front.tests.test_phase27b -v2 --keepdb

# Tous les tests unitaires (sans E2E)
docker exec hypostasia_web uv run python manage.py test front.tests.test_phases front.tests.test_phase27a front.tests.test_phase27b front.tests.test_langextract_overrides -v2 --keepdb

# === CIBLES (verification ponctuelle) ===

# Tests E2E d'un seul fichier
docker exec hypostasia_web uv run python manage.py test front.tests.e2e.test_20_tracabilite -v2 --keepdb

# Un seul test precis
docker exec hypostasia_web uv run python manage.py test front.tests.e2e.test_20_tracabilite.E2ETracabiliteTest.test_bouton_historique_visible_dans_lecture -v2 --keepdb

# === COMPLETS (avant jalon) ===

# Suite E2E complete (~19 min)
docker exec hypostasia_web uv run python manage.py test front.tests.e2e -v2 --keepdb

# TOUT (unitaires + E2E, ~20 min)
docker exec hypostasia_web uv run python manage.py test front -v2 --keepdb
```

> **Toujours utiliser `--keepdb`** — economise ~12s de creation de base a chaque run.

### Structure des fichiers

```
front/tests/
├── __init__.py                         # Re-exports
├── README.md                           # Detail par phase (ancien, phases 01-07)
├── PLAN_TEST.md                        # CE FICHIER — vue d'ensemble et philosophie
├── test_phases.py                      # 209 classes, ~744 tests (phases 01-26h)
├── test_phase27a.py                    # 7 classes, 19 tests (tracabilite)
├── test_phase27b.py                    # 3 classes, 15 tests (diff versions)
├── test_langextract_overrides.py       # 3 classes, 18 tests (surcharges LLM)
└── e2e/
    ├── __init__.py                     # Re-exports (incomplet)
    ├── base.py                         # PlaywrightLiveTestCase (classe de base)
    ├── test_01_navigation.py           # 6 tests — arbre, dossiers, SweetAlert
    ├── test_02_lecture.py              # 5 tests — lecture page, F5, titre inline
    ├── test_03_import.py               # 3 tests — import .txt, .md
    ├── test_04_extractions.py          # 8 tests — cartes, statuts, pastilles
    ├── test_05_config_ia.py            # 3 tests — toggle IA, selection modele
    ├── test_06_charte_visuelle.py      # 6 tests — polices, CSS, WCAG
    ├── test_07_layout.py               # 8 tests — drawer, focus, raccourcis
    ├── test_08_curation.py             # 4 tests — masquer/restaurer
    ├── test_09_alignement.py           # 3 tests — tableau hypostases
    ├── test_10_mobile.py               # 27 tests — mobile 390px, bottom sheet
    ├── test_11_confirmation_analyse.py # 12 tests — tokens, cout, prompt
    ├── test_12_providers_ia.py         # 9 tests — Ollama, Anthropic, tarifs
    ├── test_13_auth.py                 # 11 tests — login, register, logout
    ├── test_14_visibilite.py           # 8 tests — public/prive/partage
    ├── test_15_token.py                # 4 tests — token API, regeneration
    ├── test_16_invitation_explorer.py  # 8 tests — invitations, suivis
    ├── test_17_filtre_contributeur.py  # 8 tests — pilules toggle, union
    ├── test_18_bibliotheque_analyseurs.py # 15 tests — grille, permissions, versions
    ├── test_19_credits.py              # 12 tests — solde, Stripe, cadeau
    └── test_20_tracabilite.py          # 12 tests — historique, diff versions
```

### Fichiers hors suite de tests (scripts manuels)

| Fichier | Role |
|---------|------|
| `test_analysis.py` (racine) | Script pour reproduire des problemes d'analyse en prod |
| `tools/test_langextract.py` | Script de demonstration du moteur LangExtract |

Ces fichiers ne sont PAS decouverts par `manage.py test` (pas de classe TestCase).

---

## 3. Tests E2E — infrastructure Playwright

### Classe de base : `PlaywrightLiveTestCase`

Fichier : `front/tests/e2e/base.py`

- Herite de `StaticLiveServerTestCase` (serveur Django live + fichiers statiques)
- Lance Chromium une fois par classe
- Ouvre un onglet par test
- Celery en mode eager (pas de worker, execution synchrone)

### Helpers disponibles

| Helper | Ce qu'il fait |
|--------|--------------|
| `naviguer_vers(chemin)` | goto + `wait_until="networkidle"` |
| `attendre_htmx(timeout_ms)` | Attend `.htmx-request` = 0 |
| `creer_page_demo(titre, texte)` | Cree une Page via ORM |
| `creer_dossier_demo(nom)` | Cree un Dossier via ORM |
| `creer_utilisateur_demo(username, password)` | Cree un User via ORM |
| `se_connecter(username, password)` | Navigue vers /auth/login/ + remplit formulaire |
| `ouvrir_arbre()` | Clique hamburger + attend overlay arbre visible |
| `ouvrir_drawer()` | Presse E + attend overlay drawer visible |

### Configuration

```python
@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
```

Mode headed (debug visuel) : `PLAYWRIGHT_HEADED=1`

### Probleme resolu (2026-03-20) : Chromium ne demarre pas

**Statut : CORRIGE** — l'erreur "Playwright Sync API inside asyncio loop" etait un
faux diagnostic. La vraie cause : **librairies systeme manquantes** pour Chromium
dans le container Docker (`libnspr4`, `libnss3`, etc.).

**Symptome** : Chromium crash au lancement → Playwright renvoyait une erreur trompeuse.

**Fix applique** :
```bash
docker exec -u root hypostasia_web apt-get install -y \
  libnspr4 libnss3 libatk1.0-0t64 libatk-bridge2.0-0t64 libcups2t64 \
  libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
  libpango-1.0-0 libcairo2 libasound2t64 libxshmfence1
```

**Attention** : ce fix est ephemere (perdu au rebuild du container). A ajouter dans
le `Dockerfile` ou `install.sh` pour que ce soit permanent.

---

## 4. Inventaire detaille — Tests unitaires

### test_phases.py — Le monolithe (phases 01 a 26h)

| Phase | Classes | Tests | Ce qui est couvert |
|-------|---------|-------|--------------------|
| 01 | 1 | 10 | Extraction CSS/JS depuis base.html |
| 02 | 7 | 29 | Assets locaux, polices, Tailwind, CDN, collectstatic |
| 03 | 4 | ~15 | LangExtract, job extraction, cleanup code |
| 04 | 9 | ~30 | CRUD (supprimer pages/dossiers, commentaires) |
| 06 | 4 | ~12 | Champs statut_debat, masquee, variables CSS |
| 07 | 5 | ~15 | Layout mono-colonne, nettoyage CSS/JS |
| 09 | 6 | ~20 | Marginalia, cartes inline, annotations |
| 10 | 5 | ~15 | Drawer, masquage entites |
| 15 | 4 | ~12 | Audio, transcription, diarisation |
| 17 | 2 | ~8 | Raccourcis clavier, mode focus |
| 18 | 10 | ~30 | Tableaux alignement, export Markdown |
| 19 | 8 | ~25 | Heatmap, temperature debat, couleurs |
| 20 | 8 | ~25 | Notifications, mouvements, updated_at |
| 21 | 7 | ~20 | Mobile, bottom sheet |
| 23 | 4 | ~12 | Confirmation analyse, preview |
| 24 | 18 | ~55 | LLM providers (Google, Ollama, Anthropic), tarifs |
| 25 | 36 | ~110 | Auth, ownership, visibility, sharing |
| 25b | 12 | ~35 | Token, extension, dedup |
| 25c | 20 | ~60 | Visibility, access control, moderation |
| 25d | 12 | ~35 | Invitations, explorer, followers |
| 26a | 14 | ~40 | Filtre contributeur, heatmap contributeur |
| 26b | 4 | ~12 | Permissions analyseurs, modeles, templates |
| 26c | 5 | ~15 | Ownership, auto-promotion, masquage |
| 26h | 11 | ~35 | Credits, Stripe, billing |
| **Total** | **~209** | **~744** | |

> **Note** : test_phases.py fait 9644 lignes. C'est un monolithe. Les phases futures
> (27a+) ont chacune leur propre fichier — c'est le pattern a suivre.

### test_phase27a.py — Tracabilite (19 tests)

| Classe | Tests | Focus |
|--------|-------|-------|
| `PageEditModelTest` | 7 | Creation PageEdit (titre, locuteur, contenu, bloc_transcription) |
| `SourceLinkModelTest` | 3 | Creation SourceLink, type_lien |
| `HistoriqueViewTest` | 4 | Vue /lire/{pk}/historique/ (HTMX + F5) |
| `HistoriqueContenuDiffTest` | 1 | Diff del/ins dans le contenu historique |
| `ModifierTitrePageEditTest` | 2 | Hook: modifier_titre cree PageEdit |
| `EditerBlocPageEditTest` | 1 | Hook: editer_bloc cree PageEdit |
| `RenommerLocuteurPageEditTest` | 1 | Hook: renommer_locuteur cree PageEdit |

### test_phase27b.py — Diff versions (15 tests)

| Classe | Tests | Focus |
|--------|-------|-------|
| `DiffInlineMotsTest` | 3 | Fonction _diff_inline_mots() — identique, modifie, XSS |
| `DiffParagraphesTest` | 7 | Fonction _diff_paragraphes() — identique, ajout, suppression, modification, vides |
| `ComparerActionTest` | 5 | Action comparer() — v2 explicite, parent, sans parent, F5, chaines differentes |

### test_langextract_overrides.py — Surcharges LLM (18 tests)

| Classe | Tests | Type | Focus |
|--------|-------|------|-------|
| `AutoWrapTableauJSONTest` | 8 | `SimpleTestCase` | Auto-wrap JSON array en objet |
| `DocumentationSurchargesTest` | 5 | `SimpleTestCase` | Documentation des surcharges dans le code |
| `ModeleAvecCompteurTokensTest` | 5 | `SimpleTestCase` | Compteur tokens input/output |

---

## 5. Inventaire detaille — Tests E2E

### Par domaine fonctionnel

#### Navigation et layout (tests 01, 02, 07, 10)

| Fichier | Tests | Couverture |
|---------|-------|-----------|
| `test_01_navigation.py` | 6 | Arbre dossiers, SweetAlert, classer page |
| `test_02_lecture.py` | 5 | Lecture page, F5, URL, titre inline |
| `test_07_layout.py` | 8 | Drawer, focus, raccourcis T/E/L/? |
| `test_10_mobile.py` | 27 | Mobile 390px, bottom sheet, gestes, modes |

#### Extractions et debat (tests 04, 08, 09, 17)

| Fichier | Tests | Couverture |
|---------|-------|-----------|
| `test_04_extractions.py` | 8 | Cartes, 4 statuts, pastilles, scroll |
| `test_08_curation.py` | 4 | Masquer/restaurer extractions |
| `test_09_alignement.py` | 3 | Tableau hypostases, gaps |
| `test_17_filtre_contributeur.py` | 8 | Pilules toggle, multi-contributeurs |

#### Configuration IA et analyse (tests 05, 11, 12)

| Fichier | Tests | Couverture |
|---------|-------|-----------|
| `test_05_config_ia.py` | 3 | Toggle IA, selection modele |
| `test_11_confirmation_analyse.py` | 12 | Tokens, cout, prompt complet |
| `test_12_providers_ia.py` | 9 | Ollama, Anthropic, tarifs |

#### Authentification et permissions (tests 13, 14, 15, 16)

| Fichier | Tests | Couverture |
|---------|-------|-----------|
| `test_13_auth.py` | 11 | Login, register, logout, menu user |
| `test_14_visibilite.py` | 8 | Public/prive/partage, 403 |
| `test_15_token.py` | 4 | Token API, regeneration |
| `test_16_invitation_explorer.py` | 8 | Invitations email, suivis, Explorer |

#### Features avancees (tests 03, 06, 18, 19, 20)

| Fichier | Tests | Couverture |
|---------|-------|-----------|
| `test_03_import.py` | 3 | Import .txt, .md |
| `test_06_charte_visuelle.py` | 6 | Polices B612/Lora/Srisakdi, WCAG |
| `test_18_bibliotheque_analyseurs.py` | 15 | Grille, permissions, versions, rollback |
| `test_19_credits.py` | 12 | Solde, Stripe, cadeau bienvenue |
| `test_20_tracabilite.py` | 12 | Historique, diff side-by-side |

---

## 6. Dependances des tests

### Modeles utilises par les tests unitaires

| Modele | App | Utilise dans |
|--------|-----|-------------|
| `Page` | core | test_phases, test_phase27a, test_phase27b |
| `Dossier` | core | test_phases, test_phase27a, test_phase27b |
| `PageEdit` | core | test_phase27a |
| `SourceLink` | core | test_phase27a |
| `Configuration` | core | test_phases |
| `AIModel` | core | test_phases |
| `User` | auth | test_phase27a, test_phase27b |
| `ExtractionJob` | hypostasis_extractor | test_phases |
| `ExtractedEntity` | hypostasis_extractor | test_phases |
| `CommentaireExtraction` | hypostasis_extractor | test_phases |
| `AnalyseurSyntaxique` | hypostasis_extractor | test_phases |

### Modeles utilises par les tests E2E

Memes modeles + interactions navigateur via Playwright.
Les tests E2E creent les donnees en `setUp` via ORM, puis naviguent dans le navigateur.

---

## 7. Problemes connus et axes d'amelioration

### P1 — Deps systeme Chromium manquantes dans le container (CORRIGE 2026-03-20)

- **Impact** : 0/169 tests E2E ne tournaient
- **Cause** : librairies systeme manquantes pour Chromium (libnspr4, libnss3, etc.)
- **Fix** : `apt-get install` des deps — ephemere, a ajouter au Dockerfile
- **Statut** : corrige, les E2E tournent maintenant

### P2 — test_phases.py est un monolithe (9644 lignes)

- **Impact** : difficile a naviguer, risque de conflits merge
- **Piste** : decouper en fichiers par phase (comme test_phase27a.py)
- **Priorite** : basse — ca fonctionne, c'est juste un confort de dev

### P3 — front/tests/e2e/__init__.py incomplet

- **Impact** : nul (Django autodiscovery fonctionne quand meme)
- **Piste** : mettre a jour les imports ou supprimer le fichier

### P4 — Aucun test dans core/ ni hypostasis_extractor/

- **Impact** : les modeles et vues de ces apps ne sont testes que via front/tests
- **Piste** : acceptable tant que front/tests couvre les cas — pas de duplication

### P5 — Pas de `--keepdb` par defaut

- **Impact** : les migrations rejouent a chaque run (~12s de perdu)
- **Piste** : ajouter `--keepdb` dans les commandes de reference

---

## 8. Metriques de reference

| Metrique | Valeur | Date |
|----------|--------|------|
| Tests unitaires (front) | ~796 | 2026-03-20 |
| Tests E2E definis | 121 (dont 12 skipped) | 2026-03-20 |
| Tests E2E qui passent | 109/121 (90%) | 2026-03-20 |
| Tests E2E en echec | 12 (timeouts fragiles + cosmétiques) | 2026-03-20 |
| Temps unitaires complets | ~20s | 2026-03-20 |
| Temps E2E complets | ~19min | 2026-03-20 |
| Temps creation base test | ~12s (economise avec --keepdb) | 2026-03-20 |
| Fichiers test | 24 | 2026-03-20 |
| Classes test | ~247 | 2026-03-20 |
| Lignes de code test | ~14700 | 2026-03-20 |

---

## 9. Checklist pour ajouter des tests a une nouvelle phase

1. Creer `front/tests/test_phase{XX}{lettre}.py`
2. Utiliser `TestCase` sauf si pur Python (`SimpleTestCase`)
3. Nommer les classes `{Concept}Test`, les methodes `test_{comportement}`
4. Docstring en francais sur chaque methode
5. `setUp` minimal : ne creer que les objets necessaires
6. Pas d'appels reseau, pas de `time.sleep()`, pas de fixtures Django
7. Ajouter les tests E2E dans `front/tests/e2e/test_{NN}_{nom}.py`
8. Mettre a jour `PLAN/PHASES/PHASE-{XX}.md` avec le tableau de suivi des tests
9. Mettre a jour `PLAN/PHASES/INDEX.md` (section suivi des tests)
10. Verifier : `docker exec hypostasia_web uv run python manage.py test front.tests.test_phase{XX} -v2`
