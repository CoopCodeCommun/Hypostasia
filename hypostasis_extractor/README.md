# Hypostasis Extractor

Application Django utilisant **LangExtract** (Google) pour l'extraction d'entites structurees a partir du `html_readability` des Pages Hypostasia.

## Architecture

Cette application travaille en parallele avec le pipeline existant:

```
Page (core.models)
├── html_readability ──┬──► Pipeline Hypostasia (core) → TextBlock + Argument
                       │
                       └──► Hypostasis Extractor (langextract) → ExtractionJob → ExtractedEntity
```

## Modeles

### ExtractionJob
Represente une tache d'extraction sur une Page:
- `page` (FK): Page source (utilise `html_readability`)
- `ai_model` (FK): Configuration LLM (reutilise `core.models.AIModel`)
- `prompt_description`: Consigne d'extraction (ex: "Extraire les metaphores")
- `status`: pending | processing | completed | error
- `raw_result`: Resultat JSON brut de LangExtract

### ExtractedEntity
Entite extraite avec source grounding:
- `extraction_class`: Categorie (ex: "metaphore", "probleme", "donnee")
- `extraction_text`: Texte exact extrait
- `start_char` / `end_char`: Position dans le texte source
- `attributes`: JSON flexible (ex: {"emotion": "crainte"})
- `hypostasis_tag` (FK): Mapping optionnel vers `HypostasisTag`

### ExtractionExample
Exemples few-shot reutilisables pour guider LangExtract.

## API REST

| Endpoint | Methode | Description |
|----------|---------|-------------|
| `/api/extraction-jobs/` | GET/POST | Liste / Creation de jobs |
| `/api/extraction-jobs/{id}/` | GET | Detail avec entites |
| `/api/extraction-jobs/{id}/run/` | POST | Lancer l'extraction |
| `/api/extraction-jobs/{id}/visualization/` | GET | HTML de visualisation |
| `/api/extracted-entities/` | GET | Liste des entites (filtrable par job) |
| `/api/extracted-entities/{id}/validate/` | POST | Valider une entite |
| `/api/extraction-examples/` | GET/POST | Gerer les exemples few-shot |

## Utilisation

### 1. Creer un job

```python
from hypostasis_extractor.models import ExtractionJob
from core.models import Page

page = Page.objects.get(url="https://example.com/article")

job = ExtractionJob.objects.create(
    page=page,
    name="Extraction de metaphores",
    prompt_description="Extraire les metaphores conceptuelles et leur source/cible",
    ai_model=page.ai_model  # Optionnel
)
```

### 2. Associer des exemples few-shot

```python
from hypostasis_extractor.models import ExtractionExample, JobExampleMapping

example = ExtractionExample.objects.create(
    name="Metaphores spatiales",
    example_text="Nous sommes a un tournant de l'histoire.",
    example_extractions=[{
        "extraction_class": "metaphore",
        "extraction_text": "un tournant de l'histoire",
        "attributes": {"source": "espace", "cible": "temporalite"}
    }]
)

JobExampleMapping.objects.create(job=job, example=example, order=0)
```

### 3. Lancer l'extraction

```python
from hypostasis_extractor.services import run_langextract_job

# Extraction simple
entities_count, time = run_langextract_job(job)

# Avec chunking pour longs documents
entities_count, time = run_langextract_job(
    job, 
    use_chunking=True, 
    max_workers=5
)
```

### 4. Via API

```bash
# Creer un job
curl -X POST http://localhost:8000/api/extraction-jobs/ \
  -H "Content-Type: application/json" \
  -d '{
    "page": 1,
    "name": "Test extraction",
    "prompt_description": "Extraire les entites",
    "example_ids": [1, 2]
  }'

# Lancer l'extraction
curl -X POST http://localhost:8000/api/extraction-jobs/1/run/ \
  -H "Content-Type: application/json" \
  -d '{"use_chunking": false}'
```

## Integration avec Hypostasia

### Mapping vers HypostasisTag

Les entites extraites sont automatiquement mappees vers des `HypostasisTag` si le `extraction_class` correspond:

```python
# Si extraction_class = "probleme" et HypostasisTag(name="probleme") existe
# => entity.hypostasis_tag est automatiquement set
```

### Visualisation

LangExtract genere un HTML interactif avec surlignage:

```python
from hypostasis_extractor.services import generate_visualization_html

html = generate_visualization_html(job)
# Sauvegarder ou retourner dans la reponse HTTP
```

## Differences avec le pipeline core

| Aspect | Pipeline core | Hypostasis Extractor |
|--------|--------------|---------------------|
| Taxonomie | Hypostases + Modes + Themes | Classes arbitraires (configurable) |
| Output | TextBlock + Argument | ExtractedEntity (plus flexible) |
| Few-shot | TextInputs (contexte) | ExtractionExample (structure) |
| Grounding | Selecteurs CSS + offsets | Char offsets (LangExtract natif) |
| Chunking | Non implemente | Natif (passes multiples) |
| Visualisation | Sidebar navigateur | HTML interactif autonome |

## Dependencies

- `langextract>=0.1.0` (Google)
- Reutilise les modeles `core.models.Page`, `AIModel`, `HypostasisTag`

## Seed Data

```bash
# Cree les exemples few-shot de base
uv run python seed_prompts.py
```
