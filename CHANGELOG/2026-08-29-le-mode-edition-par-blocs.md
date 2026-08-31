# Le mode d'édition par blocs / The block editing mode

**Date :** 2026-08-29, complété le 2026-08-30
**Migration :** Non

## Résumé / Summary

**Quoi / What :** un bouton « Éditer le texte » ouvre un mode où **tout le texte de
la note devient modifiable d'un coup**, les blocs restant des blocs. `Ctrl+S`
enregistre par l'endpoint de lot, `Ctrl+Z` annule un geste, `Échap` sort.
/ A mode where the whole note becomes editable at once, blocks staying blocks.

**Pourquoi / Why :** c'est l'aboutissement de la décision du 23 août — l'option C,
le champ unique. Le back était livré depuis le 24 (le swap ciblé, l'endpoint de
lot) ; **aucun front ne l'appelait**. Les trois mesures qui conditionnaient la voie
sont passées les 26 et 28, et l'obstacle de l'écouteur `Échap` a été levé le 29.

---

## Ce que le mode fait, et ce qu'il REFUSE de faire

**On édite le TEXTE d'un bloc. On n'édite jamais son DÉCOUPAGE** — ni fusion, ni
scission (§ 3 de la spec). C'est ce renoncement qui rend le mode tenable : il
désamorce le piège du `contenteditable` multi-enfants, qui est la raison d'être de
ProseMirror et de BlockNote.

**La configuration est celle que le prototype a éprouvée**, et ses quatre pièces
sont toutes nécessaires — chacune couvre ce que les autres laissent passer :

| La pièce | Ce qu'elle tient, et pourquoi elle ne suffit pas seule |
|---|---|
| `contenteditable="plaintext-only"` | le collage **non traversant** — mais il **n'empêche pas** la fusion multi-blocs (210 → 205) |
| la garde sur **`beforeinput`** | tous les gestes **traversants** — sur `keydown`, `Ctrl+A` puis une frappe réduisait la note à **un seul bloc** |
| le **repli sur la sélection** | `getTargetRanges()` rend une liste **vide** sous `plaintext-only` **sur Chromium** : sans lui la garde y est aveugle |
| la parade sur **`compositionstart`** | `insertCompositionText` **n'est pas annulable** : sans elle une composition IME multi-blocs détruit 5 blocs |

## Deux défauts trouvés en branchant, que le prototype ne pouvait pas montrer

Le prototype rendait ses blocs lui-même. Le vrai gabarit a un `.corps` qui **contient**
l'élément interne — et c'est cet écart qui a livré deux bugs, tous deux mesurés :

**1. Le texte tapé au bord d'un bloc tombait À CÔTÉ du texte.** Un curseur posé à la
fin de `.corps` est **après** le `<p>` : ce qu'on y tape devient un nœud texte frère,
hors du texte du bloc. Mesuré : « CORRIGE » tapé ainsi n'arrivait **jamais** au
serveur, et le compte rendu annonçait « 0 modifié » sans que rien ne le signale.
→ **Tout se résout désormais sur l'élément interne**, jamais sur `.corps`, et le
guard ne laisse passer nativement que si **les deux bornes sont dans du texte de
bloc**.

**2. `closest()` remonte, il ne descend pas.** Un point posé sur `.corps` ne résolvait
vers **aucun** élément interne : la garde croyait le geste « hors de tout bloc ».
→ Un point dans le bloc mais à côté du texte est **rattaché** à l'élément interne de
ce bloc.

**Et un troisième, dans la foulée** : ramener une borne hors-texte à une constante
faisait que « tout sélectionner dans un bloc puis `Suppr` » ne supprimait **rien**.
Les bornes se calculent maintenant par **comparaison de positions**
(`compareBoundaryPoints`), pas par un repli arbitraire.

## Ce qui est vérifié, et sur quoi

