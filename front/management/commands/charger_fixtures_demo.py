"""
Charge les fixtures de demonstration : users + 3 pages Wikipedia (Ostrom, Alexandre, Sadin)
+ commentaires sur les extractions existantes de la page 69.
/ Load demo fixtures: users + 3 Wikipedia pages (Ostrom, Alexandre, Sadin)
/ + comments on existing extractions from page 69.

LOCALISATION : front/management/commands/charger_fixtures_demo.py

Usage :
    uv run python manage.py charger_fixtures_demo
    uv run python manage.py charger_fixtures_demo --reset  (supprime et recree)
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from core.models import Dossier, DossierPartage, Page, VisibiliteDossier
from hypostasis_extractor.models import (
    CommentaireExtraction,
    ExtractedEntity,
    ExtractionJob,
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

Libération décrit le philosophe comme vu par les uns comme un prophète de malheur et par les autres comme un lanceur d'alerte extralucide. La question posée est vertigineuse : que va-t-il rester à l'humanité quand les assistés numériques que nous sommes délégueront totalement l'apprentissage, la création et la formation du savoir à des machines ?

Parmi ses ouvrages essentiels : Surveillance globale (2009), La Vie algorithmique (2015), La Silicolonisation du monde (2016), L'Intelligence artificielle ou l'enjeu du siècle (2018), L'Ère de l'individu tyran (2020), Faire sécession (2021), La Vie spectrale (2023), Le Désert de nous-mêmes (2025)."""


# =============================================================================
# Users de demonstration (PHASE-25)
# / Demo users (PHASE-25)
# =============================================================================

USERS_DEMO = [
    {"username": "marie", "first_name": "Marie", "password": "demo1234"},
    {"username": "thomas", "first_name": "Thomas", "password": "demo1234"},
    {"username": "fatima", "first_name": "Fatima", "password": "demo1234"},
    {"username": "pierre", "first_name": "Pierre", "password": "demo1234"},
]

USER_ADMIN = {"username": "jonas", "first_name": "Jonas", "password": "admin1234", "is_staff": True}


# =============================================================================
# Commentaires de demonstration sur les extractions de la page 69
# Les commentaires representent des reactions de lecteurs fictifs
# / Demo comments on page 69 extractions
# / Comments represent reactions from fictional readers
# =============================================================================

COMMENTAIRES_DEMO = [
    # (index_entite_dans_job, username, commentaire)
    # index 0 = premiere entite du job triee par start_char

    # Entite "L'IA est la revolution la plus importante..."
    (0, "marie", "Comparer l'IA à l'écriture est une hyperbole rhétorique, pas un argument. L'écriture a transformé la cognition humaine sur des millénaires. L'IA automatise des tâches en quelques années. Ce n'est pas le même type de rupture."),
    (0, "thomas", "Je suis plutôt d'accord avec cette analyse. L'IA modifie notre rapport au savoir de manière fondamentale — c'est bien une révolution épistémique, pas seulement technique."),
    (0, "fatima", "Ostrom dirait que la question n'est pas de savoir si c'est une révolution, mais qui gouverne cette révolution et selon quelles règles."),

    # Entite "Les pays qui n'investissent pas massivement..."
    (1, "pierre", "C'est exactement le discours de Laurent Alexandre : la course technologique comme fatalité. Mais Sadin a montré que cette rhétorique guerrière sert les intérêts des GAFAM, pas ceux des peuples."),
    (1, "marie", "La compétition entre nations sur l'IA est un fait, pas une opinion. Le nier serait naïf."),

    # Entite "On nous présente l'IA comme une fatalité historique..."
    (2, "thomas", "C'est le cœur de la thèse de Sadin dans La Silicolonisation du monde : l'IA comme choix politique déguisé en progrès inévitable."),
    (2, "fatima", "Attention à ne pas tomber dans l'excès inverse : dire que tout est choix politique peut mener à l'inaction face à des transformations réelles."),

    # Entite "Je crois qu'il y a une troisième voie..."
    (4, "pierre", "Cette troisième voie rappelle directement les travaux d'Ostrom sur les communs : ni marché pur, ni État centralisé, mais auto-gouvernement avec des règles claires."),
    (4, "marie", "Belle idée en théorie, mais comment gouverner collectivement un modèle d'IA qui nécessite des milliards d'investissement ? Les communs d'Ostrom portaient sur des pâturages, pas sur des data centers."),
    (4, "thomas", "Les logiciels libres prouvent que c'est possible à grande échelle. Linux fait tourner 90% des serveurs mondiaux."),

    # Entite "Un commun numérique, c'est charmant en théorie..."
    (6, "fatima", "C'est la position de Laurent Alexandre résumée en une phrase. Il faudrait confronter cela aux 8 principes d'Ostrom pour voir si l'objection tient."),
    (6, "pierre", "Réponse typiquement techno-solutionniste. Ostrom a justement prouvé que des communautés gèrent des ressources communes depuis des siècles — le pessimisme de Hardin sur la « tragédie des communs » est une prophétie auto-réalisatrice."),

    # Entite "L'augmentation cognitive n'est pas une option..."
    (7, "marie", "Sadin qualifierait cela d'« antihumanisme radical » — réduire l'humain à un problème d'optimisation cognitive."),
    (7, "thomas", "C'est un argument darwinien : s'adapter ou disparaître. Mais l'humanité ne se réduit pas à la compétition."),

    # Entite "l'IA est un outil d'empuissancement formidable si..."
    (27, "pierre", "C'est exactement la position d'Ostrom appliquée au numérique. La condition « si et seulement si » est cruciale — elle distingue cette position du techno-optimisme naïf."),
    (27, "fatima", "Je trouve cette formulation trop conciliante. Sadin dirait qu'on ne « gouverne » pas une technologie conçue pour nous gouverner."),
    (27, "marie", "Position de compromis intéressante mais qui sous-estime la vitesse de déploiement de l'IA. Les institutions de gouvernance sont toujours en retard sur la technologie."),

    # Entite "Ni la course technologique débridée... ni le refus radical..."
    (28, "thomas", "C'est la synthèse parfaite du débat. Mais dans la pratique, le « juste milieu » est souvent un vœu pieux."),

    # Entite "C'est possible, et c'est notre responsabilité de le faire."
    (30, "pierre", "Ostrom a consacré sa carrière à prouver que c'est possible. La question est : avons-nous le temps de construire ces institutions avant que l'IA ne soit partout ?"),
    (30, "fatima", "J'entends l'optimisme mais Sadin nous rappelle qu'il reste « deux ou trois ans pour agir ». L'urgence devrait primer sur l'espoir."),
]


