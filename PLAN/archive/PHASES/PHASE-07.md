# PHASE-07 — Refonte layout : suppression 3 colonnes, lecteur avec marginalia

**Complexite** : L | **Mode** : Plan puis Normal | **Prerequis** : PHASE-01, PHASE-02

---

## 1. Contexte

Le layout 3 colonnes (arbre | lecture | extractions) est un pattern d'IDE/client mail. Hypostasia est un outil de lecture augmentee, pas un IDE. Le modele mental correct est un livre annote : le texte au centre, les annotations en marge. Le layout actuel pose 3 problemes concrets :

1. **L'arbre est permanent pour un usage ponctuel** — 16rem de largeur consommee pour un usage a 10% du temps
2. **Split-attention** — la carte d'extraction est a droite, le passage reference est au centre
3. **Competition spatiale** — sur ecran < 27", les 3 colonnes se disputent l'espace

Le layout cible : texte pleine largeur, extractions inline sous le passage, arbre en overlay sur demande.

## 2. Prerequis

- **PHASE-01** : CSS/JS extraits dans des fichiers statiques (on modifie ces fichiers, pas du inline)
- **PHASE-02** : assets locaux en place (pas de CDN qui casse pendant le refactoring)

## 3. Objectifs precis

- [ ] Supprimer le layout flex 3 colonnes (sidebar-left `w-64`, main `flex-1`, sidebar-right `w-[32rem]`)
- [ ] Mettre en place un layout mono-colonne centre (`max-width` ~700px, marges auto)
- [ ] Prevoir une zone de marge droite (~3-4rem) reservee pour les futures pastilles (PHASE-09) — la zone est presente dans le CSS mais vide pour l'instant
- [ ] Ajouter une toolbar minimale en haut avec : titre du document + placeholder pour boutons futurs (les boutons fonctionnels viendront dans les phases suivantes)
- [ ] L'arbre reste accessible via son URL directe (`/arbre/`) — le mode overlay viendra en PHASE-08

## 3b. Hors scope

> Ces elements sont traites dans les phases suivantes. Ne pas les implementer ici.

- Arbre overlay (position fixed, toggle hamburger/touche T) → **PHASE-08**
- Pastilles de marge et cartes inline → **PHASE-09**
- Drawer vue liste → **PHASE-10**
- Raccourcis clavier `T`, `E` → **PHASE-08**, **PHASE-10**

## 4. Fichiers a modifier

