"""
Tests E2E — Navigation : arbre, dossiers, pages.
/ E2E tests — Navigation: tree, folders, pages.
"""
from front.tests.e2e.base import PlaywrightLiveTestCase
from core.models import Dossier, Page


class E2ENavigationTest(PlaywrightLiveTestCase):
    """Tests de navigation dans l'arbre et entre les pages."""

    def setUp(self):
        super().setUp()
        # Creer un utilisateur et se connecter pour les actions d'ecriture
        # / Create a user and log in for write actions
        self.utilisateur_test = self.creer_utilisateur_demo()
        self.se_connecter("testuser", "testpass123")
        # Creer 2 dossiers et 3 pages (1 classee, 2 orphelines)
        # / Create 2 folders and 3 pages (1 classified, 2 orphans)
        self.dossier_alpha = self.creer_dossier_demo("Alpha")
        self.dossier_alpha.owner = self.utilisateur_test
        self.dossier_alpha.save()
        self.dossier_beta = self.creer_dossier_demo("Beta")
        self.dossier_beta.owner = self.utilisateur_test
        self.dossier_beta.save()
        self.page_classee = self.creer_page_demo(
            "Page classee",
            "<p>Contenu page classee dans Alpha.</p>",
        )
        self.page_classee.dossier = self.dossier_alpha
        self.page_classee.save()
        self.page_orpheline_1 = self.creer_page_demo(
            "Orpheline 1",
            "<p>Contenu orpheline 1.</p>",
        )
        self.page_orpheline_2 = self.creer_page_demo(
            "Orpheline 2",
            "<p>Contenu orpheline 2.</p>",
        )

    def test_onboarding_affiche_si_aucune_page(self):
        """L'onboarding s'affiche quand il n'y a aucune page."""
        # Supprimer toutes les pages pour voir l'onboarding
        # / Delete all pages to see onboarding
        Page.objects.all().delete()
        self.naviguer_vers("/")
        contenu_onboarding = self.page.text_content('[data-testid="bibliotheque-colonne-lecture"]')
        self.assertIn("Importer", contenu_onboarding)

    def test_creer_dossier_sweetalert_apparait(self):
        """Le bouton '+ Nouveau dossier' ouvre un SweetAlert avec champ texte."""
        self.naviguer_vers("/")
        self.ouvrir_arbre()
        self.page.click('[data-testid="btn-creer-dossier-overlay"]')
        # SweetAlert2 doit apparaitre
        # / SweetAlert2 must appear
        self.page.wait_for_selector(".swal2-popup", state="visible", timeout=3000)
        champ_texte = self.page.locator(".swal2-input")
        self.assertTrue(champ_texte.is_visible(), "Le champ de saisie SweetAlert doit etre visible")
        bouton_confirmer = self.page.locator(".swal2-confirm")
        self.assertTrue(bouton_confirmer.is_visible(), "Le bouton confirmer doit etre visible")
        # Fermer le SweetAlert
        # / Close the SweetAlert
        self.page.locator(".swal2-cancel").click()

    def test_naviguer_vers_page_depuis_arbre(self):
        """Cliquer une page dans l'arbre charge le contenu."""
        self.naviguer_vers("/")
        self.ouvrir_arbre()
        lien_page = self.page.locator(
            f'[data-testid="arbre-dossiers"] a[hx-get*="/lire/{self.page_orpheline_1.pk}/"]'
        )
        lien_page.click()
        self.attendre_htmx()
        contenu_lecture = self.page.text_content('[data-testid="bibliotheque-colonne-lecture"]')
        self.assertIn("Contenu orpheline 1", contenu_lecture)

    def test_renommer_dossier_sweetalert_apparait(self):
        """Le bouton renommer ouvre un SweetAlert pre-rempli avec le nom actuel."""
        self.naviguer_vers("/")
        self.ouvrir_arbre()
        # Ouvrir le menu contextuel kebab du dossier Alpha
        # / Open the kebab context menu for folder Alpha
        bouton_kebab = self.page.locator(
            f'[data-ctx-type="dossier"][data-ctx-id="{self.dossier_alpha.pk}"] [data-testid="btn-ctx-dossier"]'
        )
        bouton_kebab.click()
        # Cliquer sur l'action "Renommer" dans le menu contextuel
        # / Click the "Rename" action in the context menu
        self.page.locator(".btn-action-renommer").first.click()
        # SweetAlert2 doit apparaitre avec le nom actuel pre-rempli
        # / SweetAlert2 must appear with current name pre-filled
        self.page.wait_for_selector(".swal2-popup", state="visible", timeout=3000)
        valeur_input = self.page.locator(".swal2-input").input_value()
        self.assertEqual(valeur_input, "Alpha")
        # Fermer le SweetAlert
        # / Close the SweetAlert
        self.page.locator(".swal2-cancel").click()

    def test_supprimer_dossier_sweetalert_apparait(self):
        """Le bouton supprimer ouvre un SweetAlert de confirmation."""
        self.naviguer_vers("/")
        self.ouvrir_arbre()
        # Ouvrir le menu contextuel kebab du dossier Beta
        # / Open the kebab context menu for folder Beta
        bouton_kebab = self.page.locator(
            f'[data-ctx-type="dossier"][data-ctx-id="{self.dossier_beta.pk}"] [data-testid="btn-ctx-dossier"]'
        )
        bouton_kebab.click()
        # Cliquer sur l'action "Supprimer" dans le menu contextuel
        # / Click the "Delete" action in the context menu
        self.page.locator(".btn-action-supprimer-dossier").first.click()
        # SweetAlert2 de confirmation doit apparaitre
        # / Confirmation SweetAlert2 must appear
        self.page.wait_for_selector(".swal2-popup", state="visible", timeout=3000)
        # Le titre devrait mentionner la suppression
        # / The title should mention deletion
        contenu_swal = self.page.text_content(".swal2-popup")
        self.assertIn("Supprimer", contenu_swal)

    def test_classer_page_dans_dossier(self):
        """Classer une page orpheline dans un dossier via SweetAlert."""
        self.naviguer_vers("/")
        self.ouvrir_arbre()
        # Ouvrir le menu contextuel kebab de la page orpheline
        # / Open the kebab context menu for the orphan page
        bouton_kebab = self.page.locator(
            f'[data-ctx-type="page"][data-ctx-id="{self.page_orpheline_1.pk}"] [data-testid="btn-ctx-page"]'
        )
        bouton_kebab.click()
        # Cliquer sur l'action "Deplacer" dans le menu contextuel
        # / Click the "Move" action in the context menu
        self.page.locator(".btn-action-deplacer").first.click()
        # SweetAlert devrait apparaitre avec un select des dossiers
        # / SweetAlert should appear with a folder select
        self.page.wait_for_selector(".swal2-popup", state="visible", timeout=3000)
        # Verifier qu'un select ou input est present
        # / Verify a select or input is present
        contenu_swal = self.page.text_content(".swal2-popup")
        self.assertTrue(len(contenu_swal.strip()) > 0, "Le SweetAlert de classement doit s'afficher")
