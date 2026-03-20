"""
ViewSet pour la Bibliotheque d'analyseurs (vue utilisateur, lecture seule) — PHASE-26b.
Permet aux utilisateurs authentifies de consulter les analyseurs et leurs prompts.
Les admins ont un lien vers l'editeur complet (/api/analyseurs/).
/ ViewSet for the Analyzer Library (user view, read-only) — PHASE-26b.

LOCALISATION : front/views_analyseurs.py
"""
import logging

from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from rest_framework import permissions, viewsets
from rest_framework.decorators import action

from hypostasis_extractor.models import (
    AnalyseurSyntaxique,
    ExtractionJob,
    PromptPiece,
)

logger = logging.getLogger(__name__)


class BibliothequeAnalyseursViewSet(viewsets.ViewSet):
    """
    Bibliotheque d'analyseurs en lecture seule pour les utilisateurs authentifies.
    Les admins ont un lien vers l'editeur complet (/api/analyseurs/).
    / Read-only analyzer library for authenticated users.

    LOCALISATION : front/views_analyseurs.py

    FLUX :
    - list() → grille de cartes dans zone-lecture
    - retrieve() → page detail du prompt dans zone-lecture
    - dashboard_couts() → tableau des couts staff-only
    """
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        """
        Grille de cartes des analyseurs actifs, avec filtre optionnel par type.
        Parametre GET : ?type=analyser|reformuler|restituer
        - Requete HTMX → partial bibliotheque_analyseurs.html dans zone-lecture
        - Acces direct (F5) → page complete base.html avec vue pre-chargee
        / Grid of active analyzer cards, with optional type filter.
        """
        # Filtre optionnel par type d'analyseur
        # / Optional filter by analyzer type
        type_filtre = request.query_params.get('type', '')
        tous_les_analyseurs_actifs = AnalyseurSyntaxique.objects.filter(is_active=True)
        if type_filtre in ('analyser', 'reformuler', 'restituer'):
            tous_les_analyseurs_actifs = tous_les_analyseurs_actifs.filter(
                type_analyseur=type_filtre,
            )

        # Annoter chaque analyseur avec le nombre d'exemples few-shot
        # / Annotate each analyzer with its few-shot example count
        tous_les_analyseurs_annotes = tous_les_analyseurs_actifs.annotate(
            nombre_exemples=Count('examples'),
        ).order_by('-updated_at')

        contexte_bibliotheque = {
            'analyseurs': tous_les_analyseurs_annotes,
            'type_filtre': type_filtre,
        }

        # Requete HTMX → partial seulement
        # / HTMX request → partial only
        if request.headers.get('HX-Request'):
            return render(request, 'front/includes/bibliotheque_analyseurs.html', contexte_bibliotheque)

        # Acces direct (F5) → page complete avec vue pre-chargee
        # / Direct access (F5) → full page with pre-loaded view
        return render(request, 'front/base.html', {
            'bibliotheque_analyseurs_preloaded': True,
            **contexte_bibliotheque,
        })

    def retrieve(self, request, pk=None):
        """
        Detail d'un analyseur en lecture seule : pieces du prompt, exemples, extractions.
        - Requete HTMX → partial detail_analyseur_readonly.html dans zone-lecture
        - Acces direct (F5) → page complete base.html avec vue pre-chargee
        / Analyzer detail (read-only): prompt pieces, examples, extractions.

        LOCALISATION : front/views_analyseurs.py
        """
        analyseur = get_object_or_404(AnalyseurSyntaxique, pk=pk)

        # Pieces du prompt ordonnees par leur position
        # / Prompt pieces ordered by position
        toutes_les_pieces_du_prompt = PromptPiece.objects.filter(
            analyseur=analyseur,
        ).order_by('order')

        # Exemples few-shot avec leurs extractions et attributs pre-charges
        # / Few-shot examples with prefetched extractions and attributes
        tous_les_exemples_few_shot = analyseur.examples.prefetch_related(
            'extractions__attributes',
        ).order_by('order')

        contexte_detail_analyseur = {
            'analyseur': analyseur,
            'pieces': toutes_les_pieces_du_prompt,
            'exemples': tous_les_exemples_few_shot,
        }

        # Requete HTMX → partial seulement
        # / HTMX request → partial only
        if request.headers.get('HX-Request'):
            return render(request, 'front/includes/detail_analyseur_readonly.html', contexte_detail_analyseur)

        # Acces direct (F5) → page complete avec vue pre-chargee
        # / Direct access (F5) → full page with pre-loaded view
        return render(request, 'front/base.html', {
            'detail_analyseur_preloaded': True,
            **contexte_detail_analyseur,
        })

    @action(detail=False, methods=['get'], url_path='dashboard-couts')
    def dashboard_couts(self, request):
        """
        Dashboard des couts reels par modele IA et par mois. Accessible au staff uniquement.
        Agrege les jobs d'extraction termines qui ont un cout reel enregistre.
        / Real cost dashboard by AI model and by month. Staff only.

        LOCALISATION : front/views_analyseurs.py
        """
        if not request.user.is_staff:
            return HttpResponse(
                '<div class="p-4 text-slate-500 text-sm">Accès réservé aux administrateurs.</div>',
                status=403,
            )

        from django.db.models.functions import TruncMonth
        from django.db.models import Sum, Count as DbCount

        # Agreger les couts par modele IA et par mois calendaire
        # / Aggregate costs by AI model and calendar month
        couts_agreges_par_mois = (
            ExtractionJob.objects.filter(
                status='completed',
                cout_reel_euros__isnull=False,
            )
            .annotate(mois=TruncMonth('created_at'))
            .values('mois', 'ai_model__model_name', 'ai_model__provider')
            .annotate(
                cout_total=Sum('cout_reel_euros'),
                tokens_input_total=Sum('tokens_input_reels'),
                tokens_output_total=Sum('tokens_output_reels'),
                nombre_jobs=DbCount('id'),
            )
            .order_by('-mois')
        )

        contexte_dashboard_couts = {
            'couts_par_mois': couts_agreges_par_mois,
        }

        # Requete HTMX → partial seulement
        # / HTMX request → partial only
        if request.headers.get('HX-Request'):
            return render(request, 'front/includes/dashboard_couts.html', contexte_dashboard_couts)

        # Acces direct (F5) → page complete
        # / Direct access (F5) → full page
        return render(request, 'front/base.html', {
            'dashboard_couts_preloaded': True,
            **contexte_dashboard_couts,
        })
