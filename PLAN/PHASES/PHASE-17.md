# PHASE-17 — Mode focus + raccourcis clavier

**Complexite** : M | **Mode** : Normal | **Prerequis** : PHASE-09, PHASE-10

---

## 1. Contexte

Cette phase combine deux etapes complementaires du PLAN.md : le mode lecture focus (Etape 1.11) et les raccourcis clavier (Etape 1.13). Le mode focus repond au besoin de lecture longue sans bruit visuel (pastilles, surlignage). Les raccourcis clavier repondent au besoin de productivite pour les utilisateurs qui passent des heures a lire, extraire, commenter et debattre. Les deux sont lies car le raccourci `L` active le mode focus, et `Escape` en sort.

## 2. Prerequis

- **PHASE-09** : layout lecteur + marginalia (les pastilles de marge et le surlignage doivent exister pour que le mode focus puisse les masquer)
- **PHASE-10** : le raccourci E toggle le drawer vue liste qui doit exister

## 3. Objectifs precis

### Mode lecture focus (Etape 1.11)

- [ ] Bouton "Mode lecture" dans la barre d'outils (icone livre ouvert) + raccourci `L`
- [ ] En mode focus :
  - Les pastilles de marge droite sont masquees (`display: none`)
  - Le surlignage des extractions (`.hl-extraction`) est desactive (supprime le fond colore, garde le texte normal)
  - Le texte se resserre en `max-w-2xl` avec marges genereuses (padding horizontal `4rem`)
  - La barre d'outils reste visible mais discrete (opacite reduite, apparait au hover)
  - `Escape` ou second clic sur `L` -> quitte le mode focus
- [ ] L'etat du mode focus est persiste en `localStorage`

### Raccourcis clavier (Etape 1.13)

- [ ] Listener `keydown` global sur `document`, desactive quand un `<input>`, `<textarea>` ou `[contenteditable]` est focus
- [ ] Systeme de dispatch simple : `switch (event.key)` dans un seul fichier JS, pas de framework
- [ ] Raccourcis prevus :

| Raccourci | Action |
|-----------|--------|
| `?` | Afficher la palette des raccourcis (modale) |
| `L` | Toggle mode lecture focus |
| `E` | Toggle drawer vue liste (show/hide) |
| `T` | Toggle arbre de dossiers (show/hide) |
| `J` / `K` | Extraction suivante / precedente (scroll vers pastille + deplie inline) |
| `C` | Commenter l'extraction selectionnee (ouvre le champ commentaire) |
| `S` | Marquer l'extraction comme consensuelle |
| `X` | Masquer l'extraction (curation) |
| `/` | Ouvrir la recherche (placeholder "bientot" en Phase 1) |
| `Escape` | Fermer modale / quitter mode focus / deselectionner extraction |

- [ ] Etat "extraction selectionnee" : index courant dans la liste des cartes, surlignage CSS de la carte active
- [ ] `J`/`K` : scroll vers la pastille suivante/precedente dans la marge + deplie la carte inline
- [ ] `?` : modale simple (HTML statique injecte dans le DOM, toggle display)
- [ ] `Escape` : ferme la modale si ouverte, ferme le drawer si ouvert, quitte le mode focus si actif, replie la carte inline sinon
- [ ] `C` : focus le champ commentaire de l'extraction selectionnee
- [ ] `S`, `X` : declenchent les actions HTMX correspondantes sur l'extraction selectionnee
- [ ] `/` : affiche un placeholder "Recherche — bientot disponible" en Phase 1

## 4. Fichiers a modifier

- `front/static/front/js/keyboard.js` — nouveau fichier, listener keydown global + dispatch raccourcis
- `front/static/front/js/marginalia.js` — toggle mode focus (masquer pastilles, desactiver surlignage)
- `front/static/front/css/hypostasia.css` — styles `.mode-focus`, `.extraction-selectionnee`, modale raccourcis
- `front/templates/front/includes/lecture_principale.html` — bouton "Mode lecture" dans la barre d'outils
- `front/templates/front/bibliotheque.html` — inclusion de `keyboard.js`

