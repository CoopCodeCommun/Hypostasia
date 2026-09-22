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
from django.template.loader import render_to_string
from rest_framework import permissions, viewsets
from rest_framework.decorators import action

from core.models import ElementDocument, PageEdit
from hypostasis_extractor.serializers import (
    CorrectionEnLotSerializer,
    CorrectionDElementSerializer,
    JustificationDElementSerializer,
    ScissionDElementSerializer,
)
from hypostasis_extractor.services.garde_edition import (
    EditionBloqueeParUneSynthese,
    EditionBloqueePendantAnalyse,
    verifier_qu_aucune_analyse_ne_tourne,
)

logger = logging.getLogger(__name__)

# LES LABELS DONT LE TEXTE NE SURVIT PAS A UN ALLER-RETOUR PAR LE DOM.
#
# Mesure du 30 aout 2026, sur cinq notes et 387 blocs : `table` echoue
# 20 fois sur 20, et TOUS les autres bouclent exactement — `code`,
# `picture`, `caption`, `title`, `section_header`, `list_item`, `text`.
# La liste ne contient donc que `table`, pas les « 58 elements non
# textuels » qu'on pouvait croire concernes.
# / Measured on five notes and 387 blocks: only `table` fails.
LABELS_QUI_NE_SE_RELISENT_PAS = {"table"}


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


def _html_du_bloc(request, element, pour_swap_oob):
    """
    Rend le HTML d'UN bloc de lecture, ou None si le service n'en rend pas.
    / Renders ONE reading block's HTML, or None.

    LOCALISATION : hypostasis_extractor/views_element.py

    LE RENDU PASSE PAR LE SERVICE DE LA PAGE, JAMAIS PAR UN RENDU A PART.
    C'est plus de travail que de rendre un bloc seul, et c'est voulu : un
    second chemin finirait par rendre un bloc qui ne ressemble plus a ses
    voisins — numerotation, surlignage, minutage — et rien ne le dirait.
    / Rendering goes through the page service, never a separate path.
    """
    from front.services.rendu_elements import construire_les_blocs_de_lecture
    from front.templatetags.corpus_permissions import est_modifiable_par

    blocs = construire_les_blocs_de_lecture(element.page)
    vises = [bloc for bloc in blocs if bloc["element"].pk == element.pk]
    if not vises:
        return None
    return render_to_string(
        "front/includes/_un_bloc_element.html",
        {
            "bloc": vises[0],
            "la_note_est_modifiable": est_modifiable_par(
                element.page, request.user,
            ),
            # `page` EST INDISPENSABLE, et son absence ne leve rien.
            #
            # Le gabarit garde le bouton d'ecoute derriere
            # `{% if page.source_file %}` : sans cette cle, un bloc de
            # transcription revient avec son minutage MAIS SANS son
            # bouton — donc different de ses voisins, et sans que rien
            # ne le signale. C'est exactement la derive que ce chemin de
            # rendu unique existe pour empecher.
            # `front/views.py:_contenu_de_lecture` passe la meme cle,
            # avec un commentaire qui decrit cette panne.
            # / Without `page`, an audio block comes back without its
            # play button — different from its neighbours, silently.
            "page": element.page,
            "pour_swap_oob": pour_swap_oob,
        },
        request=request,
    )


def _reponse_de_succes_avec_le_bloc(request, element, message):
    """
    200 + toast + LE BLOC TOUCHE, en swap hors bande. Pas de rechargement.
    / 200 + toast + the touched block, out of band. No reload.

    LOCALISATION : hypostasis_extractor/views_element.py

    POURQUOI PAS `lectureReload` (SPEC-edition-par-blocs § 11.3)

    `lectureReload` fait refaire au front `zoneLecture.innerHTML` pour la
    page ENTIERE (`hypostasia.js:494-512`). Sur une note de 210 blocs,
    corriger un mot reconstruit tout : le defilement et le focus sont
    perdus — le code les resynchronise deja a la main, ce qui dit assez
    que le rechargement casse quelque chose — et le jour ou un mode
    d'edition existera, la session en cours y passera.

    Un `hx-swap-oob` remplace le seul bloc touche. HTMX traite les
    elements hors bande MEME quand le bouton porte `hx-swap="none"`, ce
    qui est le cas de tous les boutons de `_actions_element.html`.

    RESERVE AUX GESTES DE LIGNE. `scinder` et `fusionner_avec_le_suivant`
    renumerotent la page : plusieurs blocs changent d'ordre et deux
    elements neufs remplacent l'ancien. Un swap d'un seul bloc ne peut pas
    le montrer, et ces deux-la gardent `_reponse_de_succes`.
    / Line-level gestures only; page-level ones keep the full reload.
    """
    html = _html_du_bloc(request, element, pour_swap_oob=True)
    if html is None:
        # Le service ne rend rien pour cet element : on ne sait pas quoi
        # echanger, donc on retombe sur le rechargement complet plutot
        # que de laisser l'ecran mentir.
        # / Nothing to swap: fall back to the full reload.
        return _reponse_de_succes(element.page, message)
    reponse = HttpResponse(html, status=200)
    reponse["HX-Trigger"] = json.dumps({
        "showToast": {"message": message, "icon": "success"},
        "tachesChanged": {},
    })
    return reponse


