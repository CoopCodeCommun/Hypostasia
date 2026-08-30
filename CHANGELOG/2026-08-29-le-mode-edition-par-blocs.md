# Le mode d'édition par blocs / The block editing mode

**Date :** 2026-08-29
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

## Ce qui n'est PAS fait

- **La sténotypie** (§ 6) : piloter l'audio depuis le champ, le rembobinage à la
  reprise, la vitesse de lecture, la correction du locuteur au clavier. Rien.
- **La table de raccourcis du § 4.4** : les touches sont en dur dans le fichier. La
  pédale et les collisions système attendent.
- **`Entrée` reste invisible** hors des blocs `pre` : le `\n` part en base et en
  revient, mais aucun `white-space: pre-line` ne le montre.
- **Le lecteur d'écran réel** (§ 9) : jamais éprouvé, l'exigence reste entière.
- **Démasquer depuis le mode** (§ 5.3, cas 4) : le mode crée des blocs masqués et
  n'a aucun moyen de les restaurer sans en sortir.

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

### Tests automatiques
```bash
docker exec -w /app hypostasia_web python manage.py test \
  front.tests.test_mode_edition --noinput
```
→ **10 tests, OK** (mesuré le 29 août 2026).

La non-régression large :
```bash
docker exec -w /app hypostasia_web python manage.py test \
  front.tests.test_mode_edition front.tests.test_phases \
  front.tests.test_lecture_elements front.tests.test_boutons_elements \
  hypostasis_extractor.tests.test_corriger_en_lot \
  hypostasis_extractor.tests.test_le_rendu_d_un_seul_bloc \
  hypostasis_extractor.tests.test_views_element --noinput
```
→ **623 tests, OK, en 407 s** (mesuré le 29 août 2026).

Le banc des trois moteurs :
`benchmarks/edition_par_blocs/banc/mesures16_mode_edition.py`.
