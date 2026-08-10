"""
Tests du routage de l'import fichier vers l'ingestion Docling (BR-B).
/ File-import routing to Docling ingestion tests (wiring phase BR-B).

LOCALISATION : front/tests/test_import_docling.py

SPEC-ancrage-par-element-v2 § 9 (double moteur) + cahier des charges du
branchement (PLAN/branchement-moteur-ancrage-cahier-des-charges.md,
phase BR-B) : quand un fichier importe est d'un type que Docling sait
convertir, la vue d'import lance la tache `ingerer_un_fichier_avec_docling`
EN PLUS du pipeline synchrone existant. Le pipeline synchrone continue de
remplir html_readability : l'affichage reste celui de l'ANCIEN moteur
jusqu'a BR-D (aucune regression). Le flag ELEMENT sera pose par la tache
elle-meme (BR-A). Type non couvert (.txt) : repli ANCIEN, message honnete.
/ Covered file types ALSO launch the Docling ingestion task; the sync
pipeline keeps filling html_readability so display stays on the old
engine until BR-D. Uncovered types fall back to ANCIEN with an honest
message.
"""

import io
import json
import shutil
import tempfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from core.models import MoteurDePage, Page
from hypostasis_extractor.services.ingestion_docling import (
    fichier_couvert_par_docling,
)

Utilisateur = get_user_model()

# Un MEDIA_ROOT jetable : les fichiers importes par les tests ne doivent
# pas polluer le media du serveur de dev.
# / Throwaway MEDIA_ROOT: test uploads must not pollute dev media.
MEDIA_DE_TEST = tempfile.mkdtemp(prefix="test-import-docling-")


class CouvertureDoclingTest(SimpleTestCase):
    """
    Quels types de fichiers Docling sait convertir.
    / Which file types Docling can convert.
    """

    def test_les_types_couverts_par_docling(self):
        # Docling convertit pdf, docx, md, pptx, xlsx (SPEC-ancrage § 4).
        # / Docling handles pdf, docx, md, pptx, xlsx.
        for nom in ["a.pdf", "b.docx", "c.md", "d.pptx", "e.xlsx"]:
            self.assertTrue(fichier_couvert_par_docling(nom), nom)

    def test_les_types_non_couverts_par_docling(self):
        # Le texte brut n'a pas de structure a decouper : Docling ne le
        # prend pas. Le JSON de transcription a son propre pipeline.
        # / Plain text has no structure; transcription JSON has its own
        # pipeline.
        for nom in ["a.txt", "b.json", "sans-extension", ""]:
            self.assertFalse(fichier_couvert_par_docling(nom), nom)

    def test_la_casse_de_l_extension_ne_compte_pas(self):
        self.assertTrue(fichier_couvert_par_docling("RAPPORT.PDF"))


