# La sténotypie au clavier / Keyboard shorthand transcription

**Date :** 2026-08-30
**Migration :** Non

## Résumé / Summary

**Quoi / What :** dans le mode d'édition, le son se pilote **sans lâcher le
clavier** — lire/pause, écouter à partir du passage du curseur, ±5 s, ralentir,
accélérer. Deux réglages nouveaux dans la barre : la **vitesse de lecture** et le
**recul à la reprise**. Et les touches ne sont plus en dur : elles vivent dans une
**table**.
/ In the editing mode, the sound is driven from the keyboard, and the keys live
in a table.

**Pourquoi / Why :** c'est le § 6 de `SPEC-edition-par-blocs-et-stenotypie.md`,
resté entier hors du socle depuis le 29 août. « La transcription est un usage de
premier rang : ce que la machine a mal entendu devient une extraction fausse,
ancrée à un passage qui n'a jamais été dit. » Corriger une transcription demande
d'écouter en écrivant ; lâcher le clavier à chaque phrase rend le travail
insupportable, donc il n'est pas fait.

---

## Les touches, et pourquoi celles-là

| Geste | Touche | Équivalents (pédale) |
|---|---|---|
| Lire ou mettre en pause | **F4** | `MediaPlayPause`, `F13` |
| Écouter à partir du passage du curseur | **F2** | — |
| Reculer de 5 s | **F7** | `MediaTrackPrevious`, `F14` |
| Avancer de 5 s | **F8** | `MediaTrackNext`, `F15` |
| Ralentir | **F9** | — |
| Accélérer | **F10** | — |

