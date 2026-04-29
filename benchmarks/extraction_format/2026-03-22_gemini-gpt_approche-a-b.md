# Rapport de test — Format d'extraction LangExtract / Hypostasia

**Date** : 2026-03-22
**Texte source** : "La Ronde des Intelligences" (page 15, 19726 chars, ~13 chunks)
**Auteurs du texte** : Dominique Luzeaux, Jean Sallantin, Véronique Pinet, Jonas Turbeaux

---

## 1. Contexte et problématique

### 1.1 Hypostasia et la géométrie des débats

Hypostasia est un outil de gestion de débat et de connaissance. Il analyse des textes pour en
extraire l'ossature argumentative en s'appuyant sur la **géométrie des débats** — une théorie
qui définit 30 **hypostases** (manières d'être discutable). Chaque argument extrait d'un texte
est classé selon une ou plusieurs de ces hypostases (théorie, problème, hypothèse, axiome,
phénomène, etc.).

L'extraction est réalisée par un LLM (Gemini, GPT, etc.) piloté par la librairie open-source
**LangExtract** (Google). Le LLM reçoit un texte découpé en chunks, et pour chaque chunk
il renvoie un JSON structuré contenant les extractions.

### 1.2 Comment fonctionne LangExtract

LangExtract utilise un format JSON interne pour communiquer avec le LLM. Le développeur
définit ses extractions en Python :

```python
Extraction(extraction_class="character", extraction_text="ROMEO", attributes={"emotion": "wonder"})
```

LangExtract sérialise automatiquement cet objet dans le prompt envoyé au LLM :

```json
{"character": "ROMEO", "character_attributes": {"emotion": "wonder"}}
```

La clé JSON (`"character"`) correspond à `extraction_class`. La valeur (`"ROMEO"`) correspond
à `extraction_text`. Le suffixe `_attributes` est ajouté automatiquement.

Le LLM doit répondre dans ce même format. Le resolver de LangExtract parse la réponse
et reconstruit les objets `Extraction`.

### 1.3 La question : quel `extraction_class` utiliser ?

Pour Hypostasia, l'`extraction_class` peut être défini de deux manières :

**Approche A — Classe générique unique** : `extraction_class = "hypostase"` pour toutes
les extractions. L'hypostase spécifique (théorie, problème...) est rangée dans les attributs.
C'est le pattern classique de LangExtract (comme `"character"` pour tous les personnages).

Le LLM voit dans les exemples :
```json
{"hypostase": "citation du texte...", "hypostase_attributes": {"hypostases": "théorie, conjecture", ...}}
```
Toujours la même clé `"hypostase"` → format simple et prévisible.

**Approche B — Classe spécifique variable** : `extraction_class` = le nom de l'hypostase
principale (`"théorie"`, `"problème"`, `"hypothèse"`...). Chaque extraction a une clé JSON
différente. Les attributs contiennent les hypostases secondaires.

Le LLM voit dans les exemples :
```json
{"théorie": "citation du texte...", "théorie_attributes": {"hypostases": "théorie, conjecture", ...}}
{"problème": "autre citation...", "problème_attributes": {"hypostases": "problème, définition", ...}}
```
30 clés possibles → format plus riche mais plus complexe pour le LLM.

### 1.4 Enjeux

- **Stabilité** : le LLM produit-il du JSON valide dans les deux approches ? Boucle-t-il ?
- **Volume** : combien d'extractions pertinentes le LLM trouve-t-il ?
- **Richesse de classification** : le LLM utilise-t-il la diversité des 30 hypostases ?
- **Dépendance au modèle** : le résultat change-t-il entre Gemini et GPT ?
- **Impact sur le produit** : l'approche choisie détermine comment l'interface affiche les
  badges, filtres, et cartes d'extraction.

---

## 2. Objectif du test

Comparer les deux approches (A et B) avec deux modèles LLM (Gemini 2.5 Flash et GPT-4o Mini)
sur un même texte long (19726 chars, ~13 chunks) pour mesurer stabilité, volume et richesse.

---

## 3. Méthodologie

### 3.1 Configuration

| Paramètre | Valeur |
|---|---|
| `max_char_buffer` | 1500 chars (taille max d'un chunk) |
| `batch_length` | 1 (séquentiel, un chunk à la fois) |
| `max_output_tokens` | 8192 |
| Format de sortie | JSON avec fences |
| Wrapper | `{"extractions": [...]}` |
| Attribute suffix | `_attributes` |

### 3.2 Prompt commun (identique pour les 4 tests)

```
Tu es Hypostasia, un expert mondial en analyse syntaxique et en logique argumentative.
Ta mission est de déconstruire le texte fourni pour en extraire l'ossature argumentative
via les hypostases (définitions plus bas).
Tu agis avec une neutralité absolue et une précision chirurgicale.

# Définitions des 30 hypostases

- classification, aporie, approximation, paradoxe, formalisme
- événement, variation, dimension, mode, croyance
- invariant, valeur, structure, axiome, conjecture
- paradigme, objet, principe, domaine, loi
- phénomène, variable, variance, indice, donnée
- méthode, définition, hypothèse, problème, théorie

ANALYSE MAINTENANT LE TEXTE SUIVANT.
Instructions :
1. Identifie 5 à 15 arguments pertinents.
2. Pour chaque argument, extrais la citation EXACTE. Ne pas reformuler.
3. Synthétise l'idée en une phrase (résumé).
4. Associe 1 à 3 hypostases parmi les 30 définies.
5. Ignore le bruit, menus, pubs, copyright.
```

### 3.3 Pièce 5 — Approche A (classe unique)

```
RÈGLES DE FORMAT STRICTES — chaque extraction DOIT suivre ce schéma :

{
  "hypostase": "citation exacte du texte source",
  "hypostase_attributes": {
    "resume": "synthèse en une phrase",
    "hypostases": "hypothèse, théorie",
    "mots_cles": "mot1, mot2"
  }
}

- La clé est TOUJOURS "hypostase"
- "hypostases" dans les attributs : 1 à 3 parmi les 30. Ne JAMAIS lister les 30.
- Ne JAMAIS répéter la même extraction ni boucler.
```

### 3.4 Pièce 5 — Approche B (classe spécifique)

```
RÈGLES DE FORMAT STRICTES — chaque extraction DOIT suivre ce schéma :

{
  "théorie": "citation exacte du texte source",
  "théorie_attributes": {
    "resume": "synthèse en une phrase",
    "hypostases": "théorie, conjecture",
    "mots_cles": "mot1, mot2"
  }
}

- La clé est le NOM de l'hypostase principale (théorie, problème, hypothèse...)
- Chaque extraction peut avoir une clé différente selon l'hypostase identifiée.
- "hypostases" dans les attributs : 1 à 3 parmi les 30. Ne JAMAIS lister les 30.
- Ne JAMAIS répéter la même extraction ni boucler.
```

### 3.5 Few-shot examples

**Texte source de l'exemple** :
> L'intelligence artificielle est la révolution la plus importante depuis l'invention de l'écriture. On nous présente l'IA comme une fatalité historique, alors qu'il s'agit d'un choix politique.

**Approche A** (classe unique) :
```python
Extraction(extraction_class="hypostase", extraction_text="L'intelligence artificielle est la révolution...",
           attributes={"resume": "L'IA comparée à l'écriture.", "hypostases": "théorie, conjecture", "mots_cles": "IA, révolution"})
Extraction(extraction_class="hypostase", extraction_text="On nous présente l'IA comme une fatalité...",
           attributes={"resume": "L'IA est un choix politique.", "hypostases": "problème, définition", "mots_cles": "choix, politique"})
```

Ce que le LLM voit dans le prompt :
```json
{"extractions": [
  {"hypostase": "L'intelligence artificielle est la révolution...", "hypostase_attributes": {"resume": "...", "hypostases": "théorie, conjecture"}},
  {"hypostase": "On nous présente l'IA comme une fatalité...", "hypostase_attributes": {"resume": "...", "hypostases": "problème, définition"}}
]}
```

**Approche B** (classe spécifique) :
```python
Extraction(extraction_class="théorie", extraction_text="L'intelligence artificielle est la révolution...",
           attributes={"resume": "L'IA comparée à l'écriture.", "hypostases": "théorie, conjecture", "mots_cles": "IA, révolution"})
Extraction(extraction_class="problème", extraction_text="On nous présente l'IA comme une fatalité...",
           attributes={"resume": "L'IA est un choix politique.", "hypostases": "problème, définition", "mots_cles": "choix, politique"})
```

Ce que le LLM voit dans le prompt :
```json
{"extractions": [
  {"théorie": "L'intelligence artificielle est la révolution...", "théorie_attributes": {"resume": "...", "hypostases": "théorie, conjecture"}},
  {"problème": "On nous présente l'IA comme une fatalité...", "problème_attributes": {"resume": "...", "hypostases": "problème, définition"}}
]}
```

### 3.6 Code du script de test

Fichier : `tmp/test_format_extraction.py`

Le script utilise l'annotateur **natif** de LangExtract (pas notre override `AnnotateurAvecProgression`) pour tester le comportement pur de la librairie. Chaque test lance `annotate_text()` avec les mêmes paramètres, seuls le prompt (pièce 5), les few-shot et le modèle changent.

---

## 4. Résultats synthétiques

### 4.1 Tableau comparatif

| Test | Modèle | Extr. | Temps | Classes | Hyp. attributs | Couverture /30 | Moy. hyp/extr. | Erreurs |
|---|---|---|---|---|---|---|---|---|
| **A** (classe unique) | Gemini 2.5 Flash | **118** | 157.5s | 1 | 27 | **27/30** | 2.9 | 0 |
| **B** (classe spécifique) | Gemini 2.5 Flash | 112 | 176.7s | 2 | 28 | **28/30** | 3.0 | 0 |
| **A** (classe unique) | GPT-4o Mini | 104 | 220.5s | 1 | 28 | **28/30** | 2.0 | 0 |
| **B** (classe spécifique) | GPT-4o Mini | 95 | 180.2s | **14** | 26 | 26/30 | 2.1 | 0 |

**Légende** :
- **Classes** = hypostases distinctes dans `extraction_class` (1 pour approche A, variable pour B)
- **Hyp. attributs** = hypostases distinctes trouvées dans `attributes["hypostases"]`
- **Couverture /30** = nombre des 30 hypostases effectivement utilisées (dans attributs)
- **Moy. hyp/extr.** = nombre moyen d'hypostases attribuées par extraction

### 4.2 Richesse dans `extraction_class` (Approche B seulement)

**Gemini 2.5 Flash** — 2 classes :
| Classe | Nombre | % |
|---|---|---|
| théorie | 97 | 86.6% |
| problème | 15 | 13.4% |

**GPT-4o Mini** — 14 classes :
| Classe | Nombre | % |
|---|---|---|
| théorie | 59 | 62.1% |
| problème | 10 | 10.5% |
| hypothèse | 7 | 7.4% |
| événement | 5 | 5.3% |
| définition | 3 | 3.2% |
| axiome | 2 | 2.1% |
| méthode | 2 | 2.1% |
| croyance | 1 | 1.1% |
| dimension | 1 | 1.1% |
| domaine | 1 | 1.1% |
| loi | 1 | 1.1% |
| paradoxe | 1 | 1.1% |
| phénomène | 1 | 1.1% |
| principe | 1 | 1.1% |

### 4.3 Richesse dans `attributes["hypostases"]` (les 4 tests)

**Gemini 2.5 Flash — Approche A** (27/30, 345 attributions, moy. 2.9/extr.) :
| Hypostase | Freq. | | Hypostase | Freq. | | Hypostase | Freq. |
|---|---|---|---|---|---|---|---|
| méthode | 43 | | structure | 41 | | définition | 41 |
| principe | 38 | | formalisme | 20 | | problème | 16 |
| phénomène | 16 | | loi | 15 | | événement | 11 |
| théorie | 11 | | valeur | 10 | | croyance | 8 |
| domaine | 8 | | axiome | 7 | | mode | 7 |
| paradigme | 6 | | classification | 6 | | hypothèse | 5 |
| invariant | 5 | | conjecture | 4 | | dimension | 3 |
| donnée | 3 | | indice | 2 | | variable | 2 |
| paradoxe | 1 | | variation | 1 | | aporie | 1 |
| *Manquantes : objet, variance, approximation* |||||||

**Gemini 2.5 Flash — Approche B** (28/30, 335 attributions, moy. 3.0/extr.) :
| Hypostase | Freq. | | Hypostase | Freq. | | Hypostase | Freq. |
|---|---|---|---|---|---|---|---|
| principe | 41 | | définition | 37 | | méthode | 36 |
| structure | 30 | | théorie | 27 | | loi | 18 |
| problème | 17 | | formalisme | 17 | | phénomène | 16 |
| événement | 11 | | objet | 11 | | croyance | 10 |
| mode | 8 | | domaine | 7 | | axiome | 7 |
| hypothèse | 7 | | valeur | 7 | | paradigme | 5 |
| classification | 5 | | invariant | 4 | | conjecture | 3 |
| dimension | 3 | | donnée | 2 | | aporie | 2 |
| variable | 1 | | variation | 1 | | indice | 1 |
| paradoxe | 1 | | *Manquantes : variance, approximation* |||||

**GPT-4o Mini — Approche A** (28/30, 208 attributions, moy. 2.0/extr.) :
| Hypostase | Freq. | | Hypostase | Freq. | | Hypostase | Freq. |
|---|---|---|---|---|---|---|---|
| phénomène | 23 | | structure | 17 | | principe | 16 |
| méthode | 16 | | axiome | 15 | | théorie | 13 |
| domaine | 13 | | définition | 11 | | valeur | 10 |
| objet | 9 | | loi | 9 | | paradigme | 7 |
| problème | 5 | | formalisme | 5 | | paradoxe | 5 |
| dimension | 4 | | événement | 3 | | hypothèse | 3 |
| invariant | 3 | | conjecture | 2 | | classification | 2 |
| variable | 2 | | donnée | 2 | | croyance | 2 |
| mode | 1 | | variation | 1 | | aporie | 1 |
| indice | 1 | | *Manquantes : variance, approximation* |||||
| *Hallucinations : système, interaction, interface, dimenssion, étude, principes, invariants* |||||||

**GPT-4o Mini — Approche B** (26/30, 204 attributions, moy. 2.1/extr.) :
| Hypostase | Freq. | | Hypostase | Freq. | | Hypostase | Freq. |
|---|---|---|---|---|---|---|---|
| théorie | 28 | | axiome | 21 | | phénomène | 19 |
| structure | 15 | | principe | 14 | | problème | 11 |
| hypothèse | 10 | | loi | 10 | | méthode | 9 |
| dimension | 8 | | définition | 7 | | domaine | 7 |
| événement | 7 | | formalisme | 6 | | objet | 5 |
| valeur | 5 | | conjecture | 3 | | croyance | 3 |
| donnée | 3 | | variation | 2 | | mode | 2 |
| paradoxe | 2 | | variable | 2 | | paradigme | 2 |
| invariant | 1 | | variance | 1 | ||||
| *Manquantes : classification, aporie, indice, approximation* |||||||

### 4.4 Hypostases jamais utilisées

**`approximation`** est absente des 4 tests. **`variance`** est quasi-absente (1 seule occurrence sur GPT-B). Le texte source ne contient probablement pas d'arguments de ce type.

### 4.5 Hallucinations

Les LLM inventent parfois des hypostases hors-liste :

| Modèle | Approche | Hallucinations |
|---|---|---|
| Gemini | A | illustration, histoire, rôle, application, modélisation |
| Gemini | B | transformation, application, publication |
| GPT | A | système, interaction, interface, dimenssion, étude, principes, invariants |
| GPT | B | problématique |

GPT hallucine plus que Gemini (7 vs 5 en approche A), mais les hallucinations sont filtrées par la normalisation côté code (`front/normalisation.py`).

---

## 5. Résultats détaillés par test

### 5.1 TEST 1 — Approche A / Gemini 2.5 Flash

**118 extractions, 157.5s, 0 erreur**

| # | Classe | Extrait (60 premiers chars) | Hypostases |
|---|---|---|---|
| 1 | hypostase | Les intelligences artificielles, naturelle individuelle et co... | classification, structure, définition |
| 2 | hypostase | Il est parfois souhaité que les intelligences artificielles n... | mode, problème, croyance |
| 3 | hypostase | Se trouve ainsi campé le théâtre de 3 intelligences différent... | structure, phénomène, classification |
| 4 | hypostase | L'une des interfaces est entre des personnes échangeant des p... | méthode, problème, structure |
| 5 | hypostase | Roger Penrose a illustré les échanges entre des mathématicien... | événement, méthode |
| 6 | hypostase | Les mathématiciens apportent leurs formalismes dont les physi... | paradoxe, formalisme, phénomène |
| 7 | hypostase | Cette situation les fait réfléchir à la manière de faire prog... | problème, méthode, théorie |
| 8 | hypostase | les mathématiciens qualifient les mathématiques comme métapho... | définition, méthode, théorie |
| 9 | hypostase | Avant l'époque de Descartes, les mêmes érudits développaient... | invariant, structure |
| 10 | hypostase | Les mathématiques et la physiques se sont distinguées quand d... | événement, variation, classification |
| 11 | hypostase | la venue de nouveaux savoirs théoriques perturbaient en occid... | phénomène, événement, problème |
| 12 | hypostase | Descartes, Spinoza, Copernic, Galilée, Darwin en apportant d... | paradigme, problème, événement |
| 13 | hypostase | Le siècle des lumières, puis l'abolition des privilèges par l... | événement, variation, dimension |
| 14 | hypostase | L'intelligence artificielle est apparue avec Alan Turing math... | événement, formalisme, méthode |
| 15 | hypostase | Cela conduit à penser le rapport entre l'IA et la pensée hum... | problème, théorie, définition |
| 16 | hypostase | Entre les trois formes distinctes d'intelligences, il y a des... | problème, définition, structure |
| 17 | hypostase | Une géométrie des débats va servir à formaliser ces interface... | méthode, formalisme, théorie |
| 18 | hypostase | La géométrie des débats formalise de manière unifiée les déve... | formalisme, méthode, structure |
| 19 | hypostase | les arguments situés aux croisements de fils de raisonnements... | définition, principe, problème |
| 20 | hypostase | Le débat d'idées entre humain : ICH → IIH... | définition, mode |
| 21 | hypostase | une interface argumentative : IIH → IA... | définition, mode |
| 22 | hypostase | une interface propositionnelle : IA → ICH... | définition, mode |
| 23 | hypostase | Les interfaces avec l'IA sont décrits d'une manière suffisam... | principe, formalisme, méthode |
| 24 | hypostase | Hypostasia nomme une interface avec des arguments tenus lors... | définition |
| 25 | hypostase | Hypostasia interface des IA génératives. | définition, mode |
| 26 | hypostase | Hypostasia n'est pas un simple outil de prise de notes... | définition, valeur |
| 27 | hypostase | C'est un outil de gestion de débat et de connaissance dont l... | méthode, définition, structure |
| 28 | hypostase | Hypostasia les restitue en les cartographiant grâce à un plo... | méthode, structure, formalisme |
| 29 | hypostase | Ce qui permet de localiser les arguments manquants... | problème, indice, donnée |
| 30 | hypostase | Hypostasia en tirant les arguments des propos des personnes... | principe, problème, méthode |
| 31 | hypostase | Hypostasia réalise un calcul sur des arguments supposés poin... | principe, axiome, méthode |
| 32 | hypostase | Pas de reformulation sans ancrage. Pas de consensus fictif. | loi, principe, axiome |
| 33 | hypostase | Dans le débat, l'IA joue aussi un rôle de paratonnerre... | phénomène, croyance |
| 34 | hypostase | Un grand débat fort animé porte sur une co-conception partic... | événement, problème, domaine |
| 35 | hypostase | Il y a actuellement un grand débat sur les risques venant de... | problème, hypothèse, croyance |
| 36 | hypostase | Aussi faut-il poser des limites techniques, juridiques... | méthode, loi, principe |
| 37 | hypostase | Les débats s'animent quand ils portent sur des thèmes impliqu... | phénomène, variable, domaine |
| 38 | hypostase | Pour certaines communautés, il n'est pas acceptable que l'IA... | croyance, valeur, principe |
| 39 | hypostase | Il pourrait en revanche être intéressant que l'IA offre à cha... | conjecture, méthode, dimension |
| 40 | hypostase | un débat d'idées se termine le plus souvent pour des raisons... | phénomène, événement, loi |
| ... | ... | *(118 extractions au total — voir sortie complète)* | ... |

*(La liste complète des 118 extractions est dans le fichier de sortie brut)*

---

### 5.2 TEST 2 — Approche B / Gemini 2.5 Flash

**112 extractions, 176.7s, 0 erreur — 2 classes seulement (théorie 87%, problème 13%)**

| # | Classe | Extrait (60 premiers chars) | Hypostases |
|---|---|---|---|
| 1 | théorie | Les intelligences artificielles, naturelle individuelle et co... | définition, structure, phénomène |
| 2 | théorie | Il est parfois souhaité que les intelligences artificielles n... | croyance, mode, principe |
| 3 | théorie | Se trouve ainsi campé le théâtre de 3 intelligences différent... | structure, phénomène, définition |
| 4 | problème | L'une des interfaces est entre des personnes échangeant des p... | problème, méthode, mode |
| 5 | théorie | Roger Penrose a illustré les échanges entre des mathématicien... | événement, méthode, phénomène |
| 6 | théorie | Les mathématiciens apportent leurs formalismes dont les physi... | paradoxe, formalisme, phénomène |
| 7 | problème | Cette situation les fait réfléchir à la manière de faire prog... | problème, méthode, formalisme |
| 8 | théorie | On voit ainsi s'enclencher un cycle créatif... | théorie, définition, mode |
| ... | ... | *(112 extractions — 97 théorie + 15 problème)* | ... |

**Observation** : Gemini classe presque tout en `théorie`. Le texte est effectivement très théorique, mais cette pauvreté de classification rend l'approche B peu utile avec Gemini.

---

### 5.3 TEST 3 — Approche A / GPT-4o Mini

**104 extractions, 220.5s, 0 erreur**

| # | Classe | Extrait (60 premiers chars) | Hypostases |
|---|---|---|---|
| 1 | hypostase | Les intelligences artificielles, naturelle individuelle et co... | objet, phénomène |
| 2 | hypostase | Les débats d'idées se font entre personnes constituant un col... | système, phénomène |
| 3 | hypostase | Il est parfois souhaité que les intelligences artificielles n... | principe, mode |
| 4 | hypostase | L'une des interfaces est entre des personnes échangeant des p... | problème, événement |
| 5 | hypostase | Les mathématiciens apportent leurs formalismes dont les physi... | variation, axiome |
| 6 | hypostase | Cette situation les fait réfléchir à la manière de faire prog... | théorie, conjecture |
| 7 | hypostase | les mathématiciens qualifient les mathématiques comme métapho... | théorie, paradigme |
| ... | ... | *(104 extractions — toutes en classe `hypostase`)* | ... |

**Observation** : GPT est plus lent (220s vs 158s) mais produit des hypostases variées dans les attributs (2 par extraction en moyenne). Quelques hallucinations mineures dans les hypostases (`"système"`, `"interaction"`, `"dimenssion"` — non listées dans les 30).

---

### 5.4 TEST 4 — Approche B / GPT-4o Mini

**95 extractions, 180.2s, 0 erreur — 14 classes distinctes**

| # | Classe | Extrait (60 premiers chars) | Hypostases |
|---|---|---|---|
| 1 | théorie | Les intelligences artificielles, naturelle individuelle et co... | théorie, phénomène |
| 2 | problème | Il est parfois souhaité que les intelligences artificielles n... | problème, hypothèse |
| 3 | événement | Se trouve ainsi campé le théâtre de 3 intelligences différent... | événement, dimension |
| 4 | axiome | Les mathématiciens apportent leurs formalismes dont les physi... | axiome, loi |
| 5 | théorie | Cette situation les fait réfléchir à la manière de faire prog... | théorie, conjecture |
| 6 | théorie | les mathématiciens qualifient les mathématiques comme métapho... | théorie, conjecture |
| 7 | problème | les mathématiques et la physiques se sont distinguées quand d... | problème, dimension |
| 8 | théorie | la venue de nouveaux savoirs théoriques perturbaient en occid... | théorie, phénomène |
| 9 | théorie | Le siècle des lumières, puis l'abolition des privilèges par l... | théorie, variation |
| 10 | théorie | L'intelligence artificielle est apparue avec Alan Turing math... | théorie, formalisme |
| 11 | théorie | Cela conduit à penser le rapport entre l'IA et la pensée hum... | théorie, phénomène |
| 12 | théorie | Entre les trois formes distinctes d'intelligences, il y a des... | théorie, objet |
| 13 | théorie | Une géométrie des débats va servir à formaliser ces interface... | théorie, formalisme |
| 14 | théorie | La géométrie des débats formalise de manière unifiée les déve... | théorie, structure |
| 15 | théorie | Les arguments situés aux croisements de fils de raisonnements... | phénomène, invariant |
| 16 | hypothèse | Les interfaces avec l'IA sont décrites d'une manière suffisam... | hypothèse, méthode |
| 17 | problème | Hypostasia n'est pas un simple outil de prise de notes... | problème, définition |
| 18 | événement | Le débat d'idées entre humain : ICH → IIH... | événement, mode |
| 19 | événement | Une interface argumentative : IIH → IA... | événement, dimension |
| 20 | événement | Une interface propositionnelle : IA → ICH... | événement, dimension |
| 21 | théorie | Les interfaces à définir sont : ICH → IIH, IIH → IA, IA → ICH... | théorie, structure |
| 22 | théorie | C'est un outil de gestion de débat et de connaissance dont le... | principe, méthode, phénomène |
| 23 | théorie | Ce qui permet de localiser les arguments manquants... | valeur, objet, phénomène |
| 24 | hypothèse | Hypostasia en tirant les arguments des propos des personnes... | hypothèse |
| 25 | loi | Pas de consensus fictif. | loi, axiome |
| 26 | théorie | Un grand débat fort animé porte sur une co-conception partic... | domaine, événement |
| 27 | problème | l'IA nourrirait une paresse intellectuelle... | problème, croyance |
| 28 | hypothèse | Aussi faut-il poser des limites techniques, juridiques... | hypothèse, principe |
| 29 | paradoxe | Il pourrait en revanche être intéressant que l'IA offre à cha... | paradoxe, phénomène |
| 30 | événement | un débat d'idées se termine le plus souvent pour des raisons... | événement, structure |
| 31 | dimension | Chaque forme d'intelligence se distingue par sa manière d'en... | dimension, variation |
| 32 | principe | Le débat d'idées est l'interface d'échange entre des personne... | principe, structure |
| ... | ... | *(95 extractions — 14 classes — voir sortie complète)* | ... |

**Observation** : GPT-4o Mini avec l'approche B est le plus riche en classification. Il utilise 14 des 30 hypostases comme `extraction_class`, ce qui donne un paysage argumentatif beaucoup plus varié.

---

## 6. Synthèse et recommandations

### 6.1 Stabilité

**Les 4 tests produisent 0 erreur.** Pas de boucle de répétition, pas de JSON corrompu, pas de crash. Le prompt corrigé (cohérent avec les few-shot et le format natif LangExtract) stabilise les deux modèles.

### 6.2 Volume d'extractions

L'approche A produit plus d'extractions (118/104) que l'approche B (112/95). Le format plus simple laisse au LLM plus de "bande passante" pour extraire du contenu au lieu de classifier.

### 6.3 Richesse de classification — deux niveaux de lecture

**Niveau 1 : `extraction_class`** (la clé JSON)

| | Approche A | Approche B |
|---|---|---|
| **Gemini** | 1 classe (`hypostase`) | 2 classes (`théorie` 87%, `problème` 13%) |
| **GPT** | 1 classe (`hypostase`) | 14 classes variées |

Gemini en approche B est très pauvre en `extraction_class` — il reproduit les seules classes vues dans les few-shot (qui n'en montrent que 2). **Biais probable des few-shot.**

**Niveau 2 : `attributes["hypostases"]`** (la vraie richesse sémantique)

| | Approche A | Approche B |
|---|---|---|
| **Gemini** | **27/30** (345 attributions, moy. 2.9/extr.) | **28/30** (335 attributions, moy. 3.0/extr.) |
| **GPT** | **28/30** (208 attributions, moy. 2.0/extr.) | 26/30 (204 attributions, moy. 2.1/extr.) |

**Constat clé** : la richesse dans les attributs est comparable entre les 4 tests (26 à 28 sur 30). Même quand Gemini ne produit que 2 `extraction_class` en approche B, il utilise 28 hypostases distinctes dans les attributs. **Les attributs portent la vraie diversité, pas la clé JSON.**

Gemini est plus généreux en attributions (3 hypostases par extraction en moyenne) que GPT (2 par extraction).

Les hypostases `approximation` et `variance` sont absentes des 4 tests — elles ne correspondent probablement pas au contenu du texte analysé.

### 6.4 Performance

| Modèle | Approche A | Approche B |
|---|---|---|
| **Gemini** | 157.5s | 176.7s |
| **GPT** | 220.5s | 180.2s |

Gemini est plus rapide que GPT dans les deux approches.

### 6.5 Trade-offs

| Critère | Approche A (classe unique) | Approche B (classe spécifique) |
|---|---|---|
| Stabilité | Excellente | Excellente |
| Volume | Plus d'extractions (118/104) | Moins d'extractions (112/95) |
| `extraction_class` | Toujours `"hypostase"` (inutile) | Variable (riche avec GPT, pauvre avec Gemini) |
| `attributes["hypostases"]` | 27-28/30 couverture | 26-28/30 couverture |
| Richesse réelle | **Équivalente** (dans les attributs) | **Équivalente** (dans les attributs) |
| Front-end | Le badge doit lire `attributes` | Le badge lit `extraction_class` |
| Biais few-shot | Aucun (une seule classe) | **Fort avec Gemini** (reproduit les few-shot) |

### 6.6 Biais des few-shot

Ce test utilise seulement 2 extractions en few-shot : une `"théorie"` et un `"problème"`. Gemini en approche B reproduit ce pattern exactement (87% théorie, 13% problème). GPT extrapole à 14 classes.

**Hypothèse** : si les few-shot montraient les 30 hypostases, Gemini diversifierait ses `extraction_class`. À vérifier dans un prochain test avec des few-shot couvrant les 30 classes.

### 6.7 Hallucinations

Les LLM inventent parfois des hypostases hors-liste. GPT hallucine plus que Gemini (7 vs 5), mais les hallucinations sont filtrées côté code par la normalisation. Exemples : `"système"`, `"interaction"`, `"problématique"`, `"application"`.

### 6.8 Recommandation

La richesse sémantique est **dans les attributs, pas dans `extraction_class`**. Les deux approches couvrent 26 à 28 des 30 hypostases dans les attributs. Le choix entre A et B est donc un choix d'**affichage front-end**, pas de qualité d'analyse.

**Prochaine étape** : refaire le test avec des few-shot couvrant les 30 hypostases pour vérifier si Gemini diversifie ses `extraction_class` quand il voit plus d'exemples.
