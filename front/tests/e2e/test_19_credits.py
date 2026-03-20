"""
Tests E2E PHASE-26h — Credits prepays et page "Mes credits".
/ E2E tests PHASE-26h — Prepaid credits and "My credits" page.

Lancer avec : uv run python manage.py test front.tests.e2e.test_19_credits -v2
"""

from django.test import override_settings

from front.tests.e2e.base import PlaywrightLiveTestCase


@override_settings(STRIPE_ENABLED=True)
class Phase26hCreditsE2ETest(PlaywrightLiveTestCase):
    """Tests E2E pour les credits prepays et la page Mes credits."""

    def setUp(self):
        super().setUp()
        # Creer un utilisateur et se connecter pour chaque test
        # / Create a user and log in for each test
        self.utilisateur_test = self.creer_utilisateur_demo(
            username="credituser", password="testpass123",
        )
        self.se_connecter("credituser", "testpass123")

    # ====================================================================
    # Badge solde dans la navbar
    # ====================================================================

    def test_badge_solde_visible_stripe_enabled(self):
        """Le badge solde est visible dans la navbar quand STRIPE_ENABLED=True."""
        self.naviguer_vers("/")
        badge = self.page.wait_for_selector(
            '[data-testid="badge-solde-credits"]', timeout=5000,
        )
        self.assertIsNotNone(badge)
        # Le solde initial doit etre 0.00
        # / Initial balance should be 0.00
        texte_badge = badge.text_content()
        self.assertIn("0.00", texte_badge)

    def test_lien_mes_credits_dans_menu_utilisateur(self):
        """Le lien 'Mes credits' est visible dans le dropdown utilisateur."""
        self.naviguer_vers("/")
        # Ouvrir le menu utilisateur
        # / Open user menu
        self.page.click('[data-testid="btn-user-menu"]')
        lien_credits = self.page.wait_for_selector(
            '[data-testid="btn-mes-credits"]', timeout=3000,
        )
        self.assertIsNotNone(lien_credits)

    # ====================================================================
    # Page "Mes credits"
    # ====================================================================

    def test_page_credits_accessible_via_url(self):
        """La page /credits/ est accessible et affiche le solde."""
        self.naviguer_vers("/credits/")
        zone_credits = self.page.wait_for_selector(
            '[data-testid="credits-page"]', timeout=5000,
        )
        self.assertIsNotNone(zone_credits)

    def test_page_credits_affiche_solde_zero(self):
        """La page credits affiche le solde initial a 0.00."""
        self.naviguer_vers("/credits/")
        solde_element = self.page.wait_for_selector(
            '[data-testid="solde-actuel"]', timeout=5000,
        )
        self.assertIsNotNone(solde_element)
        texte_solde = solde_element.text_content()
        self.assertIn("0.00", texte_solde)

    def test_page_credits_affiche_boutons_recharge(self):
        """La page credits affiche les boutons de recharge predefinis."""
        self.naviguer_vers("/credits/")
        self.page.wait_for_selector(
            '[data-testid="credits-page"]', timeout=5000,
        )
        # Verifier que les boutons de recharge sont presents
        # / Verify top-up buttons are present
        for montant in [5, 10, 20, 50]:
            bouton = self.page.query_selector(
                f'[data-testid="btn-recharger-{montant}"]',
            )
            self.assertIsNotNone(
                bouton, f"Bouton recharger {montant} EUR manquant",
            )

    def test_page_credits_historique_vide(self):
        """La page credits affiche un message quand il n'y a pas de transactions."""
        self.naviguer_vers("/credits/")
        self.page.wait_for_selector(
            '[data-testid="credits-page"]', timeout=5000,
        )
        contenu = self.page.text_content('[data-testid="credits-page"]')
        self.assertIn("Aucune transaction", contenu)

    def test_page_credits_historique_avec_transactions(self):
        """La page credits affiche l'historique apres un credit."""
        from core.models import CreditAccount
        # Crediter le compte via l'ORM
        # / Credit the account via ORM
        compte = CreditAccount.get_ou_creer(self.utilisateur_test)
        compte.crediter(
            montant=15, type_transaction="RECHARGE",
            description="Recharge test E2E",
        )

        self.naviguer_vers("/credits/")
        self.page.wait_for_selector(
            '[data-testid="credits-page"]', timeout=5000,
        )
        contenu = self.page.text_content('[data-testid="credits-page"]')
        self.assertIn("15.00", contenu)
        self.assertIn("Recharge test E2E", contenu)

    # ====================================================================
    # Navigation HTMX vers /credits/
    # ====================================================================

    def test_clic_badge_charge_page_credits_htmx(self):
        """Cliquer sur le badge solde charge la page credits via HTMX."""
        self.naviguer_vers("/")
        self.page.click('[data-testid="badge-solde-credits"]')
        self.attendre_htmx()
        zone_credits = self.page.wait_for_selector(
            '[data-testid="credits-page"]', timeout=5000,
        )
        self.assertIsNotNone(zone_credits)

    # ====================================================================
    # Page annulation
    # ====================================================================

    def test_page_annulation_accessible(self):
        """La page /credits/annule/ est accessible et affiche le message."""
        self.naviguer_vers("/credits/annule/")
        zone_annule = self.page.wait_for_selector(
            '[data-testid="credits-annule"]', timeout=5000,
        )
        self.assertIsNotNone(zone_annule)
        contenu = zone_annule.text_content()
        self.assertIn("annule", contenu.lower())


