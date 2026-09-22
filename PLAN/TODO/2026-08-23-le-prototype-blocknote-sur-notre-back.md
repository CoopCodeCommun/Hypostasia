# Prototype : trois voies pour l'édition par blocs

> ## ⚠️ CE QUI RESTE — 23 août 2026, au soir. Le prototype a tourné.
>
> **Cette note n'est pas supprimée, et c'est délibéré.** Elle devait l'être le jour
> où la voie serait tranchée. **Elle ne l'est qu'à moitié** : l'option C est
> instruite et tient, mais **B n'a jamais été construite ni pesée** — son bundle,
> qui était son premier critère de chute, n'a pas de chiffre. L'écarter est un
> **arbitrage**, pas un résultat de mesure, et le dossier TODO garde ce qui n'est
> pas décidé.
>
> **Les chiffres, la méthode et les limites** :
> `CHANGELOG/2026-08-23-le-champ-unique-tranche-l-edition-par-blocs.md`.
> La spec porte la décision dans son encart de tête.
>
> **Ce que le prototype a établi** : le champ tient à 210 blocs (6 ms par frappe) ;
> le diff par `identifiant_stable` est exact (0 perdu, 0 dupliqué, 191 blocs
> intacts à l'octet) ; **`plaintext-only` n'empêche pas la fusion multi-blocs** ; et
> **l'interception doit vivre dans `beforeinput`** — une garde par `keydown` laisse
> `Ctrl+A` + frappe réduire une note de 210 blocs à un seul.
>
> **La mesure des ancres — le critère éliminatoire de cette note — a été prise**, et
> elle rassure : `reconcilier_les_portions_de_l_element` ne détache **que** les
> portions qui enjambent le point d'édition (22 sur 22), et **aucune** des 37
> autres. Ce comportement est **le même pour les trois voies** : elles appellent
> toutes cette fonction. Confirmé au passage, et indépendant de la voie : **14
> éléments sur 40 (35 %) sont refusés d'emblée** parce qu'une synthèse figée les
> cite.
>
> **Un piège de plateforme, découvert en refermant les trous** :
> `getTargetRanges()` rend une **liste vide** sous `plaintext-only` (Chromium 145),
> là où la sélection traverse bien trois blocs. Une garde qui s'y fie seule y est
> aveugle. `plaintext-only` n'est donc **pas** optionnel — c'est lui qui tient le
> collage non traversant — et le combiner avec la garde exige un repli sur
> `window.getSelection()`.
>
> **LES TROIS MESURES SONT FAITES, ET LES TROIS PASSENT** (26 août 2026). Cette
> note ne survit plus que pour **le bundle de B, jamais pesé** — voir la fin de cet
> encart. Le détail des trois :
>
> 1. ✅ **FAIT le 26 août 2026 — Firefox 146 et WebKit 26.** `libgtk-3-0t64` a été
>    installé dans le conteneur (décision du mainteneur) ; les binaires y étaient
>    déjà. **La promesse fondatrice tient sur les trois moteurs**, et la garde aussi
>    sur le chemin réel (sélection au clavier + `Suppr`) : **210 blocs et 210
>    gouttières intacts** partout avec elle, cassé partout sans elle. Le piège de
>    `getTargetRanges()` est **propre à Chromium**. Une divergence WebKit à
>    connaître : le repère de gouttière entre dans la sélection étendue au clavier —
>    défaut de **copie**, pas de correction.
> 2. ✅ **FAIT le 26 août 2026.** La garde a été injectée dans la **vraie page**,
>    avec ses 189 boutons d'action : les trois gestes tiennent (**189 → 189**, zéro
>    mutation, zéro erreur JS), lire `.corps.textContent` donne **0 bloc exact sur
>    189** et lire l'élément interne **189 sur 189**. Et sur la page 19, **202 sur
>    210 bouclent — les 8 échecs sont exactement les 8 `table`**.
>    *(Non vus : un `.element-masque` et un `avertissement-plafond` dans le flux.)*
> 3. ✅ **FAIT le 26 août 2026 — et la parade marche.** Vraie composition par CDP :
>    **210 → 205 sans parade, 210 → 210 avec**. On ne combat pas la composition, on
>    lui retire sa matière — la sélection est normalisée dès `compositionstart`, qui
>    arrive avant toute écriture. Le gestionnaire s'arme sur les trois moteurs.
>    ⚠️ **Android reste non éprouvé** : la vraie composition n'est déclenchable que
>    sur Chromium, et c'est là que ça compterait le plus.
>
> **Le poids du bundle de B reste sans chiffre**, et le seuil que cette note voulait
> fixer « avant de mesurer » n'a jamais été fixé. Si les coûts de C enflent — une
> annulation applicative est déjà à écrire —, **B redevient candidate**, et c'est
> par là qu'il faudra reprendre.
>
> **Tout ce qui suit est l'état d'AVANT le prototype.** Il garde ses mesures de
> lecture du dépôt `suitenumerique/docs`, qui n'ont pas été refaites.