# =============================================================================
# Commentaires sur les pages Wikipedia (PHASE-26a)
# Ajoutes pour tester le filtre contributeur avec des donnees reelles.
# Chaque tuple = (titre_page_partiel, index_entite, username, commentaire)
# / Comments on Wikipedia pages (PHASE-26a)
# / Added to test the contributor filter with real data.
# / Each tuple = (partial_page_title, entity_index, username, comment)
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


class Command(BaseCommand):
    help = (
        "Charge les fixtures de démonstration : users + 3 pages Wikipedia "
        "(Ostrom, Alexandre, Sadin) + commentaires sur les extractions."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Supprime les pages demo existantes avant de les recréer.",
        )

    def handle(self, *args, **options):
        mode_reset = options.get("reset", False)
        nom_dossier = "Petits textes"

        # 1. Creer les users demo / Create demo users
        tous_les_users_demo = self._creer_users_demo()
        user_admin = tous_les_users_demo.get("jonas")

        # 2. Recupere ou cree le dossier cible avec owner, visibilite publique (PHASE-26a)
        # / Get or create target folder with owner, public visibility (PHASE-26a)
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

        # 3. Creer un partage demo : dossier "Petits textes" partage avec marie
        # / Create a demo share: "Petits textes" folder shared with marie
        user_marie = tous_les_users_demo.get("marie")
        if user_marie:
            DossierPartage.objects.get_or_create(
                dossier=dossier, utilisateur=user_marie,
            )
            self.stdout.write(f"  Partage : {nom_dossier} → marie")

        # 4. Definition des 3 pages a creer
        # / Definition of the 3 pages to create
        pages_a_creer = [
            {
                "title": "Elinor Ostrom — Gouvernance des communs",
                "texte": TEXTE_OSTROM,
                "url": "https://fr.wikipedia.org/wiki/Elinor_Ostrom",
            },
            {
                "title": "Laurent Alexandre — Accélération technologique",
                "texte": TEXTE_ALEXANDRE,
                "url": "https://fr.wikipedia.org/wiki/Laurent_Alexandre",
            },
            {
                "title": "Éric Sadin — Critique de la technologie",
                "texte": TEXTE_SADIN,
                "url": "https://fr.wikipedia.org/wiki/%C3%89ric_Sadin",
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
                # Mettre a jour l'owner si absent / Update owner if missing
                if not page_existante.owner and user_admin:
                    page_existante.owner = user_admin
                    page_existante.save(update_fields=["owner"])
                self.stdout.write(f"  Page existante : {titre} (pk={page_existante.pk})")
                pages_creees.append(page_existante)
                continue

            # Cree la page avec le texte Wikipedia + owner
            # / Create page with Wikipedia text + owner
            texte_brut = definition_page["texte"].strip()
            html_readability = _construire_html_depuis_texte(texte_brut)

            page_nouvelle = Page.objects.create(
                title=titre,
                url=definition_page["url"],
                html_original=f"<html><body>{html_readability}</body></html>",
                html_readability=html_readability,
                text_readability=texte_brut,
                source_type="web",
                status="completed",
                dossier=dossier,
                owner=user_admin,
            )
            self.stdout.write(self.style.SUCCESS(
                f"  Page créée : {titre} (pk={page_nouvelle.pk})"
            ))
            pages_creees.append(page_nouvelle)

        # 5. Ajoute les commentaires sur les extractions de la page 69
        # / Add comments on page 69 extractions
        self._ajouter_commentaires_page_69(tous_les_users_demo)

        # 6. Ajoute les commentaires sur les pages Wikipedia (PHASE-26a)
        # / Add comments on Wikipedia pages (PHASE-26a)
        self._ajouter_commentaires_pages_wikipedia(tous_les_users_demo)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Fixtures chargées : {len(pages_creees)} pages dans « {nom_dossier} »"
        ))
        self.stdout.write(
            "  Lancez l'analyse IA sur chaque page pour générer les extractions :"
        )
        for page in pages_creees:
            self.stdout.write(f"    → /lire/{page.pk}/analyser/")

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
                },
            )
            if cree:
                utilisateur.set_password(definition_user["password"])
                utilisateur.save()
                self.stdout.write(self.style.SUCCESS(
                    f"  User créé : {utilisateur.username}"
                ))
            else:
                self.stdout.write(f"  User existant : {utilisateur.username}")
            tous_les_users[utilisateur.username] = utilisateur

        # User admin / Admin user
        admin_definition = USER_ADMIN
        utilisateur_admin, cree = User.objects.get_or_create(
            username=admin_definition["username"],
            defaults={
                "first_name": admin_definition["first_name"],
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
            self.stdout.write(f"  User admin existant : {utilisateur_admin.username}")
        tous_les_users[utilisateur_admin.username] = utilisateur_admin

        return tous_les_users

    def _ajouter_commentaires_page_69(self, tous_les_users):
        """
        Ajoute des commentaires de demonstration sur les extractions de la page 69.
        Utilise les User objects au lieu des prenoms string.
        / Add demo comments on page 69 extractions.
        Uses User objects instead of string first names.
        """
        # Recupere le dernier job termine de la page 69
        # / Get the latest completed job for page 69
        dernier_job_page_69 = (
            ExtractionJob.objects
            .filter(page_id=69, status="completed")
            .order_by("-created_at")
            .first()
        )
        if not dernier_job_page_69:
            self.stdout.write("  Page 69 : aucun job complété, commentaires ignorés.")
            return

        # Recupere les entites triees par position dans le texte
        # / Get entities sorted by position in text
        toutes_les_entites_du_job = list(
            dernier_job_page_69.entities
            .filter(masquee=False)
            .order_by("start_char")
        )

        if not toutes_les_entites_du_job:
            self.stdout.write("  Page 69 : aucune entité, commentaires ignorés.")
            return

        nombre_commentaires_crees = 0
        for index_entite, username_auteur, texte_commentaire in COMMENTAIRES_DEMO:
            # Verifie que l'index est valide
            # / Check index is valid
            if index_entite >= len(toutes_les_entites_du_job):
                self.stdout.write(
                    f"  Index {index_entite} hors limites "
                    f"({len(toutes_les_entites_du_job)} entités), ignoré."
                )
                continue

            entite_cible = toutes_les_entites_du_job[index_entite]

            # Recupere le user correspondant au username
            # / Get the user matching the username
            user_auteur = tous_les_users.get(username_auteur)
            if not user_auteur:
                self.stdout.write(f"  User '{username_auteur}' introuvable, commentaire ignoré.")
                continue

            # Verifie qu'un commentaire identique n'existe pas deja
            # / Check that an identical comment doesn't already exist
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
            f"  Page 69 : {nombre_commentaires_crees} commentaires créés"
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

            nombre_total_commentaires_crees += nombre_commentaires_page
            self.stdout.write(self.style.SUCCESS(
                f"  Page '{titre_partiel}' (pk={page_cible.pk}) : {nombre_commentaires_page} commentaires créés"
            ))

        self.stdout.write(self.style.SUCCESS(
            f"  Pages Wikipedia : {nombre_total_commentaires_crees} commentaires créés au total"
        ))
