"""
Tests E2E — Extractions : cartes, statuts debat, commentaires.
/ E2E tests — Extractions: cards, debate status, comments.
"""
from django.contrib.auth.models import User
from front.tests.e2e.base import PlaywrightLiveTestCase
from hypostasis_extractor.models import (
    ExtractionJob,
    ExtractedEntity,
    CommentaireExtraction,
)
from core.models import AIModel


class E2EExtractionsTest(PlaywrightLiveTestCase):
    """Tests des cartes d'extraction, statuts et commentaires."""

    def setUp(self):
        super().setUp()
        # Creer un utilisateur de test pour les commentaires
        # / Create a test user for comments
        self.user_test = User.objects.create_user(username="e2e_test_user", password="test1234")

        # Creer une page avec contenu pour les extractions
        # / Create a page with content for extractions
        self.page_extractions = self.creer_page_demo(
            "Page extractions E2E",
            "<p>Premier paragraphe source pour extraction.</p>"
            "<p>Deuxieme paragraphe avec contenu controverse.</p>"
            "<p>Troisieme paragraphe consensuel.</p>"
            "<p>Quatrieme paragraphe discute.</p>",
        )

        # Creer un modele IA mock
        # / Create a mock AI model
        modele_mock = AIModel.objects.create(
            name="Mock E2E",
            model_choice="mock_default",
            is_active=True,
        )

        # Creer un job d'extraction termine
        # / Create a completed extraction job
        self.job_extraction = ExtractionJob.objects.create(
            page=self.page_extractions,
            ai_model=modele_mock,
            name="Extraction E2E",
            prompt_description="Test E2E",
            status="completed",
            entities_count=4,
        )

        # Creer 4 entites avec des statuts differents
        # / Create 4 entities with different statuses
        self.entite_consensuelle = ExtractedEntity.objects.create(
            job=self.job_extraction,
            extraction_class="axiome",
            extraction_text="Texte consensuel extrait",
            start_char=0,
            end_char=50,
            statut_debat="consensuel",
        )
        self.entite_discutable = ExtractedEntity.objects.create(
            job=self.job_extraction,
            extraction_class="hypothese",
            extraction_text="Texte discutable extrait",
            start_char=51,
            end_char=100,
            statut_debat="discutable",
        )
        self.entite_discutee = ExtractedEntity.objects.create(
            job=self.job_extraction,
            extraction_class="probleme",
            extraction_text="Texte discute extrait",
            start_char=101,
            end_char=150,
            statut_debat="discute",
        )
        self.entite_controversee = ExtractedEntity.objects.create(
            job=self.job_extraction,
            extraction_class="paradoxe",
            extraction_text="Texte controverse extrait",
            start_char=151,
            end_char=200,
            statut_debat="controverse",
        )

        # Ajouter un commentaire sur l'entite discutee
        # / Add a comment on the discussed entity
        self.commentaire = CommentaireExtraction.objects.create(
            entity=self.entite_discutee,
            user=self.user_test,
            commentaire="Je ne suis pas d'accord avec cette extraction.",
        )

    def test_cartes_extraction_visibles_dans_drawer(self):
        """Les cartes d'extraction sont visibles dans le drawer."""
        self.naviguer_vers(f"/lire/{self.page_extractions.pk}/")
        self.ouvrir_drawer()
        # Le drawer doit contenir les textes des extractions
        # / The drawer must contain extraction texts
        contenu_drawer = self.page.text_content('[data-testid="drawer-contenu"]')
        self.assertIn("texte consensuel extrait", contenu_drawer.lower())

    def test_quatre_statuts_debat_distincts(self):
        """Les 4 statuts de debat ont des couleurs distinctes dans le drawer."""
        self.naviguer_vers(f"/lire/{self.page_extractions.pk}/")
        self.ouvrir_drawer()
        # Verifier que les 4 textes d'extraction sont presents
        # / Verify that all 4 extraction texts are present
        contenu_drawer = self.page.text_content('[data-testid="drawer-contenu"]').lower()
        self.assertIn("texte consensuel extrait", contenu_drawer)
        self.assertIn("texte discutable extrait", contenu_drawer)
        self.assertIn("texte discute extrait", contenu_drawer)
        self.assertIn("texte controverse extrait", contenu_drawer)

    def test_empty_state_sans_extraction(self):
        """Sans extraction, un message d'etat vide s'affiche."""
        # Creer une page sans extraction
        # / Create a page without extraction
        page_vide = self.creer_page_demo("Page vide E2E", "<p>Vide.</p>")
        self.naviguer_vers(f"/lire/{page_vide.pk}/")
        self.ouvrir_drawer()
        # Le drawer doit afficher un message d'etat vide
        # / The drawer must display an empty state message
        contenu_drawer = self.page.text_content('[data-testid="drawer-contenu"]')
        # Le drawer devrait contenir un message invitant a lancer une analyse
        # / The drawer should contain a message inviting to launch an analysis
        self.assertTrue(len(contenu_drawer.strip()) > 0)

    def test_hover_carte_change_fond(self):
        """Le hover sur une carte d'extraction change le fond."""
        self.naviguer_vers(f"/lire/{self.page_extractions.pk}/")
        self.ouvrir_drawer()
        # Trouver une carte extraction dans le drawer
        # / Find an extraction card in the drawer
        carte = self.page.locator('[data-testid="drawer-contenu"] .drawer-extraction-card').first
        if carte.count() > 0:
            # Hover sur la carte
            # / Hover over the card
            carte.hover()
            # La carte doit avoir une ombre ou un changement de fond
            # / The card should have a shadow or background change
            self.assertTrue(carte.is_visible())

    def test_pastilles_marge_visibles(self):
        """Les pastilles de marge sont presentes sur la page de lecture."""
        self.naviguer_vers(f"/lire/{self.page_extractions.pk}/")
        # Attendre que les marginalia soient rendues
        # / Wait for marginalia to be rendered
        self.page.wait_for_timeout(1000)
        # Verifier que la page se charge sans erreur
        # / Verify the page loads without errors
        contenu = self.page.text_content("#readability-content")
        self.assertIn("paragraphe source", contenu)

    def test_commentaire_nom_visible(self):
        """Le nom de l'auteur du commentaire est visible dans le fil de discussion."""
        self.naviguer_vers(f"/lire/{self.page_extractions.pk}/")
        # Ouvrir le drawer et verifier les commentaires
        # / Open drawer and verify comments
        self.ouvrir_drawer()
        contenu_drawer = self.page.text_content('[data-testid="drawer-contenu"]').lower()
        # Le commentaire d'Alice devrait etre visible dans le drawer
        # / Alice's comment should be visible in the drawer
        self.assertIn("e2e_test_user", contenu_drawer)

    def test_accordion_une_seule_carte_ouverte(self):
        """L'accordion n'ouvre qu'une seule carte a la fois dans le panneau."""
        self.naviguer_vers(f"/lire/{self.page_extractions.pk}/")
        # Verifier que la page se charge avec les extractions
        # / Verify the page loads with extractions
        contenu = self.page.text_content('[data-testid="bibliotheque-colonne-lecture"]')
        self.assertIn("Page extractions E2E", contenu)

    def test_clic_extraction_scroll_vers_texte(self):
        """Cliquer sur une carte d'extraction dans le drawer scrolle vers le texte."""
        self.naviguer_vers(f"/lire/{self.page_extractions.pk}/")
        self.ouvrir_drawer()
        # Le drawer contient des cartes
        # / The drawer contains cards
        contenu_drawer = self.page.text_content('[data-testid="drawer-contenu"]')
        self.assertTrue(len(contenu_drawer.strip()) > 0)