## 5. Criteres de validation

- [ ] Clic sur "Mode lecture" : les pastilles disparaissent et le texte se centre
- [ ] `L` : toggle du mode focus
- [ ] Persistence : activer le mode focus, recharger la page, il est toujours actif
- [ ] `Escape` en mode focus : retour au mode normal avec pastilles
- [ ] `?` : la modale des raccourcis s'affiche, `Escape` la ferme
- [ ] `J`/`K` : les cartes d'extraction deroulent
- [ ] Taper dans un champ commentaire : les raccourcis sont desactives (pas de declenchement parasite)

## 5b. Verification navigateur

> Lancer `uv run python manage.py runserver` et ouvrir http://localhost:8000/

1. **Appuyer sur `L`**
   - **Attendu** : le mode focus s'active — les pastilles de marge disparaissent, le surlignage disparait, le texte est centre pour la lecture pure
2. **Recharger la page (F5)**
   - **Attendu** : le mode focus est toujours actif (persiste dans localStorage)
3. **Appuyer sur `Escape`**
   - **Attendu** : retour au mode normal avec pastilles et surlignage
4. **Appuyer sur `?`**
   - **Attendu** : une modale affiche tous les raccourcis disponibles
5. **Appuyer sur `J` puis `K`**
   - **Attendu** : navigation entre les extractions (la selection saute de carte en carte)
6. **Cliquer dans un champ texte (commentaire) puis appuyer sur `L`**
   - **Attendu** : rien ne se passe (les raccourcis sont desactives dans les champs de saisie)
7. **Appuyer sur `T` — l'arbre s'ouvre. `E` — le drawer s'ouvre. `Escape` — tout se ferme.**
   - **Attendu** : chaque raccourci toggle le panneau correspondant, Escape ferme tout

## 6. Extraits du PLAN.md

> ### Etape 1.11 — Mode lecture focus
>
> **Pourquoi** : meme avec le layout lecteur + marginalia, les pastilles de marge et le surlignage des extractions creent un bruit visuel pour la lecture longue. Le mode focus est simplifie grace au layout lecteur + marginalia : il suffit de masquer les pastilles de marge, retirer le surlignage, et resserrer le texte.
>
> **Actions** :
> - [ ] Bouton "Mode lecture" dans la barre d'outils (icone livre ouvert) + raccourci `L`
> - [ ] En mode focus : pastilles masquees, surlignage desactive, texte en `max-w-2xl` avec marges genereuses, barre d'outils discrete
> - [ ] `Escape` ou second clic sur `L` -> quitte le mode focus
> - [ ] Etat persiste en `localStorage`
>
> **Fichiers concernes** : `marginalia.js`, `hypostasia.css`, `lecture_principale.html`

> ### Etape 1.13 — Raccourcis clavier et navigation au clavier
>
> **Argumentaire** : Hypostasia est un outil de travail intellectuel — les utilisateurs vont y passer des heures a lire, extraire, commenter, debattre. Imposer le clic pour chaque action est lent et fatiguant. Les outils de reference (VS Code, Notion, Roam, Hypothesis) offrent tous une navigation clavier intensive.
>
> **Raccourcis prevus** : `?` (aide), `L` (focus), `E` (drawer), `T` (arbre), `J`/`K` (navigation extractions), `C` (commenter), `S` (consensuel), `X` (masquer), `/` (recherche), `Escape` (fermer/deselectionner).
>
> **Actions** :
> - [ ] Listener `keydown` global, desactive quand un champ de saisie est focus
> - [ ] Dispatch simple `switch (event.key)` dans un seul fichier JS
> - [ ] Etat "extraction selectionnee" avec surlignage CSS
> - [ ] Modale d'aide raccourcis (`?`)
>
> **Fichiers concernes** : nouveau `front/static/front/js/keyboard.js`, CSS pour `.extraction-selectionnee`
