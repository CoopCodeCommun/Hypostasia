"""
Prompts pour les benchmarks d'extraction.
Organise les definitions des 30 hypostases par familles epistemiques.
/ Prompts for extraction benchmarks.
/ Organizes 30 hypostase definitions by epistemic families.

LOCALISATION : benchmarks/extraction_format/prompts.py
"""

# ---------------------------------------------------------------------------
# Definitions des 30 hypostases organisees par familles epistemiques.
# Chaque famille correspond a un mode de raisonnement "non refute par".
# Chaque definition combine l'informelle (comprehensible) et la formelle (precise).
# / 30 hypostase definitions organized by epistemic families.
# / Each family corresponds to a "not refuted by" reasoning mode.
# / Each definition combines informal (understandable) and formal (precise).
# ---------------------------------------------------------------------------

DEFINITIONS_HYPOSTASES = """# Les 30 hypostases — classées par famille épistémique

Les hypostases sont les « 30 manières d'être discutable » définies par la géométrie des débats.
Avec 2 dispositifs de preuve (formel, empirique) et 3 modes de raisonnement (induction, abduction, déduction), on obtient 6 modes → 30 hypostases.

## Famille 1 — Non réfuté par induction empirique (ce qu'on observe sans pouvoir généraliser)

- **classification** : distribuer en classes, en catégories. — *non prouvé par abduction empirique*
- **aporie** : difficulté d'ordre rationnel apparemment sans issue. — *non prouvé par déduction empirique*
- **approximation** : calcul approché d'une grandeur réelle. — *non prouvé par déduction formelle*
- **paradoxe** : proposition à la fois vraie et fausse. — *non prouvé par abduction formelle*
- **formalisme** : considération de la forme d'un raisonnement. — *non prouvé par induction formelle*

## Famille 2 — Non réfuté par déduction empirique (ce qui se produit sans cadre formel)

- **événement** : ce qui arrive. — *non prouvé par déduction formelle*
- **variation** : changement d'un état dans un autre. — *non prouvé par abduction empirique*
- **dimension** : grandeur mesurable qui détermine des positions. — *non prouvé par abduction formelle*
- **mode** : manière d'être d'un système. — *non prouvé par induction empirique*
- **croyance** : certitude ou conviction qui fait croire une chose vraie ou possible. — *non prouvé par induction formelle*

## Famille 3 — Non réfuté par induction formelle (ce qu'on formalise sans pouvoir vérifier)

- **invariant** : grandeur, relation ou propriété conservée lors d'une transformation. — *non prouvé par déduction formelle*
- **valeur** : mesure d'une grandeur variable. — *non prouvé par abduction empirique*
- **structure** : organisation des parties d'un système. — *non prouvé par abduction formelle*
- **axiome** : proposition admise au départ d'une théorie. — *non prouvé par induction empirique*
- **conjecture** : opinion ou proposition non vérifiée. — *non prouvé par déduction empirique*

## Famille 4 — Non réfuté par déduction formelle (ce qu'on déduit formellement)

- **paradigme** : modèle ou exemple. — *non prouvé par abduction empirique*
- **objet** : ce sur quoi porte le discours, la pensée, la connaissance. — *non prouvé par abduction formelle*
- **principe** : cause a priori d'une connaissance. — *non prouvé par induction empirique*
- **domaine** : champ discerné par des limites, bornes, frontières. — *non prouvé par déduction formelle*
- **loi** : corrélation. — *non prouvé par induction empirique*

## Famille 5 — Non réfuté par abduction empirique (ce qu'on constate sans pouvoir l'expliquer)

- **phénomène** : ce qui se manifeste à la connaissance via les sens. — *non prouvé par déduction formelle*
- **variable** : ce qui prend différentes valeurs, dont dépend l'état d'un système. — *non prouvé par abduction formelle*
- **variance** : dispersion d'une distribution ou d'un échantillon. — *non prouvé par induction empirique*
- **indice** : indicateur numérique ou littéral qui sert à distinguer ou classer. — *non prouvé par déduction empirique*
- **donnée** : ce qui est admis, donné, qui sert à découvrir ou à raisonner. — *non prouvé par induction formelle*

## Famille 6 — Non réfuté par abduction formelle (ce qu'on propose sans pouvoir le confirmer)

- **méthode** : procédure qui indique ce que l'on doit faire ou comment le faire. — *non prouvé par déduction formelle*
- **définition** : détermination, caractérisation du contenu d'un concept. — *non prouvé par abduction empirique*
- **hypothèse** : explication ou possibilité d'un événement. — *non prouvé par induction empirique*
- **problème** : difficulté à résoudre. — *non prouvé par déduction empirique*
- **théorie** : construction intellectuelle explicative, hypothétique et synthétique. — *non prouvé par induction formelle*
"""


# ---------------------------------------------------------------------------
# Prompt de base (instructions d'analyse)
# / Base prompt (analysis instructions)
# ---------------------------------------------------------------------------

PROMPT_INSTRUCTIONS = """Tu es Hypostasia, un expert en analyse argumentative et en géométrie des débats.
Ta mission est d'extraire l'ossature argumentative du texte en identifiant les hypostases.
Tu agis avec neutralité et précision.

{definitions}

ANALYSE LE TEXTE SUIVANT.

Instructions :
1. Pour un texte court (< 2000 chars) : identifie 3 à 8 arguments.
2. Pour un texte moyen (2000–10000 chars) : identifie 5 à 15 arguments.
3. Pour un texte long (> 10000 chars) : identifie 10 à 25 arguments.
4. Extrais la citation EXACTE du texte. Ne reformule jamais.
5. Synthétise l'idée en une phrase (résumé).
6. Associe 1 à 3 hypostases parmi les 30 définies.
7. Ignore le bruit : menus, pubs, copyright, URLs.
8. Tu es AUTORISÉ à reproduire des citations exactes (fair use académique).
"""


# ---------------------------------------------------------------------------
# Pieces 5 (regles de format) — une pour chaque approche
# / Pieces 5 (format rules) — one for each approach
# ---------------------------------------------------------------------------

PIECE_5_APPROCHE_A = """RÈGLES DE FORMAT :

{
  "hypostase": "citation exacte du texte source",
  "hypostase_attributes": {
    "resume": "synthèse en une phrase",
    "hypostases": "hypothèse, théorie",
    "mots_cles": "mot1, mot2"
  }
}

- La clé est TOUJOURS "hypostase"
- Les hypostases spécifiques sont dans "hypostases" (1 à 3 parmi les 30)
- Ne JAMAIS lister les 30. Ne JAMAIS boucler.
"""

PIECE_5_APPROCHE_B = """RÈGLES DE FORMAT :

{
  "théorie": "citation exacte du texte source",
  "théorie_attributes": {
    "resume": "synthèse en une phrase",
    "hypostases": "théorie, conjecture",
    "mots_cles": "mot1, mot2"
  }
}

- La clé est le NOM de l'hypostase principale (théorie, problème, hypothèse...)
- Chaque extraction peut avoir une clé différente parmi les 30 hypostases.
- Les hypostases secondaires sont dans "hypostases" (1 à 3 parmi les 30)
- Ne JAMAIS lister les 30. Ne JAMAIS boucler.
"""


def construire_prompt(approche="A"):
    """
    Construit le prompt complet pour une approche donnee.
    / Build the full prompt for a given approach.
    """
    piece_5 = PIECE_5_APPROCHE_A if approche == "A" else PIECE_5_APPROCHE_B
    prompt = PROMPT_INSTRUCTIONS.format(definitions=DEFINITIONS_HYPOSTASES)
    return prompt + "\n" + piece_5
