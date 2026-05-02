from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views_alignement import AlignementViewSet
from .views_auth import AuthViewSet
from .views_groupes import GroupeViewSet
from .views_invitation import InvitationViewSet
from .views_taches import TachesViewSet

app_name = "front"

# Router DRF — genere automatiquement les URLs pour chaque ViewSet
# DRF Router — automatically generates URLs for each ViewSet
router = DefaultRouter(trailing_slash=True)
router.register(r"arbre", views.ArbreViewSet, basename="arbre")
router.register(r"lire", views.LectureViewSet, basename="lire")
router.register(r"dossiers", views.DossierViewSet, basename="dossier")
router.register(r"pages", views.PageViewSet, basename="page")
router.register(r"extractions", views.ExtractionViewSet, basename="extraction")
router.register(r"config-ia", views.ConfigurationIAViewSet, basename="config-ia")
router.register(r"import", views.ImportViewSet, basename="import")
router.register(r"questionnaire", views.QuestionnaireViewSet, basename="questionnaire")
router.register(r"alignement", AlignementViewSet, basename="alignement")
router.register(r"auth", AuthViewSet, basename="auth")
router.register(r"groupes", GroupeViewSet, basename="groupe")
router.register(r"invitation", InvitationViewSet, basename="invitation")
router.register(r"taches", TachesViewSet, basename="tache")

urlpatterns = [
    # La page racine reste un path explicite (pas de pk, pas de CRUD)
    # Root page stays as explicit path (no pk, no CRUD)
    path("", views.BibliothequeViewSet.as_view({"get": "list"}), name="bibliotheque"),

    # Toutes les autres URLs sont gerees par le router
    # All other URLs are handled by the router
    path("", include(router.urls)),
]