**Sur les trois moteurs**, sur la vraie page (189 blocs, boutons d'action compris) :

| | Chromium 145 | Firefox 146 | WebKit 26 |
|---|---|---|---|
| le mode s'ouvre, `plaintext-only`, gouttières hors du champ | ✅ | ✅ | ✅ |
| frappe de remplacement du bloc 20 au 25 | **189 blocs** | **189** | **189** |
| `Ctrl+A` puis frapper | **189 blocs, 189 gouttières** | **189 / 189** | **189 / 189** |
| `Ctrl+Z` rend le geste | ✅ | ✅ | ✅ |
| `Échap` sort du mode | ✅ | ✅ | ✅ |
| erreurs JavaScript | **0** | **0** | **0** |

**Et `Ctrl+S` de bout en bout**, sur une note **jetable créée puis supprimée** — les
notes réelles portent des ancrages qu'une fausse manœuvre détacherait :

| | |
|---|---|
| corriger un bloc, vider un autre, `Ctrl+S` | **1 modifié, 1 masqué, 0 refusé** |
| en base | le texte corrigé est écrit ; **le bloc vidé est `masque=True` et son texte est PRÉSERVÉ** |
| le troisième bloc | **intact** |
| le compte rendu | affiché, `role="status"`, annoncé |

## Les décisions de conduite, et leur raison

- **L'entrée est une classe + `aria-pressed`**, comme le mode structure voisin. Le
  mode n'est pas un écran : il n'a pas d'adresse. *(Décision du mainteneur ; le § 2
  de la spec laissait le choix ouvert.)*
- **Le bouton est DÉSACTIVÉ pendant une analyse, et il dit pourquoi** (§ 8.1). Le
  refus existe aussi à l'écriture — le lot entier est alors annulé — mais un refus
  qui arrive après vingt minutes de frappe est le pire des deux mondes.
- **La garde d'entrée passe par un FILTRE de gabarit**, pas par une variable de
  contexte : `lecture_principale.html` est rendu depuis **trois** endroits, et une
  variable oubliée dans l'un d'eux vaudrait « faux » — donc un bouton actif pendant
  une analyse, sans que rien ne le signale.
- **`Échap` sort du mode au rang 4.6**, le dernier avant la désélection : le mode est
  un **état**, pas un panneau. Tout ce qui s'ouvre par-dessus lui — dialogue, menu,
  drawer, éditeur en place — se ferme d'abord. En sortir par mégarde coûte cher.
- **Le glisser-déposer est refusé à la source** : au moment du dépôt, la sélection
  est encore celle de l'origine.
- **La pile d'annulation est applicative et entière** (addendum A) : la pile native
  meurt dès qu'une interception écrit dans le DOM.

### Fichiers modifiés / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `front/static/front/js/mode_edition.js` | **neuf** — la garde, la parade, la pile, `Ctrl+S`, `beforeunload` |
| `front/templatetags/corpus_permissions.py` | filtre `une_analyse_tourne_sur` |
| `front/templates/front/includes/lecture_principale.html` | le bouton du mode + la zone du compte rendu |
| `front/templates/front/base.html` | chargement de `mode_edition.js` (`?v=1`), `maquette.css` 73→**74** |
| `front/static/front/css/maquette.css` | l'habillage du mode, **par les tokens** — le build Tailwind est figé |
| `front/static/front/js/keyboard.js` | rang **4.6** : sortir du mode |
| `front/tests/test_mode_edition.py` | **neuf** — 10 tests |

## Deuxième temps — ce que l'usage a montré (30 août 2026)

### Trois défauts d'affichage, trouvés en regardant l'écran

Aucun n'aurait été vu sans ouvrir un navigateur.

**1. Le mode était inutilisable, et rien ne le signalait.**
`contenteditable="plaintext-only"` impose `white-space: pre-wrap` à tout le champ.
Les **blancs d'indentation du gabarit Django**, jusque-là collapsés, devenaient donc
de vraies lignes vides : un bloc passait de **24 px à 197 px**, et la note de
**17 259 px à 154 062 px**.

