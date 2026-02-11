import json

from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.models import Dossier, Page
from .serializers import DossierCreateSerializer, ExtractionSerializer, PageClasserSerializer


def _render_arbre(request):
    """
    Helper interne — renvoie le partial HTML de l'arbre de dossiers.
    Internal helper — returns the folder tree HTML partial.
    """
    all_dossiers = Dossier.objects.prefetch_related("pages").all()
    pages_orphelines = Page.objects.filter(dossier__isnull=True).order_by("-created_at")
    return render(request, "front/includes/arbre_dossiers.html", {
        "dossiers": all_dossiers,
        "pages_orphelines": pages_orphelines,
    })


class BibliothequeViewSet(viewsets.ViewSet):
    """
    Page racine — shell 3 colonnes.
    Root page — 3-column shell.
    """

    def list(self, request):
        # La page principale est un template complet, pas un partial
        # Main page is a full template, not a partial
        return render(request, "front/bibliotheque.html")


class ArbreViewSet(viewsets.ViewSet):
    """
    Partial HTMX — arbre de dossiers + pages orphelines.
    HTMX partial — folder tree + orphan pages.
    """

    def list(self, request):
        return _render_arbre(request)


class LectureViewSet(viewsets.ViewSet):
    """
    Partial HTMX — zone de lecture d'une page.
    HTMX partial — reading zone for a page.
    """

    def retrieve(self, request, pk=None):
        """
        Lecture d'une page.
        - Requete HTMX → partial lecture_principale
        - Acces direct (F5) → page complete base.html avec lecture pre-chargee
        / Page reading.
        - HTMX request → lecture_principale partial
        - Direct access (F5) → full base.html with pre-loaded reading
        """
        page = get_object_or_404(Page, pk=pk)

        if request.headers.get('HX-Request'):
            return render(request, "front/includes/lecture_principale.html", {
                "page": page,
            })

        return render(request, "front/base.html", {
            "page_preloaded": page,
        })


class DossierViewSet(viewsets.ViewSet):
    """
    ViewSet explicite pour la gestion des dossiers.
    Explicit ViewSet for folder management.
    """

    def list(self, request):
        # Retourne la liste des dossiers en JSON (pour SweetAlert)
        # Returns folder list as JSON (for SweetAlert)
        all_dossiers = Dossier.objects.all().order_by("name")
        data = {str(d.pk): d.name for d in all_dossiers}
        return JsonResponse(data)

    def create(self, request):
        # Validation via serializer DRF
        # Validation via DRF serializer
        serializer = DossierCreateSerializer(data=request.POST)
        if serializer.is_valid():
            Dossier.objects.create(name=serializer.validated_data["name"])
        return _render_arbre(request)

    def destroy(self, request, pk=None):
        # Suppression explicite du dossier puis retour de l'arbre
        # Explicit folder deletion then return updated tree
        dossier = get_object_or_404(Dossier, pk=pk)
        dossier.delete()
        return _render_arbre(request)


class PageViewSet(viewsets.ViewSet):
    """
    ViewSet explicite pour les actions sur les pages.
    Explicit ViewSet for page actions.
    """

    @action(detail=True, methods=["POST"])
    def classer(self, request, pk=None):
        """
        Assigne une page a un dossier, retourne l'arbre mis a jour.
        Assign a page to a folder, return updated tree.
        """
        page = get_object_or_404(Page, pk=pk)

        # On accepte JSON ou form data
        # Accept JSON or form data
        if request.content_type == "application/json":
            body_data = json.loads(request.body)
        else:
            body_data = request.POST

        serializer = PageClasserSerializer(data=body_data)
        serializer.is_valid(raise_exception=True)

        dossier_id = serializer.validated_data["dossier_id"]
        if dossier_id:
            page.dossier = get_object_or_404(Dossier, pk=dossier_id)
        else:
            page.dossier = None
        page.save(update_fields=["dossier"])

        return _render_arbre(request)


class ExtractionViewSet(viewsets.ViewSet):
    """
    ViewSet pour les extractions de texte (manuelle et IA).
    ViewSet for text extractions (manual and AI).
    """

    @action(detail=False, methods=["POST"])
    def manuelle(self, request):
        """
        Recoit le texte selectionne pour extraction manuelle.
        Receives selected text for manual extraction.
        """
        serializer = ExtractionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_text = serializer.validated_data["text"]
        validated_page_id = serializer.validated_data.get("page_id")
        print(f"[EXTRACTION MANUELLE] page={validated_page_id} texte={validated_text}")

        return Response({"status": "ok"})

    @action(detail=False, methods=["POST"])
    def ia(self, request):
        """
        Recoit le texte selectionne pour extraction IA.
        Receives selected text for AI extraction.
        """
        serializer = ExtractionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_text = serializer.validated_data["text"]
        validated_page_id = serializer.validated_data.get("page_id")
        print(f"[EXTRACTION IA] page={validated_page_id} texte={validated_text}")

        return Response({"status": "ok"})
