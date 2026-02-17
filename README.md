<div align="center">

# Hypostasia V3

**Plateforme pedagogique d'analyse argumentative, de debat structure et d'amendement de textes — augmentee par IA en toute transparence.**

[![Python 3.14+](https://img.shields.io/badge/python-3.14+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Django 6.0](https://img.shields.io/badge/django-6.0-092E20?logo=django&logoColor=white)](https://djangoproject.com)
[![HTMX](https://img.shields.io/badge/htmx-1.27+-3366CC?logo=htmx&logoColor=white)](https://htmx.org)
[![LangExtract](https://img.shields.io/badge/langextract-0.1+-FF6F00)](https://github.com/google/langextract)
[![License](https://img.shields.io/badge/license-AGPLv3-blue)](LICENSE)

</div>

---

## En bref

Hypostasia est un outil pedagogique concu pour **lire, annoter, debattre et amender des textes de maniere collaborative**. Il s'adresse aussi bien a des groupes de travail, des classes ou des ateliers d'ecriture qu'a des equipes de recherche.

**Tout peut se faire sans IA.** L'extraction de passages, les commentaires, les debats et la redaction de restitutions fonctionnent entierement a la main. L'IA est une option a chaque etape — jamais une obligation.

Quand l'IA est sollicitee, **tout est transparent** : le prompt complet est visible, le nombre de tokens et le cout sont estimes avant chaque appel, et le modele utilise est affiche. L'utilisateur voit exactement ce qui est envoye au LLM, ce qu'il recoit, et peut toujours modifier le resultat avant de le valider. C'est aussi, en soi, **un outil pedagogique sur l'utilisation de l'IA** : comprendre ce qu'on lui envoie, ce qu'elle produit, et ce qu'on en fait.

Le cycle de travail typique est :

1. **Importer** un texte (page web, PDF, DOCX, audio transcrit)
2. **Extraire** des passages cles — manuellement ou via un analyseur IA configurable
3. **Debattre** chaque extraction dans un fil de discussion (commentaires, reformulation)
4. **Restituer** le debat en une synthese — redigee a la main ou assistee par IA
5. **Amender** le texte original : chaque restitution cree une nouvelle version tracee

Chaque etape produit des artefacts visibles et tracables. Les versions successives d'un texte sont liees entre elles, et les pastilles colorees dans le texte permettent de remonter a la source de chaque annotation ou restitution.

## Fonctionnalites principales

- **Extraction IA multi-LLM** — Google Gemini, OpenAI GPT, Anthropic Claude, Mistral, Perplexity, Moonshot
- **Analyseurs configurables** — Prompts composables, exemples few-shot, attributs flexibles
- **Benchmark LLM** — Tester et comparer les modeles cote a cote sur les memes exemples
- **Validation humaine** — Workflow d'annotation : valider, rejeter, promouvoir les extractions
- **Commentaires et debat** — Fil de discussion par extraction (layout SMS), reformulation IA
- **Restitution du debat** — Clot un debat et genere une nouvelle version du texte avec tracabilite (pastille violette)
- **Restitution IA** — Generation automatique du texte de restitution via un analyseur de type "restituer" (prompt, tokens et cout visibles avant lancement)
- **Questions / Reponses** — Systeme de Q&A par page, sans authentification (identification par prenom)
- **Import multi-format** — PDF, DOCX, PPTX, XLSX, Markdown, fichiers texte
- **Transcription audio** — Import audio avec diarisation (identification des locuteurs) via Celery
- **Configuration IA dynamique** — Toggle on/off, selection du modele, estimation des couts par appel
- **Interface 3 colonnes** — Arbre de dossiers, zone de lecture, panneau d'extraction
- **Zero SPA** — 100% server-rendered avec HTMX pour l'interactivite

## Architecture

```
Hypostasia-V3/
├── core/                       # Modeles de donnees (Page, Argument, AIModel, Prompt)
├── hypostasis_extractor/       # Integration LangExtract + Analyseurs + Tests LLM
├── front/                      # Interface lecture 3 colonnes (HTMX partials)
│   ├── services/               # Services metier (conversion fichiers, transcription audio)
│   └── tasks.py                # Taches Celery (transcription, reformulation, restitution IA)
├── hypostasia/                 # Config Django (settings, urls, wsgi, celery)
├── logs/                       # Fichiers de logs (extractor.log, core.log, django.log)
├── tools/                      # Scripts utilitaires (test_langextract.py)
├── Dockerfile                  # Build container (ffmpeg inclus)
├── docker-compose.yml          # Deploiement Nginx + Gunicorn + Celery
├── supervisord.conf            # Gestion des services (gunicorn + celery worker)
├── start.sh                    # Script de demarrage (migrations + supervisord)
└── CLAUDE.md                   # Specification stricte pour agents IA
```

### Apps Django

| App | Role |
|-----|------|
| `core` | Modeles fondamentaux + API JSON pour l'extension navigateur (Page, Dossier, AIModel, etc.) |
| `hypostasis_extractor` | Pipeline LangExtract : ExtractionJob, AnalyseurSyntaxique, TestRun, validation humaine |
| `front` | Interface de lecture 3 colonnes, navigation HTMX, gestion dossiers/pages |

### Patterns obligatoires

| Regle | Obligatoire | Interdit |
|-------|-------------|----------|
| Views | `viewsets.ViewSet` explicite | `ModelViewSet`, `View` Django |
| URLs | `DefaultRouter` DRF | `path()` manuel pour DRF |
| Validation | DRF `Serializer` | Django Forms |
| Interactivite | HTMX | SPA, React, Vue |
| Commentaires | Bilingues FR/EN | Monolingues |

## Demarrage rapide

### Prerequis

- Python 3.14+
- [uv](https://github.com/astral-sh/uv) (gestionnaire de paquets)

### Installation

```bash
git clone https://github.com/CoopCodeCommun/Hypostasia.git
cd Hypostasia/Hypostasia-V3

# Installer les dependances
uv sync

# Creer les repertoires necessaires
mkdir -p db logs staticfiles tmp/audio

# Appliquer les migrations
uv run python manage.py migrate

# (Optionnel) Creer un superutilisateur
uv run python manage.py createsuperuser

# (Optionnel) Charger les prompts et exemples de base
uv run python seed_prompts.py

# Lancer le serveur Django
uv run python manage.py runserver

# Lancer le worker Celery (dans un second terminal)
uv run celery -A hypostasia worker --loglevel=info
```

**Acces :**
- Interface : http://localhost:8000/
- Admin Django : http://localhost:8000/admin/

### Mise a jour en production (sans rebuild)

Pour appliquer un changement rapidement sans reconstruire l'image Docker :

```bash
# Entrer dans le conteneur
docker exec -it hypostasia_web bash

# Recuperer les modifications
cd /app && git pull

# (Si pyproject.toml a change) reinstaller les dependances
uv sync

# (Si migrations ajoutees) appliquer les migrations
uv run python manage.py migrate

# Relancer les services via supervisord
supervisorctl -c /app/supervisord.conf restart gunicorn celery_worker
```

### Deploiement Docker

Le conteneur utilise **supervisord** pour gerer gunicorn et le worker Celery dans un seul service.

```bash
# Configurer les variables d'environnement
cp .env.example .env  # editer avec vos cles API

# Lancer les containers
docker-compose up -d

# Les migrations et collectstatic sont lances automatiquement par start.sh
# supervisord demarre gunicorn + celery worker
```

## Configuration des modeles LLM

Les modeles IA se configurent dans l'admin Django (`/admin/core/aimodel/`). Chaque modele necessite :
- Un **model_choice** (ex: `gemini-2.5-flash`, `gpt-5.2`, `claude-opus-4-6`)
- Une **api_key** valide pour le provider correspondant

Le provider est detecte automatiquement a partir du model_choice.

### Providers supportes

| Provider | Modeles |
|----------|---------|
| Google | Gemini 2.5 Pro/Flash, 2.0 Flash, 1.5 Pro/Flash |
| OpenAI | GPT-5.2, 5 Mini/Nano, 4.1, 4o, 4 Turbo |
| Anthropic | Claude Opus 4.6, Sonnet 4.5, Haiku 4.5 |
| Mistral | Large, Medium, Small, Mixtral |
| Perplexity | Sonar (Large, Small, Huge) |
| Moonshot | Kimi K2.5, K1.5, K2 |

## Transcription audio

Hypostasia supporte l'import de fichiers audio avec transcription automatique et diarisation (identification des locuteurs). La transcription est asynchrone via **Celery**.

### Prerequis

- **ffmpeg** installe sur le systeme (pour le traitement audio, inclus dans le Dockerfile)
- **Celery worker** en cours d'execution (traitement asynchrone)
- Une **TranscriptionConfig** active dans l'admin Django

### Formats audio supportes

MP3, WAV, M4A, OGG, FLAC, WEBM, AAC, WMA, OPUS, AIFF

### Configuration

1. Creer une `TranscriptionConfig` dans `/admin/core/transcriptionconfig/`
2. Choisir le provider (`voxtral` pour Mistral API, `mock` pour simulation)
3. Pour Voxtral : renseigner la cle API Mistral et le modele (`mistral-small-latest`)
4. Activer la config (`is_active = True`)

### Celery : traitement asynchrone

La transcription audio utilise Celery avec un broker SQLite (via SQLAlchemy). Pas de Redis requis.

```bash
# Developpement local : lancer le worker dans un second terminal
uv run celery -A hypostasia worker --loglevel=info

# Docker : supervisord gere automatiquement gunicorn + celery worker
# Voir supervisord.conf pour la configuration des services
docker-compose up -d
```

**Architecture Celery :**
- **Broker** : `sqla+sqlite:///db/celery-broker.sqlite3` (pas de Redis)
- **Backend de resultats** : `django-db` (via django-celery-results)
- **Taches** : `transcrire_audio_task` (transcription), `reformuler_entite_task` (reformulation IA), `restituer_debat_task` (restitution IA), `analyser_page_task` (extraction LangExtract)
- **Timeout** : 30 minutes par tache

### Supervisord (Docker)

En production (Docker), `supervisord` gere les deux services dans un seul conteneur :

| Service | Commande | Logs |
|---------|----------|------|
| `gunicorn` | `uv run gunicorn hypostasia.wsgi:application --bind 0.0.0.0:8000 -w 3` | `logs/gunicorn.log` |
| `celery_worker` | `uv run celery -A hypostasia worker --loglevel=info --concurrency=2` | `logs/celery_worker.log` |

Le fichier `supervisord.conf` a la racine configure ces services.

### Utilisation

1. Cliquer sur "Importer un fichier ou audio" dans la sidebar gauche
2. Selectionner un fichier audio
3. L'interface affiche un indicateur de progression avec polling automatique (toutes les 3s)
4. Une fois la transcription terminee, les blocs locuteurs s'affichent avec des couleurs distinctes et des timestamps (MM:SS)

## Commentaires, debat et restitution

Chaque extraction peut etre commentee via un fil de discussion (layout SMS). Le debat suit un cycle de vie complet :

### Fil de discussion

1. Cliquer sur une extraction dans le panneau droit (ou sur sa pastille dans le texte)
2. Le panneau s'elargit en mode debat (70vw)
3. Saisir un prenom et un commentaire — le prenom est memorise en localStorage
4. Les commentaires s'affichent en layout SMS (propres a droite, autres a gauche)

### Reformulation IA

Depuis le fil de discussion, cliquer sur "Reformuler" pour lancer une reformulation IA du texte de l'extraction. Le resultat s'affiche dans un encart vert sous la carte d'extraction.

### Restitution du debat

La restitution cree une nouvelle version du texte original a partir du resume d'un debat. Le texte de restitution peut etre redige manuellement ou genere par IA.

1. Depuis le fil de discussion, cliquer sur **"Restituer le debat"** (`#btn-restituer-{id}`)
2. Dans le modal, deux options :
   - **Redaction manuelle** : saisir directement le texte dans le textarea
   - **Bouton "IA"** (violet) : choisir un analyseur de type `restituer`, visualiser le prompt complet avec estimation tokens/cout, puis lancer la generation. Le texte genere pre-remplit le textarea et reste modifiable avant validation.
3. A la validation :
   - Si une version de restitution existe deja, le texte est ajoute a la fin
   - Sinon, une nouvelle version vierge est creee avec uniquement la restitution
   - Les commentaires de l'extraction sont clos (formulaire masque)
   - L'extraction affiche le bloc "Debat restitue" avec un lien vers la version
4. Sur la nouvelle version, chaque bloc de restitution porte une **pastille violette** (`span.restitution-ancre`)
5. Cliquer sur la pastille violette ramene a la page source et ouvre le debat d'origine

### Versionnage des pages

Les versions sont gerees par une FK self-referentielle `parent_page` sur le modele `Page`. Quand plusieurs versions existent, un switcher de pills apparait en en-tete de la zone de lecture (`#switcher-versions`).

| Pastille | Couleur | Signification |
|----------|---------|---------------|
| `span.extraction-ancre` | Bleue | Extraction |
| `span.extraction-ancre.ancre-commentee` | Orange | Extraction avec commentaires |
| `span.restitution-ancre` | Violette | Texte de restitution d'un debat |

## Logs

Le systeme de logging ecrit en parallele dans la **console** et dans des **fichiers rotatifs** (`logs/`).

| Fichier | Contenu | Niveau |
|---------|---------|--------|
| `logs/extractor.log` | Vues et services de `hypostasis_extractor` | DEBUG |
| `logs/core.log` | App `core` et `front` | DEBUG |
| `logs/django.log` | Requetes Django internes | INFO |

**Format fichier** : `[YYYY-MM-DD HH:MM:SS] LEVEL name module.func:line — message`

```bash
# Suivre les logs d'extraction en temps reel
tail -f logs/extractor.log

# Filtrer les erreurs
grep ERROR logs/extractor.log

# Logs Django (requetes HTTP)
tail -f logs/django.log
```

Les fichiers sont limites a **5 MB** avec 3 backups rotatifs.

## API

### Endpoints principaux

```
# API extension navigateur (core)
GET    /api/pages/?url=...                  # Verifier si une page existe
POST   /api/pages/                          # Creer une page avec blocs
GET    /api/test-sidebar/?url=...           # Sidebar extension

# Analyseurs syntaxiques (hypostasis_extractor)
GET    /api/analyseurs/                     # Liste
GET    /api/analyseurs/{id}/                # Editeur (HTML partial ou page complete)
POST   /api/analyseurs/{id}/run_test/       # Lancer un test LLM
GET    /api/analyseurs/{id}/test_results/   # Resultats de test

# Interface lecture (front — HTMX)
GET    /                                    # Bibliotheque 3 colonnes
GET    /lire/{id}/                          # Zone de lecture
GET    /lire/{id}/previsualiser_analyse/    # Confirmation avant extraction IA
POST   /lire/{id}/analyser/                 # Lancer une extraction IA
POST   /import/fichier/                     # Import fichier (document ou audio)
GET    /import/status/?page_id=...          # Polling transcription audio

# Extractions et debat (front — HTMX)
POST   /extractions/manuelle/               # Extraction manuelle de texte
POST   /extractions/creer_manuelle/         # Creer l'extraction manuelle
POST   /extractions/panneau/                # Re-rend le panneau d'analyse
GET    /extractions/fil_discussion/         # Fil de discussion d'une extraction
POST   /extractions/ajouter_commentaire/    # Ajouter un commentaire
GET    /extractions/vue_commentaires/       # Vue globale des commentaires
GET    /extractions/choisir_reformulateur/  # Choisir un analyseur de reformulation
POST   /extractions/previsualiser_reformulation/ # Confirmation tokens/cout reformulation
POST   /extractions/reformuler/             # Lancer une reformulation IA
GET    /extractions/choisir_restituteur/    # Choisir un analyseur de restitution IA
POST   /extractions/previsualiser_restitution/ # Confirmation tokens/cout restitution IA
POST   /extractions/generer_restitution/    # Lancer une restitution IA (Celery)
GET    /extractions/restitution_ia_status/  # Polling restitution IA en cours
POST   /extractions/creer_restitution/      # Creer une restitution (nouvelle version)
POST   /extractions/supprimer_entite/       # Supprimer une extraction
POST   /extractions/promouvoir_entrainement/ # Promouvoir en donnees d'entrainement

# Configuration IA (front — HTMX)
GET    /config-ia/status/                   # Bouton toggle IA
POST   /config-ia/toggle/                   # Activer/desactiver l'IA
POST   /config-ia/select-model/             # Selectionner un modele

# Questions / Reponses (front — HTMX)
POST   /questions/poser_question/           # Poser une question sur une page
POST   /questions/repondre/                 # Repondre a une question
```

## Documentation

| Document | Description |
|----------|-------------|
| [CLAUDE.md](./CLAUDE.md) | Specification ultra-stricte pour agents IA (schemas, endpoints, contraintes) |
| [hypostasis_extractor/README.md](./hypostasis_extractor/README.md) | Architecture de l'app d'extraction |

## Contribution

Toute modification doit respecter les patterns decrits dans **[CLAUDE.md](./CLAUDE.md)** et ci-dessus. Les agents IA doivent verifier la conformite avec les contrats d'interface (schemas JSON, endpoints HTMX, ViewSets explicites).

---

<div align="center">
<sub>Hypostasia — lire, annoter, debattre et amender des textes, avec ou sans IA</sub>
</div>