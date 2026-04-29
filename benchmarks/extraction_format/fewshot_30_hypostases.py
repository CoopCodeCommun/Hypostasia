"""
Texte synthetique et few-shot couvrant les 30 hypostases.
Le texte porte sur le debat IA dans l'education — un sujet qui permet
naturellement tous les types d'arguments epistemiques.
/ Synthetic text and few-shot covering all 30 hypostases.
/ Text is about the AI in education debate — a topic that naturally
/ allows all types of epistemic arguments.

LOCALISATION : benchmarks/extraction_format/fewshot_30_hypostases.py
"""

import langextract as lx

# ---------------------------------------------------------------------------
# Texte synthetique couvrant les 30 hypostases
# Chaque paragraphe contient 5 arguments d'une meme famille epistemique.
# / Synthetic text covering all 30 hypostases
# / Each paragraph contains 5 arguments from the same epistemic family.
# ---------------------------------------------------------------------------

TEXTE_FEWSHOT_30 = """Le débat sur l'intelligence artificielle dans l'éducation

On distingue trois catégories d'usage de l'IA dans l'enseignement : l'aide à la rédaction, \
l'évaluation automatisée et la recherche documentaire. Comment évaluer un travail quand on \
ne sait plus qui l'a réellement produit ? C'est une impasse dont personne ne voit la sortie. \
Les estimations actuelles suggèrent que 40% des mémoires contiennent des passages générés \
par IA, mais ce chiffre reste une approximation grossière. L'IA aide les étudiants à mieux \
écrire mais les empêche d'apprendre à écrire : voilà le paradoxe central de cette révolution. \
Le cadre logique impose de distinguer clairement l'outil de son usage, sous peine de confondre \
le formalisme avec la réalité.

En mars 2026, une étudiante de la Sorbonne a fait rédiger son mémoire de fin d'études par \
une IA, créant un événement sans précédent dans le monde universitaire. Le rapport des \
étudiants à l'écriture académique a radicalement changé en moins de deux ans, une variation \
que personne n'avait anticipée. Le temps moyen consacré à la rédaction d'un mémoire a \
diminué de 60%, une dimension mesurable du phénomène. L'enseignement supérieur fonctionne \
désormais selon un mode hybride où l'IA est omniprésente mais rarement encadrée. Beaucoup \
d'enseignants croient sincèrement que l'IA finira par remplacer la dissertation comme \
exercice pédagogique, une croyance qui influence déjà les programmes.

Quelle que soit la technologie utilisée, l'esprit critique reste la compétence indispensable \
que l'éducation doit transmettre : c'est l'invariant de toute pédagogie. Le taux de plagiat \
détecté a augmenté de 300% en un an, une valeur qui alarme les institutions. L'université \
s'organise en trois niveaux de contrôle — département, commission pédagogique, conseil \
d'administration — une structure qui peine à suivre le rythme du changement. Tout étudiant \
a le droit d'utiliser les outils de son époque : cet axiome, rarement contesté, fonde le débat. \
On suppose que l'interdiction totale de l'IA serait contre-productive et pousserait les usages \
dans la clandestinité, mais cette conjecture n'a pas encore été vérifiée.

Le modèle finlandais, où l'IA est intégrée dans les cursus depuis 2024, constitue un paradigme \
pour les autres pays européens. L'objet de ce débat est la place de l'IA dans l'évaluation \
des compétences, pas dans l'enseignement lui-même. Le principe d'autonomie intellectuelle, \
qui fonde l'éducation depuis les Lumières, exige que l'étudiant pense par lui-même. Ce débat \
concerne exclusivement le domaine de l'enseignement supérieur et ne s'applique pas à \
l'enseignement primaire. Plus l'accès à l'IA est facile et gratuit, plus son usage non encadré \
augmente : c'est une loi empirique observée dans tous les pays.

On observe une baisse significative de la qualité argumentative dans les travaux rendus, un \
phénomène qui inquiète les jurys de soutenance. Le niveau d'appropriation de l'IA par les \
étudiants varie considérablement selon les disciplines, la variable clé étant la nature du \
travail demandé. Les résultats de l'enquête montrent une grande variance entre établissements, \
certains ayant 10% d'usage et d'autres 80%. Le nombre de citations exactes dans un mémoire \
est devenu un indice fiable de travail personnel. Les données de l'enquête PISA 2025 montrent \
que les pays qui encadrent l'IA obtiennent de meilleurs résultats que ceux qui l'interdisent.

La méthode proposée consiste à encadrer l'usage plutôt qu'à l'interdire, en s'inspirant des \
chartes universitaires existantes. On entend par « usage acceptable » toute utilisation de \
l'IA qui est déclarée, sourcée et vérifiable par l'enseignant : c'est la définition retenue par \
la commission. Si l'on autorise l'IA sous conditions strictes, la qualité des travaux pourrait \
s'améliorer plutôt que se dégrader, c'est l'hypothèse de travail de cette commission. Le \
problème central reste l'absence de règles claires et partagées entre les établissements. La \
théorie des communs d'Elinor Ostrom offre un cadre pour penser la gouvernance collective de \
l'IA comme ressource partagée par une communauté éducative."""


