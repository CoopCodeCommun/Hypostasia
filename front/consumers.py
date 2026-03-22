"""
Consumers WebSocket de l'app front.
Gere les notifications utilisateur et le suivi de progression des taches Celery.
/ WebSocket consumers for the front app.
Handles user notifications and Celery task progress tracking.
"""

import logging
import time

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    """
    Consumer WebSocket pour les notifications globales d'un utilisateur.
    Chaque utilisateur connecte rejoins son groupe personnel.
    / WebSocket consumer for global user notifications.
    Each connected user joins their personal group.
    """

    async def connect(self):
        """
        Connexion : ajoute le channel au groupe de l'utilisateur.
        Refuse la connexion si l'utilisateur n'est pas authentifie.
        / Connection: adds the channel to the user's group.
        Refuses connection if the user is not authenticated.
        """
        utilisateur_connecte = self.scope.get('user')

        # Refuser les connexions anonymes
        # / Reject anonymous connections
        if not utilisateur_connecte or not utilisateur_connecte.is_authenticated:
            logger.warning("NotificationConsumer: connexion refusee — utilisateur non authentifie")
            await self.close()
            return

        # Nom du groupe basé sur l'identifiant utilisateur
        # / Group name based on user identifier
        self.nom_groupe_utilisateur = f"notifications_user_{utilisateur_connecte.pk}"

        # Rejoindre le groupe personnel de l'utilisateur
        # / Join the user's personal group
        await self.channel_layer.group_add(
            self.nom_groupe_utilisateur,
            self.channel_name,
        )

        await self.accept()

        logger.debug(
            "NotificationConsumer: connexion acceptee user=%s groupe=%s",
            utilisateur_connecte.pk, self.nom_groupe_utilisateur,
        )

    async def disconnect(self, code_fermeture):
        """
        Deconnexion : retire le channel du groupe de l'utilisateur.
        / Disconnection: removes the channel from the user's group.
        """
        nom_groupe = getattr(self, 'nom_groupe_utilisateur', None)
        if nom_groupe:
            await self.channel_layer.group_discard(
                nom_groupe,
                self.channel_name,
            )
            logger.debug(
                "NotificationConsumer: deconnexion code=%s groupe=%s",
                code_fermeture, nom_groupe,
            )

    async def notification(self, evenement):
        """
        Handler pour les messages de type 'notification' envoyes au groupe.
        Rend le template ws_toast.html et envoie le HTML au client via WebSocket.
        HTMX (htmx-ext-ws) receptionne le HTML et applique l'OOB swap sur #ws-toasts.
        / Handler for 'notification' type messages sent to the group.
        Renders ws_toast.html and sends HTML to the client via WebSocket.
        HTMX (htmx-ext-ws) receives the HTML and applies OOB swap on #ws-toasts.
        """
        contexte_toast = {
            'niveau': evenement.get('niveau', 'info'),
            'titre': evenement.get('titre', ''),
            'message': evenement.get('message', ''),
        }

        # render_to_string est synchrone — on l'enveloppe dans sync_to_async
        # / render_to_string is synchronous — wrap it in sync_to_async
        html_toast = await sync_to_async(render_to_string)(
            'front/includes/ws_toast.html',
            contexte_toast,
        )

        await self.send(text_data=html_toast)

    async def analyse_progression(self, evenement):
        """
        Handler pour les messages de type 'analyse_progression' envoyes par la tache Celery.
        Met a jour la barre de progression dans le panneau E (OOB sur #barre-progression-analyse).
        Envoye a chaque debut de morceau LangExtract.
        / Handler for 'analyse_progression' messages sent by the Celery task.
        / Updates the progress bar in the E panel (OOB on #barre-progression-analyse).
        / Sent at the start of each LangExtract chunk.
        """
        message_progression = evenement.get('message', '')
        contexte_progression = {
            'pourcentage': evenement.get('pourcentage', 0),
            'message': message_progression,
            'chunk_courant': evenement.get('chunk_courant', 0),
            'chunks_total': evenement.get('chunks_total', 0),
            'has_warning': '—' in message_progression and len(message_progression) > 30,
        }

        html_progression = await sync_to_async(render_to_string)(
            'front/includes/ws_analyse_progression.html',
            contexte_progression,
        )

        await self.send(text_data=html_progression)

    async def analyse_terminee(self, evenement):
        """
        Signal de fin d'analyse (succes ou erreur).
        Envoie un div OOB avec hx-get + hx-trigger="load" qui force HTMX
        a recharger le drawer depuis analyse_status.
        Pas de requete DB ni de rendu HTML dans le consumer.
        / Analysis complete signal (success or error).
        / Sends OOB div with hx-get + hx-trigger="load" that forces HTMX
        / to reload the drawer from analyse_status.
        / No DB queries or HTML rendering in the consumer.

        LOCALISATION : front/consumers.py

        COMMUNICATION :
        Recoit : message 'analyse_terminee' depuis front/tasks.py (analyser_page_task)
        Emet : OOB div avec hx-get auto-load → analyse_status → drawer final
        """
        page_id = evenement.get('page_id')
        if not page_id:
            return

        # Un div OOB avec hx-get + hx-trigger="load" declenche automatiquement
        # un rechargement HTMX du drawer des qu'il est injecte dans le DOM.
        # / An OOB div with hx-get + hx-trigger="load" automatically triggers
        # / an HTMX reload of the drawer as soon as it's injected into the DOM.
        html_signal = (
            f'<div id="signal-rafraichir-drawer" '
            f'hx-swap-oob="innerHTML:#signal-rafraichir-drawer" '
            f'data-page-id="{page_id}">'
            f'<div hx-get="/lire/{page_id}/analyse_status/" '
            f'hx-target="#drawer-contenu" hx-swap="innerHTML" '
            f'hx-trigger="load"></div>'
            f'</div>'
        )
        await self.send(text_data=html_signal)

    async def rafraichir_drawer(self, evenement):
        """
        Signal leger via OOB swap sur un div cache.
        Injecte un div avec hx-get + hx-trigger="load" qui declenche
        automatiquement un rechargement HTMX du drawer via analyse_status.
        Pas de requete DB ni de rendu HTML dans le consumer.
        / Lightweight signal via OOB swap on a hidden div.
        / Injects a div with hx-get + hx-trigger="load" that automatically
        / triggers an HTMX reload of the drawer via analyse_status.
        / No DB queries or HTML rendering in the consumer.

        LOCALISATION : front/consumers.py

        COMMUNICATION :
        Recoit : message 'rafraichir_drawer' depuis front/tasks.py (callback_extraction_chunk)
        Emet : OOB div avec hx-get auto-load → analyse_status → drawer mis a jour
        """
        page_id = evenement.get('page_id')
        if not page_id:
            return

        # Un div OOB avec hx-get + hx-trigger="load" declenche automatiquement
        # un rechargement des cartes (sans ecraser le bandeau de progression).
        # Cible #drawer-cartes-liste au lieu de #drawer-contenu.
        # / An OOB div with hx-get + hx-trigger="load" automatically triggers
        # / a card reload (without overwriting the progress banner).
        # / Targets #drawer-cartes-liste instead of #drawer-contenu.
        html_signal = (
            f'<div id="signal-rafraichir-drawer" '
            f'hx-swap-oob="innerHTML:#signal-rafraichir-drawer" '
            f'data-page-id="{page_id}">'
            f'<div hx-get="/lire/{page_id}/analyse_status/?cartes_only=1" '
            f'hx-target="#drawer-cartes-liste" hx-swap="innerHTML" '
            f'hx-trigger="load"></div>'
            f'</div>'
        )
        await self.send(text_data=html_signal)


