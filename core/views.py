from rest_framework.renderers import TemplateHTMLRenderer, JSONRenderer
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from .models import Page, Argument, Prompt
from .serializers import (
    PageListSerializer, PageDetailSerializer, PageCreateSerializer,
    ArgumentSerializer, ArgumentUpdateSerializer,
    ArgumentSerializer, ArgumentUpdateSerializer,
    PromptSerializer
)
import random
import re
from .services import run_analysis_pipeline



@method_decorator(csrf_exempt, name='dispatch')
class PageViewSet(viewsets.ModelViewSet):
    """
    Vue principale pour gérer les Pages.
    
    Actions standards :
    - list (GET) : Liste simple des pages
    - retrieve (GET) : Détail complet avec blocs
    - create (POST) : Création d'une page et extraction initiale
    
    Actions personnalisées :
    - analyze (POST) : Lancer le traitement IA
    - arguments (GET) : Récupérer les arguments liés à cette page
    """
    queryset = Page.objects.all().order_by('-created_at')
    renderer_classes = [JSONRenderer, TemplateHTMLRenderer]
    authentication_classes = []  # Disable DRF SessionAuth which enforces CSRF
    permission_classes = [permissions.AllowAny]

    def get_serializer_class(self):
        """Choix du sérialiseur selon l'action"""
        if self.action == 'create':
            return PageCreateSerializer
        elif self.action == 'retrieve':
            return PageDetailSerializer
        return PageListSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        
        # Simple URL filter if not using django-filter
        url_param = request.query_params.get('url')
        if url_param:
            queryset = queryset.filter(url=url_param)
            
        # If user asks for HTML, we serve the template
        if request.accepted_renderer.format == 'html':
            return Response({'pages': queryset}, template_name='core/page_list.html')
        # Otherwise standard JSON behavior
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if request.accepted_renderer.format == 'html':
            return Response({'page': instance}, template_name='core/page_detail.html')
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], renderer_classes=[JSONRenderer, TemplateHTMLRenderer])
    def analyze(self, request, pk=None):
        """
        [MOCK] Relance l'analyse IA de la page.
        """
        page = self.get_object()
        
        # [HTMX] State update (Mocking async behavior by doing it sync)
        # In a real app, we would set status='processing', return 202, and HTMX would poll.
        # Here we just block and return result.
        
        prompt_id = request.data.get('prompt_id')
        if prompt_id:
            prompt = Prompt.objects.filter(pk=prompt_id).first()
        else:
            prompt = Prompt.objects.filter(name="Analyse Standard Hypostasia").first()
            if not prompt:
                prompt = Prompt.objects.order_by('-created_at').first()
        
        if not prompt or (prompt and not prompt.default_model):
             # Simplify error handling for now -> return generic error or empty
             pass 

        run_analysis_pipeline(page, prompt)
        
        # Reload relation
        page = self.get_object()

        if request.accepted_renderer.format == 'html':
            return Response({'page': page}, template_name='core/partials/arguments_list.html')

        return Response({
            "status": "success",
            "arguments_count": page.arguments.count()
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], renderer_classes=[JSONRenderer])
    def arguments(self, request, pk=None):
        """
        Récupère directement la liste des arguments pour cette page.
        """
        page = self.get_object()
        arguments = page.arguments.all()
        serializer = ArgumentSerializer(arguments, many=True)
        return Response(serializer.data)


class ArgumentViewSet(viewsets.ModelViewSet):
    """
    Gestion des Arguments générés.
    
    L'utilisateur ne peut modifier que via 'partial_update' (PATCH) 
    pour changer le résumé ou la posture.
    """
    queryset = Argument.objects.all()
    serializer_class = ArgumentSerializer
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_serializer_class(self):
        if self.action in ['partial_update', 'update']:
            return ArgumentUpdateSerializer
        return ArgumentSerializer

    def filter_queryset(self, queryset):
        """Permet de filtrer par page_id dans l'URL ?page=12"""
        page_id = self.request.query_params.get('page')
        if page_id:
            return queryset.filter(page_id=page_id)
        return queryset


class PromptViewSet(viewsets.ModelViewSet):
    """
    CRUD complet pour gérer les Prompts et leurs configurations.
    """
    queryset = Prompt.objects.all().order_by('-created_at')
    serializer_class = PromptSerializer