**Décidé par le mainteneur le 23 août 2026. Rien n'est codé.**

> **📘 La spec fait foi désormais.**
> `PLAN/specs/SPEC-edition-par-blocs-et-stenotypie.md` (23 août 2026) absorbe cette
> note. Celle-ci garde ses **mesures** et son historique de décision ; en cas de
> désaccord, c'est la spec qui compte — sauf sur le choix de la voie technique, que
> le prototype tranche.


**Ce prototype est jetable, et son but est de DÉCIDER**, pas de livrer. Il tranche
entre trois voies concurrentes pour l'édition par blocs :

- **A — le clavier maison** : `2026-08-23-le-mode-edition-et-son-clavier.md`
  (~300 lignes dans `keyboard.js`, aucune dépendance nouvelle) ;
- **B — BlockNote** : les gestes d'édition fournis par la bibliothèque, au prix d'un
  bundle JS et d'un modèle de données à traduire ;
- **C — le champ unique** : tout le texte éditable d'un coup, les blocs restant des
  blocs. Décidée le 23 août, **sans aucune dépendance** — voir la section en fin de
  note, et la commencer par elle : une journée contre trois.

**Tant que ce prototype n'a pas parlé, aucune des trois ne doit être codée.** La
note du back (`2026-08-23-les-deux-gestes-manquants-de-l-edition-par-blocs.md`) sert
les trois indifféremment : elle, en revanche, peut avancer.

## Ce qui est déjà établi, et n'a pas à être remesuré

Lecture du dépôt `suitenumerique/docs` v5.4.1 (cloné dans `../docs`), le 23 août 2026 :

- **BlockNote fournit les gestes structurels gratuitement.** `hook/useShortcuts.tsx`
  fait 117 lignes et **ne définit aucun raccourci d'édition** — seulement des
  annonces d'accessibilité pour le formatage (`Ctrl+Alt+1/2/3`,
  `Ctrl+Maj+0/6/7/8/9/C`) et l'interception de `@`. Entrée qui scinde, Retour arrière
  qui fusionne, Tab qui imbrique : rien n'est écrit chez eux. **C'est l'argument
  central en faveur de B.**
- **Leur module éditeur pèse 56 fichiers et 5 158 lignes de TS/TSX** — mais l'essentiel
  sert ce que nous ne voulons pas : collaboration, IA, commentaires, export docx/odt/pdf,
  multi-colonnes.
- **Leur persistance est un blob Yjs** (`toBase64(Y.encodeStateAsUpdate(yDoc))`,
  toutes les 60 s) et **leur conversion exige un serveur Node** (`servers/y-provider`,
  974 lignes, `ServerBlockNoteEditor.blocksToMarkdownLossy`). **Ni l'un ni l'autre
  n'est reprenable** : nos blocs sont des lignes en base, et notre pipeline est Python.
- **Le schéma de blocs est extensible** : `BlockNoteSchema.create({blockSpecs})`.
- **BlockNote est utilisable en vanilla** : `useCreateBlockNote` n'est qu'un `useMemo`
  autour de `BlockNoteEditor.create()`. Sans React/Mantine on perd menus, barres
  d'outils et thèmes.
