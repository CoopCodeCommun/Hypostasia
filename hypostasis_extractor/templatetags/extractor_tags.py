"""
Template tags pour hypostasis_extractor.
/ Template tags for hypostasis_extractor.

LOCALISATION : hypostasis_extractor/templatetags/extractor_tags.py
"""
import unicodedata

from django import template

register = template.Library()


def _normaliser_hypostase(valeur):
    """
    Normalise un nom d'hypostase : minuscule, sans accents.
    Ex: 'Théorie' → 'theorie', 'Phénomène' → 'phenomene'
    / Normalize a hypostase name: lowercase, no accents.
    """
    texte = str(valeur).strip().lower()
    # Decompose en caracteres de base + diacritiques, puis retire les diacritiques
    # / Decompose into base characters + diacritics, then strip diacritics
    texte_nfkd = unicodedata.normalize('NFKD', texte)
    return ''.join(c for c in texte_nfkd if not unicodedata.combining(c))


# Mapping de chaque hypostase vers sa famille de couleur (8 familles)
# / Mapping of each hypostase to its color family (8 families)
HYPOSTASE_VERS_FAMILLE = {
    # Epistemique — classification, axiome, theorie, definition, formalisme
    # / Epistemic — classification, axiom, theory, definition, formalism
    'classification': 'epistemique',
    'axiome': 'epistemique',
    'theorie': 'epistemique',
    'definition': 'epistemique',
    'formalisme': 'epistemique',
    # Empirique — phenomene, evenement, donnee, variable, indice
    # / Empirical — phenomenon, event, data, variable, clue
    'phenomene': 'empirique',
    'evenement': 'empirique',
    'donnee': 'empirique',
    'variable': 'empirique',
    'indice': 'empirique',
    # Speculatif — hypothese, conjecture, approximation
    # / Speculative — hypothesis, conjecture, approximation
    'hypothese': 'speculatif',
    'conjecture': 'speculatif',
    'approximation': 'speculatif',
    # Structurel — structure, invariant, dimension, domaine
    # / Structural — structure, invariant, dimension, domain
    'structure': 'structurel',
    'invariant': 'structurel',
    'dimension': 'structurel',
    'domaine': 'structurel',
    # Normatif — loi, principe, valeur, croyance
    # / Normative — law, principle, value, belief
    'loi': 'normatif',
    'principe': 'normatif',
    'valeur': 'normatif',
    'croyance': 'normatif',
    # Problematique — aporie, paradoxe, probleme
    # / Problematic — aporia, paradox, problem
    'aporie': 'problematique',
    'paradoxe': 'problematique',
    'probleme': 'problematique',
    # Mode/Variation — mode, variation, variance, paradigme
    # / Mode/Variation — mode, variation, variance, paradigm
    'mode': 'mode',
    'variation': 'mode',
    'variance': 'mode',
    'paradigme': 'mode',
    # Objet/Methode — objet, methode (famille par defaut)
    # / Object/Method — object, method (default family)
    'objet': 'objet',
    'methode': 'objet',
}

# Icones Unicode par statut de debat
# / Unicode icons per debate status
STATUT_ICONES = {
    'nouveau': '○',
    'consensuel': '●',
    'discutable': '◆',
    'discute': '▲',
    'controverse': '■',
    'non_pertinent': '—',
}

# Definitions en 1 phrase de chaque hypostase (memes cles normalisees que HYPOSTASE_VERS_FAMILLE)
# / One-sentence definitions for each hypostase (same normalized keys as HYPOSTASE_VERS_FAMILLE)
HYPOSTASE_DEFINITIONS = {
    # Epistemique / Epistemic
    'classification': 'Organisation des éléments en catégories distinctes selon des critères définis.',
    'axiome': 'Proposition admise sans démonstration, servant de fondement au raisonnement.',
    'theorie': 'Ensemble cohérent de propositions visant à expliquer un domaine de phénomènes.',
    'definition': 'Énoncé qui fixe le sens précis d\'un concept ou d\'un terme.',
    'formalisme': 'Système de notation ou de règles permettant une expression rigoureuse.',
    # Empirique / Empirical
    'phenomene': 'Fait observable qui se manifeste dans l\'expérience ou l\'observation.',
    'evenement': 'Occurrence singulière située dans le temps et l\'espace.',
    'donnee': 'Information brute recueillie par observation ou mesure.',
    'variable': 'Grandeur susceptible de prendre différentes valeurs dans un contexte donné.',
    'indice': 'Élément factuel orientant vers une interprétation ou une conclusion.',
    # Speculatif / Speculative
    'hypothese': 'Proposition provisoire avancée pour être testée ou discutée.',
    'conjecture': 'Affirmation plausible non démontrée, fondée sur l\'intuition ou l\'analogie.',
    'approximation': 'Évaluation approchée acceptant une marge d\'imprécision.',
    # Structurel / Structural
    'structure': 'Agencement interne des éléments d\'un système ou d\'un objet.',
    'invariant': 'Propriété qui reste stable malgré les transformations du système.',
    'dimension': 'Axe ou paramètre définissant un espace de variation.',
    'domaine': 'Champ délimité de connaissances ou d\'application.',
    # Normatif / Normative
    'loi': 'Règle prescriptive ou descriptive à portée générale.',
    'principe': 'Énoncé fondamental guidant l\'action ou le raisonnement.',
    'valeur': 'Idéal ou critère de jugement orientant les choix et les évaluations.',
    'croyance': 'Conviction tenue pour vraie sans nécessairement reposer sur une preuve.',
    # Problematique / Problematic
    'aporie': 'Difficulté logique apparemment insoluble qui bloque le raisonnement.',
    'paradoxe': 'Énoncé qui contredit l\'intuition ou engendre une contradiction apparente.',
    'probleme': 'Question ouverte appelant une résolution ou une investigation.',
    # Mode/Variation
    'mode': 'Manière particulière dont un phénomène se manifeste.',
    'variation': 'Écart ou changement par rapport à un état de référence.',
    'variance': 'Mesure de la dispersion des valeurs autour d\'une tendance centrale.',
    'paradigme': 'Cadre conceptuel dominant qui structure la pensée d\'une époque.',
    # Objet/Methode
    'objet': 'Entité distincte sur laquelle porte l\'analyse ou l\'étude.',
    'methode': 'Procédure systématique adoptée pour atteindre un objectif de connaissance.',
}


