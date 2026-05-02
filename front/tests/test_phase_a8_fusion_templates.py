"""
Tests pour le partial _card_body.html (drawer-only A.8 Phase 4-bis).
Le parametre `mode` a ete retire : le partial est maintenant unique
(plus de mode "lecture" / "drawer" — refonte drawer-only).
/ Tests for the _card_body.html partial (A.8 Phase 4-bis drawer-only).
The `mode` parameter was removed: the partial is now unique
(no more "lecture" / "drawer" modes — drawer-only refactor).
"""
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import TestCase
from core.models import Page, Dossier
from hypostasis_extractor.models import (
    CommentaireExtraction, ExtractedEntity, ExtractionJob,
)

User = get_user_model()


class PhaseA8DrawerOnlyCardBodyTest(TestCase):
    """Le partial _card_body.html rend les cartes du drawer (drawer-only A.8)."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username="fusion_test", password="x")
        cls.dossier = Dossier.objects.create(name="Test fusion", owner=cls.user)
        cls.page = Page.objects.create(
            dossier=cls.dossier, title="Page test fusion",
            url="https://example.com/fusion", source_type="web",
            text_readability="Texte test fusion",
            owner=cls.user,
        )
        cls.job = ExtractionJob.objects.create(
            page=cls.page,
            name="Job test fusion",
            prompt_description="Test prompt",
            status="completed",
        )
        cls.entite = ExtractedEntity.objects.create(
            job=cls.job, extraction_class="hypostase",
            extraction_text="Texte source", start_char=0, end_char=12,
            attributes={"hypostases": "Théorie", "resume": "Mon résumé"},
            statut_debat="commente",
        )
        CommentaireExtraction.objects.create(
            entity=cls.entite, user=cls.user, commentaire="Mon commentaire",
        )

    def _rendre(self):
        return render_to_string(
            "hypostasis_extractor/includes/_card_body.html",
            {
                "entity": self.entite,
                "attr_0": "Théorie",
                "attr_1": "Mon résumé",
                "attr_2": "",
                "attr_3": "",
                "est_proprietaire": True,
            },
        )

    def test_card_body_affiche_commentaires_inline(self):
        """Le partial affiche les commentaires existants inline.
        / The partial displays existing comments inline."""
        html = self._rendre()
        self.assertIn("Mon commentaire", html)

    def test_card_body_contient_btn_commenter(self):
        """Le partial contient le bouton 'Commenter' et la zone deroulable.
        / The partial contains the 'Comment' button and the foldable zone."""
        html = self._rendre()
        self.assertIn("btn-commenter-extraction", html)
        self.assertIn("zone-commentaire-deroulable", html)

    def test_card_body_owner_voit_btn_masquer(self):
        """Le proprietaire du dossier voit le bouton btn-masquer-drawer.
        / The folder owner sees the btn-masquer-drawer button."""
        html = self._rendre()
        self.assertIn("btn-masquer-drawer", html)
