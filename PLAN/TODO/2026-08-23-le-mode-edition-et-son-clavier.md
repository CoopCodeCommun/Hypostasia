# Le mode édition et son clavier

**Décidé par le mainteneur le 23 août 2026. Rien n'est codé.**

> **📘 La spec fait foi désormais.**
> `PLAN/specs/SPEC-edition-par-blocs-et-stenotypie.md` (23 août 2026) absorbe cette
> note. Celle-ci garde ses **mesures** et son historique de décision ; en cas de
> désaccord, c'est la spec qui compte — sauf sur le choix de la voie technique, que
> le prototype tranche.

Dépend de `2026-08-23-les-deux-gestes-manquants-de-l-edition-par-blocs.md`, qui
porte les deux endpoints qui manquent au back.

> **⚠️ Cette voie est le REPLI — 23 août 2026, au soir.**
> Le prototype a rendu ses chiffres :
> `CHANGELOG/2026-08-23-le-champ-unique-tranche-l-edition-par-blocs.md`. **C'est
> l'option C — le champ unique — qui est instruite**, et cette note-ci n'est plus
> la première à coder. Elle n'est pas morte pour autant : elle fait **autre chose**
> (sélectionner des blocs *entiers*, garder `scinder`/`fusionner` au clavier), et
> elle garde un avantage que rien n'a mesuré mais que la structure impose — **son rayon de dégât**. Sous C, une session
> couvre la note entière : un `lectureReload` déclenché par le `masquer` d'un
> collègue efface **tout** le travail ; ici, on ne perdrait que le bloc en cours.
> **Y revenir si l'un des six coûts de C est refusé.**


## Le besoin

Deux usages intensifs, aujourd'hui pénibles au clavier comme à la souris :

- **corriger une transcription** — couper un tour de parole en deux, en recoller
  deux, corriger un mot, changer un locuteur, le tout en écoutant ;
- **nettoyer une ingestion Docling** — retirer les en-têtes, pieds de page,
  numéros et bandeaux de cookies qu'un PDF ou une capture web ramène avec le texte.

Dans les deux cas le geste est répété des dizaines de fois de suite. C'est ce
régime-là que le front actuel ne sert pas.

## Ce que le code fait aujourd'hui

**Le back est déjà bon, et il n'est pas en cause.** `ElementDocument` porte un
`identifiant_stable` (UUID, `unique`, « ne change jamais, même après scission ou
fusion »), un `ordre` renumérotable, un `label`, un `texte`, et une `provenance`
qui sait d'où vient le bloc — ~~`{start_time, end_time, voice}`~~ **`{locuteur,
debut, fin}`** pour l'audio (⚠️ **corrigé le 23 août 2026** : les trois clés barrées
n'existent nulle part, et c'est ce contrat mort qui faisait garder le mauvais
locuteur à la fusion de deux tours —
`CHANGELOG/2026-08-23-la-fusion-de-deux-tours-gardait-le-mauvais-locuteur.md`),
`{page_no, boites}` pour le PDF. `ElementViewSet` porte cinq gestes avec leurs
verrous : verrou de **ligne** pour `corriger` et `masquer`, verrou de **page** pour
`scinder` et `fusionner_avec_le_suivant`, qui renumérotent toute la page.

C'est, à l'imbrication près, le modèle de bloc des éditeurs modernes — et avec la
provenance physique en plus.

**Le front, lui, en est loin.**

- **Le « mode structure » est une bascule d'affichage, pas un mode d'édition.**
  `basculerModeStructure()` (`front/static/front/js/hypostasia.js:472`) pose
  `.mode-structure` sur `#zone-lecture` ; le CSS révèle les boutons. Le clavier ne
  change pas de sens, aucun raccourci ne s'active.
- **Chaque geste passe par un bouton HTMX, un par bloc**
  (`front/templates/front/includes/_actions_element.html`).
- **`masquer` et `fusionner_avec_le_suivant` portent un `hx-confirm`** : nettoyer
  trente blocs, c'est trente boîtes de dialogue.
- **Chaque opération recharge toute la page.** L'écouteur `lectureReload`
  (`hypostasia.js:479`) fait un `fetch('/lire/<id>/')`, parse la réponse, retire les
  divs OOB, remplace `zoneLecture.innerHTML`, rappelle `htmx.process()`, puis
  **resynchronise le bouton et rend le focus à la main** — le code compense déjà ce
  que le rechargement casse. Sur une transcription de deux cents tours, corriger un
  mot repaie tout le rendu.
- **Aucune sélection multiple** : toutes les actions sont `detail=True`, une par
  élément.

Ce qui existe et qu'il faut réutiliser, en revanche :

- **`keyboard.js` est « le SEUL listener keydown de l'application »**, avec dix
  raccourcis, une cascade d'Échap, une modale d'aide (`?`), et la garde
  `estDansChampSaisie()` qui neutralise tout dans un champ. **Le mode édition passe
  par lui, jamais par un second listener.**
- **`lecteur_audio.js`** suit déjà le tour de parole en cours
  (`elementDuTourCourant`) et porte ses propres touches : ←/→ ±5 s, Home, End.

## Ce qui est décidé

