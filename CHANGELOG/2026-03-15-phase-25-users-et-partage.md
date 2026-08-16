# PHASE-25 : Users et partage

**Date :** 2026-03-15
**Migration :** Non

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

