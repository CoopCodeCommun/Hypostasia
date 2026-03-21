# PHASE-25c — Visibilite 3 niveaux + groupes + arbre restructure

**Complexite** : L | **Mode** : Plan then normal | **Prerequis** : PHASE-25

---

## 1. Contexte

La PHASE-25 a pose les bases de l'authentification et du partage binaire.
Mais le modele de visibilite est incomplet : tout est lisible par les anonymes,
il n'y a pas de distinction prive/partage/public, et le partage est binaire
sans notion de groupe. Cette phase complete le systeme de permissions pour le MVP.

### Decisions architecturales

- **Granularite par dossier uniquement** — les pages heritent de la visibilite
  de leur dossier. Pas de permission par page individuelle.
- **Prive par defaut** — un dossier uploade est invisible pour tout le monde sauf l'owner.
- **3 niveaux de visibilite** : prive, partage, public.
- **Pages orphelines interdites** — a l'upload, auto-classement dans un dossier "Mes imports"
  si aucun dossier n'est selectionne.
- **Groupes d'utilisateurs** — pour les cas "classe de 30 etudiants" ou "commission de 8 personnes".

---

## 2. Modele de visibilite

```
┌─────────────┬──────────────────────────────────────────────────────┐
│ PRIVE       │ Seul l'owner voit et modifie tout.                  │
│ (defaut)    │ Personne d'autre ne sait que ca existe.             │
├─────────────┼──────────────────────────────────────────────────────┤
│ PARTAGE     │ Owner + users/groupes invites.                      │
│             │ Les invites peuvent modifier texte + extractions +  │
│             │ commenter.                                          │
│             │ Invitation par username (email en PHASE-25d).       │
├─────────────┼──────────────────────────────────────────────────────┤
│ PUBLIC      │ Tout le monde peut lire et commenter.               │
│             │ Seul l'owner (+ invites) modifie texte/extractions. │
│             │ Decouvrable via la page "Explorer".                 │
└─────────────┴──────────────────────────────────────────────────────┘
```

### Matrice de droits

| Action                       | Owner | Invite partage | User connecte (public) | Anonyme |
|------------------------------|-------|----------------|------------------------|---------|
| Voir le dossier dans l'arbre | oui   | oui            | via Explorer/Suivi     | non     |
| Lire les pages               | oui   | oui            | oui                    | non (1) |
| Lancer une analyse IA        | oui   | oui            | non                    | non     |
| Modifier texte/extractions   | oui   | oui            | non                    | non     |
| Commenter                    | oui   | oui            | oui                    | non     |
| Changer le statut de debat   | oui   | oui            | non                    | non     |
| Supprimer le dossier         | oui   | non            | non                    | non     |
| Changer la visibilite        | oui   | non            | non                    | non     |
| Gerer les partages           | oui   | non            | non                    | non     |

(1) Les anonymes sont rediriges vers `/auth/login/`. La lecture n'est plus publique.

---

## 3. Objectifs precis

### Etape 1 — Modele de visibilite sur Dossier

