"""
Tests E2E PHASE-25d — Invitation par email.
/ E2E tests PHASE-25d — Email invitation.

Lancer avec : uv run python manage.py test front.tests.e2e.test_16_invitation -v2
"""

from front.tests.e2e.base import PlaywrightLiveTestCase


class Phase25dInvitationE2ETest(PlaywrightLiveTestCase):
    """Tests E2E pour les invitations par email."""

    # ====================================================================
    # Helpers
    # ====================================================================

    def creer_utilisateur_demo(self, username="testuser", password="testpass123", email=""):
        """
        Cree un utilisateur via l'ORM pour les tests.
        / Create a user via ORM for tests.
        """
        from django.contrib.auth.models import User
        return User.objects.create_user(username=username, password=password, email=email)

    def se_connecter(self, username, password):
        """
        Navigue vers /auth/login/, remplit le formulaire et se connecte.
        / Navigate to /auth/login/, fill form and log in.
        """
        self.naviguer_vers("/auth/login/")
        self.page.fill('[data-testid="input-username"]', username)
        self.page.fill('[data-testid="input-password"]', password)
        self.page.click('[data-testid="btn-submit-login"]')
        self.page.wait_for_url("**/")

    # ====================================================================
    # Tests
    # ====================================================================

    def test_05_inviter_email_existant(self):
        """Inviter un email existant → partage direct cree.
        / Invite an existing email → direct share created."""
        from core.models import Dossier, DossierPartage
        owner = self.creer_utilisateur_demo("inv_e2e_own", "test1234", email="invown@test.com")
        invite = self.creer_utilisateur_demo("inv_e2e_inv", "test1234", email="invinv@test.com")
        dossier = Dossier.objects.create(name="D invite e2e", owner=owner)
        self.se_connecter("inv_e2e_own", "test1234")
        self.naviguer_vers("/")
        # On fait l'invitation via POST direct (pas via UI car trop de clicks)
        # / Do invitation via direct POST (not via UI as too many clicks)
        self.page.evaluate(f"""
            fetch('/dossiers/{dossier.pk}/inviter/', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': document.cookie.match(/csrftoken=([^;]+)/)[1]}},
                body: 'email=invinv@test.com'
            }})
        """)
        self.page.wait_for_timeout(500)
        self.assertTrue(
            DossierPartage.objects.filter(dossier=dossier, utilisateur=invite).exists(),
            "Un partage direct doit avoir ete cree",
        )

    def test_06_inviter_email_inconnu(self):
        """Inviter un email inconnu → invitation creee.
        / Invite unknown email → invitation created."""
        from core.models import Dossier, Invitation
        owner = self.creer_utilisateur_demo("inv_e2e_own2", "test1234", email="invown2@test.com")
        dossier = Dossier.objects.create(name="D invite e2e2", owner=owner)
        self.se_connecter("inv_e2e_own2", "test1234")
        self.naviguer_vers("/")
        self.page.evaluate(f"""
            fetch('/dossiers/{dossier.pk}/inviter/', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': document.cookie.match(/csrftoken=([^;]+)/)[1]}},
                body: 'email=unknown_e2e@test.com'
            }})
        """)
        self.page.wait_for_timeout(500)
        self.assertTrue(
            Invitation.objects.filter(dossier=dossier, email="unknown_e2e@test.com").exists(),
            "Une invitation doit avoir ete creee",
        )

    def test_07_lien_invitation_anonyme_redirect_register(self):
        """Lien invitation pour anonyme → redirect register avec token.
        / Invitation link for anonymous → redirect register with token."""
        from core.models import Dossier, Invitation
        import secrets
        from django.utils import timezone
        from datetime import timedelta
        owner = self.creer_utilisateur_demo("inv_e2e_own3", "test1234")
        dossier = Dossier.objects.create(name="D redir", owner=owner)
        token = secrets.token_hex(32)
        Invitation.objects.create(
            dossier=dossier, email="redir@test.com",
            invite_par=owner, token=token,
            expires_at=timezone.now() + timedelta(days=7),
        )
        self.naviguer_vers(f"/invitation/{token}/")
        self.page.wait_for_timeout(500)
        # Devrait rediriger vers /auth/register/?token=...
        self.assertIn("/auth/register/", self.page.url)
        self.assertIn(token, self.page.url)

    def test_08_inscription_avec_token(self):
        """Inscription avec token → invitation auto-acceptee.
        / Registration with token → invitation auto-accepted."""
        from core.models import Dossier, Invitation, DossierPartage
        import secrets
        from django.utils import timezone
        from datetime import timedelta
        owner = self.creer_utilisateur_demo("inv_e2e_own4", "test1234")
        dossier = Dossier.objects.create(name="D register e2e", owner=owner)
        token = secrets.token_hex(32)
        Invitation.objects.create(
            dossier=dossier, email="newreg@test.com",
            invite_par=owner, token=token,
            expires_at=timezone.now() + timedelta(days=7),
        )
        self.naviguer_vers(f"/auth/register/?token={token}")
        self.page.fill('[data-testid="input-username"]', "newreg_e2e")
        self.page.fill('[data-testid="input-email"]', "newreg@test.com")
        self.page.fill('[data-testid="input-password"]', "testpass1234")
        self.page.fill('[data-testid="input-password-confirm"]', "testpass1234")
        self.page.click('[data-testid="btn-submit-register"]')
        self.page.wait_for_url("**/")
        # Verifier que l'invitation est acceptee
        invitation = Invitation.objects.get(token=token)
        self.assertTrue(invitation.acceptee)
        from django.contrib.auth.models import User
        nouveau = User.objects.get(username="newreg_e2e")
        self.assertTrue(
            DossierPartage.objects.filter(dossier=dossier, utilisateur=nouveau).exists(),
        )
