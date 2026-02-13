"""
Views pour l'application Hypostasis Extractor.
ViewSet DRF avec actions pour gerer les jobs d'extraction.
"""

import json
import logging
from datetime import timedelta

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)


def _saved_response():
    """Retourne un petit fragment HTML 'Sauvegarde OK' pour le feedback HTMX."""
    return HttpResponse('Sauvegarde OK', content_type='text/html')


def _normalize_attribute_orders_for_analyseur(analyseur_id):
    """
    Renumerote sequentiellement (0, 1, 2...) les attributs de CHAQUE extraction
    de chaque exemple de l'analyseur donne.
    Garantit que les ordres se suivent sans trou ni doublon.
    / Renumber sequentially (0, 1, 2...) the attributes of EVERY extraction
    of every example of the given analyzer.
    """
    from .models import ExtractionAttribute
    extractions_ids = ExtractionAttribute.objects.filter(
        extraction__example__analyseur_id=analyseur_id
    ).values_list('extraction_id', flat=True).distinct()

    for extraction_id in extractions_ids:
        attributes = ExtractionAttribute.objects.filter(
            extraction_id=extraction_id
        ).order_by('order', 'pk')
        for index, attr in enumerate(attributes):
            if attr.order != index:
                attr.order = index
                attr.save(update_fields=['order'])

from django.db import models as db_models
from .models import (
    ExtractionJob, ExtractedEntity, ExtractionExample,
    AnalyseurSyntaxique, PromptPiece, AnalyseurExample, ExampleExtraction, ExtractionAttribute,
    AnalyseurTestRun, TestRunExtraction,
    QuestionnairePrompt, QuestionnairePromptPiece,
)
from .serializers import (
    ExtractionJobListSerializer,
    ExtractionJobCreateSerializer,
    ExtractionJobDetailSerializer,
    ExtractedEntitySerializer,
    ExtractionExampleSerializer,
    ExtractionValidationSerializer,
    RunExtractionSerializer,
    AnalyseurSyntaxiqueCreateSerializer,
    AnalyseurSyntaxiqueUpdateSerializer,
    PromptPieceCreateSerializer,
    PromptPieceUpdateSerializer,
    AnalyseurExampleCreateSerializer,
    AnalyseurExampleUpdateSerializer,
    ExampleExtractionCreateSerializer,
    ExampleExtractionUpdateSerializer,
    ExtractionAttributeSerializer,
    ExtractionAttributeUpdateSerializer,
    RunAnalyseurTestSerializer,
    ValidateTestExtractionSerializer,
    RejectTestExtractionSerializer,
    QuestionnairePromptCreateSerializer,
    QuestionnairePromptUpdateSerializer,
    QuestionnairePromptPieceCreateSerializer,
    QuestionnairePromptPieceUpdateSerializer,
)
from .services import run_langextract_job, generate_visualization_html


