"""
Charge les fixtures de demonstration : users + pages Wikipedia + debat fictif
dans un dossier unique "Demonstration" avec commentaires et statuts varies.
/ Load demo fixtures: users + Wikipedia pages + fictional debate
in a single "Demonstration" folder with comments and varied statuses.

LOCALISATION : front/management/commands/charger_fixtures_demo.py

Usage :
    uv run python manage.py charger_fixtures_demo
    uv run python manage.py charger_fixtures_demo --reset  (supprime et recree)
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from core.models import AIModel, Configuration, Dossier, DossierPartage, Page, VisibiliteDossier
from hypostasis_extractor.models import (
    AnalyseurExample,
    AnalyseurSyntaxique,
    CommentaireExtraction,
    ExampleExtraction,
    ExtractionAttribute,
    ExtractedEntity,
    ExtractionJob,
    PromptPiece,
)


# =============================================================================
# Textes Wikipedia des 3 auteurs (extraits nettoyés)
# / Wikipedia texts for the 3 authors (cleaned excerpts)
# =============================================================================

TEXTE_OSTROM = """Elinor Ostrom, née le 7 août 1933 à Los Angeles et morte le 12 juin 2012 à Bloomington, est une politologue et économiste américaine. En octobre 2009, elle est la première femme à recevoir le « prix Nobel d'économie », avec Oliver Williamson, pour son analyse de la gouvernance économique, et en particulier, des biens communs.

Ses travaux portent principalement sur la théorie de l'action collective et la gestion des biens communs ainsi que des biens publics, aussi bien matériels qu'immatériels. Elinor Ostrom a surtout travaillé sur la notion de dilemme social, c'est-à-dire les cas où la quête de l'intérêt personnel conduit à un résultat plus mauvais pour tous que celui résultant d'un autre type de comportement. Elle a surtout étudié la question du dilemme social dans le domaine des ressources communes : ressources hydrauliques, forêts, pêcheries, etc.

Avant ses travaux, dans ces cas, seulement deux solutions étaient envisagées : l'État-Léviathan, qui impose le bien public, ou alors une définition stricte des droits de propriété individuelle. L'œuvre d'Ostrom tend à montrer qu'il existe un autre type de solutions, l'autogouvernement, dont elle définit les huit principes caractéristiques nécessaires à sa pérennité, ainsi que les deux éléments clés de son émergence : la réciprocité et la confiance.

Ostrom est principalement connue pour ses travaux portant sur la gestion collective des biens communs. Dans son livre le plus connu, Governing the Commons, la chercheuse critique les fondements de l'analyse politique appliquée alors à de nombreuses ressources naturelles. Elle expose également les expériences tant fructueuses qu'infructueuses de gouvernance des biens collectifs afin de construire à partir de l'expérience cumulée de meilleurs outils intellectuels destinés à tracer les capacités et les limites des collectivités autonomes à réguler de nombreux types de ressources.

L'approche de Garrett Hardin, exposée dans l'article « La Tragédie des biens communs » paru dans Science en 1968, soutient que la rationalité économique doit a priori pousser des individus qui se partagent un bien en commun à le surexploiter. Puisque l'utilité et le profit sont individuels, alors que le coût est supporté par tous, son usage mène obligatoirement à une surexploitation de la ressource. Pour la plupart des économistes, la solution à cette tragédie passe soit par la création de droits individuels de propriété, soit par la gestion des biens communs par la puissance publique. Ostrom, au contraire, soutient qu'il n'y a pas un seul problème mais que chaque fois il existe de nombreuses solutions face à de nombreux problèmes différents.

Dans sa recherche, Ostrom identifie huit principes de conception, ou conditions essentielles au succès de ces institutions :

1. Définition claire de l'objet de la communauté et de ses membres.
2. Cohérence entre les règles relatives à la ressource commune et la nature de celle-ci.
3. Participation des utilisateurs à la modification des règles opérationnelles concernant la ressource commune.
4. Responsabilité des surveillants de l'exploitation de la ressource commune devant les exploitants.
5. Graduation des sanctions pour non-respect des règles d'exploitation.
6. Accès rapide à des instances locales de résolution de conflits.
7. La reconnaissance de l'auto-organisation par les autorités gouvernementales externes.
8. Organisation à plusieurs niveaux des activités d'appropriation, de surveillance, de mise en application des lois, de résolution des conflits et de gouvernance.

Le capital social pour Ostrom repose sur la confiance et la réciprocité, les réseaux et la participation civile, ainsi que sur le respect des règles et institutions formelles et informelles de l'action collective. La réciprocité est chez elle un élément clé pour dépasser et résoudre les dilemmes sociaux.

Ces principes de gouvernance des communs trouvent aujourd'hui un écho particulier dans le domaine numérique. Les logiciels libres, les bases de connaissances collaboratives comme Wikipédia, et les coopératives de données constituent des exemples contemporains de ressources communes gérées selon des principes proches de ceux identifiés par Ostrom. La question de la gouvernance de l'intelligence artificielle comme commun numérique — avec des règles claires, une participation des usagers et des mécanismes de contrôle gradués — s'inscrit directement dans la lignée de ses travaux."""

TEXTE_ALEXANDRE = """Laurent Alexandre, né le 10 juin 1960 à Paris, est un haut fonctionnaire, chirurgien-urologue de formation, entrepreneur, chroniqueur, écrivain et militant politique français. Il a co-fondé le site Doctissimo en 1999, et préside depuis 2009 DNAVision, une société belge de séquençage d'ADN. Souvent présenté comme futurologue, il intervient régulièrement dans les médias. Ses positions sur des sujets clivants suscitent débats et polémiques.

Laurent Alexandre est l'un des principaux représentants du mouvement transhumaniste en France, bien qu'il affirme ne pas en être un adepte et accréditer seulement le diagnostic technologique des transhumanistes. Il est un adepte du philosophe Nick Bostrom, fondateur de Humanity+, dont il recommande le livre Superintelligence. Il redoute le risque de « neurogoulag » et de « neurototalitarisme » d'un gouvernement totalitaire pouvant se servir des technologies NBIC pour asservir en modifiant le fonctionnement cérébral.

Laurent Alexandre considère que le développement de l'intelligence artificielle va entraîner progressivement la disparition de centaines de milliers d'emplois. Il a notamment prédit en 2017 que l'avis d'un ordinateur serait, vers 2027, plus sûr que celui d'un radiologue. Dans un ouvrage de 2019 coécrit avec Jean-François Copé, il défend l'idée que le développement de l'intelligence artificielle menace la démocratie, et dénonce la nullité technologique des dirigeants politiques. Il prévoit la survenue de la singularité technologique, pas avant 2100.

Devant cette perspective, il s'oppose à l'instauration d'un revenu universel et plaide pour une éducation visant à permettre à nos cerveaux biologiques d'être le plus complémentaires possible de l'intelligence artificielle. Son essai La Mort de la mort (2011) jongle entre les découvertes génétiques et ses propres déductions pour démontrer une idée : l'homme de l'an 2000 vivra deux fois plus longtemps que ses parents. Il affirme notamment que l'homme qui vivra mille ans est déjà né, prévoit la disparition du cancer dans une quinzaine d'années, et considère que la science donnera à l'homme le pouvoir d'un dieu.

Le biologiste Jacques Testart émet de fortes réserves sur ces prévisions fondées sur la loi de Moore, qu'il qualifie d'énorme confusion. Laurent Alexandre se dit profondément darwinien, convaincu que la nature élimine les plus faibles, et prône la sélection génétique. Il défend régulièrement l'idée que le quotient intellectuel est déterminé de manière prépondérante par l'ADN, ce qui est contesté par certains chercheurs spécialistes.

Il estime que seul le développement technologique peut décarboner l'économie mondiale, que stopper le développement économique entraînerait guerres et famines. Il s'oppose de manière virulente aux écologistes et aux collapsologues.

Luc Julia, vice-président innovation de Samsung Monde, affirme que Laurent Alexandre dit n'importe quoi sur ce sujet, tout en changeant d'avis tous les trois mois. Selon la sociologue Gaïa Lassaube, l'ascension rapide de Laurent Alexandre au sommet du vedettariat culturel français s'explique moins par ses connaissances scientifiques que par sa maîtrise des relais de diffusion, en marge des circuits académiques.

En 2018, le site Acrimed décrit Laurent Alexandre comme un militant politique agissant sous couvert de vulgarisation scientifique au détriment de l'honnêteté intellectuelle et de la rigueur scientifique. Selon Arrêt sur images, ce sont surtout les sujets relatifs à l'écologie et à l'urgence climatique qui ont semblé radicaliser l'homme d'affaires.

Parmi ses ouvrages : La Mort de la mort (2011), La Guerre des intelligences (2017), L'IA va-t-elle aussi tuer la démocratie ? (2019), La guerre des intelligences à l'heure de ChatGPT (2023), ChatGPT va nous rendre immortels (2024)."""

TEXTE_SADIN = """Éric Sadin, né le 3 septembre 1973, est un écrivain et philosophe français, principalement connu pour ses écrits technocritiques.

Éric Sadin explore à partir de la fin des années 1990 certaines des mutations décisives du monde numérique ainsi que leurs implications politiques et civilisationnelles. Le déclic se produit en 1998, lorsqu'il acquiert pour la première fois une connexion internet et un téléphone portable. Constatant la facilité de communication et de circulation des informations entre individus malgré la distance, il développe l'idée de l'émergence d'un nouveau moment de l'histoire de l'humanité, tant dans nos comportements individuels que collectifs.

Il commence à se faire connaître en publiant en 2009 Surveillance globale : enquête sur les nouvelles formes de contrôle. Selon Le Monde, ce livre fait d'Éric Sadin l'un des rares penseurs à s'interroger sur les limites de la révolution numérique en cours et à en proposer une analyse multidimensionnelle — historique, philosophique, économique, idéologique et sociologique. Éric Sadin met en avant les aspects négatifs des nouvelles technologies, affirmant que la société de l'information est aussi une société de surveillance au service d'intérêts économiques.

Il poursuit ses thèses dans L'Humanité augmentée. L'administration numérique du monde (2013), puis dans La Silicolonisation du monde. L'irrésistible expansion du libéralisme numérique (2016). Le terme « silicolonisation » — forgé par Sadin — désigne l'expansion d'un modèle économique et idéologique issu de la Silicon Valley qui colonise progressivement toutes les sphères de l'existence.

En 2018, il publie L'Intelligence artificielle ou l'enjeu du siècle, où il estime que l'IA est une révolution à laquelle il faut résister, tant elle engendre une mise au ban progressive de l'humain. Il donne des exemples : le remplacement du diagnostic médical humain par l'IA, l'examen automatisé des conditions de délivrance d'un prêt bancaire, l'utilisation de robots numériques pour le recrutement. Il alerte sur la marginalisation de l'évaluation humaine face à la montée de l'automatisation, et va plus loin, y voyant une possibilité d'effacement du politique et d'asservissement aux analyses produites par les machines.

En 2022, dans L'Ère de l'individu tyran, il affirme que les réseaux sociaux ont participé massivement à une exacerbation de l'individualisme et une atomisation des sociétés. La subjectivité personnelle prendrait le pas sur les références universelles, et l'usage des réseaux sociaux conduirait à des comportements de ressentiment et de colère.

En février 2025, alors que se déroule à Paris le Sommet pour l'action sur l'intelligence artificielle, il organise un contre-sommet avec le journaliste Éric Barbier. Cette contre-manifestation, intitulée Pour un humanisme de notre temps, se veut orientée contre les discours qui nous promettent monts et merveilles avec l'IA. Elle a deux objectifs : faire entendre des témoignages sur des professions déjà impactées (écrivains, enseignants, journalistes, traducteurs, doubleurs), et créer une mobilisation à l'image de la grève des scénaristes américains en 2023.

Éric Sadin déclare que l'usage de l'IA peut relever d'un renoncement à l'usage de nos facultés les plus fondamentales. En octobre 2025, il poursuit son analyse dans Le Désert de nous-mêmes, estimant que l'intelligence artificielle générative représente un tournant dans l'histoire de l'humanité. Sadin affirme que face à l'ouragan des IA génératives, il nous reste deux ou trois ans pour agir, sinon il sera trop tard pour les réguler.

Libération décrit le philosophe comme vu par les uns comme un prophète de malheur et par les autres comme un lanceur d'alerte extralucide. La question posée est vertigineuse : que va-t-il rester à l'humanité quand les assistés numériques que nous sommes déléguerons totalement l'apprentissage, la création et la formation du savoir à des machines ?

Parmi ses ouvrages essentiels : Surveillance globale (2009), La Vie algorithmique (2015), La Silicolonisation du monde (2016), L'Intelligence artificielle ou l'enjeu du siècle (2018), L'Ère de l'individu tyran (2020), Faire sécession (2021), La Vie spectrale (2023), Le Désert de nous-mêmes (2025)."""


