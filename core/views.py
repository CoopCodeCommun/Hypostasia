import logging
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from django.shortcuts import render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import permissions, status, viewsets
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Dossier, EtatIngestion, Page, RoleSpecialDossier, VisibiliteDossier
from .services.corpus import (
    carnets_ou_ecrire,
    deplacer_une_note_vers_un_carnet,
    notes_visibles_par,
    ranger_une_note_dans_un_carnet,
)
from .serializers import ClasserDepuisExtensionSerializer, PageCreateSerializer, PageListSerializer

logger = logging.getLogger("core")

# Parametres de tracking a retirer lors de la normalisation d'URL
# / Tracking parameters to strip during URL normalization
PARAMETRES_TRACKING = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "ref", "mc_cid", "mc_eid",
}


def normaliser_url(url_brute):
    """
    Normalise une URL pour la comparaison :
    - Retire les parametres UTM et de tracking
    - Retire le fragment (#...)
    - Retire le trailing slash (sauf pour la racine d'un domaine)
    / Normalize a URL for comparison:
    / - Remove UTM and tracking parameters
    / - Remove fragment (#...)
    / - Remove trailing slash (except for domain root)
    """
    if not url_brute:
        return url_brute

    try:
        url_decomposee = urlparse(url_brute)

        # Retirer les parametres de tracking / Remove tracking parameters
        parametres_originaux = parse_qs(url_decomposee.query, keep_blank_values=True)
        parametres_filtres = {
            cle: valeurs
            for cle, valeurs in parametres_originaux.items()
            if cle not in PARAMETRES_TRACKING
        }
        query_nettoyee = urlencode(parametres_filtres, doseq=True)

        # Reconstruire l'URL sans fragment et avec query nettoyee
        # / Rebuild URL without fragment and with cleaned query
        url_normalisee = urlunparse((
            url_decomposee.scheme,
            url_decomposee.netloc,
            url_decomposee.path,
            url_decomposee.params,
            query_nettoyee,
            "",  # Pas de fragment / No fragment
        ))

        # Retirer le trailing slash (sauf si le path est juste /)
        # / Remove trailing slash (unless path is just /)
        if url_normalisee.endswith("/") and url_decomposee.path != "/":
            url_normalisee = url_normalisee[:-1]

        return url_normalisee
    except Exception:
        return url_brute


class CarnetRefuse(Exception):
    """
    Le carnet demande n'existe pas, ou l'utilisateur ne peut pas y ecrire.
    / The requested notebook is unknown or not writable by this user.

    LOCALISATION : core/views.py

    C'EST UNE EXCEPTION ET NON UN REPLI, ET C'EST TOUT LE SUJET. Avant,
    un carnet refuse etait remplace EN SILENCE par le fourre-tout : la
    capture repondait 201, l'utilisateur croyait avoir range dans le
    carnet de classe, et la note etait ailleurs. Depuis que l'extension
    fait CHOISIR le carnet avant la capture, detourner ce choix sans le
    dire est un mensonge.
    / An exception, not a fallback: a refused notebook used to be
    silently swapped for the inbox while the capture answered 201.
    """


