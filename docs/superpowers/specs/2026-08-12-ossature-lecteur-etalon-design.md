# Aligner le lecteur sur l'étalon — ossature, fixture, toast

> Spec datée du 12 août 2026.
> LOCALISATION : `docs/superpowers/specs/2026-08-12-ossature-lecteur-etalon-design.md`
> Objectif posé par le mainteneur : **« un design presque pixel perfect avec la
> maquette »**, `front/static/front/maquettes/maquette.html`.

---

## 1. Ce que la mesure a montré

Mesuré au navigateur le 12 août, fenêtre 1600 px, note 9 « Étude
épistémologique de l'IA », produit sur `https://h.localhost/lire/9/` et étalon
sur `https://h.localhost/static/front/maquettes/maquette.html`.

| | Étalon | Produit | Source |
|---|---|---|---|
| Ossature | `.plateau` grid `1fr var(--panneau)` | `#zone-lecture` bloc + `padding-right: 608px` | `maquette.html` § 5 « DISPOSITION » |
| Panneau | `sticky`, **368 px**, dans le flux, `z-index: 1` | `#drawer-overlay` `fixed`, **576 px**, `z-index: 70` | `maquette.html` § 13 « PANNEAU / DRAWER », `base.html:292` |
| Barre d'outils | 44 px, sticky, `z-index: 70` | `nav` 48 px, `relative`, **`z-index: 30`** | `maquette.html` § 3 « BARRE D'OUTILS », `base.html` |
| Colonne de texte | `.colonne-interieure` 742 px, `margin: 0 auto` | collée à gauche, non centrée | `maquette.html` § 5 « DISPOSITION » |
| Tokens de géométrie | `--gouttiere`, `--largeur-lecture`, `--panneau`, `--barre-outils` sur `:root` | seul `--gouttiere` existe, en scope local (`maquette.css:1346`) | |
| `data-*` sur `<body>` | `mode`, `source`, `panneau`, `lecteur`, `progression`, `filtre-mode` | `user-authenticated` seulement | |

Le drawer à `z-index: 70` **recouvre la nav à `z-index: 30`** : c'est la cause
exacte du défaut signalé en passation (« le panneau s'ouvre par-dessus le
reste »). `drawer_vue_liste.js:487` porte déjà
`LARGEUR_DU_PANNEAU_INTEGRE = 1400`, mais le panneau « intégré » reste un
élément `fixed` dont on compense la place par un `padding-right` sur la zone de
lecture. La grille de l'étalon n'existe pas dans le produit.

**Correction d'une erreur de la passation** : l'écart n°4 de l'en-tête de la
maquette (« le produit est mono-colonne + drawer ») était noté « FAUX — le
panneau Analyses est permanent à droite ». Il est **VRAI**. Ce qu'on prend pour
un panneau permanent est le drawer overlay auto-ouvert au-delà de 1400 px.

**État de la base** : 6 notes, 670 éléments, **0 extraction, 0 job,
0 commentaire**. Le panneau affiche « 0 extractions ». Rien à styler tant
qu'aucune carte n'existe.

---

## 2. Les trois décisions

> **AMENDEMENT DU 12 AOÛT, APRÈS EXÉCUTION — D1 A ÉTÉ RENVERSÉE.**
> Le lot B ci-dessous n'a pas été fait tel qu'écrit : c'est l'alternative que
> D1 rejetait qui a été implémentée. Voir § 6 pour ce qui a été livré, pourquoi,
> et ce que le mainteneur doit arbitrer. Les sections 2-D1 et 3-Lot B sont
> conservées telles quelles : elles disent l'état de la réflexion au moment du
> choix, pas l'état du code.

### D1 — Adopter la grille de l'étalon (validée par le mainteneur)

Introduire dans le produit le squelette de la maquette : tokens géométriques
sur `:root`, `.plateau` en grid, `.colonne-interieure` centrée, `data-*` sur
`<body>`, panneau `sticky` dans le flux au-delà de 1400 px et drawer overlay en
dessous. Le `padding-right` compensatoire disparaît.

