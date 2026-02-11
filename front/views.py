import json
import logging

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.template.loader import render_to_string
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.models import AIModel, Dossier, Page
from hypostasis_extractor.models import AnalyseurSyntaxique, ExtractionJob
from hypostasis_extractor.services import run_analyseur_on_page
from .serializers import DossierCreateSerializer, ExtractionSerializer, PageClasserSerializer, RunAnalyseSerializer

logger = logging.getLogger(__name__)


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
    Partial HTMX — zone de lecture d'une page + action analyse.
    HTMX partial — reading zone for a page + analyze action.
    """
    permission_classes = [permissions.AllowAny]

    def retrieve(self, request, pk=None):
        """
        Lecture d'une page.
        - Requete HTMX → partial lecture_principale + panneau analyse en OOB
        - Acces direct (F5) → page complete base.html avec lecture pre-chargee

        Quand c'est une requete HTMX, on renvoie deux morceaux de HTML :
        1. Le contenu de lecture (qui remplace #zone-lecture)
        2. Le panneau d'analyse en OOB swap (qui remplace #panneau-extractions)
        Ca permet de mettre a jour le panneau droit sans JS.
        """
        page = get_object_or_404(Page, pk=pk)
        analyseurs_actifs = AnalyseurSyntaxique.objects.filter(is_active=True)

        # Recupere le dernier job d'extraction termine pour cette page
        # pour afficher les resultats existants dans le panneau droit
        dernier_job_termine = ExtractionJob.objects.filter(
            page=page,
            status="completed",
        ).order_by("-created_at").first()

        # Si un job existe, on recupere ses entites pour les afficher
        entites_existantes = None
        if dernier_job_termine:
            entites_existantes = dernier_job_termine.entities.all()

        # Contexte commun pour les deux partials
        contexte_partage = {
            "page": page,
            "analyseurs_actifs": analyseurs_actifs,
            "job": dernier_job_termine,
            "entities": entites_existantes,
        }

        if request.headers.get('HX-Request'):
            # 1. Partial principal : contenu de lecture
            html_lecture = render_to_string(
                "front/includes/lecture_principale.html",
                contexte_partage,
                request=request,
            )

            # 2. Partial OOB : panneau d'analyse injecte dans le sidebar droit
            # Le hx-swap-oob="innerHTML:#panneau-extractions" dit a HTMX :
            # "remplace le contenu de #panneau-extractions avec ce HTML"
            html_panneau_analyse = render_to_string(
                "front/includes/panneau_analyse.html",
                contexte_partage,
                request=request,
            )
            html_panneau_oob = (
                '<div id="panneau-extractions" hx-swap-oob="innerHTML:#panneau-extractions">'
                + html_panneau_analyse
                + '</div>'
            )

            # On concatene les deux morceaux : HTMX traite l'OOB automatiquement
            html_complet = html_lecture + html_panneau_oob
            return HttpResponse(html_complet)

        # Acces direct (F5) → page complete avec le panneau pre-charge
        # On passe aussi le job et les entites pour que le panneau affiche les resultats existants
        return render(request, "front/base.html", {
            "page_preloaded": page,
            "analyseurs_actifs": analyseurs_actifs,
            "job": dernier_job_termine,
            "entities": entites_existantes,
        })

    @action(detail=True, methods=["POST"])
    def analyser(self, request, pk=None):
        """
        Lance une extraction LangExtract sur une page via un analyseur syntaxique.

        Donnees recues : form-data HTMX avec analyseur_id (via hx-include du select).
        Retourne le partial HTML des cartes d'extraction.
        Envoie HX-Trigger: ouvrirPanneauDroit pour ouvrir le panneau droit cote client.
        """
        # Validation via serializer DRF sur request.data (form-data envoye par HTMX)
        serializer = RunAnalyseSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning("analyser: validation echouee — %s", serializer.errors)
            return render(request, "front/includes/extraction_results.html", {
                "error_message": str(serializer.errors),
            })

        page = get_object_or_404(Page, pk=pk)
        analyseur = get_object_or_404(
            AnalyseurSyntaxique, pk=serializer.validated_data["analyseur_id"]
        )

        # On prend le premier modele IA actif
        ai_model_actif = AIModel.objects.filter(is_active=True).first()
        if not ai_model_actif:
            return render(request, "front/includes/extraction_results.html", {
                "error_message": "Aucun modele IA actif configure. Activez un modele dans l'admin.",
            })

        # Lancement de l'extraction LangExtract
        try:
            job_extraction = run_analyseur_on_page(analyseur, page, ai_model_actif)
        except Exception as exception_extraction:
            logger.error(
                "analyser: erreur extraction page=%s analyseur=%s — %s",
                pk, analyseur.name, exception_extraction, exc_info=True,
            )
            return render(request, "front/includes/extraction_results.html", {
                "error_message": str(exception_extraction),
            })

        # Rendu du partial avec les cartes d'extraction
        toutes_les_entites_du_job = job_extraction.entities.all()
        reponse = render(request, "front/includes/extraction_results.html", {
            "job": job_extraction,
            "entities": toutes_les_entites_du_job,
        })

        # Declenche l'ouverture du panneau droit cote client via event HTMX
        reponse["HX-Trigger"] = "ouvrirPanneauDroit"

        return reponse


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

        # request.data gere automatiquement JSON et form-data via DRF
        serializer = PageClasserSerializer(data=request.data)
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
