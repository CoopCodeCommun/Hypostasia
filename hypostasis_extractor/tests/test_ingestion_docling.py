"""
Tests de l'ingestion Docling — SPEC v2 section 4 (phase D).
/ Tests for Docling ingestion — SPEC v2 section 4.

LOCALISATION : hypostasis_extractor/tests/test_ingestion_docling.py

Lancer avec :
    docker exec hypostasia_dev_web uv run python manage.py test \\
        hypostasis_extractor.tests.test_ingestion_docling

La conversion Docling elle-meme est lente (chargement de modeles). Les
tests qui l'appellent portent le tag "docling" et sont ignores par defaut,
comme les tests d'appel LLM. Le reste — le parcours du document, la
construction des elements — est teste avec un document simule.
/ Docling conversion is slow; those tests are tagged and opt-in.
"""

import os

from django.test import TestCase, tag

from core.models import ElementDocument, Page, empreinte_du_texte
from hypostasis_extractor.services.ingestion_docling import (
    LABELS_SANS_CONTENU_UTILE,
    creer_les_elements_d_une_page,
    extraire_les_elements_bruts,
)


class FauxElementDocling:
    """
    Imite un element rendu par Docling.
    / Mimics an element returned by Docling.
    """

    def __init__(self, texte, label, self_ref="#/texts/0", provenances=None):
        self.text = texte
        self.label = label
        self.self_ref = self_ref
        self.prov = provenances or []


class FausseBoite:
    def __init__(self, gauche, haut, droite, bas):
        self.l = gauche
        self.t = haut
        self.r = droite
        self.b = bas
        self.coord_origin = "BOTTOMLEFT"


class FausseProvenance:
    def __init__(self, page_no, boite):
        self.page_no = page_no
        self.bbox = boite


class FauxDocumentDocling:
    """Imite un DoclingDocument. / Mimics a DoclingDocument."""

    def __init__(self, elements):
        self._elements = elements

    def iterate_items(self):
        for element in self._elements:
            yield element, 0


class ParcoursDuDocumentTest(TestCase):
    """
    Le parcours d'un document Docling, sans appeler Docling.
    / Walking a Docling document, without calling Docling.
    """

    def test_les_elements_sont_rendus_dans_l_ordre(self):
        document = FauxDocumentDocling([
            FauxElementDocling("Un titre", "title"),
            FauxElementDocling("Un paragraphe", "text"),
            FauxElementDocling("Une puce", "list_item"),
        ])

        elements = extraire_les_elements_bruts(document)

        self.assertEqual(
            [element["texte"] for element in elements],
            ["Un titre", "Un paragraphe", "Une puce"],
        )
        self.assertEqual(
            [element["label"] for element in elements],
            ["title", "text", "list_item"],
        )

    def test_le_chemin_de_section_suit_les_titres(self):
        """
        Chaque element note les titres sous lesquels il se trouve, au
        moment de l'ingestion.
        / Each element records the titles it sits under, at ingestion time.
        """
        document = FauxDocumentDocling([
            FauxElementDocling("Charte de gouvernance", "title"),
            FauxElementDocling("Ce que l'IA ne remplace pas", "section_header"),
            FauxElementDocling("Un paragraphe", "text"),
            FauxElementDocling("Les principes", "section_header"),
            FauxElementDocling("Un autre paragraphe", "text"),
        ])

        elements = extraire_les_elements_bruts(document)

        self.assertEqual(
            elements[2]["chemin_de_section"],
            ["Charte de gouvernance", "Ce que l'IA ne remplace pas"],
        )
        # Le second sous-titre remplace le premier, il ne s'empile pas.
        # / The second header replaces the first, it does not stack.
        self.assertEqual(
            elements[4]["chemin_de_section"],
            ["Charte de gouvernance", "Les principes"],
        )

    def test_les_elements_sans_contenu_utile_sont_ecartes(self):
        """
        Un pied de page repete a chaque page n'a pas a etre extrait, ni a
        recevoir des commentaires.
        / A repeated page footer must not be extracted nor commented.
        """
        document = FauxDocumentDocling([
            FauxElementDocling("Un vrai paragraphe", "text"),
            FauxElementDocling("Page 3 sur 12", "page_footer"),
            FauxElementDocling("Titre courant du document", "page_header"),
            FauxElementDocling("Une note de bas de page", "footnote"),
        ])

        elements = extraire_les_elements_bruts(document)

        self.assertEqual(len(elements), 1)
        self.assertEqual(elements[0]["texte"], "Un vrai paragraphe")

    def test_les_elements_vides_sont_ecartes(self):
        """Un element sans texte n'a rien a ancrer."""
        document = FauxDocumentDocling([
            FauxElementDocling("Un vrai paragraphe", "text"),
            FauxElementDocling("   ", "text"),
            FauxElementDocling("", "text"),
        ])

        elements = extraire_les_elements_bruts(document)

        self.assertEqual(len(elements), 1)

    def test_la_reference_docling_est_notee_sans_etre_une_cle(self):
        """
        Le self_ref est un numero de position : il glisserait si le
        document changeait. On le garde pour information seulement.
        / self_ref is positional; kept for information only.
        """
        document = FauxDocumentDocling([
            FauxElementDocling("Un paragraphe", "text", self_ref="#/texts/4"),
        ])

        elements = extraire_les_elements_bruts(document)

        self.assertEqual(elements[0]["reference_docling"], "#/texts/4")


