"""
Tests de l'ingestion Docling — SPEC v2 section 4 (phase D).
/ Tests for Docling ingestion — SPEC v2 section 4.

LOCALISATION : hypostasis_extractor/tests/test_ingestion_docling.py

Lancer avec :
    docker exec hypostasia_dev_web uv run python manage.py test \\
        hypostasis_extractor.tests.test_ingestion_docling

La conversion Docling elle-meme est lente (construction du pipeline).
Les tests qui l'appellent sont sautes SAUF si la variable
d'environnement TESTS_DOCLING est posee, comme les tests d'appel LLM.
Ils portent aussi le tag "docling", qui sert a les CIBLER
(`--tag=docling`) — ce n'est pas lui qui les saute, et aucun
`--exclude-tag=docling` n'existe dans le depot. Le reste — le parcours
du document, la construction des elements — est teste avec un document
simule.
/ Docling tests are skipped unless TESTS_DOCLING is set; the "docling"
tag only serves to target them, it is not what skips them.
"""

import enum
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


class CoordOriginFeinte(enum.Enum):
    """
    Imite l'enumeration CoordOrigin de docling-core.
    / Mimics docling-core's CoordOrigin enum.

    str() d'un membre d'enumeration rend "CoordOriginFeinte.BOTTOMLEFT" —
    le prefixe de classe compris. C'est exactement le defaut reproduit
    ici : Docling rend un membre, pas une chaine.
    / str() on a member includes the class prefix; that is the bug.
    """

    BOTTOMLEFT = "BOTTOMLEFT"


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

    def test_le_coord_origin_est_reduit_a_sa_valeur(self):
        """
        Docling rend un MEMBRE d'enumeration pour coord_origin, pas une
        chaine. str() dessus produit "CoordOriginFeinte.BOTTOMLEFT" — le
        prefixe de classe compris — inexploitable par un visualiseur PDF.
        C'est `.value` qu'il faut : "BOTTOMLEFT".
        / str() on the enum member leaks the class prefix; take `.value`.
        """
        boite = FausseBoite(10, 700, 500, 650)
        boite.coord_origin = CoordOriginFeinte.BOTTOMLEFT
        document = FauxDocumentDocling([
            FauxElementDocling(
                "Un paragraphe", "text",
                provenances=[FausseProvenance(1, boite)],
            ),
        ])

        elements = extraire_les_elements_bruts(document)

        self.assertEqual(
            elements[0]["provenance"]["boites"][0]["coord_origin"],
            "BOTTOMLEFT",
        )


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


class GardesFousDeConversionTest(TestCase):
    """
    La conversion est bornee (relecture BR-B, defaut n°1) : sur un
    serveur 8 Go partage avec la production, un PDF-fleuve ou une bombe
    de decompression ne doit pas pouvoir tout emporter.
    / Conversion is bounded: a huge PDF must not take the host down.
    """

    def test_la_conversion_passe_des_limites_a_docling(self):
        from unittest.mock import MagicMock, patch

        from hypostasis_extractor.services.ingestion_docling import (
            LIMITE_DE_PAGES_DOCLING,
            LIMITE_DE_TAILLE_DOCLING,
            _convertisseur_docling,
            convertir_un_fichier_avec_docling,
        )

        # Le convertisseur est mutualise (memoise au niveau du module) :
        # sans cette remise a zero, un test precedent laisse un cache
        # chaud, le patch ci-dessous ne construit plus rien, et
        # l'assertion finale tomberait sur un mock jamais appele.
        # / The converter is memoized: without this reset, a warm cache
        # from an earlier test makes the patch below a no-op.
        _convertisseur_docling.cache_clear()
        self.addCleanup(_convertisseur_docling.cache_clear)

        convertisseur = MagicMock()
        with patch(
            "docling.document_converter.DocumentConverter",
            return_value=convertisseur,
        ):
            convertir_un_fichier_avec_docling("/tmp/exemple.pdf")

        convertisseur.convert.assert_called_once_with(
            "/tmp/exemple.pdf",
            max_num_pages=LIMITE_DE_PAGES_DOCLING,
            max_file_size=LIMITE_DE_TAILLE_DOCLING,
        )

    def test_les_limites_sont_raisonnables(self):
        # Elles doivent exister et rester coherentes avec la limite
        # d'upload (50 Mo, front/serializers.py).
        # / Limits exist and stay consistent with the upload cap.
        from hypostasis_extractor.services.ingestion_docling import (
            LIMITE_DE_PAGES_DOCLING,
            LIMITE_DE_TAILLE_DOCLING,
        )

        self.assertGreaterEqual(LIMITE_DE_PAGES_DOCLING, 50)
        self.assertLessEqual(LIMITE_DE_PAGES_DOCLING, 1000)
        self.assertEqual(LIMITE_DE_TAILLE_DOCLING, 50 * 1024 * 1024)