**Les touches F, et pas un modificateur.** Le champ est un `contenteditable` :
toute touche nue écrit du texte. `Ctrl+Espace` — le premier candidat — est pris
par le changement de méthode de saisie sous Linux/GNOME (IBus) et par le
sélecteur de source de saisie sous macOS : il peut **ne jamais atteindre la
page**. `Ctrl+Alt+←/→` change d'espace de travail sous GNOME. Les touches F sont
libres, et on écarte les plus disputées : F1 (aide), F3 (recherche), F5
(rechargement), F6 (barre d'adresse), F11 (plein écran), F12 (outils).

**Deux réserves, que la relecture adverse a relevées et qu'il faut connaître** :
`F7` ouvre la navigation au curseur de Firefox et `F10` sa barre de menus. Sur
une note **qui a du son**, le mode consomme la touche (`preventDefault`) et le
navigateur ne la voit pas ; sur une note **sans son**, la touche lui revient — et
c'est voulu, un geste de son qui ne peut rien faire ne doit pas avaler sa
touche. Reste que sur une note écrite, `F7` ouvrira le dialogue de Firefox : à
surveiller au premier essai réel, et à rebinder dans la table si c'est gênant —
c'est précisément à ça qu'elle sert.

**La pédale est prévue.** Un footswitch USB émet des codes média ou `F13`–`F15` :
chaque geste en accepte plusieurs, la première touche étant celle qu'on affiche.

## La table (§ 4.4), et ce qu'elle change déjà

`RACCOURCIS` est **une donnée**, lue par le listener et **publiée**
(`window.modeEdition.raccourcis`). Premier effet concret : **le bandeau du mode
se compose depuis elle**. Il annonçait ses touches dans le `content:` d'une règle
CSS — une recopie qui aurait menti au premier changement de touche, et qui ne
pouvait pas savoir si la note a du son. Le CSS lit maintenant
`attr(data-bandeau)` :

| Note | Ce que le bandeau annonce |
|---|---|
| transcrite (`/lire/4/`) | `Ctrl+S enregistrer · Ctrl+Z annuler… · Échap sortir… · F4 lire ou mettre en pause · F2 écouter à partir du passage du curseur` |
| écrite (`/lire/21/`) | les trois premiers seulement |

**Un geste de son ne consomme pas sa touche s'il n'y a pas de son** : sur une
note écrite, `F4` garde son sens navigateur.

## Les deux réglages du § 6.3 — dans la barre, pas dans le mode

Ce sont « les deux gestes qui manquent vraiment ». Ils vivent dans la **barre du
lecteur**, pas dans le mode : ils servent aussi à qui écoute sans corriger, et la
barre survit à tout — elle est hors de `#zone-lecture`, que `lectureReload`
remplace en entier.

- **La vitesse** : 0,5 · 0,75 · 1 · 1,25 · 1,5 · 1,75 · 2. Une **table de
  paliers**, pas une multiplication : ×1,1 donnerait 1,331×, un nombre qu'on ne
  sait ni lire ni retrouver. Elle s'affiche (`1,25×`, virgule française) et
  **survit au changement de bloc** — la spec l'exige : `brancherLeLecteur` la
  réapplique à chaque swap.
- **Le recul à la reprise** : 0 · 1 · 2 · 3 · 5 s, défaut **2 s**. « On met en
  pause pour écrire, et on a toujours perdu le début de la phrase. » **Zéro le
  désactive** — le réglage offre un comportement, il ne l'impose pas.

**Le recul ne s'applique qu'à une REPRISE**, jamais à un saut volontaire : il
déplacerait la cible qu'on vient de désigner. C'est pourquoi `ecouterDepuis()` et
`lireOuPause()` sont deux chemins distincts.

Les deux réglages sont retenus par `localStorage` : c'est un confort de poste de
travail, pas une donnée du corpus. Deux personnes qui corrigent la même note
n'ont aucune raison de partager leur vitesse d'écoute.

## Le mode ne touche pas l'élément `<audio>`

`lecteur_audio.js` expose `window.lecteurAudio` — `lireOuPause`, `ecouterDepuis`,
`decaler`, `changerLaVitesse`, `vitesse`, `reculALaReprise`. Le mode passe par
là, **jamais** par `document.querySelector('audio')` : il refabriquerait sinon le
recul à la reprise, la table des vitesses, l'avalement du rejet de `play()` et le
rafraîchissement du rail — quatre choses qui divergeraient. C'est la règle déjà
écrite au § 6.1 : « Rien n'est recopié, donc rien ne peut diverger. »

## Ce qui est mesuré, sur la vraie note transcrite (`/lire/4/`, 9 tours)

| | |
|---|---|
| `F2` sur le passage à **3,2 s** | la lecture y saute — **3,79 s** après 600 ms de son |
| `F8` puis deux `F7` | 8,75 → **14,07** → **4,39** (±5 s, bornés) |
| deux `F10`, puis un `F9` | **1,5×** puis **1,25×**, affichés `1,5×` / `1,25×` |
| recul réglé à 3 s : pause à 5,79 | reprise à **3,43** (5,79 − 3, plus le son écoulé) |
| après **rechargement complet** | vitesse **1,25×** et recul **3 s** conservés |
| erreurs JavaScript | **0** |

→ `benchmarks/edition_par_blocs/banc/mesures23_la_stenotypie.py`

**Un piège de mesure, payé ici** : le premier `[data-element-id]` d'un bloc n'est
pas son texte, c'est le **bouton compteur d'idées de la gouttière**. Un curseur
posé là est dans une zone `contenteditable="false"`, et le navigateur le replace
au début du champ à la première frappe — le banc mesurait donc `ecouterDepuis(0)`
et accusait le code. C'est le banc qui visait mal.

### Fichiers modifiés / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `front/static/front/js/lecteur_audio.js` | vitesse, recul à la reprise, et l'API `window.lecteurAudio` — **?v=2** |
| `front/static/front/js/mode_edition.js` | la table `RACCOURCIS`, le clavier de sténotypie, le bandeau composé — **?v=14** |
| `front/templates/front/includes/_lecteur_audio.html` | les deux réglages du § 6.3 |
| `front/static/front/css/maquette.css` | l'habillage des réglages ; le bandeau lit `attr(data-bandeau)` — **?v=82** |
| `front/tests/test_barre_du_lecteur_audio.py` | **+4 tests** |

## Ce que la relecture adverse a trouvé — et qui n'était pas dans la sténotypie

Quatre défauts faisaient **perdre du travail**. Aucun n'aurait été vu sans une
lecture hostile du chemin complet.

| Ce qui se passait | Pourquoi c'était invisible | La correction |
|---|---|---|
| les frappes tapées **pendant l'envoi** du `Ctrl+S` étaient désarmées | le lot part avec le texte du `Ctrl+S` ; ce qu'on tape pendant son vol (0,3 à 1,2 s) n'y est pas, et la réponse baissait quand même le drapeau — la sortie ne demandait plus rien | un témoin compte les gestes ; le drapeau ne retombe que si rien n'a été tapé, et le mode **le dit** |
| `Ctrl+Z` **hors du champ** annulait le texte derrière | le mode reste « ouvert » quand le focus passe sur le rail, le menu du recul ou un bouton du panneau — tous légitimes | les gestes de **texte** exigent le focus dans le champ ; ceux de **son** restent atteignables partout |
| la touche **« z » nue** remplaçait `#zone-lecture` | `keyboard.js` ne se tait que si le focus est dans un champ de saisie ; sorti du champ, « e », « m » et « z » redevenaient vivants — et « z » ouvre la comparaison de versions, **sans confirmation** | `keyboard.js` se tait tant que le mode est ouvert (`Échap` reste traité plus haut, au rang 4.6) |
| **cliquer un passage surligné** ouvrait le tiroir | les `<mark>` restent dans le DOM en mode édition (ils portent le texte) : y cliquer pour poser le curseur est le geste le plus ordinaire du mode. La garde existait — **sur le mauvais des deux listeners** de `marginalia.js` | garde posée sur **les deux** |

**Et trois messages du serveur n'atteignaient personne** : le motif FALC d'un
refus (« Une analyse est en cours sur cette note… ») ne vit que dans l'en-tête,
le corps étant vide — la personne lisait un refus générique ; le résumé « 1
passage corrigé, 1 refusé », **seul message disant que la moitié EST
enregistrée**, n'était pas affiché en cas de refus partiel — exactement le
défaut qui avait motivé la modale ; et `tachesChanged` était jeté. Les trois
sont rejoués.

**Le recul à la reprise déplaçait un point qu'on venait de viser** — ce que
l'encart du § 6.3 promet pourtant de ne jamais faire. Pause, clic sur le rail,
reprise : le son repartait deux secondes avant la cible. Il ne s'applique plus
après un **saut volontaire** (rail, « écouter ce passage », `F2`), ni sur un
fichier **terminé**, et le saut s'oublie dès que le son avance — sinon un `F7`
en début d'écoute priverait de recul la pause suivante, une demi-heure plus tard.

**Mesuré après correction** : saut volontaire à 9 s → reprise à **9,51 s** (plus
de recul) ; reprise ordinaire, pause à 5,82 → **3,48** (recul de 3 s intact) ;
`Ctrl+Z` sur le rail → le texte ne bouge pas ; « z » → le champ reste modifiable ;
clic sur un surlignage → le tiroir reste fermé ; **0 erreur JS**.

**Trois défauts plus petits, corrigés aussi** : les réglages relus de
`localStorage` sont ramenés aux **paliers connus** (une vitesse hors plage fait
lever `playbackRate`, et l'exception tombait dans le branchement de la barre, à
chaque chargement) ; les annonces disent **ce qui s'est passé**, pas ce qui a été
demandé (`decaler` rend faux quand la durée est inconnue) ; et le pas de
transport ne se recopie plus dans le libellé de la table.

## Ce qui n'est PAS fait

- **La correction du locuteur au clavier (§ 6.2) est IMPOSSIBLE en l'état, et la
  spec se trompe sur ce point.** Elle affirme que « le renommage du locuteur
  EXISTE — ce qui manque est son accès ». Vérifié dans le code :
  `PageViewSet.renommer_locuteur` **refuse en 409 toute note qui porte des
  éléments** (`front/views.py`, « Cette note est lue par éléments : l'édition de
  transcription ne s'y applique pas encore »), et le moteur ELEMENT est le seul
  moteur depuis le 10 août. Le geste n'existe donc **pour aucune note réelle**.
  Lui donner un raccourci ne servirait qu'à faire répondre 409 plus vite.
  **Ce qu'il faudrait** : un geste natif ELEMENT, qui écrit `provenance["locuteur"]`
  sur l'élément visé — le refus dit lui-même pourquoi l'ancien ne peut pas être
  recyclé (« bloc N = élément ordre N » n'est vrai que sur un corpus qui alterne
  les locuteurs).
- **La modale d'aide ne rend pas encore la table** (§ 4.4). Elle est publiée pour
  cela ; l'écran reste à écrire.
- **`lecteur_audio.js` garde ses touches en dur** — les flèches, `Début` et `Fin`
  du rail, qui n'agissent que si le focus est sur le rail. C'est le seul autre
  fichier concerné : la spec § 4.4 annonçait « QUATRE listeners `keydown` », dont
  `marginalia.js:290` et `user_menu.js:52` — **ces deux-là n'en ont plus aucun**
  depuis le 29 août. Il en reste **trois** : `keyboard.js`, `lecteur_audio.js` et
  `mode_edition.js`. La table ne gouverne que le dernier.
- **L'aide (`aide_desktop.html`) recopie `M`, `Ctrl+S`, `Ctrl+Z` et `Échap` en
  dur**, et cette recopie échappe aux deux audits — celui de l'écran lit
  `onboarding_vide.html`, celui de la modale lit `liste_raccourcis` dans
  `views.py`. Elle divergera sans témoin au premier changement de touche. C'est
  le troisième point du § 4.4, et il reste entier.
- **Répéter un bloc en boucle** (`data-fin` est posé, donc c'est offert) : hors
  périmètre v1, comme le dit la spec.
- **Un bloc envoyé deux fois** est compté « corrigé » **et** « refusé » : le
  client n'en produit pas aujourd'hui, mais le jour où il en produira, le bloc
  serait peint en rouge alors que sa correction est en base. Relevé, non corrigé.
- **`Échap` sur une modale du mode** : le rang 4.6 de la cascade appelle
  `fermer()`, qui ouvre un **second** dialogue par-dessus celui qu'on voulait
  fermer. Hypothèse de lecture, **non mesurée** — l'ordre des écouteurs de
  SweetAlert2 ne se déduit pas du code.
- **Les touches média peuvent être captées par le navigateur** (Media Session)
  avant d'atteindre la page, ou la doubler. À éprouver avec une vraie pédale.

---

## Comment tester (à la main) / Manual test

Sur https://beta.hypostasia.org/, ouvrir **`/lire/4/`** (neuf tours, deux
locuteurs) ou `/lire/3/`.

### Test 1 — les réglages se voient
1. Regarder la barre du lecteur, en bas à droite : `− 1× +`, puis `reprise` et un
   menu de secondes.
2. Cliquer `+` deux fois. **Attendu** : `1,5×`, et le son accélère s'il joue.
3. Recharger la page. **Attendu** : `1,5×` est **toujours là**.

### Test 2 — écouter le passage qu'on lit
1. Cliquer **« Éditer le texte »**. Le bandeau annonce maintenant `F4` et `F2`.
2. Cliquer dans le texte d'un passage, au milieu de la note.
3. Appuyer **F2**. **Attendu** : le son repart **au début de ce passage-là**, et
   le curseur ne bouge pas — on peut taper aussitôt.

### Test 3 — le va-et-vient
1. **F4** met en pause, **F4** reprend — et la reprise repart **quelques
   secondes en arrière** (le réglage « reprise »).
2. Mettre « reprise » à **0 s**. **Attendu** : la reprise repart exactement là où
   on s'était arrêté.
3. **F7** / **F8** reculent et avancent de 5 s sans quitter le texte.

### Test 4 — une note sans son
1. Ouvrir `/lire/21/` et entrer dans le mode.
2. **Attendu** : le bandeau n'annonce **ni F4 ni F2**, et la barre du lecteur
   n'est pas là.

### Tests automatiques
```bash
docker exec -w /app hypostasia_web python manage.py test \
  front.tests.test_barre_du_lecteur_audio --noinput
```

Le banc du navigateur : `benchmarks/edition_par_blocs/banc/mesures23_la_stenotypie.py`
