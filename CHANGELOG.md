# Changelog — Hypostasia V3

> Journal des modifications par phase. Format bilingue FR/EN.
> Reverse chronological order.

---

## 2026-03-15 — PHASE-25 : Users et partage

**Quoi / What:** Authentification Django (login/register/logout), propriete des ressources
(owner sur Dossier/Page), remplacement de `prenom` par `user` FK obligatoire sur
CommentaireExtraction/Question/ReponseQuestion, partage binaire de dossiers (DossierPartage),
protection des ecritures (lectures restent publiques).

**Pourquoi / Why:** L'app fonctionnait en mono-utilisateur avec identification par prenom libre.
Cette phase ajoute une vraie authentification pour tracer les contributions et permettre
le partage de dossiers entre utilisateurs.

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `core/models.py` | +owner sur Dossier/Page, +DossierPartage, user FK sur Question/ReponseQuestion |
| `hypostasis_extractor/models.py` | user FK remplace prenom sur CommentaireExtraction |
| `core/migrations/0021_*.py` | Migration PHASE-25 (owner, DossierPartage, user FK) |
| `hypostasis_extractor/migrations/0020_*.py` | Migration PHASE-25 (user FK commentaire) |
| `core/admin.py` | Adapte pour user FK |
| `front/views_auth.py` | **Nouveau** — AuthViewSet (login/register/logout) |
| `front/views.py` | +_exiger_authentification(), protection ~28 actions POST, request.user dans create, _render_arbre filtre owner |
| `front/serializers.py` | +LoginSerializer, +RegisterSerializer, +DossierPartageSerializer, -prenom sur 3 serializers |
| `front/urls.py` | Enregistrer AuthViewSet |
| `front/templates/front/login.html` | **Nouveau** — page de connexion |
| `front/templates/front/register.html` | **Nouveau** — page d'inscription |
| `front/templates/front/base.html` | Menu utilisateur dans navbar |
| `front/templates/front/includes/fil_discussion.html` | Supprimer prenom, user FK, layout SMS server-side |
| `front/templates/front/includes/vue_commentaires.html` | Idem |
| `front/templates/front/includes/vue_questionnaire.html` | Supprimer prenom, gater formulaires |
| `front/templates/front/includes/drawer_vue_liste.html` | Affichage user.username |
| `front/templates/front/includes/arbre_dossiers.html` | Bouton partager |
| `front/templates/front/includes/partage_dossier_form.html` | **Nouveau** — formulaire partage |
| `front/management/commands/charger_fixtures_demo.py` | Creer users demo, assigner ownership |
| `front/tests/test_phases.py` | +19 tests unitaires PHASE-25, adaptation tests existants |
| `front/tests/e2e/base.py` | Helpers creer_utilisateur_demo, se_connecter |
| `front/tests/e2e/test_13_auth.py` | **Nouveau** — 10 tests E2E auth |
| `front/tests/e2e/__init__.py` | Import test_13 |
| `hypostasia/settings.py` | LOGIN_URL, LOGIN_REDIRECT_URL, LOGOUT_REDIRECT_URL |

### Audit stack-ccc