# ---------------------------------------------------------------------------
# 30 extractions — une par hypostase, organisees par famille
# / 30 extractions — one per hypostase, organized by family
# ---------------------------------------------------------------------------

EXTRACTIONS_30 = [
    # --- Famille 1 : Induction empirique (non refute par l'observation) ---
    # / --- Family 1: Empirical induction (not refuted by observation) ---
    lx.data.Extraction(
        extraction_class="classification",
        extraction_text="On distingue trois catégories d'usage de l'IA dans l'enseignement : l'aide à la rédaction, l'évaluation automatisée et la recherche documentaire.",
        attributes={"resume": "Trois catégories d'usage de l'IA identifiées.", "hypostases": "classification", "mots_cles": "IA, éducation, catégories"},
    ),
    lx.data.Extraction(
        extraction_class="aporie",
        extraction_text="Comment évaluer un travail quand on ne sait plus qui l'a réellement produit ?",
        attributes={"resume": "Impasse sur l'évaluation de l'originalité.", "hypostases": "aporie, problème", "mots_cles": "évaluation, authenticité"},
    ),
    lx.data.Extraction(
        extraction_class="approximation",
        extraction_text="Les estimations actuelles suggèrent que 40% des mémoires contiennent des passages générés par IA, mais ce chiffre reste une approximation grossière.",
        attributes={"resume": "Estimation imprécise de l'usage de l'IA dans les mémoires.", "hypostases": "approximation, donnée", "mots_cles": "estimation, mémoires, 40%"},
    ),
    lx.data.Extraction(
        extraction_class="paradoxe",
        extraction_text="L'IA aide les étudiants à mieux écrire mais les empêche d'apprendre à écrire : voilà le paradoxe central de cette révolution.",
        attributes={"resume": "L'IA améliore et dégrade simultanément l'écriture.", "hypostases": "paradoxe, problème", "mots_cles": "écriture, apprentissage, paradoxe"},
    ),
    lx.data.Extraction(
        extraction_class="formalisme",
        extraction_text="Le cadre logique impose de distinguer clairement l'outil de son usage, sous peine de confondre le formalisme avec la réalité.",
        attributes={"resume": "Nécessité de séparer l'outil de son usage dans le cadre logique.", "hypostases": "formalisme, méthode", "mots_cles": "logique, outil, usage"},
    ),

    # --- Famille 2 : Deduction empirique (ce qui se produit) ---
    # / --- Family 2: Empirical deduction (what happens) ---
    lx.data.Extraction(
        extraction_class="événement",
        extraction_text="En mars 2026, une étudiante de la Sorbonne a fait rédiger son mémoire de fin d'études par une IA, créant un événement sans précédent dans le monde universitaire.",
        attributes={"resume": "Un mémoire rédigé par IA crée un précédent à la Sorbonne.", "hypostases": "événement, problème", "mots_cles": "Sorbonne, mémoire, IA"},
    ),
    lx.data.Extraction(
        extraction_class="variation",
        extraction_text="Le rapport des étudiants à l'écriture académique a radicalement changé en moins de deux ans, une variation que personne n'avait anticipée.",
        attributes={"resume": "Changement rapide du rapport à l'écriture académique.", "hypostases": "variation, phénomène", "mots_cles": "écriture, changement"},
    ),
    lx.data.Extraction(
        extraction_class="dimension",
        extraction_text="Le temps moyen consacré à la rédaction d'un mémoire a diminué de 60%, une dimension mesurable du phénomène.",
        attributes={"resume": "Le temps de rédaction a baissé de 60%.", "hypostases": "dimension, donnée", "mots_cles": "temps, rédaction, 60%"},
    ),
    lx.data.Extraction(
        extraction_class="mode",
        extraction_text="L'enseignement supérieur fonctionne désormais selon un mode hybride où l'IA est omniprésente mais rarement encadrée.",
        attributes={"resume": "L'enseignement supérieur est en mode hybride non encadré.", "hypostases": "mode, structure", "mots_cles": "hybride, enseignement"},
    ),
    lx.data.Extraction(
        extraction_class="croyance",
        extraction_text="Beaucoup d'enseignants croient sincèrement que l'IA finira par remplacer la dissertation comme exercice pédagogique, une croyance qui influence déjà les programmes.",
        attributes={"resume": "Croyance répandue que l'IA remplacera la dissertation.", "hypostases": "croyance, conjecture", "mots_cles": "dissertation, remplacement"},
    ),

    # --- Famille 3 : Induction formelle (ce qu'on formalise) ---
    # / --- Family 3: Formal induction (what we formalize) ---
    lx.data.Extraction(
        extraction_class="invariant",
        extraction_text="Quelle que soit la technologie utilisée, l'esprit critique reste la compétence indispensable que l'éducation doit transmettre : c'est l'invariant de toute pédagogie.",
        attributes={"resume": "L'esprit critique est l'invariant de toute pédagogie.", "hypostases": "invariant, principe", "mots_cles": "esprit critique, pédagogie"},
    ),
    lx.data.Extraction(
        extraction_class="valeur",
        extraction_text="Le taux de plagiat détecté a augmenté de 300% en un an, une valeur qui alarme les institutions.",
        attributes={"resume": "Le plagiat a triplé en un an.", "hypostases": "valeur, donnée", "mots_cles": "plagiat, 300%"},
    ),
    lx.data.Extraction(
        extraction_class="structure",
        extraction_text="L'université s'organise en trois niveaux de contrôle — département, commission pédagogique, conseil d'administration — une structure qui peine à suivre le rythme du changement.",
        attributes={"resume": "La structure universitaire à 3 niveaux est trop lente.", "hypostases": "structure, problème", "mots_cles": "université, contrôle, niveaux"},
    ),
    lx.data.Extraction(
        extraction_class="axiome",
        extraction_text="Tout étudiant a le droit d'utiliser les outils de son époque : cet axiome, rarement contesté, fonde le débat.",
        attributes={"resume": "Le droit aux outils de son époque est un axiome du débat.", "hypostases": "axiome, principe", "mots_cles": "droit, outils, époque"},
    ),
    lx.data.Extraction(
        extraction_class="conjecture",
        extraction_text="On suppose que l'interdiction totale de l'IA serait contre-productive et pousserait les usages dans la clandestinité, mais cette conjecture n'a pas encore été vérifiée.",
        attributes={"resume": "L'interdiction serait contre-productive — hypothèse non vérifiée.", "hypostases": "conjecture, hypothèse", "mots_cles": "interdiction, clandestinité"},
    ),

    # --- Famille 4 : Deduction formelle (ce qu'on deduit) ---
    # / --- Family 4: Formal deduction (what we deduce) ---
    lx.data.Extraction(
        extraction_class="paradigme",
        extraction_text="Le modèle finlandais, où l'IA est intégrée dans les cursus depuis 2024, constitue un paradigme pour les autres pays européens.",
        attributes={"resume": "La Finlande est un modèle d'intégration de l'IA.", "hypostases": "paradigme, méthode", "mots_cles": "Finlande, modèle, intégration"},
    ),
    lx.data.Extraction(
        extraction_class="objet",
        extraction_text="L'objet de ce débat est la place de l'IA dans l'évaluation des compétences, pas dans l'enseignement lui-même.",
        attributes={"resume": "Le débat porte sur l'évaluation, pas l'enseignement.", "hypostases": "objet, domaine", "mots_cles": "évaluation, compétences"},
    ),
    lx.data.Extraction(
        extraction_class="principe",
        extraction_text="Le principe d'autonomie intellectuelle, qui fonde l'éducation depuis les Lumières, exige que l'étudiant pense par lui-même.",
        attributes={"resume": "L'autonomie intellectuelle est un principe fondateur.", "hypostases": "principe, axiome", "mots_cles": "autonomie, Lumières"},
    ),
    lx.data.Extraction(
        extraction_class="domaine",
        extraction_text="Ce débat concerne exclusivement le domaine de l'enseignement supérieur et ne s'applique pas à l'enseignement primaire.",
        attributes={"resume": "Le périmètre est limité à l'enseignement supérieur.", "hypostases": "domaine, classification", "mots_cles": "supérieur, primaire"},
    ),
    lx.data.Extraction(
        extraction_class="loi",
        extraction_text="Plus l'accès à l'IA est facile et gratuit, plus son usage non encadré augmente : c'est une loi empirique observée dans tous les pays.",
        attributes={"resume": "Corrélation entre accessibilité et usage non encadré.", "hypostases": "loi, phénomène", "mots_cles": "accès, corrélation"},
    ),

    # --- Famille 5 : Abduction empirique (ce qu'on constate) ---
    # / --- Family 5: Empirical abduction (what we observe) ---
    lx.data.Extraction(
        extraction_class="phénomène",
        extraction_text="On observe une baisse significative de la qualité argumentative dans les travaux rendus, un phénomène qui inquiète les jurys de soutenance.",
        attributes={"resume": "Baisse observée de la qualité argumentative.", "hypostases": "phénomène, problème", "mots_cles": "qualité, argumentation"},
    ),
    lx.data.Extraction(
        extraction_class="variable",
        extraction_text="Le niveau d'appropriation de l'IA par les étudiants varie considérablement selon les disciplines, la variable clé étant la nature du travail demandé.",
        attributes={"resume": "L'appropriation varie selon la discipline.", "hypostases": "variable, dimension", "mots_cles": "disciplines, appropriation"},
    ),
    lx.data.Extraction(
        extraction_class="variance",
        extraction_text="Les résultats de l'enquête montrent une grande variance entre établissements, certains ayant 10% d'usage et d'autres 80%.",
        attributes={"resume": "Grande disparité d'usage entre établissements.", "hypostases": "variance, donnée", "mots_cles": "établissements, disparité"},
    ),
    lx.data.Extraction(
        extraction_class="indice",
        extraction_text="Le nombre de citations exactes dans un mémoire est devenu un indice fiable de travail personnel.",
        attributes={"resume": "Les citations exactes sont un indicateur de travail personnel.", "hypostases": "indice, méthode", "mots_cles": "citations, indicateur"},
    ),
    lx.data.Extraction(
        extraction_class="donnée",
        extraction_text="Les données de l'enquête PISA 2025 montrent que les pays qui encadrent l'IA obtiennent de meilleurs résultats que ceux qui l'interdisent.",
        attributes={"resume": "PISA 2025 : encadrer l'IA donne de meilleurs résultats.", "hypostases": "donnée, loi", "mots_cles": "PISA, résultats, encadrement"},
    ),

    # --- Famille 6 : Abduction formelle (ce qu'on propose) ---
    # / --- Family 6: Formal abduction (what we propose) ---
    lx.data.Extraction(
        extraction_class="méthode",
        extraction_text="La méthode proposée consiste à encadrer l'usage plutôt qu'à l'interdire, en s'inspirant des chartes universitaires existantes.",
        attributes={"resume": "Encadrer plutôt qu'interdire.", "hypostases": "méthode, principe", "mots_cles": "encadrement, chartes"},
    ),
    lx.data.Extraction(
        extraction_class="définition",
        extraction_text="On entend par « usage acceptable » toute utilisation de l'IA qui est déclarée, sourcée et vérifiable par l'enseignant : c'est la définition retenue par la commission.",
        attributes={"resume": "Définition de l'usage acceptable : déclaré, sourcé, vérifiable.", "hypostases": "définition, méthode", "mots_cles": "usage acceptable, définition"},
    ),
    lx.data.Extraction(
        extraction_class="hypothèse",
        extraction_text="Si l'on autorise l'IA sous conditions strictes, la qualité des travaux pourrait s'améliorer plutôt que se dégrader, c'est l'hypothèse de travail de cette commission.",
        attributes={"resume": "Hypothèse : autoriser sous conditions améliorerait la qualité.", "hypostases": "hypothèse, conjecture", "mots_cles": "conditions, qualité"},
    ),
    lx.data.Extraction(
        extraction_class="problème",
        extraction_text="Le problème central reste l'absence de règles claires et partagées entre les établissements.",
        attributes={"resume": "Absence de règles claires entre établissements.", "hypostases": "problème, structure", "mots_cles": "règles, établissements"},
    ),
    lx.data.Extraction(
        extraction_class="théorie",
        extraction_text="La théorie des communs d'Elinor Ostrom offre un cadre pour penser la gouvernance collective de l'IA comme ressource partagée par une communauté éducative.",
        attributes={"resume": "La théorie des communs comme cadre de gouvernance de l'IA.", "hypostases": "théorie, paradigme", "mots_cles": "Ostrom, communs, gouvernance"},
    ),
]

# Construire l'ExampleData LangExtract
# / Build the LangExtract ExampleData
EXEMPLE_30_HYPOSTASES = lx.data.ExampleData(
    text=TEXTE_FEWSHOT_30,
    extractions=EXTRACTIONS_30,
)
