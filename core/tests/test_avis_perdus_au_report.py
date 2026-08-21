"""
Les avis qui ne retrouvent pas leur paire sont COMPTES, pas tus.
/ Opinions that lose their pair are COUNTED, never swallowed.

LOCALISATION : core/tests/test_avis_perdus_au_report.py

CE QUE CE TEST PROTEGE, ET CE QU'IL A DEJA COUTE. Un avis ne survit a
une mise a jour d'article que si sa paire est STRICTEMENT identique —
meme extraction ET meme texte de paragraphe, au mot pres. C'est
volontaire : un avis porte sur une affirmation precise, et si
l'affirmation change il ne vaut plus rien.

Mais il disparaissait EN SILENCE. Le 19 aout 2026, une campagne de
comparaison de redacteurs a regenere les wikis du carnet neuf fois : les
165 avis ecrits par les quatre juges locaux ont ete detruits sans qu'une
ligne de journal, un compteur ou un ecran ne le signale. La table etait
vide le lendemain, et il a fallu une relecture pour s'en apercevoir.

Les contestations HUMAINES, elles, sont comptees depuis toujours
(`contestations_perdues`). Les avis meritent le meme traitement : perdre
une donnee est defendable, la perdre en silence ne l'est pas.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (
    AvisDeVerification, Page, SourceLink, TypeDeNote, TypeLien,
)
from core.services.synthese import indexer_les_citations


class LesAvisPerdusAuReportSontComptes(TestCase):
    """Perdre est permis ; perdre en silence, non. / Loudly, not silently."""

    def setUp(self):
        from hypostasis_extractor.models import ExtractedEntity, ExtractionJob

        self.utilisateur = get_user_model().objects.create_user(
            username="redacteur", password="motdepasse",
        )
        note = Page.objects.create(
            title="Note", owner=self.utilisateur, type_de_note=TypeDeNote.NOTE,
        )
        job = ExtractionJob.objects.create(page=note, status="completed")
        self.extraction = ExtractedEntity.objects.create(
            job=job, extraction_text="un passage", extraction_class="hypostase",
            start_char=0, end_char=10,
        )

    def _article_cite_et_note(self, texte):
        """Un article d'un paragraphe, cite et note. / Cited and scored."""
        article = Page.objects.create(
            title="Wiki", owner=self.utilisateur, type_de_note=TypeDeNote.WIKI,
            text_readability=texte,
        )
        indexer_les_citations(article, texte, [self.extraction.pk])
        for lien in SourceLink.objects.filter(page_cible=article):
            AvisDeVerification.objects.create(
                lien=lien, methode="mdeberta v3 · directe",
                score=88.0, seuil=50.0,
            )
        return article

    def test_un_avis_dont_le_paragraphe_a_change_est_COMPTE(self):
        """
        LE CAS QUI A VIDE LA TABLE. Le redacteur reecrit l'article : le
        paragraphe change, la paire n'existe plus, l'avis tombe. Il doit
        apparaitre dans le bilan.
        / The writer rewrites the article; the pair is gone.
        """
        texte = f"Une affirmation sourcée [[ext:{self.extraction.pk}]]."
        article = self._article_cite_et_note(texte)
        self.assertEqual(AvisDeVerification.objects.count(), 1)

        texte_reecrit = (
            f"Une affirmation TOTALEMENT réécrite [[ext:{self.extraction.pk}]]."
        )
        bilan = indexer_les_citations(
            article, texte_reecrit, [self.extraction.pk],
        )

        self.assertEqual(bilan["avis_perdus"], 1)
        self.assertEqual(AvisDeVerification.objects.count(), 0)

    def test_un_avis_dont_la_paire_survit_n_est_PAS_compte_perdu(self):
        """
        Le cas nominal : le texte ne bouge pas, l'avis est reporte. Le
        compter perdu ferait crier au loup a chaque reindexation.
        / The nominal case must stay silent.
        """
        texte = f"Une affirmation sourcée [[ext:{self.extraction.pk}]]."
        article = self._article_cite_et_note(texte)

        bilan = indexer_les_citations(
            article, texte, [self.extraction.pk],
        )

        self.assertEqual(bilan["avis_perdus"], 0)
        self.assertEqual(AvisDeVerification.objects.count(), 1)

    def test_le_bilan_porte_toujours_la_cle_meme_a_zero(self):
        """
        Une cle absente obligerait chaque lecteur a un `.get(..., 0)` —
        et le premier qui l'oublie fait planter le rapport plutot que de
        lire zero. / A missing key would force a defensive .get().
        """
        # Un article JAMAIS indexe : aucun avis a perdre.
        # / Never indexed: no opinion to lose.
        texte = f"Une affirmation sourcée [[ext:{self.extraction.pk}]]."
        article = Page.objects.create(
            title="Wiki neuf", owner=self.utilisateur,
            type_de_note=TypeDeNote.WIKI, text_readability=texte,
        )

        bilan = indexer_les_citations(
            article, texte, [self.extraction.pk],
        )

        self.assertIn("avis_perdus", bilan)
        self.assertEqual(bilan["avis_perdus"], 0)