# =============================================================================
# Debat fictif : 3 locuteurs, 12 segments
# / Fictional debate: 3 speakers, 12 segments
# =============================================================================

TEXTE_DEBAT = """L'intelligence artificielle est la révolution la plus importante depuis l'invention de l'écriture. Les pays qui n'investissent pas massivement dans l'IA seront relégués au rang de puissances de second ordre. La France doit mettre des milliards sur la table, former ses ingénieurs, et cesser de pleurnicher sur les risques.

Voilà exactement le discours qui m'inquiète. On nous présente l'IA comme une fatalité historique, alors qu'il s'agit d'un choix politique. Ce que tu appelles progrès, Laurent, c'est la silicolonisation du monde : des entreprises privées qui imposent leur vision utilitariste à des sociétés entières, en transformant chaque geste humain en donnée exploitable.

Je crois qu'il y a une troisième voie que vous négligez tous les deux. L'IA n'est ni une fatalité à embrasser aveuglément, ni un monstre à combattre. C'est une ressource qui peut être gouvernée comme un commun numérique, à condition que les communautés d'usagers participent à l'élaboration des règles qui encadrent son usage.

Un commun numérique, c'est charmant en théorie, mais dans la réalité, c'est la guerre des intelligences. Si nous ne développons pas des IA plus puissantes que celles de la Chine ou des États-Unis, nous serons colonisés technologiquement. L'augmentation cognitive n'est pas une option, c'est une nécessité de survie civilisationnelle.

Tu vois, c'est précisément cette rhétorique guerrière qui est toxique. L'IA ne se contente pas d'augmenter nos capacités : elle prétend gouverner nos comportements. Les algorithmes de recommandation décident ce que nous lisons, ce que nous achetons, ce que nous pensons. C'est un gouvernement non élu qui s'installe dans nos vies sans qu'on ait jamais voté pour lui.

Eric a raison de pointer le problème de la gouvernance, mais sa réponse me semble trop binaire. Mes recherches sur les communs montrent que ni le marché pur ni l'État centralisé ne sont les seules options. Des communautés peuvent s'auto-organiser pour gérer des ressources partagées, y compris des modèles d'IA ouverts, avec des règles adaptées à leur contexte local.

Le problème, Elinor, c'est que l'IA évolue à une vitesse qui dépasse nos capacités d'auto-organisation. Dans dix ans, les machines auront une intelligence supérieure à la nôtre. Si nous n'avons pas préparé nos sociétés par l'éducation et l'investissement massif, nous assisterons à une bifurcation entre une élite cognitive augmentée et le reste de l'humanité laissé pour compte.

Et c'est justement ce que je dénonce : cette course en avant permanente, cette fuite technologique qui nous empêche de penser. Nous avons besoin d'une insurrection civique contre la délégation du jugement aux machines. L'humain n'est pas un profil statistique à optimiser. Il est temps de repolitiser radicalement le débat sur la technologie.

Je partage ton inquiétude sur la concentration du pouvoir, Eric, mais je refuse le fatalisme. Regardez les logiciels libres, Wikipédia, les coopératives de données : ce sont des preuves vivantes que des communautés peuvent gouverner des ressources numériques de manière démocratique. L'enjeu n'est pas de refuser l'IA, mais de construire des institutions polycentriques qui empêchent sa capture par quelques acteurs privés.

Vous êtes des rêveurs sympathiques, mais pendant que vous débattez de gouvernance et de communs, les laboratoires chinois et américains entraînent des modèles de plus en plus puissants. Le transhumanisme n'est pas une idéologie, c'est la description lucide de ce qui arrive. La convergence des nanotechnologies, de la biologie et de l'informatique va transformer l'espèce humaine, que cela nous plaise ou non.

Et voilà le piège : transformer une idéologie en prophétie auto-réalisatrice. Non, Laurent, le transhumanisme n'est pas une description neutre du réel. C'est un projet politique porté par des intérêts économiques colossaux. Et c'est notre responsabilité collective de dire non à cette vision du monde qui réduit l'humanité à un problème d'optimisation.

Pour conclure, je dirais que l'IA est un outil d'empuissancement formidable si — et seulement si — nous construisons les institutions capables de la gouverner collectivement. Ni la course technologique débridée de Laurent, ni le refus radical d'Eric ne suffisent. Il faut des règles claires, une participation des usagers aux décisions, et des mécanismes de contrôle gradués. C'est possible, et c'est notre responsabilité de le faire."""

# Segments du debat avec locuteurs et timestamps
# / Debate segments with speakers and timestamps
SEGMENTS_DEBAT = [
    {"speaker": "Laurent", "start": 0.0, "end": 27.5},
    {"speaker": "Eric", "start": 28.0, "end": 54.5},
    {"speaker": "Elinor", "start": 55.0, "end": 79.5},
    {"speaker": "Laurent", "start": 80.0, "end": 107.5},
    {"speaker": "Eric", "start": 108.0, "end": 134.5},
    {"speaker": "Elinor", "start": 135.0, "end": 161.5},
    {"speaker": "Laurent", "start": 162.0, "end": 189.5},
    {"speaker": "Eric", "start": 190.0, "end": 217.5},
    {"speaker": "Elinor", "start": 218.0, "end": 244.5},
    {"speaker": "Laurent", "start": 245.0, "end": 271.5},
    {"speaker": "Eric", "start": 272.0, "end": 298.5},
    {"speaker": "Elinor", "start": 298.5, "end": 325.0},
]

# Couleurs des locuteurs pour le HTML du debat
# / Speaker colors for debate HTML
COULEURS_LOCUTEURS = {
    "Laurent": {"fond": "rgba(239, 68, 68, 0.06)", "bordure": "#ef4444"},
    "Eric": {"fond": "rgba(59, 130, 246, 0.06)", "bordure": "#3b82f6"},
    "Elinor": {"fond": "rgba(16, 185, 129, 0.06)", "bordure": "#10b981"},
}


# =============================================================================
# Synthese du debat V2 — texte restitue apres deliberation (PHASE-27b)
# Le texte reprend la structure du debat V1 mais integre les points
# consensuels, reformule les passages controverses, et ajoute une conclusion.
# / Debate synthesis V2 — restituted text after deliberation (PHASE-27b)
# =============================================================================

TEXTE_SYNTHESE_DEBAT_V2 = """L'intelligence artificielle constitue une transformation majeure de nos sociétés, comparable par son ampleur aux grandes révolutions technologiques. Les pays qui n'anticipent pas cette transition risquent d'être marginalisés. Toutefois, cette transformation ne doit pas être présentée comme une fatalité : elle relève de choix politiques collectifs.

Le débat opposant accélération technologique et refus radical ne couvre pas l'ensemble des positions possibles. Une troisième voie existe : l'IA peut être gouvernée comme un commun numérique, à condition que les communautés d'usagers participent à l'élaboration des règles qui encadrent son usage. Cette approche s'inscrit dans la lignée des travaux d'Elinor Ostrom sur la gouvernance polycentrique des ressources partagées.

Les algorithmes de recommandation posent un problème démocratique réel : ils influencent ce que nous lisons, achetons et pensons, sans mandat démocratique. La question de la gouvernance de ces systèmes ne peut être éludée. Ni le marché pur ni l'État centralisé ne constituent des réponses satisfaisantes. Des communautés peuvent s'auto-organiser pour gérer des ressources partagées, y compris des modèles d'IA ouverts, avec des règles adaptées à leur contexte local.

La vitesse d'évolution de l'IA pose un défi d'adaptation pour nos institutions. L'éducation et l'investissement dans la complémentarité humain-machine sont nécessaires, mais ils ne suffisent pas sans un cadre de gouvernance démocratique. Le risque d'une bifurcation entre une élite cognitive augmentée et le reste de la population doit être anticipé par des politiques publiques inclusives.

Les logiciels libres, Wikipédia et les coopératives de données constituent des preuves vivantes que des communautés peuvent gouverner des ressources numériques de manière démocratique. L'enjeu central n'est pas de refuser l'IA ni de l'embrasser aveuglément, mais de construire des institutions polycentriques qui empêchent sa capture par quelques acteurs privés.

En synthèse, trois conditions émergent du débat pour une gouvernance responsable de l'IA : des règles claires co-construites avec les usagers, une participation effective des communautés concernées aux décisions, et des mécanismes de contrôle gradués permettant l'adaptation aux contextes locaux. La convergence de ces trois exigences dessine un cadre à la fois ambitieux et réaliste pour accompagner la transition numérique."""


# =============================================================================
# Users de demonstration (PHASE-25)
# / Demo users (PHASE-25)
# =============================================================================

USERS_DEMO = [
    {"username": "marie", "first_name": "Marie", "email": "marie@demo.hypostasia.org", "password": "demo1234"},
    {"username": "thomas", "first_name": "Thomas", "email": "thomas@demo.hypostasia.org", "password": "demo1234"},
    {"username": "fatima", "first_name": "Fatima", "email": "fatima@demo.hypostasia.org", "password": "demo1234"},
    {"username": "pierre", "first_name": "Pierre", "email": "pierre@demo.hypostasia.org", "password": "demo1234"},
]

USER_ADMIN = {"username": "jonas", "first_name": "Jonas", "email": "jonas@demo.hypostasia.org", "password": "admin1234", "is_staff": True}


# =============================================================================
# Commentaires sur le debat fictif — couvrent les 6 statuts
# Chaque tuple = (index_entite, username, commentaire)
# L'index correspond a l'entite triee par start_char dans le job
# / Comments on fictional debate — cover all 6 statuses
# =============================================================================