- **Notre back est plus prêt qu'il n'y paraît** : `reconcilier_les_portions_de_l_element`
  réaligne déjà les ancres après une correction de texte, et **compte les portions
  détachées**. Ce que je croyais bloquant ne l'est pas.
- **Notre front n'a aucune chaîne de build JS** : le `package.json` de la racine ne
  sert qu'à Playwright, il n'y a pas de `node_modules`, et les libs tierces sont des
  fichiers minifiés déposés à la main dans `front/static/front/vendor/` (htmx,
  sweetalert2).

## Le pari que le prototype doit vérifier

**Nos deux cas d'usage n'ont pas besoin de texte riche.** Une transcription, c'est du
texte brut et un locuteur ; un PDF nettoyé, c'est du texte brut et un label Docling.
On ne veut pas mettre en gras : on veut **couper, recoller, corriger, supprimer**.

Si c'est vrai, l'obstacle le plus profond — `ElementDocument.texte` est une chaîne où
l'on ancre par offsets, quand BlockNote a `content: InlineContent[]` avec styles — se
neutralise **en configuration** : un schéma minimal, sans styles inline. C'est ce
pari-là que le prototype éprouve. **S'il tombe, la voie B tombe avec lui.**

## Le montage à prototyper

- `BlockNoteEditor.create()` + `mount()`, **sans React**, **sans Yjs**, **sans
  Hocuspocus** ;
- **schéma minimal** : paragraphe et titre, aucun style inline, aucun bloc média ;
- correspondance des modèles :

| BlockNote | Nous |
|---|---|
| `id` | `ElementDocument.identifiant_stable` (UUID, `unique`) |
| `type` | `label` (`text`, `section_header`, `list_item`…) |
| `content` (texte nu) | `texte` |
| `props` | `provenance` — `{locuteur, debut, fin}` ou `{page_no, boites}` |

- **le diff se fait en Python, jamais en JavaScript.** À la sortie du mode édition, un
  seul POST de `[{id, type, texte}, …]` ; Django compare avec ses `ElementDocument`
  par `identifiant_stable` et en déduit les opérations, qu'il applique avec les
  verrous existants (ligne pour `corriger`/`masquer`, **page** pour `scinder` et
  `fusionner`, qui renumérotent). C'est la règle du skill `djc` : « toujours préférer
  la logique serveur à la logique client ».

**Le prototype vit hors du dépôt** — dans le scratchpad de session ou un dossier
ignoré. Rien de ce code n'est destiné à être gardé : ce qu'on garde, ce sont les
chiffres et la décision.

## Les six mesures à prendre

Aucune n'appelle un modèle : **pas de `make test-llm`, pas de facture.**

1. **Le poids du bundle**, produit une fois par esbuild ou vite, en octets bruts **et**
   gzippés. C'est le chiffre qui décide seul si la voie B est tenable : à titre de
   repère, `htmx-2.0.4.min.js` et `sweetalert2-11.min.js` sont tout ce que porte
   `vendor/` aujourd'hui.
2. **Le schéma minimal tient-il ?** Coller du texte riche depuis un traitement de
   texte, et vérifier qu'aucun style n'entre. Si un `<b>` survit, le texte de nos
   blocs cesse d'être une chaîne et **les ancres deviennent fausses en silence** —
   c'est la panne que ce projet refuse.
3. **Le diff tient-il ?** Une note réelle à ~200 blocs, vingt gestes enchaînés
   (scissions, fusions, corrections, suppressions), puis comparaison : le POST final
   doit produire exactement les opérations attendues, sans identifiant perdu ni
   dupliqué.
4. **Les ancres survivent-elles ?** Sur une note **analysée**, compter les portions
   détachées après la même session. `reconcilier_les_portions_de_l_element` les
   compte déjà : il n'y a qu'à lire son résultat.
