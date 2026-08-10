"""
Les restes § 5 du cahier de branchement, soldes en U3 :
- les cartes du panneau d'une page ELEMENT sont triees PAR ANCRE
  (element, position dans l'element), plus par start_char — qui n'est
  qu'un offset DE CHUNK pour ce moteur (entrelacement entre chunks) ;
- l'estimation du drawer d'analyse d'une page ELEMENT compte les
  chunks REELS (construire_les_chunks sur ses elements), plus un
  decoupage arithmetique de text_readability.
/ § 5 leftovers: anchor-ordered extraction cards for ELEMENT pages,
real chunk count in the cost estimate.

LOCALISATION : front/tests/test_restes_moteur_element.py
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (
    AIModel,
    Configuration,
    ElementDocument,
    MoteurDePage,
    Page,
    empreinte_du_texte,
)
from hypostasis_extractor.models import (
    AncrageExtraction,
    AnalyseurSyntaxique,
    ExtractedEntity,
    ExtractionJob,
    PromptPiece,
)

Utilisateur = get_user_model()


class BaseRestesTest(TestCase):
    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="proprio-restes", password="motdepasse",
        )
        self.client.force_login(self.proprietaire)

    def _creer_une_page(self, suffixe, moteur):
        return Page.objects.create(
            url=f"http://exemple.local/u3-{suffixe}",
            html_original="<p>o</p>",
            html_readability="<p>repli</p>",
            text_readability="x",
            content_hash=f"hash-u3-{suffixe}",
            owner=self.proprietaire, moteur=moteur,
            status="completed",
        )

    def _element(self, page, texte, ordre):
        return ElementDocument.objects.create(
            page=page, ordre=ordre, label="text", texte=texte,
            empreinte_contenu=empreinte_du_texte(texte),
        )

    def _extraction(self, page, texte, start_char):
        job = ExtractionJob.objects.create(page=page, status="completed")
        return ExtractedEntity.objects.create(
            job=job, extraction_class="principe",
            extraction_text=texte,
            start_char=start_char, end_char=start_char + len(texte),
        )

    def _ancrer(self, extraction, element, debut, fin):
        return AncrageExtraction.objects.create(
            extraction=extraction, element=element,
            ordre_dans_extraction=0,
            debut_dans_element=debut, fin_dans_element=fin,
        )


class OrdreDesCartesDuPanneauTest(BaseRestesTest):
    """Le drawer trie par ANCRE pour une page ELEMENT."""

    def test_les_cartes_element_suivent_l_ordre_du_document(self):
        # Deux extractions dont l'ordre par start_char (offsets de
        # chunks DIFFERENTS) contredit l'ordre du document : l'ecran
        # doit suivre le document. / start_char (chunk offset) says A
        # first; the document says B first — the document wins.
        page = self._creer_une_page("tri", MoteurDePage.ELEMENT)
        element_haut = self._element(page, "Premier paragraphe du texte.", 0)
        element_bas = self._element(page, "Second paragraphe du texte.", 1)

        extraction_du_bas = self._extraction(
            page, "Second", start_char=0,      # chunk 2, offset 0
        )
        self._ancrer(extraction_du_bas, element_bas, 0, 6)
        extraction_du_haut = self._extraction(
            page, "paragraphe du texte", start_char=50,   # chunk 1, offset 50
        )
        self._ancrer(extraction_du_haut, element_haut, 8, 27)

        reponse = self.client.get(
            f"/extractions/drawer_contenu/?page_id={page.pk}",
        )
        contenu = reponse.content.decode()
        position_haut = contenu.find(f'data-entity-id="{extraction_du_haut.pk}"')
        position_bas = contenu.find(f'data-entity-id="{extraction_du_bas.pk}"')
        self.assertNotEqual(position_haut, -1)
        self.assertNotEqual(position_bas, -1)
        self.assertLess(
            position_haut, position_bas,
            "l'extraction de l'element 0 doit preceder celle de l'element 1",
        )

    def test_une_extraction_sans_portion_passe_en_dernier(self):
        # Une extraction detachee (ou d'un vieux job a offsets) n'a pas
        # de place SURE dans le document : elle ferme la marche au lieu
        # de s'intercaler au hasard. / Un-anchored extractions go last.
        page = self._creer_une_page("detachee", MoteurDePage.ELEMENT)
        element = self._element(page, "Un paragraphe utile.", 0)

        extraction_sans_portion = self._extraction(page, "fantome", 0)
        extraction_ancree = self._extraction(page, "paragraphe", 30)
        self._ancrer(extraction_ancree, element, 3, 13)

        reponse = self.client.get(
            f"/extractions/drawer_contenu/?page_id={page.pk}",
        )
        contenu = reponse.content.decode()
        position_ancree = contenu.find(
            f'data-entity-id="{extraction_ancree.pk}"',
        )
        position_fantome = contenu.find(
            f'data-entity-id="{extraction_sans_portion.pk}"',
        )
        self.assertNotEqual(position_ancree, -1)
        self.assertNotEqual(position_fantome, -1)
        self.assertLess(position_ancree, position_fantome)

    def test_une_page_ancienne_reste_triee_par_start_char(self):
        # Aucune regression sur l'ANCIEN moteur : start_char y est un
        # offset de page, fiable. / OLD pages keep start_char order.
        page = self._creer_une_page("ancien", MoteurDePage.ANCIEN)
        extraction_deux = self._extraction(page, "seconde", start_char=40)
        extraction_une = self._extraction(page, "premiere", start_char=5)

        reponse = self.client.get(
            f"/extractions/drawer_contenu/?page_id={page.pk}",
        )
        contenu = reponse.content.decode()
        position_une = contenu.find(f'data-entity-id="{extraction_une.pk}"')
        position_deux = contenu.find(f'data-entity-id="{extraction_deux.pk}"')
        self.assertNotEqual(position_une, -1)
        self.assertNotEqual(position_deux, -1)
        self.assertLess(position_une, position_deux)


class EstimationDuDrawerTest(BaseRestesTest):
    """L'estimation compte les chunks REELS d'une page ELEMENT."""

    def _preparer_l_analyse(self):
        modele = AIModel.objects.create(
            name="Mock U3", model_choice="mock_default", is_active=True,
        )
        configuration = Configuration.get_solo()
        configuration.ai_active = True
        configuration.ai_model = modele
        configuration.save()
        analyseur = AnalyseurSyntaxique.objects.create(
            name="Analyseur U3", type_analyseur="analyser", is_active=True,
        )
        PromptPiece.objects.create(
            analyseur=analyseur, name="i", role="instruction",
            content="Analyse.", order=0,
        )
        return analyseur

    def test_l_estimation_element_compte_les_chunks_reels(self):
        # text_readability ne fait qu'UN caractere ; les elements, eux,
        # font 3 chunks reels (3 x 800 c, budget 1500). L'ancienne
        # estimation aurait dit 1. / Real chunking says 3, the old
        # text_readability arithmetic said 1.
        self._preparer_l_analyse()
        page = self._creer_une_page("estimation", MoteurDePage.ELEMENT)
        for ordre in range(3):
            self._element(page, "a" * 800, ordre)

        reponse = self.client.get(
            f"/lire/{page.pk}/previsualiser_analyse/",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.context["nombre_chunks_estime"], 3)

    def test_l_estimation_ancienne_est_inchangee(self):
        # ANCIEN : decoupage arithmetique de text_readability, comme
        # avant. / OLD pages keep the arithmetic estimate.
        self._preparer_l_analyse()
        page = self._creer_une_page("estim-ancien", MoteurDePage.ANCIEN)
        page.text_readability = "b" * 3200   # ceil(3200/1500) = 3
        page.save(update_fields=["text_readability"])

        reponse = self.client.get(
            f"/lire/{page.pk}/previsualiser_analyse/",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.context["nombre_chunks_estime"], 3)
