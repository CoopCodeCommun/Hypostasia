"""
Consumer WebSocket pour notifications de fin de tache.
Refonte A.6 : un seul consumer minimal, pas de progression streaming.
/ WebSocket consumer for task-end notifications.
A.6 refactor: single minimal consumer, no progression streaming.

LOCALISATION : front/consumers.py
"""
from channels.generic.websocket import AsyncJsonWebsocketConsumer


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    """
    Consumer minimal : ecoute le group user_<id> et pousse les notifications
    de fin de tache au bouton du client (changement de couleur).
    / Minimal consumer: listens on user_<id> group and pushes task-end
    notifications to the client's button (color change).
    """
    async def connect(self):
        # Refus si non authentifie / Refuse if not authenticated
        if not self.scope["user"].is_authenticated:
            await self.close()
            return
        # Rejoindre le group du proprietaire / Join owner's group
        self.nom_group = f"user_{self.scope['user'].pk}"
        await self.channel_layer.group_add(self.nom_group, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "nom_group"):
            await self.channel_layer.group_discard(
                self.nom_group, self.channel_name,
            )

    async def tache_terminee(self, event):
        """
        Recoit un message du group, pousse au client.
        Format event : {tache_id, tache_type, status}
        / Receives a group message, pushes to client.
        """
        await self.send_json({
            "type": "tache_terminee",
            "tache_id": event["tache_id"],
            "tache_type": event["tache_type"],
            "status": event["status"],
        })