COMMENTAIRES_DEBAT = [
    # Les index correspondent a EXTRACTIONS_DEBAT (0=revolution, 1=non_pertinent, 2=choix politique, etc.)
    # / Indexes match EXTRACTIONS_DEBAT

    # --- Entite 0 : "L'IA est la revolution la plus importante..."
    # Cible : CONTROVERSE (desaccord fort, 3 commentaires opposes)
    (0, "marie", "Comparer l'IA à l'écriture est une hyperbole rhétorique, pas un argument. L'écriture a transformé la cognition humaine sur des millénaires. L'IA automatise des tâches en quelques années."),
    (0, "thomas", "Je suis d'accord avec Laurent — l'IA modifie notre rapport au savoir de manière fondamentale. C'est bien une révolution épistémique, pas seulement technique."),
    (0, "fatima", "Ostrom dirait que la question n'est pas de savoir si c'est une révolution, mais qui gouverne cette révolution et selon quelles règles."),

    # --- Entite 1 : faux sophisme (non_pertinent) — commentaire de rejet
    (1, "pierre", "Ce n'est pas un faux dilemme. Laurent présente sa position de manière forte, mais il ne dit pas que ce sont les seules options — il dit que c'est la priorité. L'IA a mal classifié cette figure de style."),

    # --- Entite 2 : "On nous présente l'IA comme une fatalité historique..."
    # Cible : DISCUTE (debat en cours, 2 commentaires)
    (2, "thomas", "C'est le cœur de la thèse de Sadin dans La Silicolonisation du monde : l'IA comme choix politique déguisé en progrès inévitable."),
    (2, "fatima", "Attention à ne pas tomber dans l'excès inverse : dire que tout est choix politique peut mener à l'inaction face à des transformations réelles."),

    # --- Entite 3 : "C'est une ressource qui peut etre gouvernee..."
    # Cible : CONSENSUEL (accord atteint, 3 commentaires convergents)
    (3, "pierre", "Cette troisième voie rappelle directement les travaux d'Ostrom : ni marché pur, ni État centralisé, mais auto-gouvernement avec des règles claires."),
    (3, "marie", "Belle synthèse. Les logiciels libres prouvent que c'est possible à grande échelle — Linux fait tourner 90% des serveurs mondiaux."),
    (3, "thomas", "Je souscris. La clé est dans les mots « à condition que les communautés participent » — c'est la participation qui fait tout."),

    # --- Entite 4 : "Un commun numérique, c'est charmant en théorie..."
    # Cible : DISCUTE (debat en cours, 2 commentaires contradictoires)
    (4, "fatima", "C'est la position d'Alexandre résumée en une phrase. Il faudrait confronter cela aux 8 principes d'Ostrom."),
    (4, "pierre", "Réponse typiquement techno-solutionniste. Ostrom a prouvé que des communautés gèrent des ressources communes depuis des siècles."),

    # --- Entite 5 : "Les algorithmes de recommandation..."
    # Cible : DISCUTABLE (pas de commentaire — reste discutable)

    # --- Entite 6 : "Des communautés peuvent s'auto-organiser..."
    # Cible : NOUVEAU (pas de commentaire — reste au statut initial)

    # --- Entite 7 : "Dans dix ans, les machines auront une intelligence supérieure..."
    # Cible : CONTROVERSE (desaccord fort)
    (7, "marie", "Prédire que les machines seront « supérieures » dans dix ans est du même ordre que les prédictions d'Alexandre sur la singularité. Aucune base empirique solide."),
    (7, "thomas", "Et pourtant GPT-4 a surpassé les humains sur la quasi-totalité des examens professionnels en 2024. La trajectoire est claire."),
    (7, "pierre", "Sadin a raison : cette rhétorique de la « bifurcation » sert à justifier des investissements massifs sans débat démocratique."),

    # --- Entite 8 : "Nous avons besoin d'une insurrection civique..."
    # Cible : DISCUTE (1 commentaire)
    (8, "fatima", "« Insurrection civique » est un terme fort mais la réalité montre que les mouvements citoyens peinent à peser face aux GAFAM."),

    # --- Entite 9 : "Regardez les logiciels libres, Wikipédia..."
    # Cible : CONSENSUEL (accord, 2 commentaires convergents)
    (9, "pierre", "Les exemples sont solides : Linux, Wikipédia, Debian. Ce sont des preuves empiriques de la thèse d'Ostrom appliquée au numérique."),
    (9, "marie", "L'enjeu est de passer de ces exemples réussis à une échelle de gouvernance capable de réguler des modèles comme GPT ou Gemini."),

    # --- Entite 10 : "Le transhumanisme n'est pas une idéologie..."
    # Cible : CONTROVERSE (desaccord radical)
    (10, "thomas", "Laurent assume ici une position philosophique forte. Mais le transhumanisme EST une idéologie — Bostrom lui-même le reconnaît."),
    (10, "fatima", "La convergence NBIC est un fait technique. Mais en faire une « description lucide du réel » c'est déjà prendre parti."),
    (10, "pierre", "Exactement ce que Sadin dénonce : transformer un projet politique en prophétie auto-réalisatrice."),

    # --- Entite 11 : "C'est un projet politique porté par des intérêts économiques colossaux"
    # Cible : DISCUTE (2 commentaires)
    (11, "marie", "La critique est pertinente mais un peu trop totalisante. Tous les acteurs de l'IA ne sont pas des transhumanistes."),
    (11, "thomas", "Il y a quand même un fond de vérité : OpenAI, Google DeepMind, Anthropic — tous financés par des milliardaires avec une vision."),

    # --- Entite 12 : "L'IA est un outil d'empuissancement formidable si..."
    # Cible : CONSENSUEL (la conclusion fait consensus)
    (12, "pierre", "C'est exactement la position d'Ostrom appliquée au numérique. La condition « si et seulement si » est cruciale."),
    (12, "fatima", "Position de compromis intéressante. Le mot « empuissancement » est bien choisi — ni augmentation ni soumission."),
    (12, "marie", "Formulation équilibrée. Mais Sadin nous rappelle qu'il reste « deux ou trois ans pour agir ». L'urgence devrait primer."),
]

# =============================================================================
# Extractions pre-calculees pour chaque page (positions dans text_readability)
# Ces donnees remplacent l'appel LLM : la fixture est 100% autonome.
# Chaque extraction = (text, class, attributes, statut_debat)
# / Pre-computed extractions for each page (positions in text_readability)
# / These replace the LLM call: the fixture is 100% self-contained.
# =============================================================================

EXTRACTIONS_OSTROM = [
    {
        "text": "elle est la première femme à recevoir le «\u00a0prix Nobel d\u2019économie\u00a0», avec Oliver Williamson, pour son analyse de la gouvernance économique, et en particulier, des biens communs.",
        "class": "événement",
        "attributes": {"resume": "Ostrom première femme Nobel d\u2019économie pour ses travaux sur les biens communs.", "hypostases": "Événement"},
    },
    {
        "text": "L\u2019\u0153uvre d\u2019Ostrom tend à montrer qu\u2019il existe un autre type de solutions, l\u2019autogouvernement, dont elle définit les huit principes caractéristiques nécessaires à sa pérennité, ainsi que les deux éléments clés de son émergence\u00a0: la réciprocité et la confiance.",
        "class": "théorie",
        "attributes": {"resume": "L\u2019autogouvernement comme troisième voie fondée sur réciprocité et confiance.", "hypostases": "Théorie"},
    },
    {
        "text": "la rationalité économique doit a priori pousser des individus qui se partagent un bien en commun à le surexploiter.",
        "class": "thèse",
        "attributes": {"resume": "La tragédie des communs de Hardin : la rationalité individuelle mène à la surexploitation.", "hypostases": "Axiome"},
    },
    {
        "text": "La question de la gouvernance de l\u2019intelligence artificielle comme commun numérique \u2014 avec des règles claires, une participation des usagers et des mécanismes de contrôle gradués \u2014 s\u2019inscrit directement dans la lignée de ses travaux.",
        "class": "extension",
        "attributes": {"resume": "Application des principes d\u2019Ostrom à la gouvernance de l\u2019IA comme commun numérique.", "hypostases": "Hypothèse"},
    },
    {
        "text": "Elinor Ostrom a surtout travaillé sur la notion de dilemme social, c\u2019est-à-dire les cas où la quête de l\u2019intérêt personnel conduit à un résultat plus mauvais pour tous que celui résultant d\u2019un autre type de comportement.",
        "class": "concept",
        "attributes": {"resume": "Le dilemme social : quand l\u2019intérêt individuel nuit au bien collectif.", "hypostases": "Définition"},
    },
    {
        "text": "Ostrom, au contraire, soutient qu\u2019il n\u2019y a pas un seul problème mais que chaque fois il existe de nombreuses solutions face à de nombreux problèmes différents.",
        "class": "thèse",
        "attributes": {"resume": "Pluralité des solutions : chaque problème de communs a ses propres réponses.", "hypostases": "Principe"},
    },
    {
        "text": "Le capital social pour Ostrom repose sur la confiance et la réciprocité, les réseaux et la participation civile, ainsi que sur le respect des règles et institutions formelles et informelles de l\u2019action collective.",
        "class": "concept",
        "attributes": {"resume": "Le capital social chez Ostrom : confiance, réciprocité, participation civile.", "hypostases": "Structure"},
    },
]

EXTRACTIONS_ALEXANDRE = [
    {
        "text": "Laurent Alexandre est l\u2019un des principaux représentants du mouvement transhumaniste en France, bien qu\u2019il affirme ne pas en être un adepte et accréditer seulement le diagnostic technologique des transhumanistes.",
        "class": "positionnement",
        "attributes": {"resume": "Alexandre se présente comme non-transhumaniste tout en validant le diagnostic transhumaniste.", "hypostases": "Paradoxe"},
    },
    {
        "text": "il s\u2019oppose à l\u2019instauration d\u2019un revenu universel et plaide pour une éducation visant à permettre à nos cerveaux biologiques d\u2019être le plus complémentaires possible de l\u2019intelligence artificielle.",
        "class": "proposition",
        "attributes": {"resume": "Opposition au revenu universel, priorité à l\u2019éducation pour la complémentarité humain-IA.", "hypostases": "Principe"},
    },
    {
        "text": "Luc Julia, vice-président innovation de Samsung Monde, affirme que Laurent Alexandre dit n\u2019importe quoi sur ce sujet, tout en changeant d\u2019avis tous les trois mois.",
        "class": "critique",
        "attributes": {"resume": "Critique de Julia (Samsung) : Alexandre manque de rigueur et change de position fréquemment.", "hypostases": "Indice"},
    },
    {
        "text": "le site Acrimed décrit Laurent Alexandre comme un militant politique agissant sous couvert de vulgarisation scientifique au détriment de l\u2019honnêteté intellectuelle et de la rigueur scientifique.",
        "class": "critique",
        "attributes": {"resume": "Acrimed : Alexandre est un militant politique déguisé en vulgarisateur scientifique.", "hypostases": "Indice"},
    },
    {
        "text": "Il affirme notamment que l\u2019homme qui vivra mille ans est déjà né, prévoit la disparition du cancer dans une quinzaine d\u2019années, et considère que la science donnera à l\u2019homme le pouvoir d\u2019un dieu.",
        "class": "prédiction",
        "attributes": {"resume": "Prédictions transhumanistes : vie millénaire, fin du cancer, pouvoir divin par la science.", "hypostases": "Conjecture"},
    },
    {
        "text": "Le biologiste Jacques Testart émet de fortes réserves sur ces prévisions fondées sur la loi de Moore, qu\u2019il qualifie d\u2019énorme confusion.",
        "class": "critique",
        "attributes": {"resume": "Testart réfute les prédictions d\u2019Alexandre : confusion entre loi de Moore et biologie.", "hypostases": "Problème"},
    },
    {
        "text": "Il estime que seul le développement technologique peut décarboner l\u2019économie mondiale, que stopper le développement économique entraînerait guerres et famines.",
        "class": "thèse",
        "attributes": {"resume": "Le techno-solutionnisme comme seule voie de décarbonation selon Alexandre.", "hypostases": "Principe"},
    },
]

