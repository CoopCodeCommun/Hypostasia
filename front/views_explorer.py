"""
ViewSet pour la page Explorer (decouverte + curation + recherche) — PHASE-25d-v2.
/ ViewSet for the Explorer page (discovery + curation + search) — PHASE-25d-v2.

LOCALISATION : front/views_explorer.py

DEPENDENCIES :
- front.views._render_arbre (import local pour OOB swap arbre dans suivre/ne_plus_suivre)
- hypostasis_extractor.models.ExtractedEntity (pour la curation et la recherche document)
"""
import json
import logging

from django.core.paginator import Paginator
from django.db.models import Case, Count, Q, When
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils.html import escape as html_escape
from django.utils.safestring import mark_safe
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


def _extraire_snippet(texte_complet, terme_recherche, longueur_contexte=100):
    """
    Trouve la premiere occurrence du terme dans le texte et retourne
    un extrait avec contexte avant/apres + balise <mark> pour surlignage.
    / Finds the first occurrence of the search term and returns
    a snippet with surrounding context + <mark> tag for highlighting.

    LOCALISATION : front/views_explorer.py
    """
    if not texte_complet or not terme_recherche:
        return ""
    position = texte_complet.lower().find(terme_recherche.lower())
    if position == -1:
        # Pas de match direct — retourner le debut du texte
        # / No direct match — return the beginning of the text
        return html_escape(texte_complet[:200]) + "..."
    debut = max(0, position - longueur_contexte)
    fin = min(len(texte_complet), position + len(terme_recherche) + longueur_contexte)
    avant = html_escape(texte_complet[debut:position])
    mot = html_escape(texte_complet[position:position + len(terme_recherche)])
    apres = html_escape(texte_complet[position + len(terme_recherche):fin])
    prefixe = "..." if debut > 0 else ""
    suffixe = "..." if fin < len(texte_complet) else ""
    return mark_safe(f"{prefixe}{avant}<mark>{mot}</mark>{apres}{suffixe}")


