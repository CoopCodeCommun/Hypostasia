"""
Fixtures representatives du moteur ELEMENT (BR-F, SPEC § 9.4).
/ Representative fixtures for the ELEMENT engine.

LOCALISATION : hypostasis_extractor/tests/test_fixtures_representatives.py

Lancer les tests de conversion REELLE (Docling charge ses modeles,
c'est long) :
    docker exec hypostasia_dev_web python manage.py test \\
        hypostasis_extractor.tests.test_fixtures_representatives \\
        --settings=hypostasia.settings_test_fable --tag=docling

Le § 9.4 demande des documents representatifs converts par le VRAI
Docling avant la mise en production : un pad markdown (fixtures/
pad-markdown.md), un document traitement de texte avec TABLEAU
(fabrique par python-docx dans le test — pas de binaire au depot), et
le texte brut qui, lui, doit rester sur l'ancien pipeline. Le PDF a
tableaux et le verbatim diarise viendront avec leurs bascules (BR-G et
audio, decision D2). / Real-Docling conversions of representative
documents; PDF and diarised audio come with their own switches.
"""

import os
import tempfile
import unittest

from django.contrib.auth import get_user_model
from django.test import TestCase, tag

# Les conversions reelles chargent Docling : elles ne tournent QUE sur
# demande explicite (TESTS_DOCLING=1), jamais dans une suite ordinaire —
# contrainte du serveur 8 Go partage. / Real conversions only run when
# explicitly requested via TESTS_DOCLING=1.
DOCLING_DEMANDE = os.environ.get("TESTS_DOCLING") == "1"
RAISON_DU_SKIP = (
    "Conversion Docling reelle : lancer avec "
    "docker exec -e TESTS_DOCLING=1 ... --tag=docling"
)

from core.models import Page

REPERTOIRE_DES_FIXTURES = os.path.join(
    os.path.dirname(__file__), "fixtures",


)


class BaseFixturesTestCase(TestCase):
    """Socle : une page vierge par test. / A blank page per test."""

    def setUp(self):
        self.utilisateur = get_user_model().objects.create_user(
            username="testeur_fixtures", password="motdepasse",
        )
        self.page = Page.objects.create(
            url="http://exemple.local/fixture-brf",
            html_original="<p>o</p>", html_readability="<p>l</p>",
            text_readability="texte", content_hash="hash-brf",
            owner=self.utilisateur,


)


class CouvertureDesFixturesTest(BaseFixturesTestCase):
    """Ce qui route vers Docling, et ce qui n'y route pas."""

    def test_le_texte_brut_part_aussi_chez_docling(self):
        # CE TEST DISAIT L'INVERSE JUSQU'AU 21 AOUT 2026 : « le .txt n'a
        # pas de structure a decouper, il ne part JAMAIS vers Docling ».
        # Mesure faite, Docling en rend exactement les memes elements
        # qu'un .md equivalent — et une note .txt n'en avait AUCUN, donc
        # rien d'analysable, d'ancrable ni de citable.
        # / This test asserted the opposite until 21 August 2026.
        from hypostasis_extractor.services.ingestion_docling import (
            fichier_couvert_par_docling,

        )

        self.assertTrue(
            fichier_couvert_par_docling("notes-texte-brut.txt"),

    )

    def test_les_fixtures_versionnees_existent(self):
        for nom in ["pad-markdown.md", "notes-texte-brut.txt"]:
            chemin = os.path.join(REPERTOIRE_DES_FIXTURES, nom,
            )
            self.assertTrue(os.path.exists(chemin), chemin)