Audit complet de conformite au skill stack-ccc realise. 10 non-conformites detectees et corrigees :
- LOCALISATION ajoutee dans toutes les docstrings (views, serializers, helpers)
- Imports deplaces en haut de fichier (plus d'import interne dans les methodes)
- `role="alert"` + `aria-live="assertive"` sur les zones d'erreurs (login, register)
- `aria-label` sur les formulaires d'authentification et le dropdown menu
- `data-testid` sur tous les elements interactifs du partage (input, boutons, lignes)
- `aria-hidden="true"` sur les SVG decoratifs du partage

### Tests — 712 tests verts (614 unitaires + 98 E2E)

| Suite | Nombre | Statut |
|---|---|---|
| Tests unitaires PHASE-25 | 19 | OK |
| Tests unitaires existants (adaptes) | 595 | OK |
| Tests E2E PHASE-25 (auth) | 10 | OK |
| Tests E2E existants (adaptes) | 88 | OK |

---

## 2026-03-15 — PHASE-24 : Providers IA unifies

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

---

## 2026-03-11 — Corrections post-audit phases 1-6

- Renommage du skill `django-htmx-readable` → `stack-ccc` (CLAUDE.md + dossier `skills/`)
  / Renamed skill `django-htmx-readable` → `stack-ccc` (CLAUDE.md + `skills/` directory)
- Ajout attributs `aria-*` et `data-testid` dans les templates
  / Added `aria-*` and `data-testid` attributes in templates
- Mise a jour INDEX.md (phases 01-06 marquees completees)
  / Updated INDEX.md (phases 01-06 marked as completed)
- Creation de ce CHANGELOG
  / Created this CHANGELOG

**Fichiers modifies / Modified files:**
- `CLAUDE.md`
- `PLAN/PHASES/INDEX.md`
- `front/templates/front/base.html`
- `front/templates/front/includes/arbre_dossiers.html`
- `front/templates/front/includes/panneau_analyse.html`
- `front/templates/front/includes/extraction_results.html`
- `front/templates/front/includes/extraction_manuelle_form.html`
- `front/templates/front/includes/lecture_principale.html`
- `skills/django-htmx-readable/` → `skills/stack-ccc/`
- `CHANGELOG.md` (nouveau / new)

**Migration** : non / no

---

## 2026-03-11 — PHASE-06 : Modeles de donnees (statut_debat + masquee)

- Ajout des champs `statut_debat` et `masquee` sur `ExtractedEntity`
  / Added `statut_debat` and `masquee` fields on `ExtractedEntity`

**Fichiers modifies / Modified files:**
- `hypostasis_extractor/models.py`
- `hypostasis_extractor/migrations/0018_extractedentity_masquee_extractedentity_statut_debat.py`

**Migration** : oui / yes

---

## 2026-03-11 — PHASE-05 : Extension navigateur robustesse

- Amelioration de la robustesse de l'extension navigateur (gestion d'erreurs, retry)
  / Improved browser extension robustness (error handling, retry)

**Fichiers modifies / Modified files:**
- `core/views.py`

**Migration** : non / no

---

## 2026-03-11 — PHASE-04 : CRUD manquants

- Ajout des operations CRUD manquantes (renommer/supprimer dossiers, supprimer pages, deplacer pages)
  / Added missing CRUD operations (rename/delete folders, delete pages, move pages)

**Fichiers modifies / Modified files:**
- `front/views.py`
- `front/templates/front/includes/arbre_dossiers.html`
- `front/static/front/js/hypostasia.js`

**Migration** : non / no

---

## 2026-03-10 — PHASE-03 : Nettoyage code extraction

- Nettoyage et refactorisation du code d'extraction
  / Cleanup and refactoring of extraction code

**Migration** : non / no

---

## 2026-03-11 — PHASE-02 : Assets locaux (polices, CDN, collectstatic)

- Localisation des assets : Tailwind CSS, HTMX, SweetAlert2 en fichiers statiques
  / Localized assets: Tailwind CSS, HTMX, SweetAlert2 as static files
- Ajout des polices Lora (via Google Fonts, sera localise plus tard)
  / Added Lora fonts (via Google Fonts, to be localized later)

**Fichiers modifies / Modified files:**
- `front/templates/front/base.html`
- `front/static/front/css/tailwind.css`
- `front/static/front/css/hypostasia.css`
- `front/static/front/vendor/htmx-2.0.4.min.js`
- `front/static/front/vendor/sweetalert2-11.min.js`

**Migration** : non / no

---

## 2026-03-11 — PHASE-01 : Extraction CSS/JS depuis base.html

- Extraction du CSS inline vers `hypostasia.css` et du JS inline vers `hypostasia.js`
  / Extracted inline CSS to `hypostasia.css` and inline JS to `hypostasia.js`
- Mise en place de la structure `front/static/front/`
  / Set up `front/static/front/` structure

**Fichiers modifies / Modified files:**
- `front/templates/front/base.html`
- `front/static/front/css/hypostasia.css` (nouveau / new)
- `front/static/front/js/hypostasia.js` (nouveau / new)

**Migration** : non / no
