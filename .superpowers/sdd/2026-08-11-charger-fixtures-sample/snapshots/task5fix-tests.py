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
        # 3, pas 2 : --sans-mp3 ne saute que le mp3. La transcription JSON
        # (tache 3) se charge toujours, meme ici ou son ingestion n'est
        # pas mockee. / --sans-mp3 only skips the mp3; the JSON transcript
        # (task 3) still loads, even with its ingestion unmocked here.
        self.assertEqual(
            Page.objects.filter(
                appartenances_dossiers__dossier=carnet,
            ).distinct().count(),
            3,
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

        # 3, pas 2 : la transcription JSON (tache 3) se charge aussi, et
        # son idempotence propre (_note_deja_presente) evite qu'elle soit
        # doublee au second appel. / The JSON transcript (task 3) also
        # loads, and its own idempotency check prevents duplication.
        self.assertEqual(Page.objects.count(), 3)

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


class EntreesAudioTest(TestCase):
    """La transcription déjà faite, et la chaîne mp3 complète."""

    def _mocks_docling(self):
        """Les deux tâches Docling, neutralisées ensemble."""
        return (
            patch(
                "hypostasis_extractor.tasks_element."
                "ingerer_une_capture_web_avec_docling.apply",
            ),
            patch(
                "hypostasis_extractor.tasks_element."
                "ingerer_un_fichier_avec_docling.apply",
            ),
        )

    def test_le_json_devient_une_page_audio_avec_ses_elements(self):
        capture_mockee, fichier_mocke = self._mocks_docling()
        cible_ingestion = (
            "hypostasis_extractor.tasks_element."
            "ingerer_une_transcription_diarisee_en_elements.apply"
        )
        with capture_mockee, fichier_mocke, patch(cible_ingestion) as ingestion:
            call_command(
                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
            )

        page_du_json = Page.objects.get(
            original_filename="fake_debat_ia_transcription.json",
        )
        self.assertEqual(page_du_json.source_type, "audio")
        # 12 segments, 3 locuteurs — mesure du fichier versionne.
        # / 12 segments, 3 speakers, measured from the versioned file.
        self.assertEqual(len(page_du_json.transcription_raw["segments"]), 12)
        # LE POINT : la vue d'import, elle, N'appelle PAS cette ingestion
        # (front/views.py:5326). Une note importee par cette porte reste
        # sans element. La commande, elle, doit l'appeler.
        # / The import view never calls this; the command must.
        ingestion.assert_called_once_with(args=[page_du_json.pk])

    def test_sans_mp3_la_transcription_voxtral_n_est_pas_lancee(self):
        capture_mockee, fichier_mocke = self._mocks_docling()
        cible_voxtral = "front.tasks.transcrire_audio_task.apply"
        with capture_mockee, fichier_mocke, patch(
            "hypostasis_extractor.tasks_element."
            "ingerer_une_transcription_diarisee_en_elements.apply",
        ), patch(cible_voxtral) as voxtral_mocke:
            call_command(
                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
            )

        voxtral_mocke.assert_not_called()
        self.assertFalse(
            Page.objects.filter(
                original_filename="audio-FR-2locuteur-palaiscesar-14s.mp3",
            ).exists(),
        )

    def test_sans_cle_mistral_le_mp3_est_saute_et_le_reste_charge(self):
        import os

        capture_mockee, fichier_mocke = self._mocks_docling()
        sortie = StringIO()
        cle_sauvegardee = os.environ.pop("MISTRAL_API_KEY", None)
        try:
            with capture_mockee, fichier_mocke, patch(
                "hypostasis_extractor.tasks_element."
                "ingerer_une_transcription_diarisee_en_elements.apply",
            ), patch("front.tasks.transcrire_audio_task.apply") as voxtral:
                call_command("charger_fixtures_sample", stdout=sortie)
        finally:
            if cle_sauvegardee is not None:
                os.environ["MISTRAL_API_KEY"] = cle_sauvegardee

        voxtral.assert_not_called()
        self.assertIn("MISTRAL_API_KEY", sortie.getvalue())
        # Les trois autres notes sont chargees malgre tout.
        # / The other three notes are loaded regardless.
        self.assertEqual(Page.objects.count(), 3)

    def test_avec_la_cle_le_mp3_cree_une_page_et_un_job(self):
        import os

        capture_mockee, fichier_mocke = self._mocks_docling()
        with patch.dict(os.environ, {"MISTRAL_API_KEY": "une-cle-de-test"}):
            with capture_mockee, fichier_mocke, patch(
                "hypostasis_extractor.tasks_element."
                "ingerer_une_transcription_diarisee_en_elements.apply",
            ), patch("front.tasks.transcrire_audio_task.apply") as voxtral:
                call_command("charger_fixtures_sample", stdout=StringIO())

        from core.models import TranscriptionJob

        page_du_mp3 = Page.objects.get(
            original_filename="audio-FR-2locuteur-palaiscesar-14s.mp3",
        )
        job = TranscriptionJob.objects.get(page=page_du_mp3)
        self.assertEqual(job.transcription_config.provider, "voxtral")
        voxtral.assert_called_once()

    def test_echec_voxtral_est_signale_dans_le_bilan(self):
        # LE POINT : `transcrire_audio_task` attrape ses propres
        # exceptions et pose page.status/job.status = ERROR en silence
        # (front/tasks.py ~711-726). Sans controle explicite, le bilan
        # affiche "0 tour(s) de parole" — indiscernable d'un succes sans
        # contenu. On simule cet echec en posant les statuts d'erreur
        # nous-memes, comme le ferait la tache reelle en cas de panne
        # reseau. / The task swallows its own exceptions and silently
        # marks page/job as ERROR; the report must say so explicitly.
        import os

        from core.models import PageStatus, TranscriptionJob, TranscriptionJobStatus

        capture_mockee, fichier_mocke = self._mocks_docling()

        def simuler_echec_reseau_voxtral(args=None, **kwargs):
            job_de_test = TranscriptionJob.objects.get(pk=args[0])
            job_de_test.status = TranscriptionJobStatus.ERROR
            job_de_test.error_message = "Erreur réseau Voxtral (simulée)"
            job_de_test.save(update_fields=["status", "error_message"])

            page_de_test = job_de_test.page
            page_de_test.status = PageStatus.ERROR
            page_de_test.error_message = "Erreur réseau Voxtral (simulée)"
            page_de_test.save(update_fields=["status", "error_message"])

        sortie = StringIO()
        with patch.dict(os.environ, {"MISTRAL_API_KEY": "une-cle-de-test"}):
            with capture_mockee, fichier_mocke, patch(
                "hypostasis_extractor.tasks_element."
                "ingerer_une_transcription_diarisee_en_elements.apply",
            ), patch(
                "front.tasks.transcrire_audio_task.apply",
                side_effect=simuler_echec_reseau_voxtral,
            ):
                call_command("charger_fixtures_sample", stdout=sortie)

        self.assertIn("ÉCHEC", sortie.getvalue())
        self.assertIn("Erreur réseau Voxtral (simulée)", sortie.getvalue())


class RefusDesFormatsLourdsTest(TestCase):
    """Le PDF et le docx ne passent pas par cette porte."""

    def test_un_pdf_est_refuse_sans_conversion(self):
        from django.core.management.base import CommandError

        cible_fichier = (
            "hypostasis_extractor.tasks_element."
            "ingerer_un_fichier_avec_docling.apply"
        )
        with patch(cible_fichier) as fichier_mocke:
            with self.assertRaises(CommandError) as contexte:
                call_command(
                    "charger_fixtures_sample",
                    "--fichier", "sample/Etude_Epistemologique_IA.pdf",
                    stdout=StringIO(),
                )

        # Le message doit ORIENTER, pas seulement refuser.
        # / The message must point somewhere, not merely refuse.
        self.assertIn(".pdf", str(contexte.exception))
        fichier_mocke.assert_not_called()

    def test_un_docx_est_refuse_aussi(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command(
                "charger_fixtures_sample",
                "--fichier", "sample/quelque-chose.docx",
                stdout=StringIO(),
            )

    def test_fichier_restreint_le_chargement_a_ce_seul_document(self):
        cible_capture = (
            "hypostasis_extractor.tasks_element."
            "ingerer_une_capture_web_avec_docling.apply"
        )
        cible_fichier = (
            "hypostasis_extractor.tasks_element."
            "ingerer_un_fichier_avec_docling.apply"
        )
        with patch(cible_capture) as capture_mockee, patch(cible_fichier):
            call_command(
                "charger_fixtures_sample",
                "--fichier", "PRESENTATION-V3.md",
                stdout=StringIO(),
            )

        self.assertEqual(Page.objects.count(), 1)
        self.assertEqual(
            Page.objects.first().original_filename, "PRESENTATION-V3.md",
        )
        capture_mockee.assert_not_called()

    def test_un_fichier_inconnu_est_refuse_clairement(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError) as contexte:
            call_command(
                "charger_fixtures_sample",
                "--fichier", "n-existe-pas.md",
                stdout=StringIO(),
            )

        self.assertIn("n-existe-pas.md", str(contexte.exception))

    def test_fichier_est_repetable_et_charge_les_deux(self):
        # LE POINT : `--fichier` repete deux fois doit charger les DEUX
        # documents demandes, et rien d'autre — pas seulement le dernier
        # de la liste. / --fichier repeated twice must load BOTH requested
        # documents, and nothing else — not just the last one.
        cible_capture = (
            "hypostasis_extractor.tasks_element."
            "ingerer_une_capture_web_avec_docling.apply"
        )
        cible_fichier = (
            "hypostasis_extractor.tasks_element."
            "ingerer_un_fichier_avec_docling.apply"
        )
        with patch(cible_capture), patch(cible_fichier):
            call_command(
                "charger_fixtures_sample",
                "--fichier", "capture-web-badgeons-la-normandie.html",
                "--fichier", "PRESENTATION-V3.md",
                stdout=StringIO(),
            )

        noms_de_fichiers_charges = set(
            Page.objects.values_list("original_filename", flat=True),
        )
        self.assertEqual(
            noms_de_fichiers_charges,
            {
                "capture-web-badgeons-la-normandie.html",
                "PRESENTATION-V3.md",
            },
        )
        self.assertEqual(Page.objects.count(), 2)


class ReinitialisationTest(TestCase):
    """--reset rejoue tout, sauf s'il y a des preuves à perdre."""

    def _charger_une_fois(self):
        cible_capture = (
            "hypostasis_extractor.tasks_element."
            "ingerer_une_capture_web_avec_docling.apply"
        )
        cible_fichier = (
            "hypostasis_extractor.tasks_element."
            "ingerer_un_fichier_avec_docling.apply"
        )
        cible_audio = (
            "hypostasis_extractor.tasks_element."
            "ingerer_une_transcription_diarisee_en_elements.apply"
        )
        with patch(cible_capture), patch(cible_fichier), patch(cible_audio):
            call_command(
                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
            )

    def test_reset_supprime_les_notes_et_les_recharge(self):
        self._charger_une_fois()
        pks_de_depart = set(Page.objects.values_list("pk", flat=True))
        self.assertEqual(len(pks_de_depart), 3)

        cible_capture = (
            "hypostasis_extractor.tasks_element."
            "ingerer_une_capture_web_avec_docling.apply"
        )
        with patch(cible_capture) as capture_mockee, patch(
            "hypostasis_extractor.tasks_element."
            "ingerer_un_fichier_avec_docling.apply",
        ), patch(
            "hypostasis_extractor.tasks_element."
            "ingerer_une_transcription_diarisee_en_elements.apply",
        ):
            call_command(
                "charger_fixtures_sample", "--reset", "--sans-mp3",
                stdout=StringIO(),
            )
            # Le point du reset : on RECONVERTIT, la ou l'idempotence
            # aurait saute. / The point of --reset: convert again.
            self.assertEqual(capture_mockee.call_count, 1)

        self.assertEqual(Page.objects.count(), 3)
        self.assertFalse(
            set(Page.objects.values_list("pk", flat=True)) & pks_de_depart,
        )

    def test_reset_refuse_si_une_note_porte_une_ancre(self):
        from django.core.management.base import CommandError

        # Ces trois modeles vivent dans hypostasis_extractor, PAS dans
        # core.models. / These three live in hypostasis_extractor.
        from hypostasis_extractor.models import (
            AncrageExtraction, ExtractedEntity, ExtractionJob,
        )

        self._charger_une_fois()
        page_avec_ancre = Page.objects.filter(source_type="web").first()
        element = page_avec_ancre.elements.create(
            ordre=0, label="text", texte="un passage", empreinte_contenu="x",
        )
        job = ExtractionJob.objects.create(
            page=page_avec_ancre, name="job de test",
            prompt_description="peu importe", status="completed",
        )
        entite = ExtractedEntity.objects.create(
            job=job, extraction_class="PHENOMENE", extraction_text="une idée",
            start_char=0, end_char=10,
        )
        # Les champs sont debut_dans_element / fin_dans_element — des
        # positions DANS l'element, jamais dans le texte global de la
        # page. / Positions within the element, never page-global.
        AncrageExtraction.objects.create(
            extraction=entite, element=element,
            ordre_dans_extraction=0,
            debut_dans_element=0, fin_dans_element=10,
        )

        nombre_de_pages_avant = Page.objects.count()
        with self.assertRaises(CommandError) as contexte:
            call_command(
                "charger_fixtures_sample", "--reset", "--sans-mp3",
                stdout=StringIO(),
            )

        # RIEN ne doit avoir ete supprime — pas de suppression partielle
        # qui laisserait le carnet a moitie vide.
        # / Nothing deleted: no half-emptied notebook.
        self.assertEqual(Page.objects.count(), nombre_de_pages_avant)
        self.assertIn(page_avec_ancre.title, str(contexte.exception))

    def test_reset_ne_touche_pas_une_note_rangee_ailleurs(self):
        from core.models import Dossier as CarnetModele
        from core.services.corpus import ranger_une_note_dans_un_carnet

        self._charger_une_fois()
        page_partagee = Page.objects.filter(source_type="web").first()
        proprietaire = page_partagee.owner
        autre_carnet = CarnetModele.objects.create(
            name="Un autre carnet", owner=proprietaire,
        )
        ranger_une_note_dans_un_carnet(page_partagee, autre_carnet, proprietaire)

        with patch(
            "hypostasis_extractor.tasks_element."
            "ingerer_une_capture_web_avec_docling.apply",
        ), patch(
            "hypostasis_extractor.tasks_element."
            "ingerer_un_fichier_avec_docling.apply",
        ), patch(
            "hypostasis_extractor.tasks_element."
            "ingerer_une_transcription_diarisee_en_elements.apply",
        ):
            call_command(
                "charger_fixtures_sample", "--reset", "--sans-mp3",
                stdout=StringIO(),
            )

        # Elle vit ailleurs : on ne l'emporte pas.
        # / It lives elsewhere: not ours to delete.
        self.assertTrue(Page.objects.filter(pk=page_partagee.pk).exists())

    def test_a_blanc_reset_ne_supprime_rien(self):
        # La verification des ancres tourne AVANT le `if self.a_blanc:
        # return None` de `_reinitialiser` : rien ne doit disparaitre,
        # meme sans ancre a proteger. / The anchor check runs before the
        # dry-run early return: nothing should vanish, anchors or not.
        self._charger_une_fois()
        nombre_de_pages_avant = Page.objects.count()
        carnet_avant = Dossier.objects.get(name="Documents étalons")

        call_command(
            "charger_fixtures_sample", "--a-blanc", "--reset", "--sans-mp3",
            stdout=StringIO(),
        )

        self.assertEqual(Page.objects.count(), nombre_de_pages_avant)
        self.assertTrue(
            Dossier.objects.filter(pk=carnet_avant.pk).exists(),
        )
