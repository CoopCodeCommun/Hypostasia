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

    # Etat dominant : priorite erreur > en_cours > succes > neutre
    # On veut voir 'en_cours' pendant qu'une tache tourne, meme s'il y a
    # des anciennes notifications non lues (ne pas les masquer mais les
    # reporter a la fin de la tache courante).
    # / Dominant state: priority erreur > en_cours > succes > neutre
    # / We want to see 'en_cours' while a task is running, even if there
    # / are unread old notifications (don't mask them but defer to end of
    # / current task).
    a_des_erreurs_non_lues = ExtractionJob.objects.filter(
        page__owner=user, status="failed", notification_lue=False,
    ).exists() or TranscriptionJob.objects.filter(
        page__owner=user, status="failed", notification_lue=False,
    ).exists()

    if a_des_erreurs_non_lues:
        etat = "erreur"
    elif nombre_en_cours > 0:
        etat = "en_cours"
    elif nombre_non_lues > 0:
        etat = "succes"
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
        Renvoie la liste des 30 dernieres taches dans un dropdown
        + OOB swap du bouton pour realignement.
        / Returns 30 most recent tasks in a dropdown + OOB swap button.
        """
        # Taches recentes : 30 dernieres extractions + 30 dernieres transcriptions
        # melangees par created_at desc, max 30 au total
        # / Recent tasks: 30 latest extractions + 30 latest transcriptions
        # / merged by created_at desc, max 30 total
        extractions_recentes = list(ExtractionJob.objects.filter(
            page__owner=request.user,
        ).select_related("page").order_by("-created_at")[:30])

        transcriptions_recentes = list(TranscriptionJob.objects.filter(
            page__owner=request.user,
        ).select_related("page").order_by("-created_at")[:30])

        # Annoter le type pour le template / Annotate type for template
        for extraction in extractions_recentes:
            extraction.type_tache = "extraction"
        for transcription in transcriptions_recentes:
            transcription.type_tache = "transcription"

        # Fusionner et trier par date desc, garder 30
        # / Merge and sort by date desc, keep 30
        toutes_taches = sorted(
            extractions_recentes + transcriptions_recentes,
            key=lambda t: t.created_at,
            reverse=True,
        )[:30]

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

    @action(detail=False, methods=["POST"], url_path="marquer-toutes-lues")
    def marquer_toutes_lues(self, request):
        """
        Marque TOUTES les notifications terminees du user comme lues.
        Refetch ensuite le dropdown frais + OOB swap du bouton (etat neutre).
        / Mark ALL user's finished notifications as read.
        Then refetch fresh dropdown + OOB swap of button (neutre state).

        LOCALISATION : front/views_taches.py
        """
        nombre_extractions = ExtractionJob.objects.filter(
            page__owner=request.user,
            status__in=["completed", "failed"],
            notification_lue=False,
        ).update(notification_lue=True)

        nombre_transcriptions = TranscriptionJob.objects.filter(
            page__owner=request.user,
            status__in=["completed", "failed"],
            notification_lue=False,
        ).update(notification_lue=True)

        # Renvoie le dropdown rafraichi (avec OOB swap du bouton inclus)
        # / Returns refreshed dropdown (with OOB button swap included)
        # Reutilise la logique de dropdown() / Reuses dropdown() logic
        return self.dropdown(request)
