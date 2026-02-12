import json
import logging

from django.db.models import Count
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.template.loader import render_to_string
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.models import AIModel, Configuration, Dossier, Page
from hypostasis_extractor.models import AnalyseurSyntaxique, CommentaireExtraction, ExtractedEntity, ExtractionJob
from hypostasis_extractor.services import run_analyseur_on_page
from .serializers import (
    CommentaireExtractionSerializer, DossierCreateSerializer, ExtractionManuelleSerializer,
    ExtractionSerializer, PageClasserSerializer, RunAnalyseSerializer, SelectModelSerializer,
)
from .utils import annoter_html_avec_ancres

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


def _annoter_entites_avec_commentaires(queryset_entites):
    """
    Annote un queryset d'entites avec le nombre de commentaires.
    Retourne (queryset_annote, set_ids_commentees).
    / Annotate entity queryset with comment count.
    Returns (annotated_queryset, set_of_commented_ids).
    """
    entites_annotees = queryset_entites.annotate(
        nombre_commentaires=Count("commentaires"),
    )
    ids_commentees = set(
        entites_annotees.filter(nombre_commentaires__gt=0).values_list("pk", flat=True)
    )
    return entites_annotees, ids_commentees


def _get_ia_active():
    """
    Helper — retourne True si l'IA est activee dans la configuration singleton.
    Helper — returns True if AI is enabled in singleton configuration.
    """
    return Configuration.get_solo().ai_active


class ConfigurationIAViewSet(viewsets.ViewSet):
    """
    ViewSet pour la configuration IA (toggle on/off, selection du modele).
    ViewSet for AI configuration (toggle on/off, model selection).
    """

    @action(detail=False, methods=["GET"])
    def status(self, request):
        """
        Retourne le partial HTML du bouton IA (pour HTMX).
        Returns the AI button HTML partial (for HTMX).
        """
        configuration = Configuration.get_solo()
        modeles_actifs = AIModel.objects.filter(is_active=True)
        return render(request, "front/includes/config_ia_toggle.html", {
            "configuration": configuration,
            "modeles_actifs": modeles_actifs,
        })

    @action(detail=False, methods=["POST"])
    def toggle(self, request):
        """
        Active ou desactive l'IA. Si plusieurs modeles actifs et activation → renvoie un select.
        Toggle AI on/off. If multiple active models and enabling → return a select.
        """
        configuration = Configuration.get_solo()
        modeles_actifs = AIModel.objects.filter(is_active=True)

        if configuration.ai_active:
            # Desactivation / Deactivate
            configuration.ai_active = False
            configuration.ai_model = None
            configuration.save()
        else:
            # Activation / Activate
            if modeles_actifs.count() == 1:
                # Un seul modele actif → activation directe
                # Single active model → direct activation
                configuration.ai_active = True
                configuration.ai_model = modeles_actifs.first()
                configuration.save()
            elif modeles_actifs.count() > 1:
                # Plusieurs modeles → on ne fait rien, le partial affiche le select
                # Multiple models → do nothing, partial shows the select
                pass
            else:
                # Aucun modele actif → on ne peut pas activer
                # No active model → cannot activate
                pass

        # Re-fetch apres modification / Re-fetch after modification
        configuration = Configuration.get_solo()
        return render(request, "front/includes/config_ia_toggle.html", {
            "configuration": configuration,
            "modeles_actifs": modeles_actifs,
        })

    @action(detail=False, methods=["POST"], url_path="select-model")
    def select_model(self, request):
        """
        Selectionne un modele IA et active l'IA.
        Select an AI model and enable AI.
        """
        serializer = SelectModelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        modele_choisi = get_object_or_404(
            AIModel, pk=serializer.validated_data["model_id"], is_active=True
        )
        configuration = Configuration.get_solo()
        configuration.ai_active = True
        configuration.ai_model = modele_choisi
        configuration.save()

        modeles_actifs = AIModel.objects.filter(is_active=True)
        return render(request, "front/includes/config_ia_toggle.html", {
            "configuration": configuration,
            "modeles_actifs": modeles_actifs,
        })