5. **Le temps de montage** sur 200 blocs, et la fluidité de la frappe — mesurés sur la
   machine de dev, dont la mémoire du projet rappelle qu'elle est une VM Haswell sans
   VNNI. **Mesurer sur une machine peu chargée** : un `docker build` en parallèle a
   déjà triplé un chiffre sans le dire.
6. **L'accessibilité.** Docs écrit 117 lignes uniquement pour *annoncer* ses
   raccourcis aux lecteurs d'écran : signe que BlockNote ne le fait pas seul. Éprouver
   au clavier seul, et avec un lecteur d'écran. Notre exigence est explicite dans
   `djc` et ne se négocie pas après coup.

## Les critères de décision, écrits AVANT la mesure

Pour que le résultat tranche au lieu de se discuter :

| Mesure | La voie B tombe si… |
|---|---|
| bundle | il dépasse ce que le mainteneur accepte de figer dans `vendor/` — **seuil à fixer avant de mesurer** |
| schéma minimal | un style inline traverse le collage |
| diff | une seule opération est fausse sur les vingt |
| ancres | le taux de portions détachées dépasse celui du même travail fait à la main |
| accessibilité | le clavier seul ne suffit pas à faire les cinq gestes |

Le temps de montage, lui, n'est pas éliminatoire : c'est un confort.

**Et un critère qui n'est pas mesurable** — celui-là se tranche à la lecture du
prototype, pas à la calculatrice : **combien de code custom reste-t-il vraiment ?**
Si brancher BlockNote demande autant de lignes que la voie A pour un bundle en plus,
l'argument qui a motivé ce prototype (« le moins de front custom à maintenir »)
s'est retourné.

## Le piège à ne pas reproduire

Un bundle pré-construit déposé dans `vendor/` **reproduit exactement le piège du
build Tailwind**, que `AGENTS.md` documente comme un invariant : « toute classe
absente du bundle est **inerte**, sans la moindre erreur ». Un second bundle figé
serait pire — il porterait de la logique, pas seulement du style.

Donc, si la voie B est retenue : la commande qui produit le bundle **est versionnée**,
et le `CHANGELOG` du chantier dit comment la relancer. Un bundle qu'on ne sait pas
reconstruire est une dette, pas une dépendance.

## Ce qui casse si on ne fait rien

Rien. On code la voie A, qui marche, qu'on maîtrise, et qui n'ajoute aucune
dépendance. Ce prototype existe pour qu'on ne le fasse pas **par défaut**, sans avoir
regardé — et pour que si l'on choisit A, ce soit avec les chiffres de B en main.

## Coût de mise en œuvre

Deux à trois jours : le bundle, un écran hors flux, l'endpoint de diff en Python, et
les six mesures. C'est un investissement de décision, pas de production — et il évite
d'en engager un beaucoup plus gros dans la mauvaise direction.

---

## Option C — le champ unique, ajoutée le 23 août 2026

**Décidée par le mainteneur dans la foulée**, et devenue la voie la plus probable :
elle n'ajoute **aucune dépendance** et se prototype en une journée.

### Le principe

Tout le texte de la note est éditable d'un coup, comme un seul document — mais
**les blocs restent des blocs**. On édite leur **texte**, jamais leur **découpage**.

Ce qui est explicitement **hors périmètre** (décision du mainteneur, YAGNI) :

- **pas de fusion**, **pas de scission** par l'édition — ni manuelle, ni automatique ;
- **pas de scission d'un bloc « trop gros »** : c'était une décision de sens prise par
  une machine, et sur une transcription elle aurait **inventé** deux intervalles de
  temps là où le code, en fusion, prend soin de **retirer** `voice` quand deux tours
  divergent (`moteur_structure.py:485-488`) ;
- **pas de polling** : `Ctrl+S`, un geste explicite.

Les gestes de structure restent ce qu'ils sont aujourd'hui — des boutons, en mode
structure. Ce mode-ci ne fait qu'une chose : **rendre le texte éditable partout**.

### Ce qui est déjà écrit et n'a rien à devenir

