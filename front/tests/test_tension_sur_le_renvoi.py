"""
Le renvoi [N] change de couleur quand les juges se contredisent.
/ The [N] reference changes colour when judges disagree.

LOCALISATION : front/tests/test_tension_sur_le_renvoi.py

CE QU'IL PORTE, ET CE QU'IL NE PORTE PAS. Le renvoi ne dit PAS le
degre — aucun chiffre dans le corps de l'article
(`PRESENTATION-V3.md` § 3.6). Il dit une seule chose : les quatre juges
locaux confirment-ils le juge de production, ou le dementent-ils ?

MESURE DU 20 AOUT 2026, sur 209 citations reelles : la contradiction
franche touche **16 citations, soit 7,7 %**. Assez rare pour se
remarquer, assez frequent pour se rencontrer — et actionnable : le
lecteur ouvre la preuve.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (
    AvisDeVerification, EtatDeVerification, Page, SourceLink, TypeDeNote,
    TypeLien,
)
from front.views_synthese import _html_avec_renvois


class LeRenvoiSignaleLaTensionEntreLesJuges(TestCase):
    """Une couleur, pas un chiffre. / A colour, never a number."""

    def setUp(self):
        from hypostasis_extractor.models import ExtractedEntity, ExtractionJob

        self.utilisateur = get_user_model().objects.create_user(
            username="lecteur", password="motdepasse",
        )
        note = Page.objects.create(
            title="Note", owner=self.utilisateur, type_de_note=TypeDeNote.NOTE,
        )
        job = ExtractionJob.objects.create(page=note, status="completed")
        self.extraction = ExtractedEntity.objects.create(
            job=job, extraction_text="un passage", extraction_class="hypostase",
            start_char=0, end_char=10,
        )

    def _article(self, degre_de_production, scores_locaux):
        """Un article d'un paragraphe, cite une fois, note. / One para."""
        texte = f"Une affirmation sourcée [[ext:{self.extraction.pk}]]."
        article = Page.objects.create(
            title="Wiki", owner=self.utilisateur, type_de_note=TypeDeNote.WIKI,
            text_readability=texte,
        )
        lien = SourceLink.objects.create(
            page_cible=article, extraction_source=self.extraction,
            type_lien=TypeLien.CITE,
            start_char_cible=0, end_char_cible=len(texte),
            score_de_verification=degre_de_production,
            etat_de_verification=EtatDeVerification.FAIBLE,
        )
        for numero, score in enumerate(scores_locaux):
            AvisDeVerification.objects.create(
                lien=lien, methode=f"juge {numero}", score=score, seuil=50.0,
            )
        return article

    def test_les_juges_qui_DEMENTENT_colorent_le_renvoi(self):
        """
        Le juge de production doute (cran 40), les locaux rehabilitent
        franchement. C'est le seul cas qui merite d'attirer l'oeil.
        """
        article = self._article(40.0, [95.0, 95.0, 95.0])

        html = _html_avec_renvois(article)

        self.assertIn('data-accord-local="tension"', html)

    def test_les_juges_qui_CONFIRMENT_ne_colorent_rien_de_special(self):
        """Le cas ordinaire ne doit pas attirer l'oeil."""
        article = self._article(70.0, [95.0, 95.0, 95.0])

        html = _html_avec_renvois(article)

        self.assertIn('data-accord-local="accord"', html)
        self.assertNotIn('data-accord-local="tension"', html)

    def test_sans_avis_local_le_renvoi_ne_dit_RIEN(self):
        """
        Affirmer l'accord quand personne n'a controle serait mentir.
        16 citations sur 225 sont dans ce cas.
        / Claiming agreement where nobody checked would be a lie.
        """
        article = self._article(70.0, [])

        html = _html_avec_renvois(article)

        self.assertNotIn("data-accord-local", html)

    def test_la_tension_est_DITE_au_lecteur_d_ecran(self):
        """
        UNE COULEUR NE SE LIT PAS TOUTE SEULE (recette F6). Un signal
        porte par la seule couleur est invisible aux lecteurs d'ecran et
        aux daltoniens — et vert/ambre est justement un axe rouge-vert.
        / A colour alone is unreadable: green/amber is a red-green axis.
        """
        article = self._article(40.0, [95.0, 95.0, 95.0])

        html = _html_avec_renvois(article)

        self.assertIn("contrôleurs", html.lower())

    def test_le_renvoi_ne_porte_TOUJOURS_aucun_chiffre(self):
        """
        L'interdit du § 3.6 tient : la couleur dit un DESACCORD, jamais
        un degre. / The § 3.6 ban holds: a disagreement, never a degree.
        """
        article = self._article(40.0, [95.0, 95.0, 95.0])

        html = _html_avec_renvois(article)

        self.assertNotIn("data-score", html)
        self.assertNotIn("sur 100", html)
