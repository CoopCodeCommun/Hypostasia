from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PageViewSet, ArgumentViewSet, PromptViewSet

router = DefaultRouter()
router.register(r'pages', PageViewSet)
router.register(r'arguments', ArgumentViewSet)
router.register(r'prompts', PromptViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