class ExplorerViewSet(viewsets.ViewSet):
    """
    Page Explorer : navigation dossiers + recherche document + curation debats.
    Integre au layout principal via base.html (PHASE-25d-v2).
    Accessible aux anonymes et aux connectes.
    Superuser voit tous les dossiers (prives, partages, publics).
    / Explorer page: folder navigation + document search + debate curation.
    Integrated into the main layout via base.html (PHASE-25d-v2).
    Accessible to anonymous and authenticated users.
    Superuser sees all folders (private, shared, public).

    LOCALISATION : front/views_explorer.py
    """
    permission_classes = [permissions.AllowAny]

    # ─── Helpers privees ──────────────────────────────────────────────────

    def _get_liste_auteurs(self, request):
        """
        Recupere la liste des auteurs pour le filtre dropdown.
        Superuser : tous les auteurs. Autres : auteurs de dossiers publics uniquement.
        / Gets the authors list for the filter dropdown.
        Superuser: all authors. Others: authors of public folders only.

        LOCALISATION : front/views_explorer.py
        """
        # order_by obligatoire pour eviter que le Meta.ordering de Dossier pollue le DISTINCT
        # / order_by required to prevent Dossier Meta.ordering from polluting DISTINCT
        if request.user.is_authenticated and request.user.is_superuser:
            queryset_auteurs = Dossier.objects.filter(owner__isnull=False)
        else:
            queryset_auteurs = Dossier.objects.filter(
                visibilite=VisibiliteDossier.PUBLIC, owner__isnull=False,
            )
        return queryset_auteurs.values_list(
            "owner__pk", "owner__username",
        ).order_by("owner__username").distinct()

    def _get_ids_dossiers_suivis(self, request):
        """
        Recupere les IDs des dossiers suivis par l'utilisateur connecte.
        / Gets the IDs of folders followed by the logged-in user.

        LOCALISATION : front/views_explorer.py
        """
        if not request.user.is_authenticated:
            return set()
        return set(
            DossierSuivi.objects.filter(
                utilisateur=request.user,
            ).values_list("dossier_id", flat=True)
        )

    def _navigation_dossiers(self, request, filtres):
        """
        Mode navigation (champ recherche vide) : renvoie des dossiers avec curation.
        / Browse mode (empty search field): returns folders with curation.

        LOCALISATION : front/views_explorer.py

        FLUX :
        1. Construit queryset dossiers avec permissions (superuser/connecte/anonyme)
        2. Applique filtres (auteur, tri) et pagination
        3. Ajoute les donnees de curation (debats actifs, compteurs)
        """
        id_auteur = filtres.get("auteur")
        tri_choisi = filtres.get("tri", "recent")
        numero_page = filtres.get("page_num", 1)
        visibilite_filtre = filtres.get("visibilite", "")

        # Queryset de base avec annotations
        # / Base queryset with annotations
        queryset_dossiers = Dossier.objects.select_related("owner").annotate(
            nombre_pages=Count(
                "pages",
                filter=Q(pages__parent_page__isnull=True),
            ),
            nombre_suivis=Count("suivis"),
        )

        # Permissions : superuser voit tout sauf ses dossiers, connecte voit public hors ses dossiers, anonyme voit public
        # / Permissions: superuser sees all except own, logged-in sees public excluding own, anonymous sees public
        if request.user.is_authenticated and request.user.is_superuser:
            # Superuser : exclure ses propres dossiers + filtre optionnel par visibilite
            # / Superuser: exclude own folders + optional visibility filter
            queryset_dossiers = queryset_dossiers.exclude(owner=request.user)
            if visibilite_filtre:
                queryset_dossiers = queryset_dossiers.filter(visibilite=visibilite_filtre)
        elif request.user.is_authenticated:
            queryset_dossiers = queryset_dossiers.filter(
                visibilite=VisibiliteDossier.PUBLIC,
            ).exclude(owner=request.user)
        else:
            queryset_dossiers = queryset_dossiers.filter(
                visibilite=VisibiliteDossier.PUBLIC,
            )

        # Filtre par auteur
        # / Filter by author
        if id_auteur:
            queryset_dossiers = queryset_dossiers.filter(owner_id=id_auteur)

        # Tri selon le choix de l'utilisateur
        # / Sort according to user choice
        if tri_choisi == "populaire":
            queryset_dossiers = queryset_dossiers.order_by("-nombre_suivis", "-created_at")
        elif tri_choisi == "nom":
            queryset_dossiers = queryset_dossiers.order_by("name")
        else:
            queryset_dossiers = queryset_dossiers.order_by("-created_at")

        # Pagination (20 par page)
        # / Pagination (20 per page)
        paginateur = Paginator(queryset_dossiers, 20)
        page_courante = paginateur.get_page(numero_page)

        # Attacher les 3 premiers titres de pages pour le preview de chaque dossier
        # / Attach first 3 page titles as preview for each folder on the current page
        for dossier_item in page_courante:
            dossier_item.preview_pages = list(
                Page.objects.filter(
                    dossier=dossier_item, parent_page__isnull=True,
                ).values_list("title", flat=True)[:3]
            )

        # === Curation : extractions en debat (PHASE-25d-v2) ===
        # / === Curation: debated extractions (PHASE-25d-v2) ===
        from hypostasis_extractor.models import ExtractedEntity

        # Les 3 extractions les plus disputees (controverse > discute > discutable)
        # / Top 3 most debated extractions (controversial > discussed > debatable)
        extractions_en_debat = ExtractedEntity.objects.filter(
            job__page__dossier__visibilite=VisibiliteDossier.PUBLIC,
            job__status="completed",
            statut_debat__in=["controverse", "discute", "discutable"],
        ).select_related(
            "job__page", "job__page__dossier",
        ).order_by(
            Case(
                When(statut_debat="controverse", then=0),
                When(statut_debat="discute", then=1),
                When(statut_debat="discutable", then=2),
            ),
            "-job__created_at",
        )[:3]

        # Extractions sans commentaire (en attente d'avis)
        # Le related_name 'commentaires' pointe vers CommentaireExtraction (FK)
        # / Extractions without comments (awaiting opinions)
        # / The related_name 'commentaires' points to CommentaireExtraction (FK)
        extractions_sans_commentaire = ExtractedEntity.objects.filter(
            job__page__dossier__visibilite=VisibiliteDossier.PUBLIC,
            job__status="completed",
            statut_debat__in=["discutable", "discute"],
        ).annotate(
            nombre_commentaires=Count("commentaires"),
        ).filter(
            nombre_commentaires=0,
        ).select_related(
            "job__page", "job__page__dossier",
        ).order_by("-job__created_at")[:3]

        # Compteurs de statuts pour le bandeau
        # / Status counters for the banner
        compteurs_bruts = ExtractedEntity.objects.filter(
            job__page__dossier__visibilite=VisibiliteDossier.PUBLIC,
            job__status="completed",
        ).exclude(
            statut_debat__in=["nouveau", "non_pertinent"],
        ).values("statut_debat").annotate(
            nombre=Count("pk"),
        )
        compteurs_statuts = {
            item["statut_debat"]: item["nombre"]
            for item in compteurs_bruts
        }

        # Stats globales
        # / Global stats
        nombre_dossiers_publics = Dossier.objects.filter(
            visibilite=VisibiliteDossier.PUBLIC,
        ).count()
        nombre_documents_publics = Page.objects.filter(
            dossier__visibilite=VisibiliteDossier.PUBLIC,
            parent_page__isnull=True,
        ).count()
        nombre_total_extractions = ExtractedEntity.objects.filter(
            job__page__dossier__visibilite=VisibiliteDossier.PUBLIC,
            job__status="completed",
        ).count()

        return {
            "mode_recherche": False,
            "page_dossiers": page_courante,
            "ids_dossiers_suivis": self._get_ids_dossiers_suivis(request),
            "terme_recherche": "",
            "id_auteur_filtre": id_auteur,
            "tri_choisi": tri_choisi,
            "visibilite_filtre": visibilite_filtre,
            "tous_les_auteurs": self._get_liste_auteurs(request),
            "paginateur": paginateur,
            # Curation
            "extractions_en_debat": extractions_en_debat,
            "extractions_sans_commentaire": extractions_sans_commentaire,
            "compteurs_statuts": compteurs_statuts,
            "nombre_dossiers_publics": nombre_dossiers_publics,
            "nombre_documents_publics": nombre_documents_publics,
            "nombre_total_extractions": nombre_total_extractions,
        }

    def _recherche_documents(self, request, filtres, terme_recherche):
        """
        Mode recherche (champ recherche rempli) : renvoie des Pages avec snippets.
        / Search mode (filled search field): returns Pages with snippets.

        LOCALISATION : front/views_explorer.py

        FLUX :
        1. Construit queryset Pages avec permissions
        2. Filtre multi-champs (titre, contenu, mots-cles, resume, auteur)
        3. Attache snippet contextuel et metadata d'extraction a chaque resultat
        """
        from hypostasis_extractor.models import ExtractedEntity

        numero_page = filtres.get("page_num", 1)
        id_auteur = filtres.get("auteur")
        tri_choisi = filtres.get("tri", "recent")
        statut_filtre = filtres.get("statut", "")

        # Base queryset : pages racines dans des dossiers
        # / Base queryset: root pages in folders
        queryset_pages = Page.objects.filter(
            parent_page__isnull=True,
            dossier__isnull=False,
        ).select_related("dossier", "dossier__owner")

        # Permissions : superuser voit tout sauf ses docs, connecte voit public hors ses docs, anonyme voit public
        # / Permissions: superuser sees all except own, logged-in sees public excluding own, anonymous sees public
        if request.user.is_authenticated and request.user.is_superuser:
            queryset_pages = queryset_pages.exclude(dossier__owner=request.user)
        elif request.user.is_authenticated:
            queryset_pages = queryset_pages.filter(
                dossier__visibilite=VisibiliteDossier.PUBLIC,
            ).exclude(dossier__owner=request.user)
        else:
            queryset_pages = queryset_pages.filter(
                dossier__visibilite=VisibiliteDossier.PUBLIC,
            )

        # Recherche multi-champs avec Q() combine (seulement si terme non vide)
        # / Multi-field search with combined Q() (only if term is not empty)
        if terme_recherche:
            queryset_pages = queryset_pages.filter(
                Q(title__icontains=terme_recherche)
                | Q(text_readability__icontains=terme_recherche)
                | Q(dossier__name__icontains=terme_recherche)
                | Q(dossier__owner__username__icontains=terme_recherche)
                | Q(extraction_jobs__entities__attributes__mots_cles__icontains=terme_recherche)
                | Q(extraction_jobs__entities__attributes__resume__icontains=terme_recherche)
            ).distinct()

        # Filtre par auteur du dossier
        # / Filter by folder author
        if id_auteur:
            queryset_pages = queryset_pages.filter(dossier__owner_id=id_auteur)

        # Filtre par statut de debat (clic compteur curation)
        # / Filter by debate status (curation counter click)
        if statut_filtre:
            queryset_pages = queryset_pages.filter(
                extraction_jobs__entities__statut_debat=statut_filtre,
            ).distinct()

        # Tri
        # / Sort
        if tri_choisi == "nom":
            queryset_pages = queryset_pages.order_by("title")
        else:
            queryset_pages = queryset_pages.order_by("-dossier__created_at")

        # Pagination
        # / Pagination
        paginateur = Paginator(queryset_pages, 20)
        page_courante = paginateur.get_page(numero_page)

        # Generer snippet et metadata pour chaque resultat
        # / Generate snippet and metadata for each result
        for page_item in page_courante:
            page_item.snippet = _extraire_snippet(
                page_item.text_readability or "", terme_recherche,
            )
            # Recuperer les hypostases et mots-cles de la premiere extraction
            # / Get hypostases and keywords from the first extraction
            premiere_extraction = ExtractedEntity.objects.filter(
                job__page=page_item, job__status="completed",
            ).exclude(attributes={}).first()
            if premiere_extraction and premiere_extraction.attributes:
                page_item.mots_cles_preview = premiere_extraction.attributes.get("mots_cles", "")
                hypostases_brutes = premiere_extraction.attributes.get("hypostases", "")
                page_item.hypostases_preview = [
                    h.strip() for h in hypostases_brutes.split(",") if h.strip()
                ] if hypostases_brutes else []
            else:
                page_item.mots_cles_preview = ""
                page_item.hypostases_preview = []

        return {
            "mode_recherche": True,
            "page_documents": page_courante,
            "ids_dossiers_suivis": self._get_ids_dossiers_suivis(request),
            "terme_recherche": terme_recherche,
            "id_auteur_filtre": id_auteur,
            "tri_choisi": tri_choisi,
            "tous_les_auteurs": self._get_liste_auteurs(request),
            "paginateur": paginateur,
        }

    # ─── Actions publiques ────────────────────────────────────────────────

    def list(self, request):
        """
        Point d'entree Explorer : navigation dossiers OU recherche documents.
        Integre au layout principal via base.html (PHASE-25d-v2).
        / Explorer entry point: folder navigation OR document search.
        Integrated into the main layout via base.html (PHASE-25d-v2).

        LOCALISATION : front/views_explorer.py

        FLUX :
        1. Valide les filtres via ExplorerFiltresSerializer
        2. Si terme de recherche → mode recherche (documents avec snippets)
           Sinon → mode navigation (dossiers avec curation)
        3. Routage : HTMX interne → partial resultats,
           HTMX zone-lecture → partial complet, F5 → base.html avec flag
        """
        # Valider les filtres via serializer
        # / Validate filters via serializer
        serializer_filtres = ExplorerFiltresSerializer(data=request.GET)
        serializer_filtres.is_valid(raise_exception=True)
        filtres = serializer_filtres.validated_data

        terme_recherche = filtres.get("q", "").strip()
        statut_filtre = filtres.get("statut", "")

        # Double mode : recherche si terme ou statut, navigation sinon
        # / Dual mode: search if term or status, browse otherwise
        if terme_recherche or statut_filtre:
            contexte = self._recherche_documents(request, filtres, terme_recherche)
        else:
            contexte = self._navigation_dossiers(request, filtres)

        # Routage HTMX vs F5 (PHASE-25d-v2)
        # / HTMX vs F5 routing (PHASE-25d-v2)
        if request.headers.get("HX-Request"):
            cible_htmx = request.headers.get("HX-Target", "")
            if cible_htmx == "explorer-resultats":
                # Mise a jour des resultats seulement (filtre, tri, pagination)
                # / Update results only (filter, sort, pagination)
                return render(request, "front/includes/explorer_resultats.html", contexte)
            # Chargement du partial complet dans zone-lecture
            # / Load full partial into zone-lecture
            return render(request, "front/includes/explorer_contenu.html", contexte)

        # Acces direct (F5) → page complete avec Explorer pre-charge dans le layout
        # / Direct access (F5) → full page with Explorer pre-loaded in layout
        return render(request, "front/base.html", {
            "explorer_preloaded": True,
            **contexte,
        })

    @action(detail=True, methods=["GET"], url_path="preview")
    def preview(self, request, pk=None):
        """
        Retourne le partial HTML avec les 8 premieres pages d'un dossier.
        Chaque page affiche son titre et un extrait de text_readability.
        / Returns the HTML partial with the first 8 pages of a folder.
        Each page shows its title and a text_readability excerpt.

        LOCALISATION : front/views_explorer.py
        """
        dossier_a_previsualiser = get_object_or_404(Dossier, pk=pk)

        # Verifier les permissions d'acces (public ou superuser)
        # / Check access permissions (public or superuser)
        est_superuser = request.user.is_authenticated and request.user.is_superuser
        if not est_superuser and dossier_a_previsualiser.visibilite != VisibiliteDossier.PUBLIC:
            return HttpResponse("", status=403)

        # Recuperer les 8 premieres pages racines
        # / Retrieve first 8 root pages
        pages_du_dossier = Page.objects.filter(
            dossier=dossier_a_previsualiser,
            parent_page__isnull=True,
        ).order_by("title")[:8]

        nombre_total_pages = Page.objects.filter(
            dossier=dossier_a_previsualiser,
            parent_page__isnull=True,
        ).count()

        contexte_preview = {
            "dossier": dossier_a_previsualiser,
            "pages_preview": pages_du_dossier,
            "nombre_total_pages": nombre_total_pages,
            "nombre_pages_restantes": max(0, nombre_total_pages - 8),
        }
        return render(request, "front/includes/explorer_preview.html", contexte_preview)

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
