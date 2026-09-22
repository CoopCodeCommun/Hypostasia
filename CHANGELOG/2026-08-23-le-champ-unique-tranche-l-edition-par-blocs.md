# Le champ unique tient, à condition que la garde vive dans `beforeinput` / The single field holds, if the guard lives in `beforeinput`

**Date :** 2026-08-23, mesures achevées le 2026-08-26
**Migration :** Non
**Code livré :** aucun **par ce chantier-ci**. C'est une décision, prise sur
mesures, et le prototype était jetable et vivait hors du dépôt — comme la note qui
le commandait l'exigeait. *(Le même soir, un autre chantier a levé le premier des
coûts nommés plus bas : `CHANGELOG/2026-08-23-un-endpoint-qui-rend-un-seul-bloc.md`.)*

## Résumé / Summary

**Quoi / What :** **C — le champ unique** est la voie retenue, et le prototype a
établi **où doit vivre son interception : dans `beforeinput`, pas dans `keydown`** —
plus une parade à la composition IME, posée sur `compositionstart`. **B —
BlockNote** est écartée, mais **par arbitrage de dépendance, pas par la mesure** :
elle n'a jamais été construite. **A — le clavier maison** reste le repli.

> **Les trois mesures qui conditionnaient cette décision sont faites, et les trois
> passent** (26 août 2026) : le **DOM réel**, **Firefox et WebKit**, et la
> **composition IME**. Le mot « à condition » du titre désigne désormais une
> exigence de mise en œuvre, plus une incertitude.
/ Option C is the path to pursue, with its guard in `beforeinput`; option B is set
aside by arbitration, not by measurement; option A remains the fallback.

**Pourquoi / Why :** deux résultats commandent tout le reste.
1. **`contenteditable="plaintext-only"` n'empêche PAS la fusion multi-blocs** —
   210 blocs deviennent 205, exactement comme sans lui. L'interception est donc
   obligatoire.
2. **Une garde par `keydown` ne suffit pas.** Elle laisse passer les trois gestes
   les plus ordinaires — remplacer une sélection en tapant, `Ctrl+X`, `Ctrl+A`
   puis frapper — et le dernier réduit **une note de 210 blocs à un seul**. La même
   garde posée sur `beforeinput` tient les trois : **210 → 210, zéro mutation**.