class ProvenancePhysiqueTest(TestCase):
    """
    La provenance PDF : page et boites.
    / PDF provenance: page and boxes.
    """

    def test_un_markdown_n_a_pas_de_provenance(self):
        document = FauxDocumentDocling([
            FauxElementDocling("Un paragraphe", "text"),
        ])

        elements = extraire_les_elements_bruts(document)

        self.assertEqual(elements[0]["provenance"], {})

    def test_une_boite_pdf_est_conservee(self):
        document = FauxDocumentDocling([
            FauxElementDocling(
                "Un paragraphe", "text",
                provenances=[
                    FausseProvenance(3, FausseBoite(10, 700, 500, 650)),
                ],
            ),
        ])

        elements = extraire_les_elements_bruts(document)

        provenance = elements[0]["provenance"]
        self.assertEqual(provenance["page_no"], 3)
        self.assertEqual(len(provenance["boites"]), 1)
        self.assertEqual(provenance["boites"][0]["l"], 10)
        self.assertEqual(provenance["boites"][0]["page_no"], 3)

    def test_un_paragraphe_a_cheval_garde_ses_deux_boites(self):
        """
        Un paragraphe a cheval sur deux colonnes ou deux pages a plusieurs
        provenances. Chacune garde SON numero de page, sinon le surlignage
        dessinerait les boites de la page 2 sur la page 1.
        / Each box keeps ITS page number, or highlighting draws on the wrong page.
        """
        document = FauxDocumentDocling([
            FauxElementDocling(
                "Un paragraphe a cheval", "text",
                provenances=[
                    FausseProvenance(3, FausseBoite(10, 100, 300, 50)),
                    FausseProvenance(4, FausseBoite(10, 750, 300, 700)),
                ],
            ),
        ])

        elements = extraire_les_elements_bruts(document)

        boites = elements[0]["provenance"]["boites"]
        self.assertEqual(len(boites), 2)
        self.assertEqual(boites[0]["page_no"], 3)
        self.assertEqual(boites[1]["page_no"], 4)


