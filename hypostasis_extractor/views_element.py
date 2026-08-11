"""
ElementViewSet — endpoints du moteur ELEMENT (BR-E, SPEC § 7 et § 8.4).
/ ElementViewSet: the ELEMENT engine's endpoints.

LOCALISATION : hypostasis_extractor/views_element.py

Cinq actions, une par operation, chacune avec son serializer (convention
du projet) : corriger (texte + reconciliation), scinder, fusionner avec
le suivant, masquer, demasquer. Les GARDES vivent dans les services
(analyse en cours, synthese figee qui cite) : ici on les attrape et on
les rend en 409 avec leur message FALC — jamais un 500.

LE VERROU (SPEC § 7, defaut de concurrence consigne le 8 aout) :
chaque action ouvre une transaction et pose select_for_update() sur la
ou les lignes ElementDocument AVANT d'appeler le service. Deux
operations concurrentes sur le MEME element se serialisent ; deux
elements differents ne se bloquent jamais.
/ Guards live in the services and surface as 409 FALC; every action
locks the ElementDocument row(s) before calling the service.

FLUX DE REPONSE : 200 + HX-Trigger {showToast, lectureReload} — le
front ecoute deja lectureReload (hypostasia.js) et recharge la zone de
lecture, qui re-rend les blocs (BR-D). Aucun HTML a construire ici.
/ 200 + HX-Trigger; the front already listens to lectureReload.
"""

import json
import logging

from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from rest_framework import permissions, viewsets
from rest_framework.decorators import action

from core.models import ElementDocument, PageEdit
from hypostasis_extractor.serializers import (
    CorrectionDElementSerializer,
    JustificationDElementSerializer,
    ScissionDElementSerializer,
)
from hypostasis_extractor.services.garde_edition import (
    EditionBloqueeParUneSynthese,
    EditionBloqueePendantAnalyse,
)

logger = logging.getLogger(__name__)


def _message_falc_du_blocage_par_analyse():
    """
    Le message montre a l'utilisateur quand une analyse tourne.
    Sans pk, sans « job », sans jargon (relecture BR-E, defaut n°4).
    / The user-facing message when an analysis is running.

    LOCALISATION : hypostasis_extractor/views_element.py
    """
    return (
        "Une analyse est en cours sur cette note. Modifier le texte "
        "maintenant ferait perdre son travail. Réessayez dans un "
        "instant, quand elle sera terminée."
    )


def _message_falc_du_blocage_par_synthese(blocage):
    """
    Le message NOMME la synthese qui bloque (§ 5.3), sans la moitie
    anglaise ni les identifiants internes de l'exception.
    / Names the blocking synthesis, without the exception's internals.

    LOCALISATION : hypostasis_extractor/views_element.py
    """
    citations = getattr(blocage, "citations", None) or []
    premiere = citations[0] if citations else None
    page_de_synthese = getattr(premiere, "page_cible", None)
    titre = getattr(page_de_synthese, "title", "") or "une synthèse adoptée"
    return (
        f"Ce passage est cité par « {titre} ». Une synthèse adoptée ne "
        "doit pas voir ses preuves changer : retirez d'abord la "
        "citation, ou produisez une nouvelle synthèse."
    )


def _reponse_avec_toast(message, statut, icone="warning"):
    """
    Une reponse HTTP qui porte un toast, et rien d'autre.
    / An HTTP response carrying a toast, nothing else.

    LOCALISATION : hypostasis_extractor/views_element.py
    """
    reponse = HttpResponse(status=statut)
    reponse["HX-Trigger"] = json.dumps({
        "showToast": {"message": message, "icon": icone},
    })
    return reponse


def _reponse_passage_disparu():
    """
    Le pk vise n'existe plus (relecture U1, defaut M4) : en
    collaboration, chaque scission ou fusion d'autrui REMPLACE des
    lignes — les boutons rendus chez les autres pointent des morts.
    404 + toast FALC + rechargement : jamais la page 404 brute dans un
    SweetAlert. / Dead pk: FALC toast + reading reload, never the raw
    404 page.
    """
    reponse = HttpResponse(status=404)
    reponse["HX-Trigger"] = json.dumps({
        "showToast": {
            "message": (
                "Ce passage vient de changer ou n'existe plus. "
                "La lecture va se recharger."
            ),
            "icon": "info",
        },
        "lectureReload": {},
    })
    return reponse


