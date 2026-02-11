"""
URL routing pour l'application Hypostasis Extractor.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'extraction-jobs', views.ExtractionJobViewSet, basename='extraction-job')
router.register(r'extracted-entities', views.ExtractedEntityViewSet, basename='extracted-entity')
router.register(r'extraction-examples', views.ExtractionExampleViewSet, basename='extraction-example')
router.register(r'analyseurs', views.AnalyseurSyntaxiqueViewSet, basename='analyseur')

urlpatterns = [
    path('', include(router.urls)),
]
