"""
Vues WebSocket utilitaires pour l'app front.
Actuellement : endpoint de test pour envoyer une notification WS a l'utilisateur courant.
/ WebSocket utility views for the front app.
Currently: test endpoint to send a WS notification to the current user.
"""

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.shortcuts import render
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework import viewsets

logger = logging.getLogger(__name__)


class NotificationTestSerializer(serializers.Serializer):
    """
    Serializer pour valider les donnees du endpoint de test de notification WS.
    / Serializer to validate data for the WS notification test endpoint.
    """
    message = serializers.CharField(max_length=500)
    titre = serializers.CharField(max_length=100, required=False, default='')
    niveau = serializers.ChoiceField(
        choices=['info', 'succes', 'avertissement', 'erreur'],
        default='info',
    )


@method_decorator(login_required, name='dispatch')
class WsTestViewSet(viewsets.ViewSet):
    """
    ViewSet de test pour les notifications WebSocket.
    Permet d'envoyer une notification WS a l'utilisateur courant via un POST.
    / Test ViewSet for WebSocket notifications.
    Allows sending a WS notification to the current user via POST.
    """

    @action(detail=False, methods=['post'])
    def notifier(self, request):
        """
        Envoie une notification WebSocket a l'utilisateur courant.
        Le message est pushed au groupe notifications_user_{id} via le channel layer.
        / Sends a WebSocket notification to the current user.
        The message is pushed to the notifications_user_{id} group via channel layer.
        """
        serializer = NotificationTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        donnees_validees = serializer.validated_data

        # Construire le nom du groupe de notification de l'utilisateur
        # / Build the notification group name for the user
        nom_groupe_utilisateur = f"notifications_user_{request.user.pk}"

        # Envoyer la notification au channel layer
        # / Send the notification to the channel layer
        couche_channels = get_channel_layer()
        if couche_channels is None:
            logger.error("WsTestViewSet.notifier: channel layer non configure")
            return render(
                request,
                'front/includes/ws_test_feedback.html',
                {
                    'succes': False,
                    'message_feedback': 'Channel layer non configuré.',
                },
                status=503,
            )

        async_to_sync(couche_channels.group_send)(
            nom_groupe_utilisateur,
            {
                'type': 'notification',
                'niveau': donnees_validees['niveau'],
                'titre': donnees_validees['titre'],
                'message': donnees_validees['message'],
            },
        )

        logger.info(
            "WsTestViewSet.notifier: notification envoyee user=%s niveau=%s",
            request.user.pk, donnees_validees['niveau'],
        )

        # Retourne un feedback HTML minimal via template pour HTMX
        # / Return minimal HTML feedback via template for HTMX
        return render(
            request,
            'front/includes/ws_test_feedback.html',
            {
                'succes': True,
                'niveau': donnees_validees['niveau'],
            },
        )