| Brique | Où | Ce qu'elle fait |
|---|---|---|
| le rendu du champ | `front/views.py:481`, `_texte_de_la_note_depuis_ses_elements` | `"\n\n".join(...)` sur les blocs non masqués, triés par `ordre` — **le séparateur est déjà celui-là** |
| l'appariement | `ElementDocument.empreinte_contenu` | SHA-256 du texte normalisé, déjà utilisé par la ré-ingestion pour « reconnaître un élément inchangé » |
| le recalcul des ancres | `reconcilier_les_portions_de_l_element` | réaligne les portions et **compte les détachées** |
| le vidage d'un bloc | `services/masquage.py` | portions en DÉTACHÉE, jamais supprimées, réversible |
| l'historique | `PageEdit` (`type_edit`, `donnees_avant`, `donnees_apres`) | déjà écrit par `corriger` |
| **la frontière visible** | `maquette.css:1670` | **chaque bloc est déjà une grille « gouttière \| corps » avec un filet d'état vertical**, gouttière de 46 px |

**La gouttière répond seule à la question des frontières** : elles sont déjà
matérialisées, bloc par bloc, sans rien ajouter. On ne perd donc que le *chrome*
d'édition — pas le repère. C'est exactement l'objectif : « comme si c'était un seul
gros fichier », sans effacer ce qui porte le sens.

### Le seul point dur, et sa réponse

Un champ unique qui traverse plusieurs blocs, c'est un `contenteditable` sur le
conteneur avec un enfant par bloc (`data-element="<identifiant_stable>"`). La
sélection traverse alors les blocs — **c'est ce qui rend possible le cas PDF**
(sélectionner trente en-têtes et les vider d'un geste), et c'est impossible avec un
`<textarea>` par bloc, entre lesquels aucune sélection ne passe.

Mais un `contenteditable` multi-enfants est précisément ce qui fait souffrir tout le
monde : le navigateur crée et supprime des enfants tout seul. **C'est la raison d'être
de ProseMirror, donc de BlockNote.**

**La décision « pas de fusion, pas de scission » désamorce ce piège**, et c'est ce qui
rend l'option C tenable : deux interceptions suffisent.

- `Entrée` → `preventDefault`, on insère un `\n` **dans** le bloc ;
- `Retour arrière` en tête de bloc → `preventDefault`, rien.

Restent le collage (à forcer en texte brut) et, à éprouver au prototype,
`contenteditable="plaintext-only"` — son support navigateur est à vérifier, pas à
supposer.

### Ce qu'il manque au back : un seul endpoint

`corriger_en_lot` : reçoit `[{identifiant_stable, texte}, …]`, et pour chaque bloc

1. compare l'empreinte — **ne traite que ce qui a changé** ;
2. texte vidé ⇒ **`masquer`**, jamais `delete` : `AncrageExtraction.element` est en
   **PROTECT**, et **386 éléments sur 1 129** portent un ancrage (826 ancrages,
   mesuré le 23 août) — un `delete()` lèverait sur un tiers des blocs ;
3. sinon `reconcilier_les_portions_de_l_element`, verrou de **ligne** (aucun ordre ne
   bouge, donc pas de verrou de page) ;
4. un `PageEdit` par lot, et **un compte rendu** : tant de blocs modifiés, tant
   masqués, **tant de passages détachés**. La réconciliation rend déjà ce nombre.

### Le mode ne s'ouvre pas si une tâche tourne

`services/garde_edition.py` refuse déjà l'édition pendant une analyse. La décision du
mainteneur : **vérifier à l'entrée du mode**, pas au `Ctrl+S` — un refus après vingt
minutes de frappe serait le pire des deux mondes. Et l'historique `PageEdit` sert de
contrôle a posteriori.

### Ce qu'il reste à mesurer, en plus des six mesures ci-dessus

1. **Le champ tient-il à 59 000 caractères ?** C'est la taille mesurée de la plus
   grosse note de la base (210 blocs). Fluidité de la frappe, temps de rendu.
2. **Les deux `preventDefault` tiennent-ils ?** Éprouver le collage, le glisser-déposer
   de texte, la correction orthographique du navigateur, l'annulation native
   (`Ctrl+Z`) — tous savent créer des nœuds.
3. **Les tables.** **2 éléments sur 1 129** contiennent une ligne vide interne, et ce
   sont **les deux des `table`**. Elles ne cassent pas l'option C (on ne re-découpe
   rien) mais leur édition en texte libre est à éprouver.
