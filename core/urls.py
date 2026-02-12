from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views
from .views import PageViewSet

# Router DRF — uniquement le ViewSet Pages pour l'extension navigateur
# / DRF Router — only the Pages ViewSet for the browser extension
router = DefaultRouter()
router.register(r"pages", PageViewSet, basename="page")

urlpatterns = [
    # Vue de test pour la sidebar de l'extension navigateur
    # / Test view for the browser extension sidebar
    path("test-sidebar/", views.test_sidebar_view, name="test_sidebar"),
    path("", include(router.urls)),
]
