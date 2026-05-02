"""
ViewSet pour le bouton 'taches en cours' dans la toolbar (refonte A.6).
- bouton() : renvoie l'etat actuel du bouton (compteurs + couleur)
- dropdown() : renvoie la liste des 10 dernieres taches + OOB swap du bouton
- marquer_lue() : passe notification_lue=True sur un job
/ ViewSet for the 'tasks in progress' button in the toolbar (A.6 refactor).

LOCALISATION : front/views_taches.py
"""
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from rest_framework import permissions, viewsets
from rest_framework.decorators import action

from core.models import TranscriptionJob
from hypostasis_extractor.models import ExtractionJob


def _calculer_etat_bouton(user):
    """
    Calcule l'etat du bouton + les compteurs pour un utilisateur.
    Priorite : erreur > succes > en_cours > neutre.
    / Compute button state + counters for a user.
    Priority: erreur > succes > en_cours > neutre.

    LOCALISATION : front/views_taches.py
    """
    # Comptage taches en cours / Count tasks in progress
    nombre_extractions_en_cours = ExtractionJob.objects.filter(
        page__owner=user, status__in=["pending", "processing"],
    ).count()
    nombre_transcriptions_en_cours = TranscriptionJob.objects.filter(
        page__owner=user, status__in=["pending", "processing"],
    ).count()
    nombre_en_cours = nombre_extractions_en_cours + nombre_transcriptions_en_cours

    # Comptage taches terminees non lues / Count finished unread tasks
    nombre_extractions_non_lues = ExtractionJob.objects.filter(
        page__owner=user,
        status__in=["completed", "failed"],
        notification_lue=False,
    ).count()
    nombre_transcriptions_non_lues = TranscriptionJob.objects.filter(
        page__owner=user,
        status__in=["completed", "failed"],
        notification_lue=False,
    ).count()
    nombre_non_lues = nombre_extractions_non_lues + nombre_transcriptions_non_lues

    # Etat dominant : priorite erreur > succes > en_cours > neutre
    # / Dominant state: priority erreur > succes > en_cours > neutre
    a_des_erreurs_non_lues = ExtractionJob.objects.filter(
        page__owner=user, status="failed", notification_lue=False,
    ).exists() or TranscriptionJob.objects.filter(
        page__owner=user, status="failed", notification_lue=False,
    ).exists()

    if a_des_erreurs_non_lues:
        etat = "erreur"
    elif nombre_non_lues > 0:
        etat = "succes"
    elif nombre_en_cours > 0:
        etat = "en_cours"
    else:
        etat = "neutre"

    return {
        "nombre_en_cours": nombre_en_cours,
        "nombre_non_lues": nombre_non_lues,
        "etat": etat,
    }


class TachesViewSet(viewsets.ViewSet):
    """
    Bouton 'taches en cours' dans la toolbar + dropdown au clic + marquer lue.
    / 'Tasks in progress' button in toolbar + dropdown on click + mark as read.

    LOCALISATION : front/views_taches.py
    """
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["GET"])
    def bouton(self, request):
        """
        Renvoie le HTML du bouton avec son etat actuel (compteur, couleur).
        Appele en reaction a un message WS (via JS dans hypostasia.js).
        / Returns button HTML with current state.
        """
        contexte = _calculer_etat_bouton(request.user)
        return render(request, "front/includes/taches_bouton.html", contexte)

    @action(detail=False, methods=["GET"])
    def dropdown(self, request):
        """
        Renvoie la liste des 10 dernieres taches dans un dropdown
        + OOB swap du bouton pour realignement.
        / Returns 10 most recent tasks in a dropdown + OOB swap button.
        """
        # Taches recentes : 10 dernieres extractions + 10 dernieres transcriptions
        # melangees par created_at desc, max 10 au total
        # / Recent tasks: 10 latest extractions + 10 latest transcriptions
        # / merged by created_at desc, max 10 total
        extractions_recentes = list(ExtractionJob.objects.filter(
            page__owner=request.user,
        ).select_related("page").order_by("-created_at")[:10])

        transcriptions_recentes = list(TranscriptionJob.objects.filter(
            page__owner=request.user,
        ).select_related("page").order_by("-created_at")[:10])

        # Annoter le type pour le template / Annotate type for template
        for extraction in extractions_recentes:
            extraction.type_tache = "extraction"
        for transcription in transcriptions_recentes:
            transcription.type_tache = "transcription"

        # Fusionner et trier par date desc, garder 10
        # / Merge and sort by date desc, keep 10
        toutes_taches = sorted(
            extractions_recentes + transcriptions_recentes,
            key=lambda t: t.created_at,
            reverse=True,
        )[:10]

        contexte_bouton = _calculer_etat_bouton(request.user)

        return render(request, "front/includes/taches_dropdown.html", {
            "taches": toutes_taches,
            **contexte_bouton,
        })

    @action(detail=True, methods=["POST"], url_path="marquer-lue")
    def marquer_lue(self, request, pk=None):
        """
        Marque une notification comme lue. Pk = id du job.
        Le query param ?type=extraction|transcription distingue les 2 modeles.
        / Marks a notification as read. Pk = job id.

        LOCALISATION : front/views_taches.py
        """
        type_tache = request.query_params.get("type")
        if type_tache == "extraction":
            job = get_object_or_404(ExtractionJob, pk=pk, page__owner=request.user)
        elif type_tache == "transcription":
            job = get_object_or_404(TranscriptionJob, pk=pk, page__owner=request.user)
        else:
            return HttpResponse("Parametre type=extraction|transcription requis", status=400)

        job.notification_lue = True
        job.save(update_fields=["notification_lue"])
        return HttpResponse(status=204)