@tag("docling")
@unittest.skipUnless(DOCLING_DEMANDE, RAISON_DU_SKIP)
class ConversionReelleDuPadMarkdownTest(BaseFixturesTestCase):
    """
    Le pad markdown, converti par le VRAI Docling.
    / The markdown pad, through real Docling.
    """

    def test_le_pad_markdown_est_decoupe_en_elements_structures(self):
        from hypostasis_extractor.services.ingestion_docling import (
            ingerer_un_fichier,

        )

        chemin = os.path.join(REPERTOIRE_DES_FIXTURES, "pad-markdown.md")
        elements = ingerer_un_fichier(self.page, chemin,

        )

        self.page.refresh_from_db()
        self.assertTrue(self.page.elements.exists(),

        )

        labels = [element.label for element in elements]
        # Les titres du pad sont des elements de titre, pas du texte.
        # / Pad headings become title elements.
        self.assertIn("title", labels,
        )
        self.assertGreaterEqual(labels.count("section_header"), 3)
        # DECOUVERTE BR-F (documentee, pas corrigee) : le backend
        # markdown de Docling traite chaque LIGNE source comme un
        # element — un paragraphe a retours a la ligne durs se
        # fragmente, et une puce continuee sur deux lignes perd son
        # label list_item (la 3e puce du pad devient deux elements
        # text). Les pads reels sont souvent ecrits sans retour dur ;
        # consigne dans la fiche A TESTER. / Docling's md backend
        # splits on hard-wrapped lines: a two-line bullet loses its
        # list_item label. Documented reality, not a target.
        self.assertGreaterEqual(labels.count("list_item"), 2,

        )

        # Le chemin de section suit la hierarchie du pad.
        # / Section paths follow the pad hierarchy.
        elements_des_points = [
            e for e in elements if "refonte du site web" in e.texte
        ]
        self.assertEqual(len(elements_des_points), 1,
        )
        self.assertIn(
            "Points en attente",
            elements_des_points[0].chemin_de_section,

)


@tag("docling")
@unittest.skipUnless(DOCLING_DEMANDE, RAISON_DU_SKIP)
class ConversionReelleDUnDocxAvecTableauTest(BaseFixturesTestCase):
    """
    Un document traitement de texte AVEC TABLEAU, fabrique puis
    converti en reel. / A word-processor document WITH A TABLE.
    """

    def test_le_tableau_d_un_docx_devient_un_element_table(self):
        import docx

        from hypostasis_extractor.services.ingestion_docling import (
            ingerer_un_fichier,

        )

        document = docx.Document()
        document.add_heading("Budget des cercles", level=1)
        document.add_paragraph(
            "Le tableau ci-dessous recapitule les enveloppes votees.",
        )
        tableau = document.add_table(rows=3, cols=2)
        lignes = [
            ("Cercle", "Enveloppe"),
            ("Formations", "6 500 euros"),
            ("Communication", "2 000 euros"),
        ]
        for ligne, (gauche, droite) in zip(tableau.rows, lignes):
            ligne.cells[0].text = gauche
            ligne.cells[1].text = droite

        with tempfile.NamedTemporaryFile(
            suffix=".docx", delete=False) as fichier:
            document.save(fichier.name,
            )
            chemin = fichier.name

        try:
            elements = ingerer_un_fichier(self.page, chemin)
        finally:
            os.unlink(chemin,

        )

        labels = [element.label for element in elements]
        self.assertIn("table", labels,

        )

        element_tableau = next(
            e for e in elements if e.label == "table"
        )
        # Le contenu des cellules est dans le texte de l'element : les
        # extractions pourront s'y ancrer. / Cell content is anchorable.
        self.assertIn("6 500 euros", element_tableau.texte,
        )
        self.assertIn("Formations", element_tableau.texte)


