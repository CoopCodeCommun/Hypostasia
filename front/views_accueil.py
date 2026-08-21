"""
Les ecrans d'accueil : l'aide, le manifeste, et le message d'accueil.
/ The welcome screens: help, manifesto, and the welcome message.

LOCALISATION : front/views_accueil.py

POURQUOI CE FICHIER EXISTE

Jusqu'au 21 aout 2026, ces deux ecrans etaient des ONGLETS de la page
racine : trois boutons, trois `<div>` que du JavaScript montrait et
cachait tour a tour. Un onglet n'a pas d'adresse — on ne peut ni le
mettre en signet, ni l'envoyer a quelqu'un, ni y revenir par le bouton
« precedent » du navigateur. Le troisieme onglet, « Bases de
connaissances », montrait en plus une SECONDE vue des bases, a cote de
`/bases/` : les deux ont derive, celle de l'accueil ignorait la
description, les compteurs et la creation.

Les deux ecrans sont donc devenus des ViewSets, atteignables par deux
entrees de menu, et l'onglet des bases a disparu au profit de `/bases/`.
/ These screens used to be JS tabs on the root page: no address, no
bookmark, no back button. They are ViewSets now.
"""

import logging

from django.shortcuts import render
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

logger = logging.getLogger(__name__)


# L'IDENTIFIANT DU MESSAGE D'ACCUEIL COURANT.
#
# La session ne retient pas « cette personne a vu le message » mais
# « cette personne a vu CE message-la ». La difference est tout le
# mecanisme : changer cette constante republie le message a tout le
# monde, y compris a ceux qui avaient coche « j'ai compris ». C'est
# ainsi qu'une mise a jour du produit s'annoncera, sans avoir a inventer
# un second dispositif ni a effacer les sessions.
#
# EN CHANGER LA VALEUR EST UN GESTE VISIBLE PAR TOUS LES UTILISATEURS.
# Ne le faire que lorsque le contenu de la modale change vraiment.
# / The session remembers WHAT was seen, not THAT something was: changing
# this constant republishes the message to everyone. It is a
# user-visible action.
UUID_DU_MESSAGE_D_ACCUEIL = "8f3b1c42-5d7e-4a90-b6f1-2c9d0e4a7b31"

# La cle sous laquelle la session range l'UUID du dernier message compris.
# / The session key holding the last acknowledged message UUID.
CLE_DE_SESSION_DU_MESSAGE_VU = "uuid_du_message_d_accueil_vu"


def le_message_d_accueil_doit_s_afficher(request):
    """
    Dit si la modale d'accueil doit paraitre sur cette requete.
    / Tell whether the welcome modal should show on this request.

    LOCALISATION : front/views_accueil.py

    DEUX CONDITIONS, ET LA SECONDE EST FACILE A OUBLIER.

    1. La session ne porte pas l'UUID du message COURANT — soit qu'elle
       n'en porte aucun, soit qu'elle en porte un plus ancien.

    2. La requete n'est PAS une requete HTMX. La modale vit dans
       `base.html` ; une reponse partielle qui l'emporterait la
       rejouerait a chaque navigation, par-dessus celle deja affichee.

    :param request: la requete Django en cours
    :return: True si la modale doit etre rendue
    / Two conditions: an outdated UUID, and a non-HTMX request.
    """
    c_est_une_navigation_htmx = request.headers.get("HX-Request") == "true"
    if c_est_une_navigation_htmx:
        return False

    uuid_deja_compris = request.session.get(CLE_DE_SESSION_DU_MESSAGE_VU)
    return uuid_deja_compris != UUID_DU_MESSAGE_D_ACCUEIL


class AideViewSet(viewsets.ViewSet):
    """
    GET /aide/ — comment marche Hypostasia, en quatre etapes.
    / GET /aide/ — how Hypostasia works, in four steps.

    LOCALISATION : front/views_accueil.py

    C'est l'ancien onglet « Decouvrir l'app ». Le mainteneur l'a renomme
    « Aide » le 21 aout : c'est le mot que l'on cherche dans un menu
    quand on ne sait pas quoi faire.

    A NE PAS CONFONDRE avec `/lire/aide/`, qui rend la modale des
    RACCOURCIS CLAVIER derriere le bouton « ? » de la barre. Celle-ci
    est un ecran, celle-la une modale ; les deux coexistent.
    / Not to be confused with /lire/aide/, the keyboard-shortcuts modal.
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """
        Requete HTMX -> le partial seul. Acces direct -> la page entiere.
        / HTMX -> partial only. Direct access -> full page.
        """
        if request.headers.get("HX-Request"):
            return render(request, "front/includes/onboarding_vide.html")

        return render(request, "front/base.html", {"aide_preloaded": True})

    @action(detail=False, methods=["POST"], url_path="j-ai-compris")
    def j_ai_compris(self, request):
        """
        POST /aide/j-ai-compris/ — la case a cocher du message d'accueil.
        / The welcome message checkbox.

        LOCALISATION : front/views_accueil.py

        LA CASE VA DANS LES DEUX SENS. HTMX n'envoie une case a cocher
        que lorsqu'elle est cochee : une case decochee arrive donc comme
        un champ ABSENT, et c'est ce qui efface l'UUID de la session.
        Sans ce retour en arriere, un clic malheureux supprimerait le
        message pour toujours, sans aucun moyen de le rappeler.

        On ecrit un UUID, jamais un booleen : voir
        `UUID_DU_MESSAGE_D_ACCUEIL`.

        204 et non 200 : le client n'a rien a afficher, il ferme sa
        modale lui-meme. Renvoyer un fragment vide ferait croire a un
        swap qui n'a pas lieu.
        / The checkbox works both ways: HTMX omits an unchecked box, and
        that absence is what clears the session. 204: nothing to swap.
        """
        la_case_est_cochee = request.data.get("j_ai_compris") == "oui"

        if la_case_est_cochee:
            request.session[CLE_DE_SESSION_DU_MESSAGE_VU] = (
                UUID_DU_MESSAGE_D_ACCUEIL
            )
        else:
            request.session.pop(CLE_DE_SESSION_DU_MESSAGE_VU, None)

        logger.info(
            "message d'accueil: compris=%s utilisateur=%s",
            la_case_est_cochee, request.user,
        )
        return Response(status=204)


class ManifesteViewSet(viewsets.ViewSet):
    """
    GET /manifeste/ — pourquoi Hypostasia est un commun numerique.
    / GET /manifeste/ — why Hypostasia is a digital commons.

    LOCALISATION : front/views_accueil.py
    """

    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """
        Requete HTMX -> le partial seul. Acces direct -> la page entiere.
        / HTMX -> partial only. Direct access -> full page.
        """
        if request.headers.get("HX-Request"):
            return render(request, "front/includes/manifeste_ecran.html")

        return render(request, "front/base.html", {"manifeste_preloaded": True})