**Et aucun CSS ne peut le contredire** : `white-space: normal !important` posé **en
ligne** reste calculé `pre-wrap`. La cure est dans le DOM — le mode retire les nœuds
texte purement blancs à l'ouverture, à **trois** niveaux (entre les blocs, dans
`.corps`, dans le `<ul>` d'une puce). Après : **+3,5 %**, soit le seul cadre du mode.

**2. Le mode ne se voyait pas.** Le fond du champ ne contraste qu'à **1,08:1** avec
la page — invisible. Le signal passe désormais par le **filet** (5,01:1 en clair,
5,69:1 en sombre) et par une **ligne qui nomme le mode** et ses trois touches.

**3. Le repère « vidé » ne s'affichait jamais.** `:empty` ne peut pas marcher : même
caché, le `<span>` des boutons d'action garde l'élément non vide au sens CSS. C'est
le JS qui pose `data-vide`, et le CSS le lit.

### Cinq demandes du mainteneur, et ce qu'elles ont révélé

| | |
|---|---|
| le refus devient une **modale** | le compte rendu s'affiche **en tête** de la note : en éditant plus bas, on ne le voit pas |
| le panneau d'analyses **s'efface** | éditer, c'est regarder le texte, pas ce qu'on en a extrait |
| **surlignages et ancres neutralisés** | les `<mark>` **restent dans le DOM** — ils portent le texte — mais deviennent transparents, et les clics n'emmènent plus ailleurs |
| **`M`** entre dans le mode | `Échap` en sort. `M` ne peut pas faire les deux : une fois dedans, la garde des champs de saisie arrête les touches simples — et c'est heureux, sinon taper « m » sortirait du mode |
| **sortir exige que tout soit enregistré** | trois issues : *Enregistrer et sortir*, *Sortir sans enregistrer*, *Rester* |

**Et la cinquième en a révélé une sixième, qui était un vrai défaut** : le drapeau
« modifié » retombait dès qu'un enregistrement rendait 200 — **même si des blocs
avaient été refusés**. Le texte refusé, toujours à l'écran mais pas en base, serait
alors parti sans un mot. Il ne retombe plus que si **tout** est passé.

### Le diagnostic qui a tout déclenché

Un usage réel sur `/lire/3/` : deux corrections, l'impression que « la sauvegarde ne
marche pas ». **Elle marchait.** Le journal le montre — une correction écrite, une
refusée parce que le passage est **cité par une synthèse figée**. Sur cette note,
**7 blocs sur 12 sont gelés**. Ce qui manquait n'était pas l'enregistrement : c'était
de **voir** le refus. D'où la modale, et le marquage du bloc **là où il est**.

### Le mode hors des transcriptions — et le tableau, qui était un piège actif

**La question posée** : le mode marche-t-il ailleurs que sur une transcription ?
**Mesuré sur cinq notes et 387 blocs** — un article web, une page Wikipédia, deux
documents techniques, un PDF — en lisant ce que le mode *enverrait*, sans envoyer :

| Label | Aller-retour |
|---|---|
| `text`, `section_header`, `title`, `list_item` | **exact** — 100 % |
| `picture`, `caption` | **exact** — 10 sur 10 |
| `code` | **exact** — 4 sur 4 |
| **`table`** | **0 sur 20** ❌ |

**Seul le tableau échoue**, et c'était un **risque actif** : son `texte` est du
markdown « pipe », ce qui s'affiche est un `<table>` construit **après** le marquage,
et aucun chemin HTML→markdown n'existe. Ce qu'on lit du tableau rendu diffère donc
**toujours** de la base — `« CatégorieArgument »` au lieu de
`« | Catégorie | Argument | »`. Un `Ctrl+S` sur la page 2 aurait **écrasé ses neuf
tableaux sans que personne n'y touche**.