class BibliothequeViewSet(viewsets.ViewSet):
    """
    Page racine — shell 3 colonnes.
    Root page — 3-column shell.
    """

    def list(self, request):
        # La page principale est un template complet, pas un partial
        # Main page is a full template, not a partial
        return render(request, "front/bibliotheque.html", {
            "ia_active": _get_ia_active(),
        })


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
        # / If a job exists, retrieve its entities for display
        entites_existantes = None
        html_annote = None
        ids_entites_commentees = set()
        if dernier_job_termine:
            entites_existantes, ids_entites_commentees = _annoter_entites_avec_commentaires(
                dernier_job_termine.entities.all()
            )
            # Annoter le HTML avec des ancres pour le scroll-to-extraction
            # / Annotate HTML with anchors for scroll-to-extraction
            html_annote = annoter_html_avec_ancres(
                page.html_readability, page.text_readability,
                entites_existantes, ids_entites_commentees,
            )

        # Contexte commun pour les deux partials
        ia_active = _get_ia_active()
        contexte_partage = {
            "page": page,
            "html_annote": html_annote,
            "analyseurs_actifs": analyseurs_actifs,
            "job": dernier_job_termine,
            "entities": entites_existantes,
            "ia_active": ia_active,
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
        # On passe aussi le job, les entites et le HTML annote
        return render(request, "front/base.html", {
            "page_preloaded": page,
            "html_annote": html_annote,
            "analyseurs_actifs": analyseurs_actifs,
            "job": dernier_job_termine,
            "entities": entites_existantes,
            "ia_active": ia_active,
        })

    @action(detail=True, methods=["POST"])
    def analyser(self, request, pk=None):
        """
        Lance une extraction LangExtract sur une page via un analyseur syntaxique.

        Donnees recues : form-data HTMX avec analyseur_id (via hx-include du select).
        Retourne le partial HTML des cartes d'extraction.
        Envoie HX-Trigger: ouvrirPanneauDroit pour ouvrir le panneau droit cote client.
        """
        # Guard : verifie que l'IA est activee / Check AI is enabled
        if not _get_ia_active():
            return HttpResponse("IA desactivee. Activez l'IA depuis le panneau de gauche.", status=403)

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
        # / Render partial with extraction cards
        toutes_les_entites_du_job, ids_entites_commentees = _annoter_entites_avec_commentaires(
            job_extraction.entities.all()
        )

        # Annoter le HTML avec des ancres pour le scroll-to-extraction
        # / Annotate HTML with anchors for scroll-to-extraction
        html_annote = annoter_html_avec_ancres(
            page.html_readability, page.text_readability,
            toutes_les_entites_du_job, ids_entites_commentees,
        )

        html_cartes = render_to_string(
            "front/includes/extraction_results.html",
            {"job": job_extraction, "entities": toutes_les_entites_du_job},
            request=request,
        )

        # OOB swap pour mettre a jour #readability-content avec le HTML annote
        # Le contenu de lecture est mis a jour en meme temps que les cartes d'extraction
        # / OOB swap to update #readability-content with annotated HTML
        html_readability_oob = (
            '<article id="readability-content" hx-swap-oob="innerHTML:#readability-content">'
            + (html_annote or page.html_readability)
            + '</article>'
        )

        html_complet = html_cartes + html_readability_oob
        reponse = HttpResponse(html_complet)

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
        reponse = _render_arbre(request)
        reponse["HX-Trigger"] = json.dumps({"showToast": {"message": "Dossier cr\u00e9\u00e9"}})
        return reponse

    def destroy(self, request, pk=None):
        # Suppression explicite du dossier puis retour de l'arbre
        # Explicit folder deletion then return updated tree
        dossier = get_object_or_404(Dossier, pk=pk)
        dossier.delete()
        reponse = _render_arbre(request)
        reponse["HX-Trigger"] = json.dumps({"showToast": {"message": "Dossier supprim\u00e9"}})
        return reponse


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

    def _get_or_create_job_manuel(self, page):
        """
        Retourne (ou cree) le job d'extraction manuelle pour une page.
        Returns (or creates) the manual extraction job for a page.
        """
        job_manuel, _created = ExtractionJob.objects.get_or_create(
            page=page,
            name="Extractions manuelles",
            defaults={"status": "completed", "ai_model": None},
        )
        return job_manuel

    def _render_panneau_complet_avec_oob(self, request, page):
        """
        Re-rend le panneau d'analyse + OOB swap du readability-content annote.
        Re-renders analysis panel + OOB swap of annotated readability-content.
        """
        analyseurs_actifs = AnalyseurSyntaxique.objects.filter(is_active=True)

        # Toutes les entites de tous les jobs completed de la page
        # / All entities from all completed jobs for the page
        tous_les_jobs_termines = ExtractionJob.objects.filter(
            page=page, status="completed",
        )
        toutes_les_entites, ids_entites_commentees = _annoter_entites_avec_commentaires(
            ExtractedEntity.objects.filter(
                job__in=tous_les_jobs_termines,
            ).order_by("start_char")
        )

        # Annoter le HTML / Annotate HTML
        html_annote = annoter_html_avec_ancres(
            page.html_readability, page.text_readability,
            toutes_les_entites, ids_entites_commentees,
        )

        # Dernier job pour le contexte du panneau / Latest job for panel context
        dernier_job = tous_les_jobs_termines.order_by("-created_at").first()

        html_panneau = render_to_string(
            "front/includes/panneau_analyse.html",
            {
                "page": page,
                "analyseurs_actifs": analyseurs_actifs,
                "job": dernier_job,
                "entities": toutes_les_entites,
                "ia_active": _get_ia_active(),
            },
            request=request,
        )

        # OOB swap pour le contenu de lecture annote
        # / OOB swap for annotated reading content
        html_readability_oob = (
            '<article id="readability-content" hx-swap-oob="innerHTML:#readability-content">'
            + (html_annote or page.html_readability)
            + '</article>'
        )

        return html_panneau + html_readability_oob

    @action(detail=False, methods=["POST"])
    def panneau(self, request):
        """
        Re-rend le panneau d'analyse complet pour une page (utilise par Annuler).
        Re-renders the full analysis panel for a page (used by Cancel).
        """
        page_id = request.data.get("page_id")
        if not page_id:
            return HttpResponse("page_id requis.", status=400)
        page = get_object_or_404(Page, pk=page_id)
        html_complet = self._render_panneau_complet_avec_oob(request, page)
        return HttpResponse(html_complet)

    @action(detail=False, methods=["POST"])
    def manuelle(self, request):
        """
        Recoit le texte selectionne, calcule les positions, et renvoie le formulaire.
        Receives selected text, computes positions, returns the form partial.
        """
        logger.info(
            "manuelle: content_type=%s data=%s",
            request.content_type, dict(request.data),
        )
        serializer = ExtractionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_text = serializer.validated_data["text"]
        validated_page_id = serializer.validated_data.get("page_id")

        if not validated_page_id:
            return HttpResponse("Aucune page selectionnee.", status=400)

        page = get_object_or_404(Page, pk=validated_page_id)

        # Calculer start_char dans text_readability cote serveur
        # / Compute start_char in text_readability server-side
        start_char = page.text_readability.find(validated_text)
        if start_char == -1:
            # Fallback : recherche soft (nbsp → espace)
            start_char = page.text_readability.replace('\xa0', ' ').find(
                validated_text.replace('\xa0', ' ')
            )
        end_char = start_char + len(validated_text) if start_char != -1 else 0
        if start_char == -1:
            start_char = 0

        # Liste des 4 attributs vides pour le formulaire de creation
        # / 4 empty attributes for the creation form
        liste_attributs_creation = [
            ("tags", ""),
            ("titre", ""),
            ("badge", ""),
            ("hashtags", ""),
        ]

        html_formulaire = render_to_string(
            "front/includes/extraction_manuelle_form.html",
            {
                "text": validated_text,
                "page_id": page.pk,
                "start_char": start_char,
                "end_char": end_char,
                "liste_attributs": liste_attributs_creation,
            },
            request=request,
        )

        reponse = HttpResponse(html_formulaire)
        reponse["HX-Trigger"] = "ouvrirPanneauDroit"
        return reponse

    @action(detail=False, methods=["POST"], url_path="creer_manuelle")
    def creer_manuelle(self, request):
        """
        Cree une ExtractedEntity manuelle et re-rend le panneau complet.
        Creates a manual ExtractedEntity and re-renders the full panel.
        """
        logger.info(
            "creer_manuelle: content_type=%s data=%s",
            request.content_type, {k: str(v)[:80] for k, v in request.data.items()},
        )
        serializer = ExtractionManuelleSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning("creer_manuelle: validation echouee — %s", serializer.errors)
            return HttpResponse(
                f'<p class="text-sm text-red-500">Erreur: {serializer.errors}</p>',
                status=400,
            )

        donnees = serializer.validated_data
        page = get_object_or_404(Page, pk=donnees["page_id"])
        job_manuel = self._get_or_create_job_manuel(page)

        # Lire les paires cle/valeur dynamiques depuis le formulaire
        # (meme pattern que modifier)
        # / Read dynamic key/value pairs from form data (same pattern as modifier)
        attributs_entite = {}
        for index_attribut in range(10):
            cle = request.data.get(f"attr_key_{index_attribut}", "").strip()
            valeur = request.data.get(f"attr_val_{index_attribut}", "").strip()
            if cle and valeur:
                attributs_entite[cle] = valeur

        ExtractedEntity.objects.create(
            job=job_manuel,
            extraction_class="",
            extraction_text=donnees["text"],
            start_char=donnees["start_char"],
            end_char=donnees["end_char"],
            attributes=attributs_entite,
        )

        html_complet = self._render_panneau_complet_avec_oob(request, page)
        reponse = HttpResponse(html_complet)
        reponse["HX-Trigger"] = json.dumps({
            "ouvrirPanneauDroit": True,
            "showToast": {"message": "Extraction cr\u00e9\u00e9e"},
        })
        return reponse

    @action(detail=False, methods=["POST"])
    def editer(self, request):
        """
        Affiche le formulaire d'edition inline pour une extraction existante.
        Displays the inline edit form for an existing extraction.
        """
        entity_id = request.data.get("entity_id")
        page_id = request.data.get("page_id")
        logger.info("editer: entity_id=%s page_id=%s", entity_id, page_id)

        entite = get_object_or_404(ExtractedEntity, pk=entity_id)
        attributs = entite.attributes or {}

        # Construire la liste des paires (cle, valeur) pour le template
        # On garde l'ordre d'insertion du dict (Python 3.7+)
        # En mode edition, on affiche les cles reelles de l'entite
        # / Build list of (key, value) pairs for the template
        # / In edit mode, display the entity's actual keys
        liste_attributs = list(attributs.items())

        # Pad a 4 elements pour avoir toujours 4 champs
        # / Pad to 4 elements to always have 4 fields
        noms_par_defaut = ["tags", "titre", "badge", "hashtags"]
        while len(liste_attributs) < 4:
            index_suivant = len(liste_attributs)
            nom_defaut = noms_par_defaut[index_suivant] if index_suivant < len(noms_par_defaut) else f"attr_{index_suivant}"
            liste_attributs.append((nom_defaut, ""))

        html_formulaire = render_to_string(
            "front/includes/extraction_manuelle_form.html",
            {
                "entity": entite,
                "page_id": page_id,
                "liste_attributs": liste_attributs,
            },
            request=request,
        )
        return HttpResponse(html_formulaire)

    @action(detail=False, methods=["POST"])
    def modifier(self, request):
        """
        Modifie une ExtractedEntity existante et re-rend le panneau complet.
        Lit les paires (attr_key_N, attr_val_N) depuis le POST pour supporter
        des cles dynamiques (ex: "Hypostases", "Resume" au lieu de "tags", "titre").
        / Modifies an existing ExtractedEntity and re-renders the full panel.
        / Reads (attr_key_N, attr_val_N) pairs from POST to support dynamic keys.
        """
        logger.info(
            "modifier: content_type=%s data=%s",
            request.content_type, {k: str(v)[:80] for k, v in request.data.items()},
        )

        entity_id = request.data.get("entity_id")
        page_id = request.data.get("page_id")
        if not entity_id or not page_id:
            return HttpResponse("entity_id et page_id requis.", status=400)

        entite = get_object_or_404(ExtractedEntity, pk=entity_id)
        page = get_object_or_404(Page, pk=page_id)

        # Lire les paires cle/valeur dynamiques depuis le formulaire
        # Le template envoie attr_key_0, attr_val_0, attr_key_1, attr_val_1, etc.
        # / Read dynamic key/value pairs from form data
        nouveaux_attributs = {}
        for index_attribut in range(10):
            cle = request.data.get(f"attr_key_{index_attribut}", "").strip()
            valeur = request.data.get(f"attr_val_{index_attribut}", "").strip()
            if cle and valeur:
                nouveaux_attributs[cle] = valeur

        entite.attributes = nouveaux_attributs
        entite.save()

        logger.info("modifier: entite pk=%s modifiee attrs=%s", entite.pk, list(nouveaux_attributs.keys()))

        html_complet = self._render_panneau_complet_avec_oob(request, page)
        reponse = HttpResponse(html_complet)
        reponse["HX-Trigger"] = json.dumps({
            "ouvrirPanneauDroit": True,
            "showToast": {"message": "Extraction modifi\u00e9e"},
        })
        return reponse

    @action(detail=False, methods=["GET"], url_path="fil_discussion")
    def fil_discussion(self, request):
        """
        Affiche le fil de discussion (commentaires) pour une extraction.
        Displays the discussion thread (comments) for an extraction.
        """
        entity_id = request.query_params.get("entity_id")
        if not entity_id:
            return HttpResponse("entity_id requis.", status=400)

        entite = get_object_or_404(ExtractedEntity, pk=entity_id)
        tous_les_commentaires = CommentaireExtraction.objects.filter(entity=entite)

        html_fil = render_to_string(
            "front/includes/fil_discussion.html",
            {
                "entity": entite,
                "commentaires": tous_les_commentaires,
            },
            request=request,
        )

        reponse = HttpResponse(html_fil)
        # Declenche l'elargissement du panneau via event HTMX
        # / Trigger panel widening via HTMX event
        reponse["HX-Trigger"] = json.dumps({
            "ouvrirPanneauDroit": True,
            "activerModeDebat": True,
        })
        return reponse

    @action(detail=False, methods=["POST"], url_path="ajouter_commentaire")
    def ajouter_commentaire(self, request):
        """
        Cree un commentaire sur une extraction et re-rend le fil de discussion.
        Creates a comment on an extraction and re-renders the discussion thread.
        """
        serializer = CommentaireExtractionSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning("ajouter_commentaire: validation echouee — %s", serializer.errors)
            return HttpResponse(
                f'<p class="text-sm text-red-500">Erreur: {serializer.errors}</p>',
                status=400,
            )

        donnees = serializer.validated_data
        entite = get_object_or_404(ExtractedEntity, pk=donnees["entity_id"])

        # Creer le commentaire / Create the comment
        CommentaireExtraction.objects.create(
            entity=entite,
            prenom=donnees["prenom"],
            commentaire=donnees["commentaire"],
        )

        # Re-rendre le fil complet / Re-render full thread
        tous_les_commentaires = CommentaireExtraction.objects.filter(entity=entite)
        html_fil = render_to_string(
            "front/includes/fil_discussion.html",
            {
                "entity": entite,
                "commentaires": tous_les_commentaires,
            },
            request=request,
        )

        reponse = HttpResponse(html_fil)
        reponse["HX-Trigger"] = json.dumps({
            "ouvrirPanneauDroit": True,
            "activerModeDebat": True,
            "showToast": {"message": "Commentaire ajout\u00e9"},
        })
        return reponse

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
