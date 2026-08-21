"""
La garde : aucun corps de wiki ne s'ecrit sans laisser de trace.
/ The guard: no wiki body is written without a history round.

LOCALISATION : core/tests/test_aucun_corps_de_wiki_sans_tour.py

SPEC-synthese, addendum du 21 aout 2026.
`_ecrire_le_corps_d_un_article` est le SEUL endroit ou un corps
d'article s'ecrit. Un futur chemin d'ecriture qui oublierait
l'historique ne le ferait pas savoir : le wiki changerait, et le
journal ne dirait rien. La garde rend l'oubli IMPOSSIBLE plutot que
detectable — c'est mecanique, pas une convention.
/ The guard makes the omission impossible, not merely detectable.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (
    Dossier, MotifDeTourDeWiki, Page, TypeDeNote, Wiki,
)
from hypostasis_extractor.models import ExtractedEntity, ExtractionJob

Utilisateur = get_user_model()


class GardeDuMotifDeTourTest(TestCase):
    """
    Ecrire un wiki sans motif est refuse ; ecrire une note ordinaire
    ou une synthese dirigee ne demande rien.
    / Writing a wiki without a motive is refused; other notes are free.
    """

    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            username="gardien_du_motif", password="motdepasse",
        )
        self.carnet = Dossier.objects.create(
            name="Carnet de la garde", owner=self.utilisateur,
        )
        self.note_source = Page.objects.create(
            title="Source", owner=self.utilisateur,
            url="http://exemple.local/garde-source",
            html_original="<p>o</p>", html_readability="<p>l</p>",
            text_readability="texte", content_hash="hash-garde-source",
            type_de_note=TypeDeNote.NOTE,
        )
        job = ExtractionJob.objects.create(
            page=self.note_source, name="Job garde", status="completed",
            ai_model=None,
        )
        self.extraction = ExtractedEntity.objects.create(
            job=job, extraction_class="argument",
            extraction_text="un passage source", start_char=0, end_char=17,
        )
        self.article = Page.objects.create(
            title="Article de la garde", owner=self.utilisateur,
            url="http://exemple.local/garde-article",
            html_original="<p>o</p>", html_readability="<p>l</p>",
            text_readability="", content_hash="hash-garde-article",
            type_de_note=TypeDeNote.WIKI,
        )

    def _corps_cite_une_source(self):
        return f"## Section\n\nUne affirmation.[[ext:{self.extraction.pk}]]\n"

    def test_ecrire_un_wiki_sans_motif_est_refuse(self):
        from front.tasks import _ecrire_le_corps_d_un_article

        Wiki.objects.create(
            page=self.article, dossier=self.carnet, sujet="La garde",
        )

        with patch("front.tasks.enchainer_la_verification"):
            with self.assertRaises(ValueError) as refus:
                _ecrire_le_corps_d_un_article(
                    self.article, self._corps_cite_une_source(), None,
                )

        self.assertIn("motif", str(refus.exception).lower())
        # L'article n'a PAS ete ecrit : le refus est un refus.
        # / The article was not written: the refusal is a refusal.
        self.article.refresh_from_db()
        self.assertEqual(self.article.text_readability, "")

    def test_ecrire_un_wiki_avec_un_motif_ecrit_un_tour(self):
        from front.tasks import _ecrire_le_corps_d_un_article

        wiki = Wiki.objects.create(
            page=self.article, dossier=self.carnet, sujet="La garde",
        )

        with patch("front.tasks.enchainer_la_verification"):
            _ecrire_le_corps_d_un_article(
                self.article, self._corps_cite_une_source(), None,
                motif_du_tour=MotifDeTourDeWiki.CREATION,
            )

        tour = wiki.tours.get()
        self.assertEqual(tour.motif, MotifDeTourDeWiki.CREATION)
        self.assertEqual(tour.texte_apres, self.article.text_readability)

    def test_une_note_qui_ne_porte_aucun_wiki_n_exige_aucun_motif(self):
        # Les deux appelants qui ecrivent une synthese dirigee ne
        # touchent aucun wiki : la garde ne doit pas les gener.
        # / The two synthesis callers must not be hindered.
        from front.tasks import _ecrire_le_corps_d_un_article

        with patch("front.tasks.enchainer_la_verification"):
            _ecrire_le_corps_d_un_article(
                self.article, self._corps_cite_une_source(), None,
            )

        self.article.refresh_from_db()
        self.assertIn("Une affirmation.", self.article.text_readability)
