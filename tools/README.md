# Tools — Scripts utilitaires Hypostasia

## test_langextract.py

Script de test et benchmark du moteur **LangExtract** (librairie Google d'extraction d'entites structurees depuis du texte brut via LLM).

### Principe general

Le script execute le pipeline complet LangExtract :

1. **Configuration** — Choix du modele LLM, de la cle API, du texte source
2. **Construction du prompt** — Soit un prompt manuel, soit un prompt assemble depuis un `AnalyseurSyntaxique` Django (morceaux de prompt ordonnes)
3. **Exemples few-shot** — Demonstrations au LLM de ce qu'on attend. Peuvent venir d'un fichier JSON, des valeurs par defaut, ou d'un `AnalyseurSyntaxique` Django
4. **Extraction** — Appel au LLM via `lx.extract()`, retourne des entites avec positions exactes dans le texte (grounding)
5. **Verification du grounding** — Controle que le texte extrait correspond bien a sa position dans le texte source
6. **Sauvegarde** — Export JSONL (format standard LangExtract) et visualisation HTML interactive
7. **Affichage JSON** — Resultat final affiche en JSON indente et lisible dans le terminal

### Integration avec les modeles Django

Le script peut charger prompt et exemples depuis un **AnalyseurSyntaxique** stocke en base :

```
AnalyseurSyntaxique
  ├── PromptPiece (morceaux de prompt ordonnes, roles: definition/instruction/format/context)
  └── AnalyseurExample (exemples few-shot)
       └── ExampleExtraction (extractions attendues)
            └── ExtractionAttribute (attributs cle-valeur)
```

Les `PromptPiece` sont concatenees dans l'ordre pour former le prompt complet.
Les `AnalyseurExample` sont convertis en objets `lx.data.ExampleData` pour LangExtract.

### Mode benchmark

Le mode `--benchmark` utilise le texte d'un exemple few-shot de l'analyseur comme texte d'entree.
Cela permet de verifier que le LLM retrouve bien les memes entites que celles definies dans l'exemple.

- Si l'analyseur n'a qu'un seul exemple, il est utilise directement.
- Si plusieurs exemples existent, le script demande a l'utilisateur de choisir via `input()`.

### Utilisation

```bash
# Test avec le texte et prompt par defaut
uv run python tools/test_langextract.py

# Avec cle API depuis la base Django
uv run python tools/test_langextract.py --django

# Avec un texte personnalise
uv run python tools/test_langextract.py --django --text "Mon texte a analyser"

# Avec un fichier texte
uv run python tools/test_langextract.py --django --text-file article.txt

# Lister les analyseurs disponibles en base
uv run python tools/test_langextract.py --django --list-analyseurs

# Utiliser un analyseur Django (prompt + exemples depuis la base)
uv run python tools/test_langextract.py --django --analyseur 1

# Mode benchmark : tester l'analyseur sur son propre texte d'exemple
uv run python tools/test_langextract.py --django --analyseur 1 --benchmark

# Options supplementaires
uv run python tools/test_langextract.py --django --model gpt-4o    # Changer de modele LLM
uv run python tools/test_langextract.py --django --chunking         # Decouper les longs textes
uv run python tools/test_langextract.py --django --no-html --no-jsonl  # Pas de fichiers de sortie
uv run python tools/test_langextract.py --django --quiet            # Mode silencieux
```

### Options CLI

| Option | Description |
|--------|-------------|
| `--text "..."` | Texte a analyser (entre guillemets) |
| `--text-file chemin` | Fichier texte a analyser |
| `--url URL` | URL d'un document (LangExtract le telecharge) |
| `--model nom` | Modele LLM (defaut: `gemini-2.5-flash`) |
| `--api-key cle` | Cle API directe |
| `--django` | Recuperer la cle API depuis la base Django |
| `--prompt "..."` | Prompt d'extraction personnalise |
| `--analyseur ID` | ID d'un AnalyseurSyntaxique Django |
| `--list-analyseurs` | Lister les analyseurs disponibles et quitter |
| `--benchmark` | Utiliser le texte d'un exemple comme input (necessite `--analyseur`) |
| `--examples-file chemin` | Fichier JSON d'exemples few-shot |
| `--chunking` | Decouper les longs textes en morceaux |
| `--workers N` | Nombre de workers paralleles (avec `--chunking`) |
| `--no-jsonl` | Ne pas sauvegarder le fichier JSONL |
| `--no-html` | Ne pas generer la visualisation HTML |
| `--quiet` | Mode silencieux |

### Sortie

Le script produit :

- **Terminal** : details etape par etape + JSON lisible des entites extraites
- **`test_output/test_extraction.jsonl`** : resultats au format standard LangExtract
- **`test_output/test_visualization.html`** : page HTML interactive avec surlignage des entites

### Prompt alignment : comprendre les warnings

Avant d'appeler le LLM, LangExtract **valide vos exemples few-shot**. Il verifie que chaque `extraction_text` est bien une citation exacte (verbatim) du `example_text` source. Si ce n'est pas le cas, un warning apparait :

```
WARNING:absl:Prompt alignment: non-exact match: [example#0] class='Methode'
  status=AlignmentStatus.MATCH_LESSER text='Un triptyque etablit...' char_span=(59, 101)
```

#### Les statuts d'alignement

| Statut | Signification |
|--------|---------------|
| `MATCH_EXACT` | Le `extraction_text` est copie mot pour mot depuis le texte source. C'est le cas ideal. |
| `MATCH_LESSER` | Correspondance partielle. Le texte a ete trouve mais ne couvre qu'une portion du `extraction_text`. Souvent cause par une reformulation ou un texte qui deborde. |
| `MATCH_FUZZY` | Correspondance approximative (via `difflib.SequenceMatcher`). Le texte est similaire mais pas identique (fautes, ponctuation, espaces). |

#### Ce que signifie `char_span=(59, 101)`

C'est la position (debut, fin) en caracteres ou LangExtract a trouve la meilleure correspondance dans le texte source. Un span court par rapport a un `extraction_text` long indique que seule une petite partie a matche.

#### Comment corriger

La regle d'or : **chaque `extraction_text` doit etre un copier-coller exact d'un passage du `example_text`**.

```
FAUX — Reformulation ou resume :
  example_text:    "Un triptyque etablit des ponts entre trois facons de presenter..."
  extraction_text: "Methode tripartite de presentation"    ← invente, pas dans le texte

CORRECT — Citation exacte :
  example_text:    "Un triptyque etablit des ponts entre trois facons de presenter..."
  extraction_text: "Un triptyque etablit des ponts entre trois facons de presenter"
```

Dans Hypostasia, cela signifie que chaque `ExampleExtraction.extraction_text` (dans l'admin Django) doit etre un copier-coller exact d'un passage du `AnalyseurExample.example_text` parent.

Erreurs frequentes :
- **Reformulation** : ecrire un resume au lieu de citer le texte
- **Debordement** : le `extraction_text` contient du texte qui n'existe pas dans le `example_text`
- **Ponctuation/accents** : guillemets differents, apostrophes typographiques vs droites, espaces insecables
- **Troncature** : copier seulement une partie d'un mot ou d'une phrase

### Dependances

- `langextract` (librairie Google)
- Django + les modeles de `core` et `hypostasis_extractor` (pour `--django`, `--analyseur`, `--benchmark`)
