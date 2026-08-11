"""
Les taches d'ingestion previennent-elles l'utilisateur ?
/ Do ingestion tasks notify the user?

LOCALISATION : hypostasis_extractor/tests/test_notifications_ingestion.py
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import Dossier, Page
from core.services.corpus import ranger_une_note_dans_un_carnet

User = get_user_model()


class NotificationDeLIngestionTest(TestCase):
    """Une ingestion qui se termine doit se faire connaitre."""

    def setUp(self):
        self.proprietaire = User.objects.create_user(username="proprio")
        self.page = Page.objects.create(
            title="Une note", source_type="web",
            html_original="<p>du texte</p>", html_readability="<p>du texte</p>",
            text_readability="du texte", content_hash="x",
            owner=self.proprietaire,
        )

    def test_une_capture_ingeree_previent_son_proprietaire(self):
        from hypostasis_extractor.tasks_element import (
            ingerer_une_capture_web_avec_docling,
        )

        with patch(
            "hypostasis_extractor.services.ingestion_docling."
            "ingerer_une_capture_web", return_value=[1, 2, 3],
        ), patch("front.tasks.notifier_tache_terminee") as notification:
            ingerer_une_capture_web_avec_docling.apply(args=[self.page.pk])

        notification.assert_called_once_with(
            user_pk=self.proprietaire.pk,
            tache_id=self.page.pk,
            tache_type="ingestion",
            status="completed",
        )

    def test_une_ingestion_en_echec_previent_aussi(self):
        # Un echec silencieux est pire qu'un echec : l'utilisateur
        # attendrait indefiniment. / A silent failure is worse.
        from hypostasis_extractor.tasks_element import (
            ingerer_une_capture_web_avec_docling,
        )

        with patch(
            "hypostasis_extractor.services.ingestion_docling."
            "ingerer_une_capture_web", side_effect=ValueError("conversion HS"),
        ), patch("front.tasks.notifier_tache_terminee") as notification:
            ingerer_une_capture_web_avec_docling.apply(args=[self.page.pk])

        self.assertEqual(
            notification.call_args.kwargs["status"], "error",
        )

    def test_le_proprietaire_d_un_carnet_est_prevenu_aussi(self):
        # C'est la correction de la phase D, restee a moitie faite :
        # une note rangee dans le carnet d'un collegue doit le prevenir.
        # / The phase D fix, left half-done.
        from hypostasis_extractor.tasks_element import (
            ingerer_une_capture_web_avec_docling,
        )

        collegue = User.objects.create_user(username="collegue")
        carnet_du_collegue = Dossier.objects.create(
            name="Le carnet du collègue", owner=collegue,
        )
        ranger_une_note_dans_un_carnet(
            self.page, carnet_du_collegue, self.proprietaire,
        )

        with patch(
            "hypostasis_extractor.services.ingestion_docling."
            "ingerer_une_capture_web", return_value=[1],
        ), patch("front.tasks.notifier_tache_terminee") as notification:
            ingerer_une_capture_web_avec_docling.apply(args=[self.page.pk])

        pks_prevenus = {
            appel.kwargs["user_pk"] for appel in notification.call_args_list
        }
        self.assertEqual(pks_prevenus, {self.proprietaire.pk, collegue.pk})

    def test_une_notification_qui_echoue_ne_casse_pas_l_ingestion(self):
        # Une ingestion reussie ne doit pas devenir un echec parce que
        # le canal de notification est tombe.
        # / A dead channel must not fail a successful ingestion.
        from hypostasis_extractor.tasks_element import (
            ingerer_une_capture_web_avec_docling,
        )

        with patch(
            "hypostasis_extractor.services.ingestion_docling."
            "ingerer_une_capture_web", return_value=[1],
        ), patch(
            "front.tasks.notifier_tache_terminee",
            side_effect=RuntimeError("channel layer HS"),
        ):
            resultat = ingerer_une_capture_web_avec_docling.apply(
                args=[self.page.pk],
            )

        self.assertEqual(resultat.result, {"elements": 1})


class DestinatairesDeLAnalyseEtDeLaTranscriptionTest(TestCase):
    """
    La correction de la phase D, appliquee aux deux chemins oublies.
    / The phase D fix, applied to the two forgotten paths.
    """

    def test_l_analyse_previent_les_proprietaires_de_carnets(self):
        from hypostasis_extractor.models import ExtractionJob
        from hypostasis_extractor.tasks_element import _prevenir_l_utilisateur

        proprietaire = User.objects.create_user(username="proprio2")
        collegue = User.objects.create_user(username="collegue2")
        page = Page.objects.create(
            title="Note analysée", source_type="web", html_original="",
            html_readability="", text_readability="", content_hash="y",
            owner=proprietaire,
        )
        carnet = Dossier.objects.create(name="Carnet", owner=collegue)
        ranger_une_note_dans_un_carnet(page, carnet, proprietaire)

        job = ExtractionJob.objects.create(
            page=page, name="j", prompt_description="p", status="completed",
        )

        with patch("front.tasks.notifier_tache_terminee") as notification:
            _prevenir_l_utilisateur(job, "completed")

        pks_prevenus = {
            appel.kwargs["user_pk"] for appel in notification.call_args_list
        }
        self.assertEqual(pks_prevenus, {proprietaire.pk, collegue.pk})