La spec l'avait tranché le 26 août (§ 12 : « lecture seule dans le mode ») ; **ce
n'était pas codé**. Ça l'est, en trois couches :

1. le tableau **sort du champ modifiable** et porte la mention « lecture seule » ;
2. il n'est **jamais envoyé** ;
3. et le serveur le **refuse**, pour le client périmé — celui qui a chargé la page
   avant la règle.

Vérifié : **9, 2 et 1 tableaux figés** sur les pages 2, 5 et 10, corps non
modifiable, **zéro tableau envoyé**.

**Et la liste se limite à `table`** — pas aux « 58 éléments non textuels » qu'on
pouvait croire concernés. Les images, les légendes et le code bouclent parfaitement.

## Troisième temps — rétablir un passage sans sortir du mode (30 août 2026)

### Le geste manquait, et la mesure disait pourquoi

Le mode **crée** des passages masqués — un bloc vidé est masqué à
l'enregistrement, jamais supprimé (§ 7.3). Il n'avait aucun moyen de les
rétablir. Le placeholder « Passage masqué » et son bouton **existaient
pourtant déjà dans le champ** : ce que la mesure du 30 août a montré, sur
`/lire/29/` — la seule note de la base qui porte des blocs masqués (2 sur 99) —,
c'est qu'ils sont `display: none` **hors du mode structure** (décision U1) :

| | hors du mode | dans le mode d'édition |
|---|---|---|
| hauteur du placeholder | **0 px** | **0 px** |
| taille du bouton « démasquer » | **0 × 0** | **0 × 0** |
| arbre d'accessibilité | retiré (`display:none`) | retiré |

Le geste n'était donc pas seulement inatteignable au clavier : il était
**invisible**, et le rétablissement passait obligatoirement par *sortir du
mode → mode structure → cliquer*.
→ `benchmarks/edition_par_blocs/resultats/resultats-le-placeholder-masque-dans-le-mode.json`

### Un panneau, pas des placeholders dans le texte

*(Arbitrage du mainteneur, contre l'affichage des placeholders au fil des
lignes.)* Le champ reste ce qu'on lit et corrige ; les passages retirés se
retrouvent dans une **commande** repliée, rendue **au-dessus** du champ — donc
hors de lui, donc jamais sérialisée.

- **La liste vient du serveur**, par un filtre de gabarit `passages_masques_de`.
  Un filtre et non une variable de contexte, pour la raison qui a déjà servi à
  la garde d'entrée : `lecture_principale.html` est rendu depuis **trois**
  endroits, et une variable oubliée dans l'un d'eux vaudrait « vide » — donc un
  panneau absent, sans que rien ne le signale.
- **`<details>` natif** : le pliage, le focus et l'annonce sont justes sans une
  ligne de JavaScript.
- **Le bouton poste l'endpoint qui existe** (`/elements/<pk>/demasquer/`), et sa
  réponse remplace le bloc par un swap ciblé.
- **Le JS ne fait que l'affichage** : retirer la ligne, refaire le compte,
  annoncer. Le geste, son droit et son écriture restent entièrement serveur.

### Ce qui est mesuré, sur une note jetable créée puis supprimée

| | |
|---|---|
| hors du mode / dans le mode | **0 px** / **39 px**, hors du champ modifiable |
| le compte | « 2 passages masqués » → **« 1 passage masqué »** → panneau **disparu** |
| les blocs du champ | 2 → 3 → **4** |
| le mode | **toujours ouvert** après chaque rétablissement |
| erreurs JavaScript | **0** |

**Contrastes calculés, en clair et en sombre** (le premier calcul était faux :
`color-mix()` sort en `color(srgb 0…1)` et non en `rgb(0…255)`, ce qui donnait
un filet à 19,73:1 au lieu de 3,16) :

