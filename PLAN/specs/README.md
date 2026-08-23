# Les quatre specs canoniques

> Elles décrivent l'**état cible** de chaque couche du produit. Sur les quatre :
> deux sont livrées, une l'est sauf ses deux dernières sections, et la dernière
> n'a pas une ligne de code.
>
> Elles vivaient à la racine du dépôt jusqu'au 16 août 2026. Elles sont ici
> parce que **l'emplacement d'un fichier ne doit pas porter un état qui change** :
> une spec « à la racine parce qu'elle est vivante » y reste le jour où elle
> cesse de l'être, et personne ne s'en aperçoit.

## Leur état, au 16 août 2026

| Spec | Couche | État |
|---|---|---|
| `SPEC-ancrage-par-element-v2.md` | le moteur d'ancrage : portions, scission/fusion, masquage, réconciliation | ✅ **livrée** — phases A-G codées et migrées, branchement BR-A→F fait. ⏳ **sauf § 8.2 (PDF) et § 8.3 (audio)** |
| `SPEC-corpus-base-carnet-note.md` | bases de connaissances, carnets, notes, catégories par relation, permissions | ✅ **livrée** — phases A à I, à l'écran |
| `SPEC-synthese-carnet.md` | wikis vivants, synthèses dirigées, sourçage `[N]`, vérification, `section_ops` | ✅ **livrée** — phases A à I, à l'écran |
| `SPEC-selection-des-preuves.md` | regroupement d'extractions par similarité, oppositions, tri par le débat | 📌 **NON codée** — 0 template, 0 route, 0 vue |

**Ce tableau n'est pas la source de vérité sur l'avancement** — `CHANGELOG/` et
`PLAN/PASSATION.md` le sont. Il donne la couleur générale ; eux donnent la date
et la mesure.

## Le cinquième fichier n'est pas une cinquième spec canonique

`SPEC-transcription-audio-locale.md` (16 août 2026) est dans ce dossier sans
appartenir aux quatre ci-dessus. La différence est de nature : les quatre
décrivent une **couche du produit** et se placent sous l'autorité d'une maquette ;
celle-là décrit une **brique d'infrastructure** — remplacer l'API Mistral Voxtral
par une chaîne locale — et son étalon est une transcription humaine, pas un écran.

**Son état est écrit dans son propre en-tête, et le chantier est suivi dans
`PLAN/PASSATION.md § 5.4`** — il n'est pas recopié ici. Deux copies d'un même état
finissent toujours par diverger, et c'est ce que la ligne précédente faisait
jusqu'au 16 août 2026.

## Le sixième fichier non plus

`SPEC-edition-par-blocs-et-stenotypie.md` (23 août 2026) décrit une **couche
d'interaction** — ce qu'un humain peut faire aux éléments : corriger, vider, écouter,
naviguer au clavier — et non une couche de produit. Elle ne définit **aucun modèle** :
elle se pose au-dessus de `SPEC-ancrage-par-element-v2.md`, dont elle suppose les
portions, le masquage et la réconciliation déjà livrés.

**Son état est dans son propre en-tête** — spécifiée, non codée — et la voie technique
n'y est délibérément pas choisie : trois sont en concurrence, et un prototype les
départage (`PLAN/TODO/2026-08-23-le-prototype-blocknote-sur-notre-back.md`).

## Comment les lire

**Les encarts datés en tête d'un fichier font foi. Ses sections, non.** Les
specs ont été déposées sans réécriture : leur corps est le texte de la
proposition d'origine, et l'écart avec le code livré est noté en tête, daté.

Exemple à connaître : `SPEC-ancrage § 2.2` décrit un `EtatAncrage` à trois
valeurs, quand le code n'en a que deux (`ANCREE` / `DETACHEE`). La correction
est dans l'encart, pas dans la section.

**Pourquoi les garder telles quelles plutôt que les mettre à jour** :
`SPEC-ancrage` le dit d'elle-même — *« c'est le seul endroit où les décisions
écartées et leurs raisons sont conservées, et le code ne les porte pas »*. Une
spec réécrite après coup perd exactement ce qui fait sa valeur : la trace de ce
qu'on a envisagé puis rejeté, et pourquoi.

## Le piège du mot « phase »

Chaque spec a sa propre numérotation, et elles ne coïncident pas :

| Document | Numérotation |
|---|---|
| `SPEC-ancrage-par-element-v2.md` | A → K, plus les addenda BR-A → BR-F et U1 → U5 |
| `SPEC-synthese-carnet.md` | A → I |
| `SPEC-corpus-base-carnet-note.md` | A → I |
| `PLAN/archive/PHASES/` | 1 → 29 |

« La phase H » désigne quatre choses différentes. **Toujours préciser de quelle
spec on parle.**

## Ce qui reste à spécifier avant de coder

- **Le visualiseur PDF.** `SPEC-ancrage § 8.2` donne trois corrections justes
  (`convertToViewportRectangle`, `devicePixelRatio`, `boites` en liste) mais
  **sans le socle** : rien sur le composant PDF.js, la pagination, le zoom, le
  calque de surlignage. La donnée existe (72 coordonnées en base). Écrire cette
  spec en addendum daté **avant** de coder. Détails et pièges dans
  `PLAN/PASSATION.md § 5.2`.
- **Le RAG**, spécifié dans `PLAN/INSPIRATION_ATOMIC.md § 6`, à réconcilier avec
  le moteur ELEMENT, non implémenté (pgvector absent).
- **La scission/fusion côté interface** : le moteur et l'endpoint existent
  (BR-E), mais aucun geste dans la maquette — « l'opération n°1 » sur une
  diarisation n'a aucune référence visuelle.
- **La granularité de l'ancrage sur un tableau** : décision de **modèle** en
  attente du mainteneur. Un tableau est un seul `ElementDocument` de 4 471
  signes ; une idée ancrée dessus désigne le tableau entier.

## Leurs étalons

`SPEC-synthese-carnet.md` et `SPEC-selection-des-preuves.md` se placent sous
l'autorité des maquettes de `front/static/front/maquettes/` : *« toute
divergence entre cette spec et la maquette est un défaut de l'une des deux, à
trancher avant de coder »*.
