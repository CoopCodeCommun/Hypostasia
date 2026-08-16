# R5 : LE PANNEAU CESSE DE RECOUVRIR LA BARRE (fixture d'extractions sans LLM, geometrie de l'etalon, toast sombre)

**Date :** 2026-08-12
**Migration :** Non

**Quoi / What :** trois defauts mesures au navigateur, corriges et
verrouilles par des tests qui MESURENT plutot qu'ils ne lisent le DOM —
c'etait la geometrie qui etait fausse, pas la structure. / Three
browser-measured defects, locked by tests that measure geometry.

Spec : `docs/superpowers/specs/2026-08-12-ossature-lecteur-etalon-design.md`

### D'ABORD, DE QUOI STYLER : `charger_extractions_demo`

La base portait six notes, 670 elements et **zero extraction**. Le
panneau affichait « 0 extractions » : il n'y avait rien a mettre au
point. Lancer une vraie analyse coute un appel facture, ne se rejoue
pas, et ne garantit aucun des cas limites que la maquette dessine.

`front/management/commands/charger_extractions_demo.py` pose 12 idees a
la main, **sans aucun appel LLM** — 13 ancrages, 5 commentaires, sur
trois notes etalons. Elle couvre expres : les 8 familles d'hypostases,
les deux statuts, deux idees **superposees** sur un meme element
(marques imbriquees), une idee qui **enjambe** deux elements, une ancre
sur un `table`, des ancres sur tours de parole audio, et des cartes a
0, 1 et 2 commentaires.

Les positions ne sont jamais ecrites en dur : chaque portion declare un
fragment litteral, la commande le cherche dans le texte de l'element et
en deduit les bornes. Fragment introuvable → elle **leve**. Une ancre
fausse produit un surlignage decale que rien ne signale ; mieux vaut un
echec bruyant.

Verifie a l'ecran : le moteur d'ancrage produit bien 7 `<mark>` sur le
paragraphe de la note 9, dont trois issues du decoupage d'une
superposition (`data-superposition="1"` et `"2"`).

### LE PANNEAU RECOUVRAIT LA BARRE D'OUTILS

Mesure du 12 aout, fenetre de 1600px : le panneau partait de `y=0` avec
un `z-index` de 70 ; la barre d'outils vit a `y=0` avec un `z-index` de
30. Le panneau la **recouvrait sur ses 576 derniers pixels** — la barre
s'arretait visuellement a `x=968`, « Dashboard », « Analyses » et
l'avatar disparaissaient dessous.

L'entree R4 de la veille annoncait un « panneau integre » : il l'etait
en largeur rendue au texte, pas en empilement. Un panneau qui mange la
barre d'outils n'est pas integre, il flotte plus discretement.

Trois declarations, sous le seuil de 1400px de l'etalon : `top:
var(--barre-outils)`, `width: var(--panneau)` — 23rem, soit 368px au
lieu de 576 — et `z-index: 67`.

**Ce qui protege la barre, c'est le `top`, pas le z-index.** Une
premiere version descendait aussi le panneau a `z-index: 20`, « sous la
barre » : elle l'a fait passer sous le FIL D'ARIANE, `sticky` a z-index
66 et large de toute la zone de lecture. `elementFromPoint` dans le
panneau rendait `#fil-ariane`, dont la bande masquait le haut des
cartes. Regression trouvee au navigateur le jour meme, verrouillee par
un test qui interroge `elementFromPoint`. La barre occupe y=0..48 et le
panneau commence a 48 : ils ne se recouvrent plus, leur ordre
d'empilement n'a plus a arbitrer entre eux.

**Deux tokens manquaient sur `:root`.** `--panneau` et `--barre-outils`
n'existaient nulle part : la largeur du panneau etait ecrite DEUX fois —
`min(36rem, 100vw)` dans le style inline du gabarit, et la meme
expression recopiee dans la compensation de la zone de lecture. Les deux
copies etaient d'accord (576px, et 576 + 2rem de respiration) ; c'est la
DUPLICATION qui posait probleme, pas une divergence — toute correction
de l'une devait etre reportee a la main sur l'autre. Elles derivent
desormais du meme token.