4. **Le cas transcription est mesurable ICI, sans rien ingérer.** Remesuré le 23 août
   2026 sur la base de dev : `provenance__has_key='locuteur'` — la clé réellement
   écrite par `ingestion_audio.py` — rend **21 éléments sur 1 129**, répartis sur
   **deux notes** (page 3 « Débat IA — transcription », 12 éléments ; page 4 « Palais
   César — deux locuteurs », 9 éléments), et **5 locuteurs distincts** (`Elinor`,
   `Eric`, `Laurent`, `speaker_1`, `speaker_2`). Exemple de provenance :
   `{'debut': 0.0, 'fin': 27.5, 'locuteur': 'Laurent'}`.
   **`provenance__has_key='voice'` rend bien 0** — l'ancienne orthographe n'est écrite
   nulle part.

   > Cette mesure **corrige** ce que deux notes du 23 août affirmaient : « 0 élément,
   > aucune transcription n'y est ingérée ». Elles interrogeaient `voice`, la clé
   > morte, et en concluaient à l'absence de transcription. Le prototype n'a donc
   > **pas** à ingérer un audio pour éprouver le cas audio — mais 21 éléments sur deux
   > notes courtes ne disent rien de la tenue à 200 blocs.

### Les blocs vidés — masqués, jamais supprimés

**C'est le geste central du nettoyage post-Docling**, et il découle de la sélection
multi-blocs : on sélectionne trente en-têtes, on vide, les trente blocs deviennent
vides, donc masqués.

- **`masquer`, jamais `delete`.** `AncrageExtraction.element` est en `PROTECT`, et
  **386 éléments sur 1 129** portent un ancrage (826 ancrages, mesuré le 23 août) :
  un `delete()` lèverait une `ProtectedError` sur un tiers des blocs.
- **C'est déjà écrit et c'est déjà le bon comportement** (`services/masquage.py`) :
  les portions passent **DÉTACHÉE**, jamais supprimées ; le bloc reste dans le
  document, barré et grisé ; il ne part plus dans les chunks envoyés au LLM ; et
  `demasquer` remet les portions en place **si le texte n'a pas changé entre-temps**.
  Le principe est celui du projet : « rien ne disparaît en silence ».
- **Le compte rendu le dit** : tant de blocs masqués, tant de passages détachés.

Trois questions restent ouvertes, et le prototype doit y répondre :

1. **Que voit-on dans le champ quand un bloc est vidé ?** Il disparaît (et le texte se
   referme), ou il reste comme une ligne vide jusqu'au `Ctrl+S` ? Le placeholder
   `.element-masque` existe déjà, mais **seulement en mode structure**.
2. **Vider puis re-remplir dans la même session** : le bloc est-il masqué puis
   démasqué, ou jamais masqué du tout ? La seconde réponse est plus simple et plus
   juste — on compare l'état au `Ctrl+S`, pas les frappes.
3. **Vider TOUS les blocs d'une note** : c'est le cas limite. On masque tout, et la
   note devient vide — faut-il un refus, ou est-ce un geste légitime qu'un
   `demasquer` rattrape ?

### Le clavier — ce qui est natif, et les trois pièges

**Vérifié dans le code le 23 août 2026.**

**Ce que le `contenteditable` unique donne gratuitement**, et qui est la raison de le
préférer à un champ par bloc : `↑` `↓` `←` `→` **traversent les blocs**,
`Maj+flèches` **étendent la sélection à travers**, `Ctrl+Début` / `Ctrl+Fin` vont aux
extrémités. Entre deux `<textarea>`, **aucune flèche ne traverse et aucune sélection
ne passe** — le cas PDF serait mort.

