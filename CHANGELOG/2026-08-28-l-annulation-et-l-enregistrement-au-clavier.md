# L'annulation et l'enregistrement au clavier / Undo and save, from the keyboard

**Date :** 2026-08-28
**Migration :** Non
**Code livré :** **aucun dans l'application.** Un addendum de spec, et le prototype
qui l'éprouve — lequel vit **dans** le dépôt depuis le 24 août
(`front/static/front/maquettes/prototype-champ-unique/`), servi publiquement.

## Résumé / Summary

**Quoi / What :** `Ctrl+Z` et `Ctrl+S` sont spécifiés — **addendum A** de
`SPEC-edition-par-blocs-et-stenotypie.md` — et le prototype les porte et les
mesure sur les trois moteurs.
/ Undo and save are now specified and prototyped.

**Pourquoi / Why :** la spec mentionnait `Ctrl+S` sans dire ce qu'il fait, et **ne
parlait pas d'annulation du tout**. Or l'annulation n'est pas un raffinement : le
geste central du mode — vider trente en-têtes d'un coup — est destructeur, et sans
`Ctrl+Z` il ne se rattrape qu'après enregistrement, par `demasquer`.

---

## La décision : l'annulation est APPLICATIVE, et elle l'est entièrement

**Le piège est de vouloir garder les deux piles.** Sous la garde, la frappe
ordinaire passe **nativement** — elle entre donc dans la pile du navigateur — mais
tout geste traversant écrit dans le DOM à la main. Et une écriture manuelle **tue**
la pile native : mesuré, après une interception, `Ctrl+Z` ne rend plus rien, **ni le
geste, ni la frappe qui le précédait**.

**`execCommand` n'est pas la sortie** : mesuré, il ne rend la pile qu'à moitié —
**une opération par `Ctrl+Z`**, donc six pour défaire une suppression de six blocs,
**aucun `\n` inséré**, et deux mutations de structure là où l'écriture directe n'en
produit aucune.

**L'interception est possible, et vérifiée** : `preventDefault` sur `Ctrl+Z`
empêche complètement l'annulation native.

| | Chromium 145 | Firefox 146 | WebKit 26 |
|---|---|---|---|
| annulation native, sans interception | marche | marche | marche |
| **`preventDefault` l'empêche** | ✅ | ✅ | ✅ |

## Une photo ne contient que des textes

**C'est le cadeau du § 3.** Le mode interdisant la fusion et la scission, la liste
des blocs est **invariante** : une photo est une table
`identifiant_stable → texte`, et **il n'y a aucune structure à restaurer**.

| | mesuré sur 210 blocs **synthétiques** |
|---|---|
| coût d'une photo | **2,6 à 5 ms** selon le moteur et la prise |
| poids d'une photo | **57 558 octets** |
| pile de 100 pas | **5,5 Mo** |

**Sur quoi exactement** : le prototype porte un jeu **synthétique de même forme**
que la plus grosse note de la base (210 blocs, mêmes labels, **−3,2 %** de
caractères). Les chiffres valent comme ordres de grandeur d'une note de cette
taille. Source : `benchmarks/edition_par_blocs/resultats/resultats-pile-native-et-cout-photo.json`.
**Et `execCommand` n'a été mesuré que sur Chromium**, le 23 août
(`resultats-volet3.json`, clé `g_execcommand`).

**Quand photographier** — pas à chaque frappe, ce serait +2,6 ms sur les 6 ms
qu'une frappe coûte déjà à 210 blocs : **avant chaque geste intercepté**, et **après
une pause de frappe de 500 ms**.

## Ce que le prototype établit, sur les trois moteurs

| | Chromium | Firefox | WebKit |
|---|---|---|---|
| un mot tapé fait **UN** pas de pile | ✅ | ✅ | ✅ |
| **un seul** `Ctrl+Z` rend les 4 blocs vidés, **et** les blocs 20 et 25 | ✅ | ✅ | ✅ |
| frontières identiques après annulation | ✅ | ✅ | ✅ |
| `Ctrl+Maj+Z` re-vide les blocs | ✅ | ✅ | ✅ |
| frontières identiques après rétablissement | ✅ | ✅ | ✅ |
| le curseur revient dans le bon bloc | ✅ | ✅ | ✅ |
| erreurs JavaScript | **0** | **0** | **0** |

**« Un `Ctrl+Z` = un geste »** est donc tenu — et c'est exactement ce que
`execCommand` ne savait pas donner.

## `Ctrl+S` — trois obstacles, vérifiés dans le code le 28 août