@tag("docling")
@unittest.skipUnless(DOCLING_DEMANDE, RAISON_DU_SKIP)
class CaptureWebEtalonTest(TestCase):
    """
    Le contrôle de non-régression de l'extraction HTML.
    / The HTML extraction's non-regression control.

    LOCALISATION : hypostasis_extractor/tests/test_fixtures_representatives.py

    Ce compte VERROUILLE les deux correctifs du 11 août 2026 :

    - une image n'est pas un tableau : sans légende elle ne produit
      aucun bloc, au lieu du message « Image not available… » destiné au
      développeur ;
    - un gras ne coupe pas une phrase : les fragments d'un même groupe
      inline se recollent, au lieu de produire deux blocs là où l'auteur
      a écrit une phrase.

    54 éléments dont un `picture` = retour à la version d'avant les
    correctifs. Une cinquantaine de blocs tous en `text` = retour du
    découpage maison par paragraphes.
    / This count locks in the two 11 August fixes.
    """

    def test_la_capture_web_rend_vingt_huit_elements(self):
        from io import StringIO

        from django.core.management import call_command

        from core.models import ElementDocument, Page

        # Ne charge QUE la capture web : les trois autres documents
        # etalons (markdown, transcription, mp3) ne nous concernent pas
        # ici et gonfleraient le temps du test. / Only the web capture.
        call_command(
            "charger_fixtures_sample",
            "--fichier", "capture-web-badgeons-la-normandie.html",
            stdout=StringIO(),
        )

        page_de_la_capture = Page.objects.get(source_type="web")
        elements = ElementDocument.objects.filter(page=page_de_la_capture)

        self.assertEqual(elements.count(), 28)

        # Ventilation par label : le compte total seul ne suffirait pas
        # a distinguer un retour du bug d'une coincidence numerique.
        # / Per-label breakdown: the total alone could hide a regression.
        comptes_par_label = {}
        for element in elements:
            comptes_par_label[element.label] = (
                comptes_par_label.get(element.label, 0) + 1
            )

        self.assertEqual(
            comptes_par_label,
            {"section_header": 4, "list_item": 5, "text": 19},
        )

    def test_la_page_ingeree_porte_l_etat_reussie(self):
        """
        L'état d'ingestion ne peut se tester qu'ici.
        / The ingestion state can only be tested here.

        Avec Docling mocké, la tâche ne tourne pas, donc n'écrit pas
        `ingestion_etat` : un test rapide qui l'affirmerait ne
        vérifierait que son propre mock. C'est justement l'écart que
        `charger_fixtures_llm_reel` avait laissé passer — ses pages
        gardaient un état vide alors que l'écran de lecture l'affiche.
        (Cette commande a été supprimée le 15 août 2026 ; l'écart
        qu'elle illustre, lui, reste d'actualité.)
        / A mocked task writes no state; asserting it would test the mock.
        """
        from io import StringIO

        from django.core.management import call_command

        from core.models import EtatIngestion, Page

        call_command(
            "charger_fixtures_sample",
            "--fichier", "capture-web-badgeons-la-normandie.html",
            stdout=StringIO(),
        )

        page_de_la_capture = Page.objects.get(source_type="web")
        self.assertEqual(
            page_de_la_capture.ingestion_etat, EtatIngestion.REUSSIE,
        )


@tag("docling")
@unittest.skipUnless(DOCLING_DEMANDE, RAISON_DU_SKIP)
class PdfEtalonTest(TestCase):
    """
    Le premier test qui prouve l'ancrage par coordonnées de bout en bout.
    / The first test proving coordinate-based anchoring end to end.

    LOCALISATION : hypostasis_extractor/tests/test_fixtures_representatives.py

    Avant ce test, AUCUN PDF n'avait jamais été ingéré par le moteur
    ELEMENT : la base ne portait pas une seule boîte de coordonnées, et
    le visualiseur PDF ne pouvait pas être développé faute du moindre
    `page_no`. Ce compte VERROUILLE ce que la conversion réelle du
    11 août 2026 a mesuré (98 s, 2 031 Mio, voir
    tmp/benchmark-docling-2026-08-11.md) : 11 éléments, dont 2 tableaux,
    et 11 boîtes sur 11 éléments.
    / Before this test, no PDF had ever been ingested by the ELEMENT
    engine: the database carried no coordinate box at all. This count
    locks in what the real 11 August conversion measured.
    """

    def test_le_pdf_rend_onze_elements_avec_leurs_boites(self):
        from io import StringIO

        from django.core.management import call_command

        from core.models import ElementDocument, Page

        # Ne charge QUE le PDF : les autres documents etalons ne nous
        # concernent pas ici et gonfleraient le temps du test.
        # / Only the PDF: the other reference documents are irrelevant.
        call_command(
            "charger_fixtures_sample",
            "--fichier", "Etude_Epistemologique_IA.pdf",
            stdout=StringIO(),
        )

        page_du_pdf = Page.objects.get(
            original_filename="Etude_Epistemologique_IA.pdf",
        )
        elements = ElementDocument.objects.filter(page=page_du_pdf)

        self.assertEqual(elements.count(), 11)

        # Ventilation par label : le compte total seul ne dirait pas si
        # les 2 tableaux ont bien ete reconnus comme tels.
        # / Per-label breakdown: the total alone wouldn't show whether
        # the 2 tables were recognised as such.
        comptes_par_label = {}
        for element in elements:
            comptes_par_label[element.label] = (
                comptes_par_label.get(element.label, 0) + 1
            )
        self.assertEqual(comptes_par_label.get("table"), 2)

        # LE POINT DE CE TEST : chaque element porte sa provenance
        # physique — page_no ET au moins une boite. Sans elle, le
        # visualiseur PDF n'a rien a afficher. / The point of this test:
        # every element carries page_no AND at least one box.
        numeros_de_page_rencontres = set()
        for element in elements:
            self.assertIn("page_no", element.provenance)
            self.assertTrue(element.provenance.get("boites"))
            numeros_de_page_rencontres.add(element.provenance["page_no"])

        self.assertEqual(numeros_de_page_rencontres, {1, 2, 3})


