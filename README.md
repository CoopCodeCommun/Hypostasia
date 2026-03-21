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

C'est tout. Au demarrage, `start.sh` appelle `install.sh` qui fait automatiquement :

*That's it. On startup, `start.sh` calls `install.sh` which automatically runs:*

1. `uv sync` — installation des dependances
2. `migrate` — creation/mise a jour des tables
3. `collectstatic` — fichiers CSS/JS
4. `charger_fixtures_demo` — donnees de demo (idempotent, ne cree que ce qui manque)

`install.sh` est **idempotent** : il peut etre relance sans risque a chaque redemarrage. Les fixtures utilisent `get_or_create` — rien n'est ecrase.

*`install.sh` is **idempotent**: it can safely run on every restart. Fixtures use `get_or_create` — nothing is overwritten.*

**Comptes crees** : `jonas` (admin), `marie`, `thomas`, `fatima`, `pierre` — mot de passe : `demo1234`

---

## Mode dev vs mode prod / Dev vs Prod mode

Le **meme** `docker-compose.yml` gere les deux modes. La variable `DEBUG` dans `.env` determine le comportement.

*The **same** `docker-compose.yml` handles both modes. The `DEBUG` variable in `.env` determines the behavior.*

| | `DEBUG=true` (dev) | `DEBUG=false` (prod) |
|---|---|---|
| **Demarrage** | `sleep infinity` (serveur lance a la main) | `start.sh` (supervisord automatique) |
| **Serveur** | `runserver` Django | Gunicorn (3 workers) |
| **Celery** | Lance a la main si besoin | Supervisord (2 workers) |
| **Nginx** | Proxy vers `host.docker.internal:8123` | Proxy vers Gunicorn interne |
| **Config Nginx** | `NGINX_CONF=dev.conf` dans `.env` | `NGINX_CONF=default.conf` (defaut) |

### Developpement / Development

```bash
# .env
DEBUG=true
NGINX_CONF=dev.conf
POSTGRES_HOST=localhost    # si PostgreSQL est hors Docker

# Lancer les containers / Start containers
docker compose up -d

# Entrer dans le container / Enter the container
docker exec -it hypostasia_web bash

# Lancer le serveur Django / Start Django server
uv run python manage.py runserver 0.0.0.0:8123

# (Autre terminal) Lancer Celery / (Another terminal) Start Celery
uv run celery -A hypostasia worker --loglevel=info
```

Ou sans Docker (Python local — necessite PostgreSQL et Redis installes) :

*Or without Docker (local Python — requires PostgreSQL and Redis installed):*

```bash
# Configurer le .env / Configure .env
cp .env.example .env
# Editer : POSTGRES_HOST=localhost, DEBUG=true

# Installer tout (dependances, migrations, static, fixtures)
# / Install everything (dependencies, migrations, static, fixtures)
bash install.sh

# Lancer le serveur / Start server
uv run python manage.py runserver 0.0.0.0:8123

# (Autre terminal) Lancer Celery pour la transcription audio
# / (Another terminal) Start Celery for audio transcription
uv run celery -A hypostasia worker --loglevel=info
```

Acces : http://localhost:8123/ — Se connecter avec `jonas` / `demo1234`

### Production

```bash
# .env
DEBUG=false
DOMAIN=hypo.example.com
SECRET_KEY=cle_longue_aleatoire
POSTGRES_PASSWORD=mot_de_passe_fort

# Lancer / Start
docker compose up -d

# Les migrations et collectstatic sont lances automatiquement par start.sh
# Supervisord demarre gunicorn + celery worker
```

### Mise a jour en production / Production update

```bash
docker exec -it hypostasia_web bash
cd /app && git pull
uv sync
uv run python manage.py migrate
supervisorctl -c /app/supervisord.conf restart gunicorn celery_worker
```

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

L'IA (ou l'utilisateur) extrait les passages cles du texte et les classe par **hypostase** — un type d'argument parmi 30 categories (theorie, hypothese, paradoxe, donnee, principe...) regroupees en 8 familles.

*The AI (or the user) extracts key passages and classifies them by **hypostasis** — an argument type among 30 categories grouped into 8 families.*

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

## Demarrage depuis zero / Starting from scratch

Apres un `docker compose down -v` (qui supprime la base de donnees), tout est recree automatiquement au redemarrage.

*After a `docker compose down -v` (which deletes the database), everything is recreated automatically on restart.*

```bash
# Detruire et reconstruire / Destroy and rebuild
docker compose down -v
docker compose build
docker compose up -d

# En mode dev (DEBUG=true), lancer manuellement :
# / In dev mode (DEBUG=true), start manually:
docker exec -it hypostasia_web bash
bash install.sh                                      # migrations + fixtures
uv run python manage.py runserver 0.0.0.0:8123       # serveur
```

`install.sh` execute dans l'ordre :

1. `uv sync` — dependances Python
2. `migrate` — schema + migration de normalisation des attributs
3. `collectstatic` — fichiers CSS/JS
4. `charger_fixtures_demo` — donnees de demo completes

Resultat : 5 utilisateurs, 1 dossier "Demonstration" avec 4 documents analyses, 33 extractions avec hypostases, 49 commentaires, debat V1 + synthese V2 chainees — pret a l'emploi.

*Result: 5 users, 1 "Demonstration" folder with 4 analyzed documents, 33 extractions with hypostases, 49 comments, debate V1 + synthesis V2 chained — ready to use.*

### Fixtures disponibles / Available fixtures

| Fixture | Contenu | Commande |
|---------|---------|----------|
| `charger_fixtures_demo` | Tout (users, dossiers, pages, extractions, commentaires, V1+V2) | `uv run python manage.py charger_fixtures_demo` |
| `demo_ia.json` | Config IA seule (modeles, analyseurs, prompts) | `uv run python manage.py loaddata front/fixtures/demo_ia.json` |
| `exemple_deliberation.json` | 1 page + 7 extractions + 4 commentaires (demo minimale) | `uv run python manage.py loaddata front/fixtures/exemple_deliberation.json` |
| `demo_alignement_versions.json` | Debat V1 + Synthese V2 (30 entites, alignement entre versions) | `uv run python manage.py loaddata front/fixtures/demo_alignement_versions.json` |

Toutes les fixtures utilisent des cles d'attributs canoniques (`resume`, `hypostases`, `mots_cles`, `statut`).

*All fixtures use canonical attribute keys (`resume`, `hypostases`, `mots_cles`, `statut`).*

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