**Piège 1 — la suppression multi-blocs FUSIONNE.** Une sélection allant du milieu du
bloc 3 au milieu du bloc 8, suivie de `Suppr`, laisse au navigateur **un seul nœud**
contenant le début de 3 et la fin de 8. C'est une fusion — précisément ce qu'on a
interdit. Il faut donc intercepter `Suppr` et `Retour arrière` **quand la sélection
traverse plusieurs blocs**, et faire le geste soi-même : vider le contenu sélectionné
**bloc par bloc**, sans jamais toucher aux frontières.

**Piège 2 — `keyboard.js` ignore tout ce qui porte Ctrl.** Ligne 372 :
`if (evenement.ctrlKey || evenement.metaKey || evenement.altKey) return;`. **`Ctrl+S`
ne passe donc pas aujourd'hui**, et il faut une exception explicite — dans ce
fichier, qui est « le SEUL listener keydown de l'application ». Il faudra aussi
`preventDefault()` : `Ctrl+S` est le raccourci « enregistrer la page » du navigateur.

*Bonne nouvelle du même endroit* : **`Échap` est traité AVANT la garde de champ de
saisie** — « Escape fonctionne toujours (même dans un champ de saisie) », ligne 357.
Sortir du mode marchera sans rien changer à la cascade existante.

**Piège 3 — le sens de la sélection.** `window.getSelection()` rend `anchorNode` et
`focusNode` dans l'ordre du **geste**, pas du document : une sélection faite vers le
haut les inverse. Il faut normaliser avec `compareDocumentPosition` avant de calculer
la plage de blocs, sinon elle est vide ou inversée une fois sur deux.

**Savoir dans quel bloc on est** : remonter de `selection.anchorNode` — un nœud texte —
au `closest('[data-element]')`.

### Le 100 % clavier, de bout en bout

La chaîne entière doit passer sans souris, et c'est à éprouver **dans cet ordre** :
entrer dans le mode → atteindre le champ → naviguer d'un bloc à l'autre → étendre une
sélection sur plusieurs blocs → vider → `Ctrl+S` → lire le compte rendu → `Échap`.

Deux exigences d'accessibilité qui ne se rattrapent pas après coup :

- **le compte rendu doit être annoncé.** `#zone-annonces` existe déjà, région live
  persistante dans `base.html`, et `annonces.js` enveloppe `Swal.fire` — « un seul
  point d'entrée couvre l'existant ET le futur ». Le `Ctrl+S` doit y passer.
- **savoir où l'on est sans regarder.** Un lecteur d'écran dans un `contenteditable`
  multi-blocs annonce du texte, pas des frontières. Chaque bloc devrait porter son
  repère — numéro, et locuteur pour une transcription. À éprouver avec un vrai lecteur
  d'écran, pas en le supposant.

### Piloter l'audio depuis le texte, au clavier

**Décidé le 23 août 2026** : depuis le mode édition, une touche lance l'écoute au
début du bloc où se trouve le curseur.

**La quasi-totalité est déjà écrite** — vérifié le 23 août :

| Brique | Où | État |
|---|---|---|
| l'instant de chaque bloc | `_blocs_elements.html:86-87` | **`data-debut` ET `data-fin`** sont posés sur `.bloc` |
| « écouter depuis ce tour » | `lecteur_audio.js:392-402` | **déjà codé**, déclenché par `.bouton-ecouter` dans la gouttière : `deplacerLaLecture(lecteur, debut)` puis `play()` |
| le suivi inverse | `lecteur_audio.js`, `elementDuTourCourant` | le tour en cours d'écoute est déjà surligné |
| le transport | `lecteur_audio.js:409` | `←` `→` ±5 s, `Début`, `Fin` |

**Ce qu'il reste à écrire est minuscule** : trouver le bloc du curseur
(`selection.anchorNode` → `closest('.bloc[data-debut]')`), lire son `data-debut`, et
appeler la fonction qui existe. Une dizaine de lignes, et **rien n'est recopié** —
c'est la règle que le lecteur applique déjà pour le bouton des cartes d'idées :
« Rien n'est recopié, donc rien ne peut diverger. »