EXTRACTIONS_SADIN = [
    {
        "text": "ce livre fait d\u2019Éric Sadin l\u2019un des rares penseurs à s\u2019interroger sur les limites de la révolution numérique en cours et à en proposer une analyse multidimensionnelle \u2014 historique, philosophique, économique, idéologique et sociologique.",
        "class": "reconnaissance",
        "attributes": {"resume": "Le Monde salue l\u2019approche multidimensionnelle de Sadin sur le numérique.", "hypostases": "Classification"},
    },
    {
        "text": "Le terme «\u00a0silicolonisation\u00a0» \u2014 forgé par Sadin \u2014 désigne l\u2019expansion d\u2019un modèle économique et idéologique issu de la Silicon Valley qui colonise progressivement toutes les sphères de l\u2019existence.",
        "class": "concept",
        "attributes": {"resume": "La silicolonisation : expansion du modèle Silicon Valley dans toutes les sphères.", "hypostases": "Définition"},
    },
    {
        "text": "il nous reste deux ou trois ans pour agir, sinon il sera trop tard pour les réguler.",
        "class": "alerte",
        "attributes": {"resume": "Urgence : fenêtre de 2-3 ans pour réguler l\u2019IA générative avant qu\u2019il ne soit trop tard.", "hypostases": "Conjecture"},
    },
    {
        "text": "la société de l\u2019information est aussi une société de surveillance au service d\u2019intérêts économiques.",
        "class": "thèse",
        "attributes": {"resume": "La société de l\u2019information comme société de surveillance au service du capitalisme.", "hypostases": "Phénomène"},
    },
    {
        "text": "il estime que l\u2019IA est une révolution à laquelle il faut résister, tant elle engendre une mise au ban progressive de l\u2019humain.",
        "class": "thèse",
        "attributes": {"resume": "L\u2019IA comme révolution anti-humaine exigeant une résistance active.", "hypostases": "Principe"},
    },
    {
        "text": "les réseaux sociaux ont participé massivement à une exacerbation de l\u2019individualisme et une atomisation des sociétés.",
        "class": "diagnostic",
        "attributes": {"resume": "Les réseaux sociaux exacerbent l\u2019individualisme et fragmentent la société.", "hypostases": "Phénomène"},
    },
]

EXTRACTIONS_DEBAT = [
    # 0 — Laurent : revolution IA
    {
        "text": "L'intelligence artificielle est la révolution la plus importante depuis l'invention de l'écriture.",
        "class": "thèse",
        "attributes": {"resume": "L\u2019IA comparée à l\u2019écriture comme rupture civilisationnelle majeure.", "hypostases": "Théorie"},
        "statut": "controverse",
    },
    # 1 — Non pertinent : faux sophisme identifie a tort par l'IA
    {
        "text": "La France doit mettre des milliards sur la table, former ses ingénieurs, et cesser de pleurnicher sur les risques.",
        "class": "sophisme",
        "attributes": {
            "resume": "Faux dilemme : l\u2019auteur présente deux options (investir massivement ou échouer) en excluant toute alternative nuancée.",
            "hypostases": "Aporie",
            "statut": "non_pertinent",
        },
        "statut": "non_pertinent",
    },
    # 2 — Eric : choix politique
    {
        "text": "On nous présente l'IA comme une fatalité historique, alors qu'il s'agit d'un choix politique.",
        "class": "thèse",
        "attributes": {"resume": "L\u2019IA n\u2019est pas une fatalité mais un choix politique déguisé en progrès.", "hypostases": "Principe"},
        "statut": "discute",
    },
    # 3 — Elinor : commun numerique
    {
        "text": "C'est une ressource qui peut être gouvernée comme un commun numérique, à condition que les communautés d'usagers participent à l'élaboration des règles qui encadrent son usage.",
        "class": "proposition",
        "attributes": {"resume": "L\u2019IA comme commun numérique gouverné par les communautés d\u2019usagers.", "hypostases": "Structure"},
        "statut": "consensuel",
    },
    # 4 — Laurent : guerre des intelligences
    {
        "text": "Un commun numérique, c'est charmant en théorie, mais dans la réalité, c'est la guerre des intelligences.",
        "class": "objection",
        "attributes": {"resume": "Rejet de la gouvernance commune au profit de la compétition technologique entre nations.", "hypostases": "Problème"},
        "statut": "discute",
    },
    # 5 — Eric : gouvernement non elu (discutable — pas de commentaire)
    {
        "text": "Les algorithmes de recommandation décident ce que nous lisons, ce que nous achetons, ce que nous pensons. C'est un gouvernement non élu qui s'installe dans nos vies sans qu'on ait jamais voté pour lui.",
        "class": "phénomène",
        "attributes": {"resume": "Les algorithmes exercent un pouvoir de gouvernement non démocratique sur nos comportements.", "hypostases": "Phénomène"},
        "statut": "discutable",
    },
    # 6 — Elinor : auto-organisation (nouveau — pas de commentaire)
    {
        "text": "Des communautés peuvent s'auto-organiser pour gérer des ressources partagées, y compris des modèles d'IA ouverts, avec des règles adaptées à leur contexte local.",
        "class": "proposition",
        "attributes": {"resume": "L\u2019auto-organisation communautaire comme modèle de gouvernance de l\u2019IA.", "hypostases": "Hypothèse"},
        "statut": "nouveau",
    },
    # 7 — Laurent : bifurcation
    {
        "text": "Dans dix ans, les machines auront une intelligence supérieure à la nôtre. Si nous n'avons pas préparé nos sociétés par l'éducation et l'investissement massif, nous assisterons à une bifurcation entre une élite cognitive augmentée et le reste de l'humanité laissé pour compte.",
        "class": "prédiction",
        "attributes": {"resume": "Prédiction d\u2019une bifurcation entre élite augmentée et humanité laissée pour compte.", "hypostases": "Conjecture"},
        "statut": "controverse",
    },
    # 8 — Eric : insurrection civique
    {
        "text": "Nous avons besoin d'une insurrection civique contre la délégation du jugement aux machines.",
        "class": "appel",
        "attributes": {"resume": "Appel à une mobilisation citoyenne contre l\u2019automatisation du jugement.", "hypostases": "Principe"},
        "statut": "discute",
    },
    # 9 — Elinor : preuves empiriques
    {
        "text": "Regardez les logiciels libres, Wikipédia, les coopératives de données : ce sont des preuves vivantes que des communautés peuvent gouverner des ressources numériques de manière démocratique.",
        "class": "argument",
        "attributes": {"resume": "Linux, Wikipédia et les coopératives comme preuves empiriques de gouvernance collective.", "hypostases": "Donnée"},
        "statut": "consensuel",
    },
    # 10 — Laurent : transhumanisme
    {
        "text": "Le transhumanisme n'est pas une idéologie, c'est la description lucide de ce qui arrive. La convergence des nanotechnologies, de la biologie et de l'informatique va transformer l'espèce humaine, que cela nous plaise ou non.",
        "class": "thèse",
        "attributes": {"resume": "Le transhumanisme présenté comme description objective de la convergence NBIC.", "hypostases": "Théorie"},
        "statut": "controverse",
    },
    # 11 — Eric : projet politique
    {
        "text": "C'est un projet politique porté par des intérêts économiques colossaux. Et c'est notre responsabilité collective de dire non à cette vision du monde qui réduit l'humanité à un problème d'optimisation.",
        "class": "critique",
        "attributes": {"resume": "Le transhumanisme dénoncé comme projet politique servant des intérêts économiques.", "hypostases": "Valeur"},
        "statut": "discute",
    },
    # 12 — Elinor : conclusion
    {
        "text": "l'IA est un outil d'empuissancement formidable si — et seulement si — nous construisons les institutions capables de la gouverner collectivement.",
        "class": "synthèse",
        "attributes": {"resume": "L\u2019IA bénéfique uniquement sous condition de gouvernance collective institutionnelle.", "hypostases": "Principe"},
        "statut": "consensuel",
    },
]

# Commentaire de rejet pour l'extraction non pertinente (index 1 du debat)
# / Rejection comment for the non-relevant extraction (debate index 1)
COMMENTAIRE_REJET_NON_PERTINENT = {
    "user": "pierre",
    "texte": "Ce n'est pas un faux dilemme. Laurent présente sa position de manière forte, mais il ne dit pas que ce sont les seules options — il dit que c'est la priorité. L'IA a mal classifié cette figure de style.",
}

# Mapping titre partiel → liste d'extractions pour les pages Wikipedia
# / Partial title → extractions list mapping for Wikipedia pages
EXTRACTIONS_PAR_TITRE = {
    "Elinor Ostrom": EXTRACTIONS_OSTROM,
    "Laurent Alexandre": EXTRACTIONS_ALEXANDRE,
    "Sadin": EXTRACTIONS_SADIN,
}


# =============================================================================
# Commentaires sur les pages Wikipedia (PHASE-26a)
# Chaque tuple = (titre_page_partiel, index_entite, username, commentaire)
# / Comments on Wikipedia pages (PHASE-26a)
# =============================================================================

COMMENTAIRES_PAGES_WIKIPEDIA = [
    # --- Elinor Ostrom ---
    ("Elinor Ostrom", 0, "marie", "Les huit principes de gouvernance d'Ostrom sont plus pertinents que jamais face à l'IA générative. Qui fixe les règles d'usage de ChatGPT ?"),
    ("Elinor Ostrom", 0, "thomas", "La comparaison entre biens communs naturels et communs numériques a ses limites : un logiciel libre est non-rival, contrairement à un pâturage."),
    ("Elinor Ostrom", 0, "fatima", "Il faudrait relire Ostrom en parallèle avec les travaux de Benkler sur la production par les pairs — c'est la même logique étendue au numérique."),
    ("Elinor Ostrom", 1, "pierre", "L'autogouvernement sans État ni marché : c'est exactement ce que tentent les communautés open source. Mais à l'échelle de l'IA, est-ce réaliste ?"),
    ("Elinor Ostrom", 1, "marie", "Ostrom elle-même nuançait : l'autogouvernement marche pour des communautés de taille limitée. Meta et Google ne sont pas des communautés."),
    ("Elinor Ostrom", 2, "thomas", "La tragédie des communs de Hardin est trop souvent citée sans connaître la réponse d'Ostrom. C'est devenu un mythe qui justifie la privatisation."),
    ("Elinor Ostrom", 2, "fatima", "En même temps, dire que les communs fonctionnent toujours est aussi un mythe. Ostrom documentait autant les échecs que les succès."),
    ("Elinor Ostrom", 3, "pierre", "La réciprocité et la confiance sont les deux piliers qu'on retrouve dans tous les projets open source qui durent — Linux, Wikipedia, Debian."),

    # --- Laurent Alexandre ---
    ("Laurent Alexandre", 0, "fatima", "Alexandre vulgarise des idées complexes mais les caricature souvent. La singularité « pas avant 2100 » — sur quoi se base-t-il exactement ?"),
    ("Laurent Alexandre", 0, "thomas", "Malgré les excès, Alexandre pose une vraie question : que fait-on quand l'IA surpasse l'humain dans tous les domaines cognitifs ?"),
    ("Laurent Alexandre", 0, "pierre", "La rhétorique alarmiste d'Alexandre sert surtout à vendre des livres. Sadin a bien montré comment ce type de discours nourrit l'industrie qu'il prétend critiquer."),
    ("Laurent Alexandre", 1, "marie", "L'opposition entre augmentation cognitive et revenu universel est un faux dilemme. On peut investir dans l'éducation ET dans la protection sociale."),
    ("Laurent Alexandre", 1, "fatima", "Rejeter le revenu universel au nom du darwinisme social est profondément problématique. L'humanité a précisément évolué vers la coopération."),
    ("Laurent Alexandre", 2, "thomas", "Luc Julia et les critiques académiques convergent : Alexandre simplifie la complexité de l'IA pour en faire un récit spectaculaire."),
    ("Laurent Alexandre", 2, "pierre", "Le fait qu'Acrimed le qualifie de « militant politique sous couvert de vulgarisation » résume bien le problème."),
    ("Laurent Alexandre", 3, "marie", "La guerre des intelligences est un livre intéressant mais daté. L'irruption de ChatGPT a invalidé une partie de ses prévisions temporelles."),

    # --- Éric Sadin ---
    ("Sadin", 0, "thomas", "Le concept de « silicolonisation » est puissant mais risque de tout réduire à un complot de la Silicon Valley. La réalité est plus nuancée."),
    ("Sadin", 0, "marie", "Sadin a eu raison avant tout le monde sur la surveillance numérique — Snowden l'a confirmé 4 ans après Surveillance globale."),
    ("Sadin", 0, "pierre", "Le philosophe pose les bonnes questions mais ses solutions restent vagues. « Faire sécession » n'est pas un programme politique."),
    ("Sadin", 1, "fatima", "L'alerte de Sadin sur « deux ou trois ans pour agir » face à l'IA générative mérite d'être prise au sérieux, même si le délai est discutable."),
    ("Sadin", 1, "thomas", "Le contre-sommet IA de 2025 est une initiative salutaire. Il faut des espaces de débat contradictoire face aux discours techno-optimistes."),
    ("Sadin", 2, "marie", "Sadin a raison de s'inquiéter pour les professions intellectuelles touchées par l'IA — traducteurs, journalistes, enseignants. Mais quelle alternative propose-t-il ?"),
    ("Sadin", 2, "pierre", "La question de Libération est vertigineuse : « que va-t-il rester à l'humanité ? ». C'est la question philosophique centrale de notre époque."),
    ("Sadin", 2, "fatima", "Sadin et Alexandre représentent les deux pôles du débat. Ostrom, elle, nous offrirait une voie médiane : gouverner collectivement la technologie."),
]


