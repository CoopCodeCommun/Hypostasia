"""
Tests du routage de l'import fichier vers l'ingestion Docling (BR-B).
/ File-import routing to Docling ingestion tests (wiring phase BR-B).

LOCALISATION : front/tests/test_import_docling.py

La vue d'import ne convertit rien. Elle enregistre le fichier, cree la
note, et confie son decoupage a la file `ingestion_docling` — servie par
un worker a concurrence 1, pour que deux conversions ne chargent jamais
leurs modeles en meme temps.
/ The import view converts nothing: it stores the file, creates the note,
and hands the cutting to the concurrency-1 Docling queue.

CE FICHIER A DECRIT UN DOUBLE MOTEUR JUSQU'AU 21 AOUT 2026. La vue
convertissait le fichier DANS la requete HTTP — MarkItDown pour les PDF,
mammoth pour les DOCX — pour remplir `html_readability` et donner a lire
tout de suite, PUIS lancait Docling. Deux rendus du meme fichier, dont un
etait remplace par l'autre quelques secondes plus tard, et qui ne
disaient pas la meme chose : 6 426 caracteres contre 8 770 sur le PDF
etalon. Surtout, le rendu synchrone ne produisait aucun `ElementDocument`
— donc rien d'ancrable, rien d'analysable, rien de citable.
/ This file described a double engine until 21 August 2026: two renderings
of the same file, one replaced by the other, and only one of them usable.

Detail et mesures :
`CHANGELOG/2026-08-21-un-seul-moteur-d-ingestion.md`.
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

from core.models import Dossier, Page
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
        # Docling convertit pdf, docx, md, txt, pptx, xlsx.
        #
        # LE `.txt` A REJOINT LA LISTE LE 21 AOUT 2026. Il en etait
        # exclu au motif qu'« il n'a pas de structure a decouper » :
        # mesure faite, Docling en rend exactement les memes elements
        # que du `.md` equivalent, et une note `.txt` avait donc ZERO
        # element — impossible a analyser, a ancrer ou a citer.
        # / .txt joined the list: Docling yields the same elements as
        # the equivalent .md, and text notes had zero elements.
        for nom in ["a.pdf", "b.docx", "c.md", "d.txt", "e.pptx", "f.xlsx"]:
            self.assertTrue(fichier_couvert_par_docling(nom), nom,

    )

    def test_les_types_non_couverts_par_docling(self):
        # Le JSON de transcription a son propre pipeline, qui sait ce
        # qu'est un tour de parole. Docling n'a rien a y faire.
        # / Transcription JSON has its own pipeline, which knows what a
        # speaking turn is.
        for nom in ["b.json", "sans-extension", ""]:
            self.assertFalse(fichier_couvert_par_docling(nom), nom,

    )

    def test_la_casse_de_l_extension_ne_compte_pas(self):
        self.assertTrue(fichier_couvert_par_docling("RAPPORT.PDF"),

)


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
        cls.addClassCleanup(shutil.rmtree, MEDIA_DE_TEST, ignore_errors=True,

    )

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="importeur", password="motdepasse",
        )
        self.client.force_login(self.proprietaire)
        self.carnet = Dossier.objects.create(
            name="Carnet d'import", owner=self.proprietaire,
        )

    def _importer(self, nom_fichier, contenu):
        # LE CARNET EST OBLIGATOIRE depuis le 21 aout 2026 : le serveur
        # n'a plus de destination par defaut, les deux fourre-tout ont
        # ete supprimes. Un import sans `dossier_id` rend 400.
        # / The notebook is mandatory: no default destination remains.
        return self.client.post(
            reverse("front:import-fichier"),
            {
                "fichier": SimpleUploadedFile(nom_fichier, contenu),
                "dossier_id": self.carnet.pk,
            },
)

    @mock.patch(
        "hypostasis_extractor.tasks_element"
        ".ingerer_un_fichier_avec_docling.delay"
    )
    def test_un_type_couvert_lance_l_ingestion_docling(self, delay_mock):
        # Un .md est couvert : la vue cree la note et confie TOUT le
        # decoupage a la file. Elle ne convertit plus rien elle-meme.
        # / A covered type: the view creates the note and hands all the
        # cutting to the queue. It converts nothing itself.
        reponse = self._importer(
            "notes.md", "# Titre\n\nUn paragraphe.".encode("utf-8"))

        self.assertEqual(reponse.status_code, 200,
        )
        page = Page.objects.get(original_filename="notes.md")

        # AUCUN RENDU PROVISOIRE. La vue convertissait le fichier DANS
        # la requete HTTP (MarkItDown pour les PDF, mammoth pour les
        # DOCX) pour remplir l'ecran pendant l'attente. Ce rendu-la etait
        # remplace par celui de Docling quelques secondes plus tard, et
        # les deux ne disaient pas la meme chose : 6 426 caracteres
        # contre 8 770 sur le PDF etalon, mesure du 21 aout 2026.
        # L'archive d'un import, c'est le FICHIER.
        # / No provisional rendering: it was replaced by Docling's and
        # the two disagreed. An import's archive is the FILE.
        self.assertEqual(page.html_original, "")
        self.assertEqual(page.html_readability, "")
        self.assertEqual(page.text_readability, "")
        self.assertTrue(page.source_file)

        # Les elements viennent de la tache, pas de la vue.
        # / Elements come from the task, not from the view.
        self.assertFalse(page.elements.exists(),

        )

        # La vue ne passe QUE la cle primaire : c'est la tache qui resout
        # le chemin depuis page.source_file (relecture BR-B, defaut n°5 —
        # un backend de stockage sans .path ne doit pas casser la vue).
        # / The view passes only the pk; the task resolves the path.
        delay_mock.assert_called_once_with(page.pk,

        )

        # Le toast dit honnetement ce qui se passe : le decoupage en
        # elements est lance en arriere-plan.
        # / The toast honestly says element ingestion was launched.
        declencheurs = json.loads(reponse["HX-Trigger"],
        )
        self.assertIn("éléments", declencheurs["showToast"]["message"])

    @mock.patch(
        "hypostasis_extractor.tasks_element"
        ".ingerer_un_fichier_avec_docling.delay"
    )
    def test_un_texte_brut_part_aussi_au_decoupage(self, delay_mock):
        # CE TEST DISAIT L'INVERSE JUSQU'AU 21 AOUT 2026. Il s'appelait
        # « reste sur l'ancien moteur » et verrouillait le fait qu'un
        # .txt n'ait AUCUN element. Or une note sans element ne peut
        # etre ni analysee (`analyse_par_element` sort aussitot), ni
        # ancree, ni citee : elle etait lisible et morte. Docling avale
        # un .txt et en rend les memes elements qu'un .md equivalent.
        # / This test asserted the opposite until 21 August 2026: a
        # text note had zero elements — readable and dead.
        reponse = self._importer(
            "brouillon.txt", "Du texte brut.\n\nEt deux paragraphes.".encode("utf-8"),

        )

        self.assertEqual(reponse.status_code, 200)
        page = Page.objects.get(original_filename="brouillon.txt",
        )

        delay_mock.assert_called_once_with(page.pk)

        declencheurs = json.loads(reponse["HX-Trigger"],
        )
        self.assertIn("éléments", declencheurs["showToast"]["message"])

    @mock.patch(
        "hypostasis_extractor.tasks_element"
        ".ingerer_un_fichier_avec_docling.delay"
    )
    def test_un_docx_reel_est_route_vers_docling(self, delay_mock):
        # Le cas nominal reel est un fichier BINAIRE (relecture BR-B,
        # defaut n°6) : un vrai .docx est enregistre tel quel et son
        # decoupage part en file.
        # / The real nominal case is a binary file: a genuine .docx.
        import docx

        document = docx.Document()
        document.add_paragraph("Un paragraphe dans un vrai docx.",
        )
        tampon = io.BytesIO()
        document.save(tampon,

        )

        reponse = self._importer("rapport.docx", tampon.getvalue())

        self.assertEqual(reponse.status_code, 200,
        )
        page = Page.objects.get(original_filename="rapport.docx")
        # CE TEST LISAIT LE TEXTE DE MAMMOTH. La vue convertissait le
        # .docx dans la requete ; elle enregistre desormais le FICHIER et
        # confie le texte a Docling. Ce qu'on verifie ici, c'est donc que
        # le binaire est bien arrive jusqu'a la file — pas ce qu'une
        # conversion synchrone en avait tire.
        # / This test read mammoth's text; the view now stores the FILE
        # and hands the text to Docling.
        self.assertTrue(page.source_file)
        self.assertEqual(page.text_readability, "")
        delay_mock.assert_called_once_with(page.pk,
)

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
        delay_mock.side_effect = Exception("connexion au broker refusee",

        )

        reponse = self._importer(
            "notes-broker.md", "# Titre\n\nParagraphe.".encode("utf-8"))

        self.assertEqual(reponse.status_code, 200,
        )
        page = Page.objects.get(original_filename="notes-broker.md")
        self.assertFalse(page.elements.exists(),

        )

        declencheurs = json.loads(reponse["HX-Trigger"])
        self.assertNotIn("éléments", declencheurs["showToast"]["message"],
)

    @mock.patch(
        "hypostasis_extractor.tasks_element"
        ".ingerer_un_fichier_avec_docling.delay"
    )
    def test_un_fichier_refuse_ne_lance_pas_docling(self, delay_mock):
        # UN FICHIER REJETE NE DOIT JAMAIS ATTEINDRE DOCLING, et ce test
        # verrouille cet ordre pour les reorganisations futures.
        #
        # LE REJET A CHANGE DE MAIN le 21 aout 2026. Il venait du
        # pipeline synchrone, qui levait une ValueError sur une
        # extension inconnue ; ce pipeline a disparu avec MarkItDown et
        # mammoth. C'est desormais le serializer d'import qui refuse, en
        # amont — la seule validation d'entree, comme partout ailleurs.
        # / The rejection moved: the sync pipeline is gone, the import
        # serializer refuses upstream.
        reponse = self._importer(
            "tableur.ods", b"pas un format accepte",

        )

        self.assertEqual(reponse.status_code, 400)
        delay_mock.assert_not_called()
        self.assertFalse(
            Page.objects.filter(original_filename="tableur.ods").exists())