**Deux points à vérifier au prototype, pas à supposer :**

1. **Le transport est aujourd'hui lié au focus sur le rail.**
   `lecteur_audio.js:410` : `if (!evenement.target.closest("#rail")) return;`. En mode
   édition le focus est dans le champ : les flèches n'atteindront donc pas le lecteur —
   **et c'est heureux**, elles doivent déplacer le curseur texte. Il faut décider quelles
   touches pilotent le son **depuis le champ**, et lesquelles restent au texte.
2. **`Ctrl+Espace` est pris par le système sur les deux plateformes principales** :
   changement de méthode de saisie sous Linux/GNOME (IBus), sélecteur de source de
   saisie sous macOS. Le raccourci peut donc ne jamais atteindre la page. À éprouver
   sur les deux, et à changer si besoin.

### Les trois choses qui manquent pour un vrai outil de sténo

Le reste du chemin est fait. Ces trois-là ne le sont pas, et **aucune n'apparaît dans
`lecteur_audio.js`** (vérifié par recherche le 23 août) :

1. **Le rembobinage automatique à la reprise** — *le* geste signature de la
   transcription : on met en pause pour écrire, et à la reprise le son repart **une à
   trois secondes en arrière**, parce qu'on a toujours perdu le début de la phrase.
   Aucun outil de transcription sérieux ne s'en passe. **Cinq lignes**, et c'est le
   manque le plus important des trois.
2. **La vitesse de lecture variable** (`audio.playbackRate`) — on ralentit à 0,7× un
   passage difficile, on accélère à 1,5× un passage clair. **Aucune occurrence** de
   `playbackRate` dans le code. Une propriété, deux touches, un affichage.
3. **La correction du locuteur** — le seul manque de fond, déjà décrit dans
   `2026-08-23-les-deux-gestes-manquants-de-l-edition-par-blocs.md`. Sans elle, on
   corrige le texte d'une transcription mais pas **qui parle** — or c'est la
   correction la plus fréquente après une diarisation.

**Un quatrième point, qui décide de l'usage professionnel** : la **pédale**. Les
transcripteurs pilotent le transport au pied, et un footswitch USB émet des touches
(codes média, ou `F13`–`F15` selon les modèles). Des raccourcis écrits en dur
l'excluent. Reconnaître au minimum `MediaPlayPause` coûte une ligne et ouvre l'outil
à ceux qui transcrivent pour de bon.

**Et une possibilité offerte gratuitement** : `data-fin` étant déjà posé, **répéter un
bloc en boucle** ne demande aucune donnée nouvelle. YAGNI pour l'instant, mais la
brique est là le jour où un passage résiste.

### Ce que ça ajoute aux mesures de l'option C

5. **La navigation et la sélection traversent-elles vraiment ?** Sur 210 blocs, au
   clavier seul : atteindre le dernier bloc, sélectionner du bloc 3 au bloc 8, vider.
6. **L'interception de la suppression multi-blocs tient-elle ?** Les frontières
   doivent être **exactement** les mêmes avant et après — comparaison des
   `identifiant_stable` et de leur `ordre`.
7. **Le parcours complet au clavier**, et avec un lecteur d'écran.
8. **Le pilotage audio depuis le champ** : la touche choisie atteint-elle la
   page sur Linux et sur macOS, et le son part-il bien au début du bloc où est
   le curseur — y compris juste après une correction non enregistrée ?

### Ce que le prototype compare, désormais

| | dépendance | front à écrire | back neuf | sert le nettoyage PDF | sert la transcription |
|---|---|---|---|---|---|
| **A** — clavier maison | aucune | ~300 lignes | 2 endpoints | oui | oui |
| **B** — BlockNote | bundle JS | à mesurer | 1 endpoint de diff | oui | à vérifier |
| **C** — champ unique | **aucune** | **peu** | **1 endpoint** | **très bien** | à mesurer |

**C se prototype en une journée**, contre trois pour B. Le comparer en premier coûte
peu et peut rendre les deux autres sans objet.