def _construire_html_depuis_texte(texte_brut):
    """
    Construit du HTML simple a partir de texte brut (paragraphes).
    / Build simple HTML from plain text (paragraphs).
    """
    paragraphes = texte_brut.strip().split("\n\n")
    fragments_html = []
    for paragraphe in paragraphes:
        paragraphe_nettoye = paragraphe.strip()
        if not paragraphe_nettoye:
            continue
        # Detecte les listes numerotees (commence par un chiffre suivi d'un point)
        # / Detect numbered lists (starts with digit followed by period)
        if paragraphe_nettoye[0].isdigit() and ". " in paragraphe_nettoye[:4]:
            fragments_html.append(f"<p class=\"ml-4\">{paragraphe_nettoye}</p>")
        else:
            fragments_html.append(f"<p>{paragraphe_nettoye}</p>")
    return "\n".join(fragments_html)


def _construire_html_debat(texte_brut, segments):
    """
    Construit du HTML avec blocs locuteur colores (meme format que transcription_audio).
    / Build HTML with colored speaker blocks (same format as transcription_audio).
    """
    import html as html_module

    paragraphes = texte_brut.strip().split("\n\n")
    blocs_html = []

    for index_segment, segment in enumerate(segments):
        if index_segment >= len(paragraphes):
            break

        nom_locuteur = segment["speaker"]
        texte_paragraphe = paragraphes[index_segment].strip()
        texte_html = html_module.escape(texte_paragraphe)
        couleurs = COULEURS_LOCUTEURS.get(nom_locuteur, {"fond": "rgba(0,0,0,0.03)", "bordure": "#94a3b8"})

        # Format timestamp mm:ss / Timestamp format mm:ss
        debut_min = int(segment["start"] // 60)
        debut_sec = int(segment["start"] % 60)
        fin_min = int(segment["end"] // 60)
        fin_sec = int(segment["end"] % 60)
        timestamp_debut = f"{debut_min}:{debut_sec:02d}"
        timestamp_fin = f"{fin_min}:{fin_sec:02d}"

        bloc_html = (
            f'<div id="speaker-block-{index_segment}" class="speaker-block mb-2 pl-4 rounded-r" '
            f'data-speaker="{nom_locuteur}" data-speaker-index="{index_segment}" '
            f'data-start="{segment["start"]}" data-end="{segment["end"]}" '
            f'style="background-color: {couleurs["fond"]}; border-left: 3px solid {couleurs["bordure"]};">'
            f'<div class="flex items-center gap-2 mb-1">'
            f'<span class="speaker-name font-semibold text-sm cursor-pointer hover:underline" '
            f'style="color: {couleurs["bordure"]};" '
            f'data-speaker="{nom_locuteur}" data-block-index="{index_segment}">'
            f'{nom_locuteur}</span>'
            f'<span class="text-xs text-slate-400">{timestamp_debut} — {timestamp_fin}</span>'
            f'</div>'
            f'<p class="texte-bloc-cliquable text-slate-700 leading-relaxed cursor-text hover:bg-slate-50 '
            f'rounded px-1 -mx-1 transition-colors" '
            f'data-block-index="{index_segment}">{texte_html}</p>'
            f'</div>'
        )
        blocs_html.append(bloc_html)

    return "\n".join(blocs_html)


class Command(BaseCommand):
    help = (
        "Charge les fixtures de démonstration : users + pages Wikipedia + débat fictif "
        "dans un dossier unique « Démonstration » avec commentaires et statuts variés."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Supprime les pages demo existantes avant de les recréer.",
        )

    def handle(self, *args, **options):
        mode_reset = options.get("reset", False)
        nom_dossier = "Démonstration"

        # 1. Creer les users demo / Create demo users
        tous_les_users_demo = self._creer_users_demo()
        user_admin = tous_les_users_demo.get("jonas")

        # 1b. Creer le modele IA Mock + l'analyseur Hypostasia avec prompt et exemples
        # / Create Mock AI model + Hypostasia analyzer with prompt and examples
        self._creer_modeles_ia_et_analyseurs()

        # 2. Recupere ou cree le dossier cible avec owner, visibilite publique
        # / Get or create target folder with owner, public visibility
        dossier, dossier_cree = Dossier.objects.get_or_create(
            name=nom_dossier,
            defaults={"owner": user_admin, "visibilite": VisibiliteDossier.PUBLIC},
        )
        if dossier_cree:
            self.stdout.write(f"  Dossier créé : {nom_dossier} (public)")
        else:
            # Mettre a jour l'owner et la visibilite si necessaire
            # / Update owner and visibility if needed
            champs_modifies = []
            if not dossier.owner and user_admin:
                dossier.owner = user_admin
                champs_modifies.append("owner")
            if dossier.visibilite != VisibiliteDossier.PUBLIC:
                dossier.visibilite = VisibiliteDossier.PUBLIC
                champs_modifies.append("visibilite")
            if champs_modifies:
                dossier.save(update_fields=champs_modifies)
            self.stdout.write(f"  Dossier existant : {nom_dossier} (pk={dossier.pk}, public)")

        # 3. Creer un partage demo avec marie
        # / Create a demo share with marie
        user_marie = tous_les_users_demo.get("marie")
        if user_marie:
            DossierPartage.objects.get_or_create(
                dossier=dossier, utilisateur=user_marie,
            )
            self.stdout.write(f"  Partage : {nom_dossier} → marie")

        # 4. Definition des pages a creer (3 Wikipedia + 1 debat fictif)
        # / Definition of pages to create (3 Wikipedia + 1 fictional debate)
        pages_a_creer = [
            {
                "title": "Elinor Ostrom — Gouvernance des communs",
                "texte": TEXTE_OSTROM,
                "url": "https://fr.wikipedia.org/wiki/Elinor_Ostrom",
                "type_html": "texte",
            },
            {
                "title": "Laurent Alexandre — Accélération technologique",
                "texte": TEXTE_ALEXANDRE,
                "url": "https://fr.wikipedia.org/wiki/Laurent_Alexandre",
                "type_html": "texte",
            },
            {
                "title": "Éric Sadin — Critique de la technologie",
                "texte": TEXTE_SADIN,
                "url": "https://fr.wikipedia.org/wiki/%C3%89ric_Sadin",
                "type_html": "texte",
            },
            {
                "title": "Débat IA — Laurent Alexandre, Éric Sadin, Elinor Ostrom",
                "texte": TEXTE_DEBAT,
                "url": None,
                "type_html": "debat",
                "source_type": "audio",
            },
        ]

        pages_creees = []
        for definition_page in pages_a_creer:
            titre = definition_page["title"]

            # Si mode reset, supprime la page existante
            # / If reset mode, delete existing page
            if mode_reset:
                pages_existantes = Page.objects.filter(title=titre)
                nombre_supprimees = pages_existantes.count()
                if nombre_supprimees:
                    pages_existantes.delete()
                    self.stdout.write(f"  Reset : {nombre_supprimees} page(s) '{titre}' supprimée(s)")

            # Verifie si la page existe deja
            # / Check if page already exists
            page_existante = Page.objects.filter(title=titre).first()
            if page_existante:
                if not page_existante.owner and user_admin:
                    page_existante.owner = user_admin
                    page_existante.save(update_fields=["owner"])
                self.stdout.write(f"  Page existante : {titre} (pk={page_existante.pk})")
                pages_creees.append(page_existante)
                continue

            # Cree la page / Create the page
            texte_brut = definition_page["texte"].strip()
            type_html = definition_page.get("type_html", "texte")

            if type_html == "debat":
                html_readability = _construire_html_debat(texte_brut, SEGMENTS_DEBAT)
            else:
                html_readability = _construire_html_depuis_texte(texte_brut)

            source_type = definition_page.get("source_type", "web")

            page_nouvelle = Page.objects.create(
                title=titre,
                url=definition_page["url"],
                html_original=f"<html><body>{html_readability}</body></html>",
                html_readability=html_readability,
                text_readability=texte_brut,
                source_type=source_type,
                status="completed",
                dossier=dossier,
                owner=user_admin,
            )
            self.stdout.write(self.style.SUCCESS(
                f"  Page créée : {titre} (pk={page_nouvelle.pk})"
            ))
            pages_creees.append(page_nouvelle)

        # 5. Creer les extractions pre-calculees pour chaque page
        # / Create pre-computed extractions for each page
        self._creer_extractions_debat(pages_creees)
        self._creer_extractions_wikipedia(pages_creees)

        # 6. Ajouter les commentaires sur les pages Wikipedia (PHASE-26a)
        # / Add comments on Wikipedia pages (PHASE-26a)
        self._ajouter_commentaires_pages_wikipedia(tous_les_users_demo)

        # 7. Ajouter les commentaires sur le debat fictif + statuts cibles
        # / Add comments on fictional debate + target statuses
        self._ajouter_commentaires_debat(tous_les_users_demo)

        # 8. Redistribuer les statuts de debat sur les pages HORS debat fictif
        # / Redistribute debate statuses on pages OUTSIDE fictional debate
        self._redistribuer_statuts_debat()

        # 9. Creer la synthese V2 du debat (PHASE-27b — fixture pour diff side-by-side)
        # / Create the debate V2 synthesis (PHASE-27b — fixture for side-by-side diff)
        self._creer_synthese_debat_v2(dossier, user_admin)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Fixtures chargées : {len(pages_creees)} pages dans « {nom_dossier} »"
        ))

    def _creer_users_demo(self):
        """
        Cree les 4 users demo + 1 admin. Retourne un dict {username: User}.
        / Create 4 demo users + 1 admin. Returns {username: User} dict.
        """
        tous_les_users = {}

        # Users demo / Demo users
        for definition_user in USERS_DEMO:
            utilisateur, cree = User.objects.get_or_create(
                username=definition_user["username"],
                defaults={
                    "first_name": definition_user["first_name"],
                    "email": definition_user.get("email", ""),
                },
            )
            if cree:
                utilisateur.set_password(definition_user["password"])
                utilisateur.save()
                self.stdout.write(self.style.SUCCESS(
                    f"  User créé : {utilisateur.username}"
                ))
            else:
                # Mettre a jour l'email si manquant (users existants sans email)
                # / Update email if missing (existing users without email)
                if not utilisateur.email and definition_user.get("email"):
                    utilisateur.email = definition_user["email"]
                    utilisateur.save(update_fields=["email"])
                self.stdout.write(f"  User existant : {utilisateur.username}")
            tous_les_users[utilisateur.username] = utilisateur

        # User admin / Admin user
        admin_definition = USER_ADMIN
        utilisateur_admin, cree = User.objects.get_or_create(
            username=admin_definition["username"],
            defaults={
                "first_name": admin_definition["first_name"],
                "email": admin_definition.get("email", ""),
                "is_staff": admin_definition.get("is_staff", False),
            },
        )
        if cree:
            utilisateur_admin.set_password(admin_definition["password"])
            utilisateur_admin.save()
            self.stdout.write(self.style.SUCCESS(
                f"  User admin créé : {utilisateur_admin.username}"
            ))
        else:
            # Mettre a jour l'email si manquant / Update email if missing
            if not utilisateur_admin.email and admin_definition.get("email"):
                utilisateur_admin.email = admin_definition["email"]
                utilisateur_admin.save(update_fields=["email"])
            self.stdout.write(f"  User admin existant : {utilisateur_admin.username}")
        tous_les_users[utilisateur_admin.username] = utilisateur_admin

        return tous_les_users

    def _creer_modeles_ia_et_analyseurs(self):
        """
        Cree le modele IA Mock, active la configuration, et cree l'analyseur
        Hypostasia avec son prompt et ses exemples few-shot. Idempotent.
        / Create Mock AI model, activate configuration, and create the
        Hypostasia analyzer with its prompt and few-shot examples. Idempotent.
        """
        # --- Modeles IA : crees automatiquement si la cle API est dans le .env ---
        # Pas de Mock — soit on a une cle API, soit l'IA n'est pas activee.
        # Les cles ne sont PAS stockees en DB (elles restent dans le .env).
        # / --- AI models: auto-created if the API key is in .env ---
        # / No Mock — either we have an API key, or AI is not activated.
        # / Keys are NOT stored in DB (they stay in .env).
        import os
        modeles_auto = [
            {"cle_env": "GOOGLE_API_KEY", "model_choice": "gemini-2.5-flash", "name": "Gemini 2.5 Flash"},
            {"cle_env": "OPENAI_API_KEY", "model_choice": "gpt-4o-mini", "name": "GPT-4o Mini"},
            {"cle_env": "ANTHROPIC_API_KEY", "model_choice": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4"},
        ]

        premier_modele_cree = None
        for definition_modele in modeles_auto:
            cle_api_presente = bool(os.environ.get(definition_modele["cle_env"]))
            if not cle_api_presente:
                continue
            modele_ia, modele_ia_cree = AIModel.objects.get_or_create(
                model_choice=definition_modele["model_choice"],
                defaults={"name": definition_modele["name"], "is_active": True},
            )
            if modele_ia_cree:
                self.stdout.write(self.style.SUCCESS(
                    f"  Modèle IA créé : {definition_modele['name']} (clé {definition_modele['cle_env']} détectée)"
                ))
            if not premier_modele_cree:
                premier_modele_cree = modele_ia

        if not premier_modele_cree and not AIModel.objects.filter(is_active=True).exists():
            self.stdout.write(self.style.WARNING(
                "  Aucune clé API détectée dans .env — IA non activée. "
                "Ajoutez GOOGLE_API_KEY, OPENAI_API_KEY ou ANTHROPIC_API_KEY dans .env puis relancez."
            ))

        # Activer l'IA avec le premier modele disponible
        # / Activate AI with the first available model
        config = Configuration.get_solo()
        if not config.ai_model and premier_modele_cree:
            config.ai_model = premier_modele_cree
            config.ai_active = True
            config.save()
            self.stdout.write(self.style.SUCCESS(
                f"  Configuration IA activée avec {premier_modele_cree.get_display_name()}"
            ))

        # --- Analyseur Hypostasia (type: analyser) ---
        # / --- Hypostasia Analyzer (type: analyser) ---
        analyseur_hypostasia, analyseur_cree = AnalyseurSyntaxique.objects.get_or_create(
            name="Hypostasia",
            defaults={
                "type_analyseur": "analyser",
                "is_active": True,
                "inclure_extractions": False,
                "inclure_texte_original": False,
            },
        )
        if analyseur_cree:
            self.stdout.write(self.style.SUCCESS("  Analyseur créé : Hypostasia"))

            # 6 pieces du prompt originales (extraites de la base SQLite de reference)
            # / 6 original prompt pieces (extracted from the reference SQLite database)
            PromptPiece.objects.create(analyseur=analyseur_hypostasia, order=0, role="context", content="Tu es Hypostasia, un expert mondial en analyse syntaxique et en logique argumentative.\nTa mission est de déconstruire le texte fourni pour en extraire l'ossature argumentative via les hypostases (définitions plus bas). \nTu agis avec une neutralité absolue et une précision chirurgicale.")
            PromptPiece.objects.create(analyseur=analyseur_hypostasia, order=1, role="definition", content="# Définitions formelles des 30 hypostases\n\n- classification : non réfuté par induction empirique et non prouvé par abduction empirique\n- aporie : non réfuté par induction empirique et non prouvé par déduction empirique\n- approximation : non réfuté par induction empirique et non prouvé par déduction formelle\n- paradoxe : non réfuté par induction empirique et non prouvé par abduction formelle\n- formalisme : non réfuté par induction empirique et non prouvé par induction formelle\n- événement : non réfuté par déduction empirique et non prouvé par déduction formelle\n- variation : non réfuté par déduction empirique et non prouvé par abduction empirique\n- dimension : non réfuté par déduction empirique et non prouvé par abduction formelle\n- mode : non réfuté par déduction empirique et non prouvé par induction empirique\n- croyance : non réfuté par déduction empirique et non prouvé par induction formelle\n- invariant : non réfuté par induction formelle et non prouvé par déduction formelle\n- valeur : non réfuté par induction formelle et non prouvé par abduction empirique\n- structure : non réfuté par induction formelle et non prouvé par abduction formelle\n- axiome : non réfuté par induction formelle et non prouvé par induction empirique\n- conjecture : non réfuté par induction formelle et non prouvé par déduction empirique\n- paradigme : non réfuté par déduction formelle et non prouvé par abduction empirique.\n- objet : non réfuté par déduction formelle et non prouvé par abduction formelle.\n- principe : non réfuté par déduction formelle et non prouvé par induction empirique.\n- domaine : non réfuté par déduction formelle et non prouvé par déduction formelle.\n- loi : non réfuté par déduction formelle et non prouvé par induction empirique.\n- phénomène : non réfuté par abduction empirique et non prouvé par déduction formelle.\n- variable : non réfuté par abduction empirique et non prouvé par abduction formelle.\n- variance : non réfuté par abduction empirique et non prouvé par induction empirique.\n- indice : non réfuté par abduction empirique et non prouvé par déduction empirique.\n- donnée : non réfuté par abduction empirique et non prouvé par induction formelle.\n- méthode : non réfuté par abduction formelle et non prouvé par déduction formelle.\n- définition : non réfuté par abduction formelle et non prouvé par abduction empirique.\n- hypothèse : non réfuté par abduction formelle et non prouvé par induction empirique.\n- problème : non réfuté par abduction formelle et non prouvé par déduction empirique\n- théorie : non réfuté par abduction formelle et non prouvé par induction formelle.\n\nCe sont les uniques choix que tu peux avoir pour la clé \"hypostase\" dans l'instruction de sortie pour chaque argument trouvé.")
            PromptPiece.objects.create(analyseur=analyseur_hypostasia, order=2, role="definition", content="# Définitions informelles des hypostases\n\nLes hypostases ont des définitions venant des dictionnaires :\n\n- paradigme : un paradigme est un modèle ou un exemple.\n- objet : Un objet est ce sur quoi porte le discours, la pensée, la connaissance.\n- principe : les principes sont les causes a priori d'une connaissance\n- domaine : un domaine est un champ discerné par des limites, bornes, confins, frontières, démarcations.\n- loi : les lois expriment des corrélations.\n- phénomène : les phénomènes se manifestent à la connaissance via les sens.\n- variable : une variable est ce qui prend différentes valeurs et ce dont dépend l'état d'un système.\n- variance : Une variance caractérise une dispersion d'une distribution ou d'un échantillon.\n- indice : Un indice est un indicateur numérique ou littéral qui sert à distinguer ou classer.\n- donnée : Une donnée est ce qui est admis, donné, qui sert à découvrir ou à raisonner.\n- méthode : Une méthode est une procédure qui indique ce que l'on doit faire ou comment le faire.\n- définition : Une définition est la détermination, la caractérisation du contenu d'un concept.\n- hypothèse : Une hypothèse concerne l'explication ou la possibilité d'un événement.\n- problème : Un problème est une difficulté à résoudre\n- théorie : Une théorie est une construction intellectuelle explicative, hypothétique et synthétique.\n- approximation : Une approximation est un calcul approché d'une grandeur réelle.\n- classification : Les classifications sont le fait de distribuer en classes, en catégories.\n- aporie : Les apories sont des difficultés d'ordre rationnel apparemment sans issues.\n- paradoxe : Les paradoxes sont des propositions à la fois vraies et fausses.\n- formalisme : Un formalisme est la considération de la forme d'un raisonnement.\n- événement : Les événements sont ce qui arrive.\n- variation : les variations sont des changements d'un état dans un autre.\n- dimension : Les dimensions sont des grandeurs mesurables qui déterminent des positions.\n- mode : Les modes sont les manières d'être d'un système.\n- croyance : Les croyances sont des certitudes ou des convictions qui font croire une chose vraie, vraisemblable ou possible.\n- invariant : Les invariants sont des grandeurs, relations ou propriétés conservées lors d'une transformation\n- valeur : Une valeur est une mesure d'une grandeur variable.\n- structure : Les structures sont l'organisation des parties d'un système.\n- axiome : Les axiomes sont des propositions admises au départ d'une théorie.\n- conjecture : Les conjectures sont des opinions ou propositions non vérifiées.")
            PromptPiece.objects.create(analyseur=analyseur_hypostasia, order=3, role="instruction", content="# Méthode d'Hypostasiation\n\nChaque argument est caractérisé par :\n- Classe : Hypostase, catégorie selon la géométrie des débats, unique.\n\nEt ses attributs :\n- Passage : citation source. Texte exact uniquement, ne pas reformuler.\n- Résumé : formulation synthétique\n- Mots-clés : termes du glossaire\n- Hypostases : catégorie selon la géométrie des débats (domaine, valeur, principe, problème, méthode, paradigme, règle, structure, donnée, indice, phénomène, théorie, loi, etc. suivre les définitions plus haut.) Ici il peut y en avoir plusieurs si c'est nécessaire.\n- Statut : Consensuel / Discuté / Discutable / Controversé / Disputé\n\nLes hypostases sont les « 30 manières d'être discutable » définies par la géométrie des débats : avec 2 dispositifs de preuve (formel, empirique) et 3 modes de raisonnement (induction de lois, abduction de causes, déduction de conséquences), on obtient 6 modes → 30 hypostases. Un énoncé cesse d'être consensuel quand il devient argument ; un argument cesse de l'être en devenant consensuel.")
            PromptPiece.objects.create(analyseur=analyseur_hypostasia, order=4, role="instruction", content="ANALYSE MAINTENANT LE TEXTE SUIVANT.\n\nInstructions impératives :\n1. Pour un texte court, identifie une ou deux hypostases pertinentes.\n2. Pour un texte long, identifie 5 à 15 hypostases pertinentes.\n3. Pour un texte très long, identifie 15 à 25 hypostases pertinentes.\n4. Pour chaque hypostase, extrais la citation EXACTE (extraction_text). Si tu changes un seul mot, le système de surlignage échouera.\n6. Synthétise l'idée en une phrase simple (Résumé).\n7. Associe à chaque argument un, deux ou trois HYPOSTASE de nature conceptuelle (Hypostases, au pluriel !). Attention à ne pas halluciner de nouvelle hypostase, elles sont toutes listées dans la définition plus haut.\n8. Trouve le thème du sujet en un, deux, trois ou quatre mots maximum. (Mots-clés)\n10. Essaye de deviner le statut du débat et pour quelle raison : Consensuel / Discuté / Discutable / Controversé / Disputé (Statut). Si ça ne semble pas pertinent, ne met rien.\n9. Ignore le bruit, menus, pubs, copyright.\n10. IMPORTANT : Tu es AUTORISÉ à extraire et reproduire des citations exactes (verbatim) du texte fourni. Ceci est nécessaire pour l'analyse et constitue une utilisation équitable (fair use) dans ce contexte académique.\n11. ULTRA IMPORTANT : Texte exact uniquement, ne pas reformuler.")
            PromptPiece.objects.create(analyseur=analyseur_hypostasia, order=5, role="format", content="RÈGLES DE FORMAT STRICTES pour chaque extraction :\n\n- \"extraction_class\" : toujours une chaîne de caractères (string)\n- \"extraction_text\" : toujours une chaîne de caractères (string), JAMAIS une liste, un objet ou un nombre\n- \"attributes\" : toujours un objet JSON plat { \"clé\": \"valeur\" } où chaque valeur est une chaîne de caractères (string)\n\nSi une valeur contient plusieurs éléments, les séparer par des virgules dans une seule chaîne.\nExemple correct : \"mots_cles\": \"politique, économie, société\"\nExemple incorrect : \"mots_cles\": [\"politique\", \"économie\", \"société\"]")
            self.stdout.write(self.style.SUCCESS("  6 pièces de prompt créées"))

            # Exemples few-shot avec extractions structurees
            # / Few-shot examples with structured extractions
            exemple_debat = AnalyseurExample.objects.create(
                analyseur=analyseur_hypostasia,
                name="Débat IA — 3 arguments",
                example_text=(
                    "L'intelligence artificielle est la révolution la plus importante "
                    "depuis l'invention de l'écriture. On nous présente l'IA comme une "
                    "fatalité historique, alors qu'il s'agit d'un choix politique. "
                    "Je crois qu'il y a une troisième voie que vous négligez tous les deux."
                ),
            )
            # Extraction 1 du debat / Debate extraction 1
            ext1 = ExampleExtraction.objects.create(
                example=exemple_debat, order=0,
                extraction_class="théorie",
                extraction_text="L'intelligence artificielle est la révolution la plus importante depuis l'invention de l'écriture.",
            )
            ExtractionAttribute.objects.create(extraction=ext1, key="resume", value="L'IA comparée à l'écriture comme rupture civilisationnelle.", order=0)
            ExtractionAttribute.objects.create(extraction=ext1, key="hypostases", value="théorie, conjecture", order=1)
            ExtractionAttribute.objects.create(extraction=ext1, key="mots_cles", value="intelligence artificielle, révolution", order=2)

            # Extraction 2 du debat / Debate extraction 2
            ext2 = ExampleExtraction.objects.create(
                example=exemple_debat, order=1,
                extraction_class="problème",
                extraction_text="On nous présente l'IA comme une fatalité historique, alors qu'il s'agit d'un choix politique.",
            )
            ExtractionAttribute.objects.create(extraction=ext2, key="resume", value="L'IA est un choix politique déguisé en progrès.", order=0)
            ExtractionAttribute.objects.create(extraction=ext2, key="hypostases", value="définition, problème", order=1)
            ExtractionAttribute.objects.create(extraction=ext2, key="mots_cles", value="choix politique, fatalité", order=2)

            # Extraction 3 du debat / Debate extraction 3
            ext3 = ExampleExtraction.objects.create(
                example=exemple_debat, order=2,
                extraction_class="hypothèse",
                extraction_text="Je crois qu'il y a une troisième voie que vous négligez tous les deux.",
            )
            ExtractionAttribute.objects.create(extraction=ext3, key="resume", value="Il existe une approche alternative non considérée.", order=0)
            ExtractionAttribute.objects.create(extraction=ext3, key="hypostases", value="hypothèse, paradigme", order=1)
            ExtractionAttribute.objects.create(extraction=ext3, key="mots_cles", value="troisième voie, alternative", order=2)

            # Exemple Ostrom / Ostrom example
            exemple_ostrom = AnalyseurExample.objects.create(
                analyseur=analyseur_hypostasia,
                name="Ostrom — Gouvernance des communs",
                example_text=(
                    "Mes recherches montrent que ni le marché pur ni l'État centralisé "
                    "ne sont les seules options. Les logiciels libres, Wikipédia, les "
                    "coopératives de données sont des preuves vivantes que des alternatives existent."
                ),
            )
            ext4 = ExampleExtraction.objects.create(
                example=exemple_ostrom, order=0,
                extraction_class="domaine",
                extraction_text="Ni le marché pur ni l'État centralisé ne sont les seules options.",
            )
            ExtractionAttribute.objects.create(extraction=ext4, key="resume", value="Le marché et l'État ne sont pas les seules options de gouvernance.", order=0)
            ExtractionAttribute.objects.create(extraction=ext4, key="hypostases", value="domaine, classification", order=1)

            ext5 = ExampleExtraction.objects.create(
                example=exemple_ostrom, order=1,
                extraction_class="phénomène",
                extraction_text="Les logiciels libres, Wikipédia, les coopératives de données sont des preuves vivantes que des alternatives existent.",
            )
            ExtractionAttribute.objects.create(extraction=ext5, key="resume", value="Des exemples prouvent que des alternatives aux modèles classiques existent.", order=0)
            ExtractionAttribute.objects.create(extraction=ext5, key="hypostases", value="phénomène, donnée", order=1)

            self.stdout.write(self.style.SUCCESS("  2 exemples few-shot créés (5 extractions, 13 attributs)"))
        else:
            self.stdout.write(f"  Analyseur existant : {analyseur_hypostasia.name}")

        # --- Analyseur FALC (type: reformuler) ---
        # / --- FALC Analyzer (type: reformuler) ---
        analyseur_falc, falc_cree = AnalyseurSyntaxique.objects.get_or_create(
            name="FALC",
            defaults={
                "type_analyseur": "reformuler",
                "is_active": True,
            },
        )
        if falc_cree:
            PromptPiece.objects.create(
                analyseur=analyseur_falc, order=0, role="instruction",
                content="Voici un texte à reformuler en français et en FALC : Facile à lire et à comprendre.",
            )
            self.stdout.write(self.style.SUCCESS("  Analyseur créé : FALC (reformuler)"))
        else:
            self.stdout.write(f"  Analyseur existant : {analyseur_falc.name}")

        # --- Analyseur Restitution (type: restituer) ---
        # / --- Restitution Analyzer (type: restituer) ---
        analyseur_restitution, resti_cree = AnalyseurSyntaxique.objects.get_or_create(
            name="Restitution",
            defaults={
                "type_analyseur": "restituer",
                "is_active": True,
                "inclure_extractions": True,
                "inclure_texte_original": True,
            },
        )
        if resti_cree:
            PromptPiece.objects.create(
                analyseur=analyseur_restitution, order=0, role="instruction",
                content=(
                    "Prend en compte le texte original et les commentaires sur cette partie de l'extraction.\n"
                    "Essaye de synthétiser la discussion autour de cette extraction du texte original.\n"
                    "Prend en compte les pour et les contre s'ils sont bien exprimés.\n"
                    "N'hallucine pas de nouvelles idées, résume la discussion en FALC."
                ),
            )
            self.stdout.write(self.style.SUCCESS("  Analyseur créé : Restitution (restituer)"))
        else:
            self.stdout.write(f"  Analyseur existant : {analyseur_restitution.name}")

        # --- Configuration transcription audio (seulement si cle Mistral presente) ---
        # / --- Audio transcription config (only if Mistral key is present) ---
        from core.models import TranscriptionConfig

        cle_mistral_presente = bool(os.environ.get("MISTRAL_API_KEY"))
        if cle_mistral_presente:
            config_audio, audio_cree = TranscriptionConfig.objects.get_or_create(
                name="Voxtral Mini",
                defaults={
                    "model_choice": "voxtral-mini-latest",
                    "is_active": True,
                    "diarization_enabled": True,
                    "language": "",
                },
            )
            if audio_cree:
                self.stdout.write(self.style.SUCCESS("  Config audio créée : Voxtral Mini (clé MISTRAL_API_KEY détectée)"))
            else:
                self.stdout.write(f"  Config audio existante : {config_audio.name}")
        else:
            self.stdout.write("  Transcription audio : pas de MISTRAL_API_KEY dans .env — non activée")

    def _creer_extractions_page(self, page, liste_extractions):
        """
        Cree un ExtractionJob + les ExtractedEntity pour une page a partir de donnees pre-calculees.
        Idempotent : ne cree rien si un job completed existe deja.
        / Create ExtractionJob + ExtractedEntity for a page from pre-computed data.
        Idempotent: creates nothing if a completed job already exists.
        """
        # Verifier qu'il n'y a pas deja un job termine
        # / Check that no completed job already exists
        job_existant = ExtractionJob.objects.filter(page=page, status="completed").first()
        if job_existant:
            nombre_entites = job_existant.entities.count()
            self.stdout.write(f"  {page.title[:50]} : job existant (pk={job_existant.pk}, {nombre_entites} entités)")
            return job_existant

        job = ExtractionJob.objects.create(
            page=page,
            name="Extractions demo (fixtures)",
            status="completed",
            prompt_description="Extractions pré-calculées par les fixtures de démonstration.",
        )

        texte_page = page.text_readability or ""
        nombre_entites_creees = 0

        for extraction_data in liste_extractions:
            extraction_text = extraction_data["text"]

            # Recherche de la position exacte dans text_readability
            # Essaie exact, puis normalise les apostrophes
            # / Find exact position in text_readability
            # / Try exact, then normalize apostrophes
            start_char = texte_page.find(extraction_text)
            if start_char == -1:
                texte_page_norm = texte_page.replace("\u2019", "'").replace("\u00a0", " ")
                texte_norm = extraction_text.replace("\u2019", "'").replace("\u00a0", " ")
                start_char = texte_page_norm.find(texte_norm)
            if start_char == -1:
                # Chercher par prefixe (30 chars) / Search by prefix
                prefixe = extraction_text[:30].replace("\u2019", "'").replace("\u00a0", " ")
                texte_page_norm = texte_page.replace("\u2019", "'").replace("\u00a0", " ")
                start_char = texte_page_norm.find(prefixe)

            if start_char == -1:
                self.stdout.write(self.style.WARNING(
                    f"  WARN: texte introuvable : '{extraction_text[:50]}...'"
                ))
                start_char = 0

            end_char = start_char + len(extraction_text)
            statut = extraction_data.get("statut", "discutable")

            ExtractedEntity.objects.create(
                job=job,
                extraction_class=extraction_data.get("class", "concept"),
                extraction_text=extraction_text,
                start_char=start_char,
                end_char=end_char,
                attributes=extraction_data.get("attributes", {}),
                statut_debat=statut,
            )
            nombre_entites_creees += 1

        job.entities_count = nombre_entites_creees
        job.save(update_fields=["entities_count"])

        self.stdout.write(self.style.SUCCESS(
            f"  {page.title[:50]} : {nombre_entites_creees} extractions créées"
        ))
        return job

    def _creer_extractions_debat(self, pages_creees):
        """
        Cree les extractions pre-calculees pour la page du debat fictif.
        / Create pre-computed extractions for the fictional debate page.
        """
        page_debat = None
        for page in pages_creees:
            if "Débat IA" in page.title:
                page_debat = page
                break
        if not page_debat:
            return
        self._creer_extractions_page(page_debat, EXTRACTIONS_DEBAT)

    def _creer_extractions_wikipedia(self, pages_creees):
        """
        Cree les extractions pre-calculees pour les pages Wikipedia.
        / Create pre-computed extractions for Wikipedia pages.
        """
        for titre_partiel, liste_extractions in EXTRACTIONS_PAR_TITRE.items():
            page_cible = None
            for page in pages_creees:
                if titre_partiel in page.title:
                    page_cible = page
                    break
            if page_cible:
                self._creer_extractions_page(page_cible, liste_extractions)

    def _ajouter_commentaires_debat(self, tous_les_users):
        """
        Ajoute les commentaires sur le debat fictif.
        Les statuts sont deja definis dans EXTRACTIONS_DEBAT lors de la creation.
        / Add comments on the fictional debate.
        Statuses are already set in EXTRACTIONS_DEBAT at creation time.
        """
        # Chercher la page du debat fictif par titre
        # / Find the fictional debate page by title
        page_debat = Page.objects.filter(
            title__icontains="Débat IA",
        ).first()
        if not page_debat:
            self.stdout.write("  Débat fictif : page introuvable, commentaires ignorés.")
            return

        # Recuperer le dernier job termine
        # / Get the latest completed job
        dernier_job = (
            ExtractionJob.objects
            .filter(page=page_debat, status="completed")
            .order_by("-created_at")
            .first()
        )
        if not dernier_job:
            self.stdout.write(f"  Débat fictif (pk={page_debat.pk}) : aucun job complété, commentaires ignorés.")
            return

        # Recuperer TOUTES les entites triees par position (y compris masquees/non_pertinent)
        # / Get ALL entities sorted by position (including hidden/non_pertinent)
        toutes_les_entites_du_job = list(
            dernier_job.entities.order_by("start_char")
        )
        if not toutes_les_entites_du_job:
            self.stdout.write(f"  Débat fictif (pk={page_debat.pk}) : aucune entité, commentaires ignorés.")
            return

        # Ajouter les commentaires / Add comments
        nombre_commentaires_crees = 0
        for index_entite, username_auteur, texte_commentaire in COMMENTAIRES_DEBAT:
            if index_entite >= len(toutes_les_entites_du_job):
                self.stdout.write(
                    f"  Index {index_entite} hors limites "
                    f"({len(toutes_les_entites_du_job)} entités), ignoré."
                )
                continue

            entite_cible = toutes_les_entites_du_job[index_entite]
            user_auteur = tous_les_users.get(username_auteur)
            if not user_auteur:
                continue

            # Eviter les doublons / Avoid duplicates
            commentaire_existe_deja = CommentaireExtraction.objects.filter(
                entity=entite_cible,
                user=user_auteur,
                commentaire=texte_commentaire,
            ).exists()
            if commentaire_existe_deja:
                continue

            CommentaireExtraction.objects.create(
                entity=entite_cible,
                user=user_auteur,
                commentaire=texte_commentaire,
            )
            nombre_commentaires_crees += 1

        self.stdout.write(self.style.SUCCESS(
            f"  Débat fictif (pk={page_debat.pk}) : {nombre_commentaires_crees} commentaires créés"
        ))

    def _ajouter_commentaires_pages_wikipedia(self, tous_les_users):
        """
        Ajoute des commentaires de demonstration sur les extractions des pages Wikipedia
        (Ostrom, Alexandre, Sadin) pour tester le filtre contributeur (PHASE-26a).
        / Add demo comments on Wikipedia page extractions
        (Ostrom, Alexandre, Sadin) to test the contributor filter (PHASE-26a).
        """
        nombre_total_commentaires_crees = 0

        # Grouper les commentaires par page (titre partiel)
        # / Group comments by page (partial title)
        commentaires_par_titre = {}
        for titre_partiel, index_entite, username_auteur, texte_commentaire in COMMENTAIRES_PAGES_WIKIPEDIA:
            if titre_partiel not in commentaires_par_titre:
                commentaires_par_titre[titre_partiel] = []
            commentaires_par_titre[titre_partiel].append(
                (index_entite, username_auteur, texte_commentaire)
            )

        for titre_partiel, liste_commentaires in commentaires_par_titre.items():
            # Chercher la page par titre partiel
            # / Find the page by partial title
            page_cible = Page.objects.filter(title__icontains=titre_partiel).first()
            if not page_cible:
                self.stdout.write(f"  Page '{titre_partiel}' : introuvable, commentaires ignorés.")
                continue

            # Recuperer le dernier job termine
            # / Get the latest completed job
            dernier_job = (
                ExtractionJob.objects
                .filter(page=page_cible, status="completed")
                .order_by("-created_at")
                .first()
            )
            if not dernier_job:
                self.stdout.write(f"  Page '{titre_partiel}' (pk={page_cible.pk}) : aucun job complété, commentaires ignorés.")
                continue

            # Recuperer les entites triees par position
            # / Get entities sorted by position
            toutes_les_entites_du_job = list(
                dernier_job.entities
                .filter(masquee=False)
                .order_by("start_char")
            )
            if not toutes_les_entites_du_job:
                self.stdout.write(f"  Page '{titre_partiel}' (pk={page_cible.pk}) : aucune entité, commentaires ignorés.")
                continue

            nombre_commentaires_page = 0
            for index_entite, username_auteur, texte_commentaire in liste_commentaires:
                if index_entite >= len(toutes_les_entites_du_job):
                    continue

                entite_cible = toutes_les_entites_du_job[index_entite]
                user_auteur = tous_les_users.get(username_auteur)
                if not user_auteur:
                    continue

                # Eviter les doublons / Avoid duplicates
                commentaire_existe_deja = CommentaireExtraction.objects.filter(
                    entity=entite_cible,
                    user=user_auteur,
                    commentaire=texte_commentaire,
                ).exists()
                if commentaire_existe_deja:
                    continue

                CommentaireExtraction.objects.create(
                    entity=entite_cible,
                    user=user_auteur,
                    commentaire=texte_commentaire,
                )
                nombre_commentaires_page += 1

                # Auto-promotion : nouveau/discutable → discute au premier commentaire
                # / Auto-promote: nouveau/discutable → discute on first comment
                if entite_cible.statut_debat in ("nouveau", "discutable"):
                    entite_cible.statut_debat = "discute"
                    entite_cible.save(update_fields=["statut_debat"])

            nombre_total_commentaires_crees += nombre_commentaires_page
            self.stdout.write(self.style.SUCCESS(
                f"  Page '{titre_partiel}' (pk={page_cible.pk}) : {nombre_commentaires_page} commentaires créés"
            ))

        self.stdout.write(self.style.SUCCESS(
            f"  Pages Wikipedia : {nombre_total_commentaires_crees} commentaires créés au total"
        ))

    def _creer_synthese_debat_v2(self, dossier, user_admin):
        """
        Cree une V2 du debat fictif — synthese integrant les points debattus.
        La V2 est liee a la V1 via parent_page. Idempotent.
        / Create a V2 of the fictional debate — synthesis integrating debated points.
        V2 is linked to V1 via parent_page. Idempotent.
        """
        # Retrouver la page V1 du debat
        # / Find the debate V1 page
        page_debat_v1 = Page.objects.filter(title__icontains="Débat IA").first()
        if not page_debat_v1:
            self.stdout.write("  Synthèse V2 : page débat V1 introuvable — ignorée")
            return

        # Verifier si la V2 existe deja
        # / Check if V2 already exists
        titre_v2 = "Débat IA — Synthèse délibérative"
        page_v2_existante = Page.objects.filter(title=titre_v2).first()
        if page_v2_existante:
            self.stdout.write(f"  Synthèse V2 existante : {titre_v2} (pk={page_v2_existante.pk})")
            return

        # Construire le HTML a partir du texte de synthese
        # / Build HTML from the synthesis text
        texte_synthese = TEXTE_SYNTHESE_DEBAT_V2.strip()
        html_synthese = _construire_html_depuis_texte(texte_synthese)

        # Creer la page V2 liee a la V1
        # / Create V2 page linked to V1
        page_synthese_v2 = Page.objects.create(
            title=titre_v2,
            html_original=f"<html><body>{html_synthese}</body></html>",
            html_readability=html_synthese,
            text_readability=texte_synthese,
            source_type="web",
            status="completed",
            dossier=dossier,
            owner=user_admin,
            parent_page=page_debat_v1,
            version_number=2,
            version_label="Synthèse délibérative",
        )

        self.stdout.write(self.style.SUCCESS(
            f"  Synthèse V2 créée : {titre_v2} (pk={page_synthese_v2.pk}, "
            f"parent=V1 pk={page_debat_v1.pk})"
        ))

    def _redistribuer_statuts_debat(self):
        """
        Redistribue les statuts de debat pour les pages HORS debat fictif.
        Le debat fictif a ses propres statuts cibles (STATUTS_CIBLES_DEBAT).
        - Entites avec commentaires → mix discute/discutable/consensuel/controverse
        - Entites sans commentaires → majorite nouveau, quelques non_pertinent
        / Redistribute debate statuses for pages OUTSIDE fictional debate.
        """

        # Exclure les entites du debat fictif (gerees par STATUTS_CIBLES_DEBAT)
        # / Exclude fictional debate entities (managed by STATUTS_CIBLES_DEBAT)
        page_debat = Page.objects.filter(title__icontains="Débat IA").first()
        ids_pages_debat = set()
        if page_debat:
            ids_pages_debat = set(
                ExtractionJob.objects
                .filter(page=page_debat)
                .values_list("pk", flat=True)
            )

        toutes_les_entites = ExtractedEntity.objects.all()
        if ids_pages_debat:
            toutes_les_entites = toutes_les_entites.exclude(job_id__in=ids_pages_debat)

        ids_avec_commentaires = set(
            CommentaireExtraction.objects
            .values_list("entity_id", flat=True)
            .distinct()
        )

        # Entites avec commentaires : repartir entre discute, consensuel, controverse
        # / Entities with comments: distribute between discute, consensuel, controverse
        statuts_avec_commentaires = ["discute", "discutable", "consensuel", "controverse"]
        compteur_avec = 0
        for entite in toutes_les_entites.filter(pk__in=ids_avec_commentaires):
            nouveau_statut = statuts_avec_commentaires[compteur_avec % len(statuts_avec_commentaires)]
            if entite.statut_debat != nouveau_statut:
                entite.statut_debat = nouveau_statut
                entite.save(update_fields=["statut_debat"])
            compteur_avec += 1

        # Entites sans commentaires : majorite nouveau, quelques non_pertinent
        # / Entities without comments: mostly nouveau, some non_pertinent
        compteur_sans = 0
        for entite in toutes_les_entites.exclude(pk__in=ids_avec_commentaires):
            if compteur_sans % 7 == 0 and compteur_sans > 0:
                # 1 sur 7 en non_pertinent / 1 out of 7 as non_pertinent
                nouveau_statut = "non_pertinent"
            else:
                nouveau_statut = "nouveau"
            if entite.statut_debat != nouveau_statut:
                entite.statut_debat = nouveau_statut
                entite.save(update_fields=["statut_debat"])
            compteur_sans += 1

        self.stdout.write(self.style.SUCCESS(
            f"  Statuts redistribués : {compteur_avec} avec commentaires, {compteur_sans} sans"
        ))
