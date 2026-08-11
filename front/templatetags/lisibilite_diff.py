"""
Rendre le diff de mise à jour lisible par un humain.
/ Make the update diff human-readable.

LOCALISATION : front/templatetags/lisibilite_diff.py

POURQUOI. Le diff parlait en langage machine (recette du 10 août, F5) :
le type d'opération s'affichait tel quel — `append_to_section` — et le
contenu exposait la syntaxe interne des marqueurs — `[[ext:35284]]` —
alors qu'elle est masquée PARTOUT ailleurs dans le produit, où elle est
rendue en renvois `[N]` cliquables. L'utilisateur devait deviner ce que
son texte allait devenir, au moment précis où on lui demande d'accepter
ou de refuser.

Ces deux filtres ne changent aucune donnée : ils traduisent à
l'affichage, au dernier moment.
/ Two display-only filters: the diff spoke in machine terms right when
the user is asked to accept or refuse.
"""

import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

# Les types du schéma d'opérations (SPEC-synthese, addendum n°15).
_NOMS_D_OPERATION = {
    "append_to_section": "Ajouter à la fin de la section",
    "replace_section": "Remplacer le contenu de la section",
    "insert_section": "Insérer une nouvelle section",
    "no_change": "Ne rien changer",
}

_MARQUEUR = re.compile(r"\[\[ext:(\d+)\]\]")


@register.filter
def nom_d_operation(type_d_operation):
    """`append_to_section` → « Ajouter à la fin de la section ».

    Un type inconnu est rendu tel quel plutôt que masqué : mieux vaut
    un mot technique qu'un silence sur ce qui va être appliqué.
    / An unknown type is shown as-is: better a technical word than
    silence about what will be applied.
    """
    return _NOMS_D_OPERATION.get(type_d_operation, type_d_operation or "")


@register.filter
def marqueurs_en_renvois(texte):
    """`[[ext:35284]]` → une pastille « source 35284 ».

    Le texte est échappé AVANT toute insertion de balise : le contenu
    vient d'un modèle de langage, il n'est pas de confiance.
    / The text is escaped before any markup is added: it comes from a
    language model and is not trusted.
    """
    if not texte:
        return ""
    rendu = escape(str(texte))
    rendu = _MARQUEUR.sub(
        lambda correspondance: (
            '<span class="renvoi-diff" '
            f'title="Renvoi vers l\'extraction {correspondance.group(1)}">'
            f"source {correspondance.group(1)}</span>"
        ),
        rendu,
    )
    return mark_safe(rendu)  # noqa: S308 — échappé juste au-dessus


@register.filter
def est_sans_redaction(texte):
    """Vrai si le contenu n'est QUE des marqueurs, sans une phrase.

    C'est le défaut B2 relevé en recette : des opérations dont le
    contenu se réduisait à `[[ext:35284]]` produisaient des paragraphes
    orphelins faits d'un seul renvoi. Le back a été corrigé depuis,
    mais l'écran doit rester capable de le DIRE si cela se reproduit —
    un diff qu'on accepte les yeux fermés est un diff inutile.
    / True when the content is markers only, no sentence: the screen
    must be able to say so if it happens again.
    """
    if not texte:
        return True
    return not _MARQUEUR.sub("", str(texte)).strip()