**1. Deux modes distincts** — pas une bascule d'affichage. En mode édition, le
clavier change de sens et Échap sort. Le mode doit **se voir** : un mode invisible
qui capture le clavier est une source classique de confusion, et le projet a déjà
tranché une fois dans ce sens (les onglets sans adresse, remplacés le 21 août par
des écrans adressables).

**2. Sélection contiguë uniquement** — `Maj+↑/↓` et `Maj+clic` étendent une plage.
Pas de `Ctrl+clic`, pas de sélection discontinue.

**3. Premier jet YAGNI.** Un seul geste de lot : **masquer**. Pas de fusion en lot —
elle touche aux ancres et renumérote la page, c'est un tout autre risque.

## Les gestes du mode édition

| Touche | Geste | Endpoint |
|---|---|---|
| `↑` `↓` | bloc précédent / suivant | — |
| `Entrée` au milieu du texte | couper ici | `scinder` — existe |
| `Retour arrière` en début de bloc | recoller au précédent | `fusionner_avec_le_suivant` — existe |
| `Échap` | sortir du bloc, puis sortir du mode | — |
| `Maj+↑` `Maj+↓`, `Maj+clic` | étendre la sélection (contiguë) | — |
| `Suppr` sur une sélection | masquer le lot | **à créer** |
| `Ctrl+Z` | annuler le dernier geste | `demasquer` — existe |

**Ces sept lignes tombent exactement sur les verbes du back.** On ne conçoit pas un
modèle d'édition : on branche un clavier sur celui qui existe.

## Trois changements de posture, et pourquoi

**L'annulation remplace la confirmation.** Masquer est déjà réversible —
`demasquer` existe, et les blocs masqués gardent un placeholder visible en mode
structure. Un toast « 30 passages masqués — annuler » vaut mieux que trente
`hx-confirm`. C'est la règle du projet : un refus doit être bruyant, un geste
réversible n'a pas à l'être.

**Le swap devient ciblé.** Le back rend déjà des partials par élément
(`formulaire_correction`, `formulaire_scission`) ; il manque un partial de **bloc
rendu**, pour remplacer le bloc touché au lieu de la page. Ça supprime d'un coup le
coût du rendu, la perte de défilement, et la resynchronisation du focus faite à la
main.

**Le lot se dit.** Un masquage groupé doit rendre **un compte** — jamais un silence.
C'est la même règle que le `--maximum` de la passe de nuit : « ce qui est écarté par
cette borne est COMPTÉ ».

## Ce qui reste à trancher

1. **Le transport audio pendant la frappe.** `Espace` = lecture/pause est le
   standard des outils de transcription, et il entre en collision frontale avec la
   saisie de texte. Touche modifiée (`Ctrl+Espace`) ? Une autre touche ?
   `estDansChampSaisie()` est déjà l'endroit exact où ça se décide.
2. **Comment le mode se voit.** Une classe et un bouton `aria-pressed` suffisent-ils,
   ou faut-il une bordure, un bandeau, une adresse (`/lire/<id>/editer/`) ?
   Une adresse rendrait le mode partageable et « précédent »-able, comme les deux
   écrans d'accueil du 21 août.
3. **Que devient la sélection après un geste ?** Masquer trente blocs fait
   disparaître la plage : le curseur se pose-t-il sur le bloc suivant, ou sur le
   premier placeholder ?
4. **La garde d'édition.** `hypostasis_extractor/services/garde_edition.py` bloque
   toute édition pendant qu'une analyse tourne sur la page — décision saine (« une
   analyse dure quelques minutes, une édition peut attendre »). En mode édition
   soutenue, ce refus doit être **visible à l'entrée du mode**, pas découvert au
   trentième geste.

## Ce qu'il faut mesurer

- **Aucun appel LLM n'est requis** : rien ici n'appelle un modèle. **Pas de
  `make test-llm`, pas de facture.**
- **Des tests E2E (Playwright)**, parce que c'est du clavier et du DOM : les tests
  pytest ne peuvent pas exécuter de JavaScript. À couvrir : l'entrée et la sortie du
  mode, chaque raccourci, l'extension de sélection, l'annulation, et le fait que le
  mode ne capture **rien** quand le focus est dans un champ.
- **Fixtures étalons à écrire** : une note de transcription à plusieurs dizaines de
  tours et plusieurs locuteurs, et une ingestion Docling avec ses en-têtes et pieds
  de page — sans elles, on teste le clavier sur trois blocs, c'est-à-dire sur le seul
  cas qui marchait déjà.
- **Une mesure avant/après** du coût d'un geste : le rechargement actuel refait tout
  le rendu de la zone, le swap ciblé un seul bloc. Le chiffre n'a pas encore été pris.

## Ce qui casse si on ne fait rien

Rien ne casse : le nettoyage d'une ingestion et la correction d'une transcription
restent faisables — bloc par bloc, confirmation par confirmation, rechargement par
rechargement. C'est le travail que personne ne fait, et une transcription non
corrigée produit des extractions sur du texte faux.

## Coût de mise en œuvre

Le clavier dans `keyboard.js` et un partial de bloc rendu : deux à trois jours, plus
les tests E2E. Les deux endpoints manquants sont chiffrés dans leur propre note.