- [ ] Ajouter `visibilite` CharField sur `Dossier` (choices: `prive`, `partage`, `public`, default: `prive`)
- [ ] Migration : tous les dossiers existants passent en `prive`
  (les dossiers legacy avec `owner=null` recoivent l'owner admin ou restent `prive`)
- [ ] Les pages heritent de la visibilite de leur dossier — pas de champ `visibilite` sur Page

### Etape 2 — Modele GroupeUtilisateurs

- [ ] Creer le modele `GroupeUtilisateurs` :
  ```python
  class GroupeUtilisateurs(models.Model):
      nom = CharField(max_length=200)
      owner = FK(User, on_delete=CASCADE, related_name="groupes_possedes")
      membres = M2M(User, related_name="groupes_membre", blank=True)
      created_at = DateTimeField(auto_now_add=True)
  ```
- [ ] Admin Django pour gerer les groupes (MVP)
- [ ] Modifier `DossierPartage` pour accepter un user OU un groupe :
  ```python
  class DossierPartage(models.Model):
      dossier = FK(Dossier)
      utilisateur = FK(User, null=True, blank=True)
      groupe = FK(GroupeUtilisateurs, null=True, blank=True)
      created_at = DateTimeField(auto_now_add=True)
      # Contrainte : l'un des deux doit etre rempli
  ```

### Etape 3 — Suppression des pages orphelines

- [ ] A l'import (`ImportViewSet.fichier`), si aucun `dossier_id` n'est fourni,
  auto-creer ou reutiliser un dossier "Mes imports" pour l'utilisateur connecte
- [ ] Migrer les pages orphelines existantes dans un dossier "Imports" de leur owner
  (ou du super-admin si `owner=null`)
- [ ] Retirer la section "Non classees" de l'arbre

### Etape 4 — Filtrage par visibilite dans les vues

- [ ] `_render_arbre(request)` :
  - Connecte : mes dossiers (owner=moi) + dossiers partages (via DossierPartage user ou groupe)
    + dossiers publics que je suis (nouveau modele `DossierSuivi`)
  - Anonyme : rien — redirect vers `/auth/login/`
- [ ] `LectureViewSet.retrieve` : verifier que le user a le droit de lire la page
  (owner, invite, ou dossier public)
- [ ] Actions d'ecriture (analyser, editer_bloc, etc.) : verifier owner OU invite partage
- [ ] Actions de commentaire : verifier owner OU invite OU dossier public
- [ ] Refuser les anonymes sur toutes les vues (plus de lecture publique)

### Etape 5 — UI visibilite dans l'arbre

- [ ] Icone de visibilite a cote du nom du dossier :
  - Prive : cadenas (gris)
  - Partage : personnes (bleu) — deja code en PHASE-25
  - Public : globe (vert)
- [ ] Menu contextuel du dossier : nouvelle action "Visibilite" → dropdown 3 choix
  (seul l'owner voit cette action)
- [ ] Arbre restructure en 3 sections :
  ```
  📁 MES DOSSIERS
     📁 Brouillons 🔒 — 2 pages
     📁 Recherche IA 👥3 — 5 pages

  📁 PARTAGES AVEC MOI
     📁 Communs numeriques (par jonas 👥5) — 3 pages  [Quitter]
     📁 Projet CLR (par marie 👥2) — 1 page           [Quitter]

  📁 SUIVI
     📁 Debat IA et democratie (par fatima 🌐) — 7 pages  [Ne plus suivre]

  ─────────────
  🔍 Explorer les dossiers publics
  ```
- [ ] Bouton "Quitter le partage" pour les dossiers partages avec moi
- [ ] Modele `DossierSuivi` (FK User + FK Dossier) pour les dossiers publics suivis

### Etape 6 — Formulaire de partage ameliore

- [ ] Le formulaire de partage existant (PHASE-25) affiche maintenant aussi les groupes
- [ ] Ajout d'un onglet "Groupes" dans le formulaire avec la liste de mes groupes
- [ ] CRUD basique pour les groupes (creer, ajouter/retirer membres, supprimer)
  via SweetAlert ou modal HTMX

### Etape 7 — Moderation des commentaires publics

- [ ] L'owner d'un dossier peut supprimer n'importe quel commentaire sur ses pages
  (pas seulement les siens)
- [ ] Le bouton supprimer est visible pour l'owner meme sur les commentaires des autres

### Etape 8 — Tests

~20 tests unitaires :
- Visibilite prive/partage/public : filtrage arbre, acces lecture, acces ecriture
- GroupeUtilisateurs : creation, ajout/retrait membres, partage via groupe
- DossierSuivi : suivi/desuivi, apparition dans l'arbre
- Auto-classement pages orphelines
- Moderation : owner peut supprimer commentaire d'un autre

~10 tests E2E :
- Login requis pour toute action (plus de lecture anonyme)
- Dossier prive invisible pour les autres
- Dossier partage visible par les invites
- Dossier public lisible par tout user connecte
- Bouton "Quitter le partage" fonctionne
- Changement de visibilite via le menu contextuel

---

## 4. Fichiers a modifier/creer

| Fichier | Action |
|---------|--------|
| `core/models.py` | +`visibilite` sur Dossier, +`GroupeUtilisateurs`, +`DossierSuivi`, modifier `DossierPartage` |
| `core/migrations/00XX_*.py` | Migrations auto |
| `front/views.py` | `_render_arbre` restructure, filtrage par visibilite sur toutes les vues, auto-classement import |
| `front/views_auth.py` | Redirect anonyme sur toutes les pages |
| `front/serializers.py` | +`VisibiliteSerializer`, +`GroupeSerializer`, +`DossierSuiviSerializer` |
| `front/templates/front/includes/arbre_dossiers.html` | 3 sections, icones visibilite, bouton quitter |
| `front/templates/front/includes/partage_dossier_form.html` | Onglet groupes |
| `front/static/front/js/arbre_context_menu.js` | Action "Visibilite" dans le menu contextuel |
| `front/tests/test_phases.py` | ~20 tests unitaires |
| `front/tests/e2e/test_14_visibilite.py` | ~10 tests E2E |

---

## 5. Criteres de validation

- [ ] Un dossier cree est prive par defaut
- [ ] Un anonyme est redirige vers login (plus de lecture publique)
- [ ] Un dossier prive est invisible pour tout le monde sauf l'owner
- [ ] Un dossier partage est visible par les invites (users et groupes)
- [ ] Un dossier public est lisible/commentable par tout user connecte
- [ ] Seul l'owner peut modifier la visibilite
- [ ] Les pages orphelines sont auto-classees dans "Mes imports"
- [ ] L'arbre a 3 sections (mes dossiers, partages, suivi)
- [ ] Le bouton "Quitter" retire un partage
- [ ] L'owner peut supprimer les commentaires des autres sur ses dossiers
- [ ] 712+ tests passent (existants + nouveaux)