### UN TABLEAU FAISAIT DEFILER TOUTE LA PAGE

Les tableaux sortent du service en `<pre>` (ecart n°6 de l'etalon, non
comble). Celui du PDF etalon mesurait **3 162px** et poussait la zone de
lecture a 3 419px pour 1 586 de large : une barre de defilement
horizontale sous un texte de lecture.

`overflow-x: auto` **et** `min-width: 0` sur la piste de corps. La
seconde n'est pas decorative : dans une grille, un `1fr` a un
`min-width: auto` implicite qui le laisse grandir a la taille de son
contenu — sans elle, la boite aurait grandi avec le `<pre>` et le
defilement interne n'aurait jamais eu lieu.

### LE TOAST NE SE DETACHAIT PAS, EN SOMBRE

    texte du toast   rgb(236, 234, 228)
    fond du toast    rgb(22, 21, 26)
    fond de la page  rgb(22, 21, 26)   <- le MEME
    bordure          0px none
    ombre            noire a 18 %, invisible sur du noir

Le contraste du TEXTE etait excellent — 14,8:1 — et c'est ce qui a
trompe : aucune mesure d'accessibilite ne signalait quoi que ce soit.
Mais un rectangle sans contour, pose sur un fond identique au sien,
n'est pas percu comme un objet. On lisait son message superpose au
panneau sans voir que c'en etait un.

Fond `--papier-creux`, contour `--filet-controle`, ombre plus dense.
Contours mesures : **4,13:1 en sombre, 3,28:1 en clair** (WCAG 1.4.11
demande 3:1 quand le contour est le seul indice de la limite).

### L'EN-TETE DE LA MAQUETTE ETAIT PERIME

Quatre des sept ecarts annonces dans `maquette.html` ne tenaient plus.
Le tableau est reecrit avec l'etat verifie au navigateur, et porte
desormais la consigne de le remettre a jour a chaque correction — une
carte fausse a deja fait repartir une session sur de mauvaises bases.

Restent vrais : le lecteur audio (0 balise `<audio>`, verifie sur la
note 8), les tableaux en `<pre>`, et la progression WebSocket — celle-la
non par retard mais par **decision contraire** : `front/consumers.py:3`
dit « Refonte A.6 : un seul consumer minimal, pas de progression
streaming ».

### LES TESTS E2E N'ETAIENT PAS CASSES, IL LEUR MANQUAIT UNE VARIABLE

La passation annoncait 21 tests e2e en echec permanent. Ils echouaient
en `setUpClass` faute de `PLAYWRIGHT_BROWSERS_PATH` dans
l'environnement du conteneur — les navigateurs, eux, sont bien
installes. Avec la variable, la suite passe. A poser dans
`docker-compose.yml`.

```bash
docker exec -w /app -e PLAYWRIGHT_BROWSERS_PATH=/home/hypostasia/.cache/ms-playwright \
  hypostasia_web uv run python manage.py test front.tests.e2e
```

### ET DEUX MODULES E2E NE TOURNAIENT JAMAIS