class CreationDesElementsTest(TestCase):
    """
    La creation des ElementDocument en base.
    / Creating the ElementDocument rows.
    """

    def setUp(self):
        self.page_de_test = Page.objects.create(
            url="http://exemple.local/page-ingestion",
            html_original="x", html_readability="x", text_readability="x",
            content_hash="empreinte_ingestion",
        )

    def test_les_elements_sont_crees_dans_l_ordre(self):
        elements_bruts = [
            {"texte": "Premier", "label": "text"},
            {"texte": "Deuxieme", "label": "list_item"},
        ]

        elements_crees = creer_les_elements_d_une_page(
            self.page_de_test, elements_bruts,
        )

        self.assertEqual(len(elements_crees), 2)
        self.assertEqual(
            [element.ordre for element in elements_crees], [0, 1],
        )
        self.assertEqual(elements_crees[1].label, "list_item")

    def test_l_empreinte_est_calculee(self):
        """
        Sans empreinte, la re-ingestion ne pourrait reconnaitre aucun
        element inchange. / Without it, re-ingestion recognizes nothing.
        """
        creer_les_elements_d_une_page(
            self.page_de_test, [{"texte": "Un paragraphe", "label": "text"}],
        )

        element = self.page_de_test.elements.get()
        self.assertEqual(
            element.empreinte_contenu, empreinte_du_texte("Un paragraphe"),
        )

    def test_ingerer_deux_fois_est_refuse(self):
        """
        Une seconde ingestion ecraserait les ancres existantes. Il faut
        passer par la re-ingestion, qui reconnait les elements inchanges.
        / A second ingestion would wipe existing anchors.
        """
        creer_les_elements_d_une_page(
            self.page_de_test, [{"texte": "Un paragraphe", "label": "text"}],
        )

        with self.assertRaises(ValueError):
            creer_les_elements_d_une_page(
                self.page_de_test, [{"texte": "Un autre", "label": "text"}],
            )

    def test_chaque_element_recoit_un_identifiant_stable(self):
        creer_les_elements_d_une_page(self.page_de_test, [
            {"texte": "Premier", "label": "text"},
            {"texte": "Deuxieme", "label": "text"},
        ])

        identifiants = [
            element.identifiant_stable
            for element in self.page_de_test.elements.all()
        ]
        self.assertEqual(len(set(identifiants)), 2)


@tag("docling")
class ConversionDoclingReelleTest(TestCase):
    """
    La vraie conversion Docling, sur un fichier.
    / The real Docling conversion, on a file.

    LOCALISATION : hypostasis_extractor/tests/test_ingestion_docling.py

    Ignoree par defaut : Docling charge des modeles lourds au premier
    import, ce qui prendrait plusieurs secondes a chaque lancement de la
    suite. Pour la lancer :

        docker exec -e TESTS_DOCLING=1 hypostasia_dev_web \\
            uv run python manage.py test hypostasis_extractor --tag=docling
    / Opt-in: Docling loads heavy models on first import.
    """

    FICHIER_DE_TEST = "/app/tmp/docling_essai/essai.md"

    def setUp(self):
        if not os.environ.get("TESTS_DOCLING"):
            self.skipTest(
                "TESTS_DOCLING non definie : conversion Docling ignoree.",
            )
        if not os.path.exists(self.FICHIER_DE_TEST):
            self.skipTest(f"Fichier de test absent : {self.FICHIER_DE_TEST}")

        self.page_de_test = Page.objects.create(
            url="http://exemple.local/page-docling-reel",
            html_original="x", html_readability="x", text_readability="x",
            content_hash="empreinte_docling_reel",
        )

    def test_un_markdown_donne_les_bons_labels(self):
        """
        Docling doit rendre les labels que le chunking et l'affichage
        attendent : title, section_header, text, list_item, table.
        / Docling must return the labels chunking and display expect.
        """
        from hypostasis_extractor.services.ingestion_docling import (
            ingerer_un_fichier,
        )

        elements = ingerer_un_fichier(self.page_de_test, self.FICHIER_DE_TEST)

        labels_rendus = {element.label for element in elements}
        self.assertIn("title", labels_rendus)
        self.assertIn("section_header", labels_rendus)
        self.assertIn("list_item", labels_rendus)

    def test_un_tableau_n_est_pas_perdu(self):
        """
        Un tableau n'a pas d'attribut texte : son contenu est dans sa
        structure. Sans serialisation, il arriverait vide et tout son
        contenu serait perdu pour l'analyse.
        / Without serialization, a table would arrive empty.
        """
        from hypostasis_extractor.services.ingestion_docling import (
            ingerer_un_fichier,
        )

        elements = ingerer_un_fichier(self.page_de_test, self.FICHIER_DE_TEST)

        elements_tableaux = [e for e in elements if e.label == "table"]
        self.assertGreater(len(elements_tableaux), 0, "aucun tableau ingere")
        for element in elements_tableaux:
            self.assertNotEqual(element.texte.strip(), "")
            # Le contenu des cellules doit s'y retrouver.
            # / The cell content must be in there.
            self.assertIn("Principe", element.texte)
