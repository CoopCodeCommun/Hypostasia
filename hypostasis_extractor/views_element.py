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
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
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
                "Demandez l'acces a la personne qui la possede.",
                statut=403,
            )
        return None

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
            return _reponse_avec_toast(
                "La coupe demandée n'est pas valable : position entière "
                "obligatoire, justification de 500 caractères au plus.",
                statut=400,
            )
        position_de_coupe = serializer.validated_data["position_de_coupe"]
        justification = serializer.validated_data.get("justification", "")

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

                scinder_un_element(
                    element, position_de_coupe,
                    utilisateur=request.user,
                    justification=justification,
                )
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