@register.simple_tag
def extraction_attr(extraction, index):
    """
    Retourne la valeur de l'attribut a l'index donne (par order) d'une ExampleExtraction.
    Usage: {% extraction_attr extraction 0 as attr_val %}
    / Returns the value of the attribute at the given index (by order).
    """
    try:
        index = int(index)
        attrs = extraction.attributes.all()
        # attributes.all() est ordonne par Meta.ordering = ['order']
        if index < len(attrs):
            return attrs[index].value
    except (ValueError, AttributeError):
        pass
    return ""


@register.simple_tag
def extraction_attr_key(extraction, index):
    """
    Retourne la cle de l'attribut a l'index donne.
    Usage: {% extraction_attr_key extraction 0 as attr_key %}
    / Returns the key of the attribute at the given index.
    """
    try:
        index = int(index)
        attrs = extraction.attributes.all()
        if index < len(attrs):
            return attrs[index].key
    except (ValueError, AttributeError):
        pass
    return ""


@register.simple_tag
def entity_json_attrs(entity):
    """
    Extrait les valeurs du JSONField attributes d'une ExtractedEntity.
    Retourne une liste de 4 elements (valeurs dans l'ordre des cles, padde avec "").
    Usage: {% entity_json_attrs entity as entity_attrs %}
    / Extract values from an ExtractedEntity's JSONField attributes.
    Returns a list of 4 elements (values in key order, padded with "").
    """
    try:
        attributes_dict = entity.attributes or {}
        values_list = list(attributes_dict.values())
    except (AttributeError, TypeError):
        values_list = []

    # Pad a 4 elements pour attr_0..attr_3
    # Pad to 4 elements for attr_0..attr_3
    while len(values_list) < 4:
        values_list.append("")

    return values_list[:4]


@register.filter
def split_comma(value):
    """
    Splitte une chaine par virgule et strip les espaces.
    Usage: {{ value|split_comma }}
    / Split a string by comma and strip whitespace.
    """
    if not value:
        return []
    return [v.strip() for v in str(value).split(',') if v.strip()]


@register.filter
def hypostase_famille(value):
    """
    Retourne le nom de famille CSS pour une hypostase donnee.
    Sert a construire les noms de variables CSS : var(--hypostase-{famille}-bg).
    Famille par defaut : 'objet'.
    Usage: {{ tag|hypostase_famille }}
    / Returns the CSS family name for a given hypostase.
    Used to build CSS variable names: var(--hypostase-{family}-bg).
    Default family: 'objet'.
    """
    if not value:
        return 'objet'
    hypostase_normalisee = _normaliser_hypostase(value)
    return HYPOSTASE_VERS_FAMILLE.get(hypostase_normalisee, 'objet')


@register.filter
def statut_icone(value):
    """
    Retourne l'icone Unicode associee a un statut de debat.
    Usage: {{ attr_2|statut_icone }}
    / Returns the Unicode icon for a debate status.
    """
    if not value:
        return ''
    statut_normalise = _normaliser_hypostase(value)
    return STATUT_ICONES.get(statut_normalise, '')


@register.filter
def hypostase_definition(value):
    """
    Retourne la definition en 1 phrase d'une hypostase.
    / Returns the 1-phrase definition of a given hypostase.
    """
    if not value:
        return ''
    hypostase_normalisee = _normaliser_hypostase(value)
    return HYPOSTASE_DEFINITIONS.get(hypostase_normalisee, '')