`front/tests/e2e/__init__.py` importe ses modules UN PAR UN. Un fichier
absent de cette liste n'est jamais collecte par `manage.py test
front.tests.e2e`, et **rien ne le signale** : la suite annonce
fierement « OK » sur les modules qu'elle connait.

`test_14_visibilite` et `test_17_filtre_contributeur` en manquaient :
**15 tests ecrits, jamais executes**. Verifies avant de les ajouter —
les 15 passent. Les deux nouveaux modules de cette session y sont
egalement inscrits ; sans cela, ils auraient rejoint les orphelins.

Le symptome qui a mis sur la piste : la suite annoncait « Ran 104 »
avant ET apres l'ajout de huit tests.

**Suite e2e apres cette session : 129 tests, OK** (104 d'origine + 15
rendus a la collecte + 10 nouveaux), plus les 22 tests unitaires de
`charger_extractions_demo`.

### LA RELECTURE ADVERSE A RATTRAPE UN CRITIQUE

`text_readability` est **VIDE** sur les pages ingerees par le moteur
element — longueur 0 sur les notes « Etude epistemologique » et
« Badgeons la Normandie ». La commande y cherchait la position de
l'extraction et retombait sur 0 en cas d'echec : NEUF extractions sur
douze portaient `start_char = 0`. Le tri « Position » du panneau mentait
et tout clic sur une carte renvoyait en tete de document.

Le silence etait exactement ce que la docstring de la commande pretend
interdire deux paragraphes plus haut. Les positions sont desormais
RECONSTRUITES depuis les elements — douze valeurs distinctes, verifiees.
Et le test qui aurait du le voir construisait un `text_readability`
complaisant : le decor de test etait plus favorable que la production.

Trois autres defauts de la meme relecture :

- les commentaires de demonstration etaient poses sous le COMPTE REEL du
  mainteneur (`get_or_create(username="jonas")` a trouve le sien). Ils
  passent sous `demo_*`, inactifs et sans mot de passe utilisable ;
- un fragment ambigu — present deux fois dans le meme element —
  s'ancrait sur la premiere occurrence, au hasard de l'ecriture. La
  commande LEVE desormais ;
- deux defauts d'affichage mesures en plus : un mot insecable long
  faisait defiler la page comme le tableau (`overflow-wrap: anywhere`),
  et le panneau tronquait de 240px le menu deroulant « Dashboard »
  (defaut preexistant : le panneau etait deja au-dessus).

### DEUX CHIFFRES QUI ETAIENT RACONTES, PAS MESURES

Corriges partout ou ils avaient ete recopies :

- **la « divergence 576 / 608 »** n'a jamais existe. 608 = 576 + 2rem,
  ecrit dans la meme expression : les deux valeurs derivaient deja du
  meme `min(36rem, 100vw)`. C'etait une DUPLICATION, pas une derive ;
- **le fond « franchement distinct » du toast** ne fait que 1,09:1 en
  sombre. Il ecarte la coincidence exacte des deux couleurs, rien de
  plus. C'est le CONTOUR qui detache le toast.

Et toutes les references `maquette.html:NNN` de cette session etaient
fausses de +38 lignes, decalees par la reecriture de l'en-tete — dans le
fichier meme qui prescrit de tenir ces reperes a jour. Elles designent
desormais des sections, pas des numeros de ligne.

### CE QUI RESTE OUVERT

**La colonne de lecture n'est pas centree comme l'etalon.** Le bloc fait
bien 742px — la largeur de l'etalon — mais son centre tombe 42px a
gauche du centre de l'espace disponible, contre 13px dans la maquette.
L'etalon decale son EN-TETE vers la droite (`padding-left: calc(var(--gouttiere)
+ 1.5rem)`) ; le produit tire son CORPS vers la gauche par des marges
negatives. Les deux alignent titre et texte, un seul centre l'ensemble.
Non corrige : le CSS concerne est explicitement argumente par la session
du 9 aout, l'arbitrage revient au mainteneur.

**Le panneau reste `fixed`** la ou l'etalon le veut `sticky` dans une
grille. Ecart de moyen, pas de rendu : la geometrie mesuree est celle de
l'etalon.

---

> Session du 12 août 2026. Objectif posé par le mainteneur : « un design
> presque pixel perfect avec la maquette ».
> LOCALISATION : `A TESTER et DOCUMENTER/panneau-integre-fixture-extractions-toast.md`
> Spec : `docs/superpowers/specs/2026-08-12-ossature-lecteur-etalon-design.md`

## Ce qui a été fait

### 1. `charger_extractions_demo` — des cartes à styler

`front/management/commands/charger_extractions_demo.py`. La base portait
six notes, 670 éléments et **zéro extraction** : le panneau affichait
« 0 extractions » et il n'y avait rien à mettre au point.

La commande pose à la main, **sans aucun appel LLM**, 12 idées sur trois
notes étalons — 13 ancrages, 5 commentaires. Elle couvre exprès ce que la
maquette dessine : les 8 familles d'hypostases, les deux statuts, deux
idées **superposées** sur un même élément (marques imbriquées), une idée
qui **enjambe** deux éléments, une ancre portée par un `table`, des
ancres sur tours de parole audio, et des cartes à 0, 1 et 2 commentaires.

Les positions ne sont **jamais** écrites en dur : chaque portion déclare
un fragment littéral, la commande le cherche dans le texte de l'élément
et en déduit les bornes. Si le fragment a disparu, elle **lève** au lieu
d'ancrer à côté — une ancre fausse produit un surlignage décalé que rien
ne signale.

### 2. Le panneau ne recouvre plus la barre d'outils

`front/static/front/css/maquette.css`. Mesuré au navigateur le 12 août,
fenêtre de 1600 px : le panneau partait de `y=0` avec un `z-index` de 70,
la barre d'outils vit à `y=0` avec un `z-index` de 30. Le panneau la
**recouvrait sur ses 576 derniers pixels** — la barre s'arrêtait
visuellement à `x=968`.

Trois déclarations, sous le seuil de 1400 px de l'étalon : le panneau
commence sous la barre (`top: var(--barre-outils)`), prend la largeur de
l'étalon (`width: var(--panneau)`, 23rem = 368 px au lieu de 576) et
reste au-dessus du fil d'Ariane dans l'ordre d'empilement
(`z-index: 67`). **C'est le `top` qui protège la barre, pas le z-index** :
une première version descendait le panneau à `z-index: 20` et l'a fait
passer sous le fil d'Ariane (`sticky`, `z-index: 66`, pleine largeur), dont
la bande masquait le haut des cartes. Régression trouvée au navigateur le
jour même, verrouillée par un test qui interroge `elementFromPoint`.

Deux tokens de géométrie manquaient sur `:root` — `--panneau` et
`--barre-outils`. La largeur du panneau était écrite **deux fois** :
`min(36rem, 100vw)` en style inline, et la même expression recopiée dans
la compensation. Les deux copies étaient d'accord (576 px, et 576 + 2rem
de respiration) — c'est la duplication qui posait problème, pas une
divergence. Elles dérivent désormais du même token.

### 3. Les tableaux ne font plus défiler la page

Les tableaux sortent du service en `<pre>` (écart n°6 de l'étalon, non
comblé). Celui du PDF étalon mesurait **3 162 px** et poussait la zone de
lecture à 3 419 px pour 1 586 de large : une barre de défilement
horizontale sous un texte de lecture.

`overflow-x: auto` **plus** `min-width: 0` sur la piste de corps : dans
une grille, un `1fr` a un `min-width: auto` implicite qui le laisse
grandir à la taille de son contenu — sans la seconde déclaration, la
boîte aurait grandi avec le `<pre>` et le défilement n'aurait jamais eu
lieu.

### 4. Le toast se détache, en sombre comme en clair

Mesure reproduite : texte `rgb(236,234,228)`, fond `rgb(22,21,26)` —
**identique au fond de page** —, bordure `0px none`, ombre noire à 18 %
invisible sur fond noir.

Le contraste du texte était excellent (14,8:1), et c'est ce qui a trompé.
Un rectangle sans contour, sur un fond identique au sien, n'est pas perçu
comme un objet : on lisait son message superposé au panneau sans voir que
c'en était un.

**C'est le contour qui fait le travail.** Le fond passe à `--papier-creux`,
mais soyons exact : en sombre, `#1e1d23` contre `#16151a` ne donne que
**1,09:1** — il écarte la coïncidence exacte, rien de plus. Ce qui détache
réellement le toast, c'est le contour au filet renforcé
`--filet-controle` : **4,1:1 en sombre, 3,3:1 en clair**, là où WCAG
1.4.11 demande 3:1. L'ombre, plus dense, aide en clair et reste
secondaire en sombre.

