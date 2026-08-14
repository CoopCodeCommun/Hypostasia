## 0. Ce qu'il faut savoir en trois phrases

Hypostasia est un outil de **délibération sourcée** : on importe des
documents, un LLM en extrait des « idées », et chaque idée reste
**ancrée** au passage exact dont elle vient — c'est cette ancre qui fait
la preuve.

Le moteur d'ancrage est en place et alimenté : la base porte six
documents étalons, 670 éléments, dont **72 avec leurs coordonnées de
page**. Le travail restant n'est plus d'extraire, mais de **montrer**.

Ta mission est esthétique et ergonomique, dans cet ordre : le panneau
d'extraction, la gouttière, puis le lecteur audio et le visualiseur PDF.

---

## 1. L'étalon

`front/static/front/maquettes/maquette.html` (120 Ko), servi en ligne
sur `https://hyp.nasjo.fr/static/front/maquettes/maquette.html` et en
local sur `https://h.localhost/static/front/maquettes/maquette.html`.

**Lis son en-tête avant tout le reste.** Elle est remarquablement
documentée et distingue deux choses :

- **« RÉFÉRENTIELS TIRÉS DU CODE RÉEL »** — avec les chemins exacts :
  familles d'hypostases (`extractor_tags.py:16-62`), couleurs
  (`hypostasia.css:48-70`), palette des locuteurs
  (`transcription_audio.py:23-34`), carte d'extraction
  (`_card_body.html`), drawer, raccourcis clavier. Ceux-là décrivent
  l'existant : la maquette s'y aligne, pas l'inverse.
- **« CE QUI EST UNE CIBLE, PAS L'EXISTANT »** — sept écarts numérotés,
  signalés dans la maquette par un bandeau violet `--cible: #7C5CBF`.

**Cette liste de sept est DATÉE. Trois sont déjà résolus** — vérifié au
navigateur le 11 août :

| # | Écart annoncé | État réel au 11 août |
|---|---|---|
| 1 | « aucun fil d'Ariane dans le produit » | **FAUX** — « Démonstration › Documents étalons › Étude épistémologique » s'affiche |
| 2 | « aucun `<audio>`, aucune tête de lecture » | à revérifier — c'est ton chantier 3 |
| 3 | « le WebSocket ne pousse que "terminé" » | toujours vrai pour la progression ; les notifications de fin, elles, ont été branchées le 11 août |
| 4 | « le produit est mono-colonne + drawer » | **FAUX** — le panneau « Analyses » est permanent à droite |
| 5 | « le produit n'a pas de mode sombre » | **FAUX** — il en a un, et il fonctionne |
| 6 | « les tableaux sont rendus en `<pre>` » | **VRAI, et visible** : le PDF étalon a 2 tableaux → 2 `<pre>`, 0 `<table>` |
| 7 | éléments masqués / ancres détachées sans interface | non revérifié |

**Ne prends aucune de ces sept lignes pour argent comptant : vérifie
chacune au navigateur avant de coder.** Et quand tu en corriges une,
**mets à jour l'en-tête de la maquette** — sinon la prochaine session
repartira sur la même carte périmée.

Deux autres maquettes existent, pour plus tard :
`corpus.html` et `selection-preuves.html`.

---

## 2. L'environnement

Tout tourne dans Docker. Les conteneurs sont lancés (`docker ps` :
`hypostasia_web`, `hypostasia_nginx`, `hypostasia_postgres`,
`hypostasia_redis`, `traefik`).

```bash
# Tout démarrer : runserver (port 8000) + les DEUX workers Celery
docker exec hypostasia_web supervisord -c /app/supervisord-dev.conf

# État / redémarrage d'un service
docker exec hypostasia_web supervisorctl -c /app/supervisord-dev.conf status
docker exec hypostasia_web supervisorctl -c /app/supervisord-dev.conf restart runserver

# Logs (supervisord tourne en démon, rien ne sort sur stdout)
docker exec hypostasia_web tail -f /app/logs/celery_worker_docling.log
```

Le serveur écoute sur le **port 8000, PAS 8123** (l'en-tête du
docker-compose ment, `nginx/dev.conf` proxie vers `web:8000` ; sur 8123
tu obtiens un 502).

**Le site : https://h.localhost/ — identifiants `jonas` / `admin1234`.**

**DEUX workers, pas un** (14 août 2026) : `celery_worker` sert la file
par défaut à concurrence 2, `celery_worker_docling` sert
`ingestion_docling` **à concurrence 1**. Le lancement dev tirait
auparavant les deux files depuis un worker unique à concurrence 2 —
deux conversions Docling simultanées étaient donc possibles (~2 Go et
~83 s de warm-up chacune), et une ingestion pouvait occuper les deux
slots au détriment des analyses. `hypostasis_extractor/tests/
test_files_celery_ingestion.py` verrouille désormais l'invariant.

