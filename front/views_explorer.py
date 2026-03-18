"""
ViewSet pour la page Explorer (decouverte des dossiers publics) — PHASE-25d.
/ ViewSet for the Explorer page (public folder discovery) — PHASE-25d.

LOCALISATION : front/views_explorer.py
"""
import json
import logging

from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from rest_framework import permissions, viewsets
from rest_framework.decorators import action

from core.models import Dossier, DossierSuivi, Page, VisibiliteDossier
from .serializers import ExplorerFiltresSerializer

logger = logging.getLogger(__name__)


def _exiger_authentification(request):
    """
    Verifie que l'utilisateur est authentifie.
    Retourne None si OK, ou une reponse HTTP 403 / redirect si non connecte.
    / Checks user is authenticated.
    Returns None if OK, or an HTTP 403 response / redirect if not logged in.

    LOCALISATION : front/views_explorer.py
    """
    if request.user.is_authenticated:
        return None
    if request.headers.get("HX-Request"):
        return HttpResponse(
            '<p class="text-sm text-red-600 p-3">'
            'Connexion requise. <a href="/auth/login/" class="underline text-blue-600">Se connecter</a>'
            '</p>', status=403,
        )
    from django.shortcuts import redirect
    return redirect("/auth/login/")


class ExplorerViewSet(viewsets.ViewSet):
    """
    Page Explorer : liste paginee des dossiers publics avec recherche, filtres et tri.
    Accessible aux anonymes et aux connectes.
    Suivre/Ne plus suivre reserve aux connectes.
    / Explorer page: paginated list of public folders with search, filters and sorting.
    Accessible to anonymous and authenticated users.
    Follow/Unfollow restricted to authenticated users.

    LOCALISATION : front/views_explorer.py
    """
    permission_classes = [permissions.AllowAny]

    def list(self, request):
        """
        Liste les dossiers publics avec filtres optionnels (q, auteur, tri) et pagination.
        / Lists public folders with optional filters (q, auteur, tri) and pagination.

        LOCALISATION : front/views_explorer.py
        """
        # Valider les filtres via serializer
        # / Validate filters via serializer
        serializer_filtres = ExplorerFiltresSerializer(data=request.GET)
        serializer_filtres.is_valid(raise_exception=True)
        filtres = serializer_filtres.validated_data

        terme_recherche = filtres.get("q", "").strip()
        id_auteur = filtres.get("auteur")
        tri_choisi = filtres.get("tri", "recent")
        numero_page = filtres.get("page_num", 1)

        # Queryset de base : dossiers publics avec nombre de pages racines + nombre de suivis
        # / Base queryset: public folders with root page count + follow count
        queryset_dossiers_publics = Dossier.objects.filter(
            visibilite=VisibiliteDossier.PUBLIC,
        ).select_related("owner").annotate(
            nombre_pages=Count(
                "pages",
                filter=Q(pages__parent_page__isnull=True),
            ),
            nombre_suivis=Count("suivis"),
        )

        # Filtre par nom (recherche)
        # / Filter by name (search)
        if terme_recherche:
            queryset_dossiers_publics = queryset_dossiers_publics.filter(
                name__icontains=terme_recherche,
            )

        # Filtre par auteur
        # / Filter by author
        if id_auteur:
            queryset_dossiers_publics = queryset_dossiers_publics.filter(
                owner_id=id_auteur,
            )

        # Tri selon le choix de l'utilisateur
        # / Sort according to user choice
        if tri_choisi == "populaire":
            queryset_dossiers_publics = queryset_dossiers_publics.order_by(
                "-nombre_suivis", "-created_at",
            )
        elif tri_choisi == "nom":
            queryset_dossiers_publics = queryset_dossiers_publics.order_by("name")
        else:
            # Tri par defaut : plus recents en premier
            # / Default sort: most recent first
            queryset_dossiers_publics = queryset_dossiers_publics.order_by("-created_at")

        # Prefetch des 3 premiers titres de pages pour le preview
        # / Prefetch first 3 page titles for preview
        for dossier_item in queryset_dossiers_publics[:20]:
            dossier_item.preview_pages = list(
                Page.objects.filter(
                    dossier=dossier_item, parent_page__isnull=True,
                ).values_list("title", flat=True)[:3]
            )

        # Pagination (20 par page)
        # / Pagination (20 per page)
        paginateur = Paginator(queryset_dossiers_publics, 20)
        page_courante = paginateur.get_page(numero_page)

        # Attacher le preview des pages a chaque dossier de la page courante
        # / Attach page preview to each folder on the current page
        for dossier_item in page_courante:
            if not hasattr(dossier_item, "preview_pages"):
                dossier_item.preview_pages = list(
                    Page.objects.filter(
                        dossier=dossier_item, parent_page__isnull=True,
                    ).values_list("title", flat=True)[:3]
                )

        # Recuperer les IDs des dossiers suivis (connectes uniquement)
        # / Get IDs of followed folders (authenticated only)
        ids_dossiers_suivis = set()
        if request.user.is_authenticated:
            ids_dossiers_suivis = set(
                DossierSuivi.objects.filter(
                    utilisateur=request.user,
                ).values_list("dossier_id", flat=True)
            )

        # Recuperer la liste des auteurs pour le filtre dropdown
        # order_by obligatoire pour eviter que le Meta.ordering de Dossier pollue le DISTINCT
        # / Get authors list for filter dropdown
        # / order_by required to prevent Dossier Meta.ordering from polluting DISTINCT
        tous_les_auteurs_publics = Dossier.objects.filter(
            visibilite=VisibiliteDossier.PUBLIC,
            owner__isnull=False,
        ).values_list(
            "owner__pk", "owner__username",
        ).order_by("owner__username").distinct()

        contexte = {
            "page_dossiers": page_courante,
            "ids_dossiers_suivis": ids_dossiers_suivis,
            "terme_recherche": terme_recherche,
            "id_auteur_filtre": id_auteur,
            "tri_choisi": tri_choisi,
            "tous_les_auteurs": tous_les_auteurs_publics,
            "paginateur": paginateur,
        }

        # Si requete HTMX → partial resultats seulement
        # / If HTMX request → results partial only
        if request.headers.get("HX-Request"):
            return render(request, "front/includes/explorer_resultats.html", contexte)

        # Sinon → page complete avec Explorer pre-charge
        # / Otherwise → full page with Explorer pre-loaded
        return render(request, "front/includes/explorer_page.html", contexte)

    @action(detail=True, methods=["POST"], url_path="suivre")
    def suivre(self, request, pk=None):
        """
        Suivre un dossier public → cree DossierSuivi.
        Retourne la card mise a jour + OOB swap arbre + toast.
        / Follow a public folder → creates DossierSuivi.
        Returns updated card + OOB swap tree + toast.

        LOCALISATION : front/views_explorer.py

        DEPENDENCIES :
        - front.views._render_arbre (import local pour OOB swap arbre)
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus

        dossier_a_suivre = get_object_or_404(
            Dossier, pk=pk, visibilite=VisibiliteDossier.PUBLIC,
        )

        # Creer le suivi (ignore si deja existant)
        # / Create follow (ignore if already exists)
        DossierSuivi.objects.get_or_create(
            utilisateur=request.user,
            dossier=dossier_a_suivre,
        )

        # Retourner la card mise a jour avec bouton "Ne plus suivre"
        # / Return updated card with "Unfollow" button
        html_card = render(request, "front/includes/explorer_card.html", {
            "dossier": dossier_a_suivre,
            "est_suivi": True,
        }).content.decode()

        # OOB swap pour mettre a jour l'arbre
        # / OOB swap to update the tree
        from .views import _render_arbre
        reponse_arbre = _render_arbre(request)
        html_arbre = reponse_arbre.content.decode()
        html_oob_arbre = f'<div id="arbre" hx-swap-oob="innerHTML:#arbre">{html_arbre}</div>'

        # Reponse avec toast de confirmation
        # / Response with confirmation toast
        reponse = HttpResponse(html_card + html_oob_arbre)
        reponse["HX-Trigger"] = json.dumps({
            "showToast": {"message": f"Vous suivez « {dossier_a_suivre.name} »"},
        })
        return reponse

    @action(detail=True, methods=["POST"], url_path="ne-plus-suivre")
    def ne_plus_suivre(self, request, pk=None):
        """
        Ne plus suivre un dossier → supprime DossierSuivi.
        Retourne la card mise a jour + OOB swap arbre + toast.
        / Unfollow a folder → deletes DossierSuivi.
        Returns updated card + OOB swap tree + toast.

        LOCALISATION : front/views_explorer.py

        DEPENDENCIES :
        - front.views._render_arbre (import local pour OOB swap arbre)
        """
        refus = _exiger_authentification(request)
        if refus:
            return refus

        dossier_a_ne_plus_suivre = get_object_or_404(Dossier, pk=pk)
        nom_dossier_pour_toast = dossier_a_ne_plus_suivre.name

        # Supprimer le suivi / Delete follow
        DossierSuivi.objects.filter(
            utilisateur=request.user,
            dossier=dossier_a_ne_plus_suivre,
        ).delete()

        # Retourner la card mise a jour avec bouton "Suivre"
        # / Return updated card with "Follow" button
        html_card = render(request, "front/includes/explorer_card.html", {
            "dossier": dossier_a_ne_plus_suivre,
            "est_suivi": False,
        }).content.decode()

        # OOB swap pour mettre a jour l'arbre
        # / OOB swap to update the tree
        from .views import _render_arbre
        reponse_arbre = _render_arbre(request)
        html_arbre = reponse_arbre.content.decode()
        html_oob_arbre = f'<div id="arbre" hx-swap-oob="innerHTML:#arbre">{html_arbre}</div>'

        # Reponse avec toast de confirmation
        # / Response with confirmation toast
        reponse = HttpResponse(html_card + html_oob_arbre)
        reponse["HX-Trigger"] = json.dumps({
            "showToast": {"message": f"Vous ne suivez plus « {nom_dossier_pour_toast} »"},
        })
        return reponse
