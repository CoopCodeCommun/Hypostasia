"""
Tests pour le signal Django de synchronisation automatique du statut de debat.
/ Tests for Django signal that auto-syncs debate status.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from core.models import Page, Dossier
from hypostasis_extractor.models import (
    CommentaireExtraction, ExtractedEntity, ExtractionJob,
)

User = get_user_model()


class PhaseA8SignalSynchroniseStatutTest(TestCase):
    """Le signal doit maintenir statut_debat synchronise avec l'existence
    de commentaires sur l'entite.
    / Signal must keep statut_debat synced with comment existence."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="signal_test", password="x")
        cls.dossier = Dossier.objects.create(name="Test signal", owner=cls.user)
        cls.page = Page.objects.create(
            dossier=cls.dossier, title="Page test signal",
            url="https://example.com/signal", source_type="web",
            text_readability="Texte test", owner=cls.user,
        )
        cls.job = ExtractionJob.objects.create(
            page=cls.page, name="Job test signal",
            prompt_description="Test prompt", status="completed",
        )

    def _creer_entite(self):
        return ExtractedEntity.objects.create(
            job=self.job, extraction_class="hypostase",
            extraction_text="Test", start_char=0, end_char=4,
            attributes={}, statut_debat="nouveau",
        )

    def test_creation_commentaire_passe_statut_a_commente(self):
        """A la creation d'un commentaire, statut_debat doit passer a 'commente'."""
        entite = self._creer_entite()
        self.assertEqual(entite.statut_debat, "nouveau")

        CommentaireExtraction.objects.create(
            entity=entite, user=self.user, commentaire="Premier commentaire",
        )

        entite.refresh_from_db()
        self.assertEqual(entite.statut_debat, "commente")

    def test_suppression_dernier_commentaire_repasse_a_nouveau(self):
        """A la suppression du dernier commentaire, statut_debat doit repasser a 'nouveau'."""
        entite = self._creer_entite()
        commentaire = CommentaireExtraction.objects.create(
            entity=entite, user=self.user, commentaire="Seul commentaire",
        )
        entite.refresh_from_db()
        self.assertEqual(entite.statut_debat, "commente")

        commentaire.delete()

        entite.refresh_from_db()
        self.assertEqual(entite.statut_debat, "nouveau")

    def test_suppression_avec_commentaires_restants_garde_commente(self):
        """A la suppression d'un commentaire alors qu'il en reste, statut_debat reste 'commente'."""
        entite = self._creer_entite()
        commentaire1 = CommentaireExtraction.objects.create(
            entity=entite, user=self.user, commentaire="Commentaire 1",
        )
        CommentaireExtraction.objects.create(
            entity=entite, user=self.user, commentaire="Commentaire 2",
        )
        entite.refresh_from_db()
        self.assertEqual(entite.statut_debat, "commente")

        commentaire1.delete()

        entite.refresh_from_db()
        self.assertEqual(entite.statut_debat, "commente")