@method_decorator(csrf_exempt, name="dispatch")
class PageViewSet(viewsets.ViewSet):
    """
    API pour la gestion des Pages — utilisee exclusivement par l'extension navigateur.
    Pas de templates, pas de rendu HTML : uniquement du JSON.
    / API for Page management — used exclusively by the browser extension.
    / No templates, no HTML rendering: JSON only.
    """
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """
        Liste les notes du perimetre du porteur du jeton, avec filtre
        optionnel par URL. L'extension appelle `?url=...` avant de
        capturer, pour savoir si la page est deja la.
        / Lists the token holder's notes, with an optional URL filter.

        LOCALISATION : core/views.py

        AUTHENTIFICATION EXIGEE, ET PERIMETRE PAR OBJET. Cet endpoint a
        rendu `Page.objects.all()` a qui le demandait, sans jeton, avec
        le HTML complet de chaque note et `Access-Control-Allow-Origin:
        *` — donc lisible par n'importe quel site visite. Mesure du
        20 aout 2026 avant correction : 200, 13 notes, 291 840 octets.
        / Authentication required and per-object scope: this endpoint
        used to hand the whole corpus to anyone, from any origin.

        Le jeton est exige ICI meme si un carnet public est lisible par
        un anonyme sur le site : `/api/pages/` n'est pas une surface de
        consultation, c'est l'API de l'extension — et l'extension a
        toujours un jeton, sans quoi elle ne peut rien capturer. La
        consultation publique vit sur `/carnets/`, avec une interface.
        / The token is required even though public notebooks are
        anonymously readable on the site: this is the extension's API,
        not a browsing surface, and the extension always has a token.
        """
        if not request.user or not request.user.is_authenticated:
            return Response(
                {"detail": "Authentification requise. Ajoutez votre token API "
                           "dans les options de l'extension."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        pages_du_perimetre = notes_visibles_par(request.user).order_by("-created_at")

        # Filtre par URL si le parametre est present (utilise par l'extension)
        # / Filter by URL if parameter is present (used by extension)
        url_filtre = request.query_params.get("url")
        if url_filtre:
            url_filtre_normalisee = normaliser_url(url_filtre)
            # Chercher par URL exacte et par URL normalisee
            # / Search by exact URL and by normalized URL
            pages_du_perimetre = pages_du_perimetre.filter(url=url_filtre_normalisee)

        serializer = PageListSerializer(pages_du_perimetre, many=True)
        return Response(serializer.data)

    def create(self, request):
        """
        Cree une nouvelle Page a partir des donnees envoyees par l'extension.
        Exige une authentification (token ou session). Assigne l'owner automatiquement.
        Avant creation, verifie la deduplication filtree par owner + dossiers partages.
        / Creates a new Page from data sent by the extension.
        / Requires authentication (token or session). Assigns owner automatically.
        / Before creation, checks deduplication filtered by owner + shared folders.

        LOCALISATION : core/views.py

        FLUX :
        1. Verifier l'authentification (401 si absent)
        2. Normaliser l'URL soumise
        3. Repondre aux trois conflits AVANT toute validation (voir
           ci-dessous pourquoi cet ordre n'est pas negociable)
        4. Valider via PageCreateSerializer
        5. Resoudre le carnet demande (refus explicite si interdit)
        6. Creer la page, la ranger, lancer l'ingestion ELEMENT

        LES CONFLITS SE TRAITENT AVANT `is_valid()`, ET C'EST OBLIGATOIRE.
        `Page.url` porte une contrainte d'unicite en base
        (`unique_url_si_presente`) ; DRF en deduit tout seul un
        `UniqueValidator` sur le champ `url` du serializer. Il se
        declenche donc DANS `is_valid()`, avant qu'on ait pu regarder
        quoi que ce soit — et rend un 400 « Un objet page avec ce champ
        url existe deja » que l'extension affichait « Erreur creation
        (400) ». Placer nos reponses apres la validation les rendrait
        inatteignables.
        / The conflict checks run BEFORE is_valid(): DRF derives a
        UniqueValidator from the model's unique constraint on url, which
        fires inside is_valid() and would make these answers dead code.
        """
        # Exiger l'authentification pour la creation
        # / Require authentication for creation
        if not request.user or not request.user.is_authenticated:
            return Response(
                {"detail": "Authentification requise. Ajoutez votre token API dans les options de l'extension."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # L'empreinte de contenu se calcule ici avec la MEME fonction que
        # le serializer : voir le commentaire du controle de doublon.
        # / Same fingerprint function as the serializer.
        from front.services.texte_depuis_html import empreinte_d_une_capture

        # Normaliser l'URL avant validation
        # / Normalize URL before validation
        donnees_soumises = request.data.copy()
        url_soumise = donnees_soumises.get("url", "")
        if url_soumise:
            donnees_soumises["url"] = normaliser_url(url_soumise)

        # Le perimetre de dedup est celui de la LECTURE : une note qu'on
        # peut ouvrir est une note qu'on ne veut pas recapturer.
        # / The dedup scope is the READ scope.
        pages_accessibles = notes_visibles_par(request.user)

        # Verifier le doublon par URL normalisee dans le perimetre de l'user
        # / Check for duplicate by normalized URL within user's scope
        url_normalisee = donnees_soumises.get("url", "")
        if url_normalisee:
            page_existante_par_url = pages_accessibles.filter(url=url_normalisee).first()
            if page_existante_par_url:
                logger.info(
                    "PageViewSet.create: doublon par URL — page existante %d pour url=%s (user=%s)",
                    page_existante_par_url.pk,
                    url_normalisee,
                    request.user.username,
                )
                return Response(
                    {
                        "detail": "Page deja enregistree avec cette URL.",
                        "existing_page_id": page_existante_par_url.pk,
                        # Les trois conflits sortent en 409 : sans un code
                        # machine, la popup ne peut pas les distinguer et
                        # affiche un echec comme un succes.
                        # / Three conflicts share the 409; the code is
                        # what lets the popup tell them apart.
                        "code": "deja_dans_mon_perimetre",
                    },
                    status=status.HTTP_409_CONFLICT,
                )

        # Verifier le doublon par contenu, avec l'empreinte QUE LE SERVEUR
        # CALCULE. Elle ne vient plus du client : le client la calculait
        # autrement, les deux valeurs ne se rejoignaient pas, et ce
        # controle-ci ne se declenchait donc jamais (voir
        # PageCreateSerializer.content_hash).
        # / Duplicate check by content, using the fingerprint the SERVER
        # computes; the client's own value never matched, so this check
        # never fired.
        html_de_la_capture = donnees_soumises.get("html_readability", "")
        texte_de_la_capture = donnees_soumises.get("text_readability", "")
        empreinte_de_la_capture = empreinte_d_une_capture(
            html_de_la_capture, texte_de_la_capture,
        )
        # Une capture SANS CONTENU n'est pas « le meme contenu » qu'une
        # autre capture sans contenu : ce sont deux vides, pas un
        # doublon. Sans cette porte, elles se refuseraient l'une l'autre
        # sur l'empreinte de la chaine vide.
        # / An EMPTY capture is not "the same content" as another empty
        # one: two voids are not a duplicate.
        la_capture_a_du_contenu = bool(
            (html_de_la_capture or "").strip() or (texte_de_la_capture or "").strip()
        )
        page_existante_par_hash = None
        if la_capture_a_du_contenu:
            page_existante_par_hash = pages_accessibles.filter(
                content_hash=empreinte_de_la_capture
            ).first()
        if page_existante_par_hash:
            logger.info(
                "PageViewSet.create: doublon par content_hash — page existante %d "
                "hash=%s url_existante=%s url_soumise=%s (user=%s)",
                page_existante_par_hash.pk,
                empreinte_de_la_capture[:16],
                page_existante_par_hash.url,
                url_normalisee,
                request.user.username,
            )
            return Response(
                {
                    "detail": "Contenu identique deja enregistre.",
                    "existing_page_id": page_existante_par_hash.pk,
                    "code": "contenu_deja_enregistre",
                },
                status=status.HTTP_409_CONFLICT,
            )

        # L'URL est unique GLOBALEMENT en base (`unique_url_si_presente`)
        # alors que la dedup ci-dessus est scopee au perimetre. Un tiers
        # a donc pu prendre cette URL dans un carnet qu'on ne peut pas
        # ouvrir. Sans ce controle, la contrainte remonte en 400
        # « Un objet page avec ce champ url existe deja », que l'extension
        # affichait « Erreur creation (400) ». On le dit clairement, avec
        # un code que la popup sait traduire.
        # / The URL is globally unique while dedup is scoped: say plainly
        # that a third party holds it, with a machine-readable code.
        if url_normalisee and Page.objects.filter(url=url_normalisee).exists():
            logger.info(
                "PageViewSet.create: url=%s deja prise hors du perimetre de %s",
                url_normalisee, request.user.username,
            )
            return Response(
                {
                    "detail": "Cette page a déjà été capturée sur cette "
                              "instance, dans un carnet auquel vous n'avez "
                              "pas accès.",
                    "code": "url_prise_ailleurs",
                },
                status=status.HTTP_409_CONFLICT,
            )

        # Les conflits sont ecartes : on peut valider.
        # / Conflicts are out of the way: validate.
        serializer = PageCreateSerializer(data=donnees_soumises)
        if not serializer.is_valid():
            logger.warning(
                "PageViewSet.create: erreurs de validation — %s",
                serializer.errors,
            )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Le carnet demande par l'extension. Resolu AVANT la creation :
        # une destination refusee ne doit pas laisser une note derriere
        # elle. Le `dossier_id` sort du serializer, donc c'est un entier
        # ou rien : `Dossier.objects.filter(pk="abc")` leve une
        # `ValueError` que personne n'attrape — un 500 pour une faute de
        # frappe du client.
        # / Resolved BEFORE creation, from the validated data: a raw
        # payload value would raise ValueError on a non-integer pk.
        try:
            carnet_de_destination = _resoudre_dossier(
                request.user, serializer.validated_data.get("dossier_id"),
            )
        except CarnetRefuse as carnet_refuse:
            logger.warning(
                "PageViewSet.create: carnet refuse pour %s — %s",
                request.user.username, carnet_refuse,
            )
            return Response(
                {"dossier_id": [str(carnet_refuse)]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Creer la page avec l'owner, puis la ranger via le service :
        # il pose la FK (premier carnet) ET l'appartenance N-N d'un coup
        # (SPEC-corpus § 4.3, phase D).
        # / Create the page, then file it through the service: it sets
        # the FK (first notebook) AND the N-N membership at once.
        page_creee = serializer.save(owner=request.user)
        ranger_une_note_dans_un_carnet(
            page_creee, carnet_de_destination, request.user,
        )
        logger.info(
            "PageViewSet.create: Page %d creee — url=%s owner=%s dossier=%s",
            page_creee.pk,
            page_creee.url,
            request.user.username,
            page_creee.dossier,
        )

        # U4 (decision D2, ordre 2) : une capture web nourrit AUSSI le
        # moteur ELEMENT — meme patron que l'import fichier (BR-B). Le
        # pipeline synchrone ci-dessus a rempli html_readability :
        # l'affichage reste ANCIEN (double ecriture) jusqu'a ce que les
        # elements existent. La page devient ELEMENT quand la tache
        # aboutit ; un echec laisse une page ANCIEN lisible. Broker en
        # panne : la creation reste un succes, sans fausse promesse.
        # / Web capture also feeds the ELEMENT engine, same pattern as
        # file import; a dead broker must not turn a successful capture
        # into a 500.
        if (page_creee.html_original or "").strip():
            from hypostasis_extractor.tasks_element import (
                ingerer_une_capture_web_avec_docling,
            )
            try:
                ingerer_une_capture_web_avec_docling.delay(page_creee.pk)
                # Meme patron que l'import fichier et la relance
                # (front/views.py:2103 et 5657) : constante EtatIngestion
                # (pas de chaine brute) + horodatage pose. Sans
                # ingestion_maj_le, la detection du fantome (U2) ne peut
                # jamais se declencher pour une capture web, et le tri
                # "-ingestion_maj_le" du dropdown la classerait en tete
                # (NULL en premier sous PostgreSQL).
                # / Same pattern as file import and relaunch: use the
                # enum, not a raw string, and stamp ingestion_maj_le —
                # otherwise ghost detection can never fire for a web
                # capture, and the dropdown's ordering misplaces it.
                Page.objects.filter(
                    pk=page_creee.pk, ingestion_etat="",
                ).update(
                    ingestion_etat=EtatIngestion.EN_ATTENTE,
                    ingestion_maj_le=timezone.now(),
                )
            except Exception as erreur_de_broker:
                logger.error(
                    "PageViewSet.create: ingestion web NON lancee pour la "
                    "page %d (broker indisponible ? %s) — la page reste "
                    "sur l'ancien moteur",
                    page_creee.pk, erreur_de_broker,
                )

        return Response(
            PageListSerializer(page_creee).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["GET"], url_path="me")
    def me(self, request):
        """
        Retourne les infos de l'utilisateur authentifie.
        L'extension l'appelle pour afficher "Connecte en tant que...".
        / Returns authenticated user info.
        / Extension calls this to display "Connected as...".

        LOCALISATION : core/views.py

        FLUX :
        1. Si pas authentifie → {authenticated: false}
        2. Si authentifie → {authenticated: true, username, email}
        """
        if not request.user or not request.user.is_authenticated:
            return Response(
                {"authenticated": False},
                status=status.HTTP_200_OK,
            )
        return Response({
            "authenticated": True,
            "username": request.user.username,
            "email": request.user.email,
        })

    @action(detail=False, methods=["GET"], url_path="mes_dossiers")
    def mes_dossiers(self, request):
        """
        Retourne la liste JSON des dossiers de l'utilisateur (owner + partages).
        L'extension l'appelle apres recolte pour afficher les boutons de classement.
        / Returns JSON list of user's folders (owned + shared).
        / Extension calls this after harvest to show classification buttons.

        LOCALISATION : core/views.py

        FLUX :
        1. Verifier l'authentification (401 si absent)
        2. Recuperer les dossiers owner + dossiers partages
        3. Combiner, deduper, trier par nom
        4. Retourner la liste [{id, name}, ...]
        """
        if not request.user or not request.user.is_authenticated:
            return Response(
                {"detail": "Authentification requise."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # La liste vient du service : les partages par GROUPE y sont, ce
        # que la version locale de cette regle oubliait.
        # / From the service: group shares are honoured here.
        carnets_inscriptibles = carnets_ou_ecrire(request.user).order_by("name")

        liste_dossiers = []
        for dossier_courant in carnets_inscriptibles:
            liste_dossiers.append({
                "id": dossier_courant.pk,
                "name": dossier_courant.name,
            })
        return Response(liste_dossiers)

    @action(detail=False, methods=["GET"], url_path="mes_carnets")
    def mes_carnets(self, request):
        """
        Les carnets ou l'utilisateur peut ecrire — ce que la popup met
        dans son menu avant de capturer.
        / The notebooks the user may write to, for the popup's dropdown.

        LOCALISATION : core/views.py

        POURQUOI PAS `mes_dossiers` : celui-la ne rend que `{id, name}`,
        et une extension deja installee continue de l'appeler. La popup
        a besoin de deux choses de plus — le ROLE, pour reconnaitre le
        fourre-tout sans comparer son nom (un carnet renomme restait
        propose en double), et la VISIBILITE, pour avertir au moment du
        geste qu'un carnet public publie la note (SPEC-corpus § 7.3).
        / A second endpoint because the old one is a live contract; the
        popup needs the role and the visibility on top of it.

        CETTE LECTURE N'ECRIT RIEN. Le fourre-tout « A ranger » nait a la
        premiere capture qui en a besoin, pas a l'ouverture de la popup :
        ouvrir un menu ne doit pas creer un carnet.
        / This GET writes nothing: the inbox is born on first capture.
        """
        if not request.user or not request.user.is_authenticated:
            return Response(
                {"detail": "Authentification requise."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        carnets_inscriptibles = carnets_ou_ecrire(request.user).order_by("name")

        liste_des_carnets = []
        for carnet_courant in carnets_inscriptibles:
            liste_des_carnets.append({
                "id": carnet_courant.pk,
                "nom": carnet_courant.name,
                "role_special": carnet_courant.role_special,
                "visibilite": carnet_courant.visibilite,
                # Drapeau explicite plutot qu'une comparaison de chaine
                # cote extension : la valeur de l'enum reste au serveur.
                # / An explicit flag, so the enum value stays server-side.
                "est_public": (
                    carnet_courant.visibilite == VisibiliteDossier.PUBLIC
                ),
            })
        return Response(liste_des_carnets)

    @action(detail=True, methods=["POST"], url_path="classer_depuis_extension")
    def classer_depuis_extension(self, request, pk=None):
        """
        Deplace une page dans un dossier. Appele par l'extension apres recolte.
        Verifie que l'utilisateur est bien le proprietaire de la page.
        / Moves a page into a folder. Called by extension after harvest.
        / Verifies that user owns the page.

        LOCALISATION : core/views.py

        FLUX :
        1. Verifier l'authentification (401 si absent)
        2. Recuperer la page par pk et verifier l'ownership (403 si pas owner)
        3. Valider dossier_id via ClasserDepuisExtensionSerializer
        4. Verifier que le dossier est accessible par l'utilisateur
        5. Deplacer la page dans le dossier cible
        """
        if not request.user or not request.user.is_authenticated:
            return Response(
                {"detail": "Authentification requise."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Recuperer la page et verifier l'ownership
        # / Retrieve page and check ownership
        try:
            page_a_classer = Page.objects.get(pk=pk)
        except Page.DoesNotExist:
            return Response(
                {"detail": "Page introuvable."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if page_a_classer.owner != request.user:
            return Response(
                {"detail": "Vous n'etes pas le proprietaire de cette page."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Valider les donnees via serializer DRF
        # / Validate data via DRF serializer
        serializer_classement = ClasserDepuisExtensionSerializer(data=request.data)
        if not serializer_classement.is_valid():
            return Response(serializer_classement.errors, status=status.HTTP_400_BAD_REQUEST)
        dossier_id_cible = serializer_classement.validated_data["dossier_id"]

        # Le carnet doit exister ET etre inscriptible. Le service porte
        # la regle, partages par GROUPE compris — la version locale les
        # ignorait, et un membre de groupe se voyait refuser un carnet
        # que le site lui ouvrait.
        # / The service carries the rule, group shares included.
        dossier_cible = carnets_ou_ecrire(request.user).filter(
            pk=dossier_id_cible
        ).first()
        if dossier_cible is None:
            return Response(
                {"detail": "Ce carnet n'existe pas, ou vous n'avez pas le "
                           "droit d'y écrire."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Deplacement via le service : sort du carnet designe par la FK
        # (« A ranger » dans le flux nominal), entre dans la cible, et
        # maintient la table de liaison (SPEC-corpus § 4.3, phase D).
        # / Move through the service: FK and link table stay in sync.
        deplacer_une_note_vers_un_carnet(
            page_a_classer, dossier_cible, request.user
        )
        logger.info(
            "PageViewSet.classer_depuis_extension: Page %d deplacee dans dossier '%s' (user=%s)",
            page_a_classer.pk,
            dossier_cible.name,
            request.user.username,
        )

        return Response({"detail": "Page classee.", "dossier_name": dossier_cible.name})


def _resoudre_dossier(utilisateur, dossier_id_soumis):
    """
    Resout le carnet ou ranger une capture :
    - un `dossier_id` fourni doit exister ET etre inscriptible, sinon on
      REFUSE ;
    - aucun `dossier_id` → le fourre-tout de l'utilisateur, cree au
      besoin.
    / Resolves the notebook for a capture: a supplied id must exist AND
    be writable, otherwise it is REFUSED; no id falls back to the inbox.

    LOCALISATION : core/views.py

    LE REFUS EST LE CHANGEMENT. Cette fonction retombait en silence sur
    le fourre-tout quand le carnet demande etait inconnu ou interdit.
    Tant que l'extension ne choisissait rien, personne ne s'en apercevait.
    Depuis qu'elle fait choisir, ce repli enverrait la note ailleurs que
    la ou l'utilisateur l'a demandee — en repondant « enregistree ».
    / Silent fallback was harmless while nothing chose; it is a lie now
    that the extension makes the user choose.

    :raises CarnetRefuse: carnet inconnu, ou sans droit d'ecriture
    :return: le Dossier ou ranger la capture
    """
    if dossier_id_soumis:
        carnet_demande = carnets_ou_ecrire(utilisateur).filter(
            pk=dossier_id_soumis
        ).first()
        if carnet_demande is None:
            # Un carnet inconnu et un carnet interdit recoivent la MEME
            # reponse : doctrine du 404, jamais 403 — sinon l'extension
            # devient un outil pour savoir quels carnets existent.
            # / Unknown and forbidden get the SAME answer.
            raise CarnetRefuse(
                "Ce carnet n'existe pas, ou vous n'avez pas le droit d'y "
                "écrire. / Unknown notebook, or no write access."
            )
        return carnet_demande

    # Aucun carnet demande : le fourre-tout de l'utilisateur, retrouve
    # par son ROLE technique et plus par son nom — un carnet renomme
    # reste retrouve (SPEC-corpus § 6.3). Le nom n'est qu'une valeur
    # d'affichage initiale.
    # / No notebook asked for: the user's inbox, found by its technical
    # ROLE, no longer by name.
    dossier_a_ranger, _cree = Dossier.objects.get_or_create(
        role_special=RoleSpecialDossier.A_RANGER,
        owner=utilisateur,
        defaults={"name": "A ranger"},
    )
    return dossier_a_ranger


@method_decorator(csrf_exempt, name="dispatch")
class SidebarViewSet(viewsets.ViewSet):
    """
    Endpoint de production pour la sidebar de l'extension navigateur.
    Recoit ?url=... et renvoie le HTML de la sidebar
    (soit les arguments de la page, soit un message "aucune analyse").
    Remplace l'ancienne fonction test_sidebar_view.
    / Production endpoint for the browser extension sidebar.
    / Receives ?url=... and returns sidebar HTML
    / (either page arguments or a "no analysis" message).
    / Replaces the former test_sidebar_view function.
    """
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """
        Recherche une note DU PERIMETRE du visiteur par URL, et renvoie
        le HTML de la sidebar.
        / Looks up a note IN THE VISITOR'S SCOPE by URL.

        LOCALISATION : core/views.py

        LA RECHERCHE EST BORNEE AU PERIMETRE, ET LA REPONSE NE DIT PAS
        POURQUOI. « Rien ici » et « pas pour toi » rendent le meme
        message : sinon cet endpoint devient un moyen de savoir, URL par
        URL, ce que l'instance contient. C'est la doctrine du 404, jamais
        403 (AGENTS.md).
        / Scoped lookup, and the answer never distinguishes absent from
        forbidden: otherwise this endpoint tells a stranger, URL by URL,
        what the instance holds.
        """
        url_recue = request.query_params.get("url", "")

        # Recherche de la page par URL normalisee, DANS le perimetre
        # / Look up page by normalized URL, WITHIN the scope
        notes_du_perimetre = notes_visibles_par(request.user)
        page_trouvee = None
        if url_recue:
            url_normalisee = normaliser_url(url_recue)
            page_trouvee = notes_du_perimetre.filter(url=url_normalisee).first()

            # Fallback : recherche par URL exacte si la normalisee n'a rien donne
            # / Fallback: search by exact URL if normalized didn't match
            if not page_trouvee:
                page_trouvee = notes_du_perimetre.filter(url=url_recue).first()

            # Dernier fallback : avec/sans trailing slash
            # / Last fallback: with/without trailing slash
            if not page_trouvee and url_recue.endswith("/"):
                page_trouvee = notes_du_perimetre.filter(
                    url=url_recue[:-1]
                ).first()
            elif not page_trouvee:
                page_trouvee = notes_du_perimetre.filter(
                    url=url_recue + "/"
                ).first()

        if page_trouvee:
            return render(
                request,
                "core/includes/sidebar_items.html",
                {"page": page_trouvee},
            )

        # Aucune page trouvee → message informatif
        # / No page found → informational message
        from django.http import HttpResponse
        return HttpResponse(
            '<div style="padding: 20px; text-align: center;">'
            "<p>Aucune analyse trouvee pour cette URL.</p>"
            '<div style="margin-top:20px; color:#999; font-size:12px;">'
            f"URL: {url_recue or 'Inconnue'}"
            "</div></div>"
        )
