"""
Tests de la commande charger_fixtures_sample.
/ Tests for the charger_fixtures_sample command.

LOCALISATION : front/tests/test_charger_fixtures_sample.py
"""

from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from core.models import Dossier, Page, TranscriptionConfig

User = get_user_model()


class ProprietaireEtCarnetTest(TestCase):
    """Le socle : qui possède les notes étalons, et où elles sont rangées."""

    def test_a_blanc_ne_cree_aucun_utilisateur(self):
        # Une base neuve n'a personne, et le mode a blanc n'y change
        # rien : il annonce ce qu'il ferait, sans l'ecrire.
        # / A dry run announces without writing, users included.
        self.assertEqual(User.objects.count(), 0)

        call_command("charger_fixtures_sample", "--a-blanc", stdout=StringIO())

        self.assertEqual(User.objects.count(), 0)

    def test_le_superuser_existant_est_reutilise(self):
        superuser_existant = User.objects.create_superuser(
            username="deja_la", email="deja@example.org", password="x",
        )

        sortie = StringIO()
        with patch.object(
            __import__(
                "front.management.commands.charger_fixtures_sample",
                fromlist=["Command"],
            ).Command,
            "_charger_les_documents",
            return_value=None,
        ):
            call_command("charger_fixtures_sample", stdout=sortie)

        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(User.objects.first().pk, superuser_existant.pk)
        self.assertIn("réutilisé", sortie.getvalue())

    def test_sans_utilisateur_la_commande_cree_jonas(self):
        sortie = StringIO()
        with patch.object(
            __import__(
                "front.management.commands.charger_fixtures_sample",
                fromlist=["Command"],
            ).Command,
            "_charger_les_documents",
            return_value=None,
        ):
            call_command("charger_fixtures_sample", stdout=sortie)

        utilisateur_cree = User.objects.get(username="jonas")
        self.assertTrue(utilisateur_cree.is_staff)
        self.assertTrue(utilisateur_cree.check_password("admin1234"))

    def test_le_carnet_est_cree_une_seule_fois(self):
        sortie = StringIO()
        with patch.object(
            __import__(
                "front.management.commands.charger_fixtures_sample",
                fromlist=["Command"],
            ).Command,
            "_charger_les_documents",
            return_value=None,
        ):
            call_command("charger_fixtures_sample", stdout=sortie)
            call_command("charger_fixtures_sample", stdout=sortie)

        self.assertEqual(
            Dossier.objects.filter(name="Documents étalons").count(), 1,
        )

    def test_la_config_voxtral_est_creee_si_la_cle_est_la(self):
        with patch.dict("os.environ", {"MISTRAL_API_KEY": "une-cle-de-test"}):
            with patch.object(
                __import__(
                    "front.management.commands.charger_fixtures_sample",
                    fromlist=["Command"],
                ).Command,
                "_charger_les_documents",
                return_value=None,
            ):
                call_command("charger_fixtures_sample", stdout=StringIO())

        config = TranscriptionConfig.objects.get(name="Voxtral Mini")
        self.assertTrue(config.is_active)
        self.assertEqual(config.provider, "voxtral")

    def test_sans_cle_mistral_aucune_config_n_est_creee(self):
        # Creer une config qui echouera au premier appel serait pire que
        # ne pas en creer : la transcription retomberait sur le mock, en
        # silence. / A config that will fail is worse than no config.
        with patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop("MISTRAL_API_KEY", None)
            with patch.object(
                __import__(
                    "front.management.commands.charger_fixtures_sample",
                    fromlist=["Command"],
                ).Command,
                "_charger_les_documents",
                return_value=None,
            ):
                call_command("charger_fixtures_sample", stdout=StringIO())

        self.assertEqual(TranscriptionConfig.objects.count(), 0)

    def test_a_blanc_n_ecrit_rien(self):
        call_command("charger_fixtures_sample", "--a-blanc", stdout=StringIO())

        self.assertEqual(Page.objects.count(), 0)
        self.assertEqual(Dossier.objects.count(), 0)
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(TranscriptionConfig.objects.count(), 0)


