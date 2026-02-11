<div align="center">

# Hypostasia V3

**Plateforme d'analyse argumentative et d'extraction structuree, augmentee par IA.**

[![Python 3.14+](https://img.shields.io/badge/python-3.14+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Django 6.0](https://img.shields.io/badge/django-6.0-092E20?logo=django&logoColor=white)](https://djangoproject.com)
[![HTMX](https://img.shields.io/badge/htmx-1.27+-3366CC?logo=htmx&logoColor=white)](https://htmx.org)
[![LangExtract](https://img.shields.io/badge/langextract-0.1+-FF6F00)](https://github.com/google/langextract)
[![License](https://img.shields.io/badge/license-AGPLv3-blue)](LICENSE)

</div>

---

Hypostasia est un ecosysteme logiciel qui extrait, analyse et reinjecte visuellement la couche argumentative du web. Grace a une extension navigateur et un backend Django, il revele les structures logiques sous-jacentes ("Hypostases") de n'importe quelle page web.

## Fonctionnalites principales

- **Extraction IA multi-LLM** — Google Gemini, OpenAI GPT, Anthropic Claude, Mistral, Perplexity, Moonshot
- **Analyseurs configurables** — Prompts composables, exemples few-shot, attributs flexibles
- **Benchmark LLM** — Tester et comparer les modeles cote a cote sur les memes exemples
- **Validation humaine** — Workflow d'annotation : valider, rejeter, promouvoir les extractions
- **Interface 3 colonnes** — Arbre de dossiers, zone de lecture, panneau d'extraction
- **Zero SPA** — 100% server-rendered avec HTMX pour l'interactivite

## Architecture

```
Hypostasia-V3/
├── core/                       # Modeles de donnees (Page, Argument, AIModel, Prompt)
├── hypostasis_extractor/       # Integration LangExtract + Analyseurs + Tests LLM
├── front/                      # Interface lecture 3 colonnes (HTMX partials)
├── hypostasia/                 # Config Django (settings, urls, wsgi)
├── logs/                       # Fichiers de logs (extractor.log, core.log, django.log)
├── tools/                      # Scripts utilitaires (test_langextract.py)
├── Dockerfile                  # Build container
├── docker-compose.yml          # Deploiement Nginx + Gunicorn
└── CLAUDE.md                   # Specification stricte pour agents IA
```

### Apps Django

| App | Role |
|-----|------|
| `core` | Modeles fondamentaux : Page, Dossier, TextBlock, Argument, AIModel, Prompt, HypostasisTag |
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
mkdir -p db logs staticfiles

# Appliquer les migrations
uv run python manage.py migrate

# (Optionnel) Creer un superutilisateur
uv run python manage.py createsuperuser

# (Optionnel) Charger les prompts et exemples de base
uv run python seed_prompts.py

# Lancer le serveur
uv run python manage.py runserver
```

**Acces :**
- Interface : http://localhost:8000/
- Admin Django : http://localhost:8000/admin/

### Deploiement Docker

```bash
# Configurer les variables d'environnement
cp .env.example .env  # editer avec vos cles API

# Lancer les containers
docker-compose up -d

# Migrations + collecte des fichiers statiques
docker-compose exec web uv run python manage.py migrate
docker-compose exec web uv run python manage.py collectstatic --noinput
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
# Pages et arguments
POST   /api/pages/                          # Creer une page avec blocs
POST   /api/pages/{id}/analyze/             # Lancer l'analyse IA
GET    /api/pages/{id}/arguments/           # Recuperer les arguments extraits
PATCH  /api/arguments/{id}/                 # Modifier un argument (user_edited=true)

# Extraction LangExtract
GET    /api/extraction-jobs/                # Liste des jobs
POST   /api/extraction-jobs/                # Creer un job
POST   /api/extraction-jobs/{id}/run/       # Executer l'extraction
GET    /api/extraction-jobs/{id}/visualization/  # HTML interactif

# Analyseurs syntaxiques
GET    /api/analyseurs/                     # Liste
GET    /api/analyseurs/{id}/                # Editeur (HTML partial ou page complete)
POST   /api/analyseurs/{id}/run_test/       # Lancer un test LLM
GET    /api/analyseurs/{id}/test_results/   # Resultats de test
POST   /api/analyseurs/{id}/validate_test_extraction/  # Valider → promouvoir
POST   /api/analyseurs/{id}/reject_test_extraction/    # Rejeter une extraction

# Interface lecture (HTMX)
GET    /                                    # Bibliotheque 3 colonnes
GET    /lire/{id}/                          # Zone de lecture
```

## Documentation

| Document | Description |
|----------|-------------|
| [CLAUDE.md](./CLAUDE.md) | Specification ultra-stricte pour agents IA (schemas, endpoints, contraintes) |
| [GUIDELINES.md](./GUIDELINES.md) | Regles d'architecture et contrats de donnees |
| [LangExtractReadMe.md](./LangExtractReadMe.md) | Documentation de la librairie LangExtract |
| [hypostasis_extractor/README.md](./hypostasis_extractor/README.md) | Architecture de l'app d'extraction |

## Contribution

Toute modification doit respecter les **[Guidelines](./GUIDELINES.md)** et les patterns decrits ci-dessus. Les agents IA doivent verifier la conformite avec les contrats d'interface (schemas JSON, endpoints HTMX, ViewSets explicites).

---

<div align="center">
<sub>Hypostasia — decoder la couche argumentative du web</sub>
</div>
</content>
</invoke>