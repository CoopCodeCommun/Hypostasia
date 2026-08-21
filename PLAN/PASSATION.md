# Passation — le chantier UX/UI

> Document unique de reprise de session. Il fusionne, le 16 août 2026, les deux
> passations qui coexistaient et se contredisaient : `PROMPT-session-suivante.md`
> (13 août, qui faisait foi sur l'état des chantiers) et `PASSATION-ux-ui.md`
> (14 août, qui faisait foi sur l'environnement).
>
> **Chaque chiffre ci-dessous a été mesuré, et porte la date de sa mesure.**
> Ce qui n'a pas été vérifié est dit comme tel. Ne jamais réécrire un chiffre
> sans le remesurer.

---

## 0. Ce qu'il faut savoir en trois phrases

Hypostasia est un outil de **délibération sourcée** : on importe des documents,
un LLM en extrait des « idées », et chaque idée reste **ancrée** au passage
exact dont elle vient — c'est cette ancre qui fait la preuve.

Le moteur d'ancrage est en place et alimenté. Le travail restant n'est plus
d'extraire, mais de **montrer**.

La mission d'origine était, dans l'ordre : le panneau d'extraction, la
gouttière, le lecteur audio, le visualiseur PDF. **Les trois premiers sont
faits.** Il reste le visualiseur PDF, et les proportions à mesurer.

---

## 1. Règles non négociables — à lire avant tout le reste

- **JAMAIS d'opération git.** Ni `commit`, ni `add`, ni `push`, ni
  `checkout --`, ni `stash`, ni `reset`, ni `restore --`, ni `clean`. Le dépôt
  appartient au mainteneur, et le working tree porte régulièrement des heures
  de travail non commité. Une seule commande destructive les efface.
  **Jamais de `Co-Authored-By`** dans quoi que ce soit.
- **JAMAIS `ruff format` ni `ruff check --fix` sur un fichier existant.**
  `format` réécrit des milliers de lignes hors sujet ; `--fix` supprime les
  imports à effet de bord (`@admin.register`, `@receiver`) et fait tomber
  Django au démarrage. Sur fichier neuf uniquement.
- **TDD strict** : le test d'abord, qu'on regarde échouer, puis le code.
- **Relecture adverse par un agent** avant de déclarer une étape finie. Sur la
  session du 13 août elle a rattrapé ce que la relecture ordinaire laissait
  passer : neuf extractions sur douze ancrées à `start_char = 0`, et des
  commentaires de démonstration posés sous le vrai compte du mainteneur.
- **Vérification au navigateur, en clair ET en sombre**, contrastes calculés.
  Ne jamais inventer un chiffre.
- **Un trou de spec s'écrit avant de se coder**, en addendum daté.
- **Un fichier `CHANGELOG/AAAA-MM-JJ-slug.md` par chantier**, résumé au-dessus
  du `---`, comment tester à la main en dessous. Voir `CHANGELOG/README.md`.

### Conventions du dépôt

`viewsets.ViewSet` explicites, jamais `ModelViewSet`. DRF `serializers`, jamais
Django Forms. HTMX pour l'interactivité, jamais de SPA. Commentaires bilingues
français puis anglais sur chaque bloc de logique. Noms de variables verbeux en
français. En-tête `LOCALISATION` en tête de chaque fichier.

---

## 2. L'environnement

Tout tourne dans Docker. **Tout passe par le Makefile, depuis l'hôte** — jamais
depuis l'intérieur du conteneur. `make` seul liste les cibles.

```bash
make install                        # docker compose up -d + bin/install.sh
make dev                            # runserver + les TROIS workers Celery
make status
make restart S=runserver
make logs S=celery_worker_docling
```

Le Makefile n'est qu'une façade : il appelle `bin/install.sh` et
`supervisord-dev.conf`, il ne réimplémente rien. C'est délibéré — deux
descriptions du même démarrage finissent toujours par diverger, et c'est
exactement la panne que ce Makefile existe pour empêcher.

**Le site : https://h.localhost/ — identifiants `jonas` / `admin1234`.** Le
serveur écoute sur le **port 8000, pas 8123** (`nginx/dev.conf` proxie vers
`web:8000` ; sur 8123 on obtient un 502).

**TROIS workers Celery, jamais moins.** Le détail de chacun — sa file, sa
concurrence, et pourquoi le troisième tourne sous `nice -n 19` — est dans
`AGENTS.md`, section « Les invariants ». **Il n'est pas recopié ici** : cette
section l'a porté en double jusqu'au 18 août 2026, et la seconde copie est
devenue fausse le jour où un troisième worker est arrivé. Verrouillé par
`hypostasis_extractor/tests/test_files_celery_ingestion.py` et
`.../test_worker_du_juge_local.py`.

**`uv run` n'apporte rien** : le `PATH` de l'image contient déjà
`/app/.venv/bin` (`Dockerfile:59`), donc `docker exec -w /app hypostasia_web
python manage.py check` fonctionne tel quel. Sous supervisord, `uv run` est
même nuisible — il laisse un process wrapper entre supervisord et le vrai
programme, et le SIGTERM d'arrêt irait au wrapper plutôt qu'au worker qui doit
finir sa conversion.

Le mainteneur travaille dans **byobu**. Les index de panes se renumérotent
quand on en ajoute : **cibler les panes par leur `pane_id` (`%6`, `%8`), jamais
par leur index.**

---

## 3. L'état réel de la base — mesuré le 11 août

| Note | Éléments | Ce qu'elle éprouve |
|---|---|---|
| `capture-web-badgeons-la-normandie.html` | **28** — `section_header` 4 · `list_item` 5 · `text` 19 | les labels de structure d'un HTML réel |
| `PRESENTATION-V3.md` | 549 | un document long |
| `fake_debat_ia_transcription.json` | 12 tours — Laurent, Elinor, Eric | la gouttière audio, locuteurs nommés |
| `audio-…-14s.mp3` | 9 tours — `speaker_1`, `speaker_2` | la chaîne audio complète (Voxtral réel) |
| `Etude_Epistemologique_IA.pdf` | 11 dont **2 tableaux** — 11/11 boîtes | l'ancrage par coordonnées |
| `présentation des open badges.pdf` | 61 — 61/61 boîtes | un PDF réel de 4 pages |

Total : **6 notes, 670 éléments, 72 avec `provenance.page_no` et leurs boîtes.**
Toutes en `ingestion_etat='reussie'`.

Pour repartir d'une base propre : `make install` (idempotent, ~3 min au premier
passage à cause des conversions PDF, **10 s** ensuite). L'installation charge
`charger_fixtures_sample`, puis `charger_extractions_demo` (extractions et
commentaires écrits à la main, sans LLM), puis `analyser_les_notes_etalons`
— cette dernière appelle un **vrai modèle, facturé**. Elle est **idempotente par
défaut** : elle n'analyse que ce qui ne l'est pas encore, donc une relance ne
refacture rien. `--forcer` est son seul flag, et il fait l'inverse.

### La géométrie mesurée (11 août)

| | |
|---|---|
| gouttière, document écrit | **46 px** |
| gouttière, audio | **96 px** |
| gouttière, PDF | 46 px, affiche « p. 1 », « p. 2 » |
| colonne de texte | 672 px |
| boutons « voir la source » | 11 sur le PDF étude, un par élément |

---

## 4. L'étalon

**`front/static/front/maquettes/maquette.html`** — c'est **la seule autorité**.
Servi sur `https://hyp.nasjo.fr/static/front/maquettes/maquette.html` et en
local sur `https://h.localhost/static/front/maquettes/maquette.html`.

> Une copie plus ancienne dormait dans `tmp/maquettes/` et l'index de
> documentation la désignait par erreur comme l'autorité. Elle a été renommée
> `tmp/maquettes-archive-2026-08-11/` le 16 août pour qu'on ne s'y trompe plus.
> Les deux autres maquettes — `corpus.html` et `selection-preuves.html` —
> vivent au même endroit que l'étalon.

**Lire son en-tête avant tout le reste.** Elle distingue deux choses :

- **« RÉFÉRENTIELS TIRÉS DU CODE RÉEL »** — avec les chemins exacts : familles
  d'hypostases (`extractor_tags.py:16-62`), couleurs (`hypostasia.css:48-70`),
  palette des locuteurs (`transcription_audio.py:23-34`), carte d'extraction
  (`_card_body.html`), raccourcis clavier. Ceux-là décrivent l'existant : la
  maquette s'y aligne, pas l'inverse.
- **« CE QUI EST UNE CIBLE, PAS L'EXISTANT »** — les sept écarts numérotés,
  signalés dans la maquette par un bandeau violet `--cible: #7C5CBF`.

**Au 13 août, les sept écarts sont tous résolus ou assumés** — le n°3
(progression en direct) est un écart *assumé*, pas une dette.

L'en-tête porte aussi **« Ce sur quoi le produit s'écarte de cet étalon — par
décision »** : trois arbitrages du mainteneur. **Les lire comme des retards
ferait défaire ses décisions.** C'est l'étalon qui devra évoluer, pas le
produit.

**Tenir ce tableau à jour à chaque ligne touchée.** Une session est déjà
repartie sur une carte périmée, et ça a coûté du travail.

---

## 5. Les chantiers

### 5.1 Le lecteur audio — FAIT le 13 août

Livré, mesuré au navigateur en clair et en sombre, 9 tests e2e
(`test_32_lecteur_audio`, dont deux ajoutés le 14 août avec le retrait) plus 12 tests serveur.

- **La barre** : 62 px, `fixed` en bas, `<audio preload="metadata">` sur
  `page.source_file`, bouton, minutage, rail. Elle ne paraît que si la note est
  un audio **et** qu'un média est attaché — une transcription sans son garderait
  un bouton qui ne joue rien.
- **Le rail** : un segment par tour, à la couleur de son locuteur, opacité
  `.85` quand le tour porte des idées. Cliquable pour se déplacer,
  `role="slider"` avec les flèches au clavier.
- **Le minutage de la gouttière est devenu un bouton** : il *disait* déjà
  l'instant du tour, il ne manquait qu'à pouvoir l'atteindre.
- Le tour entendu se marque dans la marge, et le texte suit l'oreille **pendant
  la lecture seulement** — une page qui bouge toute seule quand on la lit à
  l'arrêt serait insupportable.

**Deux écarts assumés avec l'étalon**, tous deux vers la justesse : les segments
sont positionnés en **absolu** (l'étalon les empile en `flex`, ce qui suppose
des tours contigus — ils ne le sont pas, et chaque segment dériverait de la
somme des silences), et le filet du haut est `--filet` et non le violet
`--cible`, qui marque ce qui n'existe pas encore.

**Corrigé au passage** : le même locuteur portait **deux couleurs** sur le même
écran — bleu dans les pilules et la timeline (palette Tailwind), orange dans la
gouttière (palette de Wong). Les widgets prennent désormais Wong
(`test_couleurs_des_locuteurs`).

#### Ce qui reste ouvert sur l'audio

**Les deux rails : tranché et exécuté le 14 août.** Le mainteneur a demandé de
« retirer la timeline clic-to-scroll du haut et le rail » ; c'est fait, et
verrouillé par `front/tests/test_retrait_timeline_audio.py`.

La mesure qui a précédé le retrait vaut d'être connue, parce qu'elle en change
le sens : les trois dispositifs de PHASE-15 visaient `.speaker-block` et
`#speaker-block-N`, c'est-à-dire le HTML diarisé figé produit à l'ingestion. Les
pages passées au moteur ELEMENT ne sont plus rendues depuis ce HTML mais depuis
leurs `ElementDocument`, en blocs `.bloc` — mesure du 14 août : `speaker-block-`
apparaît **0 fois** dans la page. La timeline cliquait donc dans le vide, les
points d'extraction n'étaient jamais rendus, et le filtre par locuteur ne
masquait aucun texte. **On n'a pas retiré trois fonctions : on a retiré trois
dispositifs qui avaient cessé d'en être.**

**Le seek exige nginx.** `/media/` est servi par `django.views.static` en dev
(`hypostasia/urls.py:32`), qui **ne gère pas les requêtes `Range`** : sur un
enregistrement long, se déplacer ne marchera pas en dev. En prod, nginx le sert
(`nginx/default.conf:25`) et gère `Range` nativement. Rien à corriger dans le
lecteur, mais à savoir avant de croire à un bug.

### 5.2 Le visualiseur PDF — le chantier restant

**Il est possible depuis le 11 août, et c'est neuf** : la base porte 72
coordonnées. Le bouton « voir la source » existe déjà dans la gouttière
(`_blocs_elements.html:155`) et **dit honnêtement qu'il ne sait pas encore le
faire** plutôt que de promettre.

La donnée, exactement :

```json
{"page_no": 1,
 "boites": [{"l": 46.0, "t": 739.232, "r": 472.768, "b": 661.032,
             "page_no": 1, "coord_origin": "BOTTOMLEFT"}]}
```

Trois pièges, chacun avec une conséquence visible :

- **`boites` est une LISTE.** Un paragraphe à cheval sur deux pages en a
  plusieurs, chacune avec son propre `page_no`. Prendre `boites[0]` perdrait la
  seconde moitié du surlignage.
- **`coord_origin` vaut `BOTTOMLEFT`** : `t` se mesure depuis le **bas**. PDF.js
  travaille en origine haut-gauche → `y_écran = hauteur_page − t`. Inverser
  dessine les surlignages à l'envers.
- **Les pages font 612 × 792 points** (Letter, pas A4) pour le PDF étude.
  **Ne pas coder cette taille en dur** : la lire du document.

`SPEC-ancrage-par-element-v2.md § 8.2` existe mais **ne suffit pas pour coder** :
elle donne trois corrections (`convertToViewportRectangle`, `devicePixelRatio`,
`boites` en liste) sans le socle — rien sur le composant PDF.js, la pagination,
le zoom, le calque de surlignage. **Écrire cette spec en addendum daté avant de
coder.**

Restent à décider : PDF.js servi en local (cohérent avec le `collectstatic` du
projet) ou par CDN ; SVG au-dessus du canvas ou divs positionnés ; et le cas
d'un PDF **sans couche texte** — un scan pur, où il n'y a aucune coordonnée à
surligner. Attention : un scan produit une page aux dimensions de son image
(935 × 1210 pour un scan 110 dpi, contre 612 × 792 pt en natif).

### 5.3 Les proportions générales

Demandé par le mainteneur, **jamais fait, et non mesuré**. Il ne reste pas
d'écart de proportion *connu* : le centrage a été corrigé le 12 août (la colonne
tombait 42 px à gauche du centre, contre 13 px dans l'étalon), et le panneau
tient ses 368 px sous les 1400 px de seuil.

Donc : **mesurer avant de conclure.** Comparer largeur de colonne de lecture,
interlignes, tailles de police, hauteurs de bandes, en 1600 px et en mobile.
S'il n'y a rien, le dire — c'est un résultat.

### 5.4 La transcription audio en local — ouvert le 16 août

Seul chantier de ce fichier qui ne soit pas d'UX/UI : il est ici parce que c'est
l'endroit prévu pour les chantiers ouverts, et qu'il porte trois décisions en
attente (§ 6).

**L'état cible et le protocole sont dans `PLAN/specs/SPEC-transcription-audio-locale.md`.**
Ne pas les recopier ici — cette entrée ne dit que ce qui bouge.

**Où on en est** : rien n'est mesuré. Le banc d'essai est écrit et compile sans
avertissement (vérifié le 16 août), le matériau de test est choisi, et le § 7 de
la spec donne les huit étapes à dérouler. La première session s'est arrêtée pendant
le téléchargement des 2,4 Go de l'encodeur.

**Les trois choses à savoir avant d'y toucher** :

- **Ce n'est pas un changement d'hébergement, c'est un changement d'architecture.**
  Le modèle Voxtral que nous appelons (`voxtral-mini-latest`, avec `diarize=True`)
  est le seul de la famille à diariser, et il n'a **pas de poids publics**. En
  local il faut reconstruire **deux** étages : un ASR *et* un diariseur.
- **`max_speakers` (défaut 5, `core/models.py:1089`) n'est jamais envoyé à l'API.**
  Il traverse `tasks.py:623` → `transcription_audio.py:52` et finit dans un
  `logger.info`. Il dit notre *intention*, pas le comportement actuel. Ça compte,
  parce que le diariseur candidat (Sortformer) plafonne à **4** locuteurs, et que
  son mode de panne au-delà est **silencieux** : la sortie reste plausible.
- **Le banc n'existe que dans les annexes de la spec.** Le scratchpad où il vivait
  a déjà été purgé une fois. Les annexes A à G sont intégrales et suffisent à tout
  reconstruire — ne pas les alléger.

**Résultats à consigner** dans un `CHANGELOG/AAAA-MM-JJ-transcription-locale.md`,
pas ici.

---

## 6. Décisions en attente du mainteneur

**La granularité de l'ancrage sur un tableau.** Un tableau est **un seul**
`ElementDocument` de 4 471 signes : une idée ancrée dessus désigne le tableau
entier, pas une ligne. Rendre un vrai `<table>` (fait le 13 août) n'y change
rien — c'est une décision de **modèle**, pas de rendu. L'audio a son garde-fou
(`BUDGET_MAXIMUM_PAR_ELEMENT_AUDIO = 1500`, avec découpe en phrases) ; les
tableaux n'en ont aucun. Découper par ligne à l'ingestion, ou assumer le bloc :
signalée deux fois, jamais tranchée.

**Combien de voix dans les enregistrements réels ?** (chantier 5.4) C'est la
question qui commande toute l'architecture de la transcription locale. Le
diariseur candidat plafonne à **4 locuteurs**, notre `max_speakers` vaut **5**, et
au-delà de 4 la sortie est fausse **sans le dire**. À 3-4 voix, la pile candidate
est excellente et gère même la parole superposée ; à 6-8, il faut un autre modèle
(Ultra-Sortformer) ou un autre diariseur. Tant que ce chiffre n'est pas connu, le
banc ne peut pas conclure.

**Faut-il un DER sur la diarisation ?** (chantier 5.4) La transcription humaine
qui sert d'étalon **n'a aucun horodatage** : on peut mesurer le WER du texte, pas
le taux d'erreur de diarisation. Un vrai DER suppose d'annoter à la main les
frontières de tours sur un extrait — quelques heures de travail. À arbitrer avant
de s'y engager, pas après.

**Où ranger le banc d'essai ?** (chantier 5.4) Il n'existe aujourd'hui que dans
les annexes de sa spec, faute d'un emplacement décidé pour du code qui n'est pas
du code de production.

**La marge de neutralité des juges locaux, à revoir.** (mesure du 20 août, sur
836 avis réels) `MARGE_DE_NEUTRALITE = 2,5` est appliquée uniformément à des
échelles différentes : **CamemBERTa v2 et mDeBERTa v3 — les deux MEILLEURS
juges par AUC appariée — sont muets 85 % du temps**, contre 4 % pour `bge-m3`.
Les juges à contradiction rendent `(P(ent) − P(contra) + 1)/2`, concentré autour
de 50 ; `bge-m3` rend `P(entailment)` brut, étalé de 0,3 à 99,2.

**L'accord affiché repose donc de fait sur `bge-m3`** — le seul juge SANS classe
contradiction, c'est-à-dire sans le signal que tout le dossier défend. Une marge
par juge, ou une échelle commune : à trancher.

**Faut-il assouplir la comparaison du verbatim ?** (mesure du 19 août,
`benchmarks/extraction_format/2026-08-19_le-mode-d-echec-du-verbatim.md`) Sur
les 60 citations `INTROUVABLE` en base, **34 (57 %)** ne tiennent qu'à une
retouche de forme : un espace de ponctuation (20), un point ajouté (8), une
majuscule d'amorce (6). **11 seulement (18 %) sont un vrai saut de passage.**

Trois règles les récupéreraient, et aucune n'ajoute ni ne retire de contenu.
Mais **c'est un arbitrage, pas un correctif** : ça déplace ce que « verbatim »
veut dire dans la chaîne de preuve, et le produit tout entier repose dessus.

Et la cause dominante n'est pas le modèle : **la page 1 porte littéralement
`territoire .`**, un point détaché de son mot par l'ingestion, que les trois
Mistral recollent et que notre comparaison leur refuse. Corriger l'ingestion
traiterait la cause — au prix d'une réingestion. **Trois voies, aucune
tranchée.**

**Le banc des rédacteurs a tourné, et il a mesuré son propre bruit.** Neuf
passes (3 modèles × 3 répétitions × 4 articles, températures à 0, périmètre
figé à 137 extractions) :
`benchmarks/redaction/2026-08-19_trois-redacteurs-a-un-seul-extracteur.md` § 9.

**Le « % de citations vérifiées » ne discrimine pas les rédacteurs.**
`mistral-large` rend 29,4 %, 40,6 % puis 31,1 % sur trois passes identiques —
onze points d'amplitude avec lui-même, pour 7,8 points d'écart entre modèles.
**Tout classement fondé sur ce taux, dans ce dépôt, est du bruit** — y compris
ceux des campagnes du 18 et du 19 août au matin.

Ce qui tranche : le nombre de citations (Small 279 contre Medium 173), la
longueur (Medium 19 k caractères contre Small 32 k), et — de justesse — la
prose sans marqueur (Medium 10 %, Small 18,8 %, Large 26,2 %).

**Large n'est premier sur aucun critère et il est le plus instable des trois.**
**Entre Small et Medium, la mesure ne tranche pas** : articles différents, pas
meilleurs. L'arbitrage est un arbitrage de prix — Small coûte dix fois moins.

**L'effet du SUJET égale celui du modèle** : Small va de 4,5 % de prose non
sourcée sur « open badges » à 35,2 % sur « gouvernance collective », le sujet
que le corpus couvre le moins. Un article sur un sujet mal couvert se dégrade
en prose non sourcée, et changer de modèle n'y change rien. **C'est un
arbitrage produit qui n'a jamais été posé.**

---

## 7. L'état des tests — remesuré le 20 août, après la tension sur le renvoi

**2200 tests, tous verts**, dont **1** sauté. La suite tourne en **24 min 18 s**
(`Ran 2200 tests in 1458.065s`, `make test-rapide`, donc **hors e2e / docling /
llm**), sous **LangExtract 1.6.0**. Suite lancée **seule**, aucune mesure
concurrente.

> **Les 50 tests de plus que la mesure de 2098 ci-dessous ne sont pas tous les
> miens, et je ne les attribue pas.** Le chantier des juges locaux en ajoute
> **20**, comptés : 14 pour la table `AvisDeVerification`, son report et l'accord
> (`core/tests/test_avis_des_juges_locaux.py`), 3 pour une extraction citée dans
> deux paragraphes (`front/tests/test_une_extraction_citee_deux_fois.py`), et 3
> de plus dans `front/tests/test_second_avis_a_l_ecran.py`, passé de 11 à 14. Les
> **30 restants** viennent d'un travail mené en parallèle le même jour : je les
> compte, je ne dis pas d'où ils sortent.

> ⚠️ **Deux mesures ont été perdues aujourd'hui pour la même raison, et il faut
> le savoir avant de croire un chiffre.** Une suite complète lancée pendant
> qu'une autre tournait a rendu **299 erreurs** en `real_ensure_connection` —
> puis, une heure plus tard, deux sessions ont lancé la leur en même temps. La
> base de test est partagée : la seconde détruit la première en plein vol, et
> **l'échec ne ressemble pas à sa cause**. La vérification tient en une commande,
> à faire AVANT de lancer :
>
> ```bash
> docker exec hypostasia_web sh -c "ps -eo args | grep -c '[m]anage.py test'"
> ```
>
> Zéro, ou on ne lance pas.

> **Les 16 tests de plus** que la mesure de 2082 ci-dessous sont ceux du typage
> du mode d'échec du verbatim
> (`hypostasis_extractor/tests/test_typage_des_non_verbatim.py`, **22 tests** au
> total). Contrairement au chantier des encodeurs, celui-ci **ajoute** des tests :
> l'outil de banc vit bien dans `benchmarks/`, mais ses fonctions de typage et de
> réparation sont pures, et **cinq d'entre elles verrouillent un cas qui ne doit
> JAMAIS passer** — un décimal blanchi par une énumération, une question devenue
> affirmation, un point que la source portait déjà. Le test est chargé par son
> chemin, ce qui permet de le collecter depuis une app.
>
> **Aucun fichier de `core/`, `front/` ou `hypostasis_extractor/` n'a été
> modifié** — seul un fichier de test y a été ajouté.

> **Le chantier des encodeurs n'ajoute AUCUN test, et c'est délibéré.** Tout ce
> qu'il livre vit dans `benchmarks/juge_de_verification/`, que `manage.py test`
> **ne collecte pas** — le dossier n'est pas une app Django et n'a pas
> d'`__init__.py`. Même précédent et mêmes raisons que `comparer_un_juge.py` et
> `comparer_shieldstral.py` ; c'est écrit en tête du README de ce dossier. Aucun
> fichier de `core/`, `front/` ou `hypostasis_extractor/` n'a été touché.
>
> **Les 6 tests de plus que la mesure de 2076 ci-dessous ne sont donc pas les
> miens** — ils viennent du travail mené en parallèle le même jour. Je les compte,
> je ne les attribue pas.

*(Le compte de 2082 ci-dessus était celui du 19 août avant le typage du
verbatim ; il est conservé pour que la chaîne des écarts reste lisible.)*

> ⚠️ **Le `Makefile` et cette section ont divergé, et cette section prétend que
> c'est impossible.** L'aide de `make test` annonce `test-rapide` à **1748 tests,
> ~7 min 30 (mesure du 15 août 2026)** ; la mesure ci-dessus en compte **2082 en
> 24 minutes**. Or le bas de cette section renvoie au `Makefile` « qui les porte
> avec leurs comptes » précisément pour éviter deux listes qui divergent — et
> les deux ont divergé de 334 tests et 16 minutes. À trancher par le mainteneur :
> soit le `Makefile` cesse d'annoncer un compte, soit il est remis à jour à
> chaque mesure.

> Les **17 tests de plus** que la mesure du 18 août (2059) : 9 pour le repli sur
> les marqueurs groupés (`core/tests/test_marqueurs_groupes.py`) et 8 pour la
> route publique qui sert les mesures
> (`front/tests/test_route_des_benchmarks.py`).

> Les **8 tests de plus** que la mesure précédente (2051) : 4 pour la tolérance
> à la liste JSON nue que la 1.6.0 apporte
> (`hypostasis_extractor/tests/test_liste_json_nue.py`), 4 pour ce qu'une
> réinstallation doit reproduire — Mistral en tête, sa plateforme, **sa
> température à 0**, les rôles, et un rôle choisi à la main qui **survit** au
> redémarrage (`front/tests/test_fixtures_analyseurs.py`).

> **Une suite à la fois, et ce n'est pas une formule.** Le 18 août, une commande
> `make test-suite` lancée pendant un `make test-rapide` a tué ce dernier après
> neuf minutes : `database "test_hypostasia_opus" does not exist`. Aucun dégât
> durable — la base de test se recrée — mais la mesure était perdue et l'échec
> ne ressemblait pas à sa cause.

> Les **30 tests de plus** viennent du chantier « deux juges en parallèle » :
> le stockage du second avis et sa survie aux mises à jour de wiki (11),
> l'affichage de l'accord et ses quatre états (11), la topologie du worker
> dédié — file, concurrence 1, `nice` (8). Le compte tombe juste :
> 2021 + 30 = 2051. Détail dans
> `CHANGELOG/2026-08-18-deux-juges-en-parallele.md`.

> **Un écart que je n'ai pas su attribuer, et qu'il faut savoir avant de
> comparer.** La mesure du 17 août disait **2007 tests dont 14 sautés**. Le
> chantier du degré en ajoute **27** (`core/tests/test_score_de_verification.py`
> et `front/tests/test_degre_a_l_ecran.py`), ce qui donnerait 2034 — or on en
> compte **2021**, et les sautés tombent de 14 à **1**.
>
> Trois commits sont tombés entre les deux mesures, dont deux « retrait des
> fixtures héritées » : ils expliquent vraisemblablement et la baisse de compte
> et la quasi-disparition des tests sautés. **Vraisemblablement, pas
> certainement** — l'établir exigerait de rejouer la suite sur l'arbre d'avant,
> donc une opération git qu'un agent ne fait pas. Le chiffre ci-dessus est
> mesuré ; son *écart* avec le précédent ne l'est pas.

> La mesure du 17 août disait **2007 tests en 22 min 32 s**, dont 14 sautés,
> après le chantier « un modèle par rôle ».

> La mesure du 17 août au matin disait **1916 tests en 22 min 00 s**, mêmes 14 sautés. Les
> **91 tests de plus** viennent du chantier « un modèle par rôle » : la table de
> rôles et son repli, le branchement des six producteurs, le chemin d'appel
> compatible OpenAI, la non-dégradation du juge, la dichotomie de lot, le gel de
> l'étalon, la commande d'affectation et ses options, la transmission de la
> température (y compris son absence, que les modèles de raisonnement exigent),
> le verrou « tout modèle du référentiel a un tarif », et l'extraction par une
> plateforme compatible OpenAI. Détail dans
> `CHANGELOG/2026-08-17-un-modele-par-role-et-un-chemin-partage.md`.

> La mesure du 13 août disait **1874 tests en 12 min 51 s**, dont 25 sautés,
> sur la suite complète e2e comprise. L'optimisation qui l'avait obtenue tient
> toujours : navigateur Playwright partagé entre modules, `networkidle`
> remplacé par des attentes sur l'objet mesuré, un module e2e de 13 tests en
> 23 s.

**Une découverte du 17 août à connaître avant de lancer quoi que ce soit.**
`CELERY_TASK_ALWAYS_EAGER` n'était pas posé sous test : la suite publiait de
VRAIS messages dans le Redis partagé, avec des clés primaires de la base de
test, et le worker de dev les exécutait contre la base de DEV. Constaté sur une
installation neuve : quatre jobs d'analyse marqués `error` par des tâches
d'article, et le carnet étalon tombé de 101 à **41** extractions citables — sans
qu'aucun test n'échoue. C'est fermé (`hypostasia/settings.py`), et vérifié : la
base de dev ressort **identique** après la suite complète. Détail dans
`CHANGELOG/2026-08-17-la-suite-de-tests-corrompait-la-base-de-dev.md`.

Les cibles et leur coût : **`make test`**. Elles ne sont pas recopiées ici —
le `Makefile` les porte avec leurs comptes, et une seconde liste divergerait.

**Une suite à la fois, jamais `--parallel`** : la base de test est partagée,
deux exécutions simultanées se la détruisent mutuellement en plein vol (755
erreurs fantômes constatées).

> **Cette section est la source de la mesure** — aujourd'hui **2148 tests en
> 24 min 21 s**, en tête de section. Ni le README ni `AGENTS.md` ne la
> répètent : ils y renvoient. Si tu remesures, c'est ici que tu écris, et
> nulle part ailleurs.
>
> Cette note portait encore « 1874 tests, 12 min 51 s » alors que la section
> annonçait 1916 depuis le matin : le chiffre de rappel avait été oublié à la
> remesure. Il n'y a qu'un endroit où écrire, et c'est **le premier
> paragraphe** — cette note ne fait que le désigner.

Le dernier échec trouvé le 13 août vaut d'être lu — c'est le genre de défaut
qu'un travail d'UX peut créer sans le voir :

> Supprimer une note citée par une synthèse adoptée répondait **204 No Content**
> au lieu de refuser. Le refus lui-même marchait (rien n'était supprimé, le
> toast partait), mais 204 se lit comme **un succès sans corps**. Cause : la
> réponse de cet endpoint était l'arbre latéral — toujours du HTML, donc
> toujours 200. L'arbre retiré, elle est devenue la liste des notes du carnet,
> qui vaut `None` quand la requête ne dit pas d'où part le geste. Corrigé en
> **409**, comme le refus jumeau `supprimer_entite`.

**La leçon** : retirer un composant change les réponses de tous les endpoints
qui le rendaient. `manage.py check` ne voit rien de tout ça — seule la suite
complète l'a montré.

---

## 8. L'état du dépôt

Le mainteneur commite lui-même. **Ne jamais le faire à sa place.**

Livré pendant la session du 12–13 août :

| Livré | Où |
|---|---|
| Panneau d'analyse intégré au corps de la note | `base.html`, `.plateau` |
| Bande de contexte unique (fil + titre du panneau) | décision A de l'étalon |
| Dashboard retiré, avec tout son code | `dashboard_consensus.*` supprimés |
| Menu burger et arbre latéral retirés définitivement | `arbre_*.js`, `_dossier_node.html` supprimés |
| Onglet « Bases de connaissances » sur la home, deux zones | `test_29` |
| Pages liste des carnets et des bases | `test_24`, `test_25` |
| Champ image de couverture sur les bases | migration `0062` |
| Analyseurs branchés à l'installation | `front/services/fixtures_analyseurs.py` |
| Fixture d'extractions déterministe, sans LLM | `charger_extractions_demo.py` |
| Formes par label : `<table>`, `<blockquote>`, `<figure>` | `rendu_elements.py:88` |
| Optimisation des tests e2e (navigateur partagé) | `front/tests/e2e/base.py` |

**Un garde-fou à ne pas casser** : `front/tests/test_aucun_geste_orphelin.py`
vérifie que chaque geste porté par l'arbre latéral supprimé a gardé un point
d'entrée quelque part. Il existe parce que deux fois dans la même journée, un
retrait « propre » a failli supprimer une fonction entière sans que personne ne
le voie — le dashboard portait le **seul** accès à la synthèse, et le bouton
« Analyses » le **seul** moyen de rouvrir le panneau.

### Plans écrits et NON exécutés

- `docs/superpowers/specs/2026-08-11-dedup-import-design.md` — déduplication à
  l'import par empreinte du fichier source. Spécifiée, pas implémentée.
- `docs/superpowers/plans/2026-08-11-suppression-et-echec-voxtral.md` — quatre
  tâches arbitrées avec le mainteneur : suppression du média avec la note
  (signal `post_delete`), règle « retirer du carnet plutôt que détruire » quand
  on n'est pas propriétaire, échec Voxtral qui supprime la page vide en gardant
  son `TranscriptionJob` (`CASCADE` → `SET_NULL`), confirmation conditionnelle
  côté JS.
  ⚠️ **Ce chantier rendra `job.page` nullable**, et
  `_destinataires_de_notification` (`front/tasks.py:50`) fait `page.owner_id`
  sans garde : il lèvera. C'est une mine posée, pas un bug actuel.

### Défauts connus, différés

`CHANGELOG/DEFAUTS-DIFFERES.md`. Les plus notables : les médias orphelins
(`Page.delete()` ne supprime pas le fichier), et une transcription échouée qui
relance un appel Voxtral **facturé** à chaque rechargement.

---

## 9. Les pièges d'environnement — chacun a déjà cassé quelque chose

| Piège | Conséquence vécue |
|---|---|
| **Build Tailwind FIGÉ** | toute classe arbitraire (`z-[70]`, `min-w-[160px]`) est **inerte**. Passer par les tokens CSS de `maquette.css` (`--papier`, `--encre`, `--panneau`, `--gouttiere`, `--barre-audio`). **Vérifier au navigateur que la classe agit** — ne pas le supposer. |
| **Fichier statique modifié** | `collectstatic` **et** bump du `?v=` dans le gabarit qui le charge. Sans les deux, les navigateurs servent l'ancien fichier. Un fichier neuf non collecté donne un 404 silencieux — le JS ne tourne pas, et rien ne le dit. |
| **Template modifié avec `DEBUG=False`** | `make restart S=daphne` puis `S=gunicorn` |
| **Deux `manage.py test` en parallèle** | ils se détruisent la base : 755 erreurs fantômes. Une suite à la fois. |
| **Playwright dans le conteneur** | `PLAYWRIGHT_BROWSERS_PATH=/home/hypostasia/.cache/ms-playwright` doit être dans l'environnement, sinon les e2e échouent en `setUpClass`. |
| **Playwright + ORM Django** | l'API sync tourne dans une boucle asyncio : toute requête ORM y lève `SynchronousOnlyOperation`. Faire ses requêtes **avant** d'ouvrir le navigateur. |
| **Nouvelle tâche Celery** | redémarrer le worker, sinon il tourne avec l'ancien code. |
| **Docling** | 2 à 3,4 Gio et 80 à 164 s par PDF. Une conversion à la fois, `free -h` avant. |
| **`AncrageExtraction.element` en PROTECT** | supprimer une page exige de retirer ses portions d'abord. |
| **Aucun `DEFAULT_PERMISSION_CLASSES`** | tout endpoint DRF est `AllowAny`. Doctrine du **404, jamais 403**. |

### Pour vérifier au navigateur

Le script de la session du 13 août est à reprendre : il ouvre le vrai serveur,
bascule les deux thèmes, calcule les contrastes WCAG et écrit des captures.
Deux pièges y sont déjà désamorcés — `hypostasia_nginx` n'est pas dans
`ALLOWED_HOSTS` (passer par `localhost` avec
`--host-resolver-rules=MAP localhost <ip nginx>`), et `color-mix()` rend des
composantes en 0–1 quand `rgb()` les donne en 0–255, ce qui avait fait annoncer
un contraste de 1,15:1 là où il valait 4,13:1.

---

## 10. Par quoi commencer

1. **Ouvrir l'étalon et le produit côte à côte**, en clair puis en sombre. Les
   sept écarts sont tous résolus ou assumés — mais les tableaux périment, et
   celui-ci s'est déjà révélé faux sur quatre lignes. Mesurer avant de croire.
2. **Écrire la spec du visualiseur PDF** avant de l'attaquer (§ 5.2).
3. **Mesurer les proportions** (§ 5.3). S'il n'y a rien à corriger, le dire :
   c'est un résultat.
4. **Mettre à jour le tableau des écarts** dans l'en-tête de `maquette.html` à
   chaque ligne touchée. La session suivante repart de là.
