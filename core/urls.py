from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PageViewSet, ArgumentViewSet, PromptViewSet
from . import views

router = DefaultRouter()
router.register(r'pages', PageViewSet)
router.register(r'arguments', ArgumentViewSet)
router.register(r'prompts', PromptViewSet)

urlpatterns = [
    path('test-sidebar/', views.test_sidebar_view, name='test_sidebar'),
    path('', include(router.urls)),
]