class UnParagrapheNEstPasCoupeParUnGrasTest(TestCase):
    """
    Un `<strong>` au milieu d'une phrase ne doit pas la couper en deux.
    / A `<strong>` mid-sentence must not split it in two.

    LOCALISATION : hypostasis_extractor/tests/test_ingestion_docling.py

    Docling range les fragments d'une meme ligne dans un GROUPE INLINE :
    « Le badge permet de » et « reconnaitre » sortent comme deux items
    `text` de parent `#/groups/11`, label `GroupLabel.INLINE`.

    Les garder separes a un cout REEL, mesure sur la capture
    `sample/capture-web-badgeons-la-normandie.html` : une idee ancree sur
    cette phrase serait coupee en deux portions sans raison, et le
    compteur de la gouttiere annoncerait deux passages la ou l'auteur en
    a ecrit un seul. Le decoupage doit suivre le SENS du document, pas
    sa mise en forme.
    / Inline groups are formatting, not structure: rejoin them.
    """

    def test_les_fragments_d_un_groupe_inline_sont_recolles(self):
        document = _DocumentFeint([
            _ItemFeint("text", "Le badge permet de", parent="#/groups/11"),
            _ItemFeint("text", "reconnaître", parent="#/groups/11"),
            _ItemFeint("text", "des apprentissages.", parent="#/groups/11"),
        ], groupes_inline={"#/groups/11"})

        elements = extraire_les_elements_bruts(document)

        self.assertEqual(len(elements), 1)
        self.assertEqual(
            elements[0]["texte"], "Le badge permet de reconnaître des apprentissages.",
        )

    def test_deux_groupes_inline_restent_deux_elements(self):
        # Recoller DANS un groupe, jamais ENTRE deux : ce sont deux
        # phrases distinctes. / Join within a group, never across.
        document = _DocumentFeint([
            _ItemFeint("text", "Première phrase", parent="#/groups/11"),
            _ItemFeint("text", "en gras.", parent="#/groups/11"),
            _ItemFeint("text", "Seconde phrase", parent="#/groups/12"),
            _ItemFeint("text", "aussi.", parent="#/groups/12"),
        ], groupes_inline={"#/groups/11", "#/groups/12"})

        elements = extraire_les_elements_bruts(document)

        self.assertEqual(len(elements), 2)
        self.assertEqual(elements[0]["texte"], "Première phrase en gras.")
        self.assertEqual(elements[1]["texte"], "Seconde phrase aussi.")

    def test_un_groupe_de_liste_n_est_PAS_recolle(self):
        # Les puces d'une liste partagent aussi un parent, mais ce sont
        # des elements a part entiere — chacune a sa gouttiere et peut
        # porter sa propre idee. / List items are structure, not
        # formatting: never merge them.
        document = _DocumentFeint([
            _ItemFeint("list_item", "récepteur : à qui", parent="#/groups/3"),
            _ItemFeint("list_item", "émetteur : qui a émis", parent="#/groups/3"),
        ], groupes_inline=set())

        elements = extraire_les_elements_bruts(document)

        self.assertEqual(len(elements), 2)

    def test_un_titre_ne_se_recolle_a_rien(self):
        document = _DocumentFeint([
            _ItemFeint("section_header", "Que sont les badges ?", parent="#/groups/11"),
            _ItemFeint("text", "En 2011,", parent="#/groups/11"),
            _ItemFeint("text", "la fondation Mozilla.", parent="#/groups/11"),
        ], groupes_inline={"#/groups/11"})

        elements = extraire_les_elements_bruts(document)

        self.assertEqual(len(elements), 2)
        self.assertEqual(elements[0]["label"], "section_header")
        self.assertEqual(elements[1]["texte"], "En 2011, la fondation Mozilla.")


