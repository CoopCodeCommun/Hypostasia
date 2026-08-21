"""
Qui doit apprendre qu'un wiki a bouge.
/ Who must learn that a wiki moved.

LOCALISATION : core/services/destinataires_de_wiki.py

CE PERIMETRE EST PLUS LARGE QUE CELUI DU BOUTON « TACHES ».
`front.tasks._destinataires_de_notification` notifie le proprietaire
d'une note et ceux des carnets qui la contiennent : c'est le bon
perimetre pour « ta tache est finie ». Ici, la question est autre — un
ARTICLE COMMUN a change, et le collectif qui lit le carnet doit
l'apprendre. Les PARTAGES du carnet entrent donc dans le compte,
utilisateurs directs et membres des groupes.
/ Wider than the tasks button: notebook shares are included.

Une personne sans adresse de courriel n'est PAS destinataire : la
compter ferait croire a un envoi qui n'a jamais eu lieu.
/ No address, no recipient: counting one would fake a delivery.
"""

from core.models import DossierPartage


def destinataires_d_un_wiki(wiki):
    """
    Les personnes a prevenir quand ce wiki bouge.
    / The people to warn when this wiki moves.

    LOCALISATION : core/services/destinataires_de_wiki.py

    :param wiki: le `Wiki` concerne / the wiki
    :return: une liste d'utilisateurs, dedoublonnee et triee par pk —
             l'ordre est stable pour que les tests et les journaux le
             soient aussi. / a deduplicated, stably ordered list
    """
    from django.contrib.auth import get_user_model

    identifiants = set()

    # 1. Le proprietaire de l'article lui-meme.
    # / The article's own owner.
    if wiki.page.owner_id is not None:
        identifiants.add(wiki.page.owner_id)

    # 2. Les proprietaires des carnets qui portent l'article — il peut
    #    y en avoir plusieurs (une note appartient a plusieurs carnets).
    # / The owners of every notebook holding the article.
    identifiants.update(
        wiki.page.appartenances_dossiers.filter(
            dossier__owner__isnull=False,
        ).values_list("dossier__owner_id", flat=True)
    )

    # 3. Le carnet du wiki lui-meme : son perimetre EST ce carnet, meme
    #    si l'article n'y est pas range. / The wiki's own notebook.
    if wiki.dossier_id is not None and wiki.dossier.owner_id is not None:
        identifiants.add(wiki.dossier.owner_id)

    # 4. Les partages du carnet : personnes directes, et membres des
    #    groupes avec qui il est partage.
    # / The notebook's shares: direct users and group members.
    partages = DossierPartage.objects.filter(dossier=wiki.dossier)
    identifiants.update(
        partages.filter(utilisateur__isnull=False)
        .values_list("utilisateur_id", flat=True)
    )
    for partage in partages.filter(groupe__isnull=False).select_related(
        "groupe",
    ):
        identifiants.update(
            partage.groupe.membres.values_list("pk", flat=True)
        )

    if not identifiants:
        return []

    return list(
        get_user_model().objects
        .filter(pk__in=identifiants)
        .exclude(email="")
        .exclude(email__isnull=True)
        .order_by("pk")
    )
