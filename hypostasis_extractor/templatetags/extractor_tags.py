"""
Template tags pour hypostasis_extractor.
/ Template tags for hypostasis_extractor.
"""
from django import template

register = template.Library()


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
