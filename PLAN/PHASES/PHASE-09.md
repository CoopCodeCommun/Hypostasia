# PHASE-09 — Refonte layout : pastilles marge + cartes inline

**Complexite** : L | **Mode** : Plan then normal | **Prerequis** : PHASE-07, PHASE-08, PHASE-06

---

## 1. Contexte

Dans le layout 3 colonnes actuel, la carte d'extraction est a droite et le passage qu'elle reference est au centre — l'utilisateur fait en permanence des allers-retours visuels (split-attention). Le nouveau layout resout ce probleme : les extractions s'affichent directement sous le passage concerne (cartes inline), et des pastilles colorees dans la marge droite indiquent la presence et le statut des extractions. C'est le coeur de l'experience "livre annote" : le texte est au centre, les annotations sont en marge, contextuelles.

## 2. Prerequis

- **PHASE-07** — Layout mono-colonne en place (zone de marge droite reservee).
- **PHASE-08** — Arbre overlay et toolbar complete en place (les deux phases modifient `base.html`, le sequencement est necessaire).
- **PHASE-06** — Modeles de statut de debat (`statut_debat` sur `ExtractedEntity`) necessaires pour colorer les pastilles.

## 3. Objectifs precis

- [ ] Supprimer la sidebar droite permanente — les extractions s'affichent inline (sous le passage) ou en drawer overlay (PHASE-10)
- [ ] Ajouter une marge droite (3-4rem) a la zone de lecture pour les pastilles
- [ ] Implementer les pastilles rondes (8-10px) dans la marge, alignees verticalement avec le passage extrait
- [ ] Couleur des pastilles = statut de debat (memes variables CSS que les badges : vert consensuel, rouge discutable, ambre discute, orange controverse)
- [ ] Si plusieurs extractions couvrent le meme passage → pastilles empilees verticalement
- [ ] Clic sur une pastille → deplie la carte d'extraction inline sous le paragraphe
- [ ] Creer le template `carte_inline.html` : meme contenu que la carte actuelle (hypostase, resume, citation, statut, commentaires, sources)
- [ ] La carte inline s'insere dans le DOM entre les paragraphes, pousse le texte vers le bas
- [ ] Bouton replier (▴) pour fermer la carte inline
- [ ] Animation CSS : slideDown 200ms ease pour l'ouverture de la carte inline
- [ ] La marge se redessine apres chaque annotation HTML (memes donnees que `front/utils.py`)
- [ ] Adapter `front/utils.py` pour generer les donnees de position des pastilles dans la marge
- [x] Le surlignage du texte est colore par statut de debat (fond + soulignement). Sur desktop le surlignage est subtil (les pastilles de marge sont le signal principal). Sur mobile (PHASE-21) le surlignage est plus marque car les pastilles sont masquees. Les extractions commentees ont un soulignement pointille.

## 4. Fichiers a modifier

- `front/utils.py` — adaptation de l'annotation HTML pour generer les positions de pastilles dans la marge
- `front/templates/front/includes/carte_inline.html` — **(nouveau)** carte d'extraction depliable inline sous le passage
- `front/templates/front/includes/lecture_principale.html` — ajout de la marge droite et des pastilles
- `front/static/front/js/marginalia.js` — **(nouveau)** gestion des pastilles (clic, depliage inline, animation)
- `front/static/front/css/hypostasia.css` — styles pastilles de marge, carte inline, animations slideDown

## 5. Criteres de validation

- [ ] Les pastilles colorees apparaissent dans la marge droite, alignees avec les passages extraits
- [ ] La couleur de chaque pastille correspond au statut de debat de l'extraction
- [ ] Clic sur une pastille deplie la carte inline sous le paragraphe concerne
- [ ] La carte inline affiche l'hypostase, le resume IA, la citation, le statut, les commentaires et sources
- [ ] Le bouton replier (▴) ferme la carte inline
- [ ] L'animation slideDown est fluide (200ms ease)
- [ ] Plusieurs pastilles empilees verticalement quand un passage a plusieurs extractions
- [ ] Le texte est repousse vers le bas quand une carte inline est depliee (pas de superposition)
- [ ] La sidebar droite permanente n'existe plus

## 5b. Verification navigateur

> Lancer `uv run python manage.py runserver` et ouvrir http://localhost:8000/

1. **Ouvrir un document avec des extractions** : cliquer sur un document analyse dans l'arbre
   - **Attendu** : des pastilles colorees (petits cercles) apparaissent dans la marge droite, alignees avec les passages extraits. Vert = CONSENSUEL, rouge = CONTROVERSE, ambre = DISCUTE, orange = DISCUTABLE
