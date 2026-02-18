# Plan : Recherche semantique par dossier via Zvec

## Contexte

Ajouter un moteur de recherche semantique embarque (Zvec) pour trouver des passages similaires **au sein d'un dossier**. Zvec fonctionne comme SQLite : pas de serveur, stockage fichier local, in-process.

## Prerequis

- Downgrade `requires-python` de `>=3.14` a `>=3.12` dans `pyproject.toml`
- Ajouter `zvec` et `sentence-transformers` aux dependances
- `uv sync` pour installer

## Architecture

```
front/services/recherche_vectorielle.py   ← service unique (3 fonctions)
db/zvec/                                  ← stockage des collections Zvec (1 par dossier)
```

### Principe : une collection Zvec par dossier

Chaque `Dossier` a sa propre collection Zvec. La recherche est **scopee au dossier** :
- On cherche dans le dossier courant (celui de la page ouverte)
- Les pages orphelines (sans dossier) ne sont pas indexees

### Ce qui est indexe

Chaque `ExtractedEntity` dont le job est `completed` :
- **Vecteur** : embedding de `extraction_text`
- **Metadata** : `entity_id`, `page_id`, `page_title`, `extraction_class`

### Modele d'embedding

`sentence-transformers/all-MiniLM-L6-v2` : gratuit, local, ~80 Mo, 384 dimensions.
Charge une seule fois au premier appel (lazy singleton dans le service).

## Fichiers impactes

| Fichier | Changement |
|---------|------------|
| `pyproject.toml` | `requires-python = ">=3.12"`, `zvec`, `sentence-transformers` |
| `front/services/recherche_vectorielle.py` | **Nouveau** — `indexer_entite()`, `rechercher()`, `supprimer_entite()` |
| `front/tasks.py` | `indexer_dossier_task` (reindexe tout un dossier) |
| `front/views.py` (ExtractionViewSet) | 2 actions : `recherche_semantique` (GET), `reindexer_dossier` (POST) |
| `front/serializers.py` | `RechercheSemantiqueSerializer` |
| `front/templates/front/includes/recherche_semantique.html` | **Nouveau** — Formulaire + resultats |
| `front/templates/front/includes/resultats_recherche.html` | **Nouveau** — Cartes de resultats avec score |
| `front/templates/front/base.html` | Barre de recherche dans la navbar |

## Etapes

### Etape 1 : Dependances

- `pyproject.toml` : `requires-python = ">=3.12"`, ajouter `zvec` et `sentence-transformers`
- `uv sync`

### Etape 2 : Service `recherche_vectorielle.py`

3 fonctions publiques + 2 helpers internes :

```python
# Helpers internes
_get_modele_embedding()     → charge le modele une seule fois (lazy singleton)
_get_ou_creer_collection()  → ouvre/cree la collection Zvec pour un dossier_id

# API publique
indexer_entite(entite)              → calcule l'embedding et l'insere dans la collection du dossier
supprimer_entite(entite)            → retire une entite de la collection
rechercher(dossier_id, texte, top_k=10) → retourne les entites les plus proches avec score
```

### Etape 3 : Tache Celery `indexer_dossier_task`

- Prend un `dossier_id`
- Recupere toutes les `ExtractedEntity` du dossier (via `job__page__dossier_id`)
- Reindexe tout dans la collection Zvec du dossier

### Etape 4 : Vues

#### `recherche_semantique` (GET)
- Params : `dossier_id`, `q` (texte libre)
- Si pas de `q` → renvoie le formulaire vide
- Si `q` → embedding du texte, query Zvec, renvoie les resultats en partial HTMX

#### `reindexer_dossier` (POST)
- Lance `indexer_dossier_task.delay(dossier_id)`
- Renvoie un toast de confirmation

### Etape 5 : Templates

#### `recherche_semantique.html`
- Champ de recherche avec `hx-get="/extractions/recherche_semantique/?dossier_id=X&q=..."`
- Zone `#resultats-recherche` pour les resultats

#### `resultats_recherche.html`
- Cartes avec : score de similarite (%), texte de l'extraction, titre de la page source
- Clic sur une carte → navigue vers la page et surligne l'extraction

### Etape 6 : Barre de recherche dans la navbar

Petit champ de recherche dans la navbar (entre le titre et le bouton Extractions).
Le `dossier_id` est lu dynamiquement depuis la page ouverte.

## Indexation automatique

Pas d'indexation automatique dans ce premier jet. L'indexation se fait :
- Manuellement via le bouton "Reindexer" dans l'arbre de dossiers
- Via la tache Celery `indexer_dossier_task`

L'indexation automatique (a chaque creation d'extraction) pourra etre ajoutee ensuite.

## Bascule vers ChromaDB

Si Zvec pose probleme, le service `recherche_vectorielle.py` est le seul fichier a recrire.
L'API publique (3 fonctions) reste identique. Le reste de l'app ne change pas.
