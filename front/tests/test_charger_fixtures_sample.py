"""
Tests de la commande charger_fixtures_sample.
/ Tests for the charger_fixtures_sample command.

LOCALISATION : front/tests/test_charger_fixtures_sample.py
"""

from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from core.models import Dossier, Page, TranscriptionConfig

User = get_user_model()

# Les trois taches d'ingestion, par leur chemin d'import. Les tests les
# mockent presque toujours : une conversion Docling reelle coute 98 s.
# / The three ingestion tasks, by import path; almost always mocked.
CIBLE_INGESTION_CAPTURE = (
    "hypostasis_extractor.tasks_element."
    "ingerer_une_capture_web_avec_docling.apply"
)
CIBLE_INGESTION_FICHIER = (
    "hypostasis_extractor.tasks_element."
    "ingerer_un_fichier_avec_docling.apply"
)
CIBLE_INGESTION_TRANSCRIPTION = (
    "hypostasis_extractor.tasks_element."
    "ingerer_une_transcription_diarisee_en_elements.apply"
)


def ingestion_simulee(*labels_des_elements):
    """
    Rend un side_effect de mock qui simule une ingestion REUSSIE.
    / Returns a mock side_effect simulating a SUCCESSFUL ingestion.

    LOCALISATION : front/tests/test_charger_fixtures_sample.py

    POURQUOI CE HELPER EXISTE

    Un `patch()` nu rend un Mock et ne cree AUCUN element : la page reste
    a moitie ingeree. Or l'idempotence de la commande porte desormais sur
    la presence d'elements, pas sur celle de la Page — une page sans
    element doit pouvoir etre rechargee. Un test qui veut eprouver le saut
    d'une note deja chargee doit donc simuler une ingestion qui produit
    vraiment quelque chose.
    / A bare patch() creates no element, so the page stays half-ingested;
    idempotency now keys on elements, so tests must simulate real output.
    """
    labels_retenus = labels_des_elements or ("text",)

    def executer_l_ingestion(args=None, **kwargs):
        page_ingeree = Page.objects.get(pk=args[0])
        for position, label in enumerate(labels_retenus):
            page_ingeree.elements.create(
                ordre=position,
                label=label,
                texte=f"élément simulé {position}",
                empreinte_contenu=f"empreinte-{page_ingeree.pk}-{position}",
            )
        return SimpleNamespace(result={"elements": len(labels_retenus)})

    return executer_l_ingestion


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
        # 5, pas 3 : --sans-mp3 ne saute que le mp3. La transcription JSON
        # (tache 3) et les deux PDF (taches 5 et 6, meme mock que le
        # fichier markdown — ingerer_un_fichier_avec_docling) se chargent
        # toujours. / --sans-mp3 only skips the mp3; the JSON transcript
        # and both PDF (same mock target as the markdown file) still load.
        self.assertEqual(
            Page.objects.filter(
                appartenances_dossiers__dossier=carnet,
            ).distinct().count(),
            5,
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
        # Les mocks SIMULENT UNE INGESTION REUSSIE (ils creent un element).
        # Un `patch()` nu n'en creerait aucun : la page resterait a moitie
        # ingeree, et l'idempotence — qui porte desormais sur la presence
        # d'elements et non sur celle de la Page — la rechargerait a juste
        # titre. Ce test-ci parle du cas nominal : une note bel et bien
        # ingeree ne se reconvertit pas.
        # / The mocks simulate a SUCCESSFUL ingestion: a bare patch() would
        # leave the page element-less, which idempotency now (rightly)
        # treats as reloadable. This test covers the nominal case.
        with patch(
            cible_capture, side_effect=ingestion_simulee("text"),
        ) as capture_mockee, patch(
            cible_fichier, side_effect=ingestion_simulee("text"),
        ) as fichier_mocke:
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
            # 3, pas 1 : cible_fichier est le mock d'ingerer_un_fichier_
            # avec_docling, partage par le markdown ET les DEUX PDF — un
            # appel chacun a la premiere execution, zero a la seconde.
            # / 3, not 1: cible_fichier is shared by the markdown AND both
            # PDF loaders — one call each on the first run.
            self.assertEqual(fichier_mocke.call_count, 3)

        # 5, pas 3 : la transcription JSON (tache 3) et les deux PDF
        # (taches 5 et 6) se chargent aussi, et leur idempotence propre
        # evite qu'ils soient doubles au second appel. / The JSON
        # transcript and both PDF also load, and their own idempotency
        # prevents duplication.
        self.assertEqual(Page.objects.count(), 5)

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
        # Les cinq autres notes sont chargees malgre tout (capture,
        # markdown, transcription JSON, les deux PDF). / The other five
        # notes are loaded regardless.
        self.assertEqual(Page.objects.count(), 5)

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
    """Le docx ne passe pas par cette porte — le PDF, lui, désormais oui."""

    def test_un_docx_est_refuse_sans_conversion(self):
        # Ce test affirmait l'inverse jusqu'au 11 aout 2026 : le PDF y
        # etait refuse. Le PDF est desormais charge par defaut (voir
        # PdfEtBaseDeDemonstrationTest) — ce test devient celui du docx,
        # le seul format qui reste refuse. / This test asserted the
        # opposite until 11 August: the PDF was refused there. The PDF
        # now loads by default — this test becomes the docx's.
        from django.core.management.base import CommandError

        cible_fichier = (
            "hypostasis_extractor.tasks_element."
            "ingerer_un_fichier_avec_docling.apply"
        )
        with patch(cible_fichier) as fichier_mocke:
            with self.assertRaises(CommandError) as contexte:
                call_command(
                    "charger_fixtures_sample",
                    "--fichier", "sample/présentation des open badges.docx",
                    stdout=StringIO(),
                )

        # Le message doit ORIENTER, pas seulement refuser.
        # / The message must point somewhere, not merely refuse.
        self.assertIn(".docx", str(contexte.exception))
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
        # 5, pas 3 : les deux PDF (taches 5 et 6) partagent cible_fichier
        # avec le markdown et se chargent donc aussi ici. / 5, not 3: both
        # PDF share cible_fichier with the markdown and load here too.
        self.assertEqual(len(pks_de_depart), 5)

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

        self.assertEqual(Page.objects.count(), 5)
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


class ConfigDeTranscriptionDuMp3Test(TestCase):
    """Quelle configuration le job de transcription reçoit, et pourquoi."""

    def _charger_avec_la_cle(self, sortie, side_effect_voxtral=None):
        """Lance la commande avec MISTRAL_API_KEY, Docling neutralisé."""
        import os

        with patch.dict(os.environ, {"MISTRAL_API_KEY": "une-cle-de-test"}):
            with patch(CIBLE_INGESTION_CAPTURE), \
                    patch(CIBLE_INGESTION_FICHIER), \
                    patch(CIBLE_INGESTION_TRANSCRIPTION), \
                    patch(
                        "front.tasks.transcrire_audio_task.apply",
                        side_effect=side_effect_voxtral,
                    ) as voxtral_mocke:
                call_command("charger_fixtures_sample", stdout=sortie)
        return voxtral_mocke

    def test_le_mp3_recoit_la_config_voxtral_pas_une_config_mock_active(self):
        # LE POINT : `filter(is_active=True).first()` prend n'importe
        # quelle config active. TranscriptionConfig n'a aucun
        # Meta.ordering, et son provider vaut MOCK par defaut : une config
        # creee depuis l'admin sans choisir de modele est une config mock.
        # Si elle passe, front/tasks.py:634 retombe sur transcrire_audio_mock
        # et le bilan annonce quand meme des tours de parole Voxtral — le
        # faux verbatim que le § 3.2 de la spec existe pour interdire.
        # / A MOCK config created first must not be picked over Voxtral:
        # the task would silently mock and the report would still lie.
        config_mock_active = TranscriptionConfig.objects.create(
            name="Config d'un autre usage", model_choice="mock",
            is_active=True,
        )
        self.assertEqual(config_mock_active.provider, "mock")

        self._charger_avec_la_cle(StringIO())

        from core.models import TranscriptionJob

        job_du_mp3 = TranscriptionJob.objects.get()
        self.assertEqual(job_du_mp3.transcription_config.provider, "voxtral")
        self.assertEqual(job_du_mp3.transcription_config.name, "Voxtral Mini")

    def test_sans_config_voxtral_le_mp3_est_saute_plutot_que_mocke(self):
        # Le cas reel : une config nommee « Voxtral Mini » existe deja mais
        # a ete posee en mock (get_or_create porte sur le seul `name`, il
        # la rend telle quelle). Sans config voxtral utilisable, mieux vaut
        # sauter le mp3 en le disant que produire un faux verbatim.
        # / An existing MOCK config named "Voxtral Mini" is returned as-is
        # by get_or_create: skip the mp3 loudly rather than fake a verbatim.
        TranscriptionConfig.objects.create(
            name="Voxtral Mini", model_choice="mock", is_active=True,
        )

        sortie = StringIO()
        voxtral_mocke = self._charger_avec_la_cle(sortie)

        voxtral_mocke.assert_not_called()
        self.assertIn("Voxtral", sortie.getvalue())
        self.assertFalse(
            Page.objects.filter(
                original_filename="audio-FR-2locuteur-palaiscesar-14s.mp3",
            ).exists(),
        )

    def test_le_media_de_la_note_audio_survit_a_la_tache(self):
        # LE POINT : `transcrire_audio_task` fait os.unlink() sur le chemin
        # recu, dans un `finally`, succes ou echec (front/tasks.py:742-747).
        # Son contrat est de recevoir un fichier TEMPORAIRE — la vue
        # d'import lui passe une copie dans AUDIO_TEMP_DIR. Lui passer
        # page.source_file.path detruit le media de la note elle-meme.
        # / The task unlinks the path it receives, in a finally block:
        # passing page.source_file.path destroys the note's own media.
        import os

        chemins_recus = []

        def simuler_le_unlink_de_la_tache(args=None, **kwargs):
            chemin_recu = args[1]
            chemins_recus.append(chemin_recu)
            if os.path.exists(chemin_recu):
                os.unlink(chemin_recu)

        self._charger_avec_la_cle(
            StringIO(), side_effect_voxtral=simuler_le_unlink_de_la_tache,
        )

        page_du_mp3 = Page.objects.get(
            original_filename="audio-FR-2locuteur-palaiscesar-14s.mp3",
        )
        self.assertEqual(len(chemins_recus), 1)
        self.assertNotEqual(chemins_recus[0], page_du_mp3.source_file.path)
        self.assertTrue(
            os.path.exists(page_du_mp3.source_file.path),
            "le média de la note a été supprimé par la tâche",
        )


class RattrapageDesNotesSansElementTest(TestCase):
    """Une ingestion ratée ne doit pas être définitive."""

    def test_une_note_sans_element_est_rechargee(self):
        # LE POINT : si l'ingestion echoue, la note reste en base SANS
        # element. `_note_deja_presente` ne testait que l'existence de la
        # Page : toutes les relances la sautaient, et l'etat a moitie
        # ingere ne se reparait jamais sans --reset.
        # / A failed ingestion left a page with no element that every rerun
        # skipped: the half-ingested state never repaired itself.
        with patch(CIBLE_INGESTION_CAPTURE) as capture_ratee, \
                patch(CIBLE_INGESTION_FICHIER), \
                patch(CIBLE_INGESTION_TRANSCRIPTION):
            call_command(
                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
            )
            self.assertEqual(capture_ratee.call_count, 1)

        with patch(
            CIBLE_INGESTION_CAPTURE,
            side_effect=ingestion_simulee("text"),
        ) as capture_rejouee, patch(CIBLE_INGESTION_FICHIER), \
                patch(CIBLE_INGESTION_TRANSCRIPTION):
            call_command(
                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
            )
            self.assertEqual(capture_rejouee.call_count, 1)

        # Rechargee, pas doublee : la contrainte unique_url_si_presente
        # interdirait de toute facon un doublon de la capture web.
        # / Reloaded, not duplicated.
        self.assertEqual(
            Page.objects.filter(source_type="web").count(), 1,
        )

    def test_une_note_avec_ses_elements_est_bien_sautee(self):
        with patch(
            CIBLE_INGESTION_CAPTURE, side_effect=ingestion_simulee("text"),
        ), patch(
            CIBLE_INGESTION_FICHIER, side_effect=ingestion_simulee("text"),
        ), patch(
            CIBLE_INGESTION_TRANSCRIPTION, side_effect=ingestion_simulee("text"),
        ):
            call_command(
                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
            )

        with patch(CIBLE_INGESTION_CAPTURE) as capture_rejouee, \
                patch(CIBLE_INGESTION_FICHIER) as fichier_rejoue, \
                patch(CIBLE_INGESTION_TRANSCRIPTION) as transcription_rejouee:
            call_command(
                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
            )

        capture_rejouee.assert_not_called()
        fichier_rejoue.assert_not_called()
        transcription_rejouee.assert_not_called()
        # 5, pas 3 : les deux PDF (taches 5 et 6) partagent
        # CIBLE_INGESTION_FICHIER avec le markdown et se chargent donc
        # aussi ici. / 5, not 3: both PDF share CIBLE_INGESTION_FICHIER
        # with the markdown.
        self.assertEqual(Page.objects.count(), 5)

    def test_une_note_sans_element_rangee_ailleurs_n_est_pas_supprimee(self):
        # Une note rangee AUSSI dans un autre carnet appartient a ce
        # quelqu'un d'autre : on ne la supprime pas pour se rattraper.
        # Meme regle que --reset. / A note also filed elsewhere is not ours.
        from core.services.corpus import ranger_une_note_dans_un_carnet

        with patch(CIBLE_INGESTION_CAPTURE), patch(CIBLE_INGESTION_FICHIER), \
                patch(CIBLE_INGESTION_TRANSCRIPTION):
            call_command(
                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
            )

        page_partagee = Page.objects.get(source_type="web")
        autre_carnet = Dossier.objects.create(
            name="Un autre carnet", owner=page_partagee.owner,
        )
        ranger_une_note_dans_un_carnet(
            page_partagee, autre_carnet, page_partagee.owner,
        )

        with patch(CIBLE_INGESTION_CAPTURE), patch(CIBLE_INGESTION_FICHIER), \
                patch(CIBLE_INGESTION_TRANSCRIPTION):
            call_command(
                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
            )

        self.assertTrue(Page.objects.filter(pk=page_partagee.pk).exists())


class ModeABlancTest(TestCase):
    """Le mode à blanc doit dire vrai, pas seulement ne rien écrire."""

    def _charger_une_fois_pour_de_vrai(self):
        with patch(
            CIBLE_INGESTION_CAPTURE, side_effect=ingestion_simulee("text"),
        ), patch(
            CIBLE_INGESTION_FICHIER, side_effect=ingestion_simulee("text"),
        ), patch(
            CIBLE_INGESTION_TRANSCRIPTION, side_effect=ingestion_simulee("text"),
        ):
            call_command(
                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
            )

    def test_a_blanc_dit_vrai_sur_une_base_deja_chargee(self):
        # LE POINT : `_creer_le_carnet` rendait None en mode a blanc sans
        # chercher le carnet existant. `_note_deja_presente` rendait donc
        # toujours False, et le mode a blanc annoncait « serait chargee »
        # pour les quatre notes alors qu'une vraie execution les sautait
        # toutes. L'option existe pour montrer ce qui se passerait.
        # / Dry run must reflect what a real run would do.
        self._charger_une_fois_pour_de_vrai()

        sortie = StringIO()
        call_command(
            "charger_fixtures_sample", "--a-blanc", "--sans-mp3",
            stdout=sortie,
        )

        texte_du_bilan = sortie.getvalue()
        self.assertIn("Capture web         : déjà présente — sautée", texte_du_bilan)
        self.assertIn("Markdown            : déjà présent — sauté", texte_du_bilan)
        self.assertNotIn("serait chargée", texte_du_bilan)

    def test_a_blanc_ne_cree_toujours_aucun_carnet(self):
        # Chercher le carnet existant ne doit pas devenir le creer.
        # / Looking the notebook up must not become creating it.
        User.objects.create_superuser(
            username="deja_la", email="deja@example.org", password="x",
        )

        call_command(
            "charger_fixtures_sample", "--a-blanc", "--sans-mp3",
            stdout=StringIO(),
        )

        self.assertEqual(Dossier.objects.count(), 0)

    def test_a_blanc_n_appelle_pas_voxtral_meme_avec_la_cle(self):
        # LE SEUL CHEMIN OU UNE GARDE MAL PLACEE COUTE UN APPEL RESEAU
        # PAYANT. Le mp3 est le seul document dont le traitement appelle
        # un service facture ; --a-blanc doit rendre la main avant.
        # / The only path where a misplaced guard costs a paid network call.
        import os

        sortie = StringIO()
        with patch.dict(os.environ, {"MISTRAL_API_KEY": "une-cle-de-test"}):
            with patch(CIBLE_INGESTION_CAPTURE), \
                    patch(CIBLE_INGESTION_FICHIER), \
                    patch(CIBLE_INGESTION_TRANSCRIPTION), \
                    patch(
                        "front.tasks.transcrire_audio_task.apply",
                    ) as voxtral_mocke, patch(
                        "front.services.transcription_audio."
                        "transcrire_audio_via_voxtral",
                    ) as voxtral_direct:
                call_command(
                    "charger_fixtures_sample", "--a-blanc", stdout=sortie,
                )

        voxtral_mocke.assert_not_called()
        voxtral_direct.assert_not_called()
        self.assertEqual(Page.objects.count(), 0)
        self.assertEqual(TranscriptionConfig.objects.count(), 0)
        from core.models import TranscriptionJob

        self.assertEqual(TranscriptionJob.objects.count(), 0)
        self.assertIn("serait transcrit", sortie.getvalue())


class PdfEtBaseDeDemonstrationTest(TestCase):
    """Le PDF entre dans les étalons, et le carnet dans une base."""

    def _mocks_sans_docling(self):
        """Les quatre tâches d'ingestion, neutralisées ensemble."""
        return [
            patch("hypostasis_extractor.tasks_element."
                  "ingerer_une_capture_web_avec_docling.apply"),
            patch("hypostasis_extractor.tasks_element."
                  "ingerer_un_fichier_avec_docling.apply"),
            patch("hypostasis_extractor.tasks_element."
                  "ingerer_une_transcription_diarisee_en_elements.apply"),
        ]

    def test_le_pdf_est_charge_par_defaut(self):
        from contextlib import ExitStack

        with ExitStack() as pile:
            for mock in self._mocks_sans_docling():
                pile.enter_context(mock)
            call_command("charger_fixtures_sample", "--sans-mp3",
                         stdout=StringIO())

        page_du_pdf = Page.objects.get(
            original_filename="Etude_Epistemologique_IA.pdf",
        )
        self.assertEqual(page_du_pdf.source_type, "file")
        # La tâche résout le chemin depuis source_file : sans lui, elle
        # rendrait {"erreur": "page sans fichier source"}.
        # / The task resolves the path from source_file.
        self.assertTrue(page_du_pdf.source_file)

    def test_le_second_pdf_est_charge_par_defaut_apres_le_premier(self):
        # LE POINT : le second PDF (« présentation des open badges.pdf »)
        # est le plus coûteux des six documents étalons (~3 365 Mio,
        # tmp/benchmark-docling-2026-08-11.md § 2) — il doit se charger
        # EN TOUT DERNIER, après le premier PDF. Son nom de fichier porte
        # un espace ET un accent : ce test vérifie qu'il traverse la
        # lecture depuis sample/, le ContentFile écrit dans media/, et la
        # résolution du chemin par la tâche, sans dommage.
        # / The second PDF is the costliest of the six reference
        # documents and must load LAST. Its filename carries a space AND
        # an accent — this checks it survives sample/ read, media/
        # write, and task path resolution unscathed.
        from contextlib import ExitStack

        with ExitStack() as pile:
            for mock in self._mocks_sans_docling():
                pile.enter_context(mock)
            call_command("charger_fixtures_sample", "--sans-mp3",
                         stdout=StringIO())

        page_du_second_pdf = Page.objects.get(
            original_filename="présentation des open badges.pdf",
        )
        self.assertEqual(page_du_second_pdf.source_type, "file")
        self.assertTrue(page_du_second_pdf.source_file)
        # `original_filename` porte le nom EXACT, espace et accent
        # compris : c'est lui que l'interface affiche. Le nom du fichier
        # stocké sous media/, lui, passe par le sanitizing standard de
        # Django (FileSystemStorage.get_valid_filename : espace ->
        # underscore) — un comportement normal pour n'importe quel nom,
        # pas une perte de donnée. / `original_filename` carries the
        # exact name; the stored file's name goes through Django's
        # ordinary sanitizing — normal for any filename, not data loss.
        self.assertIn("open_badges", page_du_second_pdf.source_file.name)
        # L'accent, lui, n'est pas touché par ce sanitizing.
        # / The accent, unlike the space, is untouched by it.
        self.assertIn("présentation", page_du_second_pdf.source_file.name)

        # Le titre distingue les deux PDF d'un coup d'œil dans
        # l'interface. / The title tells the two PDF apart at a glance.
        self.assertNotEqual(
            page_du_second_pdf.title,
            Page.objects.get(
                original_filename="Etude_Epistemologique_IA.pdf",
            ).title,
        )

    def test_fichier_accepte_le_nom_a_espace_et_accent_du_second_pdf(self):
        # LE PIÈGE DE CE FICHIER PRÉCIS : son nom contient un espace et un
        # caractère accentué. --fichier doit le résoudre tel quel, en
        # ligne de commande, sans qu'il faille le renommer.
        # / --fichier must resolve the name as-is, spaces and accent
        # included — renaming the file is not an acceptable workaround.
        with patch(
            "hypostasis_extractor.tasks_element."
            "ingerer_un_fichier_avec_docling.apply",
        ):
            call_command(
                "charger_fixtures_sample",
                "--fichier", "présentation des open badges.pdf",
                stdout=StringIO(),
            )

        self.assertEqual(Page.objects.count(), 1)
        page_du_second_pdf = Page.objects.first()
        self.assertEqual(
            page_du_second_pdf.original_filename,
            "présentation des open badges.pdf",
        )

    def test_le_docx_reste_refuse(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError) as contexte:
            call_command("charger_fixtures_sample",
                         "--fichier", "quelque-chose.docx", stdout=StringIO())

        self.assertIn(".docx", str(contexte.exception))

    def test_le_carnet_est_range_dans_la_base_demonstration(self):
        from contextlib import ExitStack

        from core.models import AppartenanceDossierBase, BaseDeConnaissances

        with ExitStack() as pile:
            for mock in self._mocks_sans_docling():
                pile.enter_context(mock)
            call_command("charger_fixtures_sample", "--sans-mp3",
                         stdout=StringIO())

        base = BaseDeConnaissances.objects.get(nom="Démonstration")
        carnet = Dossier.objects.get(name="Documents étalons")
        self.assertTrue(
            AppartenanceDossierBase.objects.filter(
                dossier=carnet, base=base,
            ).exists(),
        )

    def test_relancer_ne_cree_pas_deux_bases(self):
        from contextlib import ExitStack

        from core.models import BaseDeConnaissances

        with ExitStack() as pile:
            for mock in self._mocks_sans_docling():
                pile.enter_context(mock)
            call_command("charger_fixtures_sample", "--sans-mp3",
                         stdout=StringIO())
            call_command("charger_fixtures_sample", "--sans-mp3",
                         stdout=StringIO())

        self.assertEqual(
            BaseDeConnaissances.objects.filter(nom="Démonstration").count(), 1,
        )

    def test_a_blanc_ne_cree_pas_la_base(self):
        call_command("charger_fixtures_sample", "--a-blanc", stdout=StringIO())

        from core.models import BaseDeConnaissances

        self.assertEqual(BaseDeConnaissances.objects.count(), 0)


class BilanDeSortieTest(TestCase):
    """Le bilan du § 4 de la spec, ligne par ligne."""

    def test_le_bilan_detaille_les_labels_de_la_capture_web(self):
        # Le detail par label n'est imprime que pour la capture web : c'est
        # elle qui porte le controle de non-regression du § 5 (28 elements
        # — section_header 4 · list_item 5 · text 19). Sans ce detail,
        # un retour au decoupage maison (tout en `text`) passerait inapercu.
        # / Only the web capture prints the per-label breakdown: it carries
        # the § 5 non-regression check.
        sortie = StringIO()
        with patch(
            CIBLE_INGESTION_CAPTURE,
            side_effect=ingestion_simulee(
                "section_header", "list_item", "text", "text",
            ),
        ), patch(
            CIBLE_INGESTION_FICHIER, side_effect=ingestion_simulee("text"),
        ), patch(
            CIBLE_INGESTION_TRANSCRIPTION, side_effect=ingestion_simulee("text"),
        ):
            call_command(
                "charger_fixtures_sample", "--sans-mp3", stdout=sortie,
            )

        texte_du_bilan = sortie.getvalue()
        self.assertIn(
            "Capture web         : 4 élément(s) — "
            "section_header 1 · list_item 1 · text 2",
            texte_du_bilan,
        )
        # Le markdown, lui, n'a pas de detail par label.
        # / The markdown line carries no per-label detail.
        self.assertIn("Markdown            : 1 élément(s)", texte_du_bilan)
        self.assertNotIn("Markdown            : 1 élément(s) —", texte_du_bilan)

    def test_le_bilan_compte_les_notes_sautees(self):
        with patch(
            CIBLE_INGESTION_CAPTURE, side_effect=ingestion_simulee("text"),
        ), patch(
            CIBLE_INGESTION_FICHIER, side_effect=ingestion_simulee("text"),
        ), patch(
            CIBLE_INGESTION_TRANSCRIPTION, side_effect=ingestion_simulee("text"),
        ):
            sortie_du_premier_chargement = StringIO()
            call_command(
                "charger_fixtures_sample", "--sans-mp3",
                stdout=sortie_du_premier_chargement,
            )
            sortie_du_second_chargement = StringIO()
            call_command(
                "charger_fixtures_sample", "--sans-mp3",
                stdout=sortie_du_second_chargement,
            )

        self.assertIn(
            "Notes sautées       : 0 (déjà présentes)",
            sortie_du_premier_chargement.getvalue(),
        )
        # 5, pas 3 : les deux PDF (taches 5 et 6) partagent
        # CIBLE_INGESTION_FICHIER avec le markdown et se chargent donc
        # aussi au premier passage, puis sont sautés au second. / 5, not
        # 3: both PDF share CIBLE_INGESTION_FICHIER with the markdown.
        self.assertIn(
            "Notes sautées       : 5 (déjà présentes)",
            sortie_du_second_chargement.getvalue(),
        )