@override_settings(MEDIA_ROOT=MEDIA_DE_TEST)
class ImportRouteVersDoclingTest(TestCase):
    """
    La vue d'import lance l'ingestion Docling pour les types couverts.
    / The import view launches Docling ingestion for covered types.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Le repertoire media jetable est supprime a la fin de la classe :
        # rien ne s'accumule dans /tmp d'un run a l'autre (relecture BR-B).
        # / The throwaway media dir is removed after the class runs.
        cls.addClassCleanup(shutil.rmtree, MEDIA_DE_TEST, ignore_errors=True)

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="importeur", password="motdepasse",
        )
        self.client.force_login(self.proprietaire)

    def _importer(self, nom_fichier, contenu):
        return self.client.post(
            reverse("front:import-fichier"),
            {"fichier": SimpleUploadedFile(nom_fichier, contenu)},
        )

    @mock.patch(
        "hypostasis_extractor.tasks_element"
        ".ingerer_un_fichier_avec_docling.delay"
    )
    def test_un_type_couvert_lance_l_ingestion_docling(self, delay_mock):
        # Un .md est couvert : le pipeline synchrone cree la page (HTML
        # lisible tout de suite, moteur ANCIEN pour l'instant) ET la
        # tache Docling est lancee avec le fichier sauvegarde.
        # / A covered type creates the page synchronously AND launches
        # the Docling task on the saved file.
        reponse = self._importer(
            "notes.md", "# Titre\n\nUn paragraphe.".encode("utf-8"),
        )

        self.assertEqual(reponse.status_code, 200)
        page = Page.objects.get(original_filename="notes.md")

        # L'affichage ne regresse pas : le HTML de l'ancien pipeline est la.
        # / No display regression: old-pipeline HTML is present.
        self.assertIn("Un paragraphe", page.text_readability)

        # Le flag ELEMENT viendra de la tache (BR-A), pas de la vue :
        # a la creation la page est encore ANCIEN.
        # / The ELEMENT flag comes from the task, not the view.
        self.assertEqual(page.moteur, MoteurDePage.ANCIEN)

        # La vue ne passe QUE la cle primaire : c'est la tache qui resout
        # le chemin depuis page.source_file (relecture BR-B, defaut n°5 —
        # un backend de stockage sans .path ne doit pas casser la vue).
        # / The view passes only the pk; the task resolves the path.
        delay_mock.assert_called_once_with(page.pk)

        # Le toast dit honnetement ce qui se passe : le decoupage en
        # elements est lance en arriere-plan.
        # / The toast honestly says element ingestion was launched.
        declencheurs = json.loads(reponse["HX-Trigger"])
        self.assertIn("éléments", declencheurs["showToast"]["message"])

    @mock.patch(
        "hypostasis_extractor.tasks_element"
        ".ingerer_un_fichier_avec_docling.delay"
    )
    def test_un_type_non_couvert_reste_sur_l_ancien_moteur(self, delay_mock):
        # Un .txt n'est pas couvert : import comme avant, AUCUNE tache
        # Docling, et le toast ne pretend pas le contraire.
        # / A .txt imports as before, no Docling task, honest toast.
        reponse = self._importer(
            "brouillon.txt", "Du texte brut sans structure.".encode("utf-8"),
        )

        self.assertEqual(reponse.status_code, 200)
        page = Page.objects.get(original_filename="brouillon.txt")
        self.assertEqual(page.moteur, MoteurDePage.ANCIEN)

        delay_mock.assert_not_called()

        declencheurs = json.loads(reponse["HX-Trigger"])
        self.assertNotIn("éléments", declencheurs["showToast"]["message"])

    @mock.patch(
        "hypostasis_extractor.tasks_element"
        ".ingerer_un_fichier_avec_docling.delay"
    )
    def test_un_docx_reel_est_route_vers_docling(self, delay_mock):
        # Le cas nominal reel est un fichier BINAIRE (relecture BR-B,
        # defaut n°6) : un vrai .docx passe le pipeline synchrone
        # (mammoth) ET lance l'ingestion Docling.
        # / The real nominal case is a binary file: a genuine .docx.
        import docx

        document = docx.Document()
        document.add_paragraph("Un paragraphe dans un vrai docx.")
        tampon = io.BytesIO()
        document.save(tampon)

        reponse = self._importer("rapport.docx", tampon.getvalue())

        self.assertEqual(reponse.status_code, 200)
        page = Page.objects.get(original_filename="rapport.docx")
        self.assertIn("vrai docx", page.text_readability)
        delay_mock.assert_called_once_with(page.pk)

    @mock.patch(
        "hypostasis_extractor.tasks_element"
        ".ingerer_un_fichier_avec_docling.delay"
    )
    def test_un_broker_en_panne_ne_casse_pas_l_import(self, delay_mock):
        # Relecture BR-B, defaut n°2 : si le broker (Redis) est tombe,
        # `.delay` leve — l'import doit quand meme aboutir. La page est
        # deja creee et lisible (pipeline synchrone) : elle reste
        # ANCIEN, c'est le contrat du double moteur. Le toast ne promet
        # alors PAS de decoupage.
        # / A dead broker must not turn a successful import into a 500.
        delay_mock.side_effect = Exception("connexion au broker refusee")

        reponse = self._importer(
            "notes-broker.md", "# Titre\n\nParagraphe.".encode("utf-8"),
        )

        self.assertEqual(reponse.status_code, 200)
        page = Page.objects.get(original_filename="notes-broker.md")
        self.assertEqual(page.moteur, MoteurDePage.ANCIEN)

        declencheurs = json.loads(reponse["HX-Trigger"])
        self.assertNotIn("éléments", declencheurs["showToast"]["message"])

    @mock.patch(
        "hypostasis_extractor.tasks_element"
        ".ingerer_un_fichier_avec_docling.delay"
    )
    def test_une_conversion_en_echec_ne_lance_pas_docling(self, delay_mock):
        # Relecture BR-B, defaut n°6 : si le pipeline synchrone rejette
        # le fichier (ValueError -> 400), AUCUNE tache Docling ne doit
        # partir — le return du 400 precede le lancement, et ce test
        # verrouille cet ordre pour les reorganisations futures.
        # / A file rejected by the sync pipeline must never reach Docling.
        with mock.patch(
            "front.services.conversion_fichiers.convertir_fichier_en_html",
            side_effect=ValueError("fichier corrompu"),
        ):
            reponse = self._importer(
                "casse.docx", b"pas un vrai docx",
            )

        self.assertEqual(reponse.status_code, 400)
        delay_mock.assert_not_called()
        self.assertFalse(
            Page.objects.filter(original_filename="casse.docx").exists(),
        )
