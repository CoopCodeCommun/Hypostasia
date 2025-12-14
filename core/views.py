from rest_framework.renderers import TemplateHTMLRenderer, JSONRenderer
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import render
from django.http import HttpResponse

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
        
        # Optimize query for template rendering
        if request.accepted_renderer.format == 'html':
            instance = Page.objects.prefetch_related(
                'blocks__arguments__comments__author',
                'blocks__themes',
                'blocks__reformulations'
            ).get(pk=instance.pk)
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
        page = Page.objects.prefetch_related(
            'blocks__arguments__comments__author',
            'blocks__themes',
            'blocks__reformulations'
        ).get(pk=page.pk)

        if request.headers.get('HX-Request'):
            response = Response(status=status.HTTP_200_OK)
            response['HX-Redirect'] = request.build_absolute_uri(f'/api/pages/{page.id}/')
            return response

        if request.accepted_renderer.format == 'html':
             # Fallback for non-HTMX HTML requests (e.g. form submit)
            return Response({'page': page}, template_name='core/includes/sidebar_items.html')

        return Response({
            "status": "success",
            "arguments_count": page.arguments.count()
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], renderer_classes=[TemplateHTMLRenderer])
    def sidebar(self, request, pk=None):
        """
        Renvoie le HTML complet de la sidebar pour l'extension.
        """
        page = self.get_object()
        return Response({'page': page}, template_name='core/includes/sidebar_items.html')




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


from .models import Page, Argument, Prompt, TextInput

# ... imports ...

class PromptViewSet(viewsets.ModelViewSet):
    """
    CRUD complet pour gérer les Prompts et leurs configurations.
    """
    queryset = Prompt.objects.all().order_by('-created_at')
    serializer_class = PromptSerializer
    renderer_classes = [JSONRenderer, TemplateHTMLRenderer]

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        if request.accepted_renderer.format == 'html':
            return Response({'prompts': queryset}, template_name='core/prompt_list.html')
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if request.accepted_renderer.format == 'html':
            from .models import AIModel
            aimodels = AIModel.objects.filter(is_active=True)
            return Response({'prompt': instance, 'aimodels': aimodels}, template_name='core/prompt_detail.html')
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], renderer_classes=[TemplateHTMLRenderer])
    def update_input(self, request, pk=None):
        """
        HTMX Action: Update a specific TextInput.
        Expects: input_id, role, name, content, order
        """
        prompt = self.get_object()
        input_id = request.data.get('input_id')
        text_input = TextInput.objects.get(pk=input_id, prompt=prompt)
        
        text_input.role = request.data.get('role', text_input.role)
        text_input.name = request.data.get('name', text_input.name)
        text_input.content = request.data.get('content', text_input.content)
        text_input.order = int(request.data.get('order', text_input.order))
        text_input.save()
        
        return Response({'input': text_input}, template_name='core/includes/text_input_card.html')

    @action(detail=True, methods=['post'], renderer_classes=[TemplateHTMLRenderer])
    def add_input(self, request, pk=None):
        """
        HTMX Action: Create a new TextInput for this prompt.
        """
        prompt = self.get_object()
        # Create with defaults
        from .models import Role
        new_order = prompt.inputs.count() + 1
        text_input = TextInput.objects.create(
            prompt=prompt,
            name="Nouveau bloc",
            role=Role.CONTEXT,
            content="",
            order=new_order
        )
        return Response({'input': text_input}, template_name='core/includes/text_input_card.html')

    @action(detail=True, methods=['post'], renderer_classes=[TemplateHTMLRenderer])
    def test_run(self, request, pk=None):
        """
        Run a real test with the prompt using core.services pipeline.
        """
        prompt = self.get_object()
        model_id = request.data.get('model')
        test_input = request.data.get('test_input') or "Texte de test par défaut."
        
        from .models import AIModel, Page, Provider
        from .services import build_full_prompt, dispatch_llm_request

        # Resolve Model
        if model_id == 'mock':
             # Create ephemeral mock model config
             ai_model = AIModel(name="Simulation (Mock)", provider=Provider.MOCK)
        else:
            try:
                ai_model = AIModel.objects.get(pk=model_id)
            except (AIModel.DoesNotExist, ValueError):
                # Fallback
                ai_model = AIModel(name="Simulation (Fallback)", provider=Provider.MOCK)

        # 1. Create Transient Page (Mocking the context)
        # We don't save it, just use it for the prompt builder
        mock_page = Page(text_readability=test_input)
        
        # 2. Build Full Prompt (Production Logic)
        full_prompt = build_full_prompt(mock_page, prompt)

        # 3. Dispatch (Production Logic)
        try:
            result_json_str = dispatch_llm_request(ai_model, full_prompt, page_context=mock_page)
            
            # Formating for display
            try:
                # Pretty print if JSON
                import json
                parsed = json.loads(result_json_str)
                result_display = json.dumps(parsed, indent=2, ensure_ascii=False)
            except:
                result_display = result_json_str

        except Exception as e:
            result_display = f"Erreur lors de l'appel IA: {str(e)}"
        
        return Response({
            'result': result_display, 
            'model': ai_model.name
        }, template_name='core/includes/prompt_test_result.html')


@csrf_exempt
def test_sidebar_view(request):
    """
    Vue de test pour l'extension Sidebar-First.
    Reçoit ?url=...
    Renvoie le HTML de la sidebar (soit vide si pas de page, soit les arguments).
    """
    url_param = request.GET.get('url')
    # Pour le test, on essaie de trouver la page
    # Attention: url_param peut contenir des encodages, on tente un lookup simple
    page = None
    if url_param:
        # On peut essayer de nettoyer l'url ou fitrer exact
        page = Page.objects.filter(url=url_param).first()
        if not page and url_param.endswith('/'):
             page = Page.objects.filter(url=url_param[:-1]).first()
    
    if page:
        return render(request, 'core/includes/sidebar_items.html', {'page': page})
    else:
        # Si pas de page, on affiche un message (et pourquoi pas un bouton pour créer ?)
        return HttpResponse(f"""
            <div style="padding: 20px; text-align: center;">
                <p>Aucune analyse trouvée pour cette URL.</p>
                <div style="margin-top:20px; color:#999; font-size:12px;">
                    URL: {url_param or 'Inconnue'}
                </div>
            </div>
        """)

