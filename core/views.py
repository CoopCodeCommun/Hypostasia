import logging

from django.http import HttpResponse
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response

from .models import Page
from .serializers import PageCreateSerializer, PageListSerializer

logger = logging.getLogger("core")


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
        / Lists pages, with optional URL filter.
        / The extension uses ?url=... to check if a page already exists.
        """
        toutes_les_pages = Page.objects.all().order_by("-created_at")

        # Filtre par URL si le parametre est present (utilise par l'extension)
        # / Filter by URL if parameter is present (used by extension)
        url_filtre = request.query_params.get("url")
        if url_filtre:
            toutes_les_pages = toutes_les_pages.filter(url=url_filtre)

        serializer = PageListSerializer(toutes_les_pages, many=True)
        return Response(serializer.data)

    def create(self, request):
        """
        Cree une nouvelle Page a partir des donnees envoyees par l'extension.
        Le serializer derive text_readability depuis html_readability
        et calcule le content_hash automatiquement.
        / Creates a new Page from data sent by the extension.
        / The serializer derives text_readability from html_readability
        / and computes content_hash automatically.
        """
        serializer = PageCreateSerializer(data=request.data)

        if not serializer.is_valid():
            logger.warning(
                "PageViewSet.create: erreurs de validation — %s",
                serializer.errors,
            )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        page_creee = serializer.save()
        logger.info(
            "PageViewSet.create: Page %d creee — url=%s",
            page_creee.pk,
            page_creee.url,
        )

        return Response(serializer.data, status=status.HTTP_201_CREATED)


@csrf_exempt
def test_sidebar_view(request):
    """
    Vue de test pour l'extension Sidebar-First.
    Recoit ?url=... et renvoie le HTML de la sidebar
    (soit les arguments de la page, soit un message "aucune analyse").
    / Test view for the Sidebar-First extension.
    / Receives ?url=... and returns sidebar HTML
    / (either page arguments or a "no analysis" message).
    """
    url_recue = request.GET.get("url")

    # Recherche de la page par URL exacte (avec fallback sans trailing slash)
    # / Look up page by exact URL (with trailing slash fallback)
    page_trouvee = None
    if url_recue:
        page_trouvee = Page.objects.filter(url=url_recue).first()
        if not page_trouvee and url_recue.endswith("/"):
            page_trouvee = Page.objects.filter(url=url_recue[:-1]).first()

    if page_trouvee:
        return render(
            request,
            "core/includes/sidebar_items.html",
            {"page": page_trouvee},
        )

    # Aucune page trouvee → message informatif
    # / No page found → informational message
    return HttpResponse(
        f"""
        <div style="padding: 20px; text-align: center;">
            <p>Aucune analyse trouvee pour cette URL.</p>
            <div style="margin-top:20px; color:#999; font-size:12px;">
                URL: {url_recue or "Inconnue"}
            </div>
        </div>
        """
    )