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

    async def file_ingestion_modifiee(self, event):
        """
        Dit au client que la file d'ingestion a avance.
        / Tells the client the ingestion queue has moved.

        LOCALISATION : front/consumers.py

        POURQUOI UN SECOND TYPE DE MESSAGE

        Le menu des taches affiche une position dans la file (« 3ᵉ dans
        la file »). Quand l'ingestion de QUELQU'UN D'AUTRE se termine,
        cette position change sans que rien ne se soit passe chez le
        destinataire : il faut donc le lui dire.

        Ce n'est PAS un `tache_terminee` : aucune tache de ce
        destinataire ne s'est terminee. Reutiliser l'autre message
        marcherait aujourd'hui — le client se contente de rafraichir —
        et deviendrait un mensonge le jour ou il affichera « Tache
        terminee » en clair. Le message ne porte donc aucune donnee :
        il dit « va relire », rien de plus.
        / Not a tache_terminee: nothing of this recipient's finished.
        Carries no payload — it only says "go re-read".
        """
        await self.send_json({"type": "file_ingestion_modifiee"})
