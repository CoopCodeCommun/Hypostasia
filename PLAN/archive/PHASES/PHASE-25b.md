# PHASE-25b — Auth extension navigateur

**Complexite** : M | **Mode** : Normal | **Prerequis** : PHASE-25

---

## 1. Contexte

L'extension navigateur Chrome envoie les pages recoltees vers l'API Django (`core/views.py`)
sans aucune authentification. Les endpoints `PageViewSet` et `SidebarViewSet` sont en `AllowAny`
avec `authentication_classes = []`. Le champ "Cle API" dans les options de l'extension
(`extension/options.html` ligne 89) existe mais n'est pas utilise — le `help-text` dit
"Non utilise actuellement".

Cette phase connecte l'extension au systeme d'auth de la PHASE-25 :
- L'extension envoie un token dans les headers de chaque requete
- Le serveur associe les pages creees a l'utilisateur du token
- Les pages heritent du dossier choisi ou d'un dossier "Mes imports" par defaut

### Etat actuel du code

| Fichier | Etat |
|---------|------|
| `core/views.py:78-79` | `authentication_classes = []`, `permission_classes = [AllowAny]` sur PageViewSet |
| `core/views.py:198-199` | Idem sur SidebarViewSet |
| `core/views.py:104` | `PageViewSet.create()` cree les Pages sans `owner` |
| `extension/options.html:89` | Champ "Cle API" present mais marque "Non utilise" |
| `extension/options.js:15` | Stocke `apiKey` dans `chrome.storage.sync` |
| `extension/popup.js` | N'envoie pas le token dans les headers |

---

## 2. Objectifs precis

### Etape 1 — Token API cote serveur

- [ ] Utiliser `rest_framework.authtoken` (module DRF existant) :
  - Ajouter `'rest_framework.authtoken'` dans `INSTALLED_APPS`
  - `uv run python manage.py migrate` (cree la table `authtoken_token`)
- [ ] Ajouter une action sur `AuthViewSet` pour generer/afficher son token :
  ```python
  @action(detail=False, methods=["GET", "POST"], url_path="token")
  def mon_token(self, request):
      # GET : affiche le token (ou "pas encore de token")
      # POST : genere un nouveau token (revoque l'ancien si existant)
  ```