> **Ce document a été réécrit après deux relectures adverses.** La première a
> trouvé une contradiction interne (« le texte part en base », alors que rien
> n'était écrit) ; la seconde a trouvé que la garde mesurée ne couvrait pas le
> geste le plus courant d'un correcteur. **Les deux avaient raison** : les trous
> ont été mesurés, puis refermés, puis remesurés. Les paragraphes « Ce que ce
> prototype NE prouve PAS » sont là parce qu'elles les ont exigés.

### Où et comment cela a été mesuré / Where and how

| | |
|---|---|
| Machine | la VM 8 vCPU du projet, conteneur `hypostasia_web` |
| Navigateur | **Chromium 145.0.7632.6 headless, et lui seul**, piloté par Playwright |
| Charge | **de 1,19 à 2,92** (moyenne 1 min, 20 relevés) — une suite de tests du mainteneur a tourné pendant toute la session. **Le premier passage est à 2,02, au-dessus du seuil de 2,0 que le projet s'impose pour un banc** |
| Données | **la vraie base de dev, en lecture seule** — page 19 (210 blocs) et page 3 (la transcription, 12 blocs) |
| Écritures | **aucune conservée.** Les réconciliations d'ancres ont réellement tourné, dans des transactions **volontairement annulées** — c'est l'`atomic` qui garantit le retour en arrière. Les 40 éléments ont été relus après coup (**40 inchangés, 0 modifié**), mais cette relecture ne porte que sur `texte` et `empreinte_contenu` : elle ne dit rien des portions |
| Coût | **aucun modèle appelé, aucune facture** |

Les chiffres de taille de la spec sont **confirmés indépendamment** : page 19 =
**210 blocs**, **58 770** caractères bruts, **59 188** joints par `\n\n`.

---

## 1. Le champ tient à 59 000 caractères — largement

| | 210 blocs (58 770 car.) | 12 blocs (4 411 car.) |
|---|---|---|
| construction du DOM | **8,7 / 9,2 ms** | 3,1 / 2,7 ms |
| premier layout | **44,9 / 35,7 ms** | 8,5 / 11,2 ms |
| hauteur de la page | 14 145 px | 1 050 px |
| frappe, `keydown`→`input` médian | **6,0 / 5,6 ms** | 1,1 / 1,1 ms |
| frappe, p95 | **8,7 / 7,4 ms** | 1,8 / 2,1 ms |
| sérialisation des 210 blocs | **4,1 / 4,6 ms** | 1,0 / 0,7 ms |

**Le champ se monte en ~50 ms et coûte 6 ms par frappe** — cinq fois le coût à
12 blocs, mais **le tiers d'une trame de 16 ms**. Il n'y a pas de mur à 210 blocs.

**Chaque couple est donné dans l'ordre des deux prises : d'abord à charge 2,02,
puis à 1,39.** Elles bougent un peu — le layout passe de 44,9 à 35,7 ms, soit
−20 %. **La mesure 1 et la mesure 2 sont les seules prises deux fois** ; toutes les
autres mesures de ce document sont **une prise unique**.

## 2. Le diff par `identifiant_stable`, sur vingt gestes enchaînés

| | |
|---|---|
| blocs envoyés | **210** |
| identifiants **uniques** | **210** |
| ordre préservé | **oui** |
| identifiants **perdus / dupliqués** | **0 / 0** |
| opérations déduites | **14 `corriger`, 5 `masquer`, 191 `rien`** |
| **blocs jamais touchés revenant DIFFÉRENTS** | **0 sur 191** |

**La ligne qui compte est la dernière** : l'aller-retour DOM → sérialisation →
diff ne corrompt **aucun** des 191 blocs auxquels personne n'a touché — tableaux,
surlignages `<mark>` et sauts de ligne internes compris. La comparaison se fait
contre les textes **extraits de la base**, pas contre un état du DOM.

**La règle du § 7.2 de la spec est vérifiée par le chiffre** : comparer sur
`empreinte_du_texte()` au lieu du texte brut aurait jeté **2 corrections sur 14** —
le double espace du bloc 9 et le saut de ligne du bloc 72.

> **Découverte** : taper deux espaces dans un `contenteditable` n'insère pas deux
> espaces mais la séquence **`\xa0 \xa0`** — des U+00A0. Le texte qui *partirait*
> en base porterait donc des insécables. La comparaison brute le voit ; la
> normalisée non.

**Ce que ce chiffre ne prouve PAS.** L'attribution par geste et le POST viennent
**du même sérialiseur** : la confrontation « 0 faux positif / 0 faux négatif »
mesure surtout la cohérence de l'instrument. Et le banc en porte la preuve : le
geste n° 8, intitulé « collage dans le bloc 30 », a en réalité collé **dans le
bloc 20** — le curseur y était resté — et **rien ne l'a signalé**. Un oracle
indépendant (les textes attendus, calculés en Python depuis la liste des gestes)
reste à écrire.

## 3. La garde : `keydown` ne suffit pas, `beforeinput` tient

**C'est le résultat central de ce prototype.** Trois gestes ordinaires, sur une
sélection allant du bloc 20 au bloc 25 :

| Geste | navigateur nu | garde `keydown` | garde **`beforeinput`** |
|---|---|---|---|
| **taper une lettre** sur la sélection | 210 → **205** | 210 → **205** | **210 → 210**, 0 mutation |
| **`Ctrl+X`** sur la sélection | 210 → **205** | 210 → **205** | **210 → 210** |
| **`Ctrl+A` puis taper** | 210 → **1** | 210 → **1** | **210 → 210**, 210 gouttières |
| `Suppr` / `Retour arrière` | 210 → 205 | 210 → 210 | 210 → 210 |
| suppression traversant des **puces** | 210 → **207** | 210 → 210 | 210 → 210 |

*(Le compte de mutations n'a été relevé que pour la frappe de remplacement et la
suppression traversant des puces ; pour `Ctrl+X` et `Ctrl+A`, seule la signature de
structure a été comparée — elle est identique.)*

**Une garde par `keydown` protège donc exactement les touches auxquelles on a
pensé, et rien d'autre.** `beforeinput` voit le geste, pas la touche : il porte le
type (`insertText`, `deleteByCut`, `insertFromPaste`…) et `getTargetRanges()` dit
**quelle plage va être touchée**, ce que la sélection ne dit pas toujours.

Et il a un second mérite, mesuré : il laisse passer nativement la frappe qui **ne
traverse pas**, donc la frappe ordinaire garde son coût et son comportement natifs.

### Le collage, et le piège de `getTargetRanges()`

**Une garde `beforeinput` ne suffit pas seule au collage.** Elle laisse passer
nativement ce qui **ne traverse pas** — c'est ce qui préserve la frappe ordinaire —
et un collage de HTML riche **dans un seul bloc** en profite. Mesuré, vrai
presse-papier et vrai `Ctrl+V`, sous la garde `beforeinput` :

| | collage **dans un bloc** | collage **traversant** |
|---|---|---|
| `contenteditable="true"` | **4 enfants, `<h1>`, `<b>`, `<i>` survivent** | 210 blocs, 1 enfant, aucun style |
| `contenteditable="plaintext-only"` | 210 blocs, 1 enfant, aucun style | 210 blocs, 1 enfant, aucun style |

**`plaintext-only` n'est donc pas une redondance : c'est lui qui tient le collage
non traversant, et la garde qui tient le traversant.** Les deux sont
complémentaires — mais les combiner exige de connaître le piège suivant.

> ### ⚠️ Sous `plaintext-only`, `getTargetRanges()` rend une LISTE VIDE
>
> Mesuré sur Chromium 145, sur une sélection couvrant les blocs 14 à 16, pour
> **`insertText`, `insertFromPaste` ET `deleteContentForward`** :
>
> | | `getTargetRanges()` | `window.getSelection()` |
> |---|---|---|
> | `contenteditable="true"` | bloc 14 → 16, **traverse** | bloc 14 → 16, traverse |
> | `contenteditable="plaintext-only"` | **vide — aucune plage** | bloc 14 → 16, traverse |
>
> Une garde qui ne s'appuie que sur `getTargetRanges()` est donc **aveugle sous
> `plaintext-only`** : elle croit que rien ne traverse et laisse tout passer. La
> première version de la garde le faisait, et un collage traversant y **détruisait
> un bloc** (210 → 209) — alors que la même garde tient sous `true`.
>
> **Le remède est d'une ligne, et il est mesuré** : quand `getTargetRanges()` est
> vide, retomber sur `window.getSelection()`. Avec ce repli, les quatre cas du
> tableau ci-dessus tiennent, et les quatre gestes du tableau précédent restent à
> **210 → 210**.

### Ce que la garde `beforeinput` ne peut PAS empêcher

**`insertCompositionText` n'est pas annulable** — mesuré : `cancelable: false`.
Une **composition IME** (saisie accentuée, japonais, et **sur Android toute
frappe**) qui remplace une sélection multi-blocs détruit **5 blocs sur 210, garde
comprise**. La garde le détecte et le nomme ; elle ne l'arrête pas.

*Piste non mesurée* : normaliser la sélection dès `compositionstart` — vider
soi-même bloc par bloc avant que la composition ne s'applique. **À éprouver.**

Hors composition, l'IME est inoffensif : une composition ordinaire dans un seul
bloc rend le texte exact, **0 mutation**, avec ou sans garde.

### Les autres gestes qui créent des nœuds

| Geste | Sans garde | Avec la garde |
|---|---|---|
| `Entrée` au milieu d'un bloc | le `<p>` est **scindé en deux `<p>` portant le même identifiant** | `\n` inséré dans le texte, 0 mutation |
| **collage réel** (vrai presse-papier, vrai `Ctrl+V`) | 3 nœuds créés — `<h1>`, `<p><b>`, `<p>` — **le gras survit** | voir le tableau ci-dessous : cela dépend du `contenteditable` |
| glisser-déposer **multi-blocs** | **l'ordre des blocs est permuté**, 10 mutations, 7 blocs abîmés | frontières intactes, mais **le texte est retiré de la source sans être déposé** |
| correcteur orthographique | non déclenchable en headless | `spellcheck` vaut **`true`** sur le champ. Son type d'entrée est `insertReplacementText`, que `beforeinput` porte — **mais cela n'a PAS été mesuré ici**, faute de pouvoir déclencher le correcteur |
| `Ctrl+Z` | — | la frappe ordinaire s'annule ; **dès qu'une interception écrit, plus rien** |

**Le glisser-déposer doit être REFUSÉ à la source** (`preventDefault` sur
`dragstart`) : au moment du `drop`, la sélection est encore celle de l'origine, et
la « garde » réinsère donc au mauvais endroit. C'est écrit dans la garde 2 mais
**non mesuré** — et cela ne couvrira pas un dépôt venu d'une autre fenêtre.

**L'annulation native est morte** dès qu'une interception écrit dans le DOM — dans
les deux gardes. `document.execCommand` ne la ressuscite qu'à moitié : **un seul
`Ctrl+Z` ne défait qu'une des six opérations** d'une suppression de six blocs (un
seul `Ctrl+Z` a été mesuré ; qu'il en faille exactement six est une déduction, pas
une mesure). Il **n'insère aucun `\n`**, et il produit 2 mutations là où l'écriture
directe en produit 0. **Une annulation applicative est donc à écrire.**

## 4. Les ancres — la mesure pré-enregistrée, et elle est rassurante

C'était le critère éliminatoire de la note, et le premier passage ne l'avait pas
pris. Il l'est maintenant : `reconcilier_les_portions_de_l_element` a été appelée
**pour de vrai** sur 40 éléments porteurs de la page 19, dans des transactions
annulées.

**Un témoin d'abord**, pour savoir ce que la réconciliation fait toute seule :

| Correction | exactes | retrouvées | **détachées** |
|---|---|---|---|
| texte **identique** | — | — | **0** (la fonction ne fait rien) |
| une lettre **à la fin** | 59 | 0 | **0** |
| une lettre **au début** | 0 | 59 | **0** |

**La réconciliation est robuste** : elle repositionne tout ce qui est décalé.

**Et la règle du détachement est exacte** :

| | frappe au milieu | correction de casse |
|---|---|---|
| portions **enjambant** le point d'édition, détachées | **22 / 22** | **22 / 22** |
| portions **hors de la plage**, détachées | **0 / 37** | **0 / 37** |

> **Un artefact du banc, à connaître avant de relire les totaux.** Le genre
> « correction de casse » compte **56** portions là où les autres en comptent 59 :
> deux des 26 éléments commencent par une **espace**, où `swapcase()` ne change
> rien — la réconciliation retourne alors immédiatement, et leurs 3 portions ne
> sont jamais comptées. Même chose pour la troncature (58 au lieu de 59 : un
> élément fait exactement 15 caractères). Le taux du genre casse est donc
> **39,3 % (22/56)**, pas 37 %. La conclusion, elle, ne bouge pas.

**Seules se détachent les portions que l'édition traverse. Aucune autre.** Le taux
global (22 sur 59, 37 %) ne mesure donc pas la fragilité du champ unique : il
mesure **combien de passages ancrés couvrent le milieu de leur bloc** dans ce
corpus. **Et il est le même pour les trois voies** — toutes appellent la même
fonction serveur.

Deux chiffres durs, eux aussi indépendants de la voie :

- **14 éléments sur 40 (35 %) sont refusés d'emblée** : une synthèse figée les
  cite. La spec annonçait 30 % des porteurs ; c'est confirmé.
- **tronquer un bloc détache 100 % de ses portions** (58 sur 58). Attention au
  raccourci : ce chiffre passe par la **réconciliation** (tronquer, c'est corriger),
  et un détachement par cette voie **n'a aucun chemin de rattachement** —
  `reconciliation.py` le dit : « Un re-attachement volontaire, si on l'ajoute un
  jour… ». La réversibilité de `masquer`/`demasquer` est un **autre** chemin, celui
  du **vidage**, et `demasquer` ne restaure que « si le texte n'a pas changé » — ce
  qui n'est jamais vrai d'une troncature. **Le compte rendu doit donc le dire, et
  le mot « réversible » ne s'applique pas ici.**

## 5. Les surlignages d'ancrage survivent à l'édition

Les `<mark class="portion">` vivent **dans** la zone éditable.

| Geste | texte exact ? | la marque |
|---|---|---|
| frappe **dans** la marque | **oui** | conservée, la frappe entre dedans |
| frappe sur sa frontière **gauche** | **oui** | conservée, la frappe reste dehors |
| frappe sur sa frontière **droite** | **oui** | conservée, la frappe entre dedans |
| suppression couvrant la marque | **oui** | supprimée, comme il se doit |
| suppression multi-blocs | — | **2 détruites, exactement les 2 de la plage** ; les 57 autres intactes |

**Le texte sérialisé est exact dans les quatre cas où il a été comparé** — c'est la
seule chose qui compte, un texte faux donnant des offsets faux. Le cinquième, la
suppression multi-blocs, n'a été mesuré que sur le **compte des marques**.

## 6. Le parcours clavier passe ; le lecteur d'écran n'a PAS été éprouvé

`Tab` atteint le champ · `↑` `↓` traversent les blocs · `Maj+↓` étend à travers ·
`Ctrl+Fin` va au dernier bloc · `Ctrl+S` intercepté et annoncé dans
`#zone-annonces` · **la gouttière n'entre pas dans la sélection**.

Ce dernier point tient à `user-select: none`, que le vrai CSS porte déjà sur
`#readability-content .gouttiere` (`maquette.css:1784`) — le prototype en a sa
propre copie, donc **le comportement se transposera, mais il n'a pas été mesuré
sur le vrai CSS**.

**L'arbre d'accessibilité** (Chromium, 12 blocs, **une seule prise**) : 177 nœuds,
le champ est un `textbox` nommé, et le numéro de bloc comme le locuteur sont
exposés — **en `StaticText` À L'INTÉRIEUR du textbox**. Un lecteur d'écran les lira
donc dans le flux du texte. Utile (« savoir où l'on est ») ou bruyant : **cela ne
se tranche pas sur un arbre d'accessibilité.** Et dans l'application, `numero-element`
est en `display:none` hors mode structure — la gouttière réelle n'expose donc pas
la même chose que celle du prototype.

> ⚠️ **Aucun lecteur d'écran réel n'a été essayé** : cette machine n'a pas de
> session graphique. L'exigence du § 9 de la spec **reste entière**.

## 7. `contenteditable="plaintext-only"` : accepté ici, et insuffisant

**Sur Chromium 145 : accepté** — la propriété relue vaut bien `plaintext-only`. Il
empêche seul la scission du `<p>` par `Entrée` (0 mutation contre 1) et nettoie le
collage.

**Mais il n'empêche pas la fusion multi-blocs** : `210 → 205`, cinq blocs détruits,
**exactement comme `contenteditable="true"`**. L'interception reste donc obligatoire.

**En revanche, il n'est PAS redondant, et cette phrase a dû être réécrite.** Une
première version de ce document en faisait « une ceinture par-dessus les
bretelles ». La mesure dit l'inverse : c'est `plaintext-only` qui tient le
**collage non traversant**, que la garde laisse passer par construction. Les deux se
répartissent le travail — et leur combinaison exige le repli sur la sélection décrit
au § 3, faute de quoi elle est **pire** que la garde seule.

**Son support ailleurs redevient donc un critère.** Firefox et WebKit **n'ont pas pu
être lancés** ici : les moteurs se téléchargent, mais leurs dépendances système
manquent à l'image (`libgtk-3-0t64`), et une suite de tests du mainteneur tournait
dans ce conteneur — je n'y ai pas installé de paquet.

---

## La décision

**C est la voie retenue, et son interception vit dans `beforeinput`** — avec une
parade sur `compositionstart`, sans laquelle une composition IME détruit des blocs
que rien d'autre n'arrête. Elle tient **les trois mesures qui la conditionnaient**,
sur **trois moteurs**, sur le **DOM réel**, et n'ajoute **aucune dépendance** — mais
son front est **plus grand que la note ne l'annonçait**.

**B est écartée — par arbitrage, pas par la mesure.** Il faut le dire ainsi, parce
que c'est vrai : **B n'a jamais été construite, son bundle n'a jamais été pesé, et
le seuil que la note voulait fixer « avant de mesurer » ne l'a pas été.** L'écarter
reste défendable — un bundle figé dans `vendor/` reproduirait le piège du build
Tailwind, et les gestes structurels qu'elle offre sont précisément ceux que ce mode
interdit. **Mais l'honnêteté oblige à noter que ce prototype a renforcé son
dossier sur trois points** : l'annulation propre, l'interception par `beforeinput`
et la resynchronisation après une composition IME non annulable sont exactement ce
que ProseMirror — donc BlockNote — fournit. Si les coûts ci-dessous enflent, **B
redevient candidate**, et il faudra alors peser son bundle avant d'en reparler.

**A reste le repli.** Elle n'a pas été éliminée : elle fait autre chose —
sélectionner des blocs *entiers*, et garder `scinder`/`fusionner` au clavier. C
couvre son usage de lot, mesuré. Et **A a un avantage que C n'a pas** : son rayon
de dégât. Sous C, une session couvre la note entière — un `lectureReload` déclenché
par le `masquer` d'un collègue, ou le refus total du § 8.1, efface **tout** le
travail ; sous A, on ne perdrait que le bloc en cours.

### Les six coûts à accepter avant d'écrire une ligne

1. ~~**`identifiant_stable` n'est nulle part dans le DOM.**~~ **LEVÉ le 23 août au
   soir**, dans la foulée de cette décision : chaque bloc porte désormais
   `data-element="<identifiant_stable>"` et `id="bloc-<identifiant_stable>"`.
   → `CHANGELOG/2026-08-23-un-endpoint-qui-rend-un-seul-bloc.md`
2. **Une annulation applicative est à écrire.** Sans elle, vider quatre blocs par
   erreur ne se rattrape que par `demasquer`, après enregistrement.
3. **L'interception vit dans `beforeinput`**, et le glisser-déposer se refuse à la
   source. La composition IME multi-blocs reste un trou ouvert.
4. **L'`Entrée` reste invisible** sur les blocs non-`pre` tant que le CSS n'a pas
   de `white-space: pre-line` : `#readability-content .bloc > .corps`
   (`maquette.css:1763-1772`) n'en porte aucun. Le `\n` survit à la sérialisation
   et au diff — c'est mesuré ; **il ne se voit pas**. *(La spec chiffre à 1 107 sur
   1 129 les blocs concernés ; ce compte n'exclut explicitement que les 2 `code`,
   l'exclusion des 20 `table` y est implicite.)*
5. **Les 58 éléments non textuels ne sont pas éditables tels quels** — **20
   `table`, 19 `caption`, 17 `picture`, 2 `code`, vérifiés en base. Aucun chemin
   HTML→markdown n'existe dans le dépôt**, et le `<table>` affiché est construit
   *après* le marquage (`rendu_elements.py:669-680`). Le prototype a édité un
   `table` **comme du texte** — ce que l'application ne sait pas relire. **Lecture
   seule dans le mode**, ou le mode leur ment.
6. **Les insécables.** Une correction d'espaces produit des U+00A0 qui partiront en
   base. Leur effet sur la réconciliation est **nul** (mesuré : même détachement
   qu'une frappe ordinaire) ; leur effet sur les chunks envoyés au LLM, la
   recherche et les exports **n'est pas tranché**.

### Ce que ce prototype NE prouve PAS

- **Il n'a pas tourné sur le DOM réel.** Il reproduit la structure du gabarit —
  `.bloc > .gouttiere + .filet-etat + .corps` — mais pas ses **blancs de template**
  (le vrai `.corps` contient l'indentation Django : sérialiser son `textContent`
  rendrait les 210 blocs différents **avant tout geste** — la sérialisation devra
  lire l'élément interne). Il n'a **jamais** rendu les quatre boutons de
  `_actions_element.html` *dans* le `<p>` (l'option existe dans le prototype, aucune
  mesure ne l'a activée), ni les placeholders `.element-masque`, ni les
  `avertissement-plafond`, qui vivent **entre** les blocs, donc dans le futur champ.
- **Un seul moteur.** La promesse fondatrice de C — la sélection qui **traverse**
  des îlots `contenteditable="false"` — n'est mesurée que sur Chromium. C'est
  précisément là que les moteurs divergent.
- **La sentinelle est aveugle sous le corps.** Une `Entrée` nue dans une puce scinde
  le `<li>` **dans** le `<ul>` : ni le compte des blocs ni la signature de structure
  ne le voient.
- **Le serveur n'a pas été traversé.** `corriger_en_lot` n'existe pas (zéro
  occurrence). Aucun POST n'a été reçu, aucun verrou éprouvé, aucun refus concurrent,
  aucune borne de lot.
- **La mesure 8 de la note — le pilotage audio depuis le champ — n'a pas été
  prise du tout.**

### ✅ Mesure faite le 26 août 2026 — le DOM RÉEL

C'était la deuxième des trois. **Elle passe**, et elle tranche deux questions que
la réplique ne pouvait pas trancher.

**Le banc** : la vraie page servie par Django, ouverte dans Chromium, la garde
`beforeinput` **injectée dedans**, et les mêmes gestes rejoués. Aucune écriture — la
garde ne touche que le DOM.

**1. Le contrat de sérialisation du § 7.1 est vérifié par le chiffre.** Sur la
page 21 (**189 blocs**, connecté en écriture, donc **189 boutons d'action rendus
DANS le `<p>`**) :

| Ce qu'on lit | exacts | différents |
|---|---|---|
| `.corps.textContent` | **0** | **189** |
| l'**élément interne**, `.actions-element` retiré | **189** | **0** |

Le premier rend `"\n    \n        Traductions de cet article\n    corriger\n    co…"` :
les blancs d'indentation Django **et** le mot « corriger » des boutons. **Sérialiser
le `.corps` ferait voir 189 blocs modifiés avant le moindre geste** — donc 189
réconciliations sur des blocs que personne n'a touchés. Lire l'élément interne, lui,
boucle **exactement**.

**2. Les 58 éléments non textuels : le compte est exact, et ce sont les tables.**
Sur la page 19 (210 blocs) : **202 bouclent exactement, 8 échouent — et ces 8 sont
les 8 `table`, rien d'autre.** Le `<table>` affiché est construit depuis le markdown
et aucun chemin ne le relit. Le coût n° 5 est donc confirmé par la mesure : **ces
éléments sont en lecture seule dans le mode, ou le mode leur ment.**

**3. Les gestes tiennent sur le vrai DOM** — celui qui porte aussi les gouttières à
boutons, les `<ul><li>`, les figures et les légendes :

| Geste, sur 189 blocs | frontières | mutations | erreurs JS |
|---|---|---|---|
| frappe de remplacement du bloc 20 au 25 | **189 → 189** | — | 0 |
| `Ctrl+A` puis frapper | **189 → 189**, 189 gouttières | — | 0 |
| `Suppr` du bloc 20 au 25 | **189 → 189** | **0** | 0 |

> **Un piège de mesure, et il a failli passer.** Le premier passage de ce banc a
> mesuré la page **en anonyme sans le dire** : la connexion avait échoué en silence
> (mot de passe valable pour `jonas` seulement), et `boutons_d_action_presents`
> valait **0** — c'est-à-dire que le banc « éprouvait » le piège des boutons sur un
> DOM qui n'en avait aucun. Le banc **vérifie désormais le cookie de session et
> s'arrête sans lui**.

**Ce que ce banc n'a toujours pas vu** : un `.element-masque` et un
`avertissement-plafond` **dans le flux** — aucun élément masqué n'existe en base, et
aucune des deux notes n'a atteint le plafond de surlignage.

### ✅ Mesure faite le 26 août 2026 — FIREFOX ET WEBKIT

C'était la première des trois, et la plus lourde de conséquences : **la promesse
fondatrice de C n'avait été mesurée que sur un moteur.** Elle est faite, sur les
trois, et **elle passe**.

*(Il a suffi d'installer `libgtk-3-0t64` dans le conteneur — décidé par le
mainteneur le 26 août. Les binaires Firefox et WebKit y étaient déjà : seules les
dépendances système manquaient, et `HOME=/app`, pas `/home/hypostasia`.)*

**La promesse fondatrice — la sélection qui traverse les gouttières
`contenteditable="false"` — tient partout :**

| | Chromium 145 | Firefox 146 | WebKit 26 |
|---|---|---|---|
| `↓` traverse les blocs | ✅ | ✅ | ✅ |
| `Maj+↓` étend à travers | ✅ | ✅ | ✅ |
| `Ctrl+Fin` va au dernier bloc | ✅ | ✅ | ✅ |
| `plaintext-only` accepté | ✅ | ✅ | ✅ |

**Et la garde `beforeinput` tient sur les trois** — sélection étendue **au clavier**
(`Maj+↓` ×12) puis `Suppr`, ce qui est le chemin réel :

| | avec la garde | sans la garde |
|---|---|---|
| Chromium | **210 blocs, 210 gouttières, textes intacts** | 210 → **206**, gouttières abîmées |
| Firefox | **210, 210, intacts** | 210 → **209**, abîmées |
| WebKit | **210, 210, intacts** | 210 → **209**, abîmées |

**Le piège de `getTargetRanges()` est PROPRE À CHROMIUM.** Sous `plaintext-only`,
il rend **0 plage** sur Chromium, et **1 plage** sur Firefox comme sur WebKit —
alors que la sélection traverse trois blocs partout. Le repli sur
`window.getSelection()` reste donc **nécessaire** (sans lui, Chromium détruit un
bloc) et **inoffensif ailleurs**.

**Une divergence WebKit, à nommer.** Sur WebKit, le repère de la gouttière (`#5`)
**entre dans `selection.toString()`** quand la sélection est étendue au clavier —
pas sur Firefox, pas sur Chromium, et pas non plus sur WebKit avec une plage posée
par programme. `user-select: none` ne l'en empêche pas.

**Ce n'est pas éliminatoire, et c'est mesuré** : la garde protège quand même, les
210 textes de gouttière sont **intacts** après le geste. Mais un **copier** depuis
Safari emporterait « #5 » avec le texte. C'est un défaut de copie, pas de
correction — à traiter le jour où le mode existera, pas avant.

### ✅ Mesure faite le 26 août 2026 — LA COMPOSITION IME, et sa parade

La dernière des trois, et la seule qui décrivait un dégât que **rien** n'arrêtait.
**Elle passe, et la parade est éprouvée.**

**Le problème, remesuré** : `insertCompositionText` arrive avec
`cancelable: false`. La garde le **voit** passer et ne peut rien en faire.

**La parade** : ne pas essayer d'arrêter la composition, mais **lui retirer sa
matière**. `compositionstart` arrive **avant** toute écriture, et la sélection y est
encore celle de l'utilisateur : on vide bloc par bloc et on replie le curseur dans un
seul bloc. La composition n'a plus qu'un bloc devant elle.

**Vraie composition IME**, déclenchée par CDP (`Input.imeSetComposition` puis
`Input.insertText`), sur une sélection allant du bloc 20 au bloc 25 :

| | sans la parade | avec la parade |
|---|---|---|
| blocs | 210 → **205** | **210 → 210** |
| gouttières | 210 → **205** | **210 → 210** |
| bloc 20 après | `"Portion argumen日本venement argument principe…"` — **la queue du bloc 25 recollée à la tête du 20** | `"Portion argumen日本"` |
| le texte composé arrive | oui | oui |
| geste non annulable signalé | `insertCompositionText` | **aucun** |

Avec la parade, le geste non annulable **n'a plus lieu d'être** : la sélection ne
traverse plus au moment où la composition démarre.

**Sur les trois moteurs**, le gestionnaire s'arme et normalise — `compositionstart`
atteint, sélection normalisée, frontières identiques, blocs 21 à 24 vidés :
Chromium 145 ✅, Firefox 146 ✅, WebKit 26 ✅.

> ⚠️ **Ce que ce banc ne peut pas faire.** Une **vraie** composition ne se déclenche
> que par CDP, donc **sur Chromium seulement** — Playwright n'expose pas
> d'équivalent pour Firefox ni WebKit. Sur ces deux-là, seuls des événements de
> composition **synthétiques** ont été employés : ils prouvent que le gestionnaire
> est atteint et qu'il normalise, **pas** que le chemin natif de leur IME se
> comporte comme celui de Chromium. **Et le cas qui compte vraiment — Android, où
> toute frappe est une composition — n'est pas éprouvé ici** : il demande un vrai
> appareil.

### Les mesures qui restaient : aucune

**Les trois mesures qui conditionnaient la décision sont faites, et les trois
passent.** Ce qui reste n'est plus une condition, c'est un reste à faire :

1. **Éprouver la composition sur un vrai appareil Android**, où toute frappe est une
   composition. La parade y est plausible, pas mesurée.
2. **Le lecteur d'écran réel** — l'exigence du § 9 de la spec, jamais levée.
3. **Peser le bundle de BlockNote**, si l'on veut un jour comparer B autrement que
   par arbitrage.

---

## Où vit le prototype, désormais

Il devait être jetable, et il l'est resté — mais il est **gardé**, à la demande du
mainteneur, en deux endroits et sans le texte d'autrui :

| Où | Quoi |
|---|---|
| `front/static/front/maquettes/prototype-champ-unique/` | **ce qui s'ouvre au navigateur** — `index.html`, et les modes `?garde=0/1/2`, `&ce=plaintext-only`, `&page=3` |
| `benchmarks/edition_par_blocs/` | les bancs (**24 fichiers, dont 16 pilotent un navigateur**) et les **27 JSON** de résultats, avec le README qui dit comment les rejouer — comptés le 29 août |

⚠️ **Ce n'est pas un étalon**, et le dit en tête de sa page : les autres fichiers de
`maquettes/` sont la référence à laquelle le code s'aligne ; celui-ci est un
prototype de décision qu'on garde pour pouvoir le remanipuler.

**Les données livrées sont SYNTHÉTIQUES** — même forme que le corpus réel (210
blocs, `{text: 116, section_header: 43, list_item: 41, table: 8, caption: 2}`, les
8 tableaux à saut de ligne, 5 locuteurs), texte fabriqué, à **−3,2 %** du volume.
La page 19 qui a servi aux mesures appartient à `thales` : son texte n'a pas sa
place dans l'historique du dépôt. Pour la même raison, les champs `post` et
`initiaux` de `resultats-2.json` en ont été retirés — ils portaient les 58 770
caractères de l'article.

**Vérifié tel que servi** (24 août 2026, Chromium par Playwright depuis le
conteneur) : zéro erreur JavaScript, et le geste décisif se comporte comme décrit —
sélection du bloc 20 au bloc 25 puis une lettre donne **205 blocs en `garde=0` et
en `garde=1`**, et **210 en `garde=2`**.

---

## Comment tester (à la main) / Manual test

**Rien n'est livré : il n'y a pas d'écran à ouvrir.** Ce qui se vérifie, c'est la
mesure — et elle se refait.

### Refaire le banc

Le prototype **était** jetable et hors dépôt ; il a été **gardé** à la demande du
mainteneur (voir « Où vit le prototype, désormais » plus haut) et vit maintenant
dans `front/static/front/maquettes/prototype-champ-unique/`. Pour le reconstruire
de zéro :

1. extraire en **lecture seule** les blocs de la page 19 et de la page 3
   (`identifiant_stable`, `ordre`, `label`, `texte`, `provenance`) ;
2. rendre chaque bloc dans la structure **réelle** du gabarit —
   `.bloc > .gouttiere + .filet-etat + .corps > <p|h2|ul>ul>li</ul>|…` — et non dans
   une structure plate : **c'est ce détail qui fait la mesure**, une sélection du
   bloc 3 au bloc 8 traverse forcément les gouttières de 4 à 8 ;
3. poser `contenteditable` sur le **conteneur**, `contenteditable="false"` sur les
   gouttières ;
4. instrumenter par un `MutationObserver` **et** par une signature de structure
   relevée avant/après — `identifiant_stable | ordre | balises du corps` — et
   **descendre jusqu'aux enfants du corps**, sans quoi la scission d'un `<li>` est
   invisible ;
5. piloter par Playwright, en comparant `?garde=0` (navigateur nu), `?garde=1`
   (`keydown`) et `?garde=2` (`beforeinput`).

### Les quatre pièges de méthode, payés dans cette session

- **Un `ClipboardEvent` ou un `DragEvent` construits en JavaScript ne déclenchent
  AUCUNE action par défaut.** Le premier banc « mesurait » un collage sans garde qui
  ne collait rien, et concluait « aucun dégât ». Il faut le vrai presse-papier
  (`navigator.clipboard.write` + permissions, puis un vrai `Ctrl+V`) et la vraie
  souris.
- **Compter les blocs ne suffit pas.** Sur l'`Entrée` sans garde, leur nombre ne
  bouge pas : c'est le `<p>` *dans* le bloc qui se scinde, et les deux moitiés
  portent **le même identifiant**.
- **N'éprouver que les touches auxquelles on a pensé donne une garde qui ne protège
  que celles-là.** Le geste le plus courant d'un correcteur — taper sur une
  sélection — n'était pas dans les vingt premiers gestes, et il détruisait cinq
  blocs.
- **Un instrument qui se vérifie lui-même ne prouve rien.** L'attribution par geste
  et le POST venaient du même sérialiseur ; un collage tombé dans le mauvais bloc
  n'a déclenché aucune alarme.

### Vérifications en base (aucune écriture)

```bash
docker exec hypostasia_web python manage.py shell -c "
from django.db.models import Count, Sum
from django.db.models.functions import Length
from core.models import ElementDocument
print(ElementDocument.objects.values('page_id').annotate(
    n=Count('id'), c=Sum(Length('texte'))).order_by('-n')[:3])
print(dict(ElementDocument.objects.values_list('label').annotate(n=Count('id'))))
"
```
→ page 19 en tête, **210 blocs, 58 770 caractères** — vrai le 23 août **et encore le
29**.

⚠️ **Les comptes GLOBAUX de ce document sont datés du 23 août et ont bougé depuis.**
La base portait alors 1 129 éléments, dont 58 non textuels (20 `table`, 19
`caption`, 17 `picture`, 2 `code`). Remesurée le **29 août** : **1 398 éléments**,
dont **76 non textuels** (20 `table`, 27 `caption`, 25 `picture`, 4 `code`) — des
ingestions postérieures. **Le raisonnement ne change pas** (les `table` ne bouclent
toujours pas), mais ne recopiez pas ces comptes sans les remesurer.
