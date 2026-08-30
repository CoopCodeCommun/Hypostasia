# SPEC — L'édition par blocs et la sténotypie

**Projet** : Hypostasia V3
**Version** : 1.1 — 23 août 2026 (relue le jour même, voir l'encart)
**Complète** : `SPEC-ancrage-par-element-v2.md` (elle en est la couche d'édition :
elle ne définit aucun modèle, elle décrit ce qu'un humain peut faire aux éléments)
**Étalon** : `front/static/front/maquettes/maquette.html` § `.bloc` — la gouttière et
son filet d'état existent déjà, et ce sont eux qui portent les frontières
**Statut** : **SPÉCIFIÉE, CODÉE DANS SON SOCLE.** Le back est livré — le swap
ciblé, l'`identifiant_stable` dans le DOM, l'endpoint de lot du § 7 — **et le mode
d'édition existe** depuis le 29 août : la garde, la parade IME, la pile
d'annulation, `Ctrl+S`, `Échap`.
→ `CHANGELOG/2026-08-29-le-mode-edition-par-blocs.md`
**Restent hors du socle** : toute la sténotypie (§ 6), la table de raccourcis
(§ 4.4), le `white-space: pre-line` de l'`Entrée` (§ 4.2), le démasquage depuis le
mode (§ 5.3) et le lecteur d'écran réel (§ 9). **La voie technique est
tranchée** — option C, le champ unique, garde sur `beforeinput` et parade sur
`compositionstart` : **les trois mesures qui la conditionnaient sont faites, et les
trois passent** (26 août 2026).
**Conventions** : skill `djc`
**Addenda** : **A** — l'annulation et l'enregistrement au clavier (28 août 2026) ·
**B** — corriger un bloc masqué (29 août 2026). Les deux en fin de document.

> ## Le prototype a parlé — 23 août 2026, au soir
>
> **C — le champ unique est la voie à instruire, et son interception vit dans
> `beforeinput`, pas dans `keydown`.** Chiffres, méthode et limites :
> `CHANGELOG/2026-08-23-le-champ-unique-tranche-l-edition-par-blocs.md`.
>
> **Les trois choses que ce prototype a établies et qui touchent cette spec :**
>
> 1. **`contenteditable="plaintext-only"` ne suffit pas.** Il empêche la scission
>    du `<p>` par `Entrée` et nettoie le collage, mais **pas** la fusion
>    multi-blocs : 210 blocs deviennent 205, comme sans lui. La question ouverte du
>    § 5.2 est donc tranchée : **il règle une partie des six gestes, pas le
>    premier.**
> 2. **Une garde par `keydown` ne protège que les touches auxquelles on a pensé.**
>    Mesuré : taper une lettre sur une sélection multi-blocs, `Ctrl+X`, et `Ctrl+A`
>    puis frapper détruisent respectivement 5, 5 et **209** blocs — *avec* la garde.
>    La même garde posée sur `beforeinput` tient les trois. Le § 4.4 doit donc
>    parler de **types d'entrée**, pas seulement de touches.
> 3. **La composition IME — le geste n° 6 du § 5.2 — n'est pas seulement un geste
>    qui crée des nœuds : elle n'est PAS ANNULABLE.** `insertCompositionText` arrive
>    avec `cancelable: false`. Une composition sur une sélection multi-blocs détruit
>    donc 5 blocs sur 210 que **rien n'arrête**, garde comprise. Le § 5.2 la liste
>    bien ; ce qu'il ne dit pas, c'est qu'elle échappe au `preventDefault` — et sur
>    Android, **toute** frappe est une composition. Piste non éprouvée : normaliser
>    la sélection dès `compositionstart`.
> 4. **`getTargetRanges()` rend une LISTE VIDE sous `plaintext-only`** (Chromium
>    145), pour `insertText`, `insertFromPaste` et `deleteContentForward` — alors
>    que la sélection, elle, traverse bien trois blocs. Une garde qui s'y fie seule
>    y est **aveugle** : mesuré, un collage traversant y détruisait un bloc. Le
>    repli sur `window.getSelection()` le corrige. **`plaintext-only` n'est donc pas
>    une option de confort** : c'est lui qui tient le collage **non traversant**, que
>    la garde laisse passer par construction.
>
> **Les trois mesures qui restent, et qui conditionnent la décision** — le § 11 les
> désigne, les voici :
>
> 1. ✅ **FAIT le 26 août 2026 — Firefox 146 et WebKit 26.** La promesse
>    fondatrice tient sur **les trois moteurs** : `↓` et `Maj+↓` traversent les
>    gouttières, `Ctrl+Fin` va au dernier bloc, `plaintext-only` est accepté
>    partout. Et la garde tient partout sur le chemin réel — sélection étendue **au
>    clavier** puis `Suppr` : **210 blocs et 210 gouttières intacts** avec elle,
>    contre 206 (Chromium) et 209 (Firefox, WebKit) sans elle.
>    **Le piège de `getTargetRanges()` est propre à Chromium** : 0 plage sous
>    `plaintext-only` là où Firefox et WebKit en rendent 1. Le repli sur la
>    sélection reste nécessaire, et il est inoffensif ailleurs.
>    **Une divergence WebKit à connaître** : le repère de la gouttière entre dans
>    `selection.toString()` quand on étend au clavier — `user-select: none` ne l'en
>    empêche pas. La garde protège quand même (textes de gouttière intacts), mais un
>    **copier** depuis Safari emporterait « #5 » avec le texte.
> 2. ✅ **FAIT le 26 août 2026 — le DOM réel.** La garde a été injectée dans la
>    vraie page servie par Django, boutons d'action compris (189 sur 189), et les
>    trois gestes tiennent : **189 → 189, zéro mutation, zéro erreur JS**. Deux
>    résultats pour le § 7.1 : lire `.corps.textContent` rend **0 bloc exact sur
>    189** (les blancs du gabarit **et** le mot « corriger » des boutons y entrent),
>    lire l'**élément interne** débarrassé de ses boutons en rend **189 sur 189** ;
>    et sur la page 19, **202 bouclent sur 210 — les 8 qui échouent sont exactement
>    les 8 `table`**, ce qui tranche la question ouverte du § 12 : **les éléments
>    non textuels sont en lecture seule dans le mode.**
>    *(Restent non vus : un `.element-masque` et un `avertissement-plafond` dans le
>    flux — il n'en existe aucun en base.)*
> 3. ✅ **FAIT le 26 août 2026 — la composition IME, et sa parade.**
>    Vraie composition par CDP sur une sélection du bloc 20 au bloc 25 : **210 → 205
>    blocs sans parade** (la queue du bloc 25 recollée à la tête du 20), **210 → 210
>    avec**. La parade : normaliser la sélection dès `compositionstart`, qui arrive
>    **avant** toute écriture — on ne combat pas la composition, on lui retire sa
>    matière. Le gestionnaire s'arme et normalise sur **les trois moteurs**.
>    ⚠️ La vraie composition n'est déclenchable que sur Chromium ; **Android — où
>    toute frappe est une composition — demande un vrai appareil.**
>
> **Et une mesure qui rassure** : la réconciliation des ancres ne détache **que**
> les portions qui enjambent le point d'édition — 22 sur 22 —, et **aucune** des
> 37 autres. Ce comportement est **identique pour les trois voies** : elles
> appellent toutes la même fonction serveur. Confirmé au passage : **14 éléments
> sur 40 (35 %) sont refusés d'emblée** parce qu'une synthèse figée les cite (§ 8.2
> annonçait 30 %).

> ## Relecture adverse du 23 août 2026 — deux erreurs de fait, et un défaut de production
>
> La version 1.0 a été relue le jour de son écriture. Elle portait **deux erreurs qui
> la rendaient inapplicable**, toutes deux vérifiées depuis :
>
> 1. **La clé de provenance audio.** La v1.0 était écrite contre `voice`,
> `start_time` et `end_time`. **L'ingestion écrit `locuteur`, `debut`, `fin`**
> (`ingestion_audio.py:144-146, 172-174`), et c'est ce que le rendu lit. Le seul
> endroit du code de production à employer l'autre vocabulaire était
> `moteur_structure.py` — **il était en défaut, et il est corrigé** depuis le
> 23 août 2026 :
> `CHANGELOG/2026-08-23-la-fusion-de-deux-tours-gardait-le-mauvais-locuteur.md`.
> Le préalable que cette spec posait au § 6 est donc **levé**.
> 2. **La détection des changements.** La v1.0 comparait sur `empreinte_contenu`, qui
> **normalise** (`empreinte_du_texte`, `core/models.py:2116` : minuscules, espaces
> écrasés, `strip`). Elle aurait jeté en silence toute correction de casse ou
> d'espace — les plus fréquentes en transcription. Le § 7 compare désormais sur le
> **texte brut**.
>
> Trois autres corrections : **le renommage de locuteur existe déjà** (§ 6.2), il y a
> **quatre** listeners clavier et non un (§ 4.4), et **`Échap` détruit aujourd'hui
> l'éditeur en place** sans rien enregistrer (§ 2).

> **Cette spec n'est pas une cinquième spec canonique.** Comme
> `SPEC-transcription-audio-locale.md`, elle décrit une **couche d'interaction**.

> **Ce qu'elle absorbe** : trois notes de `PLAN/TODO/` du 23 août 2026, qui gardent
> leurs **mesures**. En cas de désaccord, cette spec fait foi — sauf sur le choix de
> la voie technique, que le prototype tranche.

---

## 0. Ce que cette spec décide

| # | Décision | § |
|---|---|---|
| 1 | Deux modes distincts : **lire** et **éditer**. Le mode se voit et s'annonce | 2 |
| 2 | **On édite le texte d'un bloc, jamais le découpage** — ni fusion, ni scission | 3 |
| 3 | Un bloc **vidé** est **masqué**, jamais supprimé | 5.3 |
| 4 | La sélection est **contiguë**, et elle **traverse** les blocs | 5.1 |
| 5 | L'enregistrement est **explicite**, compare le **texte brut**, et **rend un compte** | 7 |
| 6 | Le mode **ne s'ouvre pas** si une tâche tourne — et le refus subsiste à l'écriture | 8.1 |
| 7 | Tout se fait **au clavier**, de bout en bout, y compris le son | 4, 9 |
| 8 | Les raccourcis sont **une table de configuration**, lue par les quatre listeners | 4.4 |
| 9 | La transcription est un **usage de premier rang** | 6 |
| 10 | Un swap **ciblé** remplace `lectureReload` : sans lui, un tiers détruit la session | 11 |

---

## 1. Le problème

Deux travaux, aujourd'hui pénibles au point de ne pas être faits : **corriger une
transcription** (couper, recoller, corriger, réattribuer un tour, en écoutant) et
**nettoyer une ingestion Docling** (retirer en-têtes, pieds de page, bandeaux). Le
geste est répété des dizaines de fois ; le front actuel sert un bouton par bloc, une
confirmation par geste, et un rechargement complet après chacun.

**Le back est prêt sur l'essentiel** : `ElementDocument` porte `identifiant_stable`,
`ordre`, `label`, `texte`, `empreinte_contenu`, `provenance` ;
`reconcilier_les_portions_de_l_element` réaligne les ancres et **compte les
détachées** ; `masquer` rend les portions DÉTACHÉE sans rien supprimer. Cette spec
n'ajoute **aucun modèle**.

**Il ne l'est pas sur deux points**, et il faut les traiter avant :

- **la clé de provenance audio** est incohérente entre l'ingestion et la fusion (voir
  l'encart et le TODO dédié) ;
- **le corps rendu d'un bloc n'est pas son texte** : il contient les
  `<mark class="portion">` **et** les quatre boutons de `_actions_element.html`,
  rendus *à l'intérieur* du `<p>`/`<h2>`/`<li>`/`<pre>`. Un `textContent` naïf rendrait
  « corrigercouperrecollermasquer », et **chaque caractère parasite décale tous les
  offsets**. Le contrat de sérialisation du § 7 existe pour ça.

> **`identifiant_stable` ne survit PAS à une scission ni à une fusion.** Le help_text
> du modèle dit « ne change jamais, même après scission ou fusion » : il veut dire que
> l'UUID d'une **ligne donnée** n'est jamais réécrit. Le code, lui, **supprime** les
> éléments et en crée de nouveaux (`moteur_structure.py:150`, `:395-396`). Cela
> n'affecte pas le § 3 — qui exclut ces gestes du mode — mais interdit de s'en servir
> comme argument.

---

## 2. Deux modes

**Mode lecture** — l'écran actuel, inchangé, et c'est le défaut.

**Mode édition** — le texte devient éditable partout, d'un coup, et le clavier change
de sens.

**Le mode doit se voir et s'annoncer.** Un mode invisible qui capture le clavier est
une source de confusion, et le projet a déjà tranché en remplaçant, le 21 août 2026,
des onglets sans adresse par des écrans adressables. À trancher : une classe et un
`aria-pressed`, ou une **adresse** (`/lire/<id>/editer/`) qui rende le mode
partageable et « précédent »-able ?

**Sortir : `Échap` — et il y a deux obstacles à lever AVANT d'écrire une ligne.**

1. **La cascade doit gagner un échelon.** `gererEscape()` (`keyboard.js:291-348`) est
   ordonnée : bottom sheet → modale alignement → modale aide → bandeau → drawer →
   désélection. Le mode d'édition n'y est pas. Tant qu'il n'y est pas, `Échap` avec le
   drawer ouvert ferme le drawer, pas le mode.
2. **`marginalia.js:290-297` est un danger direct.** Un **second** écouteur `Échap`,
   hors cascade, fait :
   ```js
   var bloc = document.querySelector('.bloc.est-en-edition');
   if (!bloc) return;
   bloc.classList.remove('est-en-edition');
   var editeur = bloc.querySelector('.editeur');
   if (editeur) editeur.remove();
   ```
   — **destruction du DOM de l'éditeur, sans confirmation ni enregistrement**.
   `.editeur` et `.est-en-edition` sont la convention de `_editeur_en_place.html`
   (son script inline pose la classe) et de `maquette.css:2040-2044`.

   ✅ **LEVÉ le 29 août 2026.** L'écouteur a été **fusionné dans la cascade**, pas
   neutralisé : c'était le jumeau du bouton « Annuler », une fonction vivante. Le
   danger n'était d'ailleurs pas que futur — mesuré, avec le drawer ouvert par-dessus
   un éditeur, **un seul `Échap` fermait les deux** et jetait la correction en cours
   de frappe. `marginalia.js` ne porte plus aucun écouteur clavier ; la cascade
   appelle `window.marginalia.fermerEditeurEnPlace()` à un rang **après** le drawer.
   → `CHANGELOG/2026-08-29-un-seul-ecouteur-echap.md`

---

## 3. Le contrat d'édition

**On édite le TEXTE d'un bloc. On n'édite jamais le DÉCOUPAGE.**

Hors de ce mode, et le restant : **la fusion et la scission**, qui gardent leurs
boutons en mode structure parce qu'elles renumérotent la page (verrou de **page**),
déplacent les ancres et **suppriment les éléments d'origine** ; et **toute scission
automatique** — un bloc « trop gros » n'est pas coupé par la machine, ce serait une
décision de sens, et sur une transcription elle **inventerait** un intervalle de temps.

**La garantie, et sa borne.** Après une session, la liste des `identifiant_stable` et
leur `ordre` sont **exactement** ceux d'avant, aux blocs masqués près — **à condition
qu'aucun autre écrivain n'ait touché la page pendant la session**. Quatre peuvent le
faire, et la spec ne prétend pas les empêcher :

1. **un autre utilisateur en mode structure** — scission ou fusion **suppriment** des
   éléments ; les identifiants envoyés au `Ctrl+S` n'existeront plus (§ 7.4) ;
2. **une ré-ingestion** (`services/reingestion.py`) — elle remplace les éléments ;
3. **une re-transcription** — `transcrire_audio_task` réécrit la page ;
4. **le navigateur lui-même** (§ 5.2).

C'est une garantie **testable**, et ce doit être un test (§ 12).

---

## 4. Le clavier

### 4.1 Navigation et sélection

| Touche | Geste |
|---|---|
| `↑` `↓` `←` `→` | déplacer le curseur — **traverse les blocs** |
| `Maj` + flèches | étendre la sélection — **traverse les blocs** |
| `Ctrl+Début` / `Ctrl+Fin` | début / fin de la note |
| `Échap` | sortir du mode (§ 2) |

### 4.2 Édition

| Touche | Geste |
|---|---|
| `Entrée` | insère un saut de ligne **dans** le bloc — **ne crée jamais de bloc** |
| `Retour arrière` en tête de bloc | **ne fait rien** — pas de fusion |
| `Suppr` / `Retour arrière` sur une sélection multi-blocs | vide le texte sélectionné **bloc par bloc** (§ 5.2) |
| `Ctrl+S` | enregistrer (§ 7) |

> **`Entrée` est aujourd'hui invisible sur 1 107 blocs sur 1 129.** Aucun
> `white-space: pre-line` sur `.bloc > .corps` (`maquette.css:1763-1772`) : dans un
> `<p>`, un `<h2>`, un `<li>` ou un `<blockquote>`, un `\n` **s'affiche comme une
> espace**. Seuls les 2 blocs `code` (`<pre>`) le montrent. **À trancher** : soit le
> CSS accueille le saut de ligne — et il faut alors `collectstatic` **et** le bump du
> `?v=` —, soit `Entrée` ne fait rien hors des blocs `pre`. Un geste qui ne se voit
> pas est pire que pas de geste.

### 4.3 Son

Lecture/pause au **bloc du curseur**, recul/avance ±5 s, ralentir/accélérer (§ 6.2).
Les touches ne sont pas fixées ici : voir 4.4.

### 4.4 Les raccourcis sont une table, pas des touches en dur

1. **Les collisions système existent.** `Ctrl+Espace` — le premier candidat — est pris
   par le changement de méthode de saisie sous Linux/GNOME (IBus) et par le sélecteur
   de source de saisie sous macOS. Il peut ne **jamais** atteindre la page.
2. **La pédale.** Un footswitch USB émet des touches — codes média, ou `F13`–`F15`.
   Des touches en dur l'excluent ; reconnaître `MediaPlayPause` coûte une ligne.
3. **Il y a QUATRE listeners `keydown` au niveau document**, et non un :
   `keyboard.js:353`, `lecteur_audio.js:409`, `marginalia.js:290`, `user_menu.js:52`
   (plus cinq écouteurs portés par des éléments). **La table doit être lue par tous**,
   ou ils doivent être fusionnés. Et `keyboard.js:372` ignore aujourd'hui **tout ce qui
   porte Ctrl, Meta ou Alt** : `Ctrl+S` exige une exception explicite, plus un
   `preventDefault()` — c'est le raccourci « enregistrer la page » du navigateur.

**Une table nommée** (`{geste: touche}`), avec des valeurs par défaut. La modale d'aide
(`?`) la rend telle qu'elle est, jamais une liste recopiée qui divergerait.

---

## 5. La sélection et le masquage

### 5.1 Contiguë, et elle traverse

Une plage continue, du milieu d'un bloc au milieu d'un autre. **Pas de sélection
discontinue.** **Elle doit traverser** : c'est ce qui rend possible le nettoyage d'une
ingestion.

### 5.2 Rien ne doit fusionner deux blocs — et six gestes le tentent

Le piège central. Une sélection allant du milieu du bloc 3 au milieu du bloc 8, suivie
de `Suppr`, conduit un navigateur à laisser **un seul nœud** contenant le début de 3 et
la fin de 8 — une **fusion**, que le § 3 interdit.

**Le comportement spécifié** : chaque bloc de la plage perd exactement la part de son
texte qui était sélectionnée. Les blocs 3 et 8 gardent leur reste ; les blocs 4 à 7
sont vidés, donc masqués (§ 5.3). **Les frontières ne bougent pas.**

**Six gestes créent ou suppriment des nœuds, et tous doivent être traités** — la
suppression n'est que le premier :

1. `Suppr` / `Retour arrière` sur une sélection multi-blocs ;
2. le **collage** — un collage HTML multi-paragraphes injecte des nœuds ;
3. le **glisser-déposer** d'une sélection ;
4. la **correction orthographique** du navigateur ;
5. l'**annulation native** (`Ctrl+Z` du navigateur, distinct de toute annulation
   applicative) ;
6. la **composition IME** — saisie accentuée et non latine.

**À trancher au prototype** : `contenteditable="plaintext-only"` en règle-t-il une
partie ? Son support navigateur est à **vérifier**, pas à supposer.

### 5.3 Un bloc vidé est masqué, jamais supprimé

- **`AncrageExtraction.element` est en `PROTECT`** : un `delete()` lèverait sur tout
  bloc portant une portion — **386 éléments sur 1 129**, pour 826 ancrages (23 août).
- **`masquer` fait déjà ce qu'il faut** (`services/masquage.py`) : portions en
  **DÉTACHÉE**, jamais supprimées ; bloc barré et grisé, conservé ; exclu des chunks
  envoyés au LLM ; `demasquer` les remet en place si le texte n'a pas changé.

**Masquer détache aussi des CITATIONS, et ce n'est pas la même chose.**
`detacher_les_citations_des_portions` (`core/services/synthese.py:817`) bascule **tout**
`SourceLink` de type `CITE` pointant ces portions en `DETACHEE` — **wikis compris**.
Mesuré le 23 août : **294 liens `CITE` visent un wiki, sur 117 éléments**. Le refus du
§ 8.2 ne couvre que les synthèses **figées** : vider trente en-têtes peut donc détacher
des dizaines de sources d'articles **sans refus**. C'est acceptable — un wiki est
vivant, il se met à jour — mais **jamais silencieux** : le compte rendu du § 7 porte ce
nombre, distinct de celui des ancres.

**Quatre cas à trancher à l'implémentation :**

1. **ce que montre le champ** quand un bloc est vidé — il se referme, ou une ligne vide
   subsiste jusqu'à l'enregistrement ? Le placeholder `.element-masque` existe, mais
   **seulement en mode structure** (`maquette.css:1504-1505`), et **aucun élément
   masqué n'existe en base** : il n'a jamais été vu en conditions réelles ;
2. **vider puis re-remplir avant d'enregistrer** : la bonne réponse est « jamais
   masqué » — on compare l'**état**, pas les frappes ;
3. **tout vider** : geste légitime qu'un `demasquer` rattrape, ou refus ?
4. **démasquer depuis le mode** : le § 5.3 crée des blocs masqués, et le mode n'a
   aujourd'hui **aucun moyen de les voir ni de les restaurer**. Sans ce geste, le
   masquage n'est réversible qu'en sortant du mode.

---

## 6. La sténotypie

**La transcription est un usage de premier rang.** Ce que la machine a mal entendu
devient une extraction fausse, ancrée à un passage qui n'a jamais été dit.

> **Le préalable que posait la v1.1 est LEVÉ.** `_fusionner_les_provenances` lisait
> trois clés que l'ingestion n'écrit pas : la fusion de deux tours conservait
> silencieusement le locuteur **et** la borne de fin du premier, et son test était
> vert sur un contrat mort. Corrigé le 23 août 2026 —
> `CHANGELOG/2026-08-23-la-fusion-de-deux-tours-gardait-le-mauvais-locuteur.md`. Les
> gestes décrits ci-dessous reposent donc sur un contrat de provenance juste.

**Le vocabulaire, et il n'y en a qu'un** : `provenance` porte **`locuteur`**,
**`debut`**, **`fin`** — écrits par `ingestion_audio.py:144-146, 172-174`, lus par
`front/services/rendu_elements.py`. `voice`, `start_time` et `end_time` n'existent
nulle part ailleurs que dans le code en défaut et dans un `help_text` à corriger.

### 6.1 Ce qui existe déjà, et qu'il ne faut pas réécrire

| Brique | Où |
|---|---|
| l'instant de chaque bloc | `_blocs_elements.html:86-87` — **`data-debut` ET `data-fin`** |
| « écouter depuis ce tour » | `lecteur_audio.js:392` — `deplacerLaLecture()` puis `play()`, via `.bouton-ecouter` |
| le suivi inverse | `elementDuTourCourant` — le tour écouté est déjà surligné |
| le transport | `lecteur_audio.js:409` — ±5 s, Début, Fin, **mais seulement si le focus est sur `#rail`** |
| **le renommage du locuteur** | `PageViewSet.renommer_locuteur` (`front/views.py:3263`) et son formulaire (`:3241`) |

Lancer l'écoute au bloc du curseur revient à **trouver le bloc, lire son `data-debut`,
appeler la fonction qui existe**. Rien n'est recopié — la règle du lecteur : « Rien
n'est recopié, donc rien ne peut diverger. »

### 6.2 Le renommage du locuteur EXISTE — ce qui manque est son accès

**Correction de la v1.0**, qui affirmait qu'aucun geste ne corrigeait le locuteur.
`renommer_locuteur` renomme dans `transcription_raw`, reconstruit le HTML et le texte,
met à jour `provenance["locuteur"]` sur les éléments par `bulk_update`, et écrit un
`PageEdit` de type `locuteur` (`TypeEdit.LOCUTEUR`, PHASE-27a). Il porte **trois
portées** : `tous`, `ce_bloc_seul`, `ce_bloc_et_suivants`.

**`ce_bloc_seul` est exactement la réattribution d'un tour.** Ce qui manque n'est donc
pas le geste : c'est **son accès au clavier depuis le mode**, sans passer par une
modale — et le fait qu'il soit atteignable sur le bloc du curseur.

### 6.3 Les deux gestes qui manquent vraiment

Aucun n'apparaît dans `lecteur_audio.js` (recherche du 23 août 2026) :

1. **Le rembobinage à la reprise.** À la reprise après une pause, le son repart **une
   à trois secondes en arrière** : on met en pause pour écrire, et on a toujours perdu
   le début de la phrase. Le retard est **réglable**, et **zéro le désactive**.
2. **La vitesse de lecture** (`audio.playbackRate`), de 0,5× à 2×, par pas visibles.
   Elle s'affiche et **survit** au changement de bloc.

**Offert sans donnée nouvelle** : `data-fin` étant posé, **répéter un bloc en boucle**
ne demande rien de plus. Hors périmètre v1.

---

## 7. L'enregistrement

**Explicite, jamais un polling muet.** Le polling automatise le silence : sur un refus
(§ 8), l'utilisateur taperait dix minutes sans que rien ne soit enregistré.

### 7.1 Ce que le client envoie — le contrat de sérialisation

Une liste de `{identifiant_stable, texte}`. Deux exigences, et la première est un
piège vérifié :

- **le texte est dérivé du DOM, pas lu tel quel.** Le corps d'un bloc contient les
  `<mark class="portion">` **et** les quatre boutons de `_actions_element.html`. Le
  client retire les nœuds qui ne sont pas du texte d'origine, ou ces boutons ne sont
  pas rendus en mode édition. **Un caractère parasite décale tous les offsets** ;
- **l'identifiant est `identifiant_stable`**, jamais le `pk` — c'est lui qui désigne
  un bloc indépendamment de son ordre, et le journal l'emploie déjà.

### 7.2 Ce que le serveur compare — le texte BRUT

**Jamais `empreinte_contenu`.** `empreinte_du_texte()` (`core/models.py:2116`)
normalise : minuscules, espaces écrasés, `strip`. Comparer là-dessus jetterait en
silence :

- toute correction de **casse** — « paul » → « Paul » ;
- toute correction d'**espaces** — double espace, espace avant un signe ;
- **le `Entrée` du § 4.2 lui-même** : `"abc def"` et `"abc\ndef"` ont la même
  empreinte normalisée.

`hash_du_texte_brut()` (`services/masquage.py:52`) existe **exactement pour ce cas**,
et son commentaire le dit : « une correction qui ne change que la casse ou les espaces
DÉPLACE les caractères sans changer l'empreinte normalisée […] les offsets deviennent
faux, et l'empreinte normalisée ne le voit pas. » **C'est lui qu'on emploie.**

### 7.3 Ce que le serveur fait, bloc par bloc

1. texte identique au caractère près ⇒ **rien**, pas même un journal ;
2. texte vide ⇒ **masquer** (§ 5.3) — et si le bloc est **déjà masqué**, c'est un
   **non-geste** : rien d'écrit, rien de compté ;
3. bloc **déjà masqué** et texte non vide ⇒ **refusé**, ce bloc seul. Le corriger
   rendrait son démasquage impossible, en silence et pour toujours : voir
   l'**addendum B**, qui le chiffre ;
4. sinon ⇒ `reconcilier_les_portions_de_l_element`, **verrou de ligne**.

### 7.4 Le compte rendu — cinq nombres et une liste

Blocs **modifiés**, blocs **masqués**, **ancres détachées**, **citations détachées**
(§ 5.3 — un nombre distinct), blocs **refusés** — et pour ceux-là, **la liste avec leur
identifiant et leur motif**. Un compte sans liste ne dit pas quoi retaper.

**Trois refus à nommer explicitement :**

- **un bloc a disparu** (scission, fusion, ré-ingestion par un tiers) : ce bloc est
  refusé, **et lui seul**. Le code actuel répond à un élément introuvable par un
  `_reponse_passage_disparu()` qui déclenche un `lectureReload` — donc l'effacement de
  la session. Le lot doit refuser le bloc **sans** recharger ;
- **une analyse a démarré pendant la session** : le refus est **total**, pas partiel
  (§ 8.1) ;
- **un passage est cité par une synthèse figée** : refus de ce bloc (§ 8.2).

**Ne pas perdre ce qui n'est pas enregistré** : quitter la page avec des modifications
en attente doit prévenir — `beforeunload` **et** les navigations HTMX internes, qui ne
le déclenchent pas.

**Une borne au lot.** 210 blocs modifiés font 210 verrous et 210 réconciliations dans
une requête. La borne, et le compte de ce qu'elle écarte, suivent la règle du dépôt :
« ce qui est écarté par cette borne est COMPTÉ ».

---

## 8. Les refus

### 8.1 L'analyse — à l'entrée ET à l'écriture

`services/garde_edition.py` interdit d'éditer pendant qu'une analyse tourne, et la
raison est bonne : « le job travaille sur un texte qui n'existe plus » — soit des
ancres fausses en silence, soit une analyse entière perdue et facturée.

**Le contrôle vit aux deux endroits, et le second n'est pas retirable** :
`reconcilier_les_portions_de_l_element` et `masquer_un_element` appellent la garde
**eux-mêmes**, au niveau **page**. Conséquence à écrire noir sur blanc : si une analyse
démarre pendant une session, **le lot entier est refusé** — 0 passé, N refusés. Le
contrôle à l'entrée du mode ne fait qu'éviter le cas fréquent ; il ne le supprime pas.

**Question ouverte, et elle n'a pas de réponse aujourd'hui : qui empêche une analyse de
démarrer pendant une session ?** Une dizaine de points créent des `ExtractionJob`, et
aucun ne sait qu'une session est ouverte. Le WebSocket ne porte que `tache_terminee` et
`file_ingestion_modifiee` — **aucun message « une tâche vient de démarrer »**.
L'éditeur ne peut donc pas être prévenu. Trois voies : un verrou de session, un
troisième message WebSocket, ou l'acceptation du refus total avec un texte conservé
côté client.

### 8.2 Les autres refus

**Droit d'écriture** sur la note. **Passage cité par une synthèse figée** — et ce refus
est **plus large qu'il n'en a l'air** : une extraction peut porter des portions sur
plusieurs éléments, et citer cette extraction **gèle tous ses éléments**. Mesuré :
**114 éléments gelés**, soit 30 % des porteurs d'ancrage. Un lot de trente blocs peut
donc en voir dix refusés pour un motif que l'écran ne montre pas — d'où l'obligation
d'une **liste** au § 7.4.

---

## 9. L'accessibilité — de bout en bout, sans souris

Critère d'acceptation, pas raffinement. La chaîne : entrer dans le mode → atteindre le
champ → naviguer → étendre une sélection → vider → enregistrer → **lire le compte
rendu** → sortir.

- **Le compte rendu s'annonce** — mais attention : `annonces.js` **n'annonce que les
  toasts** et exclut délibérément les modales (« SweetAlert les annonce déjà »). Un
  compte rendu à cinq nombres **et une liste** ne passe pas par ce canal tel quel : il
  faut soit un résumé en toast et le détail ailleurs, soit une région live dédiée.
- **Savoir où l'on est sans regarder** : un champ multi-blocs annonce du texte, pas des
  frontières. Chaque bloc porte son repère — son numéro, et son **locuteur**.
- **L'entrée et la sortie du mode s'annoncent.**
- **À éprouver avec un vrai lecteur d'écran**, jamais en le supposant.

---

## 10. L'historique

`PageEdit` existe et `corriger` l'écrit (`views_element.py:305-316`), avec
l'`identifiant_stable` — « l'ordre, lui, est renuméroté à chaque scission/fusion ».
`TypeEdit` porte déjà `contenu`, `bloc_transcription` et `locuteur`.

**Un enregistrement produit une entrée par lot**, pas une par bloc : c'est le geste que
l'humain a fait. Elle porte l'avant et l'après de chaque bloc touché, et le compte rendu
du § 7.4.

---

## 11. Ce que cette spec NE décide PAS — et ce qu'elle exige quand même

**La voie technique.** Trois étaient en concurrence : **A** le clavier maison,
**B** BlockNote, **C** le champ unique. **Le prototype du 23 août 2026 a instruit
C** (voir l'encart en tête) : elle tient, son interception vit dans `beforeinput`,
et **B est écartée par arbitrage de dépendance — pas par la mesure, elle n'a jamais
été construite.** **A reste le repli**, et elle garde un avantage que C n'a pas :
sous C une session couvre la note entière, donc un `lectureReload` déclenché par un
tiers efface **tout** le travail, quand A n'en perdrait qu'un bloc. Cette spec
décrit ce que l'utilisateur peut faire ; elle ne dit toujours pas comment.
**Les trois doivent servir le même contrat** — c'est ainsi qu'on les compare.

**Trois choses valent quelle que soit la voie, et s'écrivent sans attendre :**

1. **corriger la fusion des provenances** (TODO dédié) — préalable de tout le § 6 ;
2. ✅ **FAIT le 24 août 2026 — l'endpoint de lot** (§ 7) :
   `POST /elements/corriger_en_lot/`. Il compare le **texte brut**, masque les
   blocs vidés, refuse un bloc disparu **lui seul**, refuse le lot **entier** si
   une analyse tourne, écrit **un** `PageEdit` par lot, et rend les cinq nombres
   avec la liste des refus. **17 tests.**
   → `CHANGELOG/2026-08-24-l-endpoint-de-lot.md`
3. ✅ **FAIT les 23-24 août 2026 — l'endpoint qui rend UN bloc, et le swap ciblé.**
   `GET /elements/<pk>/bloc/` rend un seul bloc, et `corriger`, `masquer`,
   `demasquer` répondent désormais avec le bloc touché en `hx-swap-oob` **au lieu
   de** `lectureReload`. Éprouvé au navigateur par un témoin posé sur un bloc
   voisin : il survit au geste, donc la zone de lecture n'est plus refaite.
   `scinder` et `fusionner_avec_le_suivant` gardent le rechargement — ils
   renumérotent la page —, et un pk mort aussi : il veut dire qu'un tiers a
   restructuré, et là la vue est périmée pour de bon.
   → `CHANGELOG/2026-08-23-un-endpoint-qui-rend-un-seul-bloc.md`

   Chaque bloc porte aussi son **`identifiant_stable`** dans le DOM
   (`data-element` et `id="bloc-<uuid>"`), ce qu'aucun gabarit ne faisait : c'est
   le prérequis du contrat de sérialisation du § 7.1.

---

## 12. Les mesures et l'étalon

**Aucun appel LLM. Pas de `make test-llm`, pas de facture.**

**Les tests passent par le Makefile et `manage.py test`** — le dépôt n'utilise pas
pytest (`grep pytest pyproject.toml` ne rend rien ; seul `playwright` est présent, et
les e2e tournent sous `manage.py test front.tests.e2e`). La ligne de partage est
**serveur / navigateur**, pas un choix d'outil : ce qui touche au DOM et au clavier va
en e2e.

**Fixtures étalons à écrire** — sans elles, on éprouve trois blocs :

- une **transcription réelle**, plusieurs locuteurs, dont **un tour issu d'une fusion**
  (pour éprouver le correctif du TODO) ;
- une **ingestion Docling** avec ses en-têtes et pieds de page répétés ;
- une note **longue** : la plus grosse de la base fait **210 blocs**, dont les textes
  totalisent **58 770 caractères** — **59 188** une fois joints par `\n\n`, ce que rend
  `_texte_de_la_note_depuis_ses_elements` (`front/views.py:481`) ;
- les labels **non textuels** : sur 1 129 éléments, **20 `table`** (dont **2** portent
  une ligne vide interne), **19 `caption`**, **17 `picture`**, **2 `code`**. Un
  `table` n'a **aucun aller-retour** : son `texte` est du markdown « pipe », son DOM un
  vrai `<table>` construit après coup (`rendu_elements.py:675-679`), et le HTML→markdown
  qui permettrait de le relire **n'existe pas**. ~~**À trancher : ces 58 éléments sont-ils
  éditables, ou en lecture seule dans le mode ?**~~ **TRANCHÉ le 26 août 2026 par
  la mesure** : sur la page 19, 202 blocs sur 210 bouclent exactement par le DOM, et
  **les 8 qui échouent sont exactement les 8 `table`**. Un `<table>` rendu ne se
  relit pas en markdown — aucun chemin ne le fait. **Lecture seule dans le mode.**

> **Le cas transcription EST mesurable sur cette base** — remesuré le 23 août 2026 :
> `provenance__has_key='locuteur'` rend **21 éléments sur 1 129**, sur **deux** notes
> (page 3 « Débat IA — transcription », 12 éléments ; page 4 « Palais César — deux
> locuteurs », 9), et **5 locuteurs distincts**. Cet encart annonçait « 0 élément,
> aucune transcription ingérée » : la requête avait porté sur `voice`, la clé morte —
> `provenance__has_key='voice'` rend bien 0. **Il n'y a donc rien à ingérer avant de
> commencer** ; mais 21 éléments sur deux notes courtes ne disent rien de la tenue à
> 200 blocs, et le correctif de fusion, lui, est fait.

**Les tests** :

1. **les frontières sont identiques avant/après** une session — `identifiant_stable` et
   `ordre`, aux masqués près (§ 3) ;
2. **la suppression multi-blocs ne fusionne pas** (§ 5.2) ;
3. **le collage ne crée aucun bloc** — ni le glisser-déposer, ni la correction
   orthographique ;
4. **un bloc supprimé par un tiers ne fait pas perdre le lot** : ce bloc est refusé, les
   autres passent, **et aucun `lectureReload` n'est déclenché** ;
5. **le lot partiel** : trois refusés, vingt-sept passés, et le compte rendu porte les
   trois identifiants ;
6. **une analyse démarrée en cours de session** : refus **total**, et le texte n'est pas
   perdu ;
7. **la casse et les espaces sont enregistrés** — le test qui aurait attrapé l'erreur de
   la v1.0 ;
8. **la concurrence**, en `TransactionTestCase` — un `TestCase` ordinaire enferme tout
   dans une transaction et `select_for_update` n'y prouve rien. Deux enregistrements
   qui se chevauchent : le second ne doit pas écraser le premier **en silence** ;
9. **le parcours complet au clavier**, puis avec un lecteur d'écran ;
10. **le son** : la touche choisie atteint-elle la page sous Linux et sous macOS, et le
    son part-il au début du bloc du curseur ?

---

## Addendum A — l'annulation et l'enregistrement au clavier

**28 août 2026.** Cette spec mentionnait `Ctrl+S` au § 4.2 sans dire ce qu'il fait,
et **ne parlait pas d'annulation du tout**. Ce trou s'écrit avant de se coder.

**Ce qui suit est mesuré — et voici exactement sur quoi.** Les bancs tournent sur le
**prototype**, donc sur un jeu **synthétique de même forme** que la plus grosse note
de la base : 210 blocs, même répartition de labels, **−3,2 %** de caractères. Les
chiffres valent donc comme ordres de grandeur d'une note de cette taille, pas comme
mesures de cette note-là.

| Ce qui est mesuré | Sur combien de moteurs | Source |
|---|---|---|
| `Ctrl+Z` / `Ctrl+S`, un geste par pas, la pile conservée | **trois** | `resultats-volet14-annulation.json` |
| `preventDefault` empêche l'annulation native ; coût et poids d'une photo | **trois** | `resultats-pile-native-et-cout-photo.json` |
| `execCommand` : une opération par `Ctrl+Z`, aucun `\n`, 2 mutations | **Chromium seul**, le 23 août | `resultats-volet3.json`, clé `g_execcommand` |
| le coût d'un lot côté serveur | sans navigateur | `resultats-cout-d-un-gros-lot.json` |

Tout est dans `benchmarks/edition_par_blocs/`.

### A.1 L'annulation est APPLICATIVE, et elle l'est entièrement

**Décision : `Ctrl+Z` est intercepté, toujours, et le mode tient sa propre pile.**

**Pourquoi pas la pile native**, et pourquoi pas un mélange des deux : sous la
garde, la frappe ordinaire passe **nativement** — elle entre donc dans la pile du
navigateur —, mais tout geste qui traverse écrit dans le DOM à la main. Or une
écriture manuelle **tue** la pile native : mesuré, après une interception, `Ctrl+Z`
ne rend plus rien, **ni le geste, ni la frappe qui le précédait**. Une annulation
qui passe tantôt par le navigateur, tantôt par nous, dans un ordre qui ne suit pas
l'histoire de l'utilisateur, est **pire que pas d'annulation**.

**Et `document.execCommand` n'est pas la sortie** : mesuré, il ne rend la pile
native qu'à moitié — **une opération par `Ctrl+Z`**, donc six `Ctrl+Z` pour défaire
une suppression de six blocs, **aucun `\n` inséré**, et deux mutations de structure
là où l'écriture directe n'en produit aucune.

**L'interception est possible** — `preventDefault` sur `Ctrl+Z` empêche complètement
l'annulation native sur **Chromium 145, Firefox 146 et WebKit 26** (mesuré).

### A.2 Ce qu'une photo contient : les textes, et rien d'autre

**C'est le cadeau du § 3.** Puisque le mode interdit la fusion et la scission, la
liste des blocs est **invariante** : une photo est une simple table
`identifiant_stable → texte`. **Il n'y a aucune structure à restaurer.**

| | mesuré sur 210 blocs synthétiques |
|---|---|
| coût d'une photo | **2,6 à 5 ms** selon le moteur et la prise |
| poids d'une photo | **57 558 octets** |
| pile de 100 pas | **5,5 Mo** |

*(Deux prises. L'attribution par moteur **s'inverse** de l'une à l'autre — Firefox
4 ms puis 5 ms, WebKit 5 puis 4 : l'écart est du bruit, et il ne faut pas lire ce
tableau comme un classement des moteurs.)*

**La pile est bornée**, et — règle du dépôt — **ce qu'elle écarte est compté** : la
plus vieille photo qui tombe hors de la borne doit être dite, pas oubliée en
silence.

### A.3 Quand photographier : un `Ctrl+Z` = un GESTE

Surtout pas à chaque frappe : ce serait **+2,6 à 5 ms sur les 6 ms** que coûte déjà
une frappe à 210 blocs.

1. **avant chaque geste intercepté** — ils sont rares, et ce sont eux qui détruisent ;
2. **après une pause de frappe** (~500 ms d'inactivité), pour qu'un mot tapé fasse
   **un seul** pas d'annulation.

**Restaurer** = réécrire **seulement les blocs dont le texte diffère** de l'état
courant, avec la fonction que la garde emploie déjà. **Le curseur se restaure
aussi** (bloc + offset) : une annulation qui laisse le curseur ailleurs désoriente.

**Le rétablissement** (`Ctrl+Maj+Z`) est gratuit une fois la pile là. Toute frappe
neuve après une annulation **coupe la branche de rétablissement** — comportement
attendu partout, et il faut le dire.

### A.4 `Ctrl+S` — trois obstacles dans le code, et le flux

**Les trois obstacles, vérifiés le 28 août 2026 :**

1. **`keyboard.js:392` ignore tout ce qui porte Ctrl, Meta ou Alt** :
   `if (evenement.ctrlKey || evenement.metaKey || evenement.altKey) return;`.
   `Ctrl+S` n'atteint donc **jamais** l'application. Il faut une exception
   explicite, **avant** cette ligne.
2. **`preventDefault()` est obligatoire** — c'est le raccourci « enregistrer la
   page » du navigateur.
3. **Il reste TROIS écouteurs `keydown` au niveau document** — `keyboard.js:373`,
   `lecteur_audio.js:409`, `user_menu.js:52`. Celui de `marginalia.js` a été
   fusionné dans la cascade le 29 août (§ A.6) ; **`user_menu.js` porte encore le
   même défaut** : menu ouvert + éditeur ouvert, un seul `Échap` ferme les deux.
   La table du § 4.4 doit être lue par tous, ou ils doivent fusionner.

**Le flux — sa moitié SERVEUR est en place depuis le 24 août ; sa moitié client
n'existe pas, et son premier pas est justement l'obstacle n° 1 ci-dessus :**

```
Ctrl+S → preventDefault
       → sérialiser : lire l'ÉLÉMENT INTERNE du bloc, retirer .actions-element
         (mesuré sur le vrai DOM : 189/189 exacts ; lire le .corps donne 0/189,
          les blancs du gabarit ET le mot « corriger » des boutons y entrent)
       → POST /elements/corriger_en_lot/
       → le compte rendu HTML (role="status" aria-live="polite") + un toast
```

**Trois points de conduite, chacun tiré d'une mesure :**

- **un état d'attente visible** : le lot prend **295 ms** au plancher et **~1,2 s**
  pour une session ordinaire — assez pour qu'on croie que rien ne s'est passé ;
- **`Ctrl+S` est désarmé pendant l'envoi**, sinon deux lots se chevauchent — et le
  § 12.8 exige déjà un test de concurrence ;
- **après un enregistrement réussi, la pile d'annulation est CONSERVÉE**, seul le
  drapeau « modifié » retombe. Annuler après avoir enregistré redevient une
  modification en attente : cohérent, et sans perte.

### A.5 Ne pas perdre ce qui n'est pas enregistré

`beforeunload` **et** les navigations HTMX internes, qui ne le déclenchent pas. Le
§ 7.4 le demandait déjà ; il est répété ici parce que c'est le même geste que
`Ctrl+S`, vu de l'autre côté.

### A.6 ✅ L'obstacle est levé — 29 août 2026

Cette section demandait de traiter le **second** écouteur `Échap` de
`marginalia.js` avant la première ligne du mode. **C'est fait**, et par la fusion,
pas par la neutralisation : cet écouteur était le jumeau du bouton « Annuler », donc
une fonction vivante qu'il fallait garder.

**Le danger n'était pas que futur**, et c'est la mesure qui l'a montré : avec le
drawer ouvert par-dessus un éditeur de correction, **un seul `Échap` fermait les
deux** et jetait la correction en cours de frappe.

`marginalia.js` ne porte plus **aucun** écouteur clavier — un test l'épingle. La
cascade de `keyboard.js` appelle `window.marginalia.fermerEditeurEnPlace()` à un
rang **après** le drawer : un panneau ouvert par-dessus le texte se ferme d'abord.
**Le mode d'édition prendra son propre rang au-dessus de celui-ci.**
→ `CHANGELOG/2026-08-29-un-seul-ecouteur-echap.md`

### A.7 Ce que cet addendum ne décide pas

- **la borne de la pile** — 100 pas font 5,5 Mo ; le chiffre est au mainteneur ;
- **le raccourci de rétablissement** — `Ctrl+Maj+Z` ou `Ctrl+Y`, à mettre dans la
  table du § 4.4, jamais en dur ;
- **si l'annulation doit franchir un enregistrement**, c'est-à-dire annuler un lot
  déjà écrit en base. La réponse simple est **non** : la pile est celle de la
  session à l'écran, et le journal `PageEdit` est l'autre histoire, celle du
  serveur. Les mélanger demanderait un endpoint d'annulation de lot, que personne
  n'a demandé.

---

## Addendum B — corriger un bloc MASQUÉ

**29 août 2026.** Ni le § 5.3 ni le § 7.3 ne disaient ce qu'un lot doit faire d'un
bloc **déjà masqué** dont le client envoie du **texte non vide**. Le code, lui, le
faisait — et il le faisait mal. Ce trou s'écrit avant de se recoder.

### B.1 Ce que cela coûtait, mesuré

`demasquer_un_element` ne rattache ses portions **que si le texte n'a pas bougé
depuis le masquage** : il compare l'empreinte du **texte brut** notée au masquage à
l'empreinte actuelle. C'est une garde saine — des offsets pris sur un texte qui a
changé ne désignent plus rien de sûr.

Mais un lot qui corrige un bloc masqué passe **entre les deux**. Mesuré le 29 août,
sur un élément de la page 19 portant **3 portions**, en transaction annulée :

| | rattachées au démasquage | laissées détachées |
|---|---|---|
| masquer → démasquer | **3** | **0** |
| masquer → **corriger** → démasquer | **0** | **3** |

**Les trois ancres sont perdues définitivement, et rien ne le dit.** Le compte rendu
annonçait même « 1 bloc modifié » — pour un bloc que le champ n'affiche pas.

### B.2 La décision : le bloc est REFUSÉ, et le refus se nomme

**Un lot qui envoie du texte non vide pour un bloc masqué voit ce bloc refusé**, lui
seul, avec son motif dans la liste du § 7.4. Trois raisons :

1. **Le client ne devrait jamais l'envoyer.** En mode édition, un élément masqué est
   rendu comme un **placeholder** (`.element-masque`), pas comme un bloc modifiable.
   Recevoir du texte pour lui signifie que la vue du client est **périmée** — un
   tiers a masqué ce bloc pendant la session. C'est exactement le cas que le § 7.4
   traite déjà pour un bloc disparu : on refuse **ce bloc**, et lui seul.
2. **Accepter romprait une garantie**, en silence, et pour toujours : le masquage
   promet d'être réversible, et cette correction-là le rend irréversible.
3. **Démasquer à sa place serait décider à sa place.** Le § 3 refuse déjà qu'une
   machine prenne une décision de sens. « Cet utilisateur voulait sûrement le
   restaurer » en est une.

### B.3 Ce que le refus n'est PAS

**Ce n'est pas un refus de vider.** Un bloc masqué dont le client envoie du texte
**vide** reste un **non-geste** : rien n'est écrit, rien n'est compté, aucun journal.
C'était déjà la règle depuis le 29 août, et elle ne change pas.

**Ce n'est pas un refus de corriger un bloc qu'on vient de vider.** Dans une même
session, vider puis re-remplir avant d'enregistrer ne masque jamais rien : on
compare **l'état** au `Ctrl+S`, pas les frappes (§ 5.3, cas 2). Le bloc n'a jamais
été masqué en base, donc rien ne le refuse.

### B.4 Ce que cela laisse ouvert

**Le mode ne sait toujours pas démasquer** (§ 5.3, cas 4). Un utilisateur qui veut
rendre un bloc masqué à la lecture doit sortir du mode et passer par le bouton
« démasquer » du mode structure. Ce refus-ci rend le manque plus visible : la seule
manière de « corriger un bloc masqué » est de le démasquer d'abord, puis de le
corriger. C'est cohérent, et c'est un aller-retour de trop.
