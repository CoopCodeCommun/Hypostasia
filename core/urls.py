from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import PageViewSet, SidebarViewSet

# Router DRF — ViewSets pour l'extension navigateur
# / DRF Router — ViewSets for the browser extension
router = DefaultRouter()
router.register(r"pages", PageViewSet, basename="page")
router.register(r"sidebar", SidebarViewSet, basename="sidebar")

urlpatterns = [
    path("", include(router.urls)),
]