@method_decorator(csrf_exempt, name='dispatch')
class ExtractionJobViewSet(viewsets.ViewSet):
    """
    ViewSet pour gerer les jobs d'extraction LangExtract.
    
    Actions:
    - list: Liste des jobs
    - retrieve: Detail d'un job avec ses entites
    - create: Creation d'un nouveau job
    - run: Lancement de l'extraction (action custom)
    - validate_entity: Validation d'une entite par l'utilisateur
    - visualization: Generation du HTML de visualisation
    """
    
    permission_classes = [permissions.AllowAny]
    
    def list(self, request):
        """
        Liste tous les jobs d'extraction.
        Filtre possible par page_id via query param.
        """
        jobs_query = ExtractionJob.objects.select_related('page', 'ai_model')
        
        # Filtre par page si specifie
        page_id = request.query_params.get('page')
        if page_id:
            jobs_query = jobs_query.filter(page_id=page_id)
        
        # Filtre par statut
        status_filter = request.query_params.get('status')
        if status_filter:
            jobs_query = jobs_query.filter(status=status_filter)
        
        jobs_list = jobs_query.order_by('-created_at')
        
        # Si requete HTML, on rend le template
        if request.accepted_renderer.format == 'html':
            return render(request, 'hypostasis_extractor/job_list.html', {
                'jobs': jobs_list
            })
        
        # Sinon JSON
        serializer = ExtractionJobListSerializer(jobs_list, many=True)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        """
        Detail d'un job avec toutes ses entites.
        """
        job = get_object_or_404(
            ExtractionJob.objects.select_related('page', 'ai_model'),
            pk=pk
        )
        
        # Precharge les entites pour optimisation
        job_with_entities = ExtractionJob.objects.prefetch_related('entities').get(pk=job.pk)
        
        if request.accepted_renderer.format == 'html':
            from core.models import HypostasisTag
            return render(request, 'hypostasis_extractor/job_detail.html', {
                'job': job_with_entities,
                'page': job.page,
                'all_hypostases': HypostasisTag.objects.all().order_by('name')
            })
        
        serializer = ExtractionJobDetailSerializer(job_with_entities)
        return Response(serializer.data)
    
    def create(self, request):
        """
        Creation d'un nouveau job d'extraction.
        """
        serializer = ExtractionJobCreateSerializer(data=request.data)
        
        if serializer.is_valid():
            job = serializer.save()
            
            if request.headers.get('HX-Request'):
                # Retourne un partiel HTMX
                return render(request, 'hypostasis_extractor/includes/job_row.html', {
                    'job': job
                }, status=status.HTTP_201_CREATED)
            
            return Response(
                ExtractionJobDetailSerializer(job).data,
                status=status.HTTP_201_CREATED
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def run(self, request, pk=None):
        """
        Action: Lance l'extraction LangExtract pour ce job.
        """
        job = get_object_or_404(ExtractionJob, pk=pk)
        
        # Valide les parametres d'execution
        params_serializer = RunExtractionSerializer(data=request.data)
        params_serializer.is_valid(raise_exception=True)
        params = params_serializer.validated_data
        
        try:
            # Execute l'extraction
            entities_count, processing_time = run_langextract_job(
                job,
                use_chunking=params['use_chunking'],
                max_workers=params['max_workers']
            )
            
            # Recharge le job avec les entites
            job = ExtractionJob.objects.prefetch_related('entities').get(pk=job.pk)
            
            if request.headers.get('HX-Request'):
                # Retourne le partiel avec les resultats
                return render(request, 'hypostasis_extractor/includes/job_results.html', {
                    'job': job
                })
            
            return Response({
                'status': 'success',
                'entities_count': entities_count,
                'processing_time': processing_time
            })
            
        except Exception as e:
            if request.headers.get('HX-Request'):
                return render(request, 'hypostasis_extractor/includes/job_error.html', {
                    'job': job,
                    'error': str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            return Response({
                'status': 'error',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['get'])
    def visualization(self, request, pk=None):
        """
        Action: Genere le HTML de visualisation LangExtract.
        """
        job = get_object_or_404(ExtractionJob, pk=pk)
        
        if job.status != 'completed':
            return Response({
                'error': 'Job not completed yet'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            html_content = generate_visualization_html(job)
            
            if hasattr(html_content, 'data'):
                html_content = html_content.data
            
            return Response({'html': html_content})
            
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(csrf_exempt, name='dispatch')
class ExtractedEntityViewSet(viewsets.ViewSet):
    """
    ViewSet pour gerer les entites extraites.
    """
    
    permission_classes = [permissions.AllowAny]
    
    def list(self, request):
        """
        Liste les entites, filtrable par job_id.
        """
        entities_query = ExtractedEntity.objects.select_related('job', 'hypostasis_tag')
        
        job_id = request.query_params.get('job')
        if job_id:
            entities_query = entities_query.filter(job_id=job_id)
        
        # Filtre par classe d'extraction
        extraction_class = request.query_params.get('class')
        if extraction_class:
            entities_query = entities_query.filter(extraction_class=extraction_class)
        
        # Filtre par validation
        validated = request.query_params.get('validated')
        if validated is not None:
            entities_query = entities_query.filter(user_validated=validated.lower() == 'true')
        
        entities_list = entities_query.order_by('start_char')
        
        serializer = ExtractedEntitySerializer(entities_list, many=True)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        """
        Detail d'une entite.
        """
        entity = get_object_or_404(
            ExtractedEntity.objects.select_related('job', 'hypostasis_tag'),
            pk=pk
        )
        
        serializer = ExtractedEntitySerializer(entity)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post', 'patch'])
    def validate(self, request, pk=None):
        """
        Action: Valide ou modifie une entite extraite.
        Permet a l'utilisateur de corriger le mapping vers une hypostasis.
        """
        entity = get_object_or_404(ExtractedEntity, pk=pk)
        
        serializer = ExtractionValidationSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            
            entity.user_validated = data['user_validated']
            entity.user_notes = data.get('user_notes', '')
            
            # Met a jour le tag hypostasis si fourni
            hypostasis_id = data.get('hypostasis_tag_id')
            if hypostasis_id:
                from core.models import HypostasisTag
                try:
                    entity.hypostasis_tag = HypostasisTag.objects.get(pk=hypostasis_id)
                except HypostasisTag.DoesNotExist:
                    pass
            
            entity.save()
            
            if request.headers.get('HX-Request'):
                return render(request, 'hypostasis_extractor/includes/entity_card.html', {
                    'entity': entity
                })
            
            return Response(ExtractedEntitySerializer(entity).data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(csrf_exempt, name='dispatch')
class ExtractionExampleViewSet(viewsets.ViewSet):
    """
    ViewSet pour gerer les exemples few-shot reutilisables.
    """
    
    permission_classes = [permissions.AllowAny]
    
    def list(self, request):
        """
        Liste tous les exemples actifs.
        """
        examples_list = ExtractionExample.objects.filter(is_active=True).order_by('-created_at')
        
        if request.accepted_renderer.format == 'html':
            return render(request, 'hypostasis_extractor/example_list.html', {
                'examples': examples_list
            })
        
        serializer = ExtractionExampleSerializer(examples_list, many=True)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        """
        Detail d'un exemple.
        """
        example = get_object_or_404(ExtractionExample, pk=pk)
        serializer = ExtractionExampleSerializer(example)
        return Response(serializer.data)
    
    def create(self, request):
        """
        Creation d'un nouvel exemple.
        """
        serializer = ExtractionExampleSerializer(data=request.data)

        if serializer.is_valid():
            example = serializer.save()
            return Response(
                ExtractionExampleSerializer(example).data,
                status=status.HTTP_201_CREATED
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# =============================================================================
# ViewSet pour les Analyseurs Syntaxiques
# / ViewSet for Syntactic Analyzers
# =============================================================================

@method_decorator(csrf_exempt, name='dispatch')
class AnalyseurSyntaxiqueViewSet(viewsets.ViewSet):
    """
    ViewSet pour gerer les analyseurs syntaxiques configurables.
    CRUD complet + actions pour pieces, exemples, extractions, attributs.
    / ViewSet for managing configurable syntactic analyzers.
    Full CRUD + actions for pieces, examples, extractions, attributes.
    """

    permission_classes = [permissions.AllowAny]

    # ---- CRUD Analyseur ----

    def list(self, request):
        """Liste des analyseurs — retourne HTML partial pour sidebar."""
        analyseurs_list = AnalyseurSyntaxique.objects.filter(is_active=True)
        return render(request, 'hypostasis_extractor/analyseur_list.html', {
            'analyseurs': analyseurs_list
        })

    def retrieve(self, request, pk=None):
        """
        Detail d'un analyseur.
        - Requete HTMX → retourne le partial editeur (zone-lecture)
        - Acces direct (F5, lien) → retourne la page complete base.html avec editeur pre-charge
        / Analyzer detail.
        - HTMX request → returns editor partial (zone-lecture)
        - Direct access (F5, link) → returns full base.html with pre-loaded editor
        """
        analyseur = get_object_or_404(
            AnalyseurSyntaxique.objects.prefetch_related(
                'pieces', 'examples__extractions__attributes'
            ),
            pk=pk
        )

        from core.models import AIModel
        active_ai_models = AIModel.objects.filter(
            api_key__isnull=False,
        )

        # Contexte commun onglet/scroll
        active_tab = request.query_params.get('tab', 'prompt')
        scroll_to = request.query_params.get('scroll_to', '')
        editor_context = {
            'analyseur': analyseur,
            'active_tab': active_tab,
            'scroll_to': scroll_to,
            'collapse_examples': bool(scroll_to),
            'active_ai_models': active_ai_models,
        }

        # Requete HTMX → partial seulement
        if request.headers.get('HX-Request'):
            return render(request, 'hypostasis_extractor/analyseur_editor.html', editor_context)

        # Acces direct (F5) → page complete avec editeur pre-charge
        return render(request, 'front/base.html', {
            'analyseur_preloaded': analyseur,
            **editor_context,
        })

    def create(self, request):
        """Creation d'un analyseur."""
        serializer = AnalyseurSyntaxiqueCreateSerializer(data=request.data)
        if serializer.is_valid():
            analyseur = AnalyseurSyntaxique.objects.create(**serializer.validated_data)
            logger.info("Analyseur cree: pk=%d name='%s'", analyseur.pk, analyseur.name)
            return render(request, 'hypostasis_extractor/includes/analyseur_item.html', {
                'analyseur': analyseur
            }, status=status.HTTP_201_CREATED)
        logger.warning("Analyseur create: validation echouee — %s", serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, pk=None):
        """Mise a jour partielle (auto-save) / Partial update (auto-save)."""
        analyseur = get_object_or_404(AnalyseurSyntaxique, pk=pk)
        serializer = AnalyseurSyntaxiqueUpdateSerializer(data=request.data)
        if serializer.is_valid():
            for field_name, field_value in serializer.validated_data.items():
                setattr(analyseur, field_name, field_value)
            analyseur.save()
            return _saved_response()
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, pk=None):
        """Suppression d'un analyseur / Delete an analyzer."""
        analyseur = get_object_or_404(AnalyseurSyntaxique, pk=pk)
        logger.info("Analyseur supprime: pk=%d name='%s'", analyseur.pk, analyseur.name)
        analyseur.delete()
        # 200 au lieu de 204 : HTMX ignore le swap sur 204 No Content
        return HttpResponse(status=200)

    # ---- Actions PromptPiece ----

    @action(detail=True, methods=['post'])
    def add_piece(self, request, pk=None):
        """Ajoute une piece de prompt / Add a prompt piece."""
        analyseur = get_object_or_404(AnalyseurSyntaxique, pk=pk)
        serializer = PromptPieceCreateSerializer(data=request.data)
        if serializer.is_valid():
            piece = PromptPiece.objects.create(
                analyseur=analyseur, **serializer.validated_data
            )
            return render(request, 'hypostasis_extractor/includes/piece_row.html', {
                'piece': piece, 'analyseur': analyseur
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'])
    def update_piece(self, request, pk=None):
        """Mise a jour partielle d'une piece (auto-save) / Partial update."""
        get_object_or_404(AnalyseurSyntaxique, pk=pk)
        serializer = PromptPieceUpdateSerializer(data=request.data)
        if serializer.is_valid():
            piece_id = serializer.validated_data.pop('piece_id')
            piece = get_object_or_404(PromptPiece, pk=piece_id, analyseur_id=pk)
            for field_name, field_value in serializer.validated_data.items():
                setattr(piece, field_name, field_value)
            piece.save()
            return _saved_response()
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['delete'])
    def delete_piece(self, request, pk=None):
        """Supprime une piece / Delete a piece."""
        get_object_or_404(AnalyseurSyntaxique, pk=pk)
        piece_id = request.data.get('piece_id') or request.query_params.get('piece_id')
        piece = get_object_or_404(PromptPiece, pk=piece_id, analyseur_id=pk)
        piece.delete()
        return HttpResponse(status=200)

    # ---- Actions AnalyseurExample ----

    @action(detail=True, methods=['post'])
    def add_example(self, request, pk=None):
        """Ajoute un exemple / Add an example."""
        analyseur = get_object_or_404(AnalyseurSyntaxique, pk=pk)
        serializer = AnalyseurExampleCreateSerializer(data=request.data)
        if serializer.is_valid():
            example = AnalyseurExample.objects.create(
                analyseur=analyseur, **serializer.validated_data
            )
            return render(request, 'hypostasis_extractor/includes/example_card.html', {
                'example': example, 'analyseur': analyseur
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'])
    def update_example(self, request, pk=None):
        """Mise a jour partielle d'un exemple (auto-save) / Partial update."""
        get_object_or_404(AnalyseurSyntaxique, pk=pk)
        serializer = AnalyseurExampleUpdateSerializer(data=request.data)
        if serializer.is_valid():
            example_id = serializer.validated_data.pop('example_id')
            example = get_object_or_404(AnalyseurExample, pk=example_id, analyseur_id=pk)
            for field_name, field_value in serializer.validated_data.items():
                setattr(example, field_name, field_value)
            example.save()
            return _saved_response()
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['delete'])
    def delete_example(self, request, pk=None):
        """Supprime un exemple / Delete an example."""
        get_object_or_404(AnalyseurSyntaxique, pk=pk)
        example_id = request.data.get('example_id') or request.query_params.get('example_id')
        example = get_object_or_404(AnalyseurExample, pk=example_id, analyseur_id=pk)
        example.delete()
        return HttpResponse(status=200)

    # ---- Actions ExampleExtraction ----

    @action(detail=True, methods=['post'])
    def add_extraction(self, request, pk=None):
        """
        Ajoute une extraction a un exemple.
        Si l'exemple a deja des extractions, copie les cles d'attributs
        (avec ordre) de la premiere, valeurs vides.
        / Add an extraction to an example.
        If the example already has extractions, copy attribute keys
        (with order) from the first one, with empty values.
        """
        analyseur = get_object_or_404(AnalyseurSyntaxique, pk=pk)
        serializer = ExampleExtractionCreateSerializer(data=request.data)
        if serializer.is_valid():
            example_id = serializer.validated_data.pop('example_id')
            example = get_object_or_404(AnalyseurExample, pk=example_id, analyseur_id=pk)

            # Recupere la premiere extraction existante pour copier ses cles
            first_sibling = example.extractions.prefetch_related('attributes').first()

            extraction = ExampleExtraction.objects.create(
                example=example, **serializer.validated_data
            )

            # Copie les cles d'attributs depuis la premiere extraction sœur
            if first_sibling:
                for attr in first_sibling.attributes.all():
                    ExtractionAttribute.objects.create(
                        extraction=extraction,
                        key=attr.key,
                        value="",
                        order=attr.order
                    )

            _normalize_attribute_orders_for_analyseur(analyseur.pk)
            extraction_count = example.extractions.count()
            # Nouvelle extraction = jamais la premiere (first_sibling existait)
            is_first = not first_sibling
            return render(request, 'hypostasis_extractor/includes/extraction_row.html', {
                'extraction': extraction, 'analyseur': analyseur,
                'extraction_count': extraction_count, 'is_first': is_first
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'])
    def update_extraction(self, request, pk=None):
        """Mise a jour partielle d'une extraction (auto-save) / Partial update."""
        analyseur = get_object_or_404(AnalyseurSyntaxique, pk=pk)
        serializer = ExampleExtractionUpdateSerializer(data=request.data)
        if serializer.is_valid():
            extraction_id = serializer.validated_data.pop('extraction_id')
            extraction = get_object_or_404(
                ExampleExtraction.objects.filter(example__analyseur=analyseur),
                pk=extraction_id
            )
            for field_name, field_value in serializer.validated_data.items():
                setattr(extraction, field_name, field_value)
            extraction.save()
            return _saved_response()
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'])
    def save_all_extractions(self, request, pk=None):
        """
        Sauvegarde de TOUTES les extractions d'un exemple d'un coup.
        Evite les ecrasements quand on modifie plusieurs extractions.
        Payload JSON attendu :
        {
            "example_id": 1,
            "extractions": [
                {
                    "extraction_id": 1,
                    "extraction_class": "these",
                    "extraction_text": "...",
                    "attributes": [{"id": 1, "key": "stance", "value": "pour"}, ...]
                },
                ...
            ]
        }
        / Save ALL extractions of an example at once.
        Prevents overwrites when multiple extractions are modified.
        """
        from .serializers import sanitize_text

        analyseur = get_object_or_404(AnalyseurSyntaxique, pk=pk)
        example_id = request.data.get('example_id')
        example = get_object_or_404(AnalyseurExample, pk=example_id, analyseur=analyseur)
        extractions_data = request.data.get('extractions', [])

        for ext_data in extractions_data:
            extraction_id = ext_data.get('extraction_id')
            if not extraction_id:
                continue
            try:
                extraction = ExampleExtraction.objects.get(pk=extraction_id, example=example)
            except ExampleExtraction.DoesNotExist:
                continue

            # Mise a jour classe et texte
            extraction_class = ext_data.get('extraction_class')
            extraction_text = ext_data.get('extraction_text')
            if extraction_class is not None:
                extraction.extraction_class = sanitize_text(extraction_class)
            if extraction_text is not None:
                extraction.extraction_text = sanitize_text(extraction_text)
            extraction.save()

            # Mise a jour des attributs (avec order)
            attributes_data = ext_data.get('attributes', [])
            for index, attr_data in enumerate(attributes_data):
                attr_id = attr_data.get('id')
                attr_key = sanitize_text(attr_data.get('key', ''))
                attr_value = sanitize_text(attr_data.get('value', ''))
                attr_order = attr_data.get('order', index)

                if attr_id:
                    try:
                        attribute = ExtractionAttribute.objects.get(
                            pk=attr_id, extraction=extraction
                        )
                        attribute.key = attr_key
                        attribute.value = attr_value
                        attribute.order = attr_order
                        attribute.save()
                    except ExtractionAttribute.DoesNotExist:
                        pass
                else:
                    ExtractionAttribute.objects.create(
                        extraction=extraction, key=attr_key, value=attr_value, order=attr_order
                    )

        _normalize_attribute_orders_for_analyseur(analyseur.pk)

        # Propage les cles de la 1ere extraction vers toutes les sœurs
        # / Propagate keys from 1st extraction to all siblings
        first_extraction = example.extractions.order_by('order', 'pk').first()
        if first_extraction:
            reference_attributes = list(first_extraction.attributes.order_by('order'))
            sibling_extractions = example.extractions.exclude(pk=first_extraction.pk)
            # Propage la classe de reference / Propagate reference class
            for sibling in sibling_extractions:
                if sibling.extraction_class != first_extraction.extraction_class:
                    sibling.extraction_class = first_extraction.extraction_class
                    sibling.save(update_fields=['extraction_class'])
            for sibling in sibling_extractions:
                existing_attrs = list(sibling.attributes.order_by('order'))
                for i, ref_attr in enumerate(reference_attributes):
                    if i < len(existing_attrs):
                        if existing_attrs[i].key != ref_attr.key or existing_attrs[i].order != ref_attr.order:
                            existing_attrs[i].key = ref_attr.key
                            existing_attrs[i].order = ref_attr.order
                            existing_attrs[i].save(update_fields=['key', 'order'])
                    else:
                        ExtractionAttribute.objects.create(
                            extraction=sibling,
                            key=ref_attr.key,
                            value="",
                            order=ref_attr.order
                        )
                if len(existing_attrs) > len(reference_attributes):
                    ids_to_delete = [a.pk for a in existing_attrs[len(reference_attributes):]]
                    ExtractionAttribute.objects.filter(pk__in=ids_to_delete).delete()

        return _saved_response()

    @action(detail=True, methods=['delete'])
    def delete_extraction(self, request, pk=None):
        """
        Supprime une extraction attendue.
        Declenche un refresh des cartes de test si des TestRunExtraction
        pointaient vers cette extraction (promoted_to_extraction).
        / Delete an expected extraction.
        Triggers a test card refresh if TestRunExtractions
        pointed to this extraction (promoted_to_extraction).
        """
        analyseur = get_object_or_404(AnalyseurSyntaxique, pk=pk)
        extraction_id = request.data.get('extraction_id') or request.query_params.get('extraction_id')
        extraction = get_object_or_404(
            ExampleExtraction.objects.select_related('example').filter(example__analyseur=analyseur),
            pk=extraction_id
        )

        example_id = extraction.example_id
        extraction.delete()

        # Declenche un refresh du container de test pour cet exemple
        # Les cartes "Obtenu" verront que promoted_to_extraction est devenu null (SET_NULL)
        # / Trigger a test container refresh for this example
        # "Obtained" cards will see that promoted_to_extraction became null (SET_NULL)
        response = HttpResponse(status=200)
        response['HX-Trigger'] = json.dumps({
            'refreshTestResults': {
                'exampleId': example_id,
            }
        })
        return response

    # ---- Actions ExtractionAttribute ----

    @action(detail=True, methods=['post'])
    def add_attribute(self, request, pk=None):
        """Ajoute un attribut a une extraction / Add an attribute."""
        analyseur = get_object_or_404(AnalyseurSyntaxique, pk=pk)
        extraction_id = request.data.get('extraction_id')
        extraction = get_object_or_404(
            ExampleExtraction.objects.filter(example__analyseur=analyseur),
            pk=extraction_id
        )
        serializer = ExtractionAttributeSerializer(data=request.data)
        if serializer.is_valid():
            # Calcule l'order max + 1 pour le nouvel attribut
            max_order = extraction.attributes.aggregate(db_models.Max('order'))['order__max'] or -1
            validated = serializer.validated_data
            validated['order'] = max_order + 1
            attribute = ExtractionAttribute.objects.create(
                extraction=extraction, **validated
            )

            # Propage la meme cle (valeur vide) aux extractions sœurs
            # / Propagate same key (empty value) to sibling extractions
            example = extraction.example
            sibling_extractions = example.extractions.exclude(pk=extraction.pk)
            for sibling in sibling_extractions:
                if not sibling.attributes.filter(order=attribute.order).exists():
                    ExtractionAttribute.objects.create(
                        extraction=sibling,
                        key=attribute.key,
                        value="",
                        order=attribute.order
                    )

            _normalize_attribute_orders_for_analyseur(analyseur.pk)
            attribute.refresh_from_db()
            return render(request, 'hypostasis_extractor/includes/attribute_row.html', {
                'attribute': attribute, 'analyseur': analyseur
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'])
    def update_attribute(self, request, pk=None):
        """Mise a jour d'un attribut (auto-save) / Update attribute."""
        analyseur = get_object_or_404(AnalyseurSyntaxique, pk=pk)
        serializer = ExtractionAttributeUpdateSerializer(data=request.data)
        if serializer.is_valid():
            attribute_id = serializer.validated_data.pop('attribute_id')
            attribute = get_object_or_404(
                ExtractionAttribute.objects.filter(extraction__example__analyseur=analyseur),
                pk=attribute_id
            )
            for field_name, field_value in serializer.validated_data.items():
                setattr(attribute, field_name, field_value)
            attribute.save()
            return _saved_response()
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'])
    def reorder_attribute(self, request, pk=None):
        """
        Permute l'ordre d'un attribut avec son voisin (up/down).
        Le swap est applique sur TOUTES les extractions de l'exemple
        (cle:valeur restent groupees).
        Retourne le bloc complet de toutes les extractions re-rendues.
        / Swap an attribute's order with its neighbor (up/down).
        The swap is applied on ALL extractions of the example
        (key:value stay grouped).
        Returns the full re-rendered extractions block.
        """
        analyseur = get_object_or_404(AnalyseurSyntaxique, pk=pk)
        attribute_id = request.data.get('attribute_id')
        direction = request.data.get('direction')  # "up" ou "down"

        attribute = get_object_or_404(
            ExtractionAttribute.objects.filter(extraction__example__analyseur=analyseur),
            pk=attribute_id
        )
        extraction = attribute.extraction
        example = extraction.example

        # Normalise avant swap
        _normalize_attribute_orders_for_analyseur(analyseur.pk)
        attribute.refresh_from_db()

        all_attributes = list(extraction.attributes.order_by('order', 'pk'))
        current_index = next(
            (i for i, a in enumerate(all_attributes) if a.pk == attribute.pk), None
        )
        if current_index is None:
            return HttpResponse(status=400)

        # Determine le voisin a permuter
        if direction == 'up' and current_index > 0:
            neighbor = all_attributes[current_index - 1]
        elif direction == 'down' and current_index < len(all_attributes) - 1:
            neighbor = all_attributes[current_index + 1]
        else:
            # Deja en haut/bas — re-rend sans changer
            example = AnalyseurExample.objects.prefetch_related(
                'extractions__attributes'
            ).get(pk=example.pk)
            return render(request, 'hypostasis_extractor/includes/extractions_block.html', {
                'example': example, 'analyseur': analyseur
            })

        old_order = attribute.order
        new_order = neighbor.order

        # Applique le swap sur TOUTES les extractions de l'exemple
        # / Apply the swap on ALL extractions of the example
        for ext in example.extractions.all():
            ext_attrs = {a.order: a for a in ext.attributes.all()}
            attr_a = ext_attrs.get(old_order)
            attr_b = ext_attrs.get(new_order)
            if attr_a and attr_b:
                attr_a.order, attr_b.order = new_order, old_order
                attr_a.save(update_fields=['order'])
                attr_b.save(update_fields=['order'])

        # Recharge l'exemple avec toutes ses relations
        example = AnalyseurExample.objects.prefetch_related(
            'extractions__attributes'
        ).get(pk=example.pk)
        return render(request, 'hypostasis_extractor/includes/extractions_block.html', {
            'example': example, 'analyseur': analyseur
        })

    @action(detail=True, methods=['delete'])
    def delete_attribute(self, request, pk=None):
        """Supprime un attribut / Delete an attribute."""
        analyseur = get_object_or_404(AnalyseurSyntaxique, pk=pk)
        attribute_id = request.data.get('attribute_id') or request.query_params.get('attribute_id')
        attribute = get_object_or_404(
            ExtractionAttribute.objects.filter(extraction__example__analyseur=analyseur),
            pk=attribute_id
        )
        attribute.delete()
        _normalize_attribute_orders_for_analyseur(analyseur.pk)
        return HttpResponse(status=200)

    # ---- Actions Test & Benchmark LLM ----

    @action(detail=True, methods=['post'])
    def run_test(self, request, pk=None):
        """
        Lance un entrainement LangExtract asynchrone sur un exemple via Celery.
        - Si un entrainement est deja en cours pour cet exemple → renvoie le polling
        - Sinon → cree un AnalyseurTestRun, lance la tache Celery, renvoie le polling
        / Launches an async LangExtract training on an example via Celery.
        - If training already running for this example → returns polling
        - Otherwise → creates AnalyseurTestRun, launches Celery task, returns polling
        """
        from core.models import AIModel
        analyseur = get_object_or_404(AnalyseurSyntaxique, pk=pk)
        serializer = RunAnalyseurTestSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning("run_test: validation echouee — %s", serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        example_id = serializer.validated_data['example_id']
        ai_model_id = serializer.validated_data['ai_model_id']
        example = get_object_or_404(AnalyseurExample, pk=example_id, analyseur=analyseur)
        ai_model = get_object_or_404(AIModel, pk=ai_model_id, api_key__isnull=False)

        # Guard anti-doublon : verifier s'il y a deja un entrainement en cours pour cet exemple
        # / Anti-duplicate guard: check if training already running for this example
        test_run_en_cours = AnalyseurTestRun.objects.filter(
            analyseur=analyseur,
            example=example,
            status__in=["pending", "processing"],
        ).first()

        if test_run_en_cours:
            logger.info(
                "run_test: entrainement deja en cours test_run=%s pour example=%s",
                test_run_en_cours.pk, example.pk,
            )
            return render(request, 'hypostasis_extractor/includes/entrainement_en_cours.html', {
                'test_run': test_run_en_cours,
                'analyseur': analyseur,
            })

        # Construire le prompt snapshot depuis les pieces de l'analyseur
        # / Build prompt snapshot from analyzer's prompt pieces
        pieces_ordonnees = PromptPiece.objects.filter(
            analyseur=analyseur,
        ).order_by("order")
        prompt_snapshot = "\n".join(piece.content for piece in pieces_ordonnees)

        # Creer le test run en status PENDING
        # / Create test run in PENDING status
        nom_modele_affichage = f"{ai_model.provider} / {ai_model.model_name}"
        test_run = AnalyseurTestRun.objects.create(
            analyseur=analyseur,
            example=example,
            ai_model=ai_model,
            ai_model_display_name=nom_modele_affichage,
            prompt_snapshot=prompt_snapshot,
            status="pending",
        )

        # Lancer la tache Celery en arriere-plan
        # / Launch the Celery task in background
        from hypostasis_extractor.tasks import entrainer_analyseur_task
        entrainer_analyseur_task.delay(test_run.pk)

        logger.info(
            "run_test: test_run pk=%s cree pour analyseur=%s example=%s model=%s — tache Celery lancee",
            test_run.pk, analyseur.pk, example.pk, ai_model.model_name,
        )

        # Retourner le template de polling
        # / Return the polling template
        return render(request, 'hypostasis_extractor/includes/entrainement_en_cours.html', {
            'test_run': test_run,
            'analyseur': analyseur,
        })

    @action(detail=True, methods=['get'])
    def test_run_status(self, request, pk=None):
        """
        Endpoint de polling HTMX pour suivre la progression d'un entrainement.
        - pending/processing → renvoie le partial de polling (hx-trigger="every 3s")
        - completed → renvoie test_run_result.html (arrete le polling)
        - error → renvoie test_run_error.html (arrete le polling)
        / HTMX polling endpoint to track training progress.
        """
        analyseur = get_object_or_404(AnalyseurSyntaxique, pk=pk)
        test_run_id = request.query_params.get('test_run_id')
        if not test_run_id:
            return HttpResponse("test_run_id requis.", status=400)

        test_run = get_object_or_404(AnalyseurTestRun, pk=test_run_id, analyseur=analyseur)

        if test_run.status in ("pending", "processing"):
            # Timeout : si l'entrainement est bloque depuis plus de 5 minutes → erreur
            # / Timeout: if training stuck for more than 5 minutes → error
            delai_max_polling = timedelta(minutes=5)
            age_du_test_run = timezone.now() - test_run.created_at
            if age_du_test_run > delai_max_polling:
                logger.warning(
                    "test_run_status: test_run pk=%s bloque depuis %s — timeout",
                    test_run.pk, age_du_test_run,
                )
                test_run.status = "error"
                test_run.error_message = (
                    "Timeout : l'entrainement n'a pas repondu apres 5 minutes. "
                    "Verifiez que le worker Celery tourne."
                )
                test_run.save(update_fields=["status", "error_message"])
                return render(request, 'hypostasis_extractor/includes/test_run_error.html', {
                    'error': test_run.error_message,
                })

            # Toujours en cours → renvoyer le partial de polling
            # / Still processing → return polling partial
            return render(request, 'hypostasis_extractor/includes/entrainement_en_cours.html', {
                'test_run': test_run,
                'analyseur': analyseur,
            })

        if test_run.status == "completed":
            # Termine → renvoyer le resultat complet du test run
            # / Completed → return full test run result
            test_extractions_with_attrs = _resolve_test_extraction_attrs(test_run)
            expected_extractions = list(
                test_run.example.extractions.prefetch_related('attributes').all()
            )

            return render(request, 'hypostasis_extractor/includes/test_run_result.html', {
                'test_run': test_run,
                'test_extractions_with_attrs': test_extractions_with_attrs,
                'expected_extractions': expected_extractions,
                'analyseur': analyseur,
            })

        # Error → renvoyer le message d'erreur / Error → return error message
        return render(request, 'hypostasis_extractor/includes/test_run_error.html', {
            'error': test_run.error_message or "Erreur inconnue",
        })

    @action(detail=True, methods=['get'])
    def test_results(self, request, pk=None):
        """
        Retourne la liste des test runs pour un exemple donne.
        / Returns the list of test runs for a given example.
        """
        analyseur = get_object_or_404(AnalyseurSyntaxique, pk=pk)
        example_id = request.query_params.get('example_id')
        if not example_id:
            return HttpResponse(status=400)

        test_runs = AnalyseurTestRun.objects.filter(
            analyseur=analyseur, example_id=example_id
        ).prefetch_related('extractions__promoted_to_extraction')

        # Pre-resoudre les attributs pour chaque test run
        test_runs_data = []
        example = get_object_or_404(AnalyseurExample, pk=example_id, analyseur=analyseur)
        expected_extractions = list(example.extractions.prefetch_related('attributes').all())

        for test_run in test_runs:
            test_extractions_with_attrs = _resolve_test_extraction_attrs(test_run)
            test_runs_data.append({
                'test_run': test_run,
                'test_extractions_with_attrs': test_extractions_with_attrs,
                'expected_extractions': expected_extractions,
            })

        return render(request, 'hypostasis_extractor/includes/test_results_list.html', {
            'test_runs_data': test_runs_data,
            'analyseur': analyseur,
        })

    @action(detail=True, methods=['get'])
    def expected_extractions(self, request, pk=None):
        """
        Retourne le bloc HTML des extractions attendues d'un exemple.
        Utilise par le refresh HTMX apres validation d'une extraction de test.
        / Returns the HTML block of expected extractions for an example.
        Used by HTMX refresh after validating a test extraction.
        """
        analyseur = get_object_or_404(AnalyseurSyntaxique, pk=pk)
        example_id = request.query_params.get('example_id')
        if not example_id:
            return HttpResponse(status=400)

        example = get_object_or_404(
            AnalyseurExample.objects.prefetch_related('extractions__attributes'),
            pk=example_id, analyseur=analyseur
        )

        return render(request, 'hypostasis_extractor/includes/extractions_block.html', {
            'example': example,
            'analyseur': analyseur,
        })

    @action(detail=True, methods=['delete'])
    def delete_test_run(self, request, pk=None):
        """Supprime un test run / Delete a test run."""
        analyseur = get_object_or_404(AnalyseurSyntaxique, pk=pk)
        test_run_id = request.data.get('test_run_id') or request.query_params.get('test_run_id')
        test_run = get_object_or_404(AnalyseurTestRun, pk=test_run_id, analyseur=analyseur)
        logger.info("delete_test_run: pk=%d model=%s analyseur=%d",
                    test_run.pk, test_run.ai_model_display_name, analyseur.pk)
        test_run.delete()
        return HttpResponse(status=200)

    @action(detail=True, methods=['post'])
    def validate_test_extraction(self, request, pk=None):
        """
        Valide une extraction obtenue : la copie comme ExampleExtraction attendue.
        Utilise les CLES DE REFERENCE (premiere extraction humaine) et mappe
        les VALEURS du LLM par position.
        / Validate an obtained extraction: copy it as an expected ExampleExtraction.
        Uses REFERENCE KEYS (first human extraction) and maps LLM VALUES by position.
        """
        from .models import TestRunExtractionAnnotation

        analyseur = get_object_or_404(AnalyseurSyntaxique, pk=pk)

        # Validation via serializer — verifie existence, pas deja validee,
        # et correspondance du nombre d'attributs avec la reference
        # / Validation via serializer — checks existence, not already validated,
        # and attribute count matches reference
        serializer = ValidateTestExtractionSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning("validate_test_extraction: validation echouee — %s", serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        test_extraction = serializer.validated_data['test_extraction']
        reference_attribute_keys = serializer.validated_data['reference_attribute_keys']
        example = test_extraction.test_run.example
        logger.info("validate_test_extraction: extraction=%d class='%s' example=%d ref_keys=%s",
                    test_extraction.pk, test_extraction.extraction_class, example.pk,
                    reference_attribute_keys)

        # Calcule l'order max des extractions existantes
        # / Compute max order of existing extractions
        max_order_result = example.extractions.aggregate(
            max_order=db_models.Max('order')
        )['max_order']
        next_order = (max_order_result or 0) + 1

        # Cree l'ExampleExtraction attendue / Create the expected ExampleExtraction
        new_extraction = ExampleExtraction.objects.create(
            example=example,
            extraction_class=test_extraction.extraction_class,
            extraction_text=test_extraction.extraction_text,
            order=next_order,
        )

        # Mappe les valeurs LLM sur les cles de reference PAR POSITION
        # Ex: reference = ["Hypostases", "Resume", "Statut", "Mots-cles"]
        #     LLM values = ["Definition", "Le triptyque...", "Consensuel", "Triptyque, ..."]
        # → attr 0: key="Hypostases" value="Definition"
        # / Map LLM values to reference keys BY POSITION
        llm_attribute_values = list((test_extraction.attributes or {}).values())

        for attr_order, reference_key in enumerate(reference_attribute_keys):
            # Valeur du LLM a cette position, ou vide si manquante
            # / LLM value at this position, or empty if missing
            llm_value = ""
            if attr_order < len(llm_attribute_values):
                llm_value = str(llm_attribute_values[attr_order])

            ExtractionAttribute.objects.create(
                extraction=new_extraction,
                key=reference_key,
                value=llm_value,
                order=attr_order,
            )

        # Marque l'annotation / Mark the annotation
        test_extraction.human_annotation = TestRunExtractionAnnotation.VALIDATED
        test_extraction.promoted_to_extraction = new_extraction
        test_extraction.save(update_fields=['human_annotation', 'promoted_to_extraction'])
        logger.info("validate_test_extraction: promue en ExampleExtraction pk=%d avec %d attributs",
                    new_extraction.pk, len(reference_attribute_keys))

        _normalize_attribute_orders_for_analyseur(analyseur.pk)

        # Retourne la carte annotee + le header HX-Trigger pour rafraichir
        # le bloc des extractions attendues cote client
        # / Return annotated card + HX-Trigger header to refresh
        # the expected extractions block on the client side
        response = render(request, 'hypostasis_extractor/includes/test_extraction_card.html', {
            'resolved': _resolve_single_test_extraction(test_extraction),
            'analyseur': analyseur,
        })

        # Declenche un evenement HTMX custom pour re-rendre le bloc attendu
        # / Trigger a custom HTMX event to re-render the expected block
        response['HX-Trigger-After-Swap'] = json.dumps({
            'refreshExpectedExtractions': {
                'exampleId': example.pk,
            }
        })
        return response

    @action(detail=True, methods=['post'])
    def reject_test_extraction(self, request, pk=None):
        """
        Marque une extraction obtenue comme inappropriee.
        / Mark an obtained extraction as inappropriate.
        """
        from .models import TestRunExtractionAnnotation

        analyseur = get_object_or_404(AnalyseurSyntaxique, pk=pk)

        # Validation via serializer / Validation via serializer
        serializer = RejectTestExtractionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        extraction_id = serializer.validated_data['extraction_id']
        note = serializer.validated_data['note']

        test_extraction = get_object_or_404(
            TestRunExtraction.objects.filter(test_run__analyseur=analyseur),
            pk=extraction_id
        )

        test_extraction.human_annotation = TestRunExtractionAnnotation.REJECTED
        test_extraction.annotation_note = note
        test_extraction.save(update_fields=['human_annotation', 'annotation_note'])
        logger.info("reject_test_extraction: extraction=%d rejetee, note='%s'",
                    test_extraction.pk, note[:80] if note else '')

        return render(request, 'hypostasis_extractor/includes/test_extraction_card.html', {
            'resolved': _resolve_single_test_extraction(test_extraction),
            'analyseur': analyseur,
        })


def _build_resolved_dict(test_extraction):
    """
    Construit le dict de contexte template pour une TestRunExtraction.
    Inclut les attr_0..3 par position et le flag is_promotion_alive.
    / Build the template context dict for a TestRunExtraction.
    Includes attr_0..3 by position and the is_promotion_alive flag.
    """
    attrs = test_extraction.attributes or {}
    values = list(attrs.values())

    # Verifie si la FK promoted_to_extraction pointe encore vers un objet existant
    # SET_NULL fait que le champ devient None si l'ExampleExtraction est supprimee
    # / Check if promoted_to_extraction FK still points to an existing object
    is_promotion_alive = (
        test_extraction.human_annotation == 'validated'
        and test_extraction.promoted_to_extraction_id is not None
    )

    return {
        'extraction': test_extraction,
        'attr_0': values[0] if len(values) > 0 else '',
        'attr_1': values[1] if len(values) > 1 else '',
        'attr_2': values[2] if len(values) > 2 else '',
        'attr_3': values[3] if len(values) > 3 else '',
        'is_promotion_alive': is_promotion_alive,
    }


def _resolve_single_test_extraction(test_extraction):
    """
    Resoud les attributs d'une seule TestRunExtraction pour le template.
    / Resolve attributes for a single TestRunExtraction for the template.
    """
    return _build_resolved_dict(test_extraction)


def _resolve_test_extraction_attrs(test_run):
    """
    Pre-resoud les attributs JSON de toutes les TestRunExtraction d'un test run.
    / Pre-resolve JSON attributes of all TestRunExtractions of a test run.
    """
    resolved_extractions = []
    for extraction in test_run.extractions.select_related('promoted_to_extraction').all():
        resolved_extractions.append(_build_resolved_dict(extraction))
    return resolved_extractions


# =============================================================================
# ViewSet pour les Questionnaire Prompts
# / ViewSet for Questionnaire Prompts
# =============================================================================

@method_decorator(csrf_exempt, name='dispatch')
class QuestionnairePromptViewSet(viewsets.ViewSet):
    """
    ViewSet pour gerer les prompts de questionnaire configurables.
    CRUD complet + actions pour les pieces de prompt.
    / ViewSet for managing configurable questionnaire prompts.
    Full CRUD + actions for prompt pieces.
    """

    permission_classes = [permissions.AllowAny]

    # ---- CRUD QuestionnairePrompt ----

    def list(self, request):
        """Liste des prompts questionnaire — retourne HTML partial pour sidebar."""
        tous_les_prompts_questionnaire = QuestionnairePrompt.objects.filter(is_active=True)
        return render(request, 'hypostasis_extractor/questionnaire_prompt_list.html', {
            'questionnaire_prompts': tous_les_prompts_questionnaire
        })

    def retrieve(self, request, pk=None):
        """
        Detail d'un prompt questionnaire.
        - Requete HTMX → retourne le partial editeur (zone-lecture)
        - Acces direct (F5, lien) → retourne la page complete base.html avec editeur pre-charge
        / Questionnaire prompt detail.
        - HTMX request → returns editor partial (zone-lecture)
        - Direct access (F5, link) → returns full base.html with pre-loaded editor
        """
        prompt_questionnaire = get_object_or_404(
            QuestionnairePrompt.objects.prefetch_related('pieces'),
            pk=pk
        )

        editor_context = {
            'prompt_questionnaire': prompt_questionnaire,
        }

        # Requete HTMX → partial seulement
        # / HTMX request → partial only
        if request.headers.get('HX-Request'):
            return render(request, 'hypostasis_extractor/questionnaire_editor.html', editor_context)

        # Acces direct (F5) → page complete avec editeur pre-charge
        # / Direct access (F5) → full page with pre-loaded editor
        return render(request, 'front/base.html', {
            'questionnaire_prompt_preloaded': prompt_questionnaire,
            **editor_context,
        })

    def create(self, request):
        """Creation d'un prompt questionnaire / Create a questionnaire prompt."""
        serializer = QuestionnairePromptCreateSerializer(data=request.data)
        if serializer.is_valid():
            nouveau_prompt_questionnaire = QuestionnairePrompt.objects.create(**serializer.validated_data)
            logger.info("QuestionnairePrompt cree: pk=%d name='%s'", nouveau_prompt_questionnaire.pk, nouveau_prompt_questionnaire.name)
            return render(request, 'hypostasis_extractor/includes/questionnaire_item.html', {
                'prompt_questionnaire': nouveau_prompt_questionnaire
            }, status=status.HTTP_201_CREATED)
        logger.warning("QuestionnairePrompt create: validation echouee — %s", serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request, pk=None):
        """Mise a jour partielle (auto-save) / Partial update (auto-save)."""
        prompt_questionnaire = get_object_or_404(QuestionnairePrompt, pk=pk)
        serializer = QuestionnairePromptUpdateSerializer(data=request.data)
        if serializer.is_valid():
            for nom_champ, valeur_champ in serializer.validated_data.items():
                setattr(prompt_questionnaire, nom_champ, valeur_champ)
            prompt_questionnaire.save()
            return _saved_response()
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, pk=None):
        """Suppression d'un prompt questionnaire / Delete a questionnaire prompt."""
        prompt_questionnaire = get_object_or_404(QuestionnairePrompt, pk=pk)
        logger.info("QuestionnairePrompt supprime: pk=%d name='%s'", prompt_questionnaire.pk, prompt_questionnaire.name)
        prompt_questionnaire.delete()
        # 200 au lieu de 204 : HTMX ignore le swap sur 204 No Content
        # / 200 instead of 204: HTMX ignores swap on 204 No Content
        return HttpResponse(status=200)

    # ---- Actions QuestionnairePromptPiece ----

    @action(detail=True, methods=['post'])
    def add_piece(self, request, pk=None):
        """Ajoute une piece de prompt questionnaire / Add a questionnaire prompt piece."""
        prompt_questionnaire = get_object_or_404(QuestionnairePrompt, pk=pk)
        serializer = QuestionnairePromptPieceCreateSerializer(data=request.data)
        if serializer.is_valid():
            nouvelle_piece = QuestionnairePromptPiece.objects.create(
                questionnaire_prompt=prompt_questionnaire, **serializer.validated_data
            )
            return render(request, 'hypostasis_extractor/includes/questionnaire_piece_row.html', {
                'piece': nouvelle_piece, 'prompt_questionnaire': prompt_questionnaire
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'])
    def update_piece(self, request, pk=None):
        """Mise a jour partielle d'une piece (auto-save) / Partial update."""
        get_object_or_404(QuestionnairePrompt, pk=pk)
        serializer = QuestionnairePromptPieceUpdateSerializer(data=request.data)
        if serializer.is_valid():
            piece_id = serializer.validated_data.pop('piece_id')
            piece_a_modifier = get_object_or_404(QuestionnairePromptPiece, pk=piece_id, questionnaire_prompt_id=pk)
            for nom_champ, valeur_champ in serializer.validated_data.items():
                setattr(piece_a_modifier, nom_champ, valeur_champ)
            piece_a_modifier.save()
            return _saved_response()
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['delete'], url_path='remove_piece')
    def delete_piece(self, request, pk=None):
        """Supprime une piece de prompt questionnaire / Delete a questionnaire prompt piece."""
        get_object_or_404(QuestionnairePrompt, pk=pk)
        piece_id = request.data.get('piece_id') or request.query_params.get('piece_id')
        piece_a_supprimer = get_object_or_404(QuestionnairePromptPiece, pk=piece_id, questionnaire_prompt_id=pk)
        piece_a_supprimer.delete()
        return HttpResponse(status=200)
