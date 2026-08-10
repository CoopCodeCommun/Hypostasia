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

    def test_le_texte_brut_reste_sur_l_ancien_pipeline(self):
        # Le .txt n'a pas de structure a decouper : il ne part JAMAIS
        # vers Docling (BR-B). / Plain text never goes to Docling.
        from hypostasis_extractor.services.ingestion_docling import (
            fichier_couvert_par_docling,

        )

        self.assertFalse(
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