@tag("docling")
@unittest.skipUnless(DOCLING_DEMANDE, RAISON_DU_SKIP)
class PdfDesOpenBadgesEtalonTest(TestCase):
    """
    Le second PDF étalon : plus lourd, sans tableau, quatre pages.
    / The second reference PDF: heavier, table-free, four pages.

    LOCALISATION : hypostasis_extractor/tests/test_fixtures_representatives.py

    Ajouté le 11 août 2026 pour éprouver le moteur d'ingestion sur un PDF
    réel plus lourd que `Etude_Epistemologique_IA.pdf`. Ce compte
    VERROUILLE la mesure de `tmp/benchmark-docling-2026-08-11.md` § 2 :
    61 éléments (`list_item` 28, `section_header` 12, `text` 21), 61/61
    avec `page_no` et boîte, sur 4 pages Docling. Contrairement à
    l'étude épistémologique (2 `table`), ce document n'en contient
    aucun — la ventilation le confirme plutôt que de le supposer.
    / Locks in the 11 August measurement: 61 elements, 61/61 with
    page_no and box, across 4 pages, no table.
    """

    def test_le_pdf_rend_soixante_et_un_elements_avec_leurs_boites(self):
        from io import StringIO

        from django.core.management import call_command

        from core.models import ElementDocument, Page

        # Ne charge QUE ce PDF : les autres documents etalons ne nous
        # concernent pas ici et gonfleraient le temps du test.
        # / Only this PDF: the other reference documents are irrelevant.
        call_command(
            "charger_fixtures_sample",
            "--fichier", "présentation des open badges.pdf",
            stdout=StringIO(),
        )

        page_du_pdf = Page.objects.get(
            original_filename="présentation des open badges.pdf",
        )
        elements = ElementDocument.objects.filter(page=page_du_pdf)

        self.assertEqual(elements.count(), 61)

        # Ventilation par label : le compte total seul ne dirait pas si
        # l'absence de tableau est bien reelle, ou une coincidence
        # numerique. / Per-label breakdown: the total alone wouldn't show
        # whether the absence of a table is real or a numeric coincidence.
        comptes_par_label = {}
        for element in elements:
            comptes_par_label[element.label] = (
                comptes_par_label.get(element.label, 0) + 1
            )
        self.assertEqual(
            comptes_par_label,
            {"list_item": 28, "section_header": 12, "text": 21},
        )

        # LE POINT DE CE TEST : chaque element porte sa provenance
        # physique — page_no ET au moins une boite, sur les 4 pages.
        # / Every element carries page_no AND at least one box, across
        # the 4 pages.
        numeros_de_page_rencontres = set()
        for element in elements:
            self.assertIn("page_no", element.provenance)
            self.assertTrue(element.provenance.get("boites"))
            numeros_de_page_rencontres.add(element.provenance["page_no"])

        self.assertEqual(numeros_de_page_rencontres, {1, 2, 3, 4})