class UneImageNAmenePasDeMessageTechniqueTest(TestCase):
    """
    Le placeholder de Docling ne doit jamais atterrir dans le document.
    / Docling's placeholder must never reach the document.

    LOCALISATION : hypostasis_extractor/tests/test_ingestion_docling.py

    Une image n'a pas de `.text`. Le code tombait alors sur
    `export_to_markdown`, prevu pour les TABLEAUX, qui rend pour une
    image : « Image not available. Please use PdfPipelineOptions… ».

    Mesure sur `sample/capture-web-badgeons-la-normandie.html` : ce
    message destine au developpeur devenait un bloc de lecture, au
    milieu du texte que l'utilisateur lit.
    / A developer-facing message became a reading block.
    """

    def test_une_image_sans_legende_ne_produit_aucun_bloc(self):
        document = _DocumentFeint([
            _ItemFeint("text", "Avant l'image."),
            _ItemFeint("picture", None, markdown="<!-- 🖼️❌ Image not available. "
                                                 "Please use `PdfPipelineOptions`… -->"),
            _ItemFeint("text", "Après l'image."),
        ])

        elements = extraire_les_elements_bruts(document)

        self.assertEqual(len(elements), 2)
        for element in elements:
            self.assertNotIn("Image not available", element["texte"])
            self.assertNotIn("PdfPipelineOptions", element["texte"])

    def test_une_image_LEGENDEE_garde_sa_legende(self):
        # La legende, elle, est du texte d'auteur : elle reste, et elle
        # est citable. / A caption is authored text: it stays.
        document = _DocumentFeint([
            _ItemFeint("picture", None, markdown="<!-- Image not available -->",
                       legende="Courbe de participation, 2019-2026."),
        ])

        elements = extraire_les_elements_bruts(document)

        self.assertEqual(len(elements), 1)
        self.assertEqual(elements[0]["texte"], "Courbe de participation, 2019-2026.")
        self.assertEqual(elements[0]["label"], "picture")

    def test_un_tableau_est_toujours_serialise(self):
        # La serialisation markdown reste NECESSAIRE pour les tableaux :
        # eux n'ont pas de `.text` non plus, et leur contenu compte.
        # / Tables still need it: that is what it was written for.
        document = _DocumentFeint([
            _ItemFeint("table", None, markdown="| Projet | Durée |\n|---|---|\n| A | 9 ans |"),
        ])

        elements = extraire_les_elements_bruts(document)

        self.assertEqual(len(elements), 1)
        self.assertIn("Projet", elements[0]["texte"])


class _ItemFeint:
    """Un item Docling minimal. / A minimal Docling item."""

    _compteur = 0

    def __init__(self, label, texte, parent=None, markdown=None, legende=None):
        _ItemFeint._compteur += 1
        self.label = label
        self.text = texte
        self.self_ref = f"#/texts/{_ItemFeint._compteur}"
        self.parent = _RefFeinte(parent) if parent else None
        self.captions = [_LegendeFeinte(legende)] if legende else []
        self._markdown = markdown

    def export_to_markdown(self, doc=None):
        if self._markdown is None:
            raise AttributeError("pas de markdown")
        return self._markdown


class _RefFeinte:
    def __init__(self, cref):
        self.cref = cref


class _LegendeFeinte:
    def __init__(self, texte):
        self.text = texte

    def resolve(self, doc=None):
        return self


class _DocumentFeint:
    def __init__(self, items, groupes_inline=frozenset()):
        self._items = items
        self._groupes_inline = groupes_inline

    def iterate_items(self):
        for item in self._items:
            yield item, 1

    def groupe_est_inline(self, cref):
        return cref in self._groupes_inline