L'alternative — rapiécer l'existant (corriger le z-index, la largeur, le
centrage au cas par cas) — a été écartée : elle laisse le panneau hors flux, et
chaque écart suivant se re-corrigerait à la main. Le pixel-perfect resterait
approximatif.

### D2 — Fixture d'extractions déterministe, sans LLM (validée par le mainteneur)

Une commande `charger_extractions_demo` qui pose à la main les objets. Choisie
contre une vraie analyse LLM (facturée, non déterministe, non rejouable, sans
garantie de produire les cas limites) et contre l'hybride analyse-puis-gel
(deux sources à tenir à jour, coût initial).

La fixture doit couvrir **exprès** ce que la maquette dessine, sinon on style à
l'aveugle : les 8 familles d'hypostases, les deux statuts (`nouveau`,
`commente`), un chevauchement produisant des marques imbriquées, une ancre sur
un tableau, des ancres sur tours de parole audio, et des cartes à 0, 1 et 2
commentaires.

### D3 — Navigation croisée plutôt que cartes positionnées en face du texte

Le mainteneur demandait que « les extractions soient au même niveau que
l'endroit où elles sont dans le texte, pour faire la correspondance d'un coup
d'œil ». Cette demande est **en tension avec l'objectif pixel-perfect** :
l'étalon empile ses cartes en liste dense (`.panneau-corps { overflow-y: auto }`,
`maquette.html` § 13), il ne les décale pas verticalement.

L'étalon répond au même besoin autrement, par sa **navigation croisée**
(`maquette.html` § 8 « NAVIGATION CROISÉE ») : survol ou clic sur une carte → la marque
correspondante passe en `est-active` dans le texte et le bloc défile en vue ;
clic sur une marque → la carte passe en `est-active` et le panneau défile en
`{block:'nearest'}`.

Décision prise en autonomie, le mainteneur ayant délégué : **on implémente la
navigation croisée de l'étalon**. Si le décalage vertical façon commentaires
Google Docs est vraiment voulu, ce sera un écart assumé avec la maquette, à
demander explicitement — il change la nature du panneau (positionnement absolu
+ évitement de collisions) et coûte bien plus cher.

---

## 3. Périmètre de cette spec

Trois lots, dans cet ordre. La fixture d'abord : sans cartes, les deux autres
lots se travaillent à l'aveugle.

### Lot A — `charger_extractions_demo`

Commande de management dans `front/management/commands/`, sur le modèle de
`charger_fixtures_demo.py` (en-tête `LOCALISATION`, options `--reset`,
idempotence par `get_or_create`).

Objets posés, par note étalon :

| Note | Contenu visé |
|---|---|
| 9 — Étude épistémologique (PDF, 11 éléments dont 2 tableaux) | 6 extractions, dont une ancrée sur un tableau et deux qui se chevauchent sur le même élément |
| 8 — Palais César (audio, 9 tours) | 3 extractions ancrées sur des tours de parole |
| 5 — Badgeons la Normandie (HTML, 28 éléments) | 4 extractions sur `list_item` et `section_header` |

Contraintes du modèle à respecter :

- `AncrageExtraction.debut_dans_element` / `fin_dans_element` sont des positions
  **dans le texte de l'élément**, jamais dans le texte global de la page.
- `ordre_dans_extraction` commence à 0 et est unique par extraction (contrainte
  `unicite_ordre_dans_l_extraction`, `DEFERRED`).
- `ExtractedEntity.statut_debat` est **auto-dérivé par signal** de l'existence
  de commentaires : ne jamais l'assigner à la main. Poser les commentaires, le
  statut suit.
- `ExtractedEntity.start_char` / `end_char` restent renseignés (positions dans
  `text_readability`) — le modèle les impose.
  **Corrigé après mesure** : `text_readability` est **vide** sur les pages
  ingérées par le moteur élément (longueur 0 sur les notes 9 et 5). Y chercher
  une position et retomber sur 0 en cas d'échec donnait `start_char = 0` à neuf
  extractions sur douze, ce qui casse le tri (`front/views.py:941`) et renvoie
  tout clic en tête de document. Les deux champs sont **reconstruits depuis les
  éléments** : somme des longueurs des éléments précédents plus un séparateur de
  jonction, plus le début de la première portion. Ce n'est pas un offset dans
  `text_readability` — ce texte n'existe pas — mais une position dans le
  document reconstitué, monotone et distincte, ce que le tri demande.