1. **`keyboard.js:372` ignore tout ce qui porte Ctrl, Meta ou Alt.** `Ctrl+S`
   n'atteint **jamais** l'application. Exception explicite à poser **avant** cette
   ligne.
2. **`preventDefault()` est obligatoire** — c'est « enregistrer la page ».
3. **Quatre écouteurs `keydown` au niveau document** — `keyboard.js:353`,
   `lecteur_audio.js:409`, `marginalia.js:290`, `user_menu.js:52`.

**Trois points de conduite, tenus par le prototype et mesurés :**

| | les trois moteurs |
|---|---|
| l'état d'attente est annoncé | ✅ |
| un second `Ctrl+S` pendant l'envoi est **refusé** | ✅ |
| le drapeau « modifié » retombe après l'enregistrement | ✅ |
| **la pile d'annulation SURVIT** à l'enregistrement | ✅ |

L'état d'attente n'est pas cosmétique : le lot prend **295 ms** au plancher et
**~1,2 s** pour une session ordinaire (mesuré le 26 août).

Et `beforeunload` est posé — avec sa borne écrite dans le code : **il ne couvre pas
les navigations HTMX internes**, qui demanderont un garde sur `htmx:beforeRequest`.

## Ce qui reste, et l'obstacle à lever avant de coder

**`marginalia.js:290-294` est un danger direct** : un **second** écouteur `Échap`,
hors cascade, retire `.est-en-edition` et **supprime le `.editeur`** — sans
confirmation ni enregistrement. Si le mode réutilise cette convention — le chemin
naturel —, **une frappe d'`Échap` efface le travail.** À fusionner dans la cascade
ou à neutraliser **avant** la première ligne du mode.

**Trois choses que l'addendum ne décide pas** : la borne de la pile (100 pas font
5,5 Mo, le chiffre est au mainteneur), le raccourci de rétablissement (`Ctrl+Maj+Z`
ou `Ctrl+Y`, à mettre dans la table du § 4.4 et jamais en dur), et si l'annulation
doit franchir un enregistrement — la réponse simple est **non**, la pile est celle
de la session à l'écran, le journal `PageEdit` est l'histoire du serveur.

### Fichiers modifiés / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `PLAN/specs/SPEC-edition-par-blocs-et-stenotypie.md` | **addendum A** (A.1 à A.7) + le pointeur en tête |
| `front/static/front/maquettes/prototype-champ-unique/prototype.js` | la pile, `Ctrl+Z`/`Ctrl+Maj+Z`/`Ctrl+S`, le drapeau, `beforeunload` |
| `benchmarks/edition_par_blocs/banc/mesures14_annulation.py` | **neuf** — le banc des trois moteurs |
| `benchmarks/edition_par_blocs/banc/mesures_pile_native_et_cout_photo.py` | **neuf** — la pile native et le coût d'une photo |

---

## Comment tester (à la main) / Manual test

Ouvrir le prototype dans sa **configuration éprouvée**, annulation comprise :

**https://beta.hypostasia.org/static/front/maquettes/prototype-champ-unique/index.html?garde=2&ce=plaintext-only&compo=1&annulation=1**

### Test 1 — un mot tapé fait un seul pas
1. Cliquer dans un bloc, taper `bonjour`, attendre une seconde.
2. `Ctrl+Z`.
3. **Attendu** : le mot entier disparaît d'un coup, pas lettre par lettre.

### Test 2 — annuler une suppression multi-blocs
1. Sélectionner du milieu d'un bloc au milieu d'un bloc cinq rangs plus bas.
2. `Suppr` : les blocs intermédiaires se vident, les deux extrêmes gardent leur reste.
3. **Un seul** `Ctrl+Z`.
4. **Attendu** : tout revient, y compris les deux blocs extrêmes — et le compteur de
   blocs n'a **jamais** bougé.

### Test 3 — le rétablissement et le curseur
1. Après le test 2, `Ctrl+Maj+Z` : les blocs se re-vident.
2. `Ctrl+Z` : ils reviennent, **et le curseur est dans le premier bloc de la plage**.

### Test 4 — `Ctrl+S`
1. `Ctrl+S` : le bandeau annonce « Enregistrement en cours ».
2. `Ctrl+S` une seconde fois **pendant** l'attente → **refusé**, et il le dit.
3. À la fin, le compte rendu affiche le POST **et l'état de la pile** — qui n'a pas
   été vidée.
4. Le navigateur ne propose **jamais** sa propre boîte « enregistrer la page ».

### Test 5 — ne rien perdre
1. Taper quelque chose, puis fermer l'onglet.
2. **Attendu** : le navigateur prévient. Après un `Ctrl+S`, il ne prévient plus.
