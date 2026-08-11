"""
Une notification en echec ne doit pas ecraser le succes d'une transcription.
/ A failed notification must not overwrite a transcription's success.

LOCALISATION : front/tests/test_notification_transcription.py

CONTEXTE (revue adverse de la tache 7) : les deux boucles de notification
de `transcrire_audio_task` (succes ~704, erreur ~736) sont a l'interieur
du `try` principal de la tache. Sans `try/except` autour de l'appel a
`notifier_tache_terminee`, une exception levee par le channel layer (le
`group_send` de la ligne 39, non protege par le garde `couche_channels is
None`) remonte jusqu'au `except Exception` de la tache et ECRASE le
statut COMPLETED deja sauvegarde par ERROR. Une transcription reussie,
texte deja en base, se retrouverait marquee en echec.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import Page, PageStatus, TranscriptionJob

User = get_user_model()


class NotificationDeTranscriptionEnEchecTest(TestCase):
    """La notification est un confort ; la transcription est le travail."""

    def setUp(self):
        self.proprietaire = User.objects.create_user(username="proprio_audio")
        self.page = Page.objects.create(
            title="Un audio", source_type="audio",
            html_original="", html_readability="",
            text_readability="", content_hash="a",
            owner=self.proprietaire,
        )
        self.job_transcription = TranscriptionJob.objects.create(
            page=self.page,
        )

    def test_une_notification_qui_echoue_ne_marque_pas_la_page_en_erreur(self):
        from front.tasks import transcrire_audio_task

        segments_factices = {
            "model": "mock",
            "text": "bonjour",
            "segments": [
                {"speaker": "Locuteur 1", "start": 0.0, "end": 1.0,
                 "text": "bonjour"},
            ],
        }

        with patch(
            "front.services.transcription_audio.transcrire_audio_mock",
            return_value=segments_factices,
        ), patch(
            "hypostasis_extractor.tasks_element."
            "ingerer_une_transcription_diarisee_en_elements.delay",
        ), patch(
            "front.tasks.notifier_tache_terminee",
            side_effect=RuntimeError("channel layer HS"),
        ):
            transcrire_audio_task.apply(
                args=[self.job_transcription.pk, "/tmp/inexistant-pour-le-test.wav"],
            )

        self.page.refresh_from_db()
        self.job_transcription.refresh_from_db()

        self.assertEqual(self.page.status, PageStatus.COMPLETED)
        self.assertEqual(self.job_transcription.status, "completed")