def _resume_du_lot(compte_rendu):
    """
    Le resume d'un enregistrement, en une phrase.
    / A batch save's summary, in one sentence.

    LOCALISATION : hypostasis_extractor/views_element.py

    C'EST LE SEUL RETOUR VISIBLE D'UN `Ctrl+S` REUSSI. Le compte rendu
    detaille s'affiche EN TETE de la note : en bas d'une note de 200
    blocs, on ne le voit pas. Ce resume-la part dans le toast, en haut a
    droite, quel que soit le defilement.

    IL NE DIT QUE CE QUI A EU LIEU. « 0 corrige, 0 masque, 0 refuse »
    fait lire trois nombres pour apprendre qu'il ne s'est rien passe —
    et un « 0 » en tete se lit comme une panne.

    LES ANCRES ET LES CITATIONS DETACHEES N'Y SONT PAS : ce sont des
    consequences, pas des gestes. Elles ont leur place dans le compte
    rendu detaille, qui les nomme separement (§ 7.4).

    :param compte_rendu: le dictionnaire des cinq nombres
    :return: la phrase, accordee
    """
    morceaux = []
    modifies = compte_rendu["blocs_modifies"]
    masques = compte_rendu["blocs_masques"]
    refuses = compte_rendu["blocs_refuses"]

    if modifies:
        morceaux.append(
            f"{modifies} passage{'s' if modifies > 1 else ''} "
            f"corrigé{'s' if modifies > 1 else ''}"
        )
    if masques:
        # « corrigé, 1 masqué » : le mot « passage » ne se repete pas.
        # / The noun is not repeated in the following clauses.
        if morceaux:
            morceaux.append(f"{masques} masqué{'s' if masques > 1 else ''}")
        else:
            morceaux.append(
                f"{masques} passage{'s' if masques > 1 else ''} "
                f"masqué{'s' if masques > 1 else ''}"
            )
    if refuses:
        if morceaux:
            morceaux.append(f"{refuses} refusé{'s' if refuses > 1 else ''}")
        else:
            morceaux.append(
                f"{refuses} passage{'s' if refuses > 1 else ''} "
                f"refusé{'s' if refuses > 1 else ''}"
            )

    if not morceaux:
        # Renvoyer le meme texte n'est pas une erreur : le mode envoie
        # TOUS les blocs, touches ou non. Mais « 0 corrige » se lirait
        # comme une panne.
        # / Unchanged text is not an error, but "0" reads like a failure.
        return "Aucun changement à enregistrer."
    return ", ".join(morceaux) + "."


