"""
Ce que chaque personne doit lire le matin, et rien de plus.
/ What each person must read in the morning, and nothing more.

LOCALISATION : core/services/recapitulatif_du_matin.py

DEUX CHOSES SE RACONTENT, ET DEUX SEULEMENT (addendum du 21 aout
2026) :

1. les wikis **modifies** depuis le dernier mail de cette personne —
   par la passe de nuit comme par un humain, la distinction est portee
   par `TourDeWiki.fait_par` ;
2. les wikis dont le perimetre a recu du **neuf** que l'article n'a pas
   repris.

CE QUI EMPECHE LE SPAM, et c'est la partie qui compte. « Du neuf » ne
veut PAS dire « il reste des extractions ecartees » : un wiki
volontairement partiel en porte pour toujours, et l'annoncer chaque
matin serait un rappel quotidien que personne ne lirait plus au bout de
trois jours. Il faut que quelque chose soit APPARU depuis le dernier
mail — une extraction, un commentaire — ET qu'il ne soit pas repris.
/ "News" requires something new since the last mail, not merely
something missing.

Un tour qui n'a RIEN change (lot entierement rejete) n'est pas une
nouvelle : c'est un fait d'histoire, qui se lit dans l'historique de
l'article, pas dans un mail. Une REPARATION DE TITRES non plus : elle
change le texte, mais elle ne change pas ce que l'article DIT — annoncer
« votre wiki a ete modifie » pour un `###` ramene a `##` userait le mail
sans rien apprendre a personne.
/ A round that changed nothing is history, not news — and neither is a
heading repair.
"""

from datetime import timedelta

from django.db.models import F
from django.utils import timezone

from core.models import EnvoiDuRecapitulatif, MotifDeTourDeWiki, Wiki
from core.services.destinataires_de_wiki import destinataires_d_un_wiki
from core.services.nouveautes_du_perimetre import nouveautes_du_perimetre
from core.services.synthese import (
    extractions_ecartees, notes_du_perimetre_d_un_wiki,
)

# Sans envoi precedent, on regarde la derniere journee. Remonter plus
# loin ferait raconter a une nouvelle personne un mois d'histoire dans
# son tout premier mail. / A first mail covers one day, not a month.
DUREE_PAR_DEFAUT = timedelta(hours=24)


def borne_du_destinataire(utilisateur):
    """
    Depuis quand faut-il raconter a cette personne ?
    / Since when should we tell this person?

    LOCALISATION : core/services/recapitulatif_du_matin.py

    C'est la date de son dernier recapitulatif — la garantie « un mail
    par jour au maximum » et « rien deux fois » sont la meme ligne de
    code. / One mail a day and no repetition are the same rule.
    """
    dernier_envoi = EnvoiDuRecapitulatif.objects.filter(
        destinataire=utilisateur,
    ).first()
    if dernier_envoi is not None:
        return dernier_envoi.envoye_le
    return timezone.now() - DUREE_PAR_DEFAUT


def matiere_par_destinataire():
    """
    Ce qu'il y a a dire, range par personne.
    / What there is to say, sorted by person.

    LOCALISATION : core/services/recapitulatif_du_matin.py

    :return: une liste de dicts, un par destinataire AYANT quelque
        chose a lire, triee par pk d'utilisateur :
        `{"utilisateur", "depuis", "wikis_modifies", "wikis_avec_du_neuf"}`.
        Une personne sans rien a lire n'est PAS dans la liste — pas de
        mail vide. / People with nothing to read are absent.
    """
    matiere_par_pk = {}

    for wiki in Wiki.objects.select_related("page", "dossier"):
        destinataires = destinataires_d_un_wiki(wiki)
        if not destinataires:
            continue

        # Les tours qui ont REELLEMENT change l'article, du plus recent
        # au plus ancien (l'ordering du modele).
        # / Only rounds that actually changed the article.
        tours_qui_ont_change = list(
            wiki.tours.exclude(texte_avant=F("texte_apres"))
            .exclude(motif=MotifDeTourDeWiki.REPARATION_DE_TITRES)
            .select_related("fait_par")
        )

        notes = notes_du_perimetre_d_un_wiki(wiki)
        try:
            reste_a_reprendre = extractions_ecartees(wiki.page).count()
        except Exception:
            # Perimetre illisible (article historique) : on ne raconte
            # rien plutot que de raconter faux.
            # / Unreadable scope: say nothing rather than something false.
            reste_a_reprendre = 0

        for utilisateur in destinataires:
            entree = matiere_par_pk.get(utilisateur.pk)
            if entree is None:
                entree = {
                    "utilisateur": utilisateur,
                    "depuis": borne_du_destinataire(utilisateur),
                    "wikis_modifies": [],
                    "wikis_avec_du_neuf": [],
                }
                matiere_par_pk[utilisateur.pk] = entree

            tours_a_raconter = [
                tour for tour in tours_qui_ont_change
                if tour.fait_le > entree["depuis"]
            ]
            if tours_a_raconter:
                entree["wikis_modifies"].append({
                    "wiki": wiki,
                    "tours": tours_a_raconter,
                    "reste_a_reprendre": reste_a_reprendre,
                })
                continue

            # Pas de modification : y a-t-il une raison de revenir ?
            # / No change: is there any reason to come back?
            if not reste_a_reprendre:
                continue
            comptes = nouveautes_du_perimetre(notes, entree["depuis"])
            if comptes["total"]:
                entree["wikis_avec_du_neuf"].append({
                    "wiki": wiki,
                    "nouveautes": comptes,
                    "reste_a_reprendre": reste_a_reprendre,
                })

    return [
        entree for _pk, entree in sorted(matiere_par_pk.items())
        if entree["wikis_modifies"] or entree["wikis_avec_du_neuf"]
    ]