def _reponse_de_succes(page, message):
    """
    200 + toast + rechargement de la lecture de la page.
    / 200 + toast + reading reload for the page.

    LOCALISATION : hypostasis_extractor/views_element.py
    """
    reponse = HttpResponse(status=200)
    reponse["HX-Trigger"] = json.dumps({
        "showToast": {"message": message, "icon": "success"},
        "lectureReload": {"page_id": str(page.pk)},
        "tachesChanged": {},
    })
    return reponse


class ElementViewSet(viewsets.ViewSet):
    """
    Les operations sur UN element : corriger, scinder, fusionner,
    masquer, demasquer. / Operations on ONE element.
    """

    permission_classes = [permissions.IsAuthenticated]

    def _element_verrouille(self, pk):
        """
        Charge l'element AVEC le verrou de ligne (SPEC § 7).
        A appeler DANS une transaction. / Loads the element WITH the
        row lock; call inside a transaction.
        """
        return get_object_or_404(
            ElementDocument.objects.select_for_update().select_related(
                "page",
            ),
            pk=pk,
        )

    def _page_verrouillee_pour_la_structure(self, pk_de_l_element):
        """
        Verrouille la ligne PAGE avant une operation de STRUCTURE
        (relecture BR-E, defaut n°1) : scission et fusion renumerotent
        les ordres de TOUTE la page (`ordre__gt`), et deux operations
        simultanees sur des elements differents de la meme page se
        percutaient au commit (contrainte d'ordre DEFERRED ->
        IntegrityError -> 500). Le verrou de page les serialise ;
        corriger et masquer, qui ne touchent pas aux ordres, restent au
        verrou de ligne. / Structure operations renumber the whole
        page: the page-row lock serialises them.
        """
        from core.models import Page as ModelePage

        identifiant_de_page = get_object_or_404(
            ElementDocument.objects.values_list("page_id", flat=True),
            pk=pk_de_l_element,
        )
        ModelePage.objects.select_for_update().get(pk=identifiant_de_page)

    def _refus_si_pas_le_droit(self, request, page):
        """
        Le MEME droit que le reste de la lecture (front/views.py) —
        import paresseux pour eviter le cycle front <-> extractor.
        / Same write right as the reading views; lazy import to avoid
        an import cycle.
        """
        from front.views import _utilisateur_peut_ecrire_page

        if not _utilisateur_peut_ecrire_page(request.user, page):
            return _reponse_avec_toast(
                "Vous n'avez pas le droit de modifier cette note. "
                "Demandez l'accès à la personne qui la possède.",
                statut=403,
            )
        return None

    @action(detail=True, methods=["GET"])
    def formulaire_correction(self, request, pk=None):
        """
        Le formulaire de correction du texte, rendu par le serveur (U1).
        / The server-rendered text-correction form.

        FLUX : bouton « corriger » (_actions_element.html) -> GET ici ->
        injecte DANS LE CORPS DU BLOC -> le script bascule le bloc en
        edition -> POST corriger.

        L'ETALON CORRIGE DANS LE DOCUMENT, PAS DANS UN MODAL (§ 11).
        Le <dialog> livre en U1 arrachait le passage a son contexte : on
        corrigeait une phrase sans voir celles qui l'entourent, alors
        que ce sont elles qui disent si la correction est juste. Le
        dialogue reste pour la SCISSION, ou l'on vise un point de coupe
        dans un texte qu'il faut montrer en entier.
        / The mock edits inside the document; the modal hid the context.

        Le droit est LE MEME que pour agir : pas de formulaire pour qui
        ne peut pas ecrire. / Same write rule as the action itself.
        """
        element = ElementDocument.objects.select_related("page").filter(
            pk=pk,
        ).first()
        if element is None:
            return _reponse_passage_disparu()
        refus = self._refus_si_pas_le_droit(request, element.page)
        if refus:
            return refus
        return render(
            request,
            "front/includes/_editeur_en_place.html",
            {"element": element},
        )

    @action(detail=True, methods=["GET"])
    def formulaire_scission(self, request, pk=None):
        """
        Le formulaire de scission : placer le curseur, couper (U1).
        / The split form: place the caret, cut.

        La position de coupe est lue au moment de l'envoi depuis
        selectionStart du textarea (en lecture seule) — le gabarit
        porte ce cablage. / The cut position comes from the read-only
        textarea's selectionStart at submit time.
        """
        element = ElementDocument.objects.select_related("page").filter(
            pk=pk,
        ).first()
        if element is None:
            return _reponse_passage_disparu()
        refus = self._refus_si_pas_le_droit(request, element.page)
        if refus:
            return refus
        return render(
            request,
            "front/includes/_formulaire_element_scission.html",
            {"element": element},
        )

    @action(detail=True, methods=["POST"])
    def corriger(self, request, pk=None):
        """
        Corrige le TEXTE d'un element et reconcilie ses portions.
        / Fixes an element's TEXT and reconciles its portions.

        FLUX :
        1. Verrou de ligne + droit d'ecriture.
        2. reconcilier_les_portions_de_l_element (gardes incluses).
        3. Journal PageEdit (texte avant/apres).
        4. Toast + rechargement de la lecture.
        """
        serializer = CorrectionDElementSerializer(data=request.data)
        if not serializer.is_valid():
            return _reponse_avec_toast(
                "Le texte corrigé ne peut pas être vide.", statut=400,
            )
        nouveau_texte = serializer.validated_data["texte"]

        from hypostasis_extractor.services.reconciliation import (
            reconcilier_les_portions_de_l_element,
        )

        try:
            with transaction.atomic():
                element = self._element_verrouille(pk)
                refus = self._refus_si_pas_le_droit(request, element.page)
                if refus:
                    return refus

                resultat = reconcilier_les_portions_de_l_element(
                    element, nouveau_texte,
                )

                # Rien n'a change : pas de journal, pas de bruit
                # (relecture BR-E, defaut n°5). / No change: no journal
                # entry, no noise.
                if resultat["ancien_texte"] == nouveau_texte:
                    return _reponse_avec_toast(
                        "Aucun changement : le texte est identique.",
                        statut=200, icone="info",
                    )

                # Journal : le texte d'AVANT vient du resultat, lu SOUS
                # le verrou — pas d'une relecture qui rouvrirait une
                # course. L'identifiant STABLE est note : l'ordre, lui,
                # est renumerote a chaque scission/fusion.
                # / The before-text comes from the locked read; the
                # stable identifier survives renumbering.
                PageEdit.objects.create(
                    page=element.page,
                    user=request.user,
                    type_edit="contenu",
                    description=(
                        f"Élément {element.ordre} corrigé"[:500]
                    ),
                    donnees_avant={"texte": resultat["ancien_texte"]},
                    donnees_apres={
                        "texte": nouveau_texte,
                        "identifiant_stable": str(element.identifiant_stable),
                    },
                )
        except Http404:
            return _reponse_passage_disparu()
        except EditionBloqueePendantAnalyse:
            return _reponse_avec_toast(
                _message_falc_du_blocage_par_analyse(), statut=409,
            )
        except EditionBloqueeParUneSynthese as blocage:
            return _reponse_avec_toast(
                _message_falc_du_blocage_par_synthese(blocage), statut=409,
            )

        nombre_detachees = len(resultat["detachees"])
        if nombre_detachees:
            message = (
                f"Texte corrigé. Attention : {nombre_detachees} passage(s) "
                "surligné(s) n'ont pas été retrouvés dans le nouveau texte."
            )
        else:
            message = "Texte corrigé. Les passages surlignés suivent."
        return _reponse_de_succes(element.page, message)

    @action(detail=True, methods=["POST"])
    def scinder(self, request, pk=None):
        """
        Coupe un element en deux a la position donnee.
        / Splits an element in two at the given position.
        """
        serializer = ScissionDElementSerializer(data=request.data)
        if not serializer.is_valid():
            # Le message dit QUOI FAIRE (relecture U1, defaut M6) : le
            # cas de loin le plus courant est un envoi sans avoir place
            # le curseur. / Say what to do: the common case is
            # submitting without placing the caret.
            if "position_de_coupe" in serializer.errors:
                return _reponse_avec_toast(
                    "Placez d'abord le curseur dans le texte, à "
                    "l'endroit exact de la coupe. Puis appuyez sur "
                    "« Couper ici ».",
                    statut=400,
                )
            return _reponse_avec_toast(
                "La justification ne doit pas dépasser 500 caractères.",
                statut=400,
            )
        position_de_coupe = serializer.validated_data["position_de_coupe"]
        justification = serializer.validated_data.get("justification", "")
        empreinte_annoncee = serializer.validated_data.get(
            "empreinte_du_texte", "",
        )

        from hypostasis_extractor.services.moteur_structure import (
            scinder_un_element,
        )

        try:
            with transaction.atomic():
                # Operation de STRUCTURE : verrou de PAGE d'abord
                # (relecture BR-E, defaut n°1). / Structure operation:
                # page lock first.
                self._page_verrouillee_pour_la_structure(pk)
                element = self._element_verrouille(pk)
                refus = self._refus_si_pas_le_droit(request, element.page)
                if refus:
                    return refus

                # Le texte a-t-il change depuis l'affichage du
                # formulaire ? (relecture U1, defaut H2) La position de
                # coupe n'a de sens que sur le texte AFFICHE : sur un
                # autre texte, elle couperait au mauvais endroit, sans
                # aucun signal. / Has the text changed since the form
                # was shown? A stale cut position corrupts silently.
                if (empreinte_annoncee
                        and empreinte_annoncee != element.empreinte_contenu):
                    return _reponse_avec_toast(
                        "Ce passage a été modifié entre-temps. Fermez "
                        "la fenêtre et rouvrez-la pour couper le texte "
                        "à jour.",
                        statut=409,
                    )

                scinder_un_element(
                    element, position_de_coupe,
                    utilisateur=request.user,
                    justification=justification,
                )
        except Http404:
            return _reponse_passage_disparu()
        except EditionBloqueePendantAnalyse:
            return _reponse_avec_toast(
                _message_falc_du_blocage_par_analyse(), statut=409,
            )
        except EditionBloqueeParUneSynthese as blocage:
            return _reponse_avec_toast(
                _message_falc_du_blocage_par_synthese(blocage), statut=409,
            )
        except ValueError as erreur:
            # Jamais str(erreur) brut vers l'utilisateur (relecture U1,
            # defaut M6) : le detail va au journal, l'ecran parle
            # simplement. / Raw error text goes to the log, not the
            # user.
            logger.info("Scission refusée (élément %s) : %s", pk, erreur)
            return _reponse_avec_toast(
                "On ne peut pas couper là. Placez le curseur au milieu "
                "du texte : il faut garder du texte des deux côtés de "
                "la coupe.",
                statut=400,
            )

        return _reponse_de_succes(
            element.page, "Élément coupé en deux.",
        )

    @action(detail=True, methods=["POST"])
    def fusionner_avec_le_suivant(self, request, pk=None):
        """
        Recolle un element avec celui qui le suit (ordre + 1).
        / Merges an element with the next one.

        C'est L'OPERATION n°1 sur une vraie diarisation : recoller un
        tour de parole scinde. / The number-one operation on real
        diarised audio: re-joining a split speech turn.
        """
        serializer = JustificationDElementSerializer(data=request.data)
        if not serializer.is_valid():
            return _reponse_avec_toast(
                "La justification ne doit pas dépasser 500 caractères.",
                statut=400,
            )
        justification = serializer.validated_data.get("justification", "")

        from hypostasis_extractor.services.moteur_structure import (
            fusionner_deux_elements,
        )

        try:
            with transaction.atomic():
                # Operation de STRUCTURE : verrou de PAGE d'abord
                # (relecture BR-E, defaut n°1). / Page lock first.
                self._page_verrouillee_pour_la_structure(pk)
                element = self._element_verrouille(pk)
                refus = self._refus_si_pas_le_droit(request, element.page)
                if refus:
                    return refus

                # Le suivant est verrouille AUSSI : la fusion touche les
                # deux lignes. / The next row is locked too.
                suivant = (
                    ElementDocument.objects.select_for_update()
                    .filter(page=element.page, ordre=element.ordre + 1)
                    .first()
                )
                if suivant is None:
                    return _reponse_avec_toast(
                        "Cet élément est le dernier : il n'y a rien "
                        "après lui à recoller.", statut=400,
                    )

                fusionner_deux_elements(
                    element, suivant,
                    utilisateur=request.user,
                    justification=justification,
                )
        except Http404:
            return _reponse_passage_disparu()
        except EditionBloqueePendantAnalyse:
            return _reponse_avec_toast(
                _message_falc_du_blocage_par_analyse(), statut=409,
            )
        except EditionBloqueeParUneSynthese as blocage:
            return _reponse_avec_toast(
                _message_falc_du_blocage_par_synthese(blocage), statut=409,
            )
        except ValueError as erreur:
            # Message FALC dedie (relecture U1, defauts M6 et M8) : le
            # cas reel est « le suivant est masque » — le bouton n'est
            # plus rendu dans ce cas, mais un rendu perime peut encore
            # l'envoyer. / Dedicated plain-words message; the real case
            # is a hidden next element from a stale render.
            logger.info("Fusion refusée (élément %s) : %s", pk, erreur)
            if "masque" in str(erreur):
                return _reponse_avec_toast(
                    "Le passage suivant est masqué. Rétablissez-le "
                    "d'abord si vous voulez les recoller.",
                    statut=400,
                )
            return _reponse_avec_toast(
                "Ces deux passages ne peuvent pas être recollés en "
                "l'état. Rechargez la page et réessayez.",
                statut=400,
            )

        return _reponse_de_succes(
            element.page, "Les deux éléments ont été recollés.",
        )

    @action(detail=True, methods=["POST"])
    def masquer(self, request, pk=None):
        """
        Retire un element du contenu utile, sans le supprimer.
        / Hides an element from the useful content without deleting it.
        """
        serializer = JustificationDElementSerializer(data=request.data)
        # Une justification invalide (trop longue) est REFUSEE, pas
        # avalee en silence (relecture BR-E, defaut n°2).
        # / An invalid justification is refused, not silently dropped.
        if not serializer.is_valid():
            return _reponse_avec_toast(
                "La justification ne doit pas dépasser 500 caractères.",
                statut=400,
            )
        justification = serializer.validated_data.get("justification", "")

        from hypostasis_extractor.services.masquage import masquer_un_element

        try:
            with transaction.atomic():
                element = self._element_verrouille(pk)
                refus = self._refus_si_pas_le_droit(request, element.page)
                if refus:
                    return refus

                masquer_un_element(
                    element, justification=justification,
                    utilisateur=request.user,
                )
        except Http404:
            return _reponse_passage_disparu()
        except EditionBloqueePendantAnalyse:
            return _reponse_avec_toast(
                _message_falc_du_blocage_par_analyse(), statut=409,
            )
        except EditionBloqueeParUneSynthese as blocage:
            return _reponse_avec_toast(
                _message_falc_du_blocage_par_synthese(blocage), statut=409,
            )
        except ValueError as erreur:
            return _reponse_avec_toast(str(erreur), statut=400)

        return _reponse_de_succes(
            element.page,
            "Élément masqué. Il ne sera plus analysé ni affiché.",
        )

    @action(detail=True, methods=["POST"])
    def demasquer(self, request, pk=None):
        """
        Remet un element masque dans le contenu utile.
        / Puts a hidden element back into the useful content.
        """
        serializer = JustificationDElementSerializer(data=request.data)
        if not serializer.is_valid():
            return _reponse_avec_toast(
                "La justification ne doit pas dépasser 500 caractères.",
                statut=400,
            )
        justification = serializer.validated_data.get("justification", "")

        from hypostasis_extractor.services.masquage import (
            demasquer_un_element,
        )

        try:
            with transaction.atomic():
                element = self._element_verrouille(pk)
                refus = self._refus_si_pas_le_droit(request, element.page)
                if refus:
                    return refus

                bilan = demasquer_un_element(
                    element, justification=justification,
                    utilisateur=request.user,
                )
        except Http404:
            return _reponse_passage_disparu()
        except EditionBloqueePendantAnalyse:
            return _reponse_avec_toast(
                _message_falc_du_blocage_par_analyse(), statut=409,
            )
        except ValueError as erreur:
            return _reponse_avec_toast(str(erreur), statut=400)

        rattachees = bilan.get("portions_rattachees", 0)
        if rattachees:
            message = (
                f"Élément rétabli. {rattachees} passage(s) surligné(s) "
                "retrouvent leur place."
            )
        else:
            message = "Élément rétabli."
        return _reponse_de_succes(element.page, message)
