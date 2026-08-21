"""
Ce qui est apparu dans le perimetre DEPUIS un acte donne.
/ What appeared in the scope SINCE a given act.

LOCALISATION : core/services/nouveautes_du_perimetre.py

A QUOI CA SERT. Un article propose deux gestes couteux — « mettre a
jour » et « verifier les citations ». Rien ne disait s'ils avaient une
raison d'etre : le lecteur relancait a l'aveugle un travail qui ne
changerait rien, ou laissait dormir un article que trois extractions
neuves auraient enrichi.

CE QU'ON COMPTE, ET POURQUOI CES DEUX-LA. Une synthese repose sur le
corpus de son perimetre. Deux choses peuvent l'avoir change depuis :

- une **extraction** de plus — le corpus dit quelque chose que l'article
  n'a pas pu reprendre ;
- un **commentaire** de plus — une extraction deja citee est desormais
  contestee, et le § 7.2 veut que le debat remonte a la citation.

CE QU'ON NE COMPTE PAS : les extractions MASQUEES. Elles ont ete
retirees du contenu utile par curation ; les compter proposerait de
relancer une production sur du materiel qu'un humain a ecarte.
/ Hidden extractions are excluded: they were curated out.
"""


def nouveautes_du_perimetre(notes, depuis):
    """
    Combien d'extractions et de commentaires depuis `depuis` ?
    / How many extractions and comments since `depuis`?

    LOCALISATION : core/services/nouveautes_du_perimetre.py

    :param notes: les `Page` du perimetre — un queryset ou une liste.
    :param depuis: la date de l'acte de reference, ou None.
    :return: un dict `{"extractions": n, "commentaires": n, "total": n,
             "depuis": date}`. **`total` vaut 0 quand `depuis` est
             None** : sans date de reference, on ne sait pas ce qui est
             « nouveau », et inventer un compte serait pire que de n'en
             donner aucun.
             / With no reference date, nothing is "new": inventing a
             count would be worse than giving none.
    """
    from hypostasis_extractor.models import (
        CommentaireExtraction, ExtractedEntity,
    )

    if depuis is None:
        return {
            "extractions": 0, "commentaires": 0, "total": 0, "depuis": None,
        }

    extractions = ExtractedEntity.objects.filter(
        job__page__in=notes, masquee=False, created_at__gt=depuis,
    ).count()
    commentaires = CommentaireExtraction.objects.filter(
        entity__job__page__in=notes,
        entity__masquee=False,
        created_at__gt=depuis,
    ).count()
    return {
        "extractions": extractions,
        "commentaires": commentaires,
        "total": extractions + commentaires,
        "depuis": depuis,
    }


def derniere_verification(page_d_article):
    """
    Quand cet article a-t-il ete verifie pour la derniere fois ?
    / When was this article last verified?

    LOCALISATION : core/services/nouveautes_du_perimetre.py

    C'est la date du verdict le plus RECENT parmi ses citations, et non
    une date rangee sur l'article : une verification ne touche que les
    citations, et rien d'autre ne la date. **None** quand aucune
    citation n'a jamais ete jugee — l'article n'a pas ete verifie une
    fois « il y a longtemps », il ne l'a jamais ete.
    / The most recent verdict among its citations; None when no citation
    was ever judged — never verified, not verified long ago.
    """
    from core.models import SourceLink, TypeLien

    return (
        SourceLink.objects.filter(
            page_cible=page_d_article, type_lien=TypeLien.CITE,
        )
        .exclude(verifie_le__isnull=True)
        .order_by("-verifie_le")
        .values_list("verifie_le", flat=True)
        .first()
    )
