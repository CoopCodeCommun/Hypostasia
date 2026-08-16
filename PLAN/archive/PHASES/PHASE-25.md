# PHASE-25 — Users et partage

**Complexite** : L | **Mode** : Plan then normal | **Prerequis** : PHASE-22

---

## 1. Contexte

Hypostasia fonctionne actuellement en mode mono-utilisateur (prenom libre dans les commentaires). Pour permettre le partage de dossiers, la collaboration sur les debats, et la tracabilite des contributions, il faut un vrai systeme d'authentification Django avec propriete des ressources et mecanisme de partage. L'extension navigateur doit aussi s'authentifier.

## 2. Prerequis

PHASE-22 (PostgreSQL + Redis) — les ecritures concurrentes multi-utilisateurs necessitent PostgreSQL.

## 3. Objectifs precis

### Etape 2.1 — Authentification Django

- [ ] Activer `django.contrib.auth` (deja installe) avec login/logout/register
- [ ] Creer un modele `UserProfile` si necessaire (preferences, avatar)
- [ ] Ajouter un middleware d'authentification pour le front (pages protegees)
- [ ] L'API core (extension) reste `AllowAny` pour le MVP, mais prevoir token auth

### Etape 2.2 — Propriete et partage de dossiers

- [ ] Ajouter `owner` (FK User) sur `Dossier` et `Page`
- [ ] Creer un modele `DossierPartage` : user + dossier + permission (lecture/ecriture)
- [ ] Filtrer l'arbre par user connecte (mes dossiers + dossiers partages avec moi)
- [ ] Remplacer `prenom` par `request.user` dans CommentaireExtraction et Question/Reponse

### Etape 2.3 — Auth dans l'extension navigateur

- [ ] Ajouter un champ token/session dans les options de l'extension
- [ ] Envoyer le token dans les headers de chaque requete API
- [ ] Associer automatiquement les pages creees au user connecte

## 4. Fichiers a modifier

- `hypostasia/settings.py` — configuration auth, middleware
- `core/models.py` — `UserProfile`, `owner` sur Dossier/Page, `DossierPartage`, migrations
- `front/views.py` — ArbreViewSet (filtrage par user), DossierViewSet (ownership), remplacement prenom par request.user
- `front/auth_views.py` — nouveau fichier ou `AuthViewSet` pour login/logout/register
- `front/templates/front/` — pages login/register, mise a jour header avec user info
- `extension/popup.js` — champ token/session
- `extension/options.js` — configuration auth
- `core/views.py` — prevoir token auth pour l'API extension
- `front/serializers.py` — serializers pour auth et partage

## 5. Criteres de validation

- [ ] Un utilisateur peut s'inscrire, se connecter, se deconnecter
- [ ] Les pages du front sont protegees (redirect vers login si non connecte)
- [ ] Chaque dossier et page a un `owner`
- [ ] Un utilisateur ne voit que ses dossiers + ceux partages avec lui dans l'arbre
- [ ] Le partage de dossier fonctionne (lecture et ecriture)
- [ ] Les commentaires affichent le vrai user au lieu d'un prenom libre
- [ ] L'extension navigateur envoie le token et les pages sont associees au bon user
- [ ] `uv run python manage.py check` passe
- [ ] Les migrations s'appliquent sans erreur

## 5b. Verification navigateur

> Lancer `uv run python manage.py runserver` et ouvrir http://localhost:8000/

1. **Ouvrir http://localhost:8000/ sans etre connecte**
   - **Attendu** : redirect vers la page de login
2. **Se connecter**
   - **Attendu** : l'arbre ne montre que ses propres dossiers
3. **Creer un 2e utilisateur (admin ou inscription) — se connecter avec le 2e compte**
   - **Attendu** : arbre vide
4. **Avec le 1er utilisateur : partager un dossier avec le 2e**
   - **Attendu** : le 2e voit maintenant le dossier partage
5. **Ajouter un commentaire avec le 2e utilisateur**
   - **Attendu** : le nom affiche est le vrai username (pas un champ texte libre)
6. **Ouvrir l'extension navigateur**
   - **Attendu** : elle demande les credentials ou un token — apres auth, les pages recoltees sont associees au bon user

## 6. Extraits du PLAN.md

> ## 3. Phase 2 — Gestion utilisateurs et partage
>
> Objectif : passer d'un mode mono-utilisateur (prenom) a un vrai systeme d'auth avec partage.
>
> ### Etape 2.1 — Authentification Django
>
> **Actions** :
> - [ ] Activer `django.contrib.auth` (deja installe) avec login/logout/register
> - [ ] Creer un modele `UserProfile` si necessaire (preferences, avatar)
> - [ ] Ajouter un middleware d'authentification pour le front (pages protegees)
> - [ ] L'API core (extension) reste `AllowAny` pour le MVP, mais prevoir token auth
>
> **Fichiers concernes** : `hypostasia/settings.py`, nouveau fichier `front/auth_views.py` ou actions sur un `AuthViewSet`
>
> ### Etape 2.2 — Propriete et partage de dossiers
>
> **Actions** :
> - [ ] Ajouter `owner` (FK User) sur `Dossier` et `Page`
> - [ ] Modele `DossierPartage` : user + dossier + permission (lecture/ecriture)
> - [ ] Filtrer l'arbre par user connecte (mes dossiers + dossiers partages avec moi)
> - [ ] Remplacer `prenom` par `request.user` dans CommentaireExtraction et Question/Reponse
>
> **Fichiers concernes** : `core/models.py`, `front/views.py` (ArbreViewSet, DossierViewSet), migrations
>
> ### Etape 2.3 — Auth dans l'extension navigateur
>
> **Actions** :
> - [ ] Ajouter un champ token/session dans les options de l'extension
> - [ ] Envoyer le token dans les headers de chaque requete API
> - [ ] Associer automatiquement les pages creees au user connecte
>
> **Fichiers concernes** : `extension/popup.js`, `extension/options.js`, `core/views.py`
>
> ### Tests E2E Phase 2
>
> - [ ] Login/logout/register
> - [ ] Arbre filtre par user (mes dossiers + partages)
> - [ ] Commentaire avec user authentifie (plus de prenom libre)
> - [ ] Filtre contributeur : selectionner un user, verifier que seules ses extractions commentees sont visibles
> - [ ] Filtre contributeur : verifier que les commentaires des autres sont en opacite reduite (pas masques)
> - [ ] Filtre contributeur + heat map : verifier que la temperature reflette uniquement les commentaires du contributeur selectionne
