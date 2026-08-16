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
make dev                            # runserver + les DEUX workers Celery
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

**Deux workers Celery, jamais un seul** (mesuré le 14 août) : `celery_worker`
sert la file par défaut à concurrence 2, `celery_worker_docling` sert
`ingestion_docling` **à concurrence 1** — une conversion Docling à la fois,
elles pèsent ~2 Go et ~83 s de warm-up chacune. C'est aussi ce qui rend exacte
la position affichée dans la file d'attente.
`hypostasis_extractor/tests/test_files_celery_ingestion.py` verrouille
l'invariant.

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

---

## 7. L'état des tests — mesuré le 13 août

**1874 tests, tous verts.** La suite complète tourne en **12 min 51 s**
(`front core hypostasis_extractor`), dont 25 sautés. Elle prenait bien plus
avant l'optimisation du 13 août — navigateur Playwright partagé entre modules,
`networkidle` remplacé par des attentes sur l'objet mesuré. Un module e2e de 13
tests passe désormais en 23 s.

Les cibles et leur coût : **`make test`**. Elles ne sont pas recopiées ici —
le `Makefile` les porte avec leurs comptes, et une seconde liste divergerait.

**Une suite à la fois, jamais `--parallel`** : la base de test est partagée,
deux exécutions simultanées se la détruisent mutuellement en plein vol (755
erreurs fantômes constatées).

> **Ce paragraphe est la source de la mesure ci-dessus** (1874 tests,
> 12 min 51 s). Ni le README ni `AGENTS.md` ne la répètent : ils y renvoient.
> Si tu remesures, c'est ici que tu écris, et nulle part ailleurs.

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