- [ ] Template `front/templates/front/mon_token.html` :
  - Affiche le token en lecture seule (champ texte + bouton copier)
  - Bouton "Regenerer" (revoque l'ancien, en cree un nouveau)
  - Instructions : "Copiez ce token dans les options de l'extension Hypostasia"
- [ ] Lien vers `/auth/token/` dans le dropdown menu utilisateur (apres "Deconnexion")

### Etape 2 — Auth sur les endpoints API core

- [ ] Modifier `PageViewSet` dans `core/views.py` :
  ```python
  from rest_framework.authentication import TokenAuthentication, SessionAuthentication

  class PageViewSet(viewsets.ViewSet):
      authentication_classes = [TokenAuthentication, SessionAuthentication]
      permission_classes = [permissions.IsAuthenticatedOrReadOnly]
  ```
  - `list()` reste accessible sans auth (l'extension verifie si une page existe)
  - `create()` requiert un token valide → `request.user` est l'utilisateur du token
- [ ] Modifier `SidebarViewSet` dans `core/views.py` :
  ```python
  class SidebarViewSet(viewsets.ViewSet):
      authentication_classes = [TokenAuthentication, SessionAuthentication]
      permission_classes = [permissions.AllowAny]  # la sidebar est en lecture
  ```
- [ ] Dans `PageViewSet.create()` : ajouter `owner=request.user` sur la Page creee
  (si l'user est authentifie — sinon refuser avec 401)

### Etape 3 — Dossier par defaut pour les pages de l'extension

- [ ] Quand l'extension cree une page, la classer automatiquement :
  - Si un `dossier_id` est envoye dans le payload → utiliser ce dossier
    (verifier que l'user en est owner ou invite)
  - Sinon → auto-creer ou reutiliser un dossier "Pages web" pour cet utilisateur
    (meme pattern que "Mes imports" pour l'upload de fichiers)
- [ ] Ajouter le champ optionnel `dossier_id` dans `PageCreateSerializer` de `core/serializers.py`

### Etape 4 — Extension : envoyer le token

- [ ] `extension/popup.js` : lire le token depuis `chrome.storage.sync`
  et l'ajouter dans les headers de toutes les requetes fetch :
  ```javascript
  var headersRequete = {
      'Content-Type': 'application/json',
  };
  if (config.apiKey) {
      headersRequete['Authorization'] = 'Token ' + config.apiKey;
  }
  ```
- [ ] `extension/sidebar.js` : idem pour les requetes de la sidebar
- [ ] `extension/options.html` : renommer "Cle API (Optionnel)" en "Token d'authentification"
  et mettre a jour le `help-text` :
  "Generez votre token dans Hypostasia > Menu utilisateur > Mon token API"
- [ ] `extension/background.js` : si le token est present, l'envoyer aussi
  dans les requetes background (si applicable)

### Etape 5 — Feedback dans l'extension

- [ ] Quand le token est valide : afficher "Connecte en tant que [username]" dans la popup
  (petit texte sous l'indicateur serveur)
- [ ] Quand le token est invalide ou absent : afficher "Non connecte — les pages ne seront pas sauvegardees"
  en orange
- [ ] Ajouter un appel de verification au chargement de la popup :
  `GET /api/pages/?limit=0` avec le token → si 200, afficher le username
  (extraire depuis la reponse ou faire un endpoint `/api/me/` dedie)

### Etape 6 — Endpoint `/api/me/` (optionnel mais recommande)

- [ ] Ajouter une action simple sur PageViewSet (ou un viewset dedie) :
  ```python
  @action(detail=False, methods=["GET"], url_path="me")
  def me(self, request):
      if not request.user.is_authenticated:
          return Response({"authenticated": False}, status=401)
      return Response({
          "authenticated": True,
          "username": request.user.username,
          "email": request.user.email,
      })
  ```
- [ ] L'extension appelle `/api/pages/me/` pour verifier la connexion et afficher le username

### Etape 7 — Tests

~10 tests unitaires :
- Token generation : creation, regeneration, revocation
- `PageViewSet.create` avec token valide → owner correct
- `PageViewSet.create` sans token → 401
- `PageViewSet.list` sans token → 200 (lecture autorisee)
- `SidebarViewSet.list` sans token → 200
- Dossier par defaut "Pages web" auto-cree
- `/api/me/` avec token valide/invalide

~3 tests E2E :
- Page `/auth/token/` affiche le token et le bouton copier
- Regeneration du token via le bouton
- Lien dans le menu utilisateur

---

## 3. Fichiers a modifier/creer

| Fichier | Action |
|---------|--------|
| `hypostasia/settings.py` | Ajouter `rest_framework.authtoken` dans INSTALLED_APPS, config DRF DEFAULT_AUTHENTICATION_CLASSES |
| `core/views.py` | `authentication_classes` + `owner=request.user` sur PageViewSet.create, endpoint `/api/me/` |
| `core/serializers.py` | Ajouter `dossier_id` optionnel dans PageCreateSerializer |
| `front/views_auth.py` | Action `mon_token` (GET/POST) |
| `front/templates/front/mon_token.html` | **Nouveau** — page affichage/regeneration du token |
| `front/templates/front/base.html` | Lien "Mon token API" dans le dropdown menu user |
| `extension/popup.js` | Envoyer le token dans les headers, afficher le statut connexion |
| `extension/sidebar.js` | Envoyer le token dans les headers |
| `extension/options.html` | Renommer le champ, mettre a jour le help-text |
| `extension/options.js` | Pas de changement majeur (stocke deja apiKey) |
| `front/tests/test_phases.py` | ~10 tests unitaires PHASE-25b |
| `front/tests/e2e/test_15_token.py` | **Nouveau** — ~3 tests E2E token |

---

## 4. Criteres de validation

- [ ] Un utilisateur connecte peut generer son token API depuis `/auth/token/`
- [ ] Le token est affichable et copiable
- [ ] Regenerer le token revoque l'ancien
- [ ] `POST /api/pages/` avec `Authorization: Token xxx` cree une page avec `owner=user_du_token`
- [ ] `POST /api/pages/` sans token retourne 401
- [ ] `GET /api/pages/` sans token retourne 200 (lecture publique pour l'extension)
- [ ] Les pages creees par l'extension sont classees dans "Pages web" (dossier auto-cree)
- [ ] L'extension affiche "Connecte en tant que [username]" quand le token est valide
- [ ] L'extension affiche un warning quand le token est absent ou invalide
- [ ] `uv run python manage.py check` passe
- [ ] Les migrations s'appliquent sans erreur
- [ ] 712+ tests passent (existants + nouveaux)

---

## 5. Verification navigateur

1. **Se connecter sur Hypostasia** → menu utilisateur → "Mon token API"
   - **Attendu** : page avec le token affiche, bouton copier, bouton regenerer
2. **Copier le token → le coller dans les options de l'extension**
   - **Attendu** : le champ s'appelle "Token d'authentification" avec les instructions
3. **Ouvrir une page web → cliquer "Recolter" dans la popup de l'extension**
   - **Attendu** : la page est creee avec `owner` = l'utilisateur du token,
     classee dans le dossier "Pages web"
4. **Retirer le token des options de l'extension → recolter**
   - **Attendu** : message d'erreur dans la popup ("Non connecte")
5. **Verifier la popup de l'extension au chargement**
   - **Attendu** : "Connecte en tant que jonas" (si token valide)
     ou "Non connecte" (si token absent)

---

## 6. Notes d'architecture

### Pourquoi TokenAuthentication et pas SessionAuthentication seule ?

L'extension navigateur n'a pas acces aux cookies de session Django (domaine different,
contexte extension Chrome). Le token est le mecanisme standard pour les clients API externes.
On garde `SessionAuthentication` en plus pour que l'API reste utilisable depuis le navigateur
(utile pour le debug dans la DRF browsable API).

### Pourquoi pas JWT ?

DRF TokenAuthentication est plus simple (un token par user, stocke en base).
JWT ajoute de la complexite (expiration, refresh, blacklist) sans benefice pour un MVP
ou chaque user a un seul client (l'extension). On pourra migrer vers JWT plus tard
si necessaire (multi-device, expiration automatique).

### Backward compatibility

Les endpoints `list()` restent accessibles sans auth (l'extension verifie si une page existe
avant de l'envoyer). Seul `create()` requiert un token. Les tests E2E existants qui utilisent
les endpoints API core ne casseront pas car ils n'appellent pas `create()` directement.
