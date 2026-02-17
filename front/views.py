import hashlib
import json
import logging
from datetime import timedelta

from django.db.models import Count, Prefetch
from django.utils import timezone
from django.utils.html import escape, strip_tags
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.template.loader import render_to_string
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.models import AIModel, Configuration, Dossier, Page, Question, ReponseQuestion
from hypostasis_extractor.models import (
    AnalyseurSyntaxique, AnalyseurExample, CommentaireExtraction,
    ExampleExtraction, ExtractionAttribute,
    ExtractedEntity, ExtractionJob, PromptPiece,
)
from .serializers import (
    CommentaireExtractionSerializer, DossierCreateSerializer, ExtractionManuelleSerializer,
    ExtractionSerializer, ImportFichierSerializer, PageClasserSerializer,
    PromouvoirEntrainementSerializer, QuestionSerializer,
    ReponseQuestionSerializer, RunAnalyseSerializer, RunReformulationSerializer,
    RunRestitutionSerializer, SelectModelSerializer, est_fichier_audio,
)
from .utils import annoter_html_avec_ancres

logger = logging.getLogger(__name__)


def _render_arbre(request):
    """
    Helper interne — renvoie le partial HTML de l'arbre de dossiers.
    Internal helper — returns the folder tree HTML partial.
    """
    # Exclure les restitutions de l'arbre (ne montrer que les pages racines)
    # / Exclude restitutions from tree (only show root pages)
    pages_racines_seulement = Prefetch(
        "pages",
        queryset=Page.objects.filter(parent_page__isnull=True),
    )
    all_dossiers = Dossier.objects.prefetch_related(pages_racines_seulement).all()
    pages_orphelines = Page.objects.filter(dossier__isnull=True, parent_page__isnull=True).order_by("-created_at")
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
        # Requete HTMX → retourne le contenu par defaut de zone-lecture
        # / HTMX request → return default zone-lecture content
        if request.headers.get('HX-Request'):
            return HttpResponse(
                '<div class="max-w-3xl mx-auto text-slate-500 text-sm">'
                'Sélectionnez une page pour commencer la lecture.'
                '</div>'
            )

        # Acces direct → page complete
        # / Direct access → full page
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
        analyseurs_actifs = AnalyseurSyntaxique.objects.filter(is_active=True, type_analyseur="analyser")

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

        # Recupere toutes les versions de cette page (racine + restitutions)
        # / Retrieve all versions of this page (root + restitutions)
        toutes_les_versions = page.toutes_les_versions
        page_racine = page.page_racine

        # Contexte commun pour les deux partials
        ia_active = _get_ia_active()
        contexte_partage = {
            "page": page,
            "html_annote": html_annote,
            "analyseurs_actifs": analyseurs_actifs,
            "job": dernier_job_termine,
            "entities": entites_existantes,
            "ia_active": ia_active,
            "versions": toutes_les_versions,
            "page_racine": page_racine,
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
            "versions": toutes_les_versions,
            "page_racine": page_racine,
        })

    @action(detail=True, methods=["GET"], url_path="previsualiser_analyse")
    def previsualiser_analyse(self, request, pk=None):
        """
        Construit le prompt complet (pieces + exemples + texte source) et retourne
        un partial de confirmation avec : estimation tokens, cout, bouton voir prompt.
        / Builds the full prompt (pieces + examples + source text) and returns
        a confirmation partial with: token estimate, cost, view prompt button.
        """
        page = get_object_or_404(Page, pk=pk)

        # Recupere l'analyseur depuis le query param
        # / Get analyzer from query param
        analyseur_id = request.query_params.get("analyseur_id")
        if not analyseur_id:
            return HttpResponse("analyseur_id requis.", status=400)

        analyseur = get_object_or_404(AnalyseurSyntaxique, pk=analyseur_id)

        # Recupere le modele IA actif depuis la configuration singleton
        # / Get active AI model from singleton configuration
        configuration_ia = Configuration.get_solo()
        modele_ia_actif = configuration_ia.ai_model
        if not modele_ia_actif:
            return HttpResponse("Aucun modèle IA sélectionné.", status=400)

        # Construit le prompt complet depuis les pieces de l'analyseur
        # / Build full prompt from analyzer pieces
        pieces_ordonnees = PromptPiece.objects.filter(
            analyseur=analyseur,
        ).order_by("order")
        texte_prompt_pieces = "\n".join(piece.content for piece in pieces_ordonnees)

        # Serialise les exemples few-shot en texte lisible
        # / Serialize few-shot examples as readable text
        tous_les_exemples = AnalyseurExample.objects.filter(
            analyseur=analyseur,
        ).order_by("order").prefetch_related("extractions__attributes")

        texte_exemples = ""
        for exemple in tous_les_exemples:
            texte_exemples += f"\n--- Exemple : {exemple.name} ---\n"
            texte_exemples += f"Texte source :\n{exemple.example_text[:500]}...\n" if len(exemple.example_text) > 500 else f"Texte source :\n{exemple.example_text}\n"
            for extraction in exemple.extractions.all():
                texte_exemples += f"\n  [{extraction.extraction_class}] {extraction.extraction_text}\n"
                for attribut in extraction.attributes.all():
                    texte_exemples += f"    {attribut.key}: {attribut.value}\n"

        # Texte source de la page (sera envoye au LLM)
        # / Source text from the page (will be sent to the LLM)
        texte_source_page = page.text_readability or ""

        # Assemblage du prompt complet tel qu'il sera envoye au LLM
        # / Assembly of the full prompt as it will be sent to the LLM
        prompt_complet = (
            f"{texte_prompt_pieces}\n\n"
            f"=== EXEMPLES FEW-SHOT ===\n{texte_exemples}\n\n"
            f"=== TEXTE A ANALYSER ===\n{texte_source_page}"
        )

        # Comptage des tokens via tiktoken (tokenizer cl100k_base, universel)
        # / Token counting via tiktoken (cl100k_base tokenizer, universal)
        import tiktoken
        encodeur_tokens = tiktoken.get_encoding("cl100k_base")
        nombre_tokens_input = len(encodeur_tokens.encode(prompt_complet))

        # Estimation du nombre de tokens output (20% de l'input)
        # / Estimate output token count (20% of input)
        nombre_tokens_output_estime = int(nombre_tokens_input * 0.20)

        # Estimation du cout en euros via la methode du modele
        # / Cost estimate in euros via the model method
        cout_estime_euros = modele_ia_actif.estimer_cout_euros(
            nombre_tokens_input, nombre_tokens_output_estime
        )

        return render(request, "front/includes/confirmation_analyse.html", {
            "page": page,
            "analyseur": analyseur,
            "modele_ia": modele_ia_actif,
            "nombre_tokens_input": nombre_tokens_input,
            "nombre_tokens_output_estime": nombre_tokens_output_estime,
            "cout_estime_euros": cout_estime_euros,
            "prompt_complet": prompt_complet,
            "nombre_exemples": tous_les_exemples.count(),
            "nombre_pieces": pieces_ordonnees.count(),
        })

    @action(detail=True, methods=["POST"])
    def analyser(self, request, pk=None):
        """
        Lance une extraction LangExtract asynchrone sur une page via Celery.
        - Si un job est deja en cours → renvoie le template de polling (pas de re-lancement)
        - Sinon → cree un ExtractionJob, lance la tache Celery, renvoie le polling
        / Launches an async LangExtract extraction on a page via Celery.
        - If a job is already running → returns polling template (no re-launch)
        - Otherwise → creates ExtractionJob, launches Celery task, returns polling
        """
        # Guard : verifie que l'IA est activee / Check AI is enabled
        if not _get_ia_active():
            return HttpResponse("IA desactivee. Activez l'IA depuis le panneau de gauche.", status=403)

        page = get_object_or_404(Page, pk=pk)

        # Guard anti-doublon : verifier s'il y a deja un job en cours pour cette page
        # / Anti-duplicate guard: check if a job is already running for this page
        job_en_cours = ExtractionJob.objects.filter(
            page=page,
            status__in=["pending", "processing"],
        ).order_by("-created_at").first()

        if job_en_cours:
            # Un job est deja en cours → renvoyer le template de polling sans re-lancer
            # / A job is already running → return polling template without re-launching
            logger.info("analyser: job deja en cours pk=%s pour page=%s", job_en_cours.pk, pk)
            reponse = render(request, "front/includes/analyse_en_cours.html", {
                "page": page,
            })
            reponse["HX-Trigger"] = "ouvrirPanneauDroit"
            return reponse

        # Validation via serializer DRF sur request.data (form-data envoye par HTMX)
        # / Validation via DRF serializer on request.data (form-data sent by HTMX)
        serializer = RunAnalyseSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning("analyser: validation echouee — %s", serializer.errors)
            return render(request, "front/includes/extraction_results.html", {
                "error_message": str(serializer.errors),
            })

        analyseur = get_object_or_404(
            AnalyseurSyntaxique, pk=serializer.validated_data["analyseur_id"]
        )

        # Utiliser le modele selectionne dans la configuration singleton (sidebar)
        # / Use the model selected in the singleton configuration (sidebar)
        configuration_ia = Configuration.get_solo()
        ai_model_actif = configuration_ia.ai_model
        if not ai_model_actif:
            return render(request, "front/includes/extraction_results.html", {
                "error_message": "Aucun modele IA selectionne. Choisissez un modele dans la sidebar.",
            })

        # Construire le prompt snapshot depuis les pieces de l'analyseur
        # / Build prompt snapshot from the analyzer's prompt pieces
        pieces_ordonnees = PromptPiece.objects.filter(
            analyseur=analyseur,
        ).order_by("order")
        prompt_snapshot = "\n".join(piece.content for piece in pieces_ordonnees)

        # Serialiser les exemples few-shot pour stockage dans le job
        # / Serialize few-shot examples for storage in the job
        tous_les_exemples = AnalyseurExample.objects.filter(
            analyseur=analyseur,
        ).order_by("order").prefetch_related("extractions__attributes")

        exemples_serialises = []
        for exemple_django in tous_les_exemples:
            liste_extractions = []
            for extraction_django in exemple_django.extractions.all():
                dictionnaire_attributs = {}
                for attribut in extraction_django.attributes.all():
                    dictionnaire_attributs[attribut.key] = attribut.value
                liste_extractions.append({
                    "extraction_class": extraction_django.extraction_class,
                    "extraction_text": extraction_django.extraction_text,
                    "attributes": dictionnaire_attributs,
                })
            exemples_serialises.append({
                "text": exemple_django.example_text,
                "extractions": liste_extractions,
            })

        # Creer le job d'extraction en status PENDING
        # / Create extraction job in PENDING status
        job_extraction = ExtractionJob.objects.create(
            page=page,
            ai_model=ai_model_actif,
            name=f"Analyseur: {analyseur.name}",
            prompt_description=prompt_snapshot,
            status="pending",
            raw_result={
                "examples_data": exemples_serialises,
                "analyseur_id": analyseur.pk,
            },
        )

        # Lancer la tache Celery en arriere-plan
        # / Launch the Celery task in background
        from front.tasks import analyser_page_task
        analyser_page_task.delay(job_extraction.pk)

        logger.info(
            "analyser: job pk=%s cree pour page=%s analyseur=%s — tache Celery lancee",
            job_extraction.pk, pk, analyseur.name,
        )

        # Retourner le template de polling
        # / Return the polling template
        reponse = render(request, "front/includes/analyse_en_cours.html", {
            "page": page,
        })
        reponse["HX-Trigger"] = "ouvrirPanneauDroit"
        return reponse

    @action(detail=True, methods=["GET"])
    def analyse_status(self, request, pk=None):
        """
        Endpoint de polling HTMX pour suivre la progression d'une analyse IA.
        - pending/processing → renvoie le partial de polling (hx-trigger="every 3s")
        - completed → renvoie extraction_results + OOB readability (arrete le polling)
        - error → renvoie un message d'erreur (arrete le polling)
        / HTMX polling endpoint to track AI analysis progress.
        """
        page = get_object_or_404(Page, pk=pk)

        # Verifier s'il y a un job en cours / Check for in-progress job
        job_en_cours = ExtractionJob.objects.filter(
            page=page,
            status__in=["pending", "processing"],
        ).order_by("-created_at").first()

        if job_en_cours:
            # Timeout : si le job est bloque depuis plus de 5 minutes → erreur
            # / Timeout: if job stuck for more than 5 minutes → error
            delai_max_polling = timedelta(minutes=5)
            age_du_job = timezone.now() - job_en_cours.created_at
            if age_du_job > delai_max_polling:
                logger.warning(
                    "analyse_status: job pk=%s bloque depuis %s — timeout",
                    job_en_cours.pk, age_du_job,
                )
                job_en_cours.status = "error"
                job_en_cours.error_message = (
                    "Timeout : l'analyse n'a pas repondu apres 5 minutes. "
                    "Verifiez que le worker Celery tourne."
                )
                job_en_cours.save(update_fields=["status", "error_message"])
                return render(request, "front/includes/extraction_results.html", {
                    "error_message": job_en_cours.error_message,
                })

            # Toujours en cours → renvoyer le partial de polling
            # / Still processing → return polling partial
            return render(request, "front/includes/analyse_en_cours.html", {
                "page": page,
            })

        # Recuperer le dernier job termine OU en erreur (le plus recent des deux)
        # / Get the latest completed OR error job (whichever is more recent)
        dernier_job_termine = ExtractionJob.objects.filter(
            page=page,
            status="completed",
        ).order_by("-created_at").first()

        dernier_job_erreur = ExtractionJob.objects.filter(
            page=page,
            status="error",
        ).order_by("-created_at").first()

        # Comparer les timestamps : si un job error est plus recent que le completed,
        # afficher l'erreur (cas : re-analyse echouee apres une analyse reussie)
        # / Compare timestamps: if an error job is more recent than completed,
        # show the error (case: failed re-analysis after a successful one)
        if dernier_job_erreur and dernier_job_termine:
            if dernier_job_erreur.created_at > dernier_job_termine.created_at:
                # L'erreur est plus recente → afficher l'erreur
                # / Error is more recent → show error
                message_erreur = dernier_job_erreur.error_message or "Erreur inconnue"
                return render(request, "front/includes/extraction_results.html", {
                    "error_message": message_erreur,
                })

        if dernier_job_termine:
            # Termine → renvoyer les resultats d'extraction + OOB readability
            # / Completed → return extraction results + OOB readability
            toutes_les_entites_du_job, ids_entites_commentees = _annoter_entites_avec_commentaires(
                dernier_job_termine.entities.all()
            )

            html_annote = annoter_html_avec_ancres(
                page.html_readability, page.text_readability,
                toutes_les_entites_du_job, ids_entites_commentees,
            )

            html_cartes = render_to_string(
                "front/includes/extraction_results.html",
                {"job": dernier_job_termine, "entities": toutes_les_entites_du_job},
                request=request,
            )

            # OOB swap pour mettre a jour #readability-content avec le HTML annote
            # / OOB swap to update #readability-content with annotated HTML
            html_readability_oob = (
                '<article id="readability-content" hx-swap-oob="innerHTML:#readability-content">'
                + (html_annote or page.html_readability)
                + '</article>'
            )

            html_complet = html_cartes + html_readability_oob
            reponse = HttpResponse(html_complet)
            reponse["HX-Trigger"] = json.dumps({
                "ouvrirPanneauDroit": True,
                "showToast": {"message": "Analyse termin\u00e9e"},
            })
            return reponse

        if dernier_job_erreur:
            # Erreur sans aucun job completed → afficher l'erreur
            # / Error with no completed job → show error
            message_erreur = dernier_job_erreur.error_message or "Erreur inconnue"
            return render(request, "front/includes/extraction_results.html", {
                "error_message": message_erreur,
            })

        # Fallback : aucun job trouve / Fallback: no job found
        return render(request, "front/includes/extraction_results.html", {
            "error_message": "Aucun job d'analyse trouv\u00e9.",
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
    def supprimer(self, request, pk=None):
        """
        Supprime une page et retourne l'arbre mis a jour.
        Deletes a page and returns the updated tree.
        """
        page_a_supprimer = get_object_or_404(Page, pk=pk)
        titre_page = page_a_supprimer.title or "Sans titre"
        page_a_supprimer.delete()

        reponse = _render_arbre(request)
        reponse["HX-Trigger"] = json.dumps({
            "showToast": {"message": f"Page \u00ab {titre_page} \u00bb supprim\u00e9e"},
        })
        return reponse

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
        analyseurs_actifs = AnalyseurSyntaxique.objects.filter(is_active=True, type_analyseur="analyser")

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

        # Contexte reformulation + restitution : IA active + analyseurs disponibles
        # / Reformulation + restitution context: AI active + available analyzers
        ia_active = _get_ia_active()
        analyseurs_reformuler_existent = AnalyseurSyntaxique.objects.filter(
            is_active=True, type_analyseur="reformuler",
        ).exists()
        analyseurs_restituer_existent = AnalyseurSyntaxique.objects.filter(
            is_active=True, type_analyseur="restituer",
        ).exists()

        html_fil = render_to_string(
            "front/includes/fil_discussion.html",
            {
                "entity": entite,
                "commentaires": tous_les_commentaires,
                "ia_active": ia_active,
                "analyseurs_reformuler_existent": analyseurs_reformuler_existent,
                "analyseurs_restituer_existent": analyseurs_restituer_existent,
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

        # Contexte reformulation + restitution / Reformulation + restitution context
        ia_active = _get_ia_active()
        analyseurs_reformuler_existent = AnalyseurSyntaxique.objects.filter(
            is_active=True, type_analyseur="reformuler",
        ).exists()
        analyseurs_restituer_existent = AnalyseurSyntaxique.objects.filter(
            is_active=True, type_analyseur="restituer",
        ).exists()

        # Re-rendre le fil complet / Re-render full thread
        tous_les_commentaires = CommentaireExtraction.objects.filter(entity=entite)
        html_fil = render_to_string(
            "front/includes/fil_discussion.html",
            {
                "entity": entite,
                "commentaires": tous_les_commentaires,
                "ia_active": ia_active,
                "analyseurs_reformuler_existent": analyseurs_reformuler_existent,
                "analyseurs_restituer_existent": analyseurs_restituer_existent,
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

    @action(detail=False, methods=["POST"], url_path="supprimer_entite")
    def supprimer_entite(self, request):
        """
        Supprime une entite extraite (si pas de commentaires).
        Deletes an extracted entity (if no comments).
        """
        entity_id = request.data.get("entity_id")
        page_id = request.data.get("page_id")
        if not entity_id or not page_id:
            return HttpResponse("entity_id et page_id requis.", status=400)

        entite_a_supprimer = get_object_or_404(ExtractedEntity, pk=entity_id)

        # Verifier qu'il n'y a pas de commentaires / Check no comments exist
        if CommentaireExtraction.objects.filter(entity=entite_a_supprimer).exists():
            return HttpResponse("Impossible de supprimer une extraction qui a des commentaires.", status=400)

        entite_a_supprimer.delete()

        page = get_object_or_404(Page, pk=page_id)
        html_complet = self._render_panneau_complet_avec_oob(request, page)
        reponse = HttpResponse(html_complet)
        reponse["HX-Trigger"] = json.dumps({
            "ouvrirPanneauDroit": True,
            "showToast": {"message": "Extraction supprim\u00e9e"},
        })
        return reponse

    @action(detail=False, methods=["POST"], url_path="supprimer_ia")
    def supprimer_ia(self, request):
        """
        Supprime tous les jobs d'extraction IA (et leurs entites en cascade).
        Les extractions manuelles sont conservees.
        Deletes all AI extraction jobs (and their entities via cascade).
        Manual extractions are preserved.
        """
        page_id = request.data.get("page_id")
        if not page_id:
            return HttpResponse("page_id requis.", status=400)

        page = get_object_or_404(Page, pk=page_id)

        # Supprimer les entites IA sans commentaires (pas les jobs entiers pour garder celles avec commentaires)
        # / Delete AI entities without comments (not entire jobs, to keep commented ones)
        entites_ia_sans_commentaires = ExtractedEntity.objects.filter(
            job__page=page,
            job__ai_model__isnull=False,
        ).exclude(
            commentaires__isnull=False,
        )
        nombre_entites_supprimees = entites_ia_sans_commentaires.count()
        entites_ia_sans_commentaires.delete()

        # Supprimer les jobs IA qui n'ont plus d'entites
        # / Delete AI jobs that have no remaining entities
        jobs_ia_vides = ExtractionJob.objects.filter(
            page=page,
            ai_model__isnull=False,
        ).annotate(
            nombre_entites=Count("entities"),
        ).filter(nombre_entites=0)
        nombre_jobs_supprimes = jobs_ia_vides.count()
        jobs_ia_vides.delete()

        logger.info(
            "supprimer_ia: %d entites et %d jobs IA supprimes pour page pk=%s",
            nombre_entites_supprimees, nombre_jobs_supprimes, page_id,
        )

        html_complet = self._render_panneau_complet_avec_oob(request, page)
        reponse = HttpResponse(html_complet)
        reponse["HX-Trigger"] = json.dumps({
            "ouvrirPanneauDroit": True,
            "showToast": {"message": "Extractions IA supprim\u00e9es"},
        })
        return reponse

    @action(detail=False, methods=["GET"], url_path="formulaire_promouvoir")
    def formulaire_promouvoir(self, request):
        """
        Retourne le partial HTML du formulaire de promotion en entrainement.
        Charge la liste des analyseurs actifs cote serveur.
        / Returns the HTML partial for the training promotion form.
        Loads the active analyzers list server-side.
        """
        page_id = request.query_params.get("page_id")
        if not page_id:
            return HttpResponse("page_id requis.", status=400)

        page = get_object_or_404(Page, pk=page_id)
        tous_les_analyseurs_actifs = AnalyseurSyntaxique.objects.filter(is_active=True)

        return render(request, "front/includes/modale_promouvoir_entrainement.html", {
            "page": page,
            "analyseurs_actifs": tous_les_analyseurs_actifs,
        })

    @action(detail=False, methods=["POST"], url_path="promouvoir_entrainement")
    def promouvoir_entrainement(self, request):
        """
        Promeut les extractions IA d'une page en exemple d'entrainement few-shot.
        Le texte de la page devient le texte source de l'exemple.
        Chaque extraction devient une ExampleExtraction attendue avec ses attributs.
        / Promotes a page's AI extractions into a few-shot training example.
        The page text becomes the example source text.
        Each extraction becomes an expected ExampleExtraction with its attributes.
        """
        # Validation des parametres via serializer DRF
        # / Validate parameters via DRF serializer
        serializer = PromouvoirEntrainementSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning("promouvoir_entrainement: validation echouee — %s", serializer.errors)
            return HttpResponse("Parametres invalides.", status=400)

        page_id = serializer.validated_data["page_id"]
        analyseur_id = serializer.validated_data["analyseur_id"]

        page = get_object_or_404(Page, pk=page_id)
        analyseur = get_object_or_404(AnalyseurSyntaxique, pk=analyseur_id)

        # Recupere toutes les entites IA de la page (jobs completed avec ai_model)
        # / Retrieve all AI entities from the page (completed jobs with ai_model)
        toutes_les_entites_ia = ExtractedEntity.objects.filter(
            job__page=page,
            job__status="completed",
            job__ai_model__isnull=False,
        ).order_by("start_char")

        if not toutes_les_entites_ia.exists():
            return HttpResponse("Aucune extraction IA a promouvoir.", status=400)

        # Calcule l'order du nouvel exemple (max + 1)
        # / Compute order for the new example (max + 1)
        dernier_order_exemple = analyseur.examples.aggregate(
            max_order=Count("id"),
        )["max_order"] or 0

        # Cree le nouvel exemple d'entrainement avec le texte de la page
        # / Create the new training example with the page's text
        nouvel_exemple = AnalyseurExample.objects.create(
            analyseur=analyseur,
            name=page.title[:200] if page.title else f"Exemple depuis page {page.pk}",
            example_text=page.text_readability or "",
            order=dernier_order_exemple,
        )

        # Determine les cles d'attributs de reference :
        # 1. Depuis la premiere extraction du dernier exemple existant de cet analyseur
        # 2. Sinon, cles par defaut
        # / Determine reference attribute keys:
        # 1. From the first extraction of the last existing example of this analyzer
        # 2. Otherwise, default keys
        CLES_ATTRIBUTS_PAR_DEFAUT = ["Hypostase", "Résumé", "Status", "Mots clés"]
        cles_attributs_reference = CLES_ATTRIBUTS_PAR_DEFAUT

        dernier_exemple_existant = analyseur.examples.exclude(
            pk=nouvel_exemple.pk,
        ).prefetch_related("extractions__attributes").order_by("-order").first()

        if dernier_exemple_existant:
            premiere_extraction_reference = dernier_exemple_existant.extractions.first()
            if premiere_extraction_reference:
                cles_depuis_reference = list(
                    premiere_extraction_reference.attributes.order_by("order").values_list("key", flat=True)
                )
                if cles_depuis_reference:
                    cles_attributs_reference = cles_depuis_reference

        # Cree une ExampleExtraction attendue pour chaque entite IA
        # / Create an expected ExampleExtraction for each AI entity
        for numero_entite, entite in enumerate(toutes_les_entites_ia):
            nouvelle_extraction_attendue = ExampleExtraction.objects.create(
                example=nouvel_exemple,
                extraction_class=entite.extraction_class or "",
                extraction_text=entite.extraction_text or "",
                order=numero_entite,
            )

            # Mappe les valeurs du JSONField attributes sur les cles de reference
            # / Map JSONField attribute values onto reference keys
            dictionnaire_attributs_entite = entite.attributes or {}
            liste_valeurs_entite = list(dictionnaire_attributs_entite.values())

            for numero_attribut, cle_reference in enumerate(cles_attributs_reference):
                # Valeur de l'entite a cette position, ou vide si absente
                # / Entity value at this position, or empty if missing
                valeur_attribut = ""
                if numero_attribut < len(liste_valeurs_entite):
                    valeur_attribut = str(liste_valeurs_entite[numero_attribut])

                ExtractionAttribute.objects.create(
                    extraction=nouvelle_extraction_attendue,
                    key=cle_reference,
                    value=valeur_attribut,
                    order=numero_attribut,
                )

        logger.info(
            "promouvoir_entrainement: exemple pk=%d cree avec %d extractions pour analyseur pk=%d",
            nouvel_exemple.pk, toutes_les_entites_ia.count(), analyseur.pk,
        )

        # Retourne le panneau mis a jour + toast de succes
        # / Return updated panel + success toast
        html_complet = self._render_panneau_complet_avec_oob(request, page)
        reponse = HttpResponse(html_complet)
        reponse["HX-Trigger"] = json.dumps({
            "ouvrirPanneauDroit": True,
            "showToast": {"message": f"Ajouté comme entrainement dans {analyseur.name}"},
        })
        return reponse

    @action(detail=False, methods=["GET"], url_path="vue_commentaires")
    def vue_commentaires(self, request):
        """
        Vue globale des commentaires en layout SMS-like pour une page.
        Chaque extraction affiche son texte original, sa reformulation (si existante),
        puis ses commentaires. Le bouton Reformuler apparait par extraction.
        Detecte les reformulations bloquees (timeout 5 min) et les reset.
        / Global SMS-like comments view for a page.
        Each extraction shows its original text, its reformulation (if any),
        then its comments. The Reformulate button appears per extraction.
        Detects stuck reformulations (5 min timeout) and resets them.
        """
        page_id = request.query_params.get("page_id")
        if not page_id:
            return HttpResponse("page_id requis.", status=400)

        page = get_object_or_404(Page, pk=page_id)

        # Timeout : detecte les reformulations bloquees depuis plus de 5 minutes
        # et les remet en etat stable avec un message d'erreur
        # / Timeout: detect reformulations stuck for more than 5 minutes
        # and reset them to stable state with an error message
        delai_max_reformulation = timedelta(minutes=5)
        entites_bloquees = ExtractedEntity.objects.filter(
            job__page=page,
            reformulation_en_cours=True,
            reformulation_lancee_a__isnull=False,
            reformulation_lancee_a__lt=timezone.now() - delai_max_reformulation,
        )
        nombre_entites_resetees = entites_bloquees.count()
        if nombre_entites_resetees > 0:
            entites_bloquees.update(
                reformulation_en_cours=False,
                reformulation_erreur="Timeout : la reformulation n'a pas repondu apres 5 minutes. Verifiez que le worker Celery tourne.",
            )
            logger.warning(
                "vue_commentaires: %d reformulation(s) bloquee(s) resetee(s) pour page=%s",
                nombre_entites_resetees, page_id,
            )

        # Timeout fallback : si reformulation_lancee_a est null mais en_cours=True
        # depuis trop longtemps (pas de timestamp = legacy), reset aussi
        # / Timeout fallback: if reformulation_lancee_a is null but en_cours=True
        entites_bloquees_sans_timestamp = ExtractedEntity.objects.filter(
            job__page=page,
            reformulation_en_cours=True,
            reformulation_lancee_a__isnull=True,
        )
        if entites_bloquees_sans_timestamp.exists():
            entites_bloquees_sans_timestamp.update(
                reformulation_en_cours=False,
                reformulation_erreur="Reformulation interrompue (pas de timestamp). Relancez la reformulation.",
            )
            logger.warning(
                "vue_commentaires: reformulation(s) sans timestamp resetee(s) pour page=%s",
                page_id,
            )

        # Recupere les entites ayant au moins un commentaire, triees par position
        # / Retrieve entities with at least one comment, sorted by position
        entites_avec_commentaires = ExtractedEntity.objects.filter(
            job__page=page,
            job__status="completed",
            commentaires__isnull=False,
        ).distinct().prefetch_related("commentaires").order_by("start_char")

        # Verifie si des analyseurs de type reformuler/restituer existent et si l'IA est active
        # / Check if reformuler/restituer-type analyzers exist and if AI is active
        analyseurs_reformuler_existent = AnalyseurSyntaxique.objects.filter(
            is_active=True, type_analyseur="reformuler",
        ).exists()
        analyseurs_restituer_existent = AnalyseurSyntaxique.objects.filter(
            is_active=True, type_analyseur="restituer",
        ).exists()

        html_vue_commentaires = render_to_string(
            "front/includes/vue_commentaires.html",
            {
                "page": page,
                "entites_avec_commentaires": entites_avec_commentaires,
                "ia_active": _get_ia_active(),
                "analyseurs_reformuler_existent": analyseurs_reformuler_existent,
                "analyseurs_restituer_existent": analyseurs_restituer_existent,
            },
            request=request,
        )

        reponse = HttpResponse(html_vue_commentaires)
        # Declenche le mode debat pour elargir le panneau / Trigger debate mode to widen panel
        reponse["HX-Trigger"] = json.dumps({
            "ouvrirPanneauDroit": True,
            "activerModeDebat": True,
        })
        return reponse

    @action(detail=False, methods=["GET"], url_path="choisir_reformulateur")
    def choisir_reformulateur(self, request):
        """
        Liste les analyseurs actifs de type 'reformuler' pour une extraction.
        / Lists active analyzers of type 'reformuler' for an extraction.
        """
        entity_id = request.query_params.get("entity_id")
        if not entity_id:
            return HttpResponse("entity_id requis.", status=400)

        entite = get_object_or_404(ExtractedEntity, pk=entity_id)

        # Recupere les analyseurs actifs de type reformuler
        # / Retrieve active analyzers of type reformuler
        analyseurs_reformuler = AnalyseurSyntaxique.objects.filter(
            is_active=True, type_analyseur="reformuler",
        )

        return render(request, "front/includes/choisir_reformulateur.html", {
            "entity": entite,
            "page": entite.job.page,
            "analyseurs_reformuler": analyseurs_reformuler,
        })

    @action(detail=False, methods=["POST"], url_path="previsualiser_reformulation")
    def previsualiser_reformulation(self, request):
        """
        Construit le prompt complet de reformulation pour une extraction
        et retourne un partial de confirmation avec estimation tokens et cout.
        / Builds the full reformulation prompt for an extraction
        and returns a confirmation partial with token and cost estimates.
        """
        entity_id = request.data.get("entity_id")
        analyseur_id = request.data.get("analyseur_id")
        if not entity_id or not analyseur_id:
            return HttpResponse("entity_id et analyseur_id requis.", status=400)

        entite = get_object_or_404(ExtractedEntity, pk=entity_id)
        analyseur = get_object_or_404(AnalyseurSyntaxique, pk=analyseur_id)

        # Recupere le modele IA actif depuis la configuration singleton
        # / Get active AI model from singleton configuration
        configuration_ia = Configuration.get_solo()
        modele_ia_actif = configuration_ia.ai_model
        if not modele_ia_actif:
            return HttpResponse("Aucun modèle IA sélectionné.", status=400)

        # Construit le prompt depuis les pieces de l'analyseur
        # / Build prompt from analyzer pieces
        pieces_ordonnees = PromptPiece.objects.filter(
            analyseur=analyseur,
        ).order_by("order")
        texte_prompt_pieces = "\n".join(piece.content for piece in pieces_ordonnees)

        # Texte de l'extraction a reformuler / Extraction text to reformulate
        texte_a_reformuler = entite.extraction_text

        # Assemblage du prompt complet
        # / Full prompt assembly
        prompt_complet = f"{texte_prompt_pieces}\n\n=== TEXTE A REFORMULER ===\n{texte_a_reformuler}"

        # Comptage des tokens via tiktoken
        # / Token counting via tiktoken
        import tiktoken
        encodeur_tokens = tiktoken.get_encoding("cl100k_base")
        nombre_tokens_input = len(encodeur_tokens.encode(prompt_complet))
        nombre_tokens_output_estime = int(nombre_tokens_input * 0.50)

        # Estimation du cout / Cost estimate
        cout_estime_euros = modele_ia_actif.estimer_cout_euros(
            nombre_tokens_input, nombre_tokens_output_estime
        )

        return render(request, "front/includes/confirmation_reformulation.html", {
            "entity": entite,
            "page": entite.job.page,
            "analyseur": analyseur,
            "modele_ia": modele_ia_actif,
            "nombre_tokens_input": nombre_tokens_input,
            "nombre_tokens_output_estime": nombre_tokens_output_estime,
            "cout_estime_euros": cout_estime_euros,
            "prompt_complet": prompt_complet,
            "nombre_pieces": pieces_ordonnees.count(),
        })

    @action(detail=False, methods=["POST"])
    def reformuler(self, request):
        """
        Lance une reformulation asynchrone sur une extraction via Celery.
        Stocke le resultat dans entity.texte_reformule.
        / Launches an async reformulation on an extraction via Celery.
        Stores the result in entity.texte_reformule.
        """
        # Guard : verifie que l'IA est activee / Check AI is enabled
        if not _get_ia_active():
            return HttpResponse("IA desactivee.", status=403)

        serializer = RunReformulationSerializer(data=request.data)
        if not serializer.is_valid():
            return HttpResponse(f"Erreur: {serializer.errors}", status=400)

        entite = get_object_or_404(ExtractedEntity, pk=serializer.validated_data["entity_id"])
        analyseur = get_object_or_404(
            AnalyseurSyntaxique, pk=serializer.validated_data["analyseur_id"]
        )
        page = entite.job.page

        # Guard anti-doublon : verifie si une reformulation est deja en cours
        # avec un timeout de securite pour eviter le blocage permanent
        # / Anti-duplicate guard: check if a reformulation is already in progress
        # with a safety timeout to avoid permanent blocking
        if entite.reformulation_en_cours:
            # Verifie si la reformulation est bloquee (timeout 5 min)
            # / Check if reformulation is stuck (5 min timeout)
            delai_max = timedelta(minutes=5)
            if entite.reformulation_lancee_a and (timezone.now() - entite.reformulation_lancee_a) > delai_max:
                # Timeout atteint → reset et permettre un re-lancement
                # / Timeout reached → reset and allow re-launch
                logger.warning(
                    "reformuler: timeout detecte pour entity=%s — reset",
                    entite.pk,
                )
                entite.reformulation_en_cours = False
                entite.reformulation_erreur = "Timeout : reformulation precedente bloquee, relancez."
                entite.save(update_fields=["reformulation_en_cours", "reformulation_erreur"])
            else:
                return render(request, "front/includes/reformulation_en_cours.html", {
                    "page": page,
                    "entity": entite,
                })

        # Marquer comme en cours avec timestamp / Mark as in progress with timestamp
        entite.reformulation_en_cours = True
        entite.reformulation_lancee_a = timezone.now()
        entite.reformulation_erreur = ""
        entite.save(update_fields=["reformulation_en_cours", "reformulation_lancee_a", "reformulation_erreur"])

        # Lancer la tache Celery / Launch Celery task
        from front.tasks import reformuler_entite_task
        reformuler_entite_task.delay(entite.pk, analyseur.pk)

        logger.info(
            "reformuler: entity pk=%s analyseur=%s — tache Celery lancee",
            entite.pk, analyseur.name,
        )

        return render(request, "front/includes/reformulation_en_cours.html", {
            "page": page,
            "entity": entite,
        })

    @action(detail=False, methods=["GET"], url_path="choisir_restituteur")
    def choisir_restituteur(self, request):
        """
        Liste les analyseurs actifs de type 'restituer' pour une extraction.
        / Lists active analyzers of type 'restituer' for an extraction.
        """
        entity_id = request.query_params.get("entity_id")
        if not entity_id:
            return HttpResponse("entity_id requis.", status=400)

        entite = get_object_or_404(ExtractedEntity, pk=entity_id)

        # Recupere les analyseurs actifs de type restituer
        # / Retrieve active analyzers of type restituer
        analyseurs_restituer = AnalyseurSyntaxique.objects.filter(
            is_active=True, type_analyseur="restituer",
        )

        return render(request, "front/includes/choisir_restituteur.html", {
            "entity": entite,
            "page": entite.job.page,
            "analyseurs_restituer": analyseurs_restituer,
        })

    @action(detail=False, methods=["POST"], url_path="previsualiser_restitution")
    def previsualiser_restitution(self, request):
        """
        Construit le prompt complet de restitution IA pour une extraction
        et retourne un partial de confirmation avec estimation tokens et cout.
        / Builds the full AI restitution prompt for an extraction
        and returns a confirmation partial with token and cost estimates.
        """
        entity_id = request.data.get("entity_id")
        analyseur_id = request.data.get("analyseur_id")
        if not entity_id or not analyseur_id:
            return HttpResponse("entity_id et analyseur_id requis.", status=400)

        entite = get_object_or_404(ExtractedEntity, pk=entity_id)
        analyseur = get_object_or_404(AnalyseurSyntaxique, pk=analyseur_id)

        # Recupere le modele IA actif depuis la configuration singleton
        # / Get active AI model from singleton configuration
        configuration_ia = Configuration.get_solo()
        modele_ia_actif = configuration_ia.ai_model
        if not modele_ia_actif:
            return HttpResponse("Aucun modele IA selectionne.", status=400)

        # Construit le prompt depuis les pieces de l'analyseur
        # / Build prompt from analyzer pieces
        pieces_ordonnees = PromptPiece.objects.filter(
            analyseur=analyseur,
        ).order_by("order")
        texte_prompt_pieces = "\n".join(piece.content for piece in pieces_ordonnees)

        # Texte de l'extraction source / Source extraction text
        texte_extraction = entite.extraction_text

        # Commentaires du debat / Debate comments
        tous_les_commentaires = CommentaireExtraction.objects.filter(entity=entite)
        lignes_commentaires = []
        for commentaire in tous_les_commentaires:
            lignes_commentaires.append(f"{commentaire.prenom}: {commentaire.commentaire}")
        texte_commentaires = "\n".join(lignes_commentaires)

        # Reformulation existante si disponible / Existing reformulation if available
        texte_reformulation = entite.texte_reformule or ""

        # Assemblage du prompt complet
        # / Full prompt assembly
        prompt_complet = texte_prompt_pieces
        prompt_complet += f"\n\n=== EXTRACTION SOURCE ===\n{texte_extraction}"
        if texte_commentaires:
            prompt_complet += f"\n\n=== COMMENTAIRES DU DEBAT ===\n{texte_commentaires}"
        if texte_reformulation:
            prompt_complet += f"\n\n=== REFORMULATION ===\n{texte_reformulation}"

        # Comptage des tokens via tiktoken
        # / Token counting via tiktoken
        import tiktoken
        encodeur_tokens = tiktoken.get_encoding("cl100k_base")
        nombre_tokens_input = len(encodeur_tokens.encode(prompt_complet))
        nombre_tokens_output_estime = int(nombre_tokens_input * 0.50)

        # Estimation du cout / Cost estimate
        cout_estime_euros = modele_ia_actif.estimer_cout_euros(
            nombre_tokens_input, nombre_tokens_output_estime
        )

        return render(request, "front/includes/confirmation_restitution.html", {
            "entity": entite,
            "page": entite.job.page,
            "analyseur": analyseur,
            "modele_ia": modele_ia_actif,
            "nombre_tokens_input": nombre_tokens_input,
            "nombre_tokens_output_estime": nombre_tokens_output_estime,
            "cout_estime_euros": cout_estime_euros,
            "prompt_complet": prompt_complet,
            "nombre_pieces": pieces_ordonnees.count(),
        })

    @action(detail=False, methods=["POST"], url_path="generer_restitution")
    def generer_restitution(self, request):
        """
        Lance une restitution IA asynchrone sur une extraction via Celery.
        / Launches an async AI restitution on an extraction via Celery.
        """
        # Guard : verifie que l'IA est activee / Check AI is enabled
        if not _get_ia_active():
            return HttpResponse("IA desactivee.", status=403)

        serializer = RunRestitutionSerializer(data=request.data)
        if not serializer.is_valid():
            return HttpResponse(f"Erreur: {serializer.errors}", status=400)

        entite = get_object_or_404(ExtractedEntity, pk=serializer.validated_data["entity_id"])
        analyseur = get_object_or_404(
            AnalyseurSyntaxique, pk=serializer.validated_data["analyseur_id"]
        )

        # Guard anti-doublon : verifie si une restitution IA est deja en cours
        # avec un timeout de securite pour eviter le blocage permanent
        # / Anti-duplicate guard: check if an AI restitution is already in progress
        # with a safety timeout to avoid permanent blocking
        if entite.restitution_ia_en_cours:
            delai_max = timedelta(minutes=5)
            if entite.restitution_ia_lancee_a and (timezone.now() - entite.restitution_ia_lancee_a) > delai_max:
                # Timeout atteint → reset et permettre un re-lancement
                # / Timeout reached → reset and allow re-launch
                logger.warning(
                    "generer_restitution: timeout detecte pour entity=%s — reset",
                    entite.pk,
                )
                entite.restitution_ia_en_cours = False
                entite.restitution_ia_erreur = "Timeout : restitution precedente bloquee, relancez."
                entite.save(update_fields=["restitution_ia_en_cours", "restitution_ia_erreur"])
            else:
                return render(request, "front/includes/restitution_ia_en_cours.html", {
                    "entity": entite,
                })

        # Marquer comme en cours avec timestamp / Mark as in progress with timestamp
        entite.restitution_ia_en_cours = True
        entite.restitution_ia_lancee_a = timezone.now()
        entite.restitution_ia_erreur = ""
        entite.save(update_fields=["restitution_ia_en_cours", "restitution_ia_lancee_a", "restitution_ia_erreur"])

        # Lancer la tache Celery / Launch Celery task
        from front.tasks import restituer_debat_task
        restituer_debat_task.delay(entite.pk, analyseur.pk)

        logger.info(
            "generer_restitution: entity pk=%s analyseur=%s — tache Celery lancee",
            entite.pk, analyseur.name,
        )

        return render(request, "front/includes/restitution_ia_en_cours.html", {
            "entity": entite,
        })

    @action(detail=False, methods=["GET"], url_path="restitution_ia_status")
    def restitution_ia_status(self, request):
        """
        Polling : verifie l'etat de la restitution IA pour une extraction.
        Si terminee → renvoie le texte + JS pour pre-remplir le textarea du modal.
        Si en cours → re-renvoie le partial de polling.
        Si erreur → message d'erreur + bouton reessayer.
        / Polling: checks the AI restitution status for an extraction.
        If done → returns text + JS to pre-fill the modal textarea.
        If in progress → re-sends the polling partial.
        If error → error message + retry button.
        """
        entity_id = request.query_params.get("entity_id")
        if not entity_id:
            return HttpResponse("entity_id requis.", status=400)

        entite = get_object_or_404(ExtractedEntity, pk=entity_id)

        # En cours → re-renvoie le polling / In progress → re-send polling
        if entite.restitution_ia_en_cours:
            return render(request, "front/includes/restitution_ia_en_cours.html", {
                "entity": entite,
            })

        # Erreur → message d'erreur / Error → error message
        if entite.restitution_ia_erreur:
            ia_active = _get_ia_active()
            analyseurs_restituer_existent = AnalyseurSyntaxique.objects.filter(
                is_active=True, type_analyseur="restituer",
            ).exists()
            html_erreur = (
                '<div class="bg-red-50 border border-red-200 rounded-lg p-3">'
                '<div class="flex items-start gap-2">'
                '<svg class="w-4 h-4 text-red-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">'
                '<path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"/>'
                '</svg>'
                '<div class="flex-1">'
                '<p class="text-xs font-medium text-red-700 mb-0.5">Erreur de restitution IA</p>'
                f'<p class="text-[10px] text-red-600">{escape(entite.restitution_ia_erreur[:200])}</p>'
                '</div>'
                '</div>'
                '</div>'
            )
            if ia_active and analyseurs_restituer_existent:
                html_erreur += (
                    '<div class="mt-1">'
                    f'<button class="text-[10px] text-red-500 hover:text-red-700 font-medium flex items-center gap-1"'
                    f' hx-get="/extractions/choisir_restituteur/?entity_id={entite.pk}"'
                    f' hx-target="#zone-restitution-ia-{entite.pk}"'
                    f' hx-swap="innerHTML">'
                    '<svg class="w-3 h-3" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">'
                    '<path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182"/>'
                    '</svg>'
                    'Reessayer'
                    '</button>'
                    '</div>'
                )
            return HttpResponse(html_erreur)

        # Termine avec texte → renvoie le resultat + JS pour pre-remplir le textarea
        # / Done with text → return result + JS to pre-fill the textarea
        if entite.texte_restitution_ia:
            texte_echappe_js = entite.texte_restitution_ia.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n").replace("\r", "")
            html_succes = (
                '<div class="bg-violet-50 border border-violet-200 rounded-lg p-3">'
                '<div class="flex items-center gap-1.5 mb-1.5">'
                '<svg class="w-3.5 h-3.5 text-violet-500 shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">'
                '<path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z"/>'
                '</svg>'
                '<span class="text-[10px] font-semibold text-violet-600 uppercase tracking-wide">Restitution IA generee</span>'
                '</div>'
                '<p class="text-xs text-violet-700">Le texte a ete pre-rempli dans le champ ci-dessous. Modifiez-le si necessaire.</p>'
                '</div>'
                '<script>'
                f"var textarea = document.getElementById('textarea-texte-restitution');"
                f"if (textarea) {{ textarea.value = '{texte_echappe_js}'; }}"
                '</script>'
            )
            return HttpResponse(html_succes)

        # Aucun texte et pas en cours → zone vide / No text and not in progress → empty zone
        return HttpResponse("")

    @action(detail=False, methods=["POST"], url_path="creer_restitution")
    def creer_restitution(self, request):
        """
        Cree une nouvelle version de la page avec le texte de restitution insere.
        Le texte est balise avec une ancre violette renvoyant vers l'extraction source.
        / Creates a new page version with the restitution text inserted.
        The text is tagged with a violet anchor linking back to the source extraction.
        """
        from .serializers import RestitutionDebatSerializer

        serializer = RestitutionDebatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        donnees = serializer.validated_data

        entite_source = get_object_or_404(ExtractedEntity, pk=donnees["entity_id"])
        page_source = entite_source.job.page
        page_racine = page_source.page_racine

        texte_restitution_brut = donnees["texte_restitution"]
        label_version = donnees.get("version_label", "")

        # Echappement du texte utilisateur pour prevenir les injections XSS
        # / Escape user text to prevent XSS injection
        texte_restitution_echappe = escape(texte_restitution_brut)

        # Balise de restitution : pastille violette inline (meme pattern que extraction-ancre)
        # suivie du texte dans un <p>, le tout dans un <div> pour le regroupement
        # / Restitution tag: inline violet dot (same pattern as extraction-ancre)
        # followed by text in a <p>, all wrapped in a <div> for grouping
        balise_restitution = (
            f'<div id="restitution-bloc-{entite_source.pk}">'
            f'<p>'
            f'<span class="restitution-ancre" '
            f'data-source-entity-id="{entite_source.pk}" '
            f'data-source-page-id="{page_source.pk}">'
            f'</span>'
            f'{texte_restitution_echappe}'
            f'</p>'
            f'</div>'
        )

        # Cherche une version existante (restitution) de la page racine
        # Si elle existe, on y ajoute le bloc. Sinon, on en cree une vierge.
        # / Look for an existing restitution version of the root page.
        # If it exists, append the block. Otherwise, create a blank one.
        version_restitution_existante = Page.objects.filter(
            parent_page=page_racine,
        ).order_by("-version_number").first()

        if version_restitution_existante:
            # Ajoute le bloc de restitution a la version existante
            # / Append the restitution block to the existing version
            version_restitution_existante.html_readability += "\n" + balise_restitution
            version_restitution_existante.html_original = version_restitution_existante.html_readability
            version_restitution_existante.text_readability = strip_tags(version_restitution_existante.html_readability)
            version_restitution_existante.content_hash = hashlib.sha256(
                version_restitution_existante.text_readability.encode("utf-8")
            ).hexdigest()
            if label_version:
                version_restitution_existante.version_label = label_version
            version_restitution_existante.save(update_fields=[
                "html_readability", "html_original", "text_readability",
                "content_hash", "version_label",
            ])
            page_cible = version_restitution_existante
        else:
            # Cree une version vierge contenant uniquement le bloc de restitution
            # / Create a blank version containing only the restitution block
            prochain_numero = 2
            texte_brut = strip_tags(balise_restitution)
            hash_contenu = hashlib.sha256(texte_brut.encode("utf-8")).hexdigest()
            titre_restitution = page_racine.title or "Sans titre"

            page_cible = Page.objects.create(
                parent_page=page_racine,
                version_number=prochain_numero,
                version_label=label_version or "Restitutions",
                dossier=page_racine.dossier,
                source_type=page_racine.source_type,
                url=None,
                title=titre_restitution,
                html_original=balise_restitution,
                html_readability=balise_restitution,
                text_readability=texte_brut,
                content_hash=hash_contenu,
            )

        # Clot le debat : marque l'entite comme restituee avec lien vers la page cible
        # / Close the debate: mark entity as restituted with link to target page
        entite_source.restitution_page = page_cible
        entite_source.restitution_texte = texte_restitution_brut
        entite_source.restitution_date = timezone.now()
        entite_source.save(update_fields=["restitution_page", "restitution_texte", "restitution_date"])

        # Redirige vers la lecture de la version de restitution via HX-Redirect
        # / Redirect to the restitution version reading via HX-Redirect
        reponse = HttpResponse(status=204)
        reponse["HX-Redirect"] = f"/lire/{page_cible.pk}/"
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


class ImportViewSet(viewsets.ViewSet):
    """
    ViewSet pour l'import de fichiers (documents + audio).
    Convertit le fichier en HTML/texte et cree une Page.
    Les fichiers audio sont traites en async via Celery.
    / ViewSet for file import (documents + audio).
    Converts the file to HTML/text and creates a Page.
    Audio files are processed asynchronously via Celery.
    """

    @action(detail=False, methods=["POST"])
    def fichier(self, request):
        """
        Importe un fichier. Branche vers le pipeline audio si c'est un fichier audio,
        sinon pipeline synchrone pour les documents.
        / Imports a file. Branches to audio pipeline if audio file,
        otherwise synchronous pipeline for documents.
        """
        # Validation via serializer DRF
        # / Validation via DRF serializer
        serializer = ImportFichierSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning("import fichier: validation echouee — %s", serializer.errors)
            return HttpResponse(
                f'<p class="text-sm text-red-500">Erreur: {serializer.errors}</p>',
                status=400,
            )

        fichier_uploade = serializer.validated_data["fichier"]
        nom_fichier = fichier_uploade.name

        # Aiguillage : audio → pipeline async, document → pipeline synchrone
        # / Routing: audio → async pipeline, document → synchronous pipeline
        if est_fichier_audio(nom_fichier):
            return self._importer_fichier_audio(request, serializer)
        else:
            return self._importer_fichier_document(request, serializer)

    def _importer_fichier_audio(self, request, serializer):
        """
        Pipeline d'import audio : sauvegarde temp, cree Page en processing,
        lance la tache Celery, retourne le template de polling.
        / Audio import pipeline: save temp, create Page as processing,
        launch Celery task, return polling template.
        """
        import os
        import uuid
        from django.conf import settings
        from core.models import TranscriptionConfig, TranscriptionJob

        fichier_uploade = serializer.validated_data["fichier"]
        titre_personnalise = serializer.validated_data.get("titre", "")
        dossier_id = serializer.validated_data.get("dossier_id")
        nom_fichier = fichier_uploade.name
        extension_fichier = os.path.splitext(nom_fichier)[1].lower()

        # Sauvegarder le fichier audio dans AUDIO_TEMP_DIR avec un nom unique
        # / Save audio file to AUDIO_TEMP_DIR with a unique name
        nom_unique = f"{uuid.uuid4().hex}{extension_fichier}"
        chemin_fichier_audio = str(settings.AUDIO_TEMP_DIR / nom_unique)

        with open(chemin_fichier_audio, "wb") as destination:
            for morceau in fichier_uploade.chunks():
                destination.write(morceau)

        logger.info(
            "import audio: fichier sauvegarde %s (%s)",
            chemin_fichier_audio, nom_fichier,
        )

        # Determiner le titre et le dossier
        # / Determine title and folder
        nom_sans_extension = os.path.splitext(nom_fichier)[0]
        titre_final = titre_personnalise.strip() if titre_personnalise.strip() else nom_sans_extension
        dossier_assigne = None
        if dossier_id:
            dossier_assigne = Dossier.objects.filter(pk=dossier_id).first()

        # Creer la Page en status "processing" avec un placeholder HTML
        # / Create Page in "processing" status with a placeholder HTML
        page_audio = Page.objects.create(
            source_type="audio",
            original_filename=nom_fichier,
            url=None,
            title=titre_final,
            html_original="",
            html_readability='<p class="text-slate-400 italic">Transcription en cours...</p>',
            text_readability="",
            content_hash="",
            status="processing",
            dossier=dossier_assigne,
        )

        # Recuperer la config de transcription active (ou None pour mock)
        # / Get active transcription config (or None for mock)
        config_transcription_active = TranscriptionConfig.objects.filter(
            is_active=True,
        ).first()

        # Creer le TranscriptionJob
        # / Create the TranscriptionJob
        job_transcription = TranscriptionJob.objects.create(
            page=page_audio,
            transcription_config=config_transcription_active,
            audio_filename=nom_fichier,
            status="pending",
        )

        # Lancer la tache Celery en arriere-plan
        # / Launch the Celery task in background
        from front.tasks import transcrire_audio_task
        # Nombre max de locuteurs et langue depuis la config
        # / Max speakers and language from config
        max_locuteurs_config = config_transcription_active.max_speakers if config_transcription_active else 5
        langue_config = config_transcription_active.language if config_transcription_active else "fr"
        resultat_tache = transcrire_audio_task.delay(
            job_transcription.pk, chemin_fichier_audio, max_locuteurs_config, langue_config,
        )

        # Stocker l'ID Celery dans le job
        # / Store Celery ID in the job
        job_transcription.celery_task_id = resultat_tache.id
        job_transcription.save(update_fields=["celery_task_id"])

        logger.info(
            "import audio: page pk=%s job pk=%s celery_id=%s",
            page_audio.pk, job_transcription.pk, resultat_tache.id,
        )

        # Retourner le template de polling + OOB arbre
        # / Return polling template + OOB tree
        html_polling = render_to_string(
            "front/includes/transcription_en_cours.html",
            {"page": page_audio},
            request=request,
        )

        # OOB swap : arbre de dossiers mis a jour
        # / OOB swap: updated folder tree
        html_arbre_oob = render_to_string(
            "front/includes/arbre_dossiers.html",
            {
                "dossiers": Dossier.objects.prefetch_related("pages").all(),
                "pages_orphelines": Page.objects.filter(dossier__isnull=True).order_by("-created_at"),
            },
            request=request,
        )
        html_arbre_oob = (
            '<div id="arbre" hx-swap-oob="innerHTML:#arbre">'
            + html_arbre_oob
            + '</div>'
        )

        html_complet = html_polling + html_arbre_oob
        reponse = HttpResponse(html_complet)
        reponse["HX-Trigger"] = json.dumps({
            "showToast": {"message": "Transcription lanc\u00e9e..."},
        })
        return reponse

    def _importer_fichier_document(self, request, serializer):
        """
        Pipeline d'import synchrone pour les documents (PDF, DOCX, etc.).
        / Synchronous import pipeline for documents (PDF, DOCX, etc.).
        """
        import hashlib
        from front.services.conversion_fichiers import convertir_fichier_en_html

        fichier_uploade = serializer.validated_data["fichier"]
        titre_personnalise = serializer.validated_data.get("titre", "")
        dossier_id = serializer.validated_data.get("dossier_id")
        nom_fichier = fichier_uploade.name

        # Conversion du fichier en HTML + texte
        # / Convert file to HTML + text
        try:
            html_readability, text_readability, titre_extrait = convertir_fichier_en_html(
                fichier_uploade, nom_fichier,
            )
        except ValueError as erreur_conversion:
            logger.error("import fichier: erreur conversion — %s", erreur_conversion)
            return HttpResponse(
                f'<p class="text-sm text-red-500">Erreur de conversion: {erreur_conversion}</p>',
                status=400,
            )
        except Exception as erreur_inattendue:
            logger.error("import fichier: erreur inattendue — %s", erreur_inattendue, exc_info=True)
            return HttpResponse(
                '<p class="text-sm text-red-500">Erreur inattendue lors de la conversion du fichier.</p>',
                status=500,
            )

        # Determiner le titre final et le dossier
        # / Determine final title and folder
        titre_final = titre_personnalise.strip() if titre_personnalise.strip() else titre_extrait
        dossier_assigne = None
        if dossier_id:
            dossier_assigne = Dossier.objects.filter(pk=dossier_id).first()

        # Calculer le hash du contenu pour content_hash
        # / Compute content hash
        hash_contenu = hashlib.sha256(text_readability.encode("utf-8")).hexdigest()

        # Creer la Page avec source_type='file'
        # / Create the Page with source_type='file'
        page_importee = Page.objects.create(
            source_type="file",
            original_filename=nom_fichier,
            url=None,
            title=titre_final,
            html_original=html_readability,
            html_readability=html_readability,
            text_readability=text_readability,
            content_hash=hash_contenu,
            dossier=dossier_assigne,
        )

        logger.info(
            "import fichier: page pk=%s creee depuis '%s' (%d chars HTML)",
            page_importee.pk, nom_fichier, len(html_readability),
        )

        # Rendu du partial de lecture + OOB arbre et panneau
        # / Render reading partial + OOB tree and panel
        analyseurs_actifs = AnalyseurSyntaxique.objects.filter(is_active=True, type_analyseur="analyser")
        ia_active = _get_ia_active()
        contexte_partage = {
            "page": page_importee,
            "html_annote": None,
            "analyseurs_actifs": analyseurs_actifs,
            "job": None,
            "entities": None,
            "ia_active": ia_active,
        }

        html_lecture = render_to_string(
            "front/includes/lecture_principale.html",
            contexte_partage,
            request=request,
        )

        # OOB swap : arbre de dossiers mis a jour
        # / OOB swap: updated folder tree
        html_arbre_oob = render_to_string(
            "front/includes/arbre_dossiers.html",
            {
                "dossiers": Dossier.objects.prefetch_related("pages").all(),
                "pages_orphelines": Page.objects.filter(dossier__isnull=True).order_by("-created_at"),
            },
            request=request,
        )
        html_arbre_oob = (
            '<div id="arbre" hx-swap-oob="innerHTML:#arbre">'
            + html_arbre_oob
            + '</div>'
        )

        # OOB swap : panneau d'analyse reinitialise
        # / OOB swap: reset analysis panel
        html_panneau_oob = render_to_string(
            "front/includes/panneau_analyse.html",
            contexte_partage,
            request=request,
        )
        html_panneau_oob = (
            '<div id="panneau-extractions" hx-swap-oob="innerHTML:#panneau-extractions">'
            + html_panneau_oob
            + '</div>'
        )

        html_complet = html_lecture + html_arbre_oob + html_panneau_oob
        reponse = HttpResponse(html_complet)
        reponse["HX-Trigger"] = json.dumps({
            "showToast": {"message": "Fichier import\u00e9"},
        })
        return reponse

    @action(detail=False, methods=["GET"])
    def status(self, request):
        """
        Endpoint de polling HTMX pour suivre la progression d'une transcription audio.
        - pending/processing → renvoie le partial de polling (hx-trigger="every 3s")
        - completed → renvoie lecture_principale + OOB panneau (arrete le polling)
        - error → renvoie un message d'erreur (arrete le polling)
        / HTMX polling endpoint to track audio transcription progress.
        - pending/processing → returns polling partial (hx-trigger="every 3s")
        - completed → returns lecture_principale + OOB panel (stops polling)
        - error → returns error message (stops polling)
        """
        page_id = request.query_params.get("page_id")
        if not page_id:
            return HttpResponse("page_id requis.", status=400)

        page = get_object_or_404(Page, pk=page_id)

        if page.status in ("pending", "processing"):
            # Toujours en cours → renvoyer le partial de polling
            # / Still processing → return polling partial
            return render(request, "front/includes/transcription_en_cours.html", {
                "page": page,
            })

        elif page.status == "completed":
            # Termine → renvoyer le contenu de lecture normal
            # / Completed → return normal reading content
            analyseurs_actifs = AnalyseurSyntaxique.objects.filter(is_active=True, type_analyseur="analyser")
            ia_active = _get_ia_active()
            contexte_partage = {
                "page": page,
                "html_annote": None,
                "analyseurs_actifs": analyseurs_actifs,
                "job": None,
                "entities": None,
                "ia_active": ia_active,
            }

            html_lecture = render_to_string(
                "front/includes/lecture_principale.html",
                contexte_partage,
                request=request,
            )

            # OOB swap : panneau d'analyse
            # / OOB swap: analysis panel
            html_panneau_oob = render_to_string(
                "front/includes/panneau_analyse.html",
                contexte_partage,
                request=request,
            )
            html_panneau_oob = (
                '<div id="panneau-extractions" hx-swap-oob="innerHTML:#panneau-extractions">'
                + html_panneau_oob
                + '</div>'
            )

            html_complet = html_lecture + html_panneau_oob
            reponse = HttpResponse(html_complet)
            reponse["HX-Trigger"] = json.dumps({
                "showToast": {"message": "Transcription termin\u00e9e"},
            })
            return reponse

        else:
            # Erreur → afficher le message d'erreur (arrete le polling)
            # / Error → display error message (stops polling)
            message_erreur = page.error_message or "Erreur inconnue lors de la transcription."
            return HttpResponse(
                f'<div class="max-w-3xl mx-auto p-6">'
                f'<div class="bg-red-50 border border-red-200 rounded-lg p-4">'
                f'<h3 class="text-red-700 font-semibold mb-2">Erreur de transcription</h3>'
                f'<p class="text-red-600 text-sm">{message_erreur}</p>'
                f'</div></div>',
            )


    @action(detail=False, methods=["POST"], url_path="previsualiser_audio")
    def previsualiser_audio(self, request):
        """
        Recoit le fichier audio, le sauvegarde en temp, calcule la duree,
        et retourne un partial de confirmation avec estimation de cout.
        / Receives the audio file, saves it temporarily, computes duration,
        and returns a confirmation partial with cost estimate.
        """
        import os
        import uuid
        from django.conf import settings
        from core.models import TranscriptionConfig

        # Validation via serializer DRF
        # / Validation via DRF serializer
        serializer = ImportFichierSerializer(data=request.data)
        if not serializer.is_valid():
            return HttpResponse(
                f'<p class="text-sm text-red-500">Erreur: {serializer.errors}</p>',
                status=400,
            )

        fichier_uploade = serializer.validated_data["fichier"]
        nom_fichier = fichier_uploade.name
        extension_fichier = os.path.splitext(nom_fichier)[1].lower()

        # Sauvegarder le fichier audio dans AUDIO_TEMP_DIR avec un nom unique
        # / Save audio file to AUDIO_TEMP_DIR with a unique name
        nom_unique = f"{uuid.uuid4().hex}{extension_fichier}"
        chemin_fichier_audio = str(settings.AUDIO_TEMP_DIR / nom_unique)

        with open(chemin_fichier_audio, "wb") as destination:
            for morceau in fichier_uploade.chunks():
                destination.write(morceau)

        # Calculer la duree du fichier audio (mutagen + ffprobe fallback)
        # / Compute audio file duration (mutagen + ffprobe fallback)
        from front.services.transcription_audio import calculer_duree_audio
        duree_secondes = calculer_duree_audio(chemin_fichier_audio)

        # Recuperer la config de transcription active
        # / Get active transcription config
        config_transcription = TranscriptionConfig.objects.filter(is_active=True).first()

        # Calcul du cout estime en euros
        # / Compute estimated cost in euros
        cout_estime_euros = 0.0
        if config_transcription:
            cout_estime_euros = config_transcription.estimer_cout_euros(duree_secondes)

        # Formater la duree en minutes:secondes pour affichage
        # / Format duration as minutes:seconds for display
        minutes_duree = int(duree_secondes // 60)
        secondes_restantes = int(duree_secondes % 60)
        duree_formatee = f"{minutes_duree}:{secondes_restantes:02d}"

        # Taille du fichier en Mo / File size in MB
        taille_fichier_mo = os.path.getsize(chemin_fichier_audio) / (1024 * 1024)

        # Valeurs par defaut depuis la config (locuteurs et langue)
        # / Default values from config (speakers and language)
        max_locuteurs_defaut = config_transcription.max_speakers if config_transcription else 5
        langue_defaut = config_transcription.language if config_transcription else "fr"

        return render(request, "front/includes/confirmation_audio.html", {
            "nom_fichier": nom_fichier,
            "chemin_fichier_temp": nom_unique,
            "duree_formatee": duree_formatee,
            "duree_secondes": round(duree_secondes, 1),
            "taille_fichier_mo": round(taille_fichier_mo, 2),
            "config_transcription": config_transcription,
            "cout_estime_euros": cout_estime_euros,
            "choix_max_locuteurs": range(1, 11),
            "max_locuteurs_defaut": max_locuteurs_defaut,
            "langue_defaut": langue_defaut,
        })

    @action(detail=False, methods=["POST"], url_path="confirmer_audio")
    def confirmer_audio(self, request):
        """
        Lance la transcription d'un fichier audio deja sauvegarde en temp.
        Recoit le nom du fichier temp (pas le fichier lui-meme).
        / Launches transcription of an already temp-saved audio file.
        Receives the temp file name (not the file itself).
        """
        import os
        from django.conf import settings
        from core.models import TranscriptionConfig, TranscriptionJob

        nom_fichier_temp = request.data.get("chemin_fichier_temp", "")
        nom_fichier_original = request.data.get("nom_fichier", "Fichier audio")
        titre_personnalise = request.data.get("titre", "")
        dossier_id = request.data.get("dossier_id")

        # Nombre max de locuteurs choisi par l'utilisateur (defaut: 5)
        # / Max speakers count chosen by the user (default: 5)
        try:
            max_locuteurs = int(request.data.get("max_speakers", 5))
            max_locuteurs = max(1, min(max_locuteurs, 10))
        except (ValueError, TypeError):
            max_locuteurs = 5

        # Langue de l'audio choisie par l'utilisateur (vide = detection auto)
        # / Audio language chosen by the user (empty = auto-detect)
        langue_audio = request.data.get("language", "").strip()

        if not nom_fichier_temp:
            return HttpResponse("Fichier temporaire introuvable.", status=400)

        chemin_fichier_audio = str(settings.AUDIO_TEMP_DIR / nom_fichier_temp)
        if not os.path.exists(chemin_fichier_audio):
            return HttpResponse("Le fichier temporaire a expire ou n'existe plus.", status=400)

        # Determiner le titre et le dossier
        # / Determine title and folder
        nom_sans_extension = os.path.splitext(nom_fichier_original)[0]
        titre_final = titre_personnalise.strip() if titre_personnalise.strip() else nom_sans_extension
        dossier_assigne = None
        if dossier_id:
            dossier_assigne = Dossier.objects.filter(pk=dossier_id).first()

        # Creer la Page en status "processing"
        # / Create Page in "processing" status
        page_audio = Page.objects.create(
            source_type="audio",
            original_filename=nom_fichier_original,
            url=None,
            title=titre_final,
            html_original="",
            html_readability='<p class="text-slate-400 italic">Transcription en cours...</p>',
            text_readability="",
            content_hash="",
            status="processing",
            dossier=dossier_assigne,
        )

        # Recuperer la config de transcription active (ou None pour mock)
        # / Get active transcription config (or None for mock)
        config_transcription_active = TranscriptionConfig.objects.filter(
            is_active=True,
        ).first()

        # Creer le TranscriptionJob
        # / Create the TranscriptionJob
        job_transcription = TranscriptionJob.objects.create(
            page=page_audio,
            transcription_config=config_transcription_active,
            audio_filename=nom_fichier_original,
            status="pending",
        )

        # Lancer la tache Celery en arriere-plan
        # / Launch the Celery task in background
        from front.tasks import transcrire_audio_task
        resultat_tache = transcrire_audio_task.delay(
            job_transcription.pk, chemin_fichier_audio, max_locuteurs, langue_audio,
        )

        # Stocker l'ID Celery dans le job
        # / Store Celery ID in the job
        job_transcription.celery_task_id = resultat_tache.id
        job_transcription.save(update_fields=["celery_task_id"])

        logger.info(
            "confirmer_audio: page pk=%s job pk=%s celery_id=%s",
            page_audio.pk, job_transcription.pk, resultat_tache.id,
        )

        # Retourner le template de polling + OOB arbre
        # / Return polling template + OOB tree
        html_polling = render_to_string(
            "front/includes/transcription_en_cours.html",
            {"page": page_audio},
            request=request,
        )

        html_arbre_oob = render_to_string(
            "front/includes/arbre_dossiers.html",
            {
                "dossiers": Dossier.objects.prefetch_related("pages").all(),
                "pages_orphelines": Page.objects.filter(dossier__isnull=True).order_by("-created_at"),
            },
            request=request,
        )
        html_arbre_oob = (
            '<div id="arbre" hx-swap-oob="innerHTML:#arbre">'
            + html_arbre_oob
            + '</div>'
        )

        html_complet = html_polling + html_arbre_oob
        reponse = HttpResponse(html_complet)
        reponse["HX-Trigger"] = json.dumps({
            "showToast": {"message": "Transcription lancée..."},
        })
        return reponse


class QuestionnaireViewSet(viewsets.ViewSet):
    """
    ViewSet pour le questionnaire — questions et reponses liees a une page.
    / ViewSet for the questionnaire — questions and answers linked to a page.
    """

    def _render_questionnaire(self, request, page):
        """
        Helper — rend le partial du questionnaire pour une page.
        / Helper — renders the questionnaire partial for a page.
        """
        toutes_les_questions = Question.objects.filter(
            page=page,
        ).prefetch_related("reponses").order_by("-created_at")

        return render(request, "front/includes/vue_questionnaire.html", {
            "page": page,
            "toutes_les_questions": toutes_les_questions,
        })

    def list(self, request):
        """
        Affiche le questionnaire pour une page (GET avec ?page_id=...).
        / Displays the questionnaire for a page (GET with ?page_id=...).
        """
        page_id = request.query_params.get("page_id")
        if not page_id:
            return HttpResponse("page_id requis.", status=400)

        page = get_object_or_404(Page, pk=page_id)
        return self._render_questionnaire(request, page)

    @action(detail=False, methods=["POST"], url_path="poser_question")
    def poser_question(self, request):
        """
        Cree une nouvelle question sur une page et re-rend le questionnaire.
        / Creates a new question on a page and re-renders the questionnaire.
        """
        serializer = QuestionSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning("poser_question: validation echouee — %s", serializer.errors)
            return HttpResponse(
                f'<p class="text-sm text-red-500">Erreur: {serializer.errors}</p>',
                status=400,
            )

        donnees = serializer.validated_data
        page = get_object_or_404(Page, pk=donnees["page_id"])

        # Creer la question / Create the question
        Question.objects.create(
            page=page,
            prenom=donnees["prenom"],
            texte_question=donnees["texte_question"],
        )

        reponse = self._render_questionnaire(request, page)
        reponse["HX-Trigger"] = json.dumps({
            "showToast": {"message": "Question ajout\u00e9e"},
        })
        return reponse

    @action(detail=False, methods=["POST"])
    def repondre(self, request):
        """
        Cree une reponse a une question et re-rend le questionnaire.
        / Creates an answer to a question and re-renders the questionnaire.
        """
        serializer = ReponseQuestionSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning("repondre: validation echouee — %s", serializer.errors)
            return HttpResponse(
                f'<p class="text-sm text-red-500">Erreur: {serializer.errors}</p>',
                status=400,
            )

        donnees = serializer.validated_data
        question = get_object_or_404(Question, pk=donnees["question_id"])

        # Creer la reponse / Create the answer
        ReponseQuestion.objects.create(
            question=question,
            prenom=donnees["prenom"],
            texte_reponse=donnees["texte_reponse"],
        )

        reponse_http = self._render_questionnaire(request, question.page)
        reponse_http["HX-Trigger"] = json.dumps({
            "showToast": {"message": "R\u00e9ponse ajout\u00e9e"},
        })
        return reponse_http
