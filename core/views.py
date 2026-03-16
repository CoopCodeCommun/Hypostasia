import logging
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from django.db.models import Q
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import permissions, status, viewsets
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Dossier, DossierPartage, Page
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


def _ids_dossiers_accessibles(utilisateur):
    """
    Retourne les IDs des dossiers possedes par l'utilisateur + ceux partages avec lui.
    Utilise par create() et classer_depuis_extension() pour determiner le perimetre de dedup et d'acces.
    / Returns IDs of folders owned by the user + those shared with them.
    Used by create() and classer_depuis_extension() for dedup and access scope.

    LOCALISATION : core/views.py
    """
    ids_dossiers_owner = Dossier.objects.filter(owner=utilisateur).values_list("pk", flat=True)
    ids_dossiers_partages = DossierPartage.objects.filter(
        utilisateur=utilisateur
    ).values_list("dossier_id", flat=True)
    return set(ids_dossiers_owner) | set(ids_dossiers_partages)


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
        Liste les pages, avec filtre optionnel par URL.
        L'extension utilise ?url=... pour verifier si une page existe deja.
        La recherche se fait par URL normalisee (sans UTM, sans fragment, sans trailing slash).
        / Lists pages, with optional URL filter.
        / The extension uses ?url=... to check if a page already exists.
        / Search is done by normalized URL (no UTM, no fragment, no trailing slash).
        """
        toutes_les_pages = Page.objects.all().order_by("-created_at")

        # Filtre par URL si le parametre est present (utilise par l'extension)
        # / Filter by URL if parameter is present (used by extension)
        url_filtre = request.query_params.get("url")
        if url_filtre:
            url_filtre_normalisee = normaliser_url(url_filtre)
            # Chercher par URL exacte et par URL normalisee
            # / Search by exact URL and by normalized URL
            toutes_les_pages = toutes_les_pages.filter(url=url_filtre_normalisee)

        serializer = PageListSerializer(toutes_les_pages, many=True)
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
        3. Valider via PageCreateSerializer
        4. Verifier la dedup par URL dans le perimetre owner + partages
        5. Verifier la dedup par content_hash dans le meme perimetre
        6. Resoudre le dossier cible (dossier_id ou "A ranger" par defaut)
        7. Creer la page avec owner + dossier
        """
        # Exiger l'authentification pour la creation
        # / Require authentication for creation
        if not request.user or not request.user.is_authenticated:
            return Response(
                {"detail": "Authentification requise. Ajoutez votre token API dans les options de l'extension."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Normaliser l'URL avant validation
        # / Normalize URL before validation
        donnees_soumises = request.data.copy()
        url_soumise = donnees_soumises.get("url", "")
        if url_soumise:
            donnees_soumises["url"] = normaliser_url(url_soumise)

        serializer = PageCreateSerializer(data=donnees_soumises)

        if not serializer.is_valid():
            logger.warning(
                "PageViewSet.create: erreurs de validation — %s",
                serializer.errors,
            )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Determiner le perimetre de dedup : dossiers owner + partages
        # / Determine dedup scope: owner folders + shared folders
        ids_dossiers = _ids_dossiers_accessibles(request.user)

        # Pages accessibles = dans les dossiers de l'user + pages sans dossier de l'user
        # / Accessible pages = in user's folders + user's pages without folder
        pages_accessibles = Page.objects.filter(
            Q(dossier_id__in=ids_dossiers) | Q(dossier__isnull=True, owner=request.user)
        )

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
                    },
                    status=status.HTTP_409_CONFLICT,
                )

        # Verifier le doublon par content_hash dans le perimetre de l'user
        # / Check for duplicate by content_hash within user's scope
        content_hash_soumis = donnees_soumises.get("content_hash", "")
        if content_hash_soumis:
            page_existante_par_hash = pages_accessibles.filter(
                content_hash=content_hash_soumis
            ).first()
            if page_existante_par_hash:
                logger.info(
                    "PageViewSet.create: doublon par content_hash — page existante %d "
                    "hash=%s url_existante=%s url_soumise=%s (user=%s)",
                    page_existante_par_hash.pk,
                    content_hash_soumis[:16],
                    page_existante_par_hash.url,
                    url_normalisee,
                    request.user.username,
                )
                return Response(
                    {
                        "detail": "Contenu identique deja enregistre.",
                        "existing_page_id": page_existante_par_hash.pk,
                    },
                    status=status.HTTP_409_CONFLICT,
                )

        # Extraire le dossier_id optionnel des donnees soumises
        # / Extract optional dossier_id from submitted data
        dossier_id_soumis = donnees_soumises.get("dossier_id")

        # Creer la page avec l'owner et le dossier
        # / Create page with owner and folder
        page_creee = serializer.save(
            owner=request.user,
            dossier=_resoudre_dossier(request.user, dossier_id_soumis),
        )
        logger.info(
            "PageViewSet.create: Page %d creee — url=%s owner=%s dossier=%s",
            page_creee.pk,
            page_creee.url,
            request.user.username,
            page_creee.dossier,
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

        # Dossiers possedes par l'utilisateur
        # / Folders owned by user
        dossiers_owner = Dossier.objects.filter(owner=request.user)

        # Dossiers partages avec l'utilisateur
        # / Folders shared with user
        ids_dossiers_partages = DossierPartage.objects.filter(
            utilisateur=request.user
        ).values_list("dossier_id", flat=True)
        dossiers_partages = Dossier.objects.filter(pk__in=ids_dossiers_partages)

        # Combiner et serialiser en liste de dicts {id, name}
        # / Combine and serialize as list of {id, name} dicts
        tous_les_dossiers = (dossiers_owner | dossiers_partages).distinct().order_by("name")
        liste_dossiers = []
        for dossier_courant in tous_les_dossiers:
            liste_dossiers.append({
                "id": dossier_courant.pk,
                "name": dossier_courant.name,
            })
        return Response(liste_dossiers)

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

        # Verifier que le dossier est accessible par l'utilisateur
        # / Check that folder is accessible by user
        ids_accessibles = _ids_dossiers_accessibles(request.user)
        if dossier_id_cible not in ids_accessibles:
            return Response(
                {"detail": "Dossier inaccessible."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            dossier_cible = Dossier.objects.get(pk=dossier_id_cible)
        except Dossier.DoesNotExist:
            return Response(
                {"detail": "Dossier introuvable."},
                status=status.HTTP_404_NOT_FOUND,
            )

        page_a_classer.dossier = dossier_cible
        page_a_classer.save(update_fields=["dossier"])
        logger.info(
            "PageViewSet.classer_depuis_extension: Page %d deplacee dans dossier '%s' (user=%s)",
            page_a_classer.pk,
            dossier_cible.name,
            request.user.username,
        )

        return Response({"detail": "Page classee.", "dossier_name": dossier_cible.name})


def _resoudre_dossier(utilisateur, dossier_id_soumis):
    """
    Resout le dossier pour une page creee par l'extension :
    - Si dossier_id fourni et valide → l'utiliser
    - Sinon → auto-creer ou reutiliser un dossier "A ranger" pour l'owner
    / Resolves folder for a page created by extension:
    / - If dossier_id provided and valid → use it
    / - Otherwise → auto-create or reuse an "A ranger" folder for owner

    LOCALISATION : core/views.py

    Appelee par PageViewSet.create() pour determiner dans quel dossier placer la page.
    / Called by PageViewSet.create() to determine which folder to place the page in.
    """
    if dossier_id_soumis:
        try:
            dossier_choisi = Dossier.objects.get(pk=dossier_id_soumis)
            # Verifier que l'utilisateur a acces a ce dossier
            # / Check user has access to this folder
            ids_accessibles = _ids_dossiers_accessibles(utilisateur)
            if dossier_choisi.pk in ids_accessibles:
                return dossier_choisi
        except Dossier.DoesNotExist:
            pass

    # Fallback : dossier "A ranger" de l'utilisateur
    # / Fallback: user's "A ranger" folder
    dossier_a_ranger, _cree = Dossier.objects.get_or_create(
        name="A ranger",
        owner=utilisateur,
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
        Recherche une page par URL (avec normalisation) et renvoie le HTML sidebar.
        / Look up a page by URL (with normalization) and return sidebar HTML.
        """
        url_recue = request.query_params.get("url", "")

        # Recherche de la page par URL normalisee
        # / Look up page by normalized URL
        page_trouvee = None
        if url_recue:
            url_normalisee = normaliser_url(url_recue)
            page_trouvee = Page.objects.filter(url=url_normalisee).first()

            # Fallback : recherche par URL exacte si la normalisee n'a rien donne
            # / Fallback: search by exact URL if normalized didn't match
            if not page_trouvee:
                page_trouvee = Page.objects.filter(url=url_recue).first()

            # Dernier fallback : avec/sans trailing slash
            # / Last fallback: with/without trailing slash
            if not page_trouvee and url_recue.endswith("/"):
                page_trouvee = Page.objects.filter(url=url_recue[:-1]).first()
            elif not page_trouvee:
                page_trouvee = Page.objects.filter(url=url_recue + "/").first()

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