`uv run` n'est **pas** nécessaire : le `PATH` de l'image contient déjà
`/app/.venv/bin` (Dockerfile:59), donc `docker exec -w /app
hypostasia_web python manage.py check` fonctionne tel quel. La version
précédente de cette passation affirmait le contraire — c'était faux.
Sous supervisord, `uv run` est même nuisible : il laisse un process
wrapper entre supervisord et le vrai programme, et le SIGTERM d'arrêt
irait au wrapper plutôt qu'au worker qui doit finir sa conversion.

Le mainteneur travaille dans **byobu**. Convention utile : le pane 0
porte Claude, un autre le serveur, un autre le worker. Les index de
panes se renumérotent quand on en ajoute — **cible les panes par leur
`pane_id` (`%6`, `%8`), jamais par leur index.**

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

Total : **6 notes, 670 éléments, 72 avec `provenance.page_no` et leurs
boîtes.** Toutes en `ingestion_etat='reussie'`, aucune incohérence.

Pour recharger de zéro :

```bash
docker exec -w /app hypostasia_web uv run python manage.py charger_fixtures_sample --reset
```

Compte ~3 minutes : elle lance deux conversions Docling réelles et **un
appel Voxtral facturé** (c'est voulu — il sert de test de bout en bout).
`--sans-mp3` l'évite, `--a-blanc` n'écrit rien.

**Ce que la base ne contient PAS : aucune extraction, aucun commentaire.**
Zéro carte dans le panneau. Pour travailler le panneau d'extraction, il
faut d'abord lancer une analyse depuis l'écran — ou écrire une fixture
qui en pose sans appeler de LLM. **C'est probablement ton premier
geste.**

### La géométrie mesurée

| | |
|---|---|
| gouttière, document écrit | **46 px** |
| gouttière, audio | **96 px** |
| gouttière, PDF | 46 px, affiche « p. 1 », « p. 2 » |
| colonne de texte | 672 px |
| boutons « voir la source » | 11 sur le PDF étude, un par élément |

---

## 4. Les chantiers, dans l'ordre

### 4.1 Le panneau d'extraction

Il existe et fonctionne : « Analyses », un compteur d'extractions, un
tri (« Position »), un bouton « Lancer une analyse ». Il est **permanent
à droite**, contrairement à ce que dit l'écart n°4 de la maquette.

Compare-le à la maquette section « 9. PANNEAU ET SURFACES » et « 6. LA
CARTE — reproduit `_card_body.html` ».

**un défault à corriger** 

Le panneau s'ouvre par dessus le reste. Regarde sur la maquette, il est intégré au corp de la div du texte. A corriger, et rend le collapsable avec toujours ouvert sur le grand écran. Check les Z index et le scrole.

**a améliorer**

Idéalement, il faudrait que les extraction soit au même niveau que l'endroit ou elle sont dans le texte, pour pouvoir faire la correspondance facilement d'un coup d'oeil.

**Un défaut mesuré, à corriger tôt** — le toast, en mode sombre :

| | |
|---|---|
| texte | `rgb(236, 234, 228)` |
| fond du toast | `rgb(22, 21, 26)` |
| **fond de la page** | **`rgb(22, 21, 26)` — identique** |
| bordure | `0px none` |
| ombre | noire à 18 % — invisible sur fond noir |
| `z-index` | **`auto`** |

Le contraste du texte est excellent (~14,8:1). Le problème est que **le
toast ne se détache pas de la page** : son texte flotte par-dessus le
panneau et on lit les deux superposés. En clair, l'ombre suffit ; en
sombre, une ombre noire sur fond noir ne sépare rien. Il manque une
bordure ou un fond distinct, et un `z-index`.

### 4.2 La gouttière

Elle marche et respecte les largeurs cibles (46 px / 96 px). Sur l'audio
elle affiche les locuteurs colorés et les minutages ; sur le PDF, « p. N »
et le bouton « voir la source ».

À reprendre depuis la maquette : sections « 4. LE SURLIGNAGE — segments
et marques IMBRIQUÉES », « 5. LES FORMES PAR LABEL », « 8. NAVIGATION
CROISÉE — texte ⇄ glissière ⇄ cartes ».

**L'écart n°6 est ton morceau le plus concret** : le service rend les
tableaux en `<pre>`, et `blockquote`, `formula`, `picture`, `utterance`
ne sont pas dans `BALISE_PAR_LABEL` (`rendu_elements.py:82-89`) — ils
sortent tous en `<p>`. Le PDF étude, avec ses 2 tableaux, te donne la
fixture pour l'éprouver immédiatement.

**Une décision de conception t'attend là** : un tableau entier est **un
seul `ElementDocument`** (~3 000 caractères pour celui du PDF étude).
Une idée ancrée dessus porterait sur onze lignes, et la gouttière
annoncerait « ce passage » en désignant tout le tableau. L'audio a son
garde-fou (`BUDGET_MAXIMUM_PAR_ELEMENT_AUDIO = 1500`, avec découpe en
phrases) ; les tableaux n'en ont aucun. Découper par ligne, ou assumer
le bloc entier ? À trancher avec le mainteneur avant de coder.

### 4.3 Le lecteur audio

Les données sont là : 21 tours de parole sur deux notes, avec
`provenance = {"locuteur", "debut", "fin"}`.

L'écart n°2 dit « aucun `<audio>`, aucune tête de lecture ; l'existant
est une timeline click-to-scroll ». **Vérifie-le au navigateur avant de
partir dessus** — trois des sept écarts se sont révélés périmés.

Maquette : section « 2 » du bandeau cible, et la palette de locuteurs
dans `front/services/transcription_audio.py:23-34`.

Le `.mp3` source est bien attaché à la note (`Page.source_file`) : il y
a de quoi lire réellement l'audio.

### 4.4 Le visualiseur PDF

**Il est enfin possible, et c'est neuf.** Avant le 11 août la base ne
portait aucune coordonnée ; elle en porte 72. Le bouton « voir la
source » existe déjà dans la gouttière et dit honnêtement « le
visualiseur PDF n'est pas encore disponible » (`marginalia.js:253`).

Ce que la donnée te donne exactement :

```json
{"page_no": 1,
 "boites": [{"l": 46.0, "t": 739.232, "r": 472.768, "b": 661.032,
             "page_no": 1, "coord_origin": "BOTTOMLEFT"}]}
```

- **`boites` est une LISTE** : un paragraphe à cheval sur deux pages en
  a plusieurs, chacune avec son propre `page_no`.
- **`coord_origin` vaut `BOTTOMLEFT`** : `t` se mesure depuis le **bas**
  de la page. PDF.js travaille en origine haut-gauche — la conversion
  est `y_écran = hauteur_page − t`. Ne l'inverse pas : les surlignages
  se dessineraient à l'envers.
- **Les pages font 612 × 792 points** (format Letter, pas A4) pour le
  PDF étude. **Ne code pas cette taille en dur** : lis-la du document.

`SPEC-ancrage-par-element-v2.md § 8.2` existe mais est **insuffisante
pour coder** : elle donne trois corrections
(`convertToViewportRectangle`, `devicePixelRatio`, `boites` en liste)
sans le socle — rien sur le composant PDF.js, la pagination, le zoom, le
calque de surlignage. **Écris cette spec avant de coder**, en addendum
daté.

Restent à décider : PDF.js servi en local (cohérent avec le
`collectstatic` du projet) ou par CDN ; SVG au-dessus du canvas ou divs
positionnés ; et le cas d'un PDF **sans couche texte** (un scan pur).

---

## 5. Pièges d'environnement — le non-respect a déjà cassé des choses

| Piège | Conséquence vécue |
|---|---|
| **Build Tailwind FIGÉ** | toute classe arbitraire (`z-[70]`, `min-w-[160px]`) est **inerte**. Style inline, ou rebuild. **Vérifie au navigateur que ta classe agit** — ne le suppose pas. |
| **Fichier statique modifié** | `collectstatic` **et** bump du `?v=` dans le gabarit qui le charge. Sans les deux, les navigateurs servent l'ancien fichier. |
| **Template modifié avec `DEBUG=False`** | `supervisorctl restart daphne gunicorn` |
| **Deux `manage.py test` en parallèle** | ils se détruisent la base : 755 erreurs fantômes. **Une suite à la fois, et ciblée** — `manage.py test` sans argument, c'est 1597 tests et 7 minutes. |
| **Playwright dans le conteneur** | les navigateurs sont installés, mais `PLAYWRIGHT_BROWSERS_PATH=/home/hypostasia/.cache/ms-playwright` **n'est pas dans l'environnement**. Sans elle, 21 tests e2e échouent en `setUpClass` — c'est l'état actuel, et ces tests n'ont jamais tourné de la session du 11 août. |
| **Playwright + ORM Django** | l'API sync tourne dans une boucle asyncio : toute requête ORM y lève `SynchronousOnlyOperation`. Fais tes requêtes **avant** d'ouvrir le navigateur. |
| **Nouvelle tâche Celery** | redémarrer le worker, sinon il tourne avec l'ancien code. |
| **Docling** | 2 à 3,4 Gio et 80 à 164 s par PDF. Une conversion à la fois, `free -h` avant. Détail : `tmp/benchmark-docling-2026-08-11.md`. |
| **`AncrageExtraction.element` en PROTECT** | supprimer une page exige de retirer ses portions d'abord. |
| **Aucun `DEFAULT_PERMISSION_CLASSES`** | tout endpoint DRF est `AllowAny`. Doctrine du **404, jamais 403**. |

---

## 6. La méthode attendue — non négociable

- **JAMAIS d'opération git.** Ni `commit`, ni `add`, ni `checkout --`,
  ni `stash`, ni `reset`, ni `clean`. Le dépôt appartient au mainteneur.
  **Jamais de `Co-Authored-By`** s'il autorise un commit.
- **JAMAIS `ruff format` ni `ruff check --fix`** sur un fichier existant.
- **TDD strict** : le test d'abord, on le regarde échouer, puis le code.
- **Relecture adverse par un agent à chaque phase**, avec correctifs
  testés. Sur la session du 11 août, cette pratique a rattrapé un
  Critique et une quinzaine d'Important que 1597 tests verts n'avaient
  pas vus.
- **Tout front comparé à l'étalon au navigateur réel, clair ET sombre,
  contrastes calculés — pas des impressions.** Le seul défaut visuel
  trouvé le 11 août (le toast) n'a été vu ni par les tests ni par les
  huit revues : il a fallu regarder l'écran.
- **Trou de spec → écrire la spec avant de coder**, en addendum daté.
- `CHANGELOG.md` + fiche `A TESTER et DOCUMENTER/` par phase.
- **Ne jamais inventer un chiffre.** Un compte annoncé est un compte
  mesuré.

### Conventions du dépôt

`viewsets.ViewSet` explicites, jamais `ModelViewSet`. DRF `serializers`,
jamais Django Forms. HTMX pour l'interactivité, jamais de SPA.
Commentaires bilingues français puis anglais sur chaque bloc de logique.
Noms de variables verbeux en français. En-tête `LOCALISATION` par
fichier.

---

## 7. L'état du dépôt au moment de cette passation

**Une journée entière de travail commité** : ~17 fichiers créés,
une douzaine modifiés, 7 migrations (toutes appliquées à la base de
dev). C'est au mainteneur d'en décider.


### Plans écrits et NON exécutés

- `docs/superpowers/plans/2026-08-11-suppression-et-echec-voxtral.md` —
  quatre tâches arbitrées avec le mainteneur : suppression du média avec
  la note (signal `post_delete`), règle « retirer du carnet plutôt que
  détruire » quand on n'est pas propriétaire, échec Voxtral qui supprime
  la page vide en gardant son `TranscriptionJob` (`CASCADE` → `SET_NULL`),
  et confirmation conditionnelle côté JS.
  ⚠️ **Ce chantier rendra `job.page` nullable**, et
  `_destinataires_de_notification` (`front/tasks.py:50`) fait
  `page.owner_id` sans garde : il lèvera. C'est une mine posée, pas un
  bug actuel.
- `docs/superpowers/specs/2026-08-11-dedup-import-design.md` —
  déduplication à l'import par empreinte du fichier source. Spécifiée,
  pas implémentée.

### Défauts connus, différés

Ils sont listés dans
`.superpowers/sdd/2026-08-11-charger-fixtures-sample/progress.md`
(lignes `minor (deferred)` et `parked`). Les plus notables : les médias
orphelins (`Page.delete()` ne supprime pas le fichier), et le fait
qu'une transcription échouée relance un appel Voxtral facturé à chaque
rechargement.

---

## 8. Par quoi commencer, concrètement

1. **Ouvre la maquette et le produit côte à côte**, en clair puis en
   sombre. Reprends les sept écarts un par un et **écris leur état
   réel** — trois sont déjà faux.
2. **Pose des extractions dans la base.** Le panneau est vide (« 0
   extractions ») : il n'y a rien à styler tant qu'aucune carte n'existe.
   Soit tu lances une analyse depuis l'écran, soit tu écris une fixture
   qui en pose sans appeler de LLM. Sans ça, tu travailleras à l'aveugle.
3. **Corrige le toast en mode sombre** — petit, mesuré, visible.
4. Puis le panneau, la gouttière, et les deux lecteurs, dans l'ordre.

Et à chaque étape : TDD, relecture adverse par un agent opus, vérification au
navigateur avec contrastes calculés. C'est ce qui a rattrapé, sur les
sessions précédentes, ce que la relecture seule laissait passer.