### 5. L'en-tête de la maquette remis à jour

Quatre des sept écarts annoncés dans `maquette.html` étaient périmés. Le
tableau est réécrit avec l'état vérifié au navigateur le 12 août.

### 6. Deux modules e2e ne tournaient jamais

`front/tests/e2e/__init__.py` importe ses modules un par un. Un fichier
absent de la liste n'est **jamais collecté**, et rien ne le signale.
`test_14_visibilite` et `test_17_filtre_contributeur` en manquaient :
15 tests écrits, jamais exécutés. Vérifiés (les 15 passent) puis
ajoutés, avec les deux modules de cette session.

Le symptôme qui a mis sur la piste : la suite annonçait « Ran 104 »
avant **et** après l'ajout de huit tests.

## Tests à réaliser

### Suites automatiques

```bash
# La fixture — 22 tests
docker exec -w /app hypostasia_web uv run python manage.py test \
  front.tests.test_charger_extractions_demo

# Le panneau et le toast — 12 tests e2e
# ATTENTION : sans PLAYWRIGHT_BROWSERS_PATH, tous les e2e echouent en setUpClass.
docker exec -w /app -e PLAYWRIGHT_BROWSERS_PATH=/home/hypostasia/.cache/ms-playwright \
  hypostasia_web uv run python manage.py test \
  front.tests.e2e.test_18_panneau_integre front.tests.e2e.test_19_toast_sombre
```

