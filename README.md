<div align="center">

# Hypostasia

**Plateforme de lecture deliberative : lire, extraire et debattre collectivement d'un texte — augmentee par IA.**

*Deliberative reading platform: read, extract and collectively debate a text — AI-augmented.*

[![Python 3.14+](https://img.shields.io/badge/python-3.14+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Django 6.0](https://img.shields.io/badge/django-6.0-092E20?logo=django&logoColor=white)](https://djangoproject.com)
[![HTMX](https://img.shields.io/badge/htmx-2.0-3366CC?logo=htmx&logoColor=white)](https://htmx.org)
[![Tests](https://img.shields.io/badge/tests-865_passed-brightgreen?logo=pytest&logoColor=white)](#tests)
[![License](https://img.shields.io/badge/license-AGPLv3-blue)](LICENSE)

</div>

---

## En bref / Overview

Hypostasia aide un groupe de lecteurs a **debattre d'un texte** de maniere structuree.

*Hypostasia helps a group of readers to **debate a text** in a structured way.*

1. **Importez** un texte (PDF, audio, page web, Word...)
2. **L'IA extrait** les passages cles et les classe par type (hypothese, definition, paradoxe...)
3. **Commentez** chaque passage. Le statut evolue selon le debat.
4. Quand le groupe est **d'accord sur 80%** du texte, la synthese peut etre lancee.

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

# Copier le fichier d'environnement / Copy the environment file
cp .env.example .env
```

Editez `.env` avec vos valeurs :

```ini
# --- Obligatoire / Required ---
DOMAIN=hypo.example.com
SECRET_KEY=votre_cle_secrete_aleatoire
POSTGRES_PASSWORD=un_mot_de_passe_fort

# --- Dev ou Prod / Dev or Prod ---
DEBUG=true     # true = mode dev, false = mode prod

# --- Cles API (optionnel) / API keys (optional) ---
GOOGLE_API_KEY=
OPENAI_API_KEY=
MISTRAL_API_KEY=
```

### 2. Lancer / Start

```bash
docker compose up -d
```

C'est tout. Au demarrage, le conteneur lance `bin/start-dev.sh` ou
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

**Comptes crees** : `jonas` (admin), `marie`, `thomas`, `fatima`, `pierre` — mot de passe : `demo1234`

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

Acces : http://localhost:8000/ — Se connecter avec `jonas` / `demo1234`

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

---

## Architecture

```
Hypostasia/
+-- core/                       # Modeles de donnees (Page, Dossier, AIModel)
+-- hypostasis_extractor/       # Pipeline LangExtract + Analyseurs + Tests LLM
+-- front/                      # Interface lecture (HTMX partials)
|   +-- services/               # Transcription audio, conversion fichiers
|   +-- tasks.py                # Taches Celery asynchrones
|   +-- management/commands/    # Fixtures de demo (charger_fixtures_demo)
+-- hypostasia/                 # Config Django (settings, urls, celery)
+-- nginx/                      # Configs Nginx (dev.conf, default.conf)
+-- Dockerfile
+-- docker-compose.yml          # Unique dev/prod
+-- start.sh                    # Demarrage prod (migrations + supervisord)
+-- supervisord.conf
+-- CLAUDE.md                   # Regles pour agents IA
+-- PLAN/PHASES/                # Plan de developpement par phases
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

La commande `charger_fixtures_demo` cree un jeu de donnees complet :

```bash
# Charger les fixtures (4 pages, 33 extractions, 49 commentaires)
uv run python manage.py charger_fixtures_demo

# Reset complet et rechargement
uv run python manage.py charger_fixtures_demo --reset
```

Contenu cree :
- **5 utilisateurs** : jonas (admin), marie, thomas, fatima, pierre
- **1 dossier** : "Demonstration" (public, partage avec marie)
- **4 pages** : 3 articles Wikipedia (Ostrom, Alexandre, Sadin) + 1 debat fictif
- **33 extractions** avec positions exactes dans le texte
- **49 commentaires** repartis entre les 4 utilisateurs
- **6 statuts** couverts : nouveau, discutable, discute, consensuel, controverse, non pertinent
- **Mot de passe** de tous les users demo : `demo1234`

---

## Tests

Le projet a deux niveaux de tests avec des roles distincts.

*The project has two test levels with distinct roles.*

### Tests unitaires (~35s) — apres chaque modification

Tests Django classiques (pas de navigateur). Verifient les modeles, les vues, les taches Celery, la normalisation des donnees et les helpers. Rapides, fiables, a lancer souvent.

*Standard Django tests (no browser). Check models, views, Celery tasks, data normalization and helpers. Fast, reliable, run often.*

```bash
# Verification Django (0 issues attendues) / Django check (0 issues expected)
docker exec hypostasia_web uv run python manage.py check

# Tous les tests unitaires (~35s, 78 tests)
# / All unit tests (~35s, 78 tests)
docker exec hypostasia_web uv run python manage.py test \
  front.tests.test_phases \
  front.tests.test_phase27a \
  front.tests.test_phase27b \
  front.tests.test_phase28_light \
  front.tests.test_phase29_normalize \
  front.tests.test_langextract_overrides \
  -v2 --keepdb
```

| Module | Tests | Ce qu'il verifie |
|--------|-------|------------------|
| `test_phases` | ~200 | CRUD pages/dossiers, import, extraction, transcription, config IA |
| `test_phase27a` | 19 | Modele PageEdit, historique, diff de contenu |
| `test_phase27b` | 24 | Diff side-by-side, alignement hypostases entre versions |
| `test_phase28_light` | 31 | Synthese deliberative : prompt, tache Celery, anti-doublon, XSS |
| `test_phase29_normalize` | 23 | Normalisation des attributs LLM (cles, hypostases, fuzzy match) |
| `test_langextract_overrides` | ~5 | Compatibilite des surcharges LangExtract |

### Tests E2E (~8 min) — avant un jalon

Tests Playwright dans un vrai navigateur Chromium. Verifient le rendu HTML, les interactions HTMX, les WebSockets et le CSS. Plus lents, necessitent Playwright installe.

*Playwright tests in a real Chromium browser. Check HTML rendering, HTMX interactions, WebSockets and CSS. Slower, require Playwright installed.*

```bash
# Un module E2E cible (~40s) / A targeted E2E module (~40s)
docker exec hypostasia_web uv run python manage.py test \
  front.tests.e2e.test_09_alignement -v2 --keepdb

# Tous les tests E2E (~8 min, ~790 tests)
# / All E2E tests (~8 min, ~790 tests)
docker exec hypostasia_web uv run python manage.py test \
  front.tests.e2e -v2 --keepdb
```

| Module E2E | Ce qu'il verifie |
|------------|------------------|
| `test_01_navigation` | Arbre de dossiers, toolbar, raccourcis clavier |
| `test_02_lecture` | Zone de lecture, pastilles de marge, surlignage |
| `test_03_import` | Import PDF, Word, audio, page web |
| `test_04_extractions` | Cartes d'extraction, extraction manuelle, drawer |
| `test_05_config_ia` | Toggle IA, selecteur de modele, tarifs |
| `test_08_curation` | Statuts de debat, commentaires, masquage |
| `test_09_alignement` | Tableau d'alignement cross-documents |
| `test_13_auth` | Authentification, permissions, roles |
| `test_17_filtre_contributeur` | Filtre par contributeur, palette daltonien-safe |
| `test_20_tracabilite` | Historique, diff versions, comparaison |

### Suite complete (~9 min)

```bash
# Tout d'un coup / Everything at once
docker exec hypostasia_web uv run python manage.py test front.tests -v1 --keepdb
```

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

Chaque extraction recoit un statut de debat qui evolue avec les commentaires :

| Statut | Signification |
|--------|---------------|
| **Consensuel** | Accord atteint |
| **Discutable** | A debattre |
| **Discute** | Debat en cours |
| **Controverse** | Desaccord fort |

### 3. Alignement et comparaison

Le **tableau d'alignement** croise hypostases (lignes) et documents (colonnes) pour reveler les gaps argumentatifs entre 2 a 6 textes. Chaque cellule montre le nombre d'extractions et un resume.

Entre deux **versions** d'un meme texte, la comparaison affiche :
- Un **diff side-by-side** mot a mot (ajouts en vert, suppressions en rouge)
- Un **tableau d'alignement des hypostases** avec deltas (ajoute / supprime / conserve + evolution du statut)

### 4. Synthese deliberative

Quand le consensus atteint 80%, l'IA peut generer une **nouvelle version** du texte qui integre les ponderations par statut. Le texte produit est une V2 autonome, chainnee a la V1 d'origine.

Le prompt complet est visible, le cout est estime avant l'appel, et la V2 peut etre re-analysee pour relancer un nouveau cycle.

---

## Les 30 hypostases — la geometrie des debats

Une **hypostase** est une maniere d'etre discutable. C'est le concept fondateur du projet — d'ou son nom.

*A **hypostasis** is a way of being debatable. It is the founding concept of the project — hence its name.*

### Pourquoi exactement 30

Le nombre n'est pas arbitraire : il se deduit.

Une idee peut etre mise a l'epreuve de **2 manieres** (les dispositifs de preuve) selon **3 modes de raisonnement** :

| Dispositif de preuve | Mode de raisonnement |
|---|---|
| formel, empirique | induction, abduction, deduction |

**2 × 3 = 6 modes de mise a l'epreuve.**

Chaque hypostase se definit alors par un couple :

1. **ce qui ne peut pas la refuter** — 6 choix ;
2. **ce qui ne peut pas la prouver** — 5 choix restants.

Le second ne peut pas etre egal au premier : un meme mode ne peut pas a la fois echouer a refuter et echouer a prouver la meme idee sans la vider de son sens.

**6 × 5 = 30 hypostases**, chacune occupant une case unique.

*The count is derived, not arbitrary: 2 proof devices x 3 reasoning modes = 6 modes; each hypostasis is a pair (what cannot refute it, what cannot prove it), the two being distinct — 6 x 5 = 30.*

### La matrice complete

Chaque case hors diagonale contient exactement une hypostase. La diagonale est vide par construction.

| non refutee par ↓ \ non prouvee par → | induction emp. | induction form. | abduction emp. | abduction form. | deduction emp. | deduction form. |
|---|---|---|---|---|---|---|
| **induction empirique** | — | formalisme | classification | paradoxe | aporie | approximation |
| **deduction empirique** | mode | croyance | variation | dimension | — | événement |
| **induction formelle** | axiome | — | valeur | structure | conjecture | invariant |
| **deduction formelle** | loi | principe | paradigme | objet | domaine | — |
| **abduction empirique** | variance | donnée | — | variable | indice | phénomène |
| **abduction formelle** | hypothèse | théorie | définition | — | problème | méthode |

La matrice se lit aussi par paires symetriques : `valeur` ↔ `donnée`, `conjecture` ↔ `croyance`, `structure` ↔ `théorie`, `principe` ↔ `invariant`... Les 15 paires sont completes.

### Les 6 familles epistemiques

Une **famille** regroupe les 5 hypostases qui partagent le meme « ce qui ne peut pas les refuter ».

*A **family** groups the 5 hypostases sharing the same "what cannot refute them".*

#### Famille 1 — non refutee par induction empirique

*Ce qu'on observe sans pouvoir generaliser.*

| Hypostase | Definition | Non prouvee par |
|---|---|---|
| **classification** | distribuer en classes, en catégories | abduction empirique |
| **aporie** | difficulté d'ordre rationnel apparemment sans issue | déduction empirique |
| **approximation** | calcul approché d'une grandeur réelle | déduction formelle |
| **paradoxe** | proposition à la fois vraie et fausse | abduction formelle |
| **formalisme** | considération de la forme d'un raisonnement | induction formelle |

#### Famille 2 — non refutee par deduction empirique

*Ce qui se produit sans cadre formel.*

| Hypostase | Definition | Non prouvee par |
|---|---|---|
| **événement** | ce qui arrive | déduction formelle |
| **variation** | changement d'un état dans un autre | abduction empirique |
| **dimension** | grandeur mesurable qui détermine des positions | abduction formelle |
| **mode** | manière d'être d'un système | induction empirique |
| **croyance** | certitude ou conviction qui fait croire une chose vraie ou possible | induction formelle |

#### Famille 3 — non refutee par induction formelle

*Ce qu'on formalise sans pouvoir verifier.*

| Hypostase | Definition | Non prouvee par |
|---|---|---|
| **invariant** | grandeur, relation ou propriété conservée lors d'une transformation | déduction formelle |
| **valeur** | mesure d'une grandeur variable | abduction empirique |
| **structure** | organisation des parties d'un système | abduction formelle |
| **axiome** | proposition admise au départ d'une théorie | induction empirique |
| **conjecture** | opinion ou proposition non vérifiée | déduction empirique |

#### Famille 4 — non refutee par deduction formelle

*Ce qu'on deduit formellement.*

| Hypostase | Definition | Non prouvee par |
|---|---|---|
| **paradigme** | modèle ou exemple | abduction empirique |
| **objet** | ce sur quoi porte le discours, la pensée, la connaissance | abduction formelle |
| **principe** | cause a priori d'une connaissance | induction formelle |
| **domaine** | champ discerné par des limites, bornes, frontières | déduction empirique |
| **loi** | corrélation | induction empirique |

#### Famille 5 — non refutee par abduction empirique

*Ce qu'on constate sans pouvoir l'expliquer.*

| Hypostase | Definition | Non prouvee par |
|---|---|---|
| **phénomène** | ce qui se manifeste à la connaissance via les sens | déduction formelle |
| **variable** | ce qui prend différentes valeurs, dont dépend l'état d'un système | abduction formelle |
| **variance** | dispersion d'une distribution ou d'un échantillon | induction empirique |
| **indice** | indicateur numérique ou littéral qui sert à distinguer ou classer | déduction empirique |
| **donnée** | ce qui est admis, donné, qui sert à découvrir ou à raisonner | induction formelle |

#### Famille 6 — non refutee par abduction formelle

*Ce qu'on propose sans pouvoir le confirmer.*

| Hypostase | Definition | Non prouvee par |
|---|---|---|
| **méthode** | procédure qui indique ce que l'on doit faire ou comment le faire | déduction formelle |
| **définition** | détermination, caractérisation du contenu d'un concept | abduction empirique |
| **hypothèse** | explication ou possibilité d'un événement | induction empirique |
| **problème** | difficulté à résoudre | déduction empirique |
| **théorie** | construction intellectuelle explicative, hypothétique et synthétique | induction formelle |

### Ou vit ce referentiel dans le code

Les 30 hypostases sont ecrites a **quatre endroits**, qui doivent rester d'accord :

| Emplacement | Role |
|---|---|
| `core/models.py` → `HypostasisChoices` | la taxonomie du modele |
| `front/services/fixtures_analyseurs.py` | le referentiel enseigne au LLM (le tableau ci-dessus) |
| `front/services/fixtures_analyseurs.py` | les 30 exemples few-shot, un par hypostase |
| `front/normalisation.py` → `HYPOSTASES_CONNUES` | **le filtre** : toute hypostase inconnue est supprimee |

`hypostasis_extractor/tests/test_referentiel_des_hypostases.py` verifie que les quatre concordent et que les 6 familles respectent le motif. Toute evolution du referentiel doit donc toucher les quatre ensemble.

> **Correction du 14 aout 2026.** La famille 4 violait le motif depuis l'origine : `principe` et `loi` occupaient la meme case, `domaine` occupait une case diagonale (interdite), et deux cases restaient vides. Le referentiel ne comptait donc reellement que 28 manieres d'etre discutable. `principe` est passe a *induction formelle* et `domaine` a *deduction empirique* ; `loi` n'a pas bouge. Les 30 cases sont desormais toutes occupees, une seule fois chacune.

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

- **Formes daltonien-safe** : chaque statut de debat a une forme unique (cercle, losange, triangle, carre, anneau, tiret) en plus de la couleur (palette Wong 2011)
- **WCAG** : pastilles 16px (min 24px au hover), `aria-hidden` sur les icones decoratives, `aria-live` sur les zones dynamiques HTMX
- **Raccourcis clavier** : `T` bibliotheque, `E` extractions, `J/K` navigation, `A` alignement, `?` aide

---

## Licence / License

[AGPLv3](LICENSE) — Cooperative Code Commun

---

<div align="center">
<sub>Hypostasia — lire, extraire et debattre collectivement d'un texte</sub>
</div>