class ConvertisseurMutualiseTest(TestCase):
    """
    Un seul DocumentConverter par process, construit au premier besoin.
    / One DocumentConverter per process, built on first need.

    LOCALISATION : hypostasis_extractor/tests/test_ingestion_docling.py

    POURQUOI

    Construire un DocumentConverter coute 2 a 3,6 s (mesure du 14 aout
    2026 : converter neuf -> 3,09 s puis 4,96 s ; converter partage ->
    1,33 s puis 1,34 s). C'etait paye a CHAQUE ingestion, sur les deux
    portes d'entree — le fichier et la capture web.
    / Building a converter costs 2-3.6 s, paid on every single ingestion.

    LE PIEGE DU POOL PREFORK

    Celery prefork duplique le process du worker. Un objet Docling
    construit dans le PARENT serait herite par tous les enfants : des
    modeles torch partages par copie-sur-ecriture entre process, ce que
    torch ne garantit pas. La memoisation est donc PARESSEUSE — rien
    n'est construit tant qu'aucune conversion n'est demandee, et le fork
    a lieu bien avant la premiere tache. Chaque enfant construit ensuite
    le sien, dans son propre espace memoire.
    / Nothing is built at import time, so nothing is inherited across
    the fork; each child builds its own afterwards.
    """

    def setUp(self):
        from hypostasis_extractor.services.ingestion_docling import (
            _convertisseur_docling,
        )

        # Chaque test part d'un cache froid, et le laisse froid en
        # partant : un converter reel oublie ici rendrait muets les
        # patches des tests suivants.
        # / Cold cache in, cold cache out.
        _convertisseur_docling.cache_clear()
        self.addCleanup(_convertisseur_docling.cache_clear)

    def test_deux_conversions_de_fichier_ne_construisent_qu_un_convertisseur(self):
        from unittest.mock import MagicMock, patch

        from hypostasis_extractor.services.ingestion_docling import (
            convertir_un_fichier_avec_docling,
        )

        convertisseur = MagicMock()
        with patch(
            "docling.document_converter.DocumentConverter",
            return_value=convertisseur,
        ) as fabrique_de_convertisseur:
            convertir_un_fichier_avec_docling("/tmp/premier.pdf")
            convertir_un_fichier_avec_docling("/tmp/second.pdf")

        self.assertEqual(fabrique_de_convertisseur.call_count, 1)
        # Le convertisseur est partage, mais les deux documents sont bien
        # convertis : mutualiser n'est pas sauter un appel.
        # / Sharing the converter must not skip a conversion.
        self.assertEqual(convertisseur.convert.call_count, 2)

    def test_la_capture_web_partage_le_convertisseur_du_fichier(self):
        from unittest.mock import MagicMock, patch

        from hypostasis_extractor.services.ingestion_docling import (
            convertir_du_html_avec_docling,
            convertir_un_fichier_avec_docling,
        )

        # Les deux portes d'entree (fichier et HTML capture) doivent
        # tirer le MEME convertisseur : en poser un sur une seule
        # laisserait la moitie du gain.
        # / Both entry points must share it, or half the gain is lost.
        convertisseur = MagicMock()
        with patch(
            "docling.document_converter.DocumentConverter",
            return_value=convertisseur,
        ) as fabrique_de_convertisseur:
            convertir_un_fichier_avec_docling("/tmp/un.pdf")
            convertir_du_html_avec_docling("<p>une capture</p>")

        self.assertEqual(fabrique_de_convertisseur.call_count, 1)
        self.assertEqual(convertisseur.convert.call_count, 2)

    def test_le_bootstrap_celery_n_importe_jamais_docling(self):
        """
        L'invariant qui rend le partage sur pour le pool prefork.
        / The invariant that makes sharing prefork-safe.

        LOCALISATION : hypostasis_extractor/tests/test_ingestion_docling.py

        CE QU'IL FAUT OBSERVER, ET CE QU'IL NE FAUT PAS

        Une premiere version de ce test lisait `cache_info().currsize`.
        Elle ne prouvait rien : un `DocumentConverter()` construit par
        n'importe quel AUTRE chemin laisse ce compteur a zero. Verifie
        en injectant la violation — le test restait vert (relecture
        adverse du 14 aout 2026).

        Ce qu'on observe donc, c'est `sys.modules` : construire un
        convertisseur exige d'importer `docling`, quel que soit le
        chemin emprunte. Le module absent, aucun convertisseur ne peut
        exister. / Watch sys.modules, not the cache counter: building a
        converter requires importing docling by ANY path.

        LE MOMENT QU'ON REPRODUIT

        Pas un simple import du service : le fork a lieu au bootstrap de
        `celery -A hypostasia worker`, qui importe TOUS les modules de
        taches via l'autodiscover. C'est ce graphe-la qu'il faut
        parcourir — `import_default_modules()` le fait — sans quoi le
        test ne visite jamais `tasks_element.py`.
        / The fork happens after Celery's autodiscover; that is the
        import graph to walk.

        Le tout dans un process NEUF : dans celui des tests, docling a
        deja pu etre importe par un autre test.
        / In a fresh process: this one may already have imported docling.
        """
        import subprocess
        import sys

        programme = (
            "import sys, django;"
            "django.setup();"
            "from hypostasia.celery import celery_app;"
            "celery_app.loader.import_default_modules();"
            "print(int('docling' in sys.modules))"
        )
        resultat = subprocess.run(
            [sys.executable, "-c", programme],
            capture_output=True, text=True, timeout=120,
            cwd=os.getcwd(),
            env={**os.environ, "PYTHONPATH": os.getcwd()},
        )

        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        self.assertEqual(
            resultat.stdout.strip(), "0",
            "Le bootstrap de Celery importe docling : un convertisseur "
            "pourrait alors etre construit AVANT le fork, et hérité par "
            "tous les enfants du pool — avec ses threads onnxruntime et "
            "OpenMP, ce qui bloque classiquement au fork.",
        )