**Une suite à la fois** : deux `manage.py test` en parallèle se détruisent
la base de test.

### Charger les extractions sur la base de dev

```bash
docker exec -w /app hypostasia_web uv run python manage.py charger_extractions_demo --a-blanc
docker exec -w /app hypostasia_web uv run python manage.py charger_extractions_demo
# Pour repartir de zéro (ne touche QUE les jobs de démonstration) :
docker exec -w /app hypostasia_web uv run python manage.py charger_extractions_demo --reset
```

Attendu : `12 extraction(s) en base, 13 ancrage(s), 5 commentaire(s).`

### Vérifications à l'œil

Sur <https://h.localhost/lire/9/>, fenêtre large (> 1400 px) :

1. La barre d'outils va d'un bord à l'autre — « Dashboard », « Analyses »,
   « Importer » et l'avatar sont visibles à droite, **pas** cachés sous le
   panneau.
2. Le panneau fait 368 px et commence sous la barre.
3. Aucune barre de défilement horizontale, malgré les deux tableaux.
4. Le tableau défile, lui, à l'intérieur de sa propre boîte.
5. Le bouton × replie le panneau ; le texte se recentre.
6. Sous 1400 px, le panneau redevient un tiroir large avec son voile.
7. Au survol d'un paragraphe, les marques se révèlent en gris ;
   « irréductibles aux six formes canoniques » porte une marque imbriquée
   (deux idées superposées).
8. En mode sombre, un toast se détache nettement de la page.

## Enquête demandée : pourquoi aucun analyseur après la fixture

**Constat mesuré** sur la base de dev, après `charger_fixtures_sample` :

```
analyseurs : 0    versions : 0    prompts : 0    exemples : 0    modèles IA : 0
```

À l'écran, sur une note sans extraction : « Aucune analyse pour cette
page » + un bouton « Lancer une analyse » qui n'ouvre **aucun sélecteur
d'analyseur** — la liste des options se réduit au tri (« Position »,
« Activité récente »).

**La cause.** Les analyseurs sont créés par `charger_fixtures_demo`, dans
sa méthode `_creer_modeles_ia_et_analyseurs()` (ligne 822) : modèle IA
Mock, activation de la configuration, analyseur « Hypostasia »
(`type_analyseur="analyser"`) avec ses 4 `PromptPiece` et ses exemples,
puis l'analyseur de synthèse (`type_analyseur="synthetiser"`) avec ses 3
pièces.

`charger_fixtures_sample`, créée le 11 août sur `dev`, **ne reprend rien
de tout ça**. Son `handle()` enchaîne : propriétaire → réinitialisation →
carnet des étalons → config de transcription → chargement des six
documents → base de démonstration. Les seules occurrences du mot
« analyseur » dans le fichier sont `analyseur_d_arguments`, le parseur
argparse.

**Et oui, c'est bien dans `main`** — mais sous l'autre nom :
`charger_fixtures_sample.py` **n'existe pas sur `main`**. La branche
`main` ne connaît que `charger_fixtures_demo`, `import_demo_debat` et
`reset_demo`. La nouvelle commande est propre à `dev` et n'a pas hérité
de cette partie.

