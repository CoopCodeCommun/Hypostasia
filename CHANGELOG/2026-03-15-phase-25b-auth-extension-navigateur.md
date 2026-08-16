# PHASE-25b : Auth extension navigateur

**Date :** 2026-03-15
**Migration :** Non

**Quoi / What:** Authentification par token API pour l'extension navigateur Chrome.
L'extension envoie le token dans les headers HTTP. POST /api/pages/ exige un token valide (401 sinon).
Page `/auth/token/` pour generer/regenerer le token. Apres recolte, boutons dossiers pour classer
la page. Dossier "A ranger" auto-cree par defaut. Dedup filtree par owner + partages.
Fix URL hardcodee dans sidebar.js.

**Pourquoi / Why:** L'extension fonctionnait sans authentification — impossible de tracer
qui envoie quoi, ni de classer les pages par utilisateur.

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `hypostasia/settings.py` | +rest_framework.authtoken dans INSTALLED_APPS, +CORS_ALLOW_HEADERS |
| `core/views.py` | TokenAuthentication, owner sur create, endpoints me/mes_dossiers/classer_depuis_extension, dedup filtree owner+partages |
| `front/views_auth.py` | +action mon_token (GET/POST) — generation et regeneration de token |
| `front/templates/front/mon_token.html` | **Nouveau** — page standalone token avec bouton copier/regenerer |
| `front/templates/front/base.html` | Lien "Mon token API" dans dropdown menu utilisateur |
| `extension/popup.js` | Token dans headers, feedback auth, boutons dossiers post-recolte |
| `extension/popup.html` | Zones #authStatus et #dossiersChoix |
| `extension/sidebar.js` | Fix URL hardcodee → lecture serverUrl depuis storage + token dans headers |
| `extension/options.html` | Renommer "Cle API" en "Token d'authentification" + help-text |
| `front/tests/test_phases.py` | +12 tests unitaires PHASE-25b |
| `front/tests/e2e/test_15_token.py` | **Nouveau** — 3 tests E2E page token |