@override_settings(STRIPE_ENABLED=True)
class Phase26hCadeauBienvenueE2ETest(PlaywrightLiveTestCase):
    """Tests E2E pour le cadeau de bienvenue 3 EUR a l'inscription."""

    def test_inscription_cadeau_bienvenue_3_euros(self):
        """Un nouvel utilisateur inscrit voit un solde de 3.00 EUR dans le badge."""
        self.naviguer_vers("/auth/register/")
        self.page.fill('[data-testid="input-username"]', "bienvenue_user")
        self.page.fill('[data-testid="input-email"]', "bienvenue@test.com")
        self.page.fill('[data-testid="input-password"]', "monmotdepasse123")
        self.page.fill('[data-testid="input-password-confirm"]', "monmotdepasse123")
        self.page.click('[data-testid="btn-submit-register"]')
        self.page.wait_for_url("**/")

        # Le badge solde doit afficher 3.00 EUR
        # / The balance badge should show 3.00 EUR
        badge = self.page.wait_for_selector(
            '[data-testid="badge-solde-credits"]', timeout=5000,
        )
        self.assertIsNotNone(badge)
        texte_badge = badge.text_content()
        self.assertIn("3.00", texte_badge)


@override_settings(STRIPE_ENABLED=False)
class Phase26hStripeDisabledE2ETest(PlaywrightLiveTestCase):
    """Tests E2E quand STRIPE_ENABLED=False — pas de badge, pas de gate."""

    def setUp(self):
        super().setUp()
        self.utilisateur_test = self.creer_utilisateur_demo(
            username="nostripeuser", password="testpass123",
        )
        self.se_connecter("nostripeuser", "testpass123")

    def test_badge_solde_invisible_stripe_disabled(self):
        """Le badge solde n'est PAS visible quand STRIPE_ENABLED=False."""
        self.naviguer_vers("/")
        self.page.wait_for_selector("text=Hypostasia", timeout=5000)
        badge = self.page.query_selector('[data-testid="badge-solde-credits"]')
        self.assertIsNone(badge)

    def test_lien_mes_credits_invisible_stripe_disabled(self):
        """Le lien 'Mes credits' n'est PAS visible quand STRIPE_ENABLED=False."""
        self.naviguer_vers("/")
        self.page.click('[data-testid="btn-user-menu"]')
        self.page.wait_for_timeout(500)
        lien_credits = self.page.query_selector('[data-testid="btn-mes-credits"]')
        self.assertIsNone(lien_credits)
