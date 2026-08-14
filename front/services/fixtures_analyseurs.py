"""
Fixtures des modeles IA et des analyseurs — la definition unique, partagee.
/ AI models and analyzers fixtures — the single, shared definition.

LOCALISATION : front/services/fixtures_analyseurs.py

POURQUOI CE SERVICE EXISTE

Sans analyseur en base, le bouton « Lancer une analyse » n'ouvre aucun
selecteur : il n'a rien a proposer. L'application est alors inutilisable
pour sa fonction principale, et rien a l'ecran ne dit pourquoi.

Cette definition vivait dans `charger_fixtures_demo`, et seulement la.
`charger_fixtures_sample`, ecrite plus tard pour charger les documents
etalons sans le debat fictif ni les pages Wikipedia, ne la reprenait pas :
une installation menee avec elle laissait 0 analyseur, 0 modele IA,
0 prompt, 0 exemple. Recopier la methode aurait donne deux definitions a
tenir a jour — c'est exactement ainsi que l'oubli s'est produit. Elle vit
donc ici, a un seul endroit, et les deux commandes l'appellent.
/ This definition used to live only in charger_fixtures_demo; the later
charger_fixtures_sample did not repeat it, leaving fresh installs with
zero analyzers. Copying it would have left two definitions to maintain —
which is how the omission happened. It lives here now, called by both.

CE QUE LE SERVICE N'ECRIT PAS

Il n'affiche rien. Les deux commandes appelantes ne parlent pas la meme
langue — `charger_fixtures_demo` ecrit des lignes indentees et colorees,
`charger_fixtures_sample` un bilan aligne en colonnes. Le service rend
donc un rapport, et chacune le met en mots a sa facon.
/ It prints nothing: the two callers have different output styles, so it
returns a report and each renders it its own way.
"""

import os

from core.models import AIModel, Configuration
from hypostasis_extractor.models import (
    AnalyseurExample,
    AnalyseurSyntaxique,
    ExampleExtraction,
    ExtractionAttribute,
    PromptPiece,
)

NOM_DE_L_ANALYSEUR_D_EXTRACTION = "Hypostasia"
NOM_DE_L_ANALYSEUR_DE_SYNTHESE = "Synthèse délibérative"
NOM_DE_L_EXEMPLE_FEW_SHOT = "IA & éducation — 30 hypostases"

