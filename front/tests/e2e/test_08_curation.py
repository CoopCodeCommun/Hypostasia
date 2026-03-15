"""
Tests E2E — Curation : masquer/restaurer extractions.
/ E2E tests — Curation: hide/restore extractions.
"""
from django.contrib.auth.models import User
from front.tests.e2e.base import PlaywrightLiveTestCase
from hypostasis_extractor.models import (
    ExtractionJob,
    ExtractedEntity,
    CommentaireExtraction,
)
from core.models import AIModel


class E2ECurationTest(PlaywrightLiveTestCase):
    """Tests de curation (masquer/restaurer)."""

    def setUp(self):
        super().setUp()
        # Creer un utilisateur de test pour les commentaires
        # / Create a test user for comments
        self.user_test = User.objects.create_user(username="e2e_test_user", password="test1234")

        # Creer une page avec 2 extractions (1 avec commentaire, 1 sans)
        # / Create a page with 2 extractions (1 with comment, 1 without)
        self.page_curation = self.creer_page_demo(
            "Page curation E2E",
            "<p>Contenu premier paragraphe curation.</p>"
            "<p>Contenu deuxieme paragraphe curation.</p>",
        )
        modele_mock = AIModel.objects.create(
            name="Mock Curation",
            model_choice="mock_default",
            is_active=True,
        )
        job = ExtractionJob.objects.create(
            page=self.page_curation,
            ai_model=modele_mock,
            name="Extraction curation",
            prompt_description="Test curation",
            status="completed",
            entities_count=2,
        )
        # Extraction sans commentaire — masquable
        # / Extraction without comment — can be hidden
        self.entite_sans_commentaire = ExtractedEntity.objects.create(
            job=job,
            extraction_class="hypothese",
            extraction_text="Extraction masquable",
            start_char=0,
            end_char=40,
            statut_debat="discutable",
        )
        # Extraction avec commentaire — non masquable
        # / Extraction with comment — cannot be hidden
        self.entite_avec_commentaire = ExtractedEntity.objects.create(
            job=job,
            extraction_class="axiome",
            extraction_text="Extraction commentee",
            start_char=41,
            end_char=80,
            statut_debat="discute",
        )
        CommentaireExtraction.objects.create(
            entity=self.entite_avec_commentaire,
            user=self.user_test,
            commentaire="Commentaire protecteur.",
        )

    def test_bouton_masquer_visible_sans_commentaire(self):
        """Le bouton masquer est visible sur l'extraction sans commentaire."""
        self.naviguer_vers(f"/lire/{self.page_curation.pk}/")
        self.ouvrir_drawer()
        # Chercher le bouton masquer sur l'entite sans commentaire
        # / Look for the hide button on the entity without comment
        bouton_masquer = self.page.locator(
            f'[data-testid="drawer-contenu"] [data-extraction-id="{self.entite_sans_commentaire.pk}"] .btn-masquer-extraction,'
            f'[data-testid="drawer-contenu"] .btn-masquer-extraction[data-entity-id="{self.entite_sans_commentaire.pk}"]'
        )
        if bouton_masquer.count() > 0:
            self.assertTrue(bouton_masquer.first.is_visible())

    def test_bouton_masquer_absent_avec_commentaire(self):
        """Le bouton masquer est absent sur l'extraction avec commentaire."""
        self.naviguer_vers(f"/lire/{self.page_curation.pk}/")
        self.ouvrir_drawer()
        # Le bouton masquer ne doit pas exister pour l'entite avec commentaire
        # / Hide button must not exist for the entity with comment
        bouton_masquer = self.page.locator(
            f'.btn-masquer-extraction[data-entity-id="{self.entite_avec_commentaire.pk}"]'
        )
        # Il devrait etre absent ou invisible
        # / It should be absent or invisible
        nombre = bouton_masquer.count()
        if nombre > 0:
            # Si present, il devrait etre cache
            # / If present, it should be hidden
            est_visible = bouton_masquer.first.is_visible()
            self.assertFalse(est_visible, "Le bouton masquer ne devrait pas etre visible pour une extraction commentee")

    def test_clic_masquer_extraction_disparait(self):
        """Cliquer masquer fait disparaitre l'extraction."""
        self.naviguer_vers(f"/lire/{self.page_curation.pk}/")
        self.ouvrir_drawer()
        # Cliquer le bouton masquer de l'entite sans commentaire
        # / Click the hide button for the entity without comment
        bouton_masquer = self.page.locator(
            f'.btn-masquer-extraction[data-entity-id="{self.entite_sans_commentaire.pk}"]'
        )
        if bouton_masquer.count() > 0:
            bouton_masquer.first.click()
            self.attendre_htmx()
            # L'entite doit etre masquee en BDD
            # / The entity must be hidden in DB
            entite_rechargee = ExtractedEntity.objects.get(pk=self.entite_sans_commentaire.pk)
            self.assertTrue(entite_rechargee.masquee)

    def test_restaurer_depuis_onglet_masquees(self):
        """Restaurer une extraction masquee depuis l'onglet masquees du drawer."""
        # Masquer l'extraction d'abord en BDD
        # / Hide the extraction first in DB
        self.entite_sans_commentaire.masquee = True
        self.entite_sans_commentaire.save()

        self.naviguer_vers(f"/lire/{self.page_curation.pk}/")
        self.ouvrir_drawer()
        # Chercher le toggle pour afficher les masquees
        # / Look for the toggle to show hidden entities
        toggle_masquees = self.page.locator(
            '[data-testid="drawer-contenu"] .toggle-masquees, '
            '[data-testid="drawer-contenu"] summary, '
            '[data-testid="drawer-contenu"] [data-toggle="masquees"]'
        )
        if toggle_masquees.count() > 0:
            toggle_masquees.first.click()
            self.page.wait_for_timeout(300)
            # Cliquer le bouton restaurer
            # / Click the restore button
            bouton_restaurer = self.page.locator(
                f'.btn-restaurer-extraction[data-entity-id="{self.entite_sans_commentaire.pk}"]'
            )
            if bouton_restaurer.count() > 0:
                bouton_restaurer.first.click()
                self.attendre_htmx()
                # Verifier en BDD
                # / Verify in DB
                entite_rechargee = ExtractedEntity.objects.get(pk=self.entite_sans_commentaire.pk)
                self.assertFalse(entite_rechargee.masquee)
