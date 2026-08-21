"""
La recette d'ingestion d'une capture web : quel HTML, et quels labels.
/ The web capture ingestion recipe: which HTML, and which labels.

LOCALISATION : hypostasis_extractor/tests/test_recette_de_capture_web.py

CE QUE CES TESTS FERMENT. L'ingestion d'une capture web repartait de
`page.html_original` — `document.documentElement.outerHTML`, la page
ENTIERE. Readability tournait dans l'extension, son resultat etait
stocke dans `html_readability`... et le moteur ne le lisait jamais.

Mesure du 21 aout 2026 sur les deux captures du depot :

| page            | html_original | html_readability | elements bruts | propres |
|-----------------|---------------|------------------|----------------|---------|
| Wikipedia       | 367 161 car   | 58 123 car       | 248            | 108     |
| Monde diplo     | 107 248 car   | 19 522 car       | 150            |  26     |

Sur la page Wikipedia, l'article commencait a l'element 84 sur 245 :
34 % du document etait du sommaire et de la barre laterale AVANT le
premier mot du sujet. Et la conversion prenait 6,8 s au lieu de 0,2 s.
/ Ingestion restarted from the whole raw page; Readability's output was
stored and never read. 34 % of the Wikipedia document was navigation.

L'IRONIE QU'ON SUPPRIME AU PASSAGE : quand l'ingestion ECHOUAIT, la
lecture retombait sur `html_readability` — l'article propre. Quand elle
REUSSISSAIT, le lecteur voyait la page brute. L'echec donnait un
meilleur resultat que le succes.
/ On failure the reader fell back to the clean article; on success it
got the raw page. Failure read better than success.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import Page
from hypostasis_extractor.services.ingestion_docling import (
    LABELS_SANS_CONTENU_UTILE,
    MINIMUM_DE_TEXTE_LISIBLE,
    extraire_les_elements_bruts,
    source_html_d_une_capture,
)

Utilisateur = get_user_model()

# Un article credible : au-dela du plancher de texte lisible.
# / A credible article: above the readable-text floor.
ARTICLE_PROPRE = (
    "<h1>Un titre</h1><p>" + ("Un paragraphe de contenu reel. " * 20) + "</p>"
)

PAGE_BRUTE = (
    "<html><body><nav>Accueil Contact Mentions</nav>"
    "<aside>Sommaire</aside>" + ARTICLE_PROPRE
    + "<footer>Tous droits reserves</footer></body></html>"
)


def creer_une_capture(url, html_original, html_readability, owner=None):
    """Une capture web minimale. / A minimal web capture."""
    return Page.objects.create(
        url=url,
        title="Une capture",
        html_original=html_original,
        html_readability=html_readability,
        text_readability="",
        content_hash=f"hash-{url}",
        owner=owner,
    )


class ElementDoclingFactice:
    """
    Le strict necessaire pour traverser `extraire_les_elements_bruts`.
    / The bare minimum to walk through extraire_les_elements_bruts.

    On ne fait pas tourner Docling ici : ce test porte sur LE FILTRE,
    pas sur la conversion. Un vrai document exigerait une conversion de
    plusieurs secondes pour verifier une condition d'une ligne.
    / Docling is not run here: this test is about THE FILTER.
    """

    def __init__(self, label, texte):
        self.label = label
        self.text = texte
        self.self_ref = f"#/{label}"
        self.prov = []


class DocumentDoclingFactice:
    def __init__(self, elements):
        self._elements = elements

    def iterate_items(self):
        for element in self._elements:
            yield element, 0


class ChoixDeLaSourceTest(TestCase):
    """
    `source_html_d_une_capture` — quel HTML part chez Docling.
    / Which HTML goes to Docling.
    """

    def test_l_article_propre_est_prefere_a_la_page_brute(self):
        capture = creer_une_capture(
            "http://exemple.local/article", PAGE_BRUTE, ARTICLE_PROPRE,
        )
        html, origine = source_html_d_une_capture(capture)

        self.assertEqual(html, ARTICLE_PROPRE)
        self.assertEqual(origine, "html_readability")

    def test_sans_article_propre_on_retombe_sur_la_page_brute(self):
        """
        Readability echoue sur certaines pages et rend une chaine vide.
        Mieux vaut une page brute lisible qu'une note vide.
        / Readability fails on some pages; a raw page beats an empty note.
        """
        capture = creer_une_capture(
            "http://exemple.local/sans-readability", PAGE_BRUTE, "",
        )
        html, origine = source_html_d_une_capture(capture)

        self.assertEqual(html, PAGE_BRUTE)
        self.assertEqual(origine, "html_original")

    def test_un_article_trop_court_fait_retomber_sur_la_page_brute(self):
        """
        LE GARDE-FOU QUI EVITE DE REMPLACER DU BRUIT PAR DU VIDE.
        Readability est fait pour les ARTICLES. Sur une page d'accueil,
        un forum ou une page de resultats, il rend trois lignes de
        menu — et ingerer ca donnerait une note vide la ou la page
        brute, elle, portait quelque chose.
        / The guard that avoids replacing noise with emptiness.
        """
        miette = "<p>Accueil</p>"
        self.assertLess(len(miette), MINIMUM_DE_TEXTE_LISIBLE)

        capture = creer_une_capture(
            "http://exemple.local/accueil", PAGE_BRUTE, miette,
        )
        html, origine = source_html_d_une_capture(capture)

        self.assertEqual(html, PAGE_BRUTE)
        self.assertEqual(origine, "html_original")

    def test_une_capture_sans_aucun_html_ne_rend_rien(self):
        capture = creer_une_capture("http://exemple.local/vide", "", "")
        html, origine = source_html_d_une_capture(capture)

        self.assertEqual(html, "")
        self.assertEqual(origine, "aucune")


class FiltreDesLabelsTest(TestCase):
    """
    Les labels qui ne portent pas de contenu sont ecartes.
    / Labels carrying no content are dropped.
    """

    def test_les_widgets_d_interface_sont_ecartes(self):
        """
        LE CAS MESURE : la page Wikipedia produisait 13
        `checkbox_unselected` — les cases de repli du sommaire. Treize
        elements a commenter, a ancrer et a compter dans la couverture,
        pour des cases a cocher.
        / The measured case: 13 checkboxes from the collapsible TOC.
        """
        document = DocumentDoclingFactice([
            ElementDoclingFactice("checkbox_unselected", "Afficher"),
            ElementDoclingFactice("text", "Du vrai contenu."),
            ElementDoclingFactice("checkbox_selected", "Masquer"),
        ])
        elements = extraire_les_elements_bruts(document)

        self.assertEqual([e["texte"] for e in elements], ["Du vrai contenu."])

    def test_l_echafaudage_de_formulaire_est_ecarte(self):
        document = DocumentDoclingFactice([
            ElementDoclingFactice("form", "Rechercher"),
            ElementDoclingFactice("field_key", "Courriel"),
            ElementDoclingFactice("field_value", "vous@exemple.fr"),
            ElementDoclingFactice("text", "Le corps de l'article."),
        ])
        elements = extraire_les_elements_bruts(document)

        self.assertEqual([e["texte"] for e in elements], ["Le corps de l'article."])

    def test_le_contenu_reel_n_est_jamais_ecarte(self):
        """
        Le filtre doit rester TIMIDE. Une legende d'image est du texte
        d'auteur, une reference bibliographique aussi, un tableau porte
        des donnees : les ecarter ferait perdre du contenu citable pour
        gagner un peu de proprete.
        / The filter stays timid: captions, references and tables are
        author content.
        """
        for label_de_contenu in (
            "caption", "reference", "code", "formula", "table",
            "list_item", "section_header", "title", "text", "paragraph",
        ):
            self.assertNotIn(label_de_contenu, LABELS_SANS_CONTENU_UTILE)