**Pourquoi ça bloque l'analyse.** `_analyseurs_extraction_utilisables()`
(`front/views.py:704`) filtre sur `is_active=True,
type_analyseur="analyser"`, puis écarte tout analyseur sans **au moins un
exemple complet** — un texte source rempli et une extraction avec classe
et texte (`hypostasis_extractor/services/__init__.py:171`). Sans exemple,
LangExtract n'envoie aucun cadre au LLM, qui invente son format et perd
les extractions. Avec zéro analyseur en base, la liste est vide et le
panneau n'a rien à proposer.

**Trois façons de le réparer**, à arbitrer :

1. Extraire `_creer_modeles_ia_et_analyseurs()` dans un service partagé
   (`front/services/fixtures_analyseurs.py`) appelé par les deux
   commandes. Le plus propre ; une seule définition à maintenir.
2. `charger_fixtures_sample` appelle `call_command("charger_fixtures_demo")`.
   Le moins de code, mais elle chargerait aussi les pages Wikipédia et le
   débat fictif, ce que la commande `sample` évite volontairement.
3. Recopier la méthode dans `charger_fixtures_sample`. Rapide, mais deux
   définitions du même analyseur à tenir à jour — et c'est exactement
   ainsi que la première a été oubliée.

Recommandation : **1**. Non implémenté : le choix revient au mainteneur.

## Ce qui reste ouvert

- **La colonne de lecture n'est pas centrée comme l'étalon.** Le bloc fait
  bien 742 px, mais son centre tombe 42 px à gauche du centre de l'espace
  disponible, contre 13 px dans la maquette. L'étalon décale son **en-tête**
  vers la droite ; le produit tire son **corps** vers la gauche par des
  marges négatives. Les deux alignent titre et texte, un seul centre
  l'ensemble. Non corrigé : le CSS concerné est explicitement argumenté
  par une session précédente, et l'arbitrage revient au mainteneur.
- **Le panneau reste `fixed`** là où l'étalon le veut `sticky` dans une
  grille. Écart de moyen, pas de rendu — la géométrie mesurée est
  désormais celle de l'étalon. Le déplacer dans le flux imposerait de
  sortir `#drawer-overlay` de `base.html`, avec le piégeage de focus et le
  JS qui l'ouvre.
- **La carte du panneau — prochain chantier, mesuré le 12 août en sombre.**
  Le panneau lui-même est désormais conforme (fond `rgb(26,25,31)`,
  largeur 368 px, identiques à l'étalon). Les cartes, non :

  | | Étalon | Produit |
  |---|---|---|
  | fond de la carte | `rgb(22,21,26)` | **transparent** |
  | marge basse | 8 px | 2 px |
  | rayon | 5 px | 4 px |

  L'étalon donne à la carte un fond **plus sombre que le panneau**, ce
  qui la détache ; le produit la laisse se fondre dedans. Chantier à
  mener d'un bloc (fond, marges, rayon, et la citation qui ne s'ouvre
  qu'au clic — `maquette.css`, « LA CARTE DU PANNEAU : SOBRE PAR
  DÉFAUT »), pas par retouches successives.
- **Écart n°2, le lecteur audio** : confirmé vrai, 0 balise `<audio>`.
- **Écart n°6, les tableaux en `<table>`** : confirmé vrai. Une décision de
  conception attend le mainteneur — un tableau entier est **un seul**
  `ElementDocument` (~3 000 signes) : découper par ligne, ou assumer le
  bloc ?
- **`PLAYWRIGHT_BROWSERS_PATH` n'est pas dans l'environnement du conteneur.**
  Avec elle, les 104 tests e2e passent. Sans elle, ils échouent tous en
  `setUpClass`. À poser dans `docker-compose.yml` pour de bon.
- **Cinq** gabarits chargent encore `maquette.css?v=22` : `login.html`,
  `register.html`, `mon_token.html`, `invitation_erreur.html` et
  `acces_refuse.html`. Ils serviront une version périmée depuis le cache.