| | clair | sombre | exigence |
|---|---|---|---|
| résumé et extrait sur le fond | **5,24:1** | **5,94:1** | 4,5:1 |
| texte du bouton | **5,42:1** | **6,18:1** | 4,5:1 |
| filet du bouton | **3,16:1** | **4,26:1** | 3:1 (WCAG 1.4.11) |
| cible du bouton | **72 × 24 px** | idem | 24 px (WCAG 2.5.8) |

→ `benchmarks/edition_par_blocs/banc/mesures21_le_panneau_des_masques.py`

### Un défaut trouvé en chemin : un bloc revenu perdait son régime

`ouvrir()` sortait les tableaux du champ modifiable **une fois, à
l'ouverture**. Un bloc revenu **après** par un swap ciblé — un passage rétabli,
justement — arrivait avec le gabarit nu : **un tableau rétabli en pleine
session redevenait modifiable**, et son texte serait parti au `Ctrl+S` suivant
(le serveur l'aurait refusé, mais le travail était perdu). La mise en lecture
seule est désormais une fonction appelée **à l'ouverture ET après chaque
swap**.

### Et la modale de refus ne construit plus son HTML par concaténation

Le motif d'un refus porte maintenant le **titre de la synthèse** qui bloque
(§ 5.3) — donc du texte écrit par un humain. `direLesRefus` le lisait par
`textContent` (donc **décodé**) et le réinjectait en `html:` : un titre
`<img src=x onerror=…>` s'y serait exécuté. Le corps de la modale est construit
en **nœuds DOM**, chaque `<li>` par `textContent`. Un test serveur épingle en
plus l'échappement du titre dans le compte rendu.

### Fichiers modifiés / Modified files (troisième temps)

| Fichier / File | Changement / Change |
|---|---|
| `front/templatetags/corpus_permissions.py` | filtre `passages_masques_de` |
| `front/templates/front/includes/lecture_principale.html` | le panneau `<details>`, au-dessus du champ |
| `front/static/front/css/maquette.css` | l'habillage du panneau, par les tokens — **?v=80** |
| `front/static/front/js/mode_edition.js` | `figerLesBlocsEnLectureSeule`, la mise à jour du panneau, la modale en DOM — **?v=9** |
| `front/tests/test_mode_edition.py` | **+14 tests** (24 au total) : le panneau, puis l'endpoint qui le rend à jour |
| `benchmarks/edition_par_blocs/banc/mesures20_*.py`, `mesures21_*.py`, `mesures22_*.py` | **neufs** — le placeholder, le panneau, et le HTML dans les toasts |
| `hypostasis_extractor/views_element.py` | l'endpoint `panneau_des_masques` (GET, droit d'écrire, **404** jamais 403) |
| `front/templates/front/includes/_panneau_des_masques.html` | **neuf** — le partial, rendu par la page **et** par l'endpoint |
| `front/static/front/js/hypostasia.js` | `titleText` au lieu de `title` dans le toast — **?v=41** |

## Quatrième temps — ce que la relecture adverse a trouvé (30 août 2026)

Quatre défauts réels, dont **une faille de sécurité** qui n'était pas dans le
mode mais que le mode allait rendre atteignable.

### 1. Un toast pouvait exécuter du script — mesuré, puis fermé

`Swal.fire` rend son `title` **en HTML**. Or `hypostasia.js` y passait le
`message` de `HX-Trigger: showToast` — et ces messages portent des données
écrites par des humains : le nom d'un groupe, le titre d'une base, et **depuis ce
matin le titre de la synthèse** qui bloque une édition. **84 emplacements**
envoient des toasts ; aucun n'y met de balise volontaire.

**Mesuré avant correction** : un message contenant `<img src=x onerror=…>` fait
**s'exécuter le script** (`balise_executee: true`). Le scénario n'est pas
théorique — un membre d'un carnet partagé nomme sa synthèse ainsi, et le script
part chez quiconque tente de corriger un passage cité.

**Corrigé en une ligne** : `titleText` au lieu de `title`. Remesuré :
`balise_executee: false`, et le HTML arrive échappé.
→ `benchmarks/edition_par_blocs/banc/mesures22_le_toast_et_le_html.py`