class DocumentsEcritsTest(TestCase):
    """La capture web et le markdown, avec Docling mocké."""

    def setUp(self):
        self.chemin_du_module = (
            "front.management.commands.charger_fixtures_sample"
        )

    def test_la_capture_web_devient_une_page(self):
        with patch(
            "hypostasis_extractor.tasks_element."
            "ingerer_une_capture_web_avec_docling.apply",
        ), patch(
            "hypostasis_extractor.tasks_element."
            "ingerer_un_fichier_avec_docling.apply",
        ):
            call_command(
                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
            )

        page_de_la_capture = Page.objects.get(source_type="web")
        self.assertTrue(page_de_la_capture.html_original)
        self.assertEqual(
            page_de_la_capture.original_filename,
            "capture-web-badgeons-la-normandie.html",
        )

    def test_le_markdown_devient_une_page_avec_son_fichier(self):
        with patch(
            "hypostasis_extractor.tasks_element."
            "ingerer_une_capture_web_avec_docling.apply",
        ), patch(
            "hypostasis_extractor.tasks_element."
            "ingerer_un_fichier_avec_docling.apply",
        ):
            call_command(
                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
            )

        page_du_markdown = Page.objects.get(
            original_filename="PRESENTATION-V3.md",
        )
        self.assertEqual(page_du_markdown.source_type, "file")
        # La tache resout le chemin depuis source_file : sans lui, elle
        # rendrait {"erreur": "page sans fichier source"}.
        # / The task resolves the path from source_file.
        self.assertTrue(page_du_markdown.source_file)

    def test_les_deux_notes_sont_rangees_dans_le_carnet(self):
        with patch(
            "hypostasis_extractor.tasks_element."
            "ingerer_une_capture_web_avec_docling.apply",
        ), patch(
            "hypostasis_extractor.tasks_element."
            "ingerer_un_fichier_avec_docling.apply",
        ):
            call_command(
                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
            )

        carnet = Dossier.objects.get(name="Documents étalons")
        self.assertEqual(
            Page.objects.filter(
                appartenances_dossiers__dossier=carnet,
            ).distinct().count(),
            2,
        )

    def test_relancer_ne_double_rien_et_ne_reconvertit_pas(self):
        cible_capture = (
            "hypostasis_extractor.tasks_element."
            "ingerer_une_capture_web_avec_docling.apply"
        )
        cible_fichier = (
            "hypostasis_extractor.tasks_element."
            "ingerer_un_fichier_avec_docling.apply"
        )
        with patch(cible_capture) as capture_mockee, \
                patch(cible_fichier) as fichier_mocke:
            call_command(
                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
            )
            call_command(
                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
            )

            # LE POINT DE CE TEST : la seconde execution ne doit PAS
            # reconvertir. Le garde-fou du service arrive apres la
            # conversion — s'y fier ferait payer Docling pour rien.
            # / The second run must not re-convert.
            self.assertEqual(capture_mockee.call_count, 1)
            self.assertEqual(fichier_mocke.call_count, 1)

        self.assertEqual(Page.objects.count(), 2)

    def test_les_taches_sont_appelees_en_synchrone_avec_la_cle_primaire(self):
        cible_capture = (
            "hypostasis_extractor.tasks_element."
            "ingerer_une_capture_web_avec_docling.apply"
        )
        with patch(cible_capture) as capture_mockee, patch(
            "hypostasis_extractor.tasks_element."
            "ingerer_un_fichier_avec_docling.apply",
        ):
            call_command(
                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
            )

        page_de_la_capture = Page.objects.get(source_type="web")
        capture_mockee.assert_called_once_with(
            args=[page_de_la_capture.pk],
        )