class ProgressionTacheConsumer(AsyncJsonWebsocketConsumer):
    """
    Consumer WebSocket pour le suivi de progression d'une tache Celery specifique.
    L'identifiant de la tache est passe dans l'URL : /ws/tache/<tache_id>/
    / WebSocket consumer for tracking the progress of a specific Celery task.
    The task identifier is passed in the URL: /ws/tache/<tache_id>/
    """

    async def connect(self):
        """
        Connexion : ajoute le channel au groupe de la tache.
        Refuse les connexions anonymes.
        / Connection: adds the channel to the task's group.
        Refuses anonymous connections.
        """
        utilisateur_connecte = self.scope.get('user')

        # Refuser les connexions anonymes
        # / Reject anonymous connections
        if not utilisateur_connecte or not utilisateur_connecte.is_authenticated:
            logger.warning("ProgressionTacheConsumer: connexion refusee — utilisateur non authentifie")
            await self.close()
            return

        # Recuperer l'identifiant de la tache depuis les parametres d'URL
        # / Retrieve the task identifier from URL parameters
        self.identifiant_tache = self.scope['url_route']['kwargs']['tache_id']
        self.nom_groupe_tache = f"tache_{self.identifiant_tache}"

        # Rejoindre le groupe de la tache
        # / Join the task's group
        await self.channel_layer.group_add(
            self.nom_groupe_tache,
            self.channel_name,
        )

        await self.accept()

        logger.debug(
            "ProgressionTacheConsumer: connexion acceptee user=%s tache=%s groupe=%s",
            utilisateur_connecte.pk, self.identifiant_tache, self.nom_groupe_tache,
        )

    async def disconnect(self, code_fermeture):
        """
        Deconnexion : retire le channel du groupe de la tache.
        / Disconnection: removes the channel from the task's group.
        """
        nom_groupe = getattr(self, 'nom_groupe_tache', None)
        if nom_groupe:
            await self.channel_layer.group_discard(
                nom_groupe,
                self.channel_name,
            )
            logger.debug(
                "ProgressionTacheConsumer: deconnexion code=%s tache=%s",
                code_fermeture, self.identifiant_tache,
            )

    async def progression(self, evenement):
        """
        Handler pour les messages de type 'progression' envoyes par Celery.
        Rend le template ws_progression_tache.html et envoie le HTML via WebSocket.
        HTMX (htmx-ext-ws) applique l'OOB swap sur #progression-tache.
        / Handler for 'progression' type messages sent by Celery.
        Renders ws_progression_tache.html and sends HTML via WebSocket.
        HTMX (htmx-ext-ws) applies OOB swap on #progression-tache.
        """
        contexte_progression = {
            'type': 'progression',
            'pourcentage': evenement.get('pourcentage', 0),
            'message': evenement.get('message', ''),
            'status': evenement.get('status', 'en_cours'),
        }

        # render_to_string est synchrone — on l'enveloppe dans sync_to_async
        # / render_to_string is synchronous — wrap it in sync_to_async
        html_progression = await sync_to_async(render_to_string)(
            'front/includes/ws_progression_tache.html',
            contexte_progression,
        )

        await self.send(text_data=html_progression)

    async def terminee(self, evenement):
        """
        Handler pour les messages de type 'terminee' envoyes par Celery.
        Rend le template ws_progression_tache.html avec le statut final,
        envoie le HTML au client, puis ferme la connexion.
        / Handler for 'terminee' type messages sent by Celery.
        Renders ws_progression_tache.html with the final status,
        sends HTML to the client, then closes the connection.
        """
        contexte_fin = {
            'type': 'terminee',
            'status': evenement.get('status', 'completed'),
            'message': evenement.get('message', ''),
            'pourcentage': 100 if evenement.get('status') == 'completed' else 0,
        }

        # render_to_string est synchrone — on l'enveloppe dans sync_to_async
        # / render_to_string is synchronous — wrap it in sync_to_async
        html_fin = await sync_to_async(render_to_string)(
            'front/includes/ws_progression_tache.html',
            contexte_fin,
        )

        await self.send(text_data=html_fin)

        # Fermer la connexion proprement apres le resultat final
        # / Close the connection cleanly after the final result
        await self.close()
