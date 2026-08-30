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

**Aucun de ces endpoints n'est ouvert.** Chaque methode porte sa propre garde, et
un refus **en LECTURE** rend **404** — jamais 403 : un objet auquel on n'a pas droit
doit repondre exactement comme un objet qui n'existe pas (doctrine du projet,
`AGENTS.md`).

> **La doctrine ne couvre pas les ECRITURES** : sur les trois methodes POST, un
> cookie de session **sans jeton CSRF** rend `403 « CSRF Failed »` avant meme la
> garde — `SessionAuthentication` impose le controle CSRF, et le `csrf_exempt` du
> ViewSet n'y change rien. Ce n'est pas un oracle (la reponse ne depend d'aucun
> identifiant), mais il faut le savoir avant de croire un 403.

Details et mesures : `CHANGELOG/2026-08-23-fermer-l-api-d-extraction.md`.

| Endpoint | Methode | Description | Qui y a droit |
|----------|---------|-------------|---------------|
| `/api/extraction-jobs/` | GET | Liste des jobs | les notes du perimetre du visiteur |
| `/api/extraction-jobs/` | POST | Creation d'un job | le droit d'ECRIRE sur la note visee |
| `/api/extraction-jobs/{id}/` | GET | Detail avec entites | l'acces a la note du job — le champ `examples` rend `[]` a qui n'est pas **staff** |
| `/api/extracted-entities/` | GET | Liste des entites (filtrable par job) | les notes du perimetre |
| `/api/extracted-entities/{id}/` | GET | Detail d'une entite | l'acces a la note du job |
| `/api/extracted-entities/{id}/validate/` | POST | Valider une entite | le droit d'ECRIRE sur la note |
| `/api/extraction-examples/` | GET/POST | Gerer les exemples few-shot | le **staff** seul |
| `/api/extraction-examples/{id}/` | GET | Detail d'un exemple | le **staff** seul |

> Les actions `/{id}/run/` et `/{id}/visualization/` ont ete **RETIREES le 17 aout
> 2026** avec l'ancien moteur d'ancrage. L'analyse passe par
> `analyser_une_page_avec_le_moteur_element` (`tasks_element.py`), seul chemin qui
> ancre. Ce tableau les annoncait encore : elles n'existent plus.

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
    # `ai_model` est optionnel. ATTENTION : `Page` n'a PAS de champ
    # `ai_model` — le modele se resout par role
    # (`core/services/modeles_par_role.modele_du_role`), jamais depuis
    # la note. Cette ligne annoncait `page.ai_model` : elle levait.
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

`run_langextract_job` a ete **supprimee le 17 aout 2026** avec l'ancien moteur
d'ancrage : elle lisait `Page.text_readability`, vide sur toute note ingeree par
Docling, et produisait des extractions **sans aucune `AncrageExtraction`** — donc
sans preuve. Le seul chemin qui ancre est la tache Celery :

```python
from hypostasis_extractor.tasks_element import (
    analyser_une_page_avec_le_moteur_element,
)

analyser_une_page_avec_le_moteur_element.delay(job.pk)
```

### 4. Via API

**Il faut une session : un appel sans cookie rend 404**, et `example_ids` n'est
accepte que d'un membre du staff.

**Un POST exige AUSSI le jeton CSRF** — le cookie `csrftoken` ET l'en-tete
`X-CSRFToken`. Sans lui, la reponse est `403 « CSRF Failed »`, avant toute garde :
`SessionAuthentication` impose le controle, et le `csrf_exempt` du ViewSet ne le
desactive pas.

```bash
# Creer un job — session + CSRF, sur une note ou l'on peut ECRIRE
curl -X POST https://beta.hypostasia.org/api/extraction-jobs/ \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: <votre csrftoken>" \
  -b "sessionid=<votre sessionid>; csrftoken=<votre csrftoken>" \
  -d '{
    "page": 1,
    "name": "Test extraction",
    "prompt_description": "Extraire les entites"
  }'
```

Le lancement de l'extraction ne passe plus par cette API : `/{id}/run/` a ete retiree
le 17 aout 2026, et l'analyse se declenche depuis l'ecran de la note.

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
