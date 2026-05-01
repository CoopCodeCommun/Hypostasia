# PHASE-25d — Invitation par email + page Explorer

> ⚠️ **Page Explorer DEPRECATED 2026-05-01 — YAGNI.** Hypostasia n'est pas un reseau
> social, on ne fait pas de Decouverte. La **partie invitation par email reste
> conservee** (utile pour le partage de dossiers entre utilisateurs). La partie
> Explorer (vitrine de debats publics) est retiree. Voir `../discussions/YAGNI 2026-05-01.md`.

**Complexite** : M | **Mode** : Normal | **Prerequis** : PHASE-25c

---

## 1. Contexte

La PHASE-25c met en place la visibilite 3 niveaux et les groupes.
Cette phase ajoute les mecanismes de decouverte et d'invitation :
- Invitation par email (l'invite recoit un lien, cree son compte si necessaire, rejoint le partage)
- Page `/explorer/` pour decouvrir les dossiers publics (recherche, filtres, pagination)

Note : l'auth extension navigateur est traitee separement en PHASE-25b.

---

## 2. Objectifs precis

### Etape 1 — Invitation par email

- [ ] Modele `Invitation` :
  ```python
  class Invitation(models.Model):
      dossier = FK(Dossier)              # dossier concerne
      groupe = FK(GroupeUtilisateurs, null=True)  # ou groupe si invitation a un groupe
      email = EmailField()               # email de l'invite
      invite_par = FK(User)              # qui a invite
      token = CharField(max_length=64)   # token unique pour le lien
      acceptee = BooleanField(default=False)
      created_at = DateTimeField(auto_now_add=True)
      expires_at = DateTimeField()       # expiration (7 jours par defaut)
  ```
- [ ] Action `inviter` sur DossierViewSet :
  - Recoit un email
  - Si l'email correspond a un user existant → cree directement le DossierPartage
  - Sinon → cree une Invitation + envoie un email avec lien unique
- [ ] Vue `/invitation/{token}/` :
  - Si l'invite est deja connecte → accepte l'invitation, cree le partage, redirect vers le dossier
  - Si l'invite n'a pas de compte → redirect vers register avec le token en query param
  - Apres inscription → accepte automatiquement l'invitation
- [ ] Template email simple (texte + HTML basique)
- [ ] Configuration SMTP dans settings.py (variable d'env `EMAIL_HOST`, etc.)

### Etape 2 — Page Explorer (decouverte des dossiers publics)

- [ ] Nouvelle page `/explorer/` accessible par tout user connecte
- [ ] Liste paginee des dossiers publics (20 par page)
- [ ] Recherche par nom de dossier (champ texte, filtre HTMX en temps reel)
- [ ] Filtre par auteur (dropdown des users ayant des dossiers publics)
- [ ] Chaque dossier affiche : nom, auteur, nombre de pages, date de creation
- [ ] Bouton "Suivre" → cree un `DossierSuivi`, le dossier apparait dans l'arbre
- [ ] Bouton "Ne plus suivre" si deja suivi
- [ ] Lien dans le footer de l'arbre : "🔍 Explorer les dossiers publics"
- [ ] Design : cards ou lignes, style coherent avec le reste de l'app

### Etape 3 — Invitation a un groupe

- [ ] Le owner d'un groupe peut inviter par email (meme mecanisme que l'etape 1)
- [ ] L'invite rejoint le groupe (pas un dossier specifique)
- [ ] Tous les dossiers partages avec le groupe deviennent accessibles
- [ ] Page de gestion du groupe (liste des membres, invitations en attente)

### Etape 4 — Tests

~15 tests unitaires :
- Invitation par email : creation, acceptation, expiration, user existant vs nouveau
- Page Explorer : recherche, pagination, suivi/desuivi

~8 tests E2E :
- Flux invitation complet (invite → email → clic lien → register → partage actif)
- Page Explorer : recherche, suivi, arbre mis a jour
- Extension : configurer le token, envoyer une page, verifier l'owner

---

## 3. Fichiers a modifier/creer

| Fichier | Action |
|---------|--------|
| `core/models.py` | +`Invitation`, +`APIToken` (ou DRF Token) |
| `core/migrations/00XX_*.py` | Migrations auto |
| `front/views.py` | Action `inviter` sur DossierViewSet |
| `front/views_explorer.py` | **Nouveau** — ExplorerViewSet (liste, recherche, suivi) |
| `front/views_auth.py` | Vue `/invitation/{token}/`, lien register avec token |
| `front/urls.py` | Enregistrer ExplorerViewSet |
| `front/serializers.py` | +`InvitationSerializer`, +`ExplorerFiltreSerializer` |
| `front/templates/front/explorer.html` | **Nouveau** — page Explorer |
| `front/templates/front/includes/arbre_dossiers.html` | Lien vers Explorer dans le footer |
| `front/templates/emails/invitation.html` | **Nouveau** — template email invitation |
| `hypostasia/settings.py` | Configuration SMTP (EMAIL_HOST, etc.) |

---

## 4. Criteres de validation

- [ ] Inviter par email un user existant → partage cree immediatement
- [ ] Inviter par email un inconnu → email envoye avec lien, inscription → partage cree
- [ ] Invitation expiree → message d'erreur clair
- [ ] Page Explorer affiche les dossiers publics avec recherche et pagination
- [ ] Bouton "Suivre" ajoute le dossier dans l'arbre section "Suivi"
- [ ] Token API generable depuis le profil user
- [ ] L'extension navigateur envoie le token et les pages sont associees au bon user
- [ ] 732+ tests passent (existants + nouveaux)

---

## 5. Verification navigateur

1. **Inviter un email existant** → le user voit immediatement le dossier partage dans son arbre
2. **Inviter un email inconnu** → verifier l'email recu, cliquer le lien, s'inscrire, verifier le partage
3. **Ouvrir /explorer/** → voir les dossiers publics, rechercher, suivre un dossier
4. **Configurer le token dans l'extension** → envoyer une page → verifier l'owner dans l'admin
