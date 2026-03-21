"""
Template tags pour hypostasis_extractor.
/ Template tags for hypostasis_extractor.

LOCALISATION : hypostasis_extractor/templatetags/extractor_tags.py
"""
from django import template

from front.normalisation import _normaliser_texte

register = template.Library()


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
    Retourne un dict avec des cles normalisees pour le template _card_body.html :
        attr_0 = hypostase (liste separee par virgules)
        attr_1 = resume (texte libre, jamais splitte)
        attr_2 = statut de debat
        attr_3 = mots-cles (liste separee par virgules)

    L'ordre des cles dans le JSON varie selon les modeles LLM.
    On identifie chaque attribut par son nom (insensible a la casse et aux accents)
    plutot que par sa position.

    / Extract values from an ExtractedEntity's JSONField attributes.
    / Returns a dict with normalized keys for the _card_body.html template.
    / Attribute identification is by name (case/accent insensitive), not position.

    LOCALISATION : hypostasis_extractor/templatetags/extractor_tags.py
    """
    try:
        attributes_dict = entity.attributes or {}
    except (AttributeError, TypeError):
        attributes_dict = {}

    # Lecture directe des cles canoniques (normalisees au stockage)
    # / Direct read of canonical keys (normalized at storage time)
    hypostase = attributes_dict.get("hypostases", "")
    resume = attributes_dict.get("resume", "")
    statut = attributes_dict.get("statut", "")
    mots_cles = attributes_dict.get("mots_cles", "")

    # Fallback de compatibilite pour les entites non migrees :
    # si les 4 slots sont vides et le dict n'est pas vide, appliquer l'ancienne logique
    # / Compatibility fallback for non-migrated entities:
    # / if all 4 slots are empty and dict is not empty, apply legacy logic
    if not any([hypostase, resume, statut, mots_cles]) and attributes_dict:
        for cle_brute, valeur in attributes_dict.items():
            cle_normalisee = _normaliser_texte(cle_brute)

            if cle_normalisee in ("hypostase", "hypostases"):
                hypostase = valeur
            elif cle_normalisee in ("resume", "summary"):
                resume = valeur
            elif cle_normalisee in ("statut", "statut_debat", "status"):
                statut = valeur
            elif cle_normalisee in ("mots_cles", "keywords", "hashtags"):
                mots_cles = valeur
            else:
                if not hypostase:
                    hypostase = valeur
                elif not resume:
                    resume = valeur
                elif not statut:
                    statut = valeur
                elif not mots_cles:
                    mots_cles = valeur

    return [hypostase, resume, statut, mots_cles]


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
    hypostase_normalisee = _normaliser_texte(value)
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
    statut_normalise = _normaliser_texte(value)
    return STATUT_ICONES.get(statut_normalise, '')


@register.filter
def hypostase_definition(value):
    """
    Retourne la definition en 1 phrase d'une hypostase.
    / Returns the 1-phrase definition of a given hypostase.
    """
    if not value:
        return ''
    hypostase_normalisee = _normaliser_texte(value)
    return HYPOSTASE_DEFINITIONS.get(hypostase_normalisee, '')
