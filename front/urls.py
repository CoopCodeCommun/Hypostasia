from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views_alignement import AlignementViewSet
from .views_auth import AuthViewSet
from .views_corpus import BaseViewSet, CarnetViewSet, NoteCorpusViewSet
from .views_groupes import GroupeViewSet
from .views_invitation import InvitationViewSet
from .views_synthese import CitationViewSet, SyntheseViewSet, WikiViewSet
from hypostasis_extractor.views_element import ElementViewSet
from .views_taches import TachesViewSet

app_name = "front"

# Router DRF — genere automatiquement les URLs pour chaque ViewSet
# DRF Router — automatically generates URLs for each ViewSet
router = DefaultRouter(trailing_slash=True)
# La route `/arbre/` a ete retiree le 12 aout 2026 avec l'arbre lateral
# qu'elle servait : elle ne rendait qu'un gabarit du tiroir, lui-meme
# supprime. / The /arbre/ route went with the side tree it served.
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
router.register(r"carnets", CarnetViewSet, basename="carnet")
router.register(r"notes", NoteCorpusViewSet, basename="note-corpus")
router.register(r"bases", BaseViewSet, basename="base-de-connaissances")
# Couche synthese (§ 10, phase H) : wikis, syntheses dirigees, preuves.
# / Synthesis layer: wikis, frozen syntheses, evidence panels.
router.register(r"wikis", WikiViewSet, basename="wiki")
router.register(r"syntheses", SyntheseViewSet, basename="synthese")
router.register(r"citations", CitationViewSet, basename="citation")
# Les operations sur un element du moteur ELEMENT (BR-E) :
# corriger, scinder, fusionner_avec_le_suivant, masquer, demasquer.
# / ELEMENT-engine element operations (BR-E).
router.register(r"elements", ElementViewSet, basename="element")

urlpatterns = [
    # La page racine reste un path explicite (pas de pk, pas de CRUD)
    # Root page stays as explicit path (no pk, no CRUD)
    path("", views.BibliothequeViewSet.as_view({"get": "list"}), name="bibliotheque"),

    # Les collections carnet-niveau de la couche synthese (§ 10) : le
    # prefixe "carnets" appartient deja au CarnetViewSet, ces routes
    # explicites completent sans collision.
    # / Notebook-level synthesis collections, explicit paths.
    path(
        "carnets/<int:pk>/wikis/",
        WikiViewSet.as_view({
            "get": "lister_pour_le_carnet", "post": "creer_pour_le_carnet",
        }),
        name="wikis-du-carnet",
    ),
    path(
        "carnets/<int:pk>/syntheses/",
        SyntheseViewSet.as_view({
            "get": "lister_pour_le_carnet", "post": "creer_pour_le_carnet",
        }),
        name="syntheses-du-carnet",
    ),

    # Toutes les autres URLs sont gerees par le router
    # All other URLs are handled by the router
    path("", include(router.urls)),
]
