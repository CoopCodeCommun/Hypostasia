"""
Filtres de template pour les permissions de la couche corpus.
/ Template filters for corpus layer permissions.

LOCALISATION : front/templatetags/corpus_permissions.py

Permet aux templates d'utiliser LA MEME regle que les endpoints, sans
injecter est_proprietaire dans tous les contextes de rendu (8 endroits
pour lecture_principale.html). Avant la phase D, le template comparait
request.user a page.dossier.owner (FK) pendant que l'endpoint utilisait
_est_proprietaire_page : le bouton et le droit divergeaient (relecture D).
/ Lets templates use THE SAME rule as the endpoints; before phase D the
template compared against the FK owner while the endpoint used
_est_proprietaire_page — button and right diverged.
"""

from django import template

register = template.Library()


@register.filter(name="est_moderable_par")
def est_moderable_par(page, utilisateur):
    """
    Vrai si l'utilisateur est proprietaire de la note (owner de la note
    OU owner d'un carnet qui la contient — SPEC-corpus § 5.2).
    / True if the user owns the note or one of its notebooks.

    Usage : {% if page|est_moderable_par:request.user %}
    """
    # Import local pour eviter de charger front.views a l'import des
    # templatetags. / Local import to avoid loading front.views at
    # templatetag import time.
    from front.views import _est_proprietaire_page

    return _est_proprietaire_page(utilisateur, page)