> Le troisième temps affirmait avoir « suivi le titre jusqu'au bout ». C'était
> faux : le chemin du lot était propre, celui des **quatre gestes unitaires** ne
> l'était pas. L'affirmation est corrigée avec le défaut.

### 2. Le panneau ignorait ce que le mode venait de masquer

**Le cas d'usage fondateur du § 5.3 cas 4 était raté** : le panneau n'était rendu
qu'au chargement, et un bloc vidé pendant la session n'y entrait jamais. La fiche
de test manuel décrivait un comportement qui n'existait pas.

**Le geste est maintenant complet, dans les deux sens**, et il passe par le
serveur : un endpoint `GET /elements/panneau_des_masques/?page=<pk>` rend le
**même partial** que la page, et `mode_edition.js` le redemande après chaque
enregistrement et après chaque rétablissement. Rien n'est recalculé côté client —
ni le texte conservé du bloc, ni son ordre, ni le pluriel du compte.

**Cela répare aussi la ligne périmée** : un passage démasqué ailleurs (mode
structure, ou par un tiers) laissait une ligne dont le « rétablir » aurait fait
revenir la version **en base** du bloc, écrasant ce qui était en train d'être
tapé. Le panneau redemandé au serveur n'a plus cette ligne.

**Deux pièges trouvés par la mesure, pas par la lecture :**

| Ce qui se passait | Pourquoi |
|---|---|
| après un enregistrement, **plus aucun « rétablir » ne fonctionnait** | htmx ne traite pas ce qu'il n'a pas inséré : les `hx-post` d'un fragment posé par `innerHTML` sont **inertes**, sans un mot. `htmx.process()` les arme |
| le panneau **se refermait** sous les doigts | le serveur rend un `<details>` fermé ; l'état du pli se conserve maintenant au rafraîchissement |

**Mesuré de bout en bout**, sur une note jetable créée puis supprimée :

| | |
|---|---|
| au chargement | « 2 passages masqués », 2 blocs dans le champ |
| vider un bloc + `Ctrl+S` | **« 3 passages masqués »**, panneau **resté ouvert**, compte rendu « 1 bloc masqué » |
| premier « rétablir » | « 2 passages masqués », **3** blocs |
| second « rétablir » | « **1 passage masqué** », **4** blocs |
| le mode | **toujours ouvert**, **0 erreur JS** |

### 3. Un bloc revenu par swap gardait une gouttière modifiable

