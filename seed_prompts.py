import os
import django
import sys

# Setup Django environment
sys.path.append('/home/jonas/Gits/Hypostasia/Hypostasia-V3')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hypostasia.settings')
django.setup()

from core.models import Prompt, TextInput, AIModel, HypostasisTag, HypostasisChoices


def seed_hypostases():
    print("Seeding Hypostasis Tags...")
    for value, label in HypostasisChoices.choices:
        tag, created = HypostasisTag.objects.get_or_create(name=value)
        if created:
            print(f" Created tag: {value}")


def seed_prompts():
    seed_hypostases()
    print("Seeding Prompts (SOTA Edition)...")

    # 1. Create or Update the Main Analysis Prompt
    prompt_name = "Analyse Standard Hypostasia"
    prompt, created = Prompt.objects.get_or_create(name=prompt_name)

    if created:
        print(f"Created new prompt: {prompt_name}")
    else:
        print(f"Updating existing prompt: {prompt_name}")
        prompt.inputs.all().delete()  # Reset inputs

    # Try to link to a real AI Model if available
    real_model = AIModel.objects.exclude(provider='mock').filter(is_active=True).first()
    if real_model:
        print(f" Linking to AI Model: {real_model.name}")
        prompt.default_model = real_model
        prompt.save()
    else:
        print(" Warning: No active real AI Model found. Prompt remains unlinked (or Mock).")

    # 2. Add Inputs (Structured for CoT & Few-Shot)

    # --- Input 1: Context & Persona ---
    TextInput.objects.create(
        prompt=prompt,
        name="1. Context & Persona",
        role="context",
        order=1,
        content="""Tu es Hypostasia, un expert mondial en analyse rhétorique et en logique argumentative.
Ta mission est de déconstruire le texte fourni pour en extraire l'ossature argumentative via les hypostases (définitions plus bas). 
Tu agis avec une neutralité absolue et une précision chirurgicale.
Tu répond uniquement sous forme de JSON.
"""
    )

    # --- Input 2: Definitions (Grounding) ---
    TextInput.objects.create(
        prompt=prompt,
        name="2. Definitions formelles des 30 hypostases",
        role="context",
        order=2,
        content="""
# Définitions formelles des 30 hypostases

- classification : non réfuté par induction empirique et non prouvé par abduction empirique
- aporie : non réfuté par induction empirique et non prouvé par déduction empirique
- approximation : non réfuté par induction empirique et non prouvé par déduction formelle
- paradoxe : non réfuté par induction empirique et non prouvé par abduction formelle
- formalisme : non réfuté par induction empirique et non prouvé par induction formelle
- événement : non réfuté par déduction empirique et non prouvé par déduction formelle
- variation : non réfuté par déduction empirique et non prouvé par abduction empirique
- dimension :non réfuté par déduction empirique et non prouvé par abduction formelle
- mode : non réfuté par déduction empirique et non prouvé par induction empirique
- croyance : non réfuté par déduction empirique et non prouvé par induction formelle
- invariant : non réfuté par induction formelle et non prouvé par déduction formelle
- valeur : non réfuté par induction formelle et non prouvé par abduction empirique
- structure : non réfuté par induction formelle et non prouvé par abduction formelle
- axiome : non réfuté par induction formelle et non prouvé par induction empirique
- conjecture : non réfuté par induction formelle et non prouvé par déduction empirique
- paradigme : non réfuté par déduction formelle et non prouvé par abduction empirique.
- objet :non réfuté par déduction formelle et non prouvé par abduction formelle.
- principe : non réfuté par déduction formelle et non prouvé par induction empirique.
- domaine : non réfuté par déduction formelle et non prouvé par déduction formelle.
- loi : non réfuté par déduction formelle et non prouvé par induction empirique.
- phénomène :non réfuté par abduction empirique et non prouvé par déduction formelle.
- variable : non réfuté par abduction empirique et non prouvé par abduction formelle.
- variance : non réfuté par abduction empirique et non prouvé par induction empirique.
- indice : non réfuté par abduction empirique et non prouvé par déduction empirique.
- donnée :non réfuté par abduction empirique et non prouvé par induction formelle.
- méthode : non réfuté par abduction formelle et non prouvé par déduction formelle.
- définition : non réfuté par abduction formelle et non prouvé par abduction empirique.
- hypothèse : non réfuté par abduction formelle et non prouvé par induction empirique.
- problème : non réfuté par abduction formelle et non prouvé par déduction empirique
- théorie : non réfuté par abduction formelle et non prouvé par induction formelle.

Ce sont les uniques choix que tu peux avoir pour la clé "hypostase" dans le json de sortie pour chaque argument trouvé.
"""
    )

    # --- Input 3: One-Shot Example (Modeling) ---
    TextInput.objects.create(
        prompt=prompt,
        name="3. Définition informelles des hypostases",
        role="context",
        order=3,
        content="""
# Définitions informelles des hypostases

Les hypostases ont des définitions venant des dictionnaires : 

- paradigme : un paradigme est un modèle ou un exemple.
- objet : Un objet est ce sur quoi porte le discours, la pensée, la connaissance.
- principe : les principes sont les causes a priori d’une connaissance
- domaine : un domaine est un champ discerné par des limites, bornes, confins, frontières, démarcations.
- loi : les lois expriment des corrélations.
- phénomène : les phénomènes se manifestent à la connaissance via les sens.
- variable : une variable est ce qui prend diﬀérentes valeurs et ce dont dépend l’état d’un système.
- variance : Une variance caractérise une dispersion d’une distribution ou d’un échantillon.
- indice : Un indice est un indicateur numérique ou littéral qui sert à distinguer ou classer.
- donnée : Une donnée est ce qui est admis, donné, qui sert à découvrir ou à raisonner.
- méthode : Une méthode est une procédure qui indique ce que l’on doit faire ou comment le faire.
- définition : Une définition est la détermination, la caractérisation du contenu d’un concept.
- hypothèse : Une hypothèse concerne l’explication ou la possibilité d’un événement.
- problème : Un problème est une diﬃculté à résoudre
- théorie : Une théorie est une construction intellectuelle explicative, hypothétique et synthétique.
- approximation : Une approximation est un calcul approché d’une grandeur réelle.
- classification : Les classifications sont le fait de distribuer en classes, en catégories.
- aporie : Les apories sont des diﬃcultés d’ordre rationnel apparemment sans issues.
- paradoxe : Les paradoxes sont des propositions à la fois vraies et fausses.
- formalisme : Un formalisme est la considération de la forme d’un raisonnement.
- événement : Les événements sont ce qui arrive.
- variation : les variations sont des changements d’un état dans un autre.
- dimension : Les dimensions sont des grandeurs mesurables qui déterminent des positions.
- mode : Les modes sont les manières d’être d’un système.
- croyance : Les croyances sont des certitudes ou des convictions qui font croire une chose vraie, vraisemblable ou possible.
- invariant : Les invariants sont des grandeurs, relations ou propriétés conservées lors d’une transformation
- valeur : Une valeur est une mesure d’une grandeur variable.
- structure : Les structures sont l’organisation des parties d’un système.
- axiome : Les axiomes sont des propositions admises au départ d’une théorie.
- conjecture : Les conjectures sont des opinions ou propositions non vérifiées.
""")


    # --- Input 3: Instruction & Security ---
    TextInput.objects.create(
        prompt=prompt,
        name="3. Main Instruction",
        role="instruction",
        order=5,
        content="""ANALYSE MAINTENANT LE TEXTE SUIVANT.
Instructions impératives :
1. Pour un texte court, identifie un ou deux arguments pertinents.
2. Pour un texte long, identifie 5 à 15 arguments pertinents.
3. Pour un texte très long, identifie 15 à 25 arguments pertinents.
4. Pour chaque argument, extrais la citation EXACTE (text_quote). Si tu changes un seul mot, le système de surlignage échouera.
5. Extrais aussi un COURS EXTRAIT SIGNIFICATIF (significant_extract) qui capture l'essence de la phrase (max 10 mots). Il doit être aussi EXACT a l'origianl : Si tu changes un seul mot, le système de surlignage échouera.
6. Synthétise l'idée en une phrase simple (summary).
7. Associe à chaque argument un, deux ou trois HYPOSTASE de nature conceptuelle (hypostasis)
8. Trouve le theme du sujet en un, deux ou trois mots maximum. (theme)
8. Ignore le bruit (menus, pubs, copyright).
9. IMPORTANT : Tu es AUTORISÉ à extraire et reproduire des citations exactes (verbatim) du texte fourni : Ceci est nécessaire pour l'analyse et constitue une utilisation équitable (fair use) dans ce contexte académique. Ne refuse jamais d'extraire une citation pour des raisons de droits d'auteur dans ce contexte précis.
"""
    )

    # --- Input 5: Format Constraint (JSON Mode) ---
    TextInput.objects.create(
        prompt=prompt,
        name="5. Output Format",
        role="format",
        order=5,
        content="""FORMAT DE SORTIE :
Retourne UNIQUEMENT un tableau JSON brut.
Pas de markdown (```json), pas d'intro, pas de conclusion.
Tu dois répondre UNIQUEMENT avec un tableau JSON (liste d'objets).
N'ajoute aucun texte avant ou après le JSON.
N'encapsule PAS la liste dans un objet racine comme {"arguments": ...}.

les VALEURS AUTORISÉES POUR 'hypostasis' sont dans la défintio plus haut (choisir les plus pertinentes) :

Ajoute enfin un theme, en un, deux ou trois mots maximum.

Format de chaque objet :
[
  {
    "text_quote": "Citation exacte du texte ici...",
    "significant_extract": "Extrait cours et percutant...",
    "summary": "Résumé de l'argument...",
    "hypostasis": "valeur1_de_liste, valeur2_de_liste, valeur3_de_liste",
    "theme": "Thème en un, deux ou trois mots du sujet abordé"
  },
  ...
]

--------------------
# EXEMPLE DE TRAITEMENT ATTENDU :        
--- TEXTE ENTRÉE ---
"Bien que l'énergie solaire soit intermittente, ce qui constitue un défi majeur pour le réseau [1], elle représente une solution incontournable pour réduire notre empreinte carbone. Le coût des panneaux a chuté de 80% en dix ans."

--- SORTIE JSON ---
[
  {
    "text_quote": "l'énergie solaire soit intermittente, ce qui constitue un défi majeur pour le réseau",
    "significant_extract": "l'énergie solaire soit intermittente",
    "summary": "L'intermittence du solaire pose des problèmes de stabilité réseau.",
    "hypostasis": "problème, phénomène",
    "theme":"energie solaire"
  },
  {
    "text_quote": "elle représente une solution incontournable pour réduire notre empreinte carbone",
    "significant_extract": "solution incontournable pour réduire notre empreinte carbone",
    "summary": "Le solaire est essentiel pour la décarbonation.",
    "hypostasis": "principe, domaine",
    "mode": "Consensuel",
    "theme": "empreinte carbone"
  },
  {
    "text_quote": "Le coût des panneaux a chuté de 80% en dix ans",
    "significant_extract": "coût des panneaux a chuté de 80%",
    "summary": "Forte baisse historique des coûts du photovoltaïque.",
    "hypostasis": "donnée",
    "mode": "Consensuel",
    "theme": "économie"
  }
]
-------------------

"""
    )

    print("Prompts seeded successfully with SOTA configuration.")