- Une extraction qui enjambe deux éléments porte **deux** `AncrageExtraction`,
  et le rendu produit alors deux `<mark>`, pas un.

Le lot est fait quand la commande est rejouable (`--reset` puis relance donne le
même état) et que le panneau affiche des cartes dans les trois notes.

### Lot B — L'ossature

1. Porter sur `:root` (dans `maquette.css`) les tokens de géométrie de
   l'étalon : `--gouttiere: 46px`, `--largeur-lecture: 40rem`,
   `--panneau: 23rem`, `--barre-outils: 44px`, `--barre-fil: 30px`, plus les
   surcharges `body[data-source="audio"] { --gouttiere: 96px }` et
   `body[data-mode="inspection"]`.
2. Écrire les `data-*` correspondants sur `<body>` dans `base.html`, alimentés
   par le contexte de vue (source de la note, mode, état du panneau).
3. Introduire `.plateau` et `.colonne-interieure` dans le gabarit de lecture ;
   retirer le `padding-right: 608px` de `#zone-lecture`.
4. Faire du panneau un membre de la grille : `sticky` + `z-index: 1` au-delà de
   1400 px, `fixed` + `z-index: 85` (voile à 84) en dessous, conformément à
   `maquette.html` § 13 « PANNEAU / DRAWER ». La barre d'outils remonte à `z-index: 70`.
5. Rendre le panneau collapsable, ouvert par défaut au-delà de 1400 px.

**Piège d'environnement** : le build Tailwind est figé — toute classe
arbitraire (`z-[70]`, `min-w-[160px]`) est inerte. Les z-index passent par du
style inline ou par `maquette.css`, jamais par une classe arbitraire. Vérifier
au navigateur que la règle agit, ne pas le supposer.

Le lot est fait quand, mesuré au navigateur : la nav n'est plus recouverte, le
panneau fait 368 px dans le flux à 1600 px, la colonne de texte est centrée, il
n'y a pas de défilement horizontal, et le drawer redevient overlay sous
1400 px.

### Lot C — Le toast en mode sombre

Défaut mesuré en passation : texte `rgb(236,234,228)` sur fond
`rgb(22,21,26)` — **identique au fond de page** —, bordure `0px none`, ombre
noire à 18 % (invisible sur fond noir), `z-index: auto`. Le contraste du texte
est excellent (~14,8:1) ; le problème est que le toast ne se **détache** pas :
on lit son texte superposé au panneau.

Correction : un fond distinct du fond de page, une bordure, et un `z-index`
explicite. Vérifié au navigateur en clair **et** en sombre, contrastes
calculés — pas des impressions.

---

## 4. Ce qui n'est pas dans cette spec

Chantiers suivants, chacun sa spec :

- **Gouttière et formes par label** — l'écart n°6 : les tableaux sortent en
  `<pre>` et `blockquote`, `formula`, `picture`, `utterance` ne sont pas dans
  `BALISE_PAR_LABEL` (`rendu_elements.py:87-94`). Une décision de conception y
  attend le mainteneur : un tableau entier est **un seul** `ElementDocument`
  (4 471 signes pour le premier tableau du PDF étude, 1 544 pour le second,
  mesurés) ; découper par ligne ou assumer le bloc ?
- **Lecteur audio** — écart n°2, à revérifier au navigateur avant d'y aller.
- **Visualiseur PDF** — possible depuis que la base porte 72 éléments avec
  coordonnées. `SPEC-ancrage-par-element-v2.md § 8.2` est insuffisante pour
  coder (rien sur le composant PDF.js, la pagination, le zoom, le calque) : une
  spec en addendum daté est à écrire avant.

---

## 5. Méthode

- **TDD strict** : le test d'abord, on le regarde échouer, puis le code.
- **Aucune opération git** — ni `commit`, ni `add`, ni `checkout --`, ni
  `stash`, ni `reset`, ni `clean`. Le dépôt appartient au mainteneur.