2. **Cliquer sur une pastille** : cliquer sur un cercle colore dans la marge
   - **Attendu** : une carte d'extraction se deplie sous le passage concerne avec animation (slideDown ~200ms). La carte montre l'hypostase, le resume, la citation, le statut, les commentaires
3. **Cliquer sur le bouton replier (▴) de la carte** : fermer la carte inline
   - **Attendu** : la carte se replie avec animation
4. **Verifier un passage avec 2+ extractions** : trouver un passage avec plusieurs extractions
   - **Attendu** : plusieurs pastilles empilees verticalement
5. **Deplier une carte** : observer le comportement du texte en dessous
   - **Attendu** : le texte en dessous est repousse vers le bas (pas de superposition)

## 6. Extraits du PLAN.md

> **Les 3 modes d'affichage des extractions** :
>
> | Mode | Declencheur | Ce qui s'affiche |
> |---|---|---|
> | **Marginalia** (defaut) | Vue de lecture normale | Pastilles colorees dans la marge droite (statut). Le texte est surligne. Tap/clic sur pastille → deplie la carte inline |
> | **Inline deplie** | Clic sur une pastille de marge | La carte d'extraction s'ouvre sous le passage concerne, pousse le texte vers le bas. Bouton replier (▴) pour fermer |
> | **Drawer vue liste** | Toggle (touche E, ou bouton "Toutes les extractions") | Overlay a droite (32rem, position fixed) montrant TOUTES les cartes en liste scrollable |
>
> **Actions** :
> - [ ] Supprimer la sidebar droite permanente. Les extractions s'affichent inline (sous le passage) ou en drawer overlay (touche E)
> - [ ] Marge droite (3-4rem) avec pastilles colorees par statut de debat :
>   - Couleur = statut (vert consensuel, rouge discutable, ambre discute, orange controverse)
>   - Taille = nombre d'extractions sur ce passage (1 pastille = 1 extraction, empilees si plusieurs)
>   - Clic pastille → deplie la carte inline sous le paragraphe
> - [ ] Carte inline : meme contenu que la carte actuelle (hypostase, resume, citation, statut, commentaires, sources)
>   - S'insere dans le DOM entre les paragraphes, pousse le texte vers le bas
>   - Bouton replier (▴) pour fermer
>   - Animation CSS : slideDown 200ms ease
>
> **Pastilles de marge** (remplace l'ancienne minimap) — dans la marge droite du texte (~3-4rem) :
>
> - Pastilles rondes (8-10px) dans la marge droite, alignees verticalement avec le passage extrait
> - Couleur = statut de debat (memes variables CSS que les badges)
> - Si plusieurs extractions couvrent le meme passage → pastilles empilees verticalement
> - Clic sur une pastille → deplie la carte d'extraction inline sous le paragraphe
> - La marge se redessine apres chaque annotation HTML (meme donnees que `front/utils.py`)
>
> ```
> ┌───────────────────────────────────────────────────┬──────┐
> │                                                   │ marge│
> │   L'intelligence artificielle souleve des         │      │
> │   questions fondamentales sur l'avenir du          │  ●   │ ← pastille DISCUTE
> │   travail creatif.                                │      │
> │                                                   │      │
> │   ┌─────────────────────────────────────────────┐ │      │
> │   │ CONJECTURE            [replier ▴]           │ │      │
> │   │ L'IA va transformer les metiers creatifs    │ │      │
> │   │ en metiers de supervision.                  │ │      │
> │   │ « Je pense que dans 5 ans, on ne dessinera  │ │      │
> │   │   plus, on pilotera »                       │ │      │
> │   │ ● DISCUTE  #ia #metiers    💬 3    📎 2    │ │      │
> │   └─────────────────────────────────────────────┘ │      │
> │                                                   │      │
> │   En revanche, le secteur juridique semble        │      │
> │   mieux prepare.                                  │  ●●  │ ← 2 extractions
> │                                                   │      │
> │   Le consensus se forme autour de l'idee          │      │
> │   que la regulation est necessaire.               │  ○   │ ← CONSENSUEL
> └───────────────────────────────────────────────────┴──────┘
> ```
>
> **Fichiers concernes** :
> - Nouveau template `front/templates/front/includes/carte_inline.html` (carte d'extraction depliable dans le texte)
> - `front/static/front/js/marginalia.js` (gestion des pastilles, depliage inline, drawer)
> - `front/utils.py`
> - CSS : styles des pastilles de marge, animations inline
