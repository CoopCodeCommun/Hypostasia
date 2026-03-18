"""
Consumers WebSocket de l'app front.
Gere les notifications utilisateur et le suivi de progression des taches Celery.
/ WebSocket consumers for the front app.
Handles user notifications and Celery task progress tracking.
"""

import logging

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
        contexte_progression = {
            'pourcentage': evenement.get('pourcentage', 0),
            'message': evenement.get('message', ''),
            'chunk_courant': evenement.get('chunk_courant', 0),
            'chunks_total': evenement.get('chunks_total', 0),
        }

        html_progression = await sync_to_async(render_to_string)(
            'front/includes/ws_analyse_progression.html',
            contexte_progression,
        )

        await self.send(text_data=html_progression)

    async def analyse_terminee(self, evenement):
        """
        Handler pour les messages de type 'analyse_terminee' envoyes par la tache Celery.
        Envoie un fragment OOB qui declenche automatiquement le chargement du drawer final.
        Le fragment contient un div invisible avec hx-get + hx-trigger="load" :
        HTMX le traite automatiquement et fait le GET vers analyse_status,
        qui retourne le drawer complet (etat 4) en OOB sur #drawer-contenu.
        / Handler for 'analyse_terminee' messages sent by the Celery task.
        / Sends an OOB fragment that automatically triggers loading the final drawer.
        / The fragment contains an invisible div with hx-get + hx-trigger="load":
        / HTMX processes it and GETs analyse_status, which returns the full drawer (state 4)
        / via OOB on #drawer-contenu.
        """
        page_id = evenement.get('page_id')
        if not page_id:
            return

        # Fragment OOB insere dans #barre-progression-analyse.
        # Le div avec hx-trigger="load" declenche immediatement un GET vers analyse_status.
        # analyse_status detecte le job completed et retourne le drawer final en OOB.
        # / OOB fragment inserted into #barre-progression-analyse.
        # / The div with hx-trigger="load" immediately triggers a GET to analyse_status.
        # / analyse_status detects the completed job and returns the final drawer via OOB.
        html_declencheur = (
            '<div id="barre-progression-analyse" hx-swap-oob="innerHTML">'
            f'<div hx-get="/lire/{page_id}/analyse_status/"'
            ' hx-trigger="load"'
            ' hx-target="#drawer-contenu"'
            ' hx-swap="innerHTML">'
            '<p class="text-xs text-emerald-600 text-center py-2">Analyse terminée, chargement…</p>'
            '</div>'
            '</div>'
        )

        await self.send(text_data=html_declencheur)

    async def extraction_carte(self, evenement):
        """
        Handler pour les messages de type 'extraction_carte' envoyes par la tache Celery.
        Envoie un message WebSocket unique contenant deux fragments OOB :
        1. La carte d'extraction → ajoutee dans #streaming-extractions (panneau E)
        2. Le texte annote avec toutes les entites du job → remplace #readability-content

        Le navigateur reste sur le texte pendant l'analyse. Les surlignages apparaissent
        progressivement a chaque nouvelle extraction.

        / Handler for 'extraction_carte' messages sent by the Celery task.
        / Sends a single WebSocket message containing two OOB fragments:
        / 1. Extraction card → appended to #streaming-extractions (E panel)
        / 2. Annotated text with all job entities → replaces #readability-content
        / The browser stays on the text during analysis. Highlights appear progressively.
        """
        entite_pk = evenement.get('entite_pk')
        if not entite_pk:
            logger.warning("extraction_carte: entite_pk manquant dans l'evenement")
            return

        # Import local pour eviter la circularite au chargement du module
        # / Local import to avoid circular dependency at module load
        from hypostasis_extractor.models import ExtractedEntity
        from front.utils import annoter_html_avec_barres

        # Recuperer l'entite avec son job et sa page
        # / Fetch the entity with its job and page
        try:
            entite = await sync_to_async(
                ExtractedEntity.objects.select_related('job__page').get
            )(pk=entite_pk)
        except ExtractedEntity.DoesNotExist:
            logger.warning("extraction_carte: entite pk=%s introuvable", entite_pk)
            return

        # Charger toutes les entites du job jusqu'ici pour annoter le texte complet
        # / Load all job entities so far to annotate the full text
        toutes_les_entites_du_job = await sync_to_async(list)(
            ExtractedEntity.objects.filter(job=entite.job).select_related('job')
        )

        # Annoter le HTML de la page avec toutes les entites connues
        # / Annotate the page HTML with all known entities
        page = entite.job.page
        html_annote = await sync_to_async(annoter_html_avec_barres)(
            page.html_readability or '',
            page.text_readability or '',
            toutes_les_entites_du_job,
        )

        # Rendre le message WS complet : carte + texte annote (deux OOB en un)
        # / Render the complete WS message: card + annotated text (two OOBs in one)
        html_message = await sync_to_async(render_to_string)(
            'front/includes/ws_extraction_complete.html',
            {'entite': entite, 'html_annote': html_annote},
        )

        await self.send(text_data=html_message)


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