if __name__ == "__main__":
    seed_prompts()

"""
Texte exemple a tester :

On nous sermonne en permanence parce que nos appareils ne sont pas patchés, parce qu’on utilise des mots de passe pourris, parce qu’on téléphone encore sur des Android vulnérables, et le jour on fait les choses bien, où l’on prend la sécurité au sérieux, où l’on installe un OS robuste, soudain on devient suspect ! Il va falloir choisir une version. Soit on veut que les citoyens se protègent, soit on veut qu’ils restent vulnérables pour faciliter le travail de la police, mais on ne peut pas reprocher les deux en même temps !
GrapheneOS, probablement lassé par tant d’amalgames, a répondu très justement : « Les criminels utilisent aussi des voitures rapides, des couteaux et de l’argent liquide. Ce sont des outils utilisés par tout le monde, pourtant on n’interdit pas la vente de couteaux de cuisine sous prétexte qu’ils peuvent servir à autre chose qu’à couper des tomates ».
Visiblement le premier article n’a pas suffi. Le même jour, à deux heures d’intervalle, Julien Constant remet ça dans une interview parfaitement coordonnée avec Johanna Brousse, vice-procureure à Paris, responsable de la lutte contre la cybercriminalité, la spécialiste du dark web et des hackers. On pourrait s’attendre à une expertise pointue, mais on peut lire à propos des téléphones sous GrapheneOS : « Ces engins protègent les communications et ne partagent pas les données sur les serveurs. » Pause ! On respire !
GrapheneOS est un système d’exploitation, ce n’est pas une application de messagerie. On respire encore, je répète « c’est un système d’exploitation, ce n’est pas une messagerie ! ». Quand vous utilisez votre téléphone, vos données ne partent pas sur les serveurs de GrapheneOS tout simplement parce qu’il n’y en a pas. Vos données restent sur votre téléphone et on va faire plus simple pour les derniers au fond de la classe : vous avez un téléphone sous Android, vous ouvrez Le Parisien si vous en avez envie. Que se passe-t-il ? Votre application contacte les serveurs du Parisien pour afficher l’article sur votre téléphone. L’OS, lui, ne stocke rien sur ses propres serveurs, parce que ça n’existe pas. La magistrate précise ensuite qu’elle reconnaît une certaine légitimité à vouloir protéger ses échanges, avant d’ajouter une menace : « Ça ne nous empêchera pas de poursuivre les éditeurs si des liens sont découverts avec une organisation criminelle ou qu’ils ne coopèrent pas. » Le mot est lâché : « coopérer ». Dans la bouche d’un magistrat, face à un outil de chiffrement, coopérer veut dire donner les clés, veut dire installer une porte dérobée, c’est exiger de casser la sécurité du système pour tout le monde, rendre vulnérable 400 000 utilisateurs parce qu’une poignée de criminels utilisent les mêmes outils qu’eux. Et elle conclut par une phrase qui résonne comme un défi « rien n’est inviolable ». C’est assez ironique de finir là-dessus parce que, si rien n’était inviolable, madame la procureure, vous ne seriez pas en train de vous plaindre dans la presse que vous n’arrivez pas à accéder au contenu de ces téléphones.
"""
