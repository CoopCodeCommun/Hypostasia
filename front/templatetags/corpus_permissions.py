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


@register.filter(name="est_modifiable_par")
def est_modifiable_par(page, utilisateur):
    """
    Vrai si l'utilisateur PEUT ECRIRE la note (droit d'ecriture sur au
    moins un carnet qui la contient — SPEC-corpus § 5.2). C'est LA MEME
    regle que les endpoints d'element (_utilisateur_peut_ecrire_page) :
    le bouton et le droit ne divergent pas (lecon de la phase D).
    / True if the user can WRITE the note — the exact rule the element
    endpoints enforce, so button and right never diverge.

    Usage : {% if page|est_modifiable_par:request.user %}
    """
    # Import local pour eviter de charger front.views a l'import des
    # templatetags. / Local import to avoid loading front.views at
    # templatetag import time.
    from front.views import _utilisateur_peut_ecrire_page

    return _utilisateur_peut_ecrire_page(utilisateur, page)


@register.filter(name="une_analyse_tourne_sur")
def une_analyse_tourne_sur(page):
    """
    Vrai si une analyse tourne sur cette note, donc si l'edition doit
    etre refusee A L'ENTREE.
    / True if an analysis is running, so editing must be refused UP FRONT.

    Usage : {% if page|une_analyse_tourne_sur %}

    POURQUOI A L'ENTREE, ET PAS AU MOMENT D'ENREGISTRER

    `services/garde_edition.py` refuse deja l'ecriture pendant une
    analyse — les services reposent la garde eux-memes, et le lot entier
    est alors annule. Mais un refus qui arrive APRES vingt minutes de
    frappe est le pire des deux mondes : le travail est fait, et il ne
    passe pas. La spec (§ 8.1) demande donc que le mode NE S'OUVRE PAS.

    Ce filtre ne SUPPRIME pas le second controle, il evite le cas
    frequent : une analyse peut toujours demarrer une fois le mode
    ouvert, et c'est alors l'enregistrement qui refuse — en bloc, sans
    rien ecrire.
    / This does not replace the write-time guard; it avoids the common case.

    Un filtre plutot qu'une variable de contexte : `lecture_principale.html`
    est rendu depuis TROIS endroits de `front/views.py`, et une variable
    oubliee dans l'un d'eux vaudrait « faux » — donc un bouton actif
    pendant une analyse, sans que rien ne le signale.
    / A filter, not a context variable: the template is rendered from three
    places, and a forgotten variable would read as False.
    """
    from hypostasis_extractor.services.garde_edition import (
        une_analyse_tourne_sur_la_page,
    )

    return une_analyse_tourne_sur_la_page(page)