- `front/templates/front/base.html` — suppression du layout flex 3 colonnes, mise en place du layout mono-colonne
- `front/templates/front/bibliotheque.html` — adaptation pour le layout mono-colonne (l'arbre reste en place, pas encore overlay)
- `front/templates/front/includes/lecture_principale.html` — pleine largeur centree + zone de marge droite vide (reservee PHASE-09)
- `front/static/front/css/hypostasia.css` — layout mono-colonne centre, toolbar minimale en haut

## 5. Criteres de validation

- [ ] Le layout est mono-colonne avec texte centre (~700px max-width, marges auto)
- [ ] Les sidebars permanentes (gauche et droite) sont supprimees
- [ ] Une zone de marge droite (~3-4rem) est presente dans le CSS mais vide (reservee pour PHASE-09)
- [ ] Une toolbar minimale est visible en haut avec le titre du document
- [ ] L'arbre reste accessible via son URL directe (`/arbre/`)
- [ ] L'app est responsive sans media queries complexes
- [ ] `uv run python manage.py check` passe sans erreur

## 5b. Verification navigateur

> Lancer `uv run python manage.py runserver` et ouvrir http://localhost:8000/

1. **Ouvrir http://localhost:8000/** : observer le layout general
   - **Attendu** : le texte occupe toute la largeur centrale (pas de colonnes laterales permanentes). Le texte est centre avec une largeur max (~700px), marges automatiques
2. **Redimensionner la fenetre de 1920px a 768px** : utiliser les DevTools ou redimensionner manuellement
   - **Attendu** : le texte reste lisible, pas de barre de scroll horizontale
3. **Verifier l'absence des panneaux permanents** : observer la page
   - **Attendu** : il n'y a plus de panneau gauche (arbre) ni de panneau droit (extractions) visibles en permanence
4. **Verifier la toolbar minimale en haut** : inspecter la toolbar
   - **Attendu** : la barre contient le titre du document et un espace placeholder pour les futurs boutons (pas encore de hamburger fonctionnel ni de raccourcis clavier)
5. **Verifier la marge droite reservee** : inspecter le CSS de la zone de lecture
   - **Attendu** : une marge droite de ~3-4rem est presente mais vide (pas de pastilles, celles-ci viendront en PHASE-09)

## 6. Extraits du PLAN.md

> ### Etape 1.3 bis — Refonte layout : du 3 colonnes au lecteur avec marginalia
>
> **Argumentaire** : Le layout 3 colonnes (arbre | lecture | extractions) est un pattern d'IDE/client mail. Il fonctionne mais ne correspond pas au modele mental d'Hypostasia. Hypostasia est un **outil de lecture augmentee**, pas un IDE. Le modele mental correct est un **livre annote** : le texte est au centre de l'attention, les annotations sont en marge, contextuelles.
>
> **Principe : lecteur avec marginalia**
>
> ```
> +----------------------------------------------------------+
> | [hamburger]  Titre du document          [Analyser] [eng] |
> +---------------------------------------------------+------+
> |                                                    | marge|
> |   L'intelligence artificielle souleve des          |      |
> |   questions fondamentales sur l'avenir du           |  *   | <- pastille DISCUTE
> |   travail creatif.                                 |      |
> |                                                    |      |
> |   +---------------------------------------------+  |      |
> |   | CONJECTURE            [replier]              |  |      |
> |   | L'IA va transformer les metiers creatifs     |  |      |
> |   | en metiers de supervision.                   |  |      |
> |   +---------------------------------------------+  |      |
> |       ^ carte depliee inline sous le passage       |      |
> +---------------------------------------------------+------+
> ```
>
> **Les 3 modes d'affichage des extractions** :
> - **Marginalia** (defaut) : pastilles colorees dans la marge droite. Tap/clic sur pastille → deplie la carte inline
> - **Inline deplie** : la carte s'ouvre sous le passage, pousse le texte. Bouton replier pour fermer
> - **Drawer vue liste** : overlay a droite (32rem) montrant TOUTES les cartes en liste scrollable. Toggle touche E ou bouton
>
> **Actions** :
> - [ ] Supprimer la sidebar gauche permanente → overlay (toggle hamburger ou touche T)
> - [ ] Supprimer la sidebar droite permanente → inline ou drawer overlay (touche E)
> - [ ] Zone de lecture pleine largeur (`max-w-4xl` centre)
> - [ ] Marge droite avec pastilles colorees par statut
> - [ ] Carte inline depliable
> - [ ] Drawer vue liste overlay
> - [ ] Arbre overlay position fixed gauche
> - [ ] Barre d'outils en haut
>
> **Fichiers concernes** :
> - `front/templates/front/base.html`, `bibliotheque.html`
> - Nouveau : `front/templates/front/includes/carte_inline.html`
> - Adaptation : `front/templates/front/includes/extraction_results.html`
> - Nouveau : `front/static/front/js/marginalia.js`, `arbre_overlay.js`
> - CSS : layout mono-colonne, pastilles, animations, drawer
>
> **Coherence avec le reste du PLAN** :
> - L'Etape 1.8 "responsive 13-14" est simplifiee : layout nativement responsive
> - L'Etape 1.11 "mode focus" est simplifiee : masquer les pastilles et centrer le texte
> - L'Etape 1.14 "mobile" est coherente : meme principe, bottom sheet au lieu d'inline
> - La Phase 5 "wizard de synthese" s'ouvre en pleine page ou en drawer large