def _reponse_du_compte_rendu(request, compte_rendu):
    """
    Le compte rendu d'un lot : cinq nombres, et la LISTE des refus.
    / The batch report: five numbers, and the LIST of refusals.

    LOCALISATION : hypostasis_extractor/views_element.py

    SPEC-edition-par-blocs § 7.4.

    DEUX CANAUX, ET CHACUN SA PORTEE. Le partial rendu ci-dessous porte
    le DETAIL — cinq nombres et la liste des refus — et s'affiche EN
    TETE de la note. L'en-tete `HX-Trigger` porte le RESUME
    (`_resume_du_lot`), qui part dans le toast, en haut a droite : c'est
    le seul retour visible quand on edite en bas d'une note longue.

    L'appelant est un `fetch()`, qui ne declenche aucun evenement htmx :
    c'est `mode_edition.js` qui relit cet en-tete et rejoue l'evenement
    `showToast`. Sans cela, le resume n'atteindrait personne — ce fut le
    cas jusqu'au 30 aout 2026.

    JAMAIS de `lectureReload` ici, meme quand tout est refuse : recharger
    la page de qui vient d'enregistrer effacerait le texte qu'il n'a pas
    reussi a sauver — exactement ce qu'il faut lui laisser pour retaper.
    / Never a reload here: it would erase the very text they must retype.
    """
    html = render_to_string(
        "front/includes/_compte_rendu_du_lot.html",
        {"compte_rendu": compte_rendu},
        request=request,
    )
    reponse = HttpResponse(html, status=200)
    reponse["HX-Trigger"] = json.dumps({
        "showToast": {
            "message": _resume_du_lot(compte_rendu),
            "icon": "success" if not compte_rendu["blocs_refuses"] else "warning",
        },
        "tachesChanged": {},
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
    Les operations sur UN element : rendre son bloc, corriger, scinder,
    fusionner, masquer, demasquer, et enregistrer un lot.
    / Operations on ONE element, plus the batch save.
    """

    permission_classes = [permissions.IsAuthenticated]

    # LE ROUTEUR DRF ACCEPTE N'IMPORTE QUOI COMME pk PAR DEFAUT.
    #
    # Sans cette expression, `/elements/abc/bloc/` fait `filter(pk="abc")`,
    # et Django leve `ValueError: Field 'id' expected a number` — un 500,
    # pas un 404. C'est le troisieme piege de la doctrine du 404, deja
    # paye une fois dans ce depot. Il est d'autant plus couteux ici que
    # l'action `bloc` est `AllowAny` : n'importe qui, sans compte,
    # remplissait les journaux d'erreurs.
    #
    # Une seule ligne couvre TOUTES les actions du ViewSet : un pk non
    # numerique ne route plus, donc il rend 404.
    # / The DRF router accepts any pk: without this, a non-numeric pk is
    # a 500, not a 404. One line covers every action.
    lookup_value_regex = r"[0-9]+"

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

    @action(detail=False, methods=["GET"])
    def panneau_des_masques(self, request):
        """
        Rend le PANNEAU des passages masques d'une note, a jour.
        / Renders a note's panel of hidden passages, up to date.

        LOCALISATION : hypostasis_extractor/views_element.py

        SPEC-edition-par-blocs-et-stenotypie.md § 5.3, cas 4.

        POURQUOI CET ENDPOINT EXISTE

        Le mode d'edition MASQUE un bloc pendant la session — un bloc
        vide est masque a l'enregistrement. Le panneau rendu au
        chargement de la page ne le connait pas : sans un moyen de le
        redemander, le geste que le mode vient de faire resterait
        irreversible jusqu'au rechargement, ce qui est exactement le
        manque que le panneau existe pour combler.

        LE RENDU PASSE PAR LE MEME GABARIT QUE LA PAGE, jamais par un
        second markup : `_panneau_des_masques.html`. Deux rendus du meme
        panneau finiraient par diverger — et le reconstruire en
        JavaScript demanderait de recopier cote client le texte conserve
        du bloc, son ordre et le pluriel du compte.
        / Same template as the page, never a second markup.

        IL REPARE AUSSI LA LIGNE PERIMEE. Un passage demasque ailleurs
        — depuis le mode structure, ou par un tiers — laissait dans le
        panneau une ligne dont le bouton aurait fait revenir en place la
        version EN BASE du bloc, ecrasant ce qui etait en train d'etre
        tape. Redemander le panneau au serveur fait disparaitre cette
        ligne.

        LE DROIT EST CELUI D'ECRIRE, ET LE REFUS EST UN 404.

        Ce panneau montre le TEXTE de passages RETIRES de la lecture :
        `_un_bloc_element.html` ne les rend deja pas pour un simple
        lecteur. Repondre 403 lui apprendrait qu'il existe des passages
        cachees sur cette note. C'est la doctrine du depot — 404, jamais
        403 — et elle vaut ici pour le contenu, pas seulement pour le
        droit.
        / Write right required, and the refusal is a 404: the panel
        shows text removed from reading.

        :return: le partial du panneau — VIDE si rien n'est masque
        """
        from core.models import Page as ModelePage

        from front.views import _utilisateur_a_acces_page
        from front.templatetags.corpus_permissions import passages_masques_de

        # UN PARAMETRE NON NUMERIQUE EST UN 404, PAS UN 500.
        #
        # `filter(pk="abc")` leve `ValueError: Field 'id' expected a
        # number`. C'est le troisieme piege de la doctrine du 404, deja
        # paye une fois dans ce depot — et `lookup_value_regex` ne
        # protege que le pk de l'URL, pas un parametre de requete.
        # / A non-numeric query parameter must be a 404, never a 500.
        identifiant_de_page = request.query_params.get("page", "")
        if not identifiant_de_page.isdigit():
            raise Http404

        page = get_object_or_404(ModelePage, pk=identifiant_de_page)
        if not _utilisateur_a_acces_page(request.user, page):
            raise Http404

        from front.views import _utilisateur_peut_ecrire_page

        if not _utilisateur_peut_ecrire_page(request.user, page):
            raise Http404

        return render(
            request,
            "front/includes/_panneau_des_masques.html",
            {"passages_masques": passages_masques_de(page)},
        )

    @action(detail=False, methods=["POST"])
    def corriger_en_lot(self, request):
        """
        Enregistre une session d'edition : plusieurs blocs d'un coup.
        / Saves an editing session: several blocks at once.

        LOCALISATION : hypostasis_extractor/views_element.py

        SPEC-edition-par-blocs-et-stenotypie.md § 7, § 8, § 10.

        CE QU'IL FAIT, BLOC PAR BLOC (§ 7.3)
          1. texte identique AU CARACTERE PRES -> rien, pas meme un journal ;
          2. texte vide -> `masquer`, JAMAIS `delete` ;
          3. sinon -> reconciliation des portions, verrou de LIGNE.

        IL COMPARE LE TEXTE BRUT, JAMAIS L'EMPREINTE NORMALISEE (§ 7.2).
        `empreinte_du_texte()` met en minuscules et ecrase les espaces :
        comparer dessus jetterait EN SILENCE toute correction de casse et
        toute correction d'espace — les plus frequentes en transcription —
        alors que ces deux-la DEPLACENT les offsets de tout ce qui suit.

        UN LOT PORTE UNE SEULE NOTE. La garde d'analyse est au niveau
        PAGE : un lot a cheval sur deux notes la rendrait impossible a
        poser. Deux pages dans le meme envoi sont donc refusees en bloc.

        LA PORTEE DES REFUS N'EST PAS LA MEME POUR TOUS (§ 8.1)
          - un bloc DISPARU (un tiers a scinde ou fusionne) : ce bloc-la
            est refuse, et lui seul. Surtout PAS de `lectureReload` — la
            session de qui enregistre serait detruite ;
          - un passage cite par une synthese FIGEE : ce bloc-la, et lui
            seul ;
          - une ANALYSE qui tourne : le lot ENTIER est refuse, 0 passe.
            Le controle est pose une fois EN TETE, puis une fois EN FIN
            DE LOT des qu'il y a eu des ecritures — les corrections
            reposent la garde elles-memes, les vidages non. Si l'une ou
            l'autre leve, on annule tout plutot que de laisser une note
            a moitie ecrite.

        :return: le compte rendu du § 7.4 — cinq nombres et la LISTE des
            refus, avec leur motif. Un compte sans liste ne dit pas quoi
            retaper.
        """
        from core.models import EtatDeLaSource, SourceLink, TypeLien
        from core.models import Page as ModelePage
        from hypostasis_extractor.models import AncrageExtraction
        from hypostasis_extractor.services.masquage import (
            hash_du_texte_brut,
            masquer_un_element,
        )
        from hypostasis_extractor.services.reconciliation import (
            reconcilier_les_portions_de_l_element,
        )

        validation = CorrectionEnLotSerializer(data=request.data)
        if not validation.is_valid():
            return _reponse_avec_toast(
                "Rien à enregistrer, ou envoi mal formé.", statut=400,
            )
        blocs_postes = validation.validated_data["blocs"]

        # Les blocs au-dela de la borne sont ECARTES, mais COMPTES et
        # NOMMES — jamais jetes en silence.
        # / Blocks past the cap are dropped, but counted and named.
        borne = CorrectionEnLotSerializer.BORNE_DU_LOT
        hors_borne = blocs_postes[borne:]
        blocs_postes = blocs_postes[:borne]

        # UN MEME BLOC DEUX FOIS DANS LE LOT CORROMPT LE JOURNAL.
        #
        # A la seconde occurrence, l'element en memoire porte encore
        # l'ancien texte (la reconciliation ne met pas a jour l'instance
        # qu'on lui passe) : le hash differe, on rappelle le service, il
        # relit sous verrou, trouve « rien a faire », et rend un
        # `ancien_texte` qui EST le nouveau. Le journal ecrirait alors un
        # « avant » egal a l'« apres », et le compte annoncerait deux
        # blocs modifies pour un seul. On garde donc la PREMIERE
        # occurrence, et on compte les autres comme ecartees.
        # / The same block twice would corrupt the journal: keep the first.
        blocs_dedupliques = []
        deja_vus = set()
        doublons = []
        for bloc in blocs_postes:
            identifiant = str(bloc["identifiant_stable"])
            if identifiant in deja_vus:
                doublons.append(identifiant)
                continue
            deja_vus.add(identifiant)
            blocs_dedupliques.append(bloc)
        blocs_postes = blocs_dedupliques

        identifiants = [str(b["identifiant_stable"]) for b in blocs_postes]
        elements = {
            str(element.identifiant_stable): element
            for element in ElementDocument.objects.select_related("page").filter(
                identifiant_stable__in=identifiants,
            )
        }
        compte_rendu = {
            "blocs_modifies": 0,
            "blocs_masques": 0,
            "ancres_detachees": 0,
            "citations_detachees": 0,
            "blocs_refuses": 0,
            "refus": [],
        }

        def refuser(identifiant, motif):
            compte_rendu["blocs_refuses"] += 1
            compte_rendu["refus"].append(
                {"identifiant_stable": identifiant, "motif": motif},
            )

        for bloc in hors_borne:
            refuser(
                str(bloc["identifiant_stable"]),
                f"écarté : ce lot dépasse la borne de {borne} blocs",
            )
        for identifiant in doublons:
            refuser(
                identifiant,
                "envoyé deux fois dans le même lot : seule la première "
                "version a été retenue",
            )

        if not elements:
            # AUCUN des blocs envoyes n'existe plus : une re-ingestion ou
            # une re-transcription a remplace toute la note pendant la
            # session. Il n'y a plus de page sur laquelle poser une garde,
            # mais il y a quelque chose a DIRE — un 404 muet laisserait
            # l'utilisateur devant un texte qu'il ne peut plus enregistrer
            # sans savoir pourquoi.
            # / None of the posted blocks exist any more: still report it.
            for bloc in blocs_postes:
                refuser(
                    str(bloc["identifiant_stable"]),
                    "ce passage a disparu : la note a été remplacée "
                    "pendant votre travail",
                )
            return _reponse_du_compte_rendu(request, compte_rendu)

        pages = {element.page_id for element in elements.values()}
        if len(pages) > 1:
            return _reponse_avec_toast(
                "Cet envoi mélange deux notes : il n'est pas enregistré.",
                statut=400,
            )
        page = ModelePage.objects.get(pk=pages.pop())

        # QUI NE PEUT PAS LIRE N'APPREND RIEN — 404, jamais 403.
        #
        # Le refus d'ecriture, lui, rend 403 : la personne VOIT deja la
        # note, lui repondre 404 ne cacherait rien et l'egarerait. Mais
        # sans cette premiere garde, poster un `identifiant_stable` vole
        # distinguait « ce bloc existe, tu n'y touches pas » (403) de
        # « ce bloc n'existe pas » (le compte rendu « disparu ») — une
        # difference qui est une information.
        # / No read access: 404. Read but no write: 403, since they can
        # already see the note.
        from front.views import _utilisateur_a_acces_page

        if not _utilisateur_a_acces_page(request.user, page):
            raise Http404

        refus_de_droit = self._refus_si_pas_le_droit(request, page)
        if refus_de_droit:
            return refus_de_droit

        # LA GARDE D'ANALYSE, A L'ENTREE : elle refuse AVANT d'avoir
        # ecrit quoi que ce soit, et c'est le cas frequent.
        #
        # Elle ne suffit pas : une analyse peut demarrer ENSUITE. Les
        # corrections sont couvertes — `reconcilier_les_portions_de_l_element`
        # repose la garde bloc par bloc —, les vidages ne l'etaient pas
        # (`masquer_un_element` est appele ici avec
        # `verifier_les_jobs=False`). C'est pourquoi elle est reposee
        # UNE FOIS en fin de lot, plus bas, des qu'il y a eu des
        # ecritures.
        # / The entry guard refuses before any write. It is not enough:
        # hides do not re-check it, hence the single re-check at the end.
        try:
            verifier_qu_aucune_analyse_ne_tourne(page)
        except EditionBloqueePendantAnalyse:
            return _reponse_avec_toast(
                _message_falc_du_blocage_par_analyse(), statut=409,
            )

        portions_de_la_page = list(
            AncrageExtraction.objects.filter(element__page=page)
            .values_list("pk", flat=True)
        )
        # On compte les citations DETACHEES avant et apres : les services
        # les detachent eux-memes (`detacher_les_citations_des_portions`)
        # sans rendre le compte, et le § 7.4 veut ce nombre A PART de
        # celui des ancres — masquer trente en-tetes peut detacher des
        # dizaines de sources d'articles, et ce doit etre dit.
        # / Counted before and after: the services detach them without
        # returning a count, and § 7.4 wants this number separately.
        def compter_les_citations_detachees():
            return SourceLink.objects.filter(
                ancrage_source_id__in=portions_de_la_page,
                type_lien=TypeLien.CITE,
                etat_de_la_source=EtatDeLaSource.DETACHEE,
            ).count()

        citations_detachees_avant = compter_les_citations_detachees()

        journal_avant = {}
        journal_apres = {}

        # LES VERROUS SE PRENNENT DANS UN ORDRE STABLE, ET C'EST VITAL.
        #
        # Chaque bloc modifie pose un verrou de ligne. Deux lots
        # concurrents sur la meme note qui les prendraient dans l'ordre
        # de leurs envois respectifs s'interbloqueraient — PostgreSQL en
        # tue un, et l'utilisateur recoit un 500. Trier par pk donne le
        # meme ordre a tout le monde.
        # / Two concurrent batches taking row locks in posting order
        # would deadlock: sort by pk so everyone takes them alike.
        blocs_postes.sort(
            key=lambda b: (
                elements[str(b["identifiant_stable"])].pk
                if str(b["identifiant_stable"]) in elements
                else -1
            ),
        )

        try:
            with transaction.atomic():
                for bloc in blocs_postes:
                    identifiant = str(bloc["identifiant_stable"])
                    nouveau_texte = bloc["texte"]
                    element = elements.get(identifiant)
                    if element is None:
                        refuser(
                            identifiant,
                            "ce passage a disparu : quelqu'un l'a coupé, "
                            "recollé ou réingéré pendant votre travail",
                        )
                        continue

                    ancien_texte = element.texte
                    # LE TEXTE BRUT, jamais l'empreinte normalisee.
                    # / The RAW text, never the normalized fingerprint.
                    if hash_du_texte_brut(nouveau_texte) == hash_du_texte_brut(
                        ancien_texte,
                    ):
                        continue

                    # UN TABLEAU NE SE RELIT PAS — refus, ce bloc seul.
                    #
                    # Son `texte` est du markdown « pipe » ; ce qui
                    # s'affiche est un <table> construit APRES le
                    # marquage, et aucun chemin HTML -> markdown n'existe
                    # dans le depot. Ce qu'un client lirait du tableau
                    # rendu differe donc TOUJOURS de la base : l'accepter
                    # l'ecraserait, meme si personne n'y a touche.
                    #
                    # Le mode d'edition ne les envoie pas ; cette garde
                    # est pour le client perime — celui qui a charge la
                    # page avant que la regle n'existe.
                    # / A table's text is pipe markdown and the rendered
                    # table cannot be read back: refuse it.
                    if element.label in LABELS_QUI_NE_SE_RELISENT_PAS:
                        refuser(
                            identifiant,
                            "ce passage est un tableau : il ne peut pas être "
                            "corrigé dans le texte, seulement réingéré.",
                        )
                        continue

                    if element.masque:
                        # UN BLOC DEJA MASQUE QU'ON VIDE EST UN NON-GESTE.
                        #
                        # `masquer_un_element` le sait et ne fait rien,
                        # mais la vue comptait quand meme « 1 masque » et
                        # journalisait un changement qui n'a pas eu lieu.
                        # / Hiding an already-hidden block is a no-op.
                        if not nouveau_texte.strip():
                            continue

                        # CORRIGER UN BLOC MASQUE EST REFUSE (addendum B).
                        #
                        # `demasquer_un_element` ne rattache ses portions
                        # QUE si le texte n'a pas bouge depuis le
                        # masquage — il compare deux empreintes du texte
                        # brut. Une correction passe entre les deux et
                        # rend le masquage IRREVERSIBLE, en silence :
                        # mesure du 29 aout, sur un element portant trois
                        # portions, masquer puis demasquer en rattache 3 ;
                        # masquer, CORRIGER, puis demasquer en rattache 0
                        # et en laisse 3 detachees, pour toujours.
                        #
                        # Le client ne devrait d'ailleurs jamais envoyer
                        # ce texte : en mode edition un element masque est
                        # rendu comme un PLACEHOLDER, pas comme un bloc
                        # modifiable. Le recevoir veut dire que la vue du
                        # client est perimee — un tiers a masque ce bloc
                        # pendant la session. C'est le meme cas qu'un bloc
                        # disparu, et il se traite pareil : on refuse CE
                        # bloc, et lui seul.
                        # / Correcting a hidden block makes its un-hiding
                        # impossible, silently and forever.
                        refuser(
                            identifiant,
                            "ce passage est masqué : le corriger rendrait "
                            "son rétablissement impossible. Rétablissez-le "
                            "d'abord, puis corrigez-le.",
                        )
                        continue

                    try:
                        if not nouveau_texte.strip():
                            detachees = masquer_un_element(
                                element,
                                justification="vidé pendant une session d'édition",
                                utilisateur=request.user,
                                verifier_les_jobs=False,
                            )
                            compte_rendu["blocs_masques"] += 1
                            compte_rendu["ancres_detachees"] += detachees or 0
                        else:
                            resultat = reconcilier_les_portions_de_l_element(
                                element, nouveau_texte,
                            )
                            # LA RELECTURE SOUS VERROU PEUT DIRE « RIEN A
                            # FAIRE ». Le texte lu hors verrou etait
                            # perime : quelqu'un venait d'ecrire le meme
                            # texte. Compter ce bloc modifie et le
                            # journaliser ecrirait un « avant » egal a
                            # l'« apres ». Le `corriger` unitaire pose
                            # deja cette garde ; le lot la manquait.
                            # / The locked re-read may say "nothing to do".
                            if resultat["ancien_texte"] == nouveau_texte:
                                continue
                            compte_rendu["blocs_modifies"] += 1
                            compte_rendu["ancres_detachees"] += len(
                                resultat["detachees"],
                            )
                            ancien_texte = resultat["ancien_texte"]
                    except EditionBloqueeParUneSynthese as blocage:
                        # LE REFUS NOMME LA SYNTHESE QUI BLOQUE (§ 5.3
                        # de SPEC-synthese). Un motif generique — « cite
                        # par une synthese figee » — ne dit pas laquelle :
                        # sur une note ou 7 blocs sur 12 sont geles, on
                        # ne sait ni quelle citation retirer, ni quelle
                        # synthese reproduire.
                        #
                        # C'est la MEME fonction que les quatre gestes
                        # unitaires. Recopier le message ici en ferait
                        # une seconde version, qui divergerait.
                        # / The refusal names the blocking synthesis,
                        # through the very function the single gestures
                        # use — never a second copy of the message.
                        refuser(
                            identifiant,
                            _message_falc_du_blocage_par_synthese(blocage),
                        )
                        continue
                    except ElementDocument.DoesNotExist:
                        # UN TIERS A SUPPRIME CE BLOC PENDANT LE LOT.
                        #
                        # Les elements sont lus AVANT la transaction, sans
                        # verrou : entre cette lecture et le service, une
                        # scission ou une fusion d'autrui peut avoir
                        # remplace la ligne. Les services font alors un
                        # `.get()` qui leve. Sans ce filet, le lot entier
                        # partait en 500 — alors que le § 7.4 promet que
                        # ce bloc-la est refuse, ET LUI SEUL.
                        # / A third party deleted this block mid-batch:
                        # refuse this one, never the whole batch.
                        refuser(
                            identifiant,
                            "ce passage a disparu pendant l'enregistrement : "
                            "quelqu'un l'a coupé, recollé ou réingéré",
                        )
                        continue

                    journal_avant[identifiant] = ancien_texte
                    journal_apres[identifiant] = nouveau_texte

                # LA GARDE D'ANALYSE SE REPOSE UNE FOIS, EN FIN DE LOT.
                #
                # Le § 8.1 promet que le refus subsiste A L'ECRITURE, pas
                # seulement a l'entree. Pour les CORRECTIONS, c'est vrai
                # sans rien faire ici : `reconcilier_les_portions_de_l_element`
                # repose la garde a chaque bloc. Pour les VIDAGES, ca ne
                # l'etait pas — le lot appelle `masquer_un_element` avec
                # `verifier_les_jobs=False`, et un lot fait uniquement de
                # vidages n'etait donc protege que par la garde d'entree.
                # Une analyse qui demarrait entre les deux ecrivait ses
                # ancres sur un texte que le lot etait en train de
                # masquer.
                #
                # UNE SEULE FOIS, PAS UNE PAR BLOC : la reposer dans la
                # boucle couterait deux requetes par bloc masque — 400
                # requetes pour un nettoyage de 200 en-tetes — pour ne
                # rien gagner. Ce qui compte est qu'AUCUNE ecriture ne
                # soit commitee apres le demarrage d'une analyse ; la
                # lever ici annule le lot ENTIER, ce que le § 8.1
                # demande.
                #
                # SEULEMENT S'IL Y A EU DES ECRITURES : un lot ou rien
                # n'a change n'a rien a proteger, et le refuser dirait a
                # la personne qu'elle a perdu un travail qu'elle n'a pas
                # fait.
                # / The write-time guard, re-checked ONCE at the end of
                # the batch: corrections re-check it themselves, hides do
                # not. Only when something was actually written.
                if journal_avant:
                    verifier_qu_aucune_analyse_ne_tourne(page)

                compte_rendu["citations_detachees"] = (
                    compter_les_citations_detachees() - citations_detachees_avant
                )

                # UN journal par LOT, pas un par bloc : c'est le geste que
                # l'humain a fait (§ 10).
                # / One journal entry per BATCH: that is the human gesture.
                if journal_avant:
                    PageEdit.objects.create(
                        page=page,
                        user=request.user,
                        type_edit="contenu",
                        description=(
                            f"Session d'édition : "
                            f"{compte_rendu['blocs_modifies']} modifié(s), "
                            f"{compte_rendu['blocs_masques']} masqué(s)"
                        )[:500],
                        donnees_avant={"blocs": journal_avant},
                        # LE § 10 EXIGE LE COMPTE RENDU DANS LE JOURNAL,
                        # pas seulement l'avant et l'apres : les ancres et
                        # les citations detachees ne se relisent nulle part
                        # ailleurs, et ce sont elles qui disent ce que le
                        # geste a coute.
                        # / § 10 wants the report in the journal too.
                        donnees_apres={
                            "blocs": journal_apres,
                            "compte_rendu": {
                                cle: valeur
                                for cle, valeur in compte_rendu.items()
                                if cle != "refus"
                            },
                            "refus": compte_rendu["refus"],
                        },
                    )
        except EditionBloqueePendantAnalyse:
            # Une analyse a demarre PENDANT l'enregistrement : le lot
            # entier est annule, 0 passe. Mieux vaut tout refuser que
            # laisser une note a moitie ecrite (§ 8.1).
            # / An analysis started mid-save: the whole batch rolls back.
            return _reponse_avec_toast(
                _message_falc_du_blocage_par_analyse(), statut=409,
            )

        return _reponse_du_compte_rendu(request, compte_rendu)

    @action(
        detail=True,
        methods=["GET"],
        permission_classes=[permissions.AllowAny],
    )
    def bloc(self, request, pk=None):
        """
        Rend UN SEUL bloc de lecture, pret a remplacer le sien.
        / Renders ONE reading block, ready to replace its own.

        LOCALISATION : hypostasis_extractor/views_element.py

        POURQUOI CET ENDPOINT EXISTE (SPEC-edition-par-blocs § 11.3)

        Sans lui, la seule facon de montrer un bloc qui a change est
        `lectureReload` : le front refait `zoneLecture.innerHTML` pour la
        page entiere. Il y perd le defilement, le focus, et — le jour ou
        un mode d'edition existera — le travail en cours.

        LE RENDU PASSE PAR LE SERVICE DE LA PAGE, JAMAIS PAR UN RENDU A PART.
        `construire_les_blocs_de_lecture` est appele sur la page, puis on
        prend le bloc vise. C'est plus de travail que de rendre un bloc
        seul, et c'est voulu : un second chemin de rendu finirait par
        rendre un bloc qui ne ressemble plus a ses voisins — numerotation,
        surlignage, minutage —, et rien ne le signalerait. Un test epingle
        cette egalite.
        / Rendering goes through the page service, never a separate path.

        LE DROIT EST CELUI DE LIRE, pas celui d'ecrire : un bloc se
        regarde. Ce sont les BOUTONS a l'interieur qui demandent le droit
        d'ecrire, et `la_note_est_modifiable` les gouverne — la meme regle
        que la page.
        / Reading right here; the buttons inside are gated separately.

        POURQUOI `AllowAny` DANS UN VIEWSET `IsAuthenticated`

        Parce que cet endpoint rend un morceau d'une PAGE, et qu'une page
        rangee dans un carnet PUBLIC se lit sans compte
        (`_utilisateur_a_acces_dossier` : « Dossier public → accessible a
        tous (y compris anonymes) »). Herite `IsAuthenticated`, ce bloc
        serait moins accessible que la page qui le contient : le lecteur
        anonyme d'une note publique verrait ses echanges de bloc echouer,
        alors qu'il a le texte sous les yeux.

        Le controle n'est pas relache pour autant, il est DEPLACE : c'est
        `_utilisateur_a_acces_page` — la regle exacte de l'ecran de
        lecture — qui decide, et son refus est un 404.
        / AllowAny because the reading page itself is public for public
        notebooks; the check moves into the body, and refuses with 404.

        UN pk MORT REND 404, ET RIEN D'AUTRE. Surtout pas le
        `lectureReload` de `_reponse_passage_disparu` : l'appelant a
        demande UN bloc, lui recharger la page serait exactement le
        defaut qu'on repare.
        / A dead pk answers a plain 404, never a full reload.
        """
        # Import paresseux : le cycle front <-> extractor.
        # / Lazy import: the front <-> extractor cycle.
        from front.views import _utilisateur_a_acces_page

        element = ElementDocument.objects.select_related("page").filter(
            pk=pk,
        ).first()
        if element is None:
            raise Http404

        # Doctrine du projet : 404, jamais 403. Un 403 apprendrait au
        # visiteur que cette note existe.
        # / 404, never 403: a 403 would reveal that the note exists.
        if not _utilisateur_a_acces_page(request.user, element.page):
            raise Http404

        # LE MEME rendu que celui des reponses d'operation. Deux chemins
        # de rendu pour un meme bloc finiraient par diverger, et c'est
        # exactement ce que ce chantier existe pour empecher.
        # / The SAME rendering as the operation responses use.
        html = _html_du_bloc(request, element, pour_swap_oob=False)
        if html is None:
            raise Http404
        return HttpResponse(html, status=200)

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
        element.refresh_from_db()
        return _reponse_de_succes_avec_le_bloc(request, element, message)

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

        element.refresh_from_db()
        return _reponse_de_succes_avec_le_bloc(
            request, element,
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
        element.refresh_from_db()
        return _reponse_de_succes_avec_le_bloc(request, element, message)
