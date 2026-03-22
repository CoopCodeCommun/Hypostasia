# Comparatif Gemini — 4 configurations testées

Toutes les données ci-dessous concernent **Gemini 2.5 Flash** uniquement,
sur le même texte ("La Ronde des Intelligences", 19726 chars, ~13 chunks).

---

## Tableau comparatif

| | **A + 2 few-shot** | **B + 2 few-shot** | **A + 30 few-shot** | **B + 30 few-shot** |
|---|---|---|---|---|
| **Extractions** | 118 | 112 | 102 | 90 |
| **Temps** | 157s | 177s | 141s | 137s |
| **Classes distinctes** | 1 (`hypostase`) | 2 (`théorie`, `problème`) | 1 (`hypostase`) | **20** |
| **Hyp. valides dans attributs** | 27/30 | **28/30** | 27/30 | 26/30 |
| **Hallucinations attributs** | 5 | 3 | **1** | **1** |
| **Total attributions** | 345 | 335 | 295 | 263 |
| **Moy. hyp/extraction** | 2.9 | 3.0 | 2.9 | 2.9 |
| **Hyp. manquantes** | variance, objet, approx. | variance, approx. | variance, variable, approx. | variance, variable, approx., invariant |

---

## Analyse par critère

### Volume d'extractions

| Config | Extractions | Δ vs max |
|---|---|---|
| A + 2 few-shot | **118** | référence |
| B + 2 few-shot | 112 | -5% |
| A + 30 few-shot | 102 | -14% |
| B + 30 few-shot | 90 | -24% |

Plus le prompt est long (30 few-shot) et plus la clé JSON varie (approche B), moins Gemini produit d'extractions. Le prompt de 30 few-shot consomme du contexte. L'approche B demande au LLM de classifier en plus d'extraire.

### Richesse de classification (`extraction_class`)

| Config | Classes | Distribution |
|---|---|---|
| A + 2 few-shot | 1 | `hypostase` 100% |
| B + 2 few-shot | 2 | `théorie` 87%, `problème` 13% |
| A + 30 few-shot | 1 | `hypostase` 100% |
| B + 30 few-shot | **20** | `définition` 13%, `principe` 12%, `méthode` 10%, `formalisme` 8%, ... |

L'approche A donne toujours 1 classe (par design). L'approche B + 30 few-shot donne 20 classes bien réparties. L'approche B + 2 few-shot est biaisée (Gemini ne reproduit que les 2 classes vues).

### Richesse dans les attributs (`attributes["hypostases"]`)

| Config | Hyp. distinctes | Top 5 (fréquence) |
|---|---|---|
| A + 2 few-shot | 27/30 | méthode (43), structure (41), définition (41), principe (38), formalisme (20) |
| B + 2 few-shot | **28/30** | principe (41), définition (37), méthode (36), structure (30), théorie (27) |
| A + 30 few-shot | 27/30 | méthode (37), définition (36), mode (30), formalisme (25), structure (23) |
| B + 30 few-shot | 26/30 | principe (27), méthode (27), structure (26), définition (25), formalisme (24) |

**La couverture dans les attributs est stable (26-28/30) quelle que soit la configuration.** C'est la constante de ce benchmark.

### Hallucinations

| Config | Hallu. classes | Hallu. attributs | Total |
|---|---|---|---|
| A + 2 few-shot | 0 | 5 (illustration, histoire, rôle, application, modélisation) | 5 |
| B + 2 few-shot | 0 | 3 (transformation, application, publication) | 3 |
| A + 30 few-shot | 0 | **1** (fonction) | **1** |
| B + 30 few-shot | 0 | **1** (publication) | **1** |

**Les 30 few-shot réduisent drastiquement les hallucinations** (de 3-5 à 1). Le LLM a vu les 30 hypostases, il invente moins.

### Hypostases jamais détectées

`approximation` et `variance` sont absentes des 4 tests. `variable` et `invariant` disparaissent avec 30 few-shot. Ces hypostases ne correspondent probablement pas au contenu du texte analysé (qui est très théorique/définitionnel).

---

## Synthèse

| Critère | Meilleure config | Commentaire |
|---|---|---|
| **Volume** | A + 2 few-shot (118) | Prompt court = plus d'extractions |
| **Diversité `extraction_class`** | B + 30 few-shot (20) | Gemini a besoin de voir chaque classe |
| **Diversité attributs** | Toutes équivalentes (26-28/30) | Les attributs sont stables |
| **Hallucinations** | A ou B + 30 few-shot (1) | Les 30 exemples disciplinent le LLM |
| **Vitesse** | B + 30 few-shot (137s) | Paradoxalement le plus rapide |
| **Simplicité front** | A (badge = `attributes[0]`) | Pas de changement HTML nécessaire si on choisit B |

### La question clé : A ou B ?

**Si on choisit A + 30 few-shot** :
- `extraction_class` = toujours `"hypostase"` → le front doit lire `attributes["hypostases"]` pour le badge
- 102 extractions (12 de plus que B)
- Pas de risque de classe halluccinée dans `extraction_class`
- Il faut modifier les templates HTML qui affichent `extraction_class` comme badge

**Si on choisit B + 30 few-shot** :
- `extraction_class` = l'hypostase principale → le badge est direct
- 90 extractions (12 de moins que A)
- 20 classes bien réparties avec Gemini
- Le front fonctionne tel quel (le badge lit déjà `extraction_class`)
- Risque marginal de classe halluccinée (0 observé avec Gemini)

**Mon avis** : les deux se valent. Le choix dépend de si tu préfères :
- Modifier le front pour lire les attributs (A) — plus robuste, plus d'extractions
- Garder le front tel quel (B) — plus simple, classification directe, un peu moins d'extractions