Le troisième temps avait corrigé la lecture seule des tableaux, mais pas les
**gouttières** — qui portent le numéro, le locuteur et le minutage. Un bloc
rétabli revenait avec la sienne modifiable : la frappe y était acceptée, **jamais
sérialisée** (`texteDuBloc` ne lit que l'élément interne), donc perdue au
`Ctrl+S`. Le régime complet est désormais reposé après chaque swap.

### 4. Trois documents promettaient un toast que personne n'affiche

`_reponse_du_compte_rendu` pose `HX-Trigger: showToast`, mais **son seul appelant
est un `fetch()`** qui lit le corps et ignore les en-têtes. La docstring de la
vue, le commentaire du partial et le CHANGELOG du lot affirmaient le contraire.
Corrigés. **Ce qui reste ouvert** : un `Ctrl+S` entièrement réussi, en bas d'une
note longue, n'a aucun retour **visible** près du curseur.

## Ce qui n'est PAS fait

- **La sténotypie** (§ 6) : piloter l'audio depuis le champ, le rembobinage à la
  reprise, la vitesse de lecture, la correction du locuteur au clavier. Rien.
- **La table de raccourcis du § 4.4** : les touches sont en dur dans le fichier. La
  pédale et les collisions système attendent.
- **`Entrée` reste invisible** hors des blocs `pre` : le `\n` part en base et en
  revient, mais aucun `white-space: pre-line` ne le montre.
- **Le lecteur d'écran réel** (§ 9) : jamais éprouvé, l'exigence reste entière.

---

## Comment tester (à la main) / Manual test

Sur https://beta.hypostasia.org/ (`jonas` / `admin1234`), ouvrir une note qu'on peut
écrire — par exemple `/lire/21/`.

### Test 1 — ouvrir et voir
1. Cliquer **« Éditer le texte »**. **Attendu** : le fond du texte se creuse, un
   filet apparaît à gauche, les numéros de passage reviennent dans la gouttière, et
   le bandeau annonce « Mode édition ouvert ».
2. Cliquer dans le texte et taper. **Attendu** : ça s'écrit.

### Test 2 — le geste qui compte
1. Sélectionner **du milieu d'un passage au milieu d'un autre**, cinq rangs plus bas.
2. Taper **une lettre**. **Attendu** : les passages intermédiaires se vident, les
   deux extrêmes gardent leur reste, et **le nombre de passages ne bouge pas**.
3. `Ctrl+Z`. **Attendu** : tout revient, d'un seul coup.

### Test 3 — enregistrer
1. Corriger un mot, vider un passage entier.
2. `Ctrl+S`. **Attendu** : « Enregistrement en cours… », puis un compte rendu à cinq
   nombres. Le passage vidé devient un **placeholder masqué**, il n'est pas supprimé.
3. `Ctrl+S` une seconde fois pendant l'attente → **refusé**, et il le dit.

### Test 4 — ne rien perdre
1. Taper quelque chose, puis fermer l'onglet ou cliquer un lien.
2. **Attendu** : le navigateur prévient. Après un `Ctrl+S`, il ne prévient plus.

### Test 5 — le refus
1. Lancer une analyse sur la note.
2. Recharger. **Attendu** : le bouton est **grisé**, et son infobulle dit pourquoi.

### Test 6 — rétablir un passage masqué sans sortir du mode
1. Dans le mode, vider entièrement un passage, puis `Ctrl+S`. **Attendu** : le
   compte rendu dit « 1 bloc masqué ».
2. Regarder **au-dessus du texte** : une ligne « 1 passage masqué » est apparue.
   Cliquer dessus pour la déplier. **Attendu** : le début du passage retiré, et
   un bouton « rétablir ».
3. Cliquer **rétablir**. **Attendu** : le passage **revient dans le texte, à sa
   place**, la ligne quitte le panneau, et **le mode reste ouvert** — on peut
   continuer à taper.
4. S'il ne restait que celui-là, le panneau **disparaît** entièrement.
5. Sortir du mode. **Attendu** : le panneau n'est plus visible du tout — en
   lecture, c'est le mode structure qui montre les passages masqués.

### Tests automatiques
```bash
docker exec -w /app hypostasia_web python manage.py test \
  front.tests.test_mode_edition --noinput
```
→ **24 tests, OK** (mesuré le 30 août 2026 : 10 d'origine, **+7 sur le panneau
des passages masqués**, **+7 sur l'endpoint qui le rend à jour**).

La non-régression large :
```bash
docker exec -w /app hypostasia_web python manage.py test \
  front.tests.test_mode_edition front.tests.test_ce_que_dit_l_aide \
  front.tests.test_phases front.tests.test_lecture_elements \
  front.tests.test_boutons_elements front.tests.test_rendu_elements \
  hypostasis_extractor.tests.test_corriger_en_lot \
  hypostasis_extractor.tests.test_le_lot_et_les_ancrages \
  hypostasis_extractor.tests.test_le_rendu_d_un_seul_bloc \
  hypostasis_extractor.tests.test_views_element --noinput
```
→ **737 tests, OK, en 481 s** (mesuré le 30 août 2026 au soir ; 623 le 29, et
691 le 30 au matin, avant les 46 tests de la journée).

Le banc des trois moteurs :
`benchmarks/edition_par_blocs/banc/mesures16_mode_edition.py`.