- Ni `ruff format` ni `ruff check --fix` sur un fichier existant.
- Fichier statique modifié → `collectstatic` **et** bump du `?v=` dans le
  gabarit qui le charge. Sans les deux, le navigateur sert l'ancien fichier.
- Une suite de tests à la fois, et ciblée : deux `manage.py test` en parallèle
  se détruisent la base.
- Relecture adverse par un agent à chaque lot, avec correctifs testés.
- Tout front comparé à l'étalon au navigateur réel, clair et sombre.

---

## 6. Ce qui a été livré — amendement du 12 août

### D1 renversée : le panneau reste `fixed`

Le lot B prévoyait `.plateau`, `.colonne-interieure`, les `data-*` sur `<body>`
et un panneau `sticky` dans le flux. **Rien de tout cela n'a été fait.** Ce qui
a été livré, ce sont trois déclarations CSS bornées par
`@media (min-width: 1400px)` et `body.panneau-integre` : `top`, `width` et
`z-index` — c'est-à-dire, mot pour mot, l'alternative que D1 écartait.

**Pourquoi.** Deux choses découvertes après la validation de D1 :

1. `maquette.css` documente le choix inverse, argumenté par la session du
   9 août : « Le rendre `sticky` demanderait de le sortir de `base.html` […]
   Le laisser fixe et RENDRE SA PLACE au texte donne le même résultat à l'œil,
   sans rien casser. » L'argument tenait, sauf sur un point non vu à l'époque —
   le panneau recouvrait la barre d'outils.
2. Les 104 tests e2e, réputés cassés, fonctionnent dès qu'on leur donne
   `PLAYWRIGHT_BROWSERS_PATH`. Déplacer `#drawer-overlay` hors de `base.html`
   les traverse tous, ainsi que le piégeage de focus et le JS d'ouverture.

Le but posé par le mainteneur était le pixel-perfect, et la géométrie mesurée
est désormais celle de l'étalon : 368 px, sous la barre, place rendue au texte,
tiroir sous 1400 px. La grille n'y ajoutait rien de visible pour un coût et un
risque nettement supérieurs.

**Ce que le mainteneur doit arbitrer** : veut-il la grille pour elle-même —
parce qu'un panneau hors flux restera une gêne pour les chantiers suivants
(alignement des cartes, lecteur audio) — ou l'écart de moyen est-il acceptable
tant que le rendu tient ?

### Tokens : 2 posés sur 5

`--panneau` et `--barre-outils` sont sur `:root`. Manquent `--largeur-lecture`,
`--barre-fil` et la surcharge `body[data-source="audio"]`. Ils n'ont pas été
posés parce que rien ne les utilisait : la largeur de lecture vit dans
`.lecture-zone-conteneur` et la gouttière audio est déjà pilotée par
`[data-media="audio"]` sur le conteneur de blocs. Les poser sans consommateur
aurait été du décor.

### Ce qui a été corrigé en plus du périmètre

- Le débordement horizontal des `<pre>` de tableau (3 162 px poussant la page à
  3 419) et, par le même chemin, celui d'un mot insécable long.
- Deux modules e2e — `test_14_visibilite`, `test_17_filtre_contributeur` — qui
  n'étaient pas dans `front/tests/e2e/__init__.py` : 15 tests écrits, jamais
  collectés.

### Ce qui reste ouvert

- Le centrage de la colonne de lecture : 42 px de décalage contre 13 dans
  l'étalon. L'étalon décale son en-tête vers la droite, le produit tire son
  corps vers la gauche par des marges négatives.
- Le fond des cartes du panneau : transparent, là où l'étalon les pose sur un
  fond plus sombre que le panneau pour les détacher.
- Deux menus déroulants de la barre d'outils (`.dashboard-dropdown`,
  `.taches-dropdown-wrapper`, `z-index: 50`) chevauchent horizontalement le
  panneau à `z-index: 67` et peignent désormais par-dessus lui. C'est
  probablement le bon comportement pour un menu, mais ce n'est pas mesuré.