# Les modeles IA crees automatiquement, un par cle API trouvee dans le
# .env. Pas de Mock : soit une vraie cle, soit pas d'IA du tout — un
# modele fantoche donnerait l'illusion d'une chaine branchee. Les cles
# ne sont PAS stockees en base, elles restent dans l'environnement.
# / One AI model per API key found in .env. No mock model: a phantom one
# would fake a working chain. Keys stay in the environment, never in DB.
MODELES_IA_PAR_CLE_D_ENVIRONNEMENT = [
    {"cle_env": "GOOGLE_API_KEY", "model_choice": "gemini-2.5-flash", "name": "Gemini 2.5 Flash"},
    {"cle_env": "OPENAI_API_KEY", "model_choice": "gpt-4o-mini", "name": "GPT-4o Mini"},
    {"cle_env": "ANTHROPIC_API_KEY", "model_choice": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4"},
]

DESCRIPTION_DE_L_ANALYSEUR_DE_SYNTHESE = (
    "Génère une nouvelle version du texte intégrant le débat structuré "
    "(hypostases + commentaires + statuts). Pondère les passages selon "
    "leur statut de consensus."
)

# --- Les quatre pieces du prompt d'extraction (approche A, validee par
# --- benchmarks : les 30 hypostases classees par famille epistemique).
# / The four extraction prompt pieces (approach A, benchmark-validated).
PIECE_DE_CONTEXTE_DE_L_EXTRACTION = (
    "Tu es Hypostasia, un expert en analyse argumentative et en géométrie des débats.\n"
    "Ta mission est d'extraire l'ossature argumentative du texte en identifiant les hypostases.\n"
    "Tu agis avec neutralité et précision."
)

PIECE_DE_DEFINITIONS_DE_L_EXTRACTION = (
    "# Les 30 hypostases — classées par famille épistémique\n\n"
    "Les hypostases sont les « 30 manières d'être discutable » définies par la géométrie des débats.\n"
    "Avec 2 dispositifs de preuve (formel, empirique) et 3 modes de raisonnement (induction, abduction, déduction), on obtient 6 modes → 30 hypostases.\n\n"
    "## Famille 1 — Non réfuté par induction empirique (ce qu'on observe sans pouvoir généraliser)\n\n"
    "- **classification** : distribuer en classes, en catégories. — *non prouvé par abduction empirique*\n"
    "- **aporie** : difficulté d'ordre rationnel apparemment sans issue. — *non prouvé par déduction empirique*\n"
    "- **approximation** : calcul approché d'une grandeur réelle. — *non prouvé par déduction formelle*\n"
    "- **paradoxe** : proposition à la fois vraie et fausse. — *non prouvé par abduction formelle*\n"
    "- **formalisme** : considération de la forme d'un raisonnement. — *non prouvé par induction formelle*\n\n"
    "## Famille 2 — Non réfuté par déduction empirique (ce qui se produit sans cadre formel)\n\n"
    "- **événement** : ce qui arrive. — *non prouvé par déduction formelle*\n"
    "- **variation** : changement d'un état dans un autre. — *non prouvé par abduction empirique*\n"
    "- **dimension** : grandeur mesurable qui détermine des positions. — *non prouvé par abduction formelle*\n"
    "- **mode** : manière d'être d'un système. — *non prouvé par induction empirique*\n"
    "- **croyance** : certitude ou conviction qui fait croire une chose vraie ou possible. — *non prouvé par induction formelle*\n\n"
    "## Famille 3 — Non réfuté par induction formelle (ce qu'on formalise sans pouvoir vérifier)\n\n"
    "- **invariant** : grandeur, relation ou propriété conservée lors d'une transformation. — *non prouvé par déduction formelle*\n"
    "- **valeur** : mesure d'une grandeur variable. — *non prouvé par abduction empirique*\n"
    "- **structure** : organisation des parties d'un système. — *non prouvé par abduction formelle*\n"
    "- **axiome** : proposition admise au départ d'une théorie. — *non prouvé par induction empirique*\n"
    "- **conjecture** : opinion ou proposition non vérifiée. — *non prouvé par déduction empirique*\n\n"
    "## Famille 4 — Non réfuté par déduction formelle (ce qu'on déduit formellement)\n\n"
    "- **paradigme** : modèle ou exemple. — *non prouvé par abduction empirique*\n"
    "- **objet** : ce sur quoi porte le discours, la pensée, la connaissance. — *non prouvé par abduction formelle*\n"
    "- **principe** : cause a priori d'une connaissance. — *non prouvé par induction formelle*\n"
    "- **domaine** : champ discerné par des limites, bornes, frontières. — *non prouvé par déduction empirique*\n"
    "- **loi** : corrélation. — *non prouvé par induction empirique*\n\n"
    "## Famille 5 — Non réfuté par abduction empirique (ce qu'on constate sans pouvoir l'expliquer)\n\n"
    "- **phénomène** : ce qui se manifeste à la connaissance via les sens. — *non prouvé par déduction formelle*\n"
    "- **variable** : ce qui prend différentes valeurs, dont dépend l'état d'un système. — *non prouvé par abduction formelle*\n"
    "- **variance** : dispersion d'une distribution ou d'un échantillon. — *non prouvé par induction empirique*\n"
    "- **indice** : indicateur numérique ou littéral qui sert à distinguer ou classer. — *non prouvé par déduction empirique*\n"
    "- **donnée** : ce qui est admis, donné, qui sert à découvrir ou à raisonner. — *non prouvé par induction formelle*\n\n"
    "## Famille 6 — Non réfuté par abduction formelle (ce qu'on propose sans pouvoir le confirmer)\n\n"
    "- **méthode** : procédure qui indique ce que l'on doit faire ou comment le faire. — *non prouvé par déduction formelle*\n"
    "- **définition** : détermination, caractérisation du contenu d'un concept. — *non prouvé par abduction empirique*\n"
    "- **hypothèse** : explication ou possibilité d'un événement. — *non prouvé par induction empirique*\n"
    "- **problème** : difficulté à résoudre. — *non prouvé par déduction empirique*\n"
    "- **théorie** : construction intellectuelle explicative, hypothétique et synthétique. — *non prouvé par induction formelle*"
)

PIECE_D_INSTRUCTIONS_DE_L_EXTRACTION = (
    "ANALYSE LE TEXTE SUIVANT.\n\n"
    "Instructions :\n"
    "1. Pour un texte court (< 2000 chars) : identifie 3 à 8 arguments.\n"
    "2. Pour un texte moyen (2000–10000 chars) : identifie 5 à 15 arguments.\n"
    "3. Pour un texte long (> 10000 chars) : identifie 10 à 25 arguments.\n"
    "4. Extrais la citation EXACTE du texte. Ne reformule jamais.\n"
    "5. Synthétise l'idée en une phrase (résumé).\n"
    "6. Associe 1 à 3 hypostases parmi les 30 définies.\n"
    "7. Ignore le bruit : menus, pubs, copyright, URLs.\n"
    "8. Tu es AUTORISÉ à reproduire des citations exactes (fair use académique)."
)

PIECE_DE_FORMAT_DE_L_EXTRACTION = (
    "RÈGLES DE FORMAT :\n\n"
    "{\n"
    '  "hypostase": "citation exacte du texte source",\n'
    '  "hypostase_attributes": {\n'
    '    "resume": "synthèse en une phrase",\n'
    '    "hypostases": "hypothèse, théorie",\n'
    '    "mots_cles": "mot1, mot2"\n'
    "  }\n"
    "}\n\n"
    '- La clé est TOUJOURS "hypostase"\n'
    '- Les hypostases spécifiques sont dans "hypostases" (1 à 3 parmi les 30)\n'
    "- Ne JAMAIS lister les 30. Ne JAMAIS boucler."
)

TEXTE_DE_L_EXEMPLE_FEW_SHOT = (
    "Le débat sur l'intelligence artificielle dans l'éducation\n\n"
    "On distingue trois catégories d'usage de l'IA dans l'enseignement : l'aide à la rédaction, "
    "l'évaluation automatisée et la recherche documentaire. Comment évaluer un travail quand on "
    "ne sait plus qui l'a réellement produit ? C'est une impasse dont personne ne voit la sortie. "
    "Les estimations actuelles suggèrent que 40% des mémoires contiennent des passages générés "
    "par IA, mais ce chiffre reste une approximation grossière. L'IA aide les étudiants à mieux "
    "écrire mais les empêche d'apprendre à écrire : voilà le paradoxe central de cette révolution. "
    "Le cadre logique impose de distinguer clairement l'outil de son usage, sous peine de confondre "
    "le formalisme avec la réalité.\n\n"
    "En mars 2026, une étudiante de la Sorbonne a fait rédiger son mémoire de fin d'études par "
    "une IA, créant un événement sans précédent dans le monde universitaire. Le rapport des "
    "étudiants à l'écriture académique a radicalement changé en moins de deux ans, une variation "
    "que personne n'avait anticipée. Le temps moyen consacré à la rédaction d'un mémoire a "
    "diminué de 60%, une dimension mesurable du phénomène. L'enseignement supérieur fonctionne "
    "désormais selon un mode hybride où l'IA est omniprésente mais rarement encadrée. Beaucoup "
    "d'enseignants croient sincèrement que l'IA finira par remplacer la dissertation comme "
    "exercice pédagogique, une croyance qui influence déjà les programmes.\n\n"
    "Quelle que soit la technologie utilisée, l'esprit critique reste la compétence indispensable "
    "que l'éducation doit transmettre : c'est l'invariant de toute pédagogie. Le taux de plagiat "
    "détecté a augmenté de 300% en un an, une valeur qui alarme les institutions. L'université "
    "s'organise en trois niveaux de contrôle — département, commission pédagogique, conseil "
    "d'administration — une structure qui peine à suivre le rythme du changement. Tout étudiant "
    "a le droit d'utiliser les outils de son époque : cet axiome, rarement contesté, fonde le débat. "
    "On suppose que l'interdiction totale de l'IA serait contre-productive et pousserait les usages "
    "dans la clandestinité, mais cette conjecture n'a pas encore été vérifiée.\n\n"
    "Le modèle finlandais, où l'IA est intégrée dans les cursus depuis 2024, constitue un paradigme "
    "pour les autres pays européens. L'objet de ce débat est la place de l'IA dans l'évaluation "
    "des compétences, pas dans l'enseignement lui-même. Le principe d'autonomie intellectuelle, "
    "qui fonde l'éducation depuis les Lumières, exige que l'étudiant pense par lui-même. Ce débat "
    "concerne exclusivement le domaine de l'enseignement supérieur et ne s'applique pas à "
    "l'enseignement primaire. Plus l'accès à l'IA est facile et gratuit, plus son usage non encadré "
    "augmente : c'est une loi empirique observée dans tous les pays.\n\n"
    "On observe une baisse significative de la qualité argumentative dans les travaux rendus, un "
    "phénomène qui inquiète les jurys de soutenance. Le niveau d'appropriation de l'IA par les "
    "étudiants varie considérablement selon les disciplines, la variable clé étant la nature du "
    "travail demandé. Les résultats de l'enquête montrent une grande variance entre établissements, "
    "certains ayant 10% d'usage et d'autres 80%. Le nombre de citations exactes dans un mémoire "
    "est devenu un indice fiable de travail personnel. Les données de l'enquête PISA 2025 montrent "
    "que les pays qui encadrent l'IA obtiennent de meilleurs résultats que ceux qui l'interdisent.\n\n"
    "La méthode proposée consiste à encadrer l'usage plutôt qu'à l'interdire, en s'inspirant des "
    "chartes universitaires existantes. On entend par « usage acceptable » toute utilisation de "
    "l'IA qui est déclarée, sourcée et vérifiable par l'enseignant : c'est la définition retenue par "
    "la commission. Si l'on autorise l'IA sous conditions strictes, la qualité des travaux pourrait "
    "s'améliorer plutôt que se dégrader, c'est l'hypothèse de travail de cette commission. Le "
    "problème central reste l'absence de règles claires et partagées entre les établissements. La "
    "théorie des communs d'Elinor Ostrom offre un cadre pour penser la gouvernance collective de "
    "l'IA comme ressource partagée par une communauté éducative."
)

EXTRACTIONS_DE_L_EXEMPLE_FEW_SHOT = [
    # Famille 1 : Induction empirique / Family 1: Empirical induction
    ("On distingue trois catégories d'usage de l'IA dans l'enseignement : l'aide à la rédaction, l'évaluation automatisée et la recherche documentaire.", "Trois catégories d'usage de l'IA identifiées.", "classification", "IA, éducation, catégories"),
    ("Comment évaluer un travail quand on ne sait plus qui l'a réellement produit ?", "Impasse sur l'évaluation de l'originalité.", "aporie, problème", "évaluation, authenticité"),
    ("Les estimations actuelles suggèrent que 40% des mémoires contiennent des passages générés par IA, mais ce chiffre reste une approximation grossière.", "Estimation imprécise de l'usage de l'IA dans les mémoires.", "approximation, donnée", "estimation, mémoires, 40%"),
    ("L'IA aide les étudiants à mieux écrire mais les empêche d'apprendre à écrire : voilà le paradoxe central de cette révolution.", "L'IA améliore et dégrade simultanément l'écriture.", "paradoxe, problème", "écriture, apprentissage, paradoxe"),
    ("Le cadre logique impose de distinguer clairement l'outil de son usage, sous peine de confondre le formalisme avec la réalité.", "Nécessité de séparer l'outil de son usage dans le cadre logique.", "formalisme, méthode", "logique, outil, usage"),
    # Famille 2 : Deduction empirique / Family 2: Empirical deduction
    ("En mars 2026, une étudiante de la Sorbonne a fait rédiger son mémoire de fin d'études par une IA, créant un événement sans précédent dans le monde universitaire.", "Un mémoire rédigé par IA crée un précédent à la Sorbonne.", "événement, problème", "Sorbonne, mémoire, IA"),
    ("Le rapport des étudiants à l'écriture académique a radicalement changé en moins de deux ans, une variation que personne n'avait anticipée.", "Changement rapide du rapport à l'écriture académique.", "variation, phénomène", "écriture, changement"),
    ("Le temps moyen consacré à la rédaction d'un mémoire a diminué de 60%, une dimension mesurable du phénomène.", "Le temps de rédaction a baissé de 60%.", "dimension, donnée", "temps, rédaction, 60%"),
    ("L'enseignement supérieur fonctionne désormais selon un mode hybride où l'IA est omniprésente mais rarement encadrée.", "L'enseignement supérieur est en mode hybride non encadré.", "mode, structure", "hybride, enseignement"),
    ("Beaucoup d'enseignants croient sincèrement que l'IA finira par remplacer la dissertation comme exercice pédagogique, une croyance qui influence déjà les programmes.", "Croyance répandue que l'IA remplacera la dissertation.", "croyance, conjecture", "dissertation, remplacement"),
    # Famille 3 : Induction formelle / Family 3: Formal induction
    ("Quelle que soit la technologie utilisée, l'esprit critique reste la compétence indispensable que l'éducation doit transmettre : c'est l'invariant de toute pédagogie.", "L'esprit critique est l'invariant de toute pédagogie.", "invariant, principe", "esprit critique, pédagogie"),
    ("Le taux de plagiat détecté a augmenté de 300% en un an, une valeur qui alarme les institutions.", "Le plagiat a triplé en un an.", "valeur, donnée", "plagiat, 300%"),
    ("L'université s'organise en trois niveaux de contrôle — département, commission pédagogique, conseil d'administration — une structure qui peine à suivre le rythme du changement.", "La structure universitaire à 3 niveaux est trop lente.", "structure, problème", "université, contrôle, niveaux"),
    ("Tout étudiant a le droit d'utiliser les outils de son époque : cet axiome, rarement contesté, fonde le débat.", "Le droit aux outils de son époque est un axiome du débat.", "axiome, principe", "droit, outils, époque"),
    ("On suppose que l'interdiction totale de l'IA serait contre-productive et pousserait les usages dans la clandestinité, mais cette conjecture n'a pas encore été vérifiée.", "L'interdiction serait contre-productive — hypothèse non vérifiée.", "conjecture, hypothèse", "interdiction, clandestinité"),
    # Famille 4 : Deduction formelle / Family 4: Formal deduction
    ("Le modèle finlandais, où l'IA est intégrée dans les cursus depuis 2024, constitue un paradigme pour les autres pays européens.", "La Finlande est un modèle d'intégration de l'IA.", "paradigme, méthode", "Finlande, modèle, intégration"),
    ("L'objet de ce débat est la place de l'IA dans l'évaluation des compétences, pas dans l'enseignement lui-même.", "Le débat porte sur l'évaluation, pas l'enseignement.", "objet, domaine", "évaluation, compétences"),
    ("Le principe d'autonomie intellectuelle, qui fonde l'éducation depuis les Lumières, exige que l'étudiant pense par lui-même.", "L'autonomie intellectuelle est un principe fondateur.", "principe, axiome", "autonomie, Lumières"),
    ("Ce débat concerne exclusivement le domaine de l'enseignement supérieur et ne s'applique pas à l'enseignement primaire.", "Le périmètre est limité à l'enseignement supérieur.", "domaine, classification", "supérieur, primaire"),
    ("Plus l'accès à l'IA est facile et gratuit, plus son usage non encadré augmente : c'est une loi empirique observée dans tous les pays.", "Corrélation entre accessibilité et usage non encadré.", "loi, phénomène", "accès, corrélation"),
    # Famille 5 : Abduction empirique / Family 5: Empirical abduction
    ("On observe une baisse significative de la qualité argumentative dans les travaux rendus, un phénomène qui inquiète les jurys de soutenance.", "Baisse observée de la qualité argumentative.", "phénomène, problème", "qualité, argumentation"),
    ("Le niveau d'appropriation de l'IA par les étudiants varie considérablement selon les disciplines, la variable clé étant la nature du travail demandé.", "L'appropriation varie selon la discipline.", "variable, dimension", "disciplines, appropriation"),
    ("Les résultats de l'enquête montrent une grande variance entre établissements, certains ayant 10% d'usage et d'autres 80%.", "Grande disparité d'usage entre établissements.", "variance, donnée", "établissements, disparité"),
    ("Le nombre de citations exactes dans un mémoire est devenu un indice fiable de travail personnel.", "Les citations exactes sont un indicateur de travail personnel.", "indice, méthode", "citations, indicateur"),
    ("Les données de l'enquête PISA 2025 montrent que les pays qui encadrent l'IA obtiennent de meilleurs résultats que ceux qui l'interdisent.", "PISA 2025 : encadrer l'IA donne de meilleurs résultats.", "donnée, loi", "PISA, résultats, encadrement"),
    # Famille 6 : Abduction formelle / Family 6: Formal abduction
    ("La méthode proposée consiste à encadrer l'usage plutôt qu'à l'interdire, en s'inspirant des chartes universitaires existantes.", "Encadrer plutôt qu'interdire.", "méthode, principe", "encadrement, chartes"),
    ("On entend par « usage acceptable » toute utilisation de l'IA qui est déclarée, sourcée et vérifiable par l'enseignant : c'est la définition retenue par la commission.", "Définition de l'usage acceptable : déclaré, sourcé, vérifiable.", "définition, méthode", "usage acceptable, définition"),
    ("Si l'on autorise l'IA sous conditions strictes, la qualité des travaux pourrait s'améliorer plutôt que se dégrader, c'est l'hypothèse de travail de cette commission.", "Hypothèse : autoriser sous conditions améliorerait la qualité.", "hypothèse, conjecture", "conditions, qualité"),
    ("Le problème central reste l'absence de règles claires et partagées entre les établissements.", "Absence de règles claires entre établissements.", "problème, structure", "règles, établissements"),
    ("La théorie des communs d'Elinor Ostrom offre un cadre pour penser la gouvernance collective de l'IA comme ressource partagée par une communauté éducative.", "La théorie des communs comme cadre de gouvernance de l'IA.", "théorie, paradigme", "Ostrom, communs, gouvernance"),
]

PIECE_DE_CONTEXTE_DE_LA_SYNTHESE = (
    "Tu es un rédacteur expert en synthèse délibérative. "
    "Ta mission est de produire une nouvelle version d'un texte "
    "qui intègre les résultats d'un débat structuré."
)

PIECE_DE_PONDERATION_DE_LA_SYNTHESE = (
    "Règles de pondération par statut de débat :\n\n"
    "- CONSENSUEL : intégrer pleinement, ces points font l'objet d'un accord du groupe.\n"
    "- DISCUTABLE : mentionner avec nuance, le débat n'a pas encore eu lieu.\n"
    "- DISCUTÉ : présenter les différents points de vue exprimés dans les commentaires.\n"
    "- CONTROVERSÉ : expliciter la controverse sans trancher, citer les arguments des deux côtés.\n"
    "- Les extractions NON PERTINENTES sont exclues du prompt, ignore-les.\n\n"
    "Le texte produit doit être :\n"
    "1. Une version autonome et lisible (pas un résumé du débat)\n"
    "2. Rédigé dans un style cohérent avec le texte original\n"
    "3. Fidèle aux sources : chaque affirmation doit pouvoir être reliée à une extraction\n"
    "4. Équilibré : les passages controversés ne doivent pas être supprimés mais contextualisés"
)

PIECE_DE_CONSIGNE_DE_LA_SYNTHESE = (
    "Produis la synthèse délibérative de ce débat en intégrant les pondérations "
    "par statut définies dans tes instructions. Le texte produit doit être une "
    "nouvelle version autonome et lisible du document."
)



def creer_les_modeles_ia_et_les_analyseurs():
    """
    Cree les modeles IA declares dans le .env et les deux analyseurs.
    / Creates the AI models declared in .env and both analyzers.

    LOCALISATION : front/services/fixtures_analyseurs.py

    Idempotent : deux executions ne creent rien deux fois. Tout passe par
    `get_or_create` sur le nom, et les pieces de prompt comme les exemples
    ne sont poses que s'il n'y en a aucun. Un analyseur deja garni par
    quelqu'un appartient a ce quelqu'un — on n'ecrit jamais par-dessus.
    / Idempotent: get_or_create on the name, and prompt pieces or examples
    are only added when there are none. An already-furnished analyzer
    belongs to whoever furnished it; we never write over it.

    :return: dict de rapport, a mettre en mots par la commande appelante
    """
    # --- 1. Les modeles IA, un par cle API presente dans l'environnement ---
    # / --- 1. AI models, one per API key present in the environment ---
    modeles_ia_crees = []
    premier_modele_disponible = None
    for definition_du_modele in MODELES_IA_PAR_CLE_D_ENVIRONNEMENT:
        cle_api_presente = bool(os.environ.get(definition_du_modele["cle_env"]))
        if not cle_api_presente:
            continue
        modele_ia, modele_ia_cree = AIModel.objects.get_or_create(
            model_choice=definition_du_modele["model_choice"],
            defaults={"name": definition_du_modele["name"], "is_active": True},
        )
        if modele_ia_cree:
            modeles_ia_crees.append(
                (definition_du_modele["name"], definition_du_modele["cle_env"]),
            )
        if not premier_modele_disponible:
            premier_modele_disponible = modele_ia

    # Aucune cle, et aucun modele actif herite d'une execution precedente :
    # l'IA restera eteinte, et l'appelant doit le dire a voix haute.
    # / No key and no active model inherited: AI stays off, say it aloud.
    aucune_cle_api_detectee = (
        premier_modele_disponible is None
        and not AIModel.objects.filter(is_active=True).exists()
    )

    # On n'active la configuration que si elle n'a pas deja un modele :
    # un choix pose a la main dans l'interface ne doit pas etre ecrase par
    # une simple reinstallation.
    # / Only activate when no model is set: a hand-picked one must survive
    # a reinstall.
    configuration = Configuration.get_solo()
    configuration_ia_activee = False
    if not configuration.ai_model and premier_modele_disponible:
        configuration.ai_model = premier_modele_disponible
        configuration.ai_active = True
        configuration.save()
        configuration_ia_activee = True

    # --- 2. L'analyseur d'extraction ---
    # / --- 2. The extraction analyzer ---
    analyseur_extraction, analyseur_extraction_cree = AnalyseurSyntaxique.objects.get_or_create(
        name=NOM_DE_L_ANALYSEUR_D_EXTRACTION,
        defaults={
            "type_analyseur": "analyser",
            "is_active": True,
            "inclure_extractions": False,
            "inclure_texte_original": False,
            "est_par_defaut": True,
        },
    )
    pieces_de_prompt_creees = _garnir_le_prompt_d_extraction(analyseur_extraction)
    exemples_few_shot_crees, extractions_d_exemple_creees = _garnir_l_exemple_few_shot(
        analyseur_extraction,
    )

    # --- 3. L'analyseur de synthese ---
    # / --- 3. The synthesis analyzer ---
    analyseur_synthese, analyseur_synthese_cree = AnalyseurSyntaxique.objects.get_or_create(
        name=NOM_DE_L_ANALYSEUR_DE_SYNTHESE,
        defaults={
            "type_analyseur": "synthetiser",
            "is_active": True,
            "inclure_extractions": True,
            "inclure_texte_original": True,
            "est_par_defaut": True,
            "description": DESCRIPTION_DE_L_ANALYSEUR_DE_SYNTHESE,
        },
    )
    pieces_de_synthese_creees = _garnir_le_prompt_de_synthese(analyseur_synthese)

    return {
        "modeles_ia_crees": modeles_ia_crees,
        "aucune_cle_api_detectee": aucune_cle_api_detectee,
        "configuration_ia_activee": configuration_ia_activee,
        "modele_ia_de_la_configuration": premier_modele_disponible,
        "analyseur_extraction": analyseur_extraction,
        "analyseur_extraction_cree": analyseur_extraction_cree,
        "pieces_de_prompt_creees": pieces_de_prompt_creees,
        "exemples_few_shot_crees": exemples_few_shot_crees,
        "extractions_d_exemple_creees": extractions_d_exemple_creees,
        "analyseur_synthese": analyseur_synthese,
        "analyseur_synthese_cree": analyseur_synthese_cree,
        "pieces_de_synthese_creees": pieces_de_synthese_creees,
    }


def _garnir_le_prompt_d_extraction(analyseur_extraction):
    """
    Pose les quatre pieces du prompt, si l'analyseur n'en a aucune.
    / Adds the four prompt pieces, if the analyzer has none.

    LOCALISATION : front/services/fixtures_analyseurs.py

    Le garde-fou porte sur « aucune piece », pas sur « analyseur cree a
    l'instant » : un analyseur homonyme cree a la main, reste vide, doit
    pouvoir etre complete. Des qu'il y a une piece, on ne touche plus a
    rien — l'ordre et le contenu d'un prompt sont un travail d'auteur.
    / The guard is "no piece at all", not "just created": a hand-made
    empty homonym can still be furnished. As soon as one piece exists we
    stop: a prompt's content and order are somebody's authored work.

    :return: nombre de pieces creees (0 ou 4)
    """
    if analyseur_extraction.pieces.exists():
        return 0

    pieces_a_creer = [
        (0, "context", PIECE_DE_CONTEXTE_DE_L_EXTRACTION),
        (1, "definition", PIECE_DE_DEFINITIONS_DE_L_EXTRACTION),
        (2, "instruction", PIECE_D_INSTRUCTIONS_DE_L_EXTRACTION),
        (3, "format", PIECE_DE_FORMAT_DE_L_EXTRACTION),
    ]
    for ordre_de_la_piece, role_de_la_piece, contenu_de_la_piece in pieces_a_creer:
        PromptPiece.objects.create(
            analyseur=analyseur_extraction,
            order=ordre_de_la_piece,
            role=role_de_la_piece,
            content=contenu_de_la_piece,
        )
    return len(pieces_a_creer)


def _garnir_l_exemple_few_shot(analyseur_extraction):
    """
    Pose l'exemple few-shot et ses 30 extractions, s'il n'y en a aucun.
    / Adds the few-shot example and its 30 extractions, if there is none.

    LOCALISATION : front/services/fixtures_analyseurs.py

    C'EST CET EXEMPLE QUI REND L'ANALYSEUR UTILISABLE.

    `verifier_utilisabilite_analyseur` ecarte des selecteurs tout
    analyseur d'extraction sans exemple complet — un texte source rempli
    ET une extraction avec classe et texte remplis. Sans lui, LangExtract
    n'envoie aucun cadre au LLM, le LLM invente son format, et les
    extractions sont perdues en silence (le bug « exemples=0 »).
    L'analyseur existerait en base sans jamais apparaitre a l'ecran.
    / This example is what makes the analyzer usable: without a complete
    one it is filtered out of the selectors, LangExtract frames nothing,
    and extractions are silently lost.

    :return: tuple (nombre d'exemples crees, nombre d'extractions creees)
    """
    if analyseur_extraction.examples.exists():
        return 0, 0

    exemple_few_shot = AnalyseurExample.objects.create(
        analyseur=analyseur_extraction,
        name=NOM_DE_L_EXEMPLE_FEW_SHOT,
        example_text=TEXTE_DE_L_EXEMPLE_FEW_SHOT,
    )

    # Une extraction par hypostase, chacune portant ses trois attributs
    # (resume, hypostases, mots_cles) : c'est le format que le LLM doit
    # imiter. / One extraction per hypostase, each with its three
    # attributes: this is the shape the LLM has to imitate.
    for numero_de_l_extraction, definition in enumerate(
        EXTRACTIONS_DE_L_EXEMPLE_FEW_SHOT,
    ):
        texte_cite, resume, hypostases, mots_cles = definition
        extraction_d_exemple = ExampleExtraction.objects.create(
            example=exemple_few_shot,
            order=numero_de_l_extraction,
            extraction_class="hypostase",
            extraction_text=texte_cite,
        )
        ExtractionAttribute.objects.create(
            extraction=extraction_d_exemple, key="resume", value=resume, order=0,
        )
        ExtractionAttribute.objects.create(
            extraction=extraction_d_exemple, key="hypostases", value=hypostases, order=1,
        )
        ExtractionAttribute.objects.create(
            extraction=extraction_d_exemple, key="mots_cles", value=mots_cles, order=2,
        )

    return 1, len(EXTRACTIONS_DE_L_EXEMPLE_FEW_SHOT)


def _garnir_le_prompt_de_synthese(analyseur_synthese):
    """
    Pose les trois pieces du prompt de synthese, s'il n'y en a aucune.
    / Adds the three synthesis prompt pieces, if there are none.

    LOCALISATION : front/services/fixtures_analyseurs.py

    Un analyseur de synthese ne s'appuie sur aucun exemple few-shot :
    il travaille sur les extractions et le texte deja en base, pas sur un
    modele de reponse. Seul son prompt le definit.
    / A synthesis analyzer relies on no few-shot example: it works from
    the extractions and text already stored. Its prompt alone defines it.

    :return: nombre de pieces creees (0 ou 3)
    """
    if analyseur_synthese.pieces.exists():
        return 0

    pieces_a_creer = [
        (0, "context", PIECE_DE_CONTEXTE_DE_LA_SYNTHESE),
        (1, "instruction", PIECE_DE_PONDERATION_DE_LA_SYNTHESE),
        (2, "instruction", PIECE_DE_CONSIGNE_DE_LA_SYNTHESE),
    ]
    for ordre_de_la_piece, role_de_la_piece, contenu_de_la_piece in pieces_a_creer:
        PromptPiece.objects.create(
            analyseur=analyseur_synthese,
            order=ordre_de_la_piece,
            role=role_de_la_piece,
            content=contenu_de_la_piece,
        )
    return len(pieces_a_creer)
