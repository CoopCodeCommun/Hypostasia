"""
Tests de l'affichage par elements dans la lecture (BR-D).
/ Element-based reading display tests (wiring phase BR-D).

LOCALISATION : front/tests/test_lecture_elements.py

SPEC-ancrage-par-element-v2 § 9 (double moteur) + cahier
PLAN/branchement-moteur-ancrage-cahier-des-charges.md, phase BR-D :
pour une page ELEMENT, `lecture_principale` rend les blocs construits
par `construire_les_blocs_de_lecture` (front/services/rendu_elements.py)
— les marques sont posees par PORTION (`mark.portion.hl-extraction`,
markup fige par test_rendu_elements). Une page ANCIEN continue de
rendre `html_annote` / `html_readability` a l'identique.
/ ELEMENT pages render per-portion blocks; OLD pages are untouched.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import ElementDocument, Page, empreinte_du_texte
from hypostasis_extractor.models import (
    AncrageExtraction,
    ExtractedEntity,
    ExtractionJob,
)

Utilisateur = get_user_model()


class LectureParElementsTest(TestCase):
    """
    La zone de lecture selon le moteur de la page.
    / The reading zone, per page engine.
    """

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="lecteur", password="motdepasse",
        )
        self.client.force_login(self.proprietaire)

    def _creer_une_page(self, suffixe):
        return Page.objects.create(
            url=f"http://exemple.local/brd-{suffixe}",
            html_original="<p>original</p>",
            html_readability="<p>Le HTML readability de repli.</p>",
            text_readability="texte",
            content_hash=f"hash-brd-{suffixe}",
            owner=self.proprietaire,
            status="completed",

    )

    def _ajouter_un_element(self, page, texte, ordre=0, label="text",
                            masque=False):
        return ElementDocument.objects.create(
            page=page, ordre=ordre, label=label, texte=texte,
            empreinte_contenu=empreinte_du_texte(texte), masque=masque,

    )

    def _lire(self, page):
        return self.client.get(f"/lire/{page.pk}/", HTTP_HX_REQUEST="true",

    )

    def test_une_page_sans_element_rend_le_html_readability(self):
        # Aucune regression : le chemin ANCIEN est inchange.
        # / No regression on the OLD path.
        page = self._creer_une_page("ancienne")

        reponse = self._lire(page)

        self.assertEqual(reponse.status_code, 200,
        )
        contenu = reponse.content.decode()
        self.assertIn("Le HTML readability de repli.", contenu,
        )
        self.assertNotIn("blocs-elements", contenu)

    def test_une_page_element_rend_ses_blocs(self):
        # La lecture d'une page ELEMENT vient des ElementDocument, pas
        # du html_readability : titres et paragraphes avec leur balise.
        # / ELEMENT reading comes from the elements, not readability HTML.
        page = self._creer_une_page("element")
        self._ajouter_un_element(page, "Le grand titre", ordre=0, label="title")
        self._ajouter_un_element(page, "Un paragraphe de corps.", ordre=1,

        )

        reponse = self._lire(page)

        self.assertEqual(reponse.status_code, 200,
        )
        contenu = reponse.content.decode()
        self.assertIn('data-testid="blocs-elements"', contenu,
        )
        self.assertIn("Le grand titre", contenu)
        self.assertIn("Un paragraphe de corps.", contenu,
        )
        # Le HTML de repli n'est PAS rendu en double.
        # / The fallback HTML is not rendered too.
        self.assertNotIn("Le HTML readability de repli.", contenu,

    )

    def test_les_portions_sont_marquees_dans_le_texte(self):
        # Une extraction ancree sur une portion pose une marque
        # `mark.portion` sur CE passage — c'est tout l'objet du moteur.
        # / An anchored extraction marks exactly its portion.
        page = self._creer_une_page("portions")
        element = self._ajouter_un_element(
            page, "Le jugement des personnes compte beaucoup.",
        )
        job = ExtractionJob.objects.create(page=page, status="completed")
        extraction = ExtractedEntity.objects.create(
            job=job, extraction_class="principe",
            extraction_text="jugement", start_char=3, end_char=11)
        AncrageExtraction.objects.create(
            extraction=extraction, element=element,
            ordre_dans_extraction=0,
            debut_dans_element=3, fin_dans_element=11,

        )

        reponse = self._lire(page)

        contenu = reponse.content.decode()
        self.assertIn('mark class="portion hl-extraction"', contenu,
        )
        self.assertIn(f'data-extraction-id="{extraction.pk}"', contenu)

    def test_un_element_masque_n_est_pas_un_bloc_de_lecture(self):
        # Un element masque (bruit : pied de page repete...) sort du
        # TEXTE de lecture. Depuis U1 il apparait en PLACEHOLDER
        # demasquable pour qui peut ecrire (test_boutons_elements) —
        # mais jamais comme un bloc du texte.
        # / A masked element leaves the reading flow; since U1 it shows
        # as an un-hideable placeholder for writers (other test file).
        page = self._creer_une_page("masque")
        self._ajouter_un_element(page, "Contenu visible.", ordre=0)
        self._ajouter_un_element(
            page, "Pied de page repete.", ordre=1, masque=True,

        )

        reponse = self._lire(page)

        contenu = reponse.content.decode()
        self.assertIn("Contenu visible.", contenu,
        )
        self.assertNotIn('data-testid="bloc-element-1"', contenu)

    def test_le_css_neutralise_les_defauts_navigateur_de_mark(self):
        # Verif visuelle BR-D (9 aout) : sans reset, <mark> rend du
        # texte noir dur (MarkText, 1,28:1 en sombre) et un fond jaune
        # fluo (Mark) pour tout statut sans regle — dont non_pertinent
        # (4 182 extractions en base). Ce test verrouille le reset.
        # / Locks the <mark> UA-defaults reset in maquette.css.
        import re
        from pathlib import Path

        css = Path(
            "front/static/front/css/maquette.css").read_text(encoding="utf-8",
        )
        regle = re.search(
            r"mark\.hl-extraction\s*\{([^}]*)\}", css,
        )
        self.assertIsNotNone(regle, "le reset mark.hl-extraction a disparu")
        self.assertIn("color: inherit", regle.group(1),
        )
        self.assertIn("background: none", regle.group(1))

    def test_une_page_element_sans_element_retombe_sur_le_repli(self):
        # Ingestion echouee (zero element) : plutot le HTML de repli
        # qu'une page blanche — le pipeline synchrone l'a rempli (BR-B).
        # / Failed ingestion: fallback HTML beats a blank page.
        page = self._creer_une_page("vide")

        reponse = self._lire(page)

        contenu = reponse.content.decode()
        self.assertIn("Le HTML readability de repli.", contenu)
