"""
Tag de template pour la lecture par elements (BR-D).
/ Template tag for element-based reading.

LOCALISATION : front/templatetags/rendu_moteur.py

lecture_principale.html est rendu depuis PLUS DE SIX endroits
(retrieve, job en cours, post-action, renommage, import...). Injecter
`blocs_de_lecture` dans chaque contexte garantirait l'oubli — le meme
piege que corpus_permissions a resolu pour est_proprietaire. Le tag
applique donc LA MEME regle partout, au seul endroit qui affiche.
/ lecture_principale.html is rendered from 6+ places; a template tag
applies the same rule everywhere, at the single place that displays.
"""

from django import template

from core.models import MoteurDePage

register = template.Library()


@register.simple_tag(name="blocs_de_lecture_de")
def blocs_de_lecture_de(page):
    """
    Les blocs a afficher pour une page ELEMENT, sinon une liste vide.
    / The display blocks for an ELEMENT page, else an empty list.

    Usage : {% blocs_de_lecture_de page as blocs_de_lecture %}

    Une page ELEMENT sans aucun element (ingestion echouee) rend une
    liste vide : le template retombe alors sur html_readability, rempli
    par le pipeline synchrone (BR-B) — jamais une page blanche.
    / A zero-element ELEMENT page falls back to readability HTML.
    """
    if page is None or page.moteur != MoteurDePage.ELEMENT:
        return []

    from front.services.rendu_elements import construire_les_blocs_de_lecture

    return construire_les_blocs_de_lecture(page)
