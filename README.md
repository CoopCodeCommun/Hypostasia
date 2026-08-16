<div align="center">

# Hypostasia

**Plateforme de lecture deliberative : lire, extraire et debattre collectivement d'un texte — augmentee par IA.**

*Deliberative reading platform: read, extract and collectively debate a text — AI-augmented.*

[![Python 3.14+](https://img.shields.io/badge/python-3.14+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Django 6.0](https://img.shields.io/badge/django-6.0-092E20?logo=django&logoColor=white)](https://djangoproject.com)
[![HTMX](https://img.shields.io/badge/htmx-2.0-3366CC?logo=htmx&logoColor=white)](https://htmx.org)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen?logo=pytest&logoColor=white)](#tests)
[![License](https://img.shields.io/badge/license-AGPLv3-blue)](LICENSE)

</div>

---

## En bref / Overview

Hypostasia aide un groupe de lecteurs a **debattre d'un texte** de maniere structuree.

*Hypostasia helps a group of readers to **debate a text** in a structured way.*

1. **Importez** un texte (PDF, audio, page web, Word...)
2. **L'IA extrait** les passages cles et les classe par type (hypothese, definition, paradoxe...)
3. **Commentez** chaque passage. Le statut evolue selon le debat.
4. **Synthetisez** le carnet : un wiki vivant, ou une synthese figee et datee
   que le collectif adopte. Chaque affirmation reste reliee a ses preuves.

**Tout peut se faire sans IA.** L'extraction de passages, les commentaires, les debats et la redaction de restitutions fonctionnent entierement a la main. L'IA est une option a chaque etape — jamais une obligation.

Quand l'IA est sollicitee, **tout est transparent** : le prompt complet est visible, le nombre de tokens et le cout sont estimes avant chaque appel, et le modele utilise est affiche.

---

## Installation rapide / Quick Start

### Prerequis / Prerequisites

- [Docker](https://docs.docker.com/get-docker/) + Docker Compose
- Un nom de domaine (pour la prod) ou `localhost` (pour le dev)

### 1. Cloner et configurer / Clone and configure

```bash
git clone https://github.com/CoopCodeCommun/Hypostasia.git
cd Hypostasia
make install
```

`make install` fabrique le `.env` s'il n'existe pas, puis demarre tout.
Il pose **trois questions** :

| Question | Ce qu'elle ecrit |
|---|---|
| poste de dev, ou machine de production ? | `DEBUG` **et** `NGINX_CONF`, ensemble |
| le domaine ? | `DOMAIN` (defaut `h.localhost` en dev) |
| une cle de modele ? (facultative) | `GOOGLE_API_KEY`, `OPENAI_API_KEY`, … |

`SECRET_KEY` et `POSTGRES_PASSWORD` ne sont **jamais demandees** : elles
sont tirees au hasard. Une cle saisie a la main est une cle faible, ou
recopiee d'un autre projet.

Les deux premieres lignes vont ensemble par construction, et c'est le
but : `DEBUG=true` avec la conf nginx de production envoie `/` vers un
port ou personne n'ecoute, et tout le site rend 502. Une seule question,
deux lignes ecrites.

Un `.env` deja present n'est **jamais** touche : `make install` est
rejoue a chaque demarrage de conteneur, et le regenerer perdrait les
cles API, le mot de passe de la base et la passphrase du depot de
sauvegarde. Pour le refaire, le supprimer d'abord.

*`make install` builds the `.env` if missing — three questions, secrets
drawn at random — then starts everything. An existing `.env` is never
touched.*

### 2. Ce que fait l'installation / What the install does

Au demarrage, le conteneur lance `bin/start-dev.sh` ou
`bin/start-prod.sh` selon `DEBUG` ; les deux appellent `bin/install.sh`,
qui fait automatiquement :

*That's it. On startup the container runs `bin/start-dev.sh` or
`bin/start-prod.sh` depending on `DEBUG`; both call `bin/install.sh`:*

1. `uv sync` — installation des dependances
2. `migrate` — creation/mise a jour des tables
3. `collectstatic` — fichiers CSS/JS
4. `charger_fixtures_sample` — les documents etalons de `sample/`, la base de connaissances et le carnet
5. `charger_extractions_demo` — leurs extractions et commentaires
6. `analyser_les_notes_etalons` — les notes du carnet analysees par le **vrai** modele, ce qui teste les cles API

`bin/install.sh` est **idempotent** : il peut etre relance sans risque a
chaque redemarrage. Le premier passage convertit deux PDF avec Docling
(~3 min) ; les suivants prennent une dizaine de secondes, et l'analyse
par le modele ne se refacture pas.

*`bin/install.sh` is **idempotent**: safe to run on every restart. The
first run converts two PDFs (~3 min); later runs take about ten seconds
and no LLM call is re-billed.*

**Compte cree** : `jonas` (admin) — mot de passe : `admin1234`

*Les quatre comptes de demonstration (`marie`, `thomas`, `fatima`, `pierre`)
venaient de `charger_fixtures_demo`, qui n'est plus lancee par l'installation.*

---

## Mode dev vs mode prod / Dev vs Prod mode

Le **meme** `docker-compose.yml` gere les deux modes. La variable `DEBUG` dans `.env` determine le comportement.

*The **same** `docker-compose.yml` handles both modes. The `DEBUG` variable in `.env` determines the behavior.*

| | `DEBUG=true` (dev) | `DEBUG=false` (prod) |
|---|---|---|
| **Demarrage** | `bin/start-dev.sh` | `bin/start-prod.sh` |
| **Serveur HTTP** | `runserver` **:8000** (ASGI, sert aussi le WebSocket) | Gunicorn **:8001** |
| **WebSocket** | le meme `runserver` | Daphne **:8000** |
| **Celery** | 2 workers (`supervisord-dev.conf`) | 2 workers (`supervisord.conf`) |
| **Nginx** | tout vers `web:8000` | `/` vers `web:8001`, `/ws/` vers `web:8000` |
| **Config Nginx** | `NGINX_CONF=dev.conf` dans `.env` | `NGINX_CONF=default.conf` (defaut) |

> **`DEBUG` et `NGINX_CONF` se changent ENSEMBLE.** La configuration de
> prod avec `DEBUG=true` envoie `/` vers le port 8001, ou aucun process
> n'ecoute : 502 sur tout le site. L'inverse laisse Gunicorn sans trafic.
>
> *Change both together: the production nginx config with `DEBUG=true`
> targets a port nobody listens on.*

### Developpement / Development

```bash
# .env
DEBUG=true
NGINX_CONF=dev.conf
POSTGRES_HOST=localhost    # si PostgreSQL est hors Docker

# Lancer les containers / Start containers
docker compose up -d

# Tout passe par le Makefile, depuis l'hote / Everything via the Makefile
make install        # docker compose up -d + install.sh (idempotent)
make dev            # serveur + les DEUX workers Celery
make status
make restart S=runserver
make logs S=celery_worker_docling

make                # liste toutes les cibles / lists every target
```

Deux workers Celery, et non un seul : `celery_worker` (file par defaut,
concurrence 2) et `celery_worker_docling` (file `ingestion_docling`,
**concurrence 1** — une conversion Docling a la fois, elles pesent ~2 Go
chacune). Meme topologie qu'en production (`supervisord.conf`).

*Two Celery workers, not one: the Docling queue is served alone, one
conversion at a time. Same topology as production.*

Ou sans Docker (Python local — necessite PostgreSQL et Redis installes) :

*Or without Docker (local Python — requires PostgreSQL and Redis installed):*

```bash
# Configurer le .env / Configure .env
cp .env.example .env
# Editer : POSTGRES_HOST=localhost, DEBUG=true

# Installer tout (dependances, migrations, static, fixtures)
# / Install everything (dependencies, migrations, static, fixtures)
bash bin/install.sh

# Lancer le serveur / Start server
python manage.py runserver 0.0.0.0:8000

# (Autre terminal) Les DEUX workers Celery — le second est DEDIE a
# l'ingestion Docling, a concurrence 1 : une conversion a la fois.
# / (Other terminals) BOTH Celery workers; the second is dedicated to
# Docling ingestion at concurrency 1.
celery -A hypostasia worker --loglevel=info --concurrency=2
celery -A hypostasia worker --loglevel=info --concurrency=1 -Q ingestion_docling
```

Acces : http://localhost:8000/ — Se connecter avec `jonas` / `admin1234`

### Production

```bash
# .env
DEBUG=false
DOMAIN=hypo.example.com
SECRET_KEY=cle_longue_aleatoire
POSTGRES_PASSWORD=mot_de_passe_fort

# Lancer / Start
docker compose up -d

# bin/start-prod.sh attend PostgreSQL, lance bin/install.sh (migrations,
# statiques, documents, analyse), puis supervisord : gunicorn:8001,
# daphne:8000 et les DEUX workers Celery.
```

### Mise a jour en production / Production update

```bash
make prod-update CONTENEUR=hypostasia_dev_web
```

Cette cible refuse de tourner si `.env` porte `DEBUG=true` — elle n'a de
sens que sur la machine de production. Elle enchaine `git pull`, `uv
sync`, `migrate`, `collectstatic`, puis redemarre les **quatre**
programmes : `gunicorn`, `daphne`, `celery_worker` et
`celery_worker_docling`. Le nom du conteneur est a preciser car
`docker-compose-prod.yml` nomme les siens `hypostasia_dev_web`.

*Refuses to run when `.env` has `DEBUG=true`; restarts all four
programs, not just two.*

### Ce qu'il reste a poser sur une prod / Production readiness

```bash
make verif-prod
```

Un bilan en deux temps : la configuration (secrets restes a la valeur
d'exemple, `DEBUG` et `NGINX_CONF` coherents, `DOMAIN` renseigne) et la
sauvegarde (depot borg joignable, age de la derniere archive, ligne de
cron posee). Il sort en code non nul au moindre probleme — utilisable
tel quel dans un monitoring.

`make install` l'appelle aussi, avec deux differences : il se **saute
entierement** sur un poste de dev (`DEBUG=true`), et il n'arrete
**jamais** l'installation. Le depot de sauvegarde se cree depuis la
machine installee : exiger qu'il existe deja tiendrait de l'oeuf et de
la poule.

*Two-part report: configuration and backup. Non-zero on any problem.
`make install` runs it too, skipped on a dev box and never fatal.*

---

## Sauvegarde et restauration / Backup and restore

La sauvegarde suit le kit [borgwarehouse](https://github.com/CoopCodeCommun/borgwarehouse) :
depot chiffre distant, une cle SSH dediee, aucun secret dans les
scripts. Tout vit dans `bin/`, tout se lance **depuis l'hote** — le cron
et la cle SSH sont sur la machine, pas dans le conteneur.

```bash
make backup          # sauvegarde ; au 1er lancement, configure tout d'abord
make backup-check    # la derniere archive est-elle VRAIMENT restaurable ?
make restore         # ECRASE la base depuis une archive (confirmation exigee)
make restore ARCHIVE=hypostasia-jonas-FW13-2026-08-16-03-00-12
```

**Une seule commande a retenir.** Au premier lancement sur une machine,
`make backup` voit que rien n'est configure et enchaine : cle SSH
dediee, creation du depot, ecriture du `.env`, cron, puis la premiere
sauvegarde et sa verification. Les fois suivantes, il sauvegarde
directement. Il n'y a pas de commande d'initialisation a retrouver le
jour ou on en a besoin.

Les archives portent le **nom de la machine** :
`hypostasia-jonas-FW13-2026-08-16-12-05-13`. C'est ce qui permet de
reconnaitre d'ou vient une sauvegarde quand plusieurs machines
partagent un serveur — et c'est une question de moins, `hostname` y
repondant mieux que quiconque.

Le depot se cree tout seul quand la variable `borgwarehouse_ccc_api` est
exportee (c'est le cas sur les serveurs de production) ; sinon le jeton
est demande, ou le depot se cree a la main dans l'interface.

*One command: `make backup` configures itself on a fresh machine, then
backs up.*

### Ce que contient une archive / What an archive holds

| Contenu | Pourquoi |
|---|---|
| dump PostgreSQL (`-Fc`) | la base entiere, restaurable par `pg_restore` |
| `media/` | PDF, audios, transcriptions — hors git, irremplacables |
| `.env` | cles API et mots de passe |

Le code, `docker-compose.yml`, `nginx/` et `sample/` sont dans git : les
rearchiver chaque nuit n'apporterait rien qu'un `git clone` ne rende
deja. Une restauration complete se lit donc :

```bash
git clone <depot> && cd Hypostasia
cp <le .env sorti du coffre> .env
make install     # la stack, vide
make restore     # les donnees
```

### `make backup-check` : la seule question qui compte

Verifier qu'une archive *existe* ne dit rien. Cette cible repond a
*est-ce restaurable ?* — sans rien restaurer :

1. **Fraicheur** — moins de `AGE_MAX_HEURES` (25 h par defaut). Au-dela,
   le cron est mort et personne ne l'avait remarque.
2. **Contenu** — le dump, `media/` et le `.env` sont bien dedans.
3. **Exploitabilite** — le dump est **deroule entierement** dans
   `pg_restore -f /dev/null`.

Le point 3 est celui qui compte. Mesure du 16 aout 2026 sur ce projet
(PostgreSQL 17.10, dump de 417 Ko ampute de ses **100 derniers octets**) :

| | dump sain | dump ampute de 100 o |
|---|---|---|
| `pg_restore -l` | code 0 | **code 0** — au vert |
| `pg_restore -f /dev/null` | code 0 | code 1 |

Un dump tronque — disque plein, conteneur tue en plein dump — a une
taille credible, se trouve bien dans l'archive, et ne se restaure pas.
Seul le deroulement integral le demasque.

### Ce que la sauvegarde ne peut pas se sauvegarder elle-meme

**Quatre** elements, et il en faut quatre :

| Au coffre | Ce qu'il ouvre |
|---|---|
| l'adresse du depot | ou aller |
| la passphrase | le chiffrement |
| `borg key export` | le chiffrement |
| **la cle SSH privee** (`bin/.ssh/<prefixe>_ed25519`) | **l'acces** |

Le premier `make backup` les affiche **tous les quatre, en entier**,
entre deux lignes `----8<----`, avec la recette de restauration : on
selectionne, on copie, on colle dans le coffre. Puis il attend un `OUI`.
Ce que l'on ne voit pas, on ne le copie pas — c'est pourquoi la cle
privee est affichee, et pas seulement son chemin.

Sur borgwarehouse, le depot n'accepte que la cle publique enregistree
sur lui : sans la privee, une machine de secours se fait refuser par SSH
avant meme d'avoir a prouver qu'elle connait la passphrase. A defaut, il
restera a coller une nouvelle cle publique sur le depot depuis
l'interface.

> **Le NOM du fichier de cle compte.** Les scripts cherchent
> `bin/.ssh/<BORG_PREFIX>_ed25519`, et rien d'autre. Une cle reposee sous
> un autre nom n'est pas vue : ssh se rabat sur la configuration systeme,
> et le refus parle de permissions, jamais de nom de fichier. Le bloc du
> coffre porte le nom exact ; `make restore` le rappelle aussi quand la
> cle manque et que le depot est distant.

### Restaurer sur une autre machine

```bash
git clone <le depot git> && cd Hypostasia
make install                     # repond aux 3 questions
# ajouter au .env les trois lignes BORG_* du coffre
mkdir -p bin/.ssh && chmod 700 bin/.ssh
# coller la cle privee dans bin/.ssh/<BORG_PREFIX>_ed25519
chmod 600 bin/.ssh/<BORG_PREFIX>_ed25519
make restore
```

Verifier une fois, **depuis une autre machine**, qu'un `borg list` passe
avec les elements du coffre — `make backup-check`, lui, utilise le
`.env` de la machine, pas ta copie.

*Four items, not three: the SSH private key opens the access, the other
three open the encryption. All four are printed in full, ready to copy.*

*The one link a backup cannot back up: the repository passphrase and
exported key. Verify them once from another machine.*

---

## Architecture

```
Hypostasia/
+-- core/                       # Modeles de donnees (Page, Dossier, AIModel)
+-- hypostasis_extractor/       # Pipeline LangExtract + Analyseurs + Tests LLM
+-- front/                      # Interface lecture (HTMX partials)
|   +-- services/               # Transcription audio, conversion fichiers
|   +-- tasks.py                # Taches Celery asynchrones
|   +-- management/commands/    # Fixtures (charger_fixtures_sample, charger_extractions_demo)
+-- hypostasia/                 # Config Django (settings, urls, celery)
+-- nginx/                      # Configs Nginx (dev.conf, default.conf)
+-- Dockerfile
+-- docker-compose.yml          # Unique dev/prod
+-- bin/                        # install.sh, start-dev.sh, start-prod.sh, backup*
+-- supervisord.conf
+-- AGENTS.md                   # Regles pour agents IA (CLAUDE.md y pointe)
+-- PLAN/archive/PHASES/        # Historique des phases 1 a 29
```

### Apps Django

| App | Role |
|-----|------|
| `core` | Modeles fondamentaux + API JSON pour l'extension navigateur |
| `hypostasis_extractor` | Pipeline LangExtract, analyseurs configurables, tests LLM |
| `front` | Interface HTMX : lecture, extractions, debat, alignement, dashboard |

### Stack technique / Tech stack

| Composant | Technologie |
|-----------|------------|
| Backend | Django 6.0 + DRF ViewSets explicites |
| Frontend | HTMX + Tailwind CSS (100% server-rendered, zero SPA) |
| Base de donnees | PostgreSQL 17 |
| Cache / Broker | Redis 7 |
| Taches async | Celery + django-celery-results |
| Transcription | Mistral Voxtral (diarisation des locuteurs) |
| Extraction IA | LangExtract (Google Gemini, OpenAI, Ollama) |
| Deploiement | Docker + Nginx + Gunicorn + Supervisord |
| Reverse proxy | Traefik (labels dans docker-compose) |

---

## Configuration des modeles IA / AI model configuration

Les cles API peuvent etre configurees de deux manieres (priorite DB > .env) :

*API keys can be configured in two ways (DB priority > .env):*

1. **Variables d'environnement** dans `.env` (recommande)
2. **Champs dans l'admin Django** (`/admin/core/aimodel/`)

### Providers supportes / Supported providers

| Provider | Modeles | Variable .env |
|----------|---------|---------------|
| Google Gemini | 2.5 Pro, 2.5 Flash, 2.0 Flash, 1.5 Pro/Flash | `GOOGLE_API_KEY` |
| OpenAI | GPT-4o, 4o-mini, 4-Turbo, 4.1 | `OPENAI_API_KEY` |
| Anthropic | Claude Sonnet 4, Haiku 4 | `ANTHROPIC_API_KEY` |
| Mistral (audio) | Voxtral Mini, Mistral Small/Large | `MISTRAL_API_KEY` |
| Ollama (local) | Llama3, Mistral, Gemma2, Qwen2.5... | Aucune cle |

Les tarifs par modele sont affiches dans le selecteur (`/api/analyseurs/`).

### Page de configuration / Configuration page

Accessible via l'icone engrenage dans la toolbar ou `/api/analyseurs/`. Permet de :
- Choisir le modele LLM actif et voir les tarifs
- Configurer les analyseurs (prompts, exemples few-shot)
- Voir le modele audio actif et son tarif

---

## Donnees de demonstration / Demo data

**`make install` s'en charge** — il n'y a rien de plus a lancer. Les trois
commandes ci-dessous sont celles que `bin/install.sh` enchaine, dans cet ordre :

*`make install` handles this. The three commands below are the ones
`bin/install.sh` runs, in this order.*

```bash
# 1. Les six documents etalons de sample/, la base de connaissances,
#    le carnet et les analyseurs. Premier passage ~3 min (deux
#    conversions Docling reelles), 10 s ensuite.
python manage.py charger_fixtures_sample

# 2. Les extractions et les commentaires, poses A LA MAIN, sans aucun
#    appel LLM.
python manage.py charger_extractions_demo

# 3. Une analyse par le VRAI modele configure — c'est ce qui fait de
#    l'installation un test des cles API. N'analyse que ce qui ne l'est
#    pas encore : un redemarrage ne refacture rien.
python manage.py analyser_les_notes_etalons
```

Ce que ca cree :

- **1 utilisateur** : `jonas` / `admin1234`
- **6 notes** couvrant les cinq formes d'entree du produit — capture web,
  fichier ecrit, transcription deja faite, audio brut, deux PDF. Leur decompte
  exact (elements, coordonnees de page) est dans `PLAN/PASSATION.md` § 3, mesure
  et date
- **Des extractions ecrites a la main**, choisies pour couvrir des cas limites
  qu'un modele ne produit pas a coup sur : les 8 familles d'hypostases, deux
  idees superposees sur un meme element, une idee qui enjambe deux elements,
  une ancre portee par un tableau, des cartes a 0, 1 et 2 commentaires

> **Pour tout refaire de zero**, voir « Demarrage depuis zero » plus bas :
> une seule voie, et pas de rechargement partiel.

> `charger_fixtures_demo` existe encore dans le depot mais **n'est plus
> appelee par l'installation** : elle ecrit des notes fictives et ne cree
> aucune base de connaissances. Elle a longtemps ete lancee a la place des
> trois commandes ci-dessus, ce qui donnait un `/bases/` vide sur une
> installation neuve (corrige le 15 aout 2026).

---

## Tests

**Tout passe par le `Makefile`, depuis l'hote.** Les commandes ne sont ecrites
qu'a un seul endroit : une seconde copie finit toujours par mentir sur les
nombres et les durees.

*Everything goes through the Makefile, from the host. Commands live in one
place only.*

```bash
make test           # l'aide : les cibles, leur perimetre et leur COUT MESURE
```

**`make test` est la seule liste a jour.** Elle est generee par le `Makefile`,
qui porte les comptes et les durees a cote de chaque cible — les recopier ici
en ferait une seconde source, qui divergerait. Les cibles : `test-rapide` (le
geste quotidien), `test-suite S=...`, `test-e2e [S=...]`, `test-docling`,
`test-llm`, `test-tout`.

Quatre familles, et elles ne coutent pas la meme chose. **Les tests couteux
sont opt-in par deux mecanismes a la fois** : une variable d'environnement
(`TESTS_DOCLING`, `TESTS_LLM_REELS`) **et** un tag Django. Les e2e, eux, sont
tagues `e2e` par leur classe de base (`front/tests/e2e/base.py`) — c'est ce qui
permet a `test-rapide` de les exclure.

*The expensive suites are opt-in through both an environment variable and a
Django tag; e2e tests are tagged by their base class.*

### Une suite a la fois, jamais `--parallel`

La base de test est partagee : deux executions simultanees se la detruisent
mutuellement en plein vol. C'est deja arrive — 755 erreurs fantomes, sans aucun
rapport avec le code.

*One suite at a time. Two concurrent runs destroy the shared test database.*

### Ou ecrire un test

| Ce qu'on teste | Ou |
|---|---|
| du **Python** — modele, serializer, vue, service | `front/tests/`, `core/tests/`, `hypostasis_extractor/tests/` |
| du **navigateur** — rendu, HTMX, WebSocket, CSS, JS | `front/tests/e2e/` (Playwright) |
| **les deux** | un test serveur *et* un test e2e |

Detail des conventions et des pieges : `front/tests/README.md`.

**La derniere mesure de la suite complete est dans `PLAN/PASSATION.md` § 7**,
avec sa date. Elle n'est pas recopiee ici : un chiffre a deux endroits finit
toujours par differer entre les deux.

---

## Cycle deliberatif / Deliberative cycle

Le coeur d'Hypostasia est un cycle en 4 etapes qui transforme un texte brut en synthese collective.

*The core of Hypostasia is a 4-step cycle that transforms raw text into a collective synthesis.*

### 1. Extraction

L'IA (ou l'utilisateur) extrait les passages cles du texte et les classe par **hypostase** — une maniere d'etre discutable, parmi les 30 que definit la geometrie des debats (theorie, hypothese, paradoxe, donnee, principe...). Ces 30 se repartissent en **6 familles epistemiques** : voir [Les 30 hypostases](#les-30-hypostases--la-geometrie-des-debats) ci-dessous.

*The AI (or the user) extracts key passages and classifies them by **hypostasis** — one of the 30 ways of being debatable defined by the geometry of debates, split into 6 epistemic families.*

> Ne pas confondre avec les **8 familles de couleurs** utilisees pour l'affichage des cartes d'extraction (`hypostase_famille`) : ce regroupement-la est purement visuel et sans rapport avec les 6 familles epistemiques.
>
> *Not to be confused with the 8 colour families used for card display: that grouping is purely visual.*

### 2. Debat

Chaque extraction porte un statut de debat, et il n'en existe que **deux** :

| Statut | Signification |
|--------|---------------|
| **Nouveau** | personne n'a encore reagi |
| **Commente** | au moins une intervention humaine |

*Two statuses only: **new** (nobody reacted yet) and **commented** (at least one
human intervention).*

> Les six statuts d'autrefois — consensuel, discutable, discute, controverse,
> non pertinent — ont ete fusionnes le 2 mai 2026 : ils demandaient a chaque
> lecteur de qualifier un debat qu'il venait de decouvrir, et personne ne le
> faisait. Ce qui porte le debat, ce sont les commentaires eux-memes.
> Definition : `hypostasis_extractor/models.py:186`.

### 3. Alignement et comparaison

Le **tableau d'alignement** croise hypostases (lignes) et documents (colonnes) pour reveler les gaps argumentatifs entre 2 a 6 textes. Chaque cellule montre le nombre d'extractions et un resume.

Entre deux **versions** d'un meme texte, la comparaison affiche :
- Un **diff side-by-side** mot a mot (ajouts en vert, suppressions en rouge)
- Un **tableau d'alignement des hypostases** avec deltas (ajoute / supprime / conserve + evolution du statut)

### 4. Synthese

Une synthese n'est PAS une nouvelle version du texte : c'est une **note du
carnet**, en deux genres qui ne se melangent pas.

| Genre | Ce que c'est |
|---|---|
| **Wiki** | un article thematique **vivant**, mis a jour par operations de section a mesure que le carnet grossit |
| **Synthese dirigee** | un **acte date et fige**, qu'un collectif adopte et auquel il peut se referer six mois plus tard |

Chaque affirmation est reliee a ses preuves par un lien persiste, controle
mecaniquement (verbatim, puis implication). Et la synthese expose **ce qu'elle
n'a pas repris** et **ce que l'analyse n'a jamais lu** — c'est ce qui la rend
contestable dans l'outil.

Le prompt complet est visible et le cout estime avant l'appel.

*A synthesis is not a new version of the text but a typed note of the notebook:
either a living **wiki** or a frozen, dated **directed synthesis**. Every claim
links to its evidence, and the synthesis shows what it left out.*

> Le modele d'avant — une V2 du document, chainee a la V1 par `parent_page` —
> a ete abandonne le 9 aout 2026. Le champ existe encore en base mais n'a plus
> aucun ecrivain en production. Le pourquoi est dans `PRESENTATION-V3.md` § 1 ;
> le detail dans `SPEC-synthese-carnet.md`.

---

## Les 30 hypostases — la geometrie des debats

Une **hypostase** est une maniere d'etre discutable. C'est le concept fondateur
du projet — d'ou son nom.

*A **hypostasis** is a way of being debatable. It is the founding concept of the
project — hence its name.*

Le compte de 30 n'est pas arbitraire, il se **deduit** : une idee peut etre mise
a l'epreuve de 2 manieres (formelle, empirique) selon 3 modes de raisonnement
(induction, abduction, deduction), soit **6 modes**. Chaque hypostase est alors
un couple — ce qui ne peut pas la refuter, ce qui ne peut pas la prouver — les
deux etant distincts : **6 x 5 = 30**.

*The count is derived, not arbitrary: 2 proof devices x 3 reasoning modes = 6;
each hypostasis is a pair of two distinct modes — 6 x 5 = 30.*

**La matrice complete, les 6 familles epistemiques et le raisonnement qui les
fonde : [`PRESENTATION-V3.md` § 8](PRESENTATION-V3.md).**

> Ne pas confondre les **6 familles epistemiques** (ci-dessus) avec les
> **8 familles de couleurs** de l'affichage — voir l'encadre de la section
> « Cycle deliberatif ».

---

## Demarrage depuis zero / Starting from scratch

Apres un `docker compose down -v` (qui supprime la base de donnees), tout est recree automatiquement au redemarrage.

*After a `docker compose down -v` (which deletes the database), everything is recreated automatically on restart.*

```bash
# Detruire et reconstruire / Destroy and rebuild
docker compose down -v
docker compose build
docker compose up -d

# Le conteneur installe et demarre tout seul, dans les deux modes.
# Suivre l'operation : / Follow along:
docker compose logs -f web
```

`bin/install.sh` execute dans l'ordre :

1. `uv sync` — dependances Python
2. `migrate` — schema + migration de normalisation des attributs
3. `collectstatic` — fichiers CSS/JS
4. `charger_fixtures_sample` — les documents etalons de `sample/`, la base de connaissances, le carnet
5. `charger_extractions_demo` — leurs extractions et commentaires
6. `analyser_les_notes_etalons` — les notes du carnet analysees par le **vrai** modele, en file Celery

Resultat : le compte `jonas`, la base « Demonstration », le carnet
« Documents etalons » et ses six notes couvrant les cinq formes d'entree
du produit (capture web, fichier ecrit, transcription, audio, deux PDF),
leurs extractions, et deux notes analysees par le modele configure —
pret a l'emploi.

Les etapes s'appellent aussi une par une : `bash bin/install.sh fixtures`,
`statiques`, ou `llm`.

*Result: the `jonas` account, the "Demonstration" knowledge base, the
"Documents etalons" notebook and its six notes covering the product's
five input forms, their extractions, and two notes analysed by the
configured model. Steps can be run one at a time.*

### Fixtures disponibles / Available fixtures

Il n'y a plus de fichiers `loaddata` : les donnees de demonstration sont
produites par des COMMANDES, qui savent ce qui existe deja et ne
recreent que ce qui manque.

*No more `loaddata` files: demo data comes from COMMANDS that only
create what is missing.*

| Commande | Contenu |
|----------|---------|
| `charger_fixtures_sample` | Les 6 documents de `sample/` (capture web, markdown, transcription, audio, 2 PDF), la base de connaissances, le carnet, les analyseurs |
| `charger_extractions_demo` | Leurs extractions et commentaires, ecrits a la main (cas limites : marques imbriquees, ancre sur tableau, cartes a 0/1/2 commentaires) |
| `analyser_les_notes_etalons` | Envoie a l'analyse par le **vrai** modele les notes du carnet qui ne le sont pas encore. Ne cree ni note ni carnet. Saute celles de plus de 100 elements (cout). |
| `charger_fixtures_demo` | Un jeu de notes fictives, sans base de connaissances. N'est plus lance par l'installation. |

Les trois premieres sont enchainees par `bin/install.sh`, donc a chaque
demarrage du conteneur, et chacune saute ce qui existe deja.

**Pour tout refaire, une seule voie** : `docker compose down -v && make
install`. Il n'existe pas de cible de rechargement partiel — elle
laisserait un melange, moitie donnees d'avant, moitie d'apres, sans
qu'on sache ce que porte la base. Les etapes restent appelables a la
main pour un cas particulier : `docker exec -w /app hypostasia_web bash
bin/install.sh fixtures` (ou `statiques`, ou `llm`).

*One way to redo everything: `down -v` then `make install`. No partial
reload, so no doubt about what the database holds.*

Les **quatre fixtures JSON** (`demo_ia.json`, `demo_completes.json`,
`exemple_deliberation.json`, `demo_alignement_versions.json`) ont ete
supprimees le 15 aout 2026 : rien ne les chargeait, et trois d'entre
elles ne se chargeaient plus depuis le 21 mars 2026 — deux migrations
avaient change le schema sous elles. Elles restent dans l'historique git.

*The four JSON fixtures were removed on 15 August 2026: nothing loaded
them, and three had been unloadable for five months. They remain in git
history.*

---

## Accessibilite / Accessibility

- **Palette daltonien-safe** (Wong 2011) pour les couleurs de locuteurs dans les
  transcriptions : la meme personne garde la meme couleur dans la gouttiere, les
  pilules et le lecteur audio.
- **WCAG** : `aria-hidden` sur les icones decoratives, `aria-live` sur les zones
  mises a jour par HTMX, contrastes verifies au navigateur en clair et en sombre.
- **Raccourcis clavier** (`front/static/front/js/keyboard.js`, le seul listener
  de l'application) : `E` panneau d'extractions, `J`/`K` extraction
  suivante/precedente, `C` commenter, `X` masquer, `A` alignement, `Z` comparer
  les versions, `/` recherche, `?` aide.

---

## Licence / License

[AGPLv3](LICENSE) — Cooperative Code Commun

---

<div align="center">
<sub>Hypostasia — lire, extraire et debattre collectivement d'un texte</sub>
</div>
