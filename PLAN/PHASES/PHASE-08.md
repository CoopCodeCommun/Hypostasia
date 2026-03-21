# PHASE-08 — Refonte layout : arbre overlay + toolbar

**Complexite** : M | **Mode** : Normal | **Prerequis** : PHASE-07

---

## 1. Contexte

Le layout 3 colonnes actuel (arbre | lecture | extractions) est un pattern d'IDE/client mail. Hypostasia est un outil de lecture augmentee — le modele mental correct est un livre annote. L'arbre de dossiers est une colonne permanente pour un usage ponctuel : on choisit un document, puis l'arbre est inutile pendant 90% de la session. Il consomme 16rem de largeur en permanence. Cette phase transforme l'arbre en overlay sur demande et ajoute une barre d'outils en haut de la zone de lecture. La zone de lecture passe en pleine largeur.

## 2. Prerequis

- **PHASE-07** — Le layout de base doit etre en place avant de le refondre.

## 3. Objectifs precis

- [ ] Transformer l'arbre de dossiers en overlay (position fixed, 20rem depuis la gauche, fond blanc, ombre portee) — la sidebar gauche a deja ete supprimee en PHASE-07
- [ ] Ajouter un backdrop assombri derriere l'arbre overlay
- [ ] Toggle de l'arbre via bouton hamburger `☰` (toujours visible en haut a gauche) ou touche `T`
- [ ] Fermeture de l'arbre au clic sur un document, sur le backdrop, ou via touche `Escape`
- [ ] Conserver le contenu HTMX existant de l'arbre (drag-and-drop, CRUD dossiers, boutons Nouveau dossier / Importer)
- [ ] Verifier que la zone de lecture reste en pleine largeur (`max-w-4xl` centre, marges confortables `mx-auto`) — deja mis en place en PHASE-07
- [ ] Ajouter une barre d'outils en haut : `[☰] Titre du document [Dashboard ▾] [Analyser] [Vue liste E] [Focus L] [⚙]`
- [ ] Le bouton "Dashboard" dans la barre d'outils ouvre un dropdown (contenu prevu en PHASE-14)
- [ ] Creer le fichier JS `arbre_overlay.js` pour gerer le toggle de l'arbre (evenements clavier, bouton, backdrop)

## 4. Fichiers a modifier

- `front/templates/front/base.html` — ajout de la barre d'outils complete (le layout mono-colonne est deja en place depuis PHASE-07)
- `front/templates/front/bibliotheque.html` — arbre en overlay au lieu de colonne permanente
- `front/templates/front/includes/arbre_dossiers.html` — adaptation du template existant pour le mode overlay
- `front/static/front/js/arbre_overlay.js` — **(nouveau)** gestion toggle arbre (evenements T, Escape, clic backdrop)
- `front/static/front/css/hypostasia.css` — styles overlay arbre, backdrop, barre d'outils complete

## 5. Criteres de validation

- [ ] L'arbre n'apparait plus en colonne permanente — la zone de lecture occupe toute la largeur
- [ ] Touche `T` ouvre/ferme l'arbre en overlay depuis la gauche
- [ ] Bouton `☰` en haut a gauche ouvre l'arbre
- [ ] Clic sur un document dans l'arbre charge la page et ferme l'arbre
- [ ] Clic sur le backdrop assombri ferme l'arbre
- [ ] Touche `Escape` ferme l'arbre
- [ ] La barre d'outils est visible en haut avec le titre du document et les boutons d'action
- [ ] Le drag-and-drop et le CRUD dossiers fonctionnent toujours dans l'arbre overlay
- [ ] L'interface est utilisable sur des ecrans de 768px a 2560px sans media query complexe

## 5b. Verification navigateur

> Lancer `uv run python manage.py runserver` et ouvrir http://localhost:8000/

1. **Cliquer sur le bouton hamburger [☰] en haut a gauche** : ouvrir l'arbre de dossiers
   - **Attendu** : l'arbre s'ouvre en overlay a gauche avec fond assombri derriere, l'arbre est navigable
2. **Appuyer sur la touche `T`** : tester le raccourci clavier
   - **Attendu** : l'arbre s'ouvre/se ferme (toggle)
3. **Cliquer sur un document dans l'arbre** : selectionner un document
   - **Attendu** : le document se charge dans la zone de lecture et l'arbre se ferme
4. **Cliquer en dehors de l'overlay** (sur le fond assombri) : tester la fermeture
   - **Attendu** : l'arbre se ferme
5. **Verifier la toolbar** : inspecter la barre d'outils en haut
   - **Attendu** : titre du document, boutons Dashboard, Analyser, E (drawer), L (focus)

## 6. Extraits du PLAN.md

> **L'arbre de dossiers — overlay sur demande** :
>
> ```
> ┌─────────────────────┬────────────────────────────────────┐
> │ ☰ Bibliotheque  [✕] │                                    │
> │                     │                                    │
> │ 📁 Projet IA       │  (le texte reste visible           │
> │   📄 Charte v1     │   en dessous, assombri)            │
> │   📄 Charte v2     │                                    │
> │   📄 CR reunion    │                                    │
> │ 📁 Juridique       │                                    │
> │   📄 Contrat X     │                                    │
> │ 📁 Recherche       │                                    │
> │                     │                                    │
> │ [+ Nouveau dossier] │                                    │
> │ [+ Importer]        │                                    │
> └─────────────────────┴────────────────────────────────────┘
> ```
>
> L'arbre s'ouvre en overlay (position fixed, 16-20rem depuis la gauche, fond blanc, ombre).
> Le reste de la page est assombri (backdrop). Clic sur un document → charge la page, ferme l'arbre.
> Raccourci `T` pour toggle. Bouton hamburger `☰` toujours visible en haut a gauche.
>
> **Actions** :
> - [ ] Supprimer la sidebar gauche permanente. L'arbre devient un overlay (position fixed, toggle via ☰ ou touche T)
> - [ ] Zone de lecture en pleine largeur (`max-w-4xl` centre, marges confortables)
> - [ ] Arbre overlay : position fixed gauche, 20rem, backdrop assombri
>   - Toggle via ☰ ou touche T
>   - Meme contenu que l'arbre actuel (HTMX, drag-and-drop, CRUD dossiers)
>   - Fermeture au clic sur un document ou sur le backdrop
> - [ ] Barre d'outils en haut : `[☰] Titre du document [Dashboard ▾] [Analyser] [Vue liste E] [Focus L] [⚙]`
> - [ ] Le dashboard de consensus (Etape 1.4) s'affiche en dropdown depuis le bouton "Dashboard" dans la barre d'outils, ou en bandeau fixe en haut de la zone de lecture (au choix lors de l'implementation)
>
> **Fichiers concernes** :
> - Refactoring majeur de `front/templates/front/base.html` (suppression du layout flex 3 colonnes)
> - Refactoring de `front/templates/front/bibliotheque.html` (arbre en overlay)
> - `front/static/front/js/arbre_overlay.js` (toggle arbre)
> - CSS : layout mono-colonne centre, styles des pastilles de marge, animations inline, drawer overlay
