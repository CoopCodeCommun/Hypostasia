import logging
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response

from .models import Page
from .serializers import PageCreateSerializer, PageListSerializer

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


@method_decorator(csrf_exempt, name="dispatch")
class PageViewSet(viewsets.ViewSet):
    """
    API pour la gestion des Pages — utilisee exclusivement par l'extension navigateur.
    Pas de templates, pas de rendu HTML : uniquement du JSON.
    / API for Page management — used exclusively by the browser extension.
    / No templates, no HTML rendering: JSON only.
    """
    authentication_classes = []
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
        Avant creation, verifie la deduplication :
        1. Par URL normalisee (meme page avec params UTM differents)
        2. Par content_hash (meme contenu sous URL differente)
        Si un doublon est detecte par content_hash, renvoie 409 Conflict.
        / Creates a new Page from data sent by the extension.
        / Before creation, checks for deduplication:
        / 1. By normalized URL (same page with different UTM params)
        / 2. By content_hash (same content under different URL)
        / If a duplicate is detected by content_hash, returns 409 Conflict.
        """
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

        # Verifier le doublon par URL normalisee
        # / Check for duplicate by normalized URL
        url_normalisee = donnees_soumises.get("url", "")
        if url_normalisee:
            page_existante_par_url = Page.objects.filter(url=url_normalisee).first()
            if page_existante_par_url:
                logger.info(
                    "PageViewSet.create: doublon par URL — page existante %d pour url=%s",
                    page_existante_par_url.pk,
                    url_normalisee,
                )
                return Response(
                    {
                        "detail": "Page deja enregistree avec cette URL.",
                        "existing_page_id": page_existante_par_url.pk,
                    },
                    status=status.HTTP_409_CONFLICT,
                )

        # Verifier le doublon par content_hash (meme contenu, URL differente)
        # / Check for duplicate by content_hash (same content, different URL)
        content_hash_soumis = donnees_soumises.get("content_hash", "")
        if content_hash_soumis:
            page_existante_par_hash = Page.objects.filter(
                content_hash=content_hash_soumis
            ).first()
            if page_existante_par_hash:
                logger.info(
                    "PageViewSet.create: doublon par content_hash — page existante %d "
                    "hash=%s url_existante=%s url_soumise=%s",
                    page_existante_par_hash.pk,
                    content_hash_soumis[:16],
                    page_existante_par_hash.url,
                    url_normalisee,
                )
                return Response(
                    {
                        "detail": "Contenu identique deja enregistre.",
                        "existing_page_id": page_existante_par_hash.pk,
                    },
                    status=status.HTTP_409_CONFLICT,
                )

        page_creee = serializer.save()
        logger.info(
            "PageViewSet.create: Page %d creee — url=%s",
            page_creee.pk,
            page_creee.url,
        )

        return Response(serializer.data, status=status.HTTP_201_CREATED)


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
    authentication_classes = []
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
