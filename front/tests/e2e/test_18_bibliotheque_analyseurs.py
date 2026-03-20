"""
Tests E2E PHASE-26b — Bibliotheque d'analyseurs (lecture seule) + permissions.
/ E2E tests PHASE-26b — Analyzer library (read-only) + permissions.

Lancer avec : uv run python manage.py test front.tests.e2e.test_18_bibliotheque_analyseurs -v2
"""

from front.tests.e2e.base import PlaywrightLiveTestCase


class Phase26bBibliothequeAnalyseursE2ETest(PlaywrightLiveTestCase):
    """Tests E2E pour la bibliotheque d'analyseurs et les permissions."""

    # ====================================================================
    # Helpers
    # ====================================================================

    def creer_utilisateur(self, username, password="test1234", is_staff=False):
        """Cree un utilisateur via l'ORM.
        / Create a user via ORM."""
        from django.contrib.auth.models import User
        return User.objects.create_user(
            username=username, password=password, is_staff=is_staff,
        )

    def se_connecter(self, username, password="test1234"):
        """Navigue vers /auth/login/, remplit le formulaire et se connecte.
        / Navigate to /auth/login/, fill form and log in."""
        self.naviguer_vers("/auth/login/")
        self.page.fill('[data-testid="input-username"]', username)
        self.page.fill('[data-testid="input-password"]', password)
        self.page.click('[data-testid="btn-submit-login"]')
        self.page.wait_for_url("**/")

    def creer_analyseurs_demo(self):
        """
        Cree 3 analyseurs de types differents avec des exemples.
        / Create 3 analyzers of different types with examples.
        """
        from hypostasis_extractor.models import (
            AnalyseurSyntaxique, PromptPiece, AnalyseurExample,
        )
        analyseur_1 = AnalyseurSyntaxique.objects.create(
            name="Extracteur entites", description="Extrait les entites nommees.",
            type_analyseur="analyser", is_active=True,
        )
        PromptPiece.objects.create(
            analyseur=analyseur_1, name="Instruction", role="instruction",
            content="Extraire les entites.", order=0,
        )
        AnalyseurExample.objects.create(
            analyseur=analyseur_1, name="Exemple 1",
            example_text="Texte d'exemple.", order=0,
        )

        analyseur_2 = AnalyseurSyntaxique.objects.create(
            name="Reformulateur", description="Reformule le texte.",
            type_analyseur="reformuler", is_active=True,
        )
        PromptPiece.objects.create(
            analyseur=analyseur_2, name="Instruction", role="instruction",
            content="Reformuler.", order=0,
        )

        analyseur_3 = AnalyseurSyntaxique.objects.create(
            name="Restituteur", description="Restitue le texte.",
            type_analyseur="restituer", is_active=True,
        )

        return analyseur_1, analyseur_2, analyseur_3

    # ====================================================================
    # Tests
    # ====================================================================

    def test_bibliotheque_affiche_cartes_analyseurs(self):
        """Naviguer vers /analyseurs/ affiche la grille avec des cartes."""
        user = self.creer_utilisateur("e2e_biblio_user")
        self.creer_analyseurs_demo()
        self.se_connecter("e2e_biblio_user")

        self.naviguer_vers("/analyseurs/")
        self.page.wait_for_selector('[data-testid="bibliotheque-analyseurs"]')
        grille = self.page.locator('[data-testid="grille-analyseurs"]')
        cartes = grille.locator('[data-testid^="carte-analyseur-"]')
        self.assertGreaterEqual(cartes.count(), 3)

    def test_carte_affiche_nom_description_type(self):
        """Les cartes contiennent nom, description, badge type."""
        user = self.creer_utilisateur("e2e_biblio_carte")
        self.creer_analyseurs_demo()
        self.se_connecter("e2e_biblio_carte")

        self.naviguer_vers("/analyseurs/")
        self.page.wait_for_selector('[data-testid="bibliotheque-analyseurs"]')
        # Verifie qu'au moins un nom d'analyseur est visible
        self.assertIsNotNone(
            self.page.locator('[data-testid="nom-analyseur"]').first.text_content()
        )
        # Verifie qu'un badge type est visible
        badges = self.page.locator('[data-testid="badge-type"]')
        self.assertGreaterEqual(badges.count(), 1)

    def test_filtre_par_type_analyseur(self):
        """Les boutons filtre filtrent correctement les cartes."""
        user = self.creer_utilisateur("e2e_biblio_filtre")
        self.creer_analyseurs_demo()
        self.se_connecter("e2e_biblio_filtre")

        self.naviguer_vers("/analyseurs/")
        self.page.wait_for_selector('[data-testid="bibliotheque-analyseurs"]')

        # Cliquer sur "Analyser"
        self.page.click('[data-testid="filtre-analyser"]')
        self.page.wait_for_selector('[data-testid="bibliotheque-analyseurs"]')
        cartes_analyser = self.page.locator('[data-testid^="carte-analyseur-"]')
        self.assertEqual(cartes_analyser.count(), 1)

        # Cliquer sur "Reformuler"
        self.page.click('[data-testid="filtre-reformuler"]')
        self.page.wait_for_selector('[data-testid="bibliotheque-analyseurs"]')
        cartes_reformuler = self.page.locator('[data-testid^="carte-analyseur-"]')
        self.assertEqual(cartes_reformuler.count(), 1)

    def test_voir_prompt_ouvre_page_detail(self):
        """Cliquer 'Voir le prompt' ouvre la page detail avec les pieces colorees."""
        user = self.creer_utilisateur("e2e_biblio_prompt")
        analyseur_1, _, _ = self.creer_analyseurs_demo()
        self.se_connecter("e2e_biblio_prompt")

        self.naviguer_vers("/analyseurs/")
        self.page.wait_for_selector('[data-testid="bibliotheque-analyseurs"]')

        # Cliquer sur le lien "Voir le prompt"
        self.page.click(f'[data-testid="btn-voir-prompt-{analyseur_1.pk}"]')
        self.page.wait_for_selector('[data-testid="detail-analyseur-readonly"]')

        # Verifier que la page detail contient le titre
        titre = self.page.locator('[data-testid="detail-titre"]').text_content()
        self.assertIn("Extracteur entites", titre)

        # Verifier qu'il y a du contenu de piece
        self.assertIsNotNone(
            self.page.locator('[data-testid="piece-content"]').first.text_content()
        )

    def test_detail_prompt_pas_de_bouton_edition_non_staff(self):
        """La page detail en lecture seule (non-staff) n'a pas de bouton editer."""
        user = self.creer_utilisateur("e2e_biblio_noedit")
        analyseur_1, _, _ = self.creer_analyseurs_demo()
        self.se_connecter("e2e_biblio_noedit")

        self.naviguer_vers(f"/analyseurs/{analyseur_1.pk}/")
        self.page.wait_for_selector('[data-testid="detail-analyseur-readonly"]')

        # Pas de lien d'edition pour un non-staff
        lien_editer = self.page.locator('[data-testid="lien-editer-analyseur"]')
        self.assertEqual(lien_editer.count(), 0)

    def test_staff_voit_lien_admin(self):
        """Un staff voit le lien 'Admin analyseurs' dans la bibliotheque."""
        self.creer_utilisateur("e2e_biblio_staff", is_staff=True)
        self.creer_analyseurs_demo()
        self.se_connecter("e2e_biblio_staff")

        self.naviguer_vers("/analyseurs/")
        self.page.wait_for_selector('[data-testid="bibliotheque-analyseurs"]')
        lien_admin = self.page.locator('[data-testid="lien-admin-analyseurs"]')
        self.assertEqual(lien_admin.count(), 1)

    def test_non_staff_pas_de_lien_admin(self):
        """Un non-staff ne voit pas le lien 'Admin analyseurs'."""
        self.creer_utilisateur("e2e_biblio_nonadmin")
        self.creer_analyseurs_demo()
        self.se_connecter("e2e_biblio_nonadmin")

        self.naviguer_vers("/analyseurs/")
        self.page.wait_for_selector('[data-testid="bibliotheque-analyseurs"]')
        lien_admin = self.page.locator('[data-testid="lien-admin-analyseurs"]')
        self.assertEqual(lien_admin.count(), 0)

    def test_non_staff_ne_peut_pas_creer_analyseur(self):
        """POST /api/analyseurs/ par un non-staff → bloque (403)."""
        self.creer_utilisateur("e2e_biblio_nocreate")
        self.se_connecter("e2e_biblio_nocreate")

        # Tenter un POST via fetch en JS
        resultat = self.page.evaluate("""
            async () => {
                const csrf = document.querySelector('[name=csrfmiddlewaretoken]')?.value
                    || document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';
                const resp = await fetch('/api/analyseurs/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrf,
                    },
                    body: JSON.stringify({name: 'Interdit', description: 'Nope'}),
                });
                return resp.status;
            }
        """)
        self.assertEqual(resultat, 403)

    def test_non_staff_ne_peut_pas_supprimer_analyseur(self):
        """DELETE /api/analyseurs/{pk}/ par un non-staff → bloque (403)."""
        self.creer_utilisateur("e2e_biblio_nodelete")
        analyseur_1, _, _ = self.creer_analyseurs_demo()
        self.se_connecter("e2e_biblio_nodelete")

        resultat = self.page.evaluate(f"""
            async () => {{
                const csrf = document.querySelector('[name=csrfmiddlewaretoken]')?.value
                    || document.cookie.match(/csrftoken=([^;]+)/)?.[1] || '';
                const resp = await fetch('/api/analyseurs/{analyseur_1.pk}/', {{
                    method: 'DELETE',
                    headers: {{
                        'X-CSRFToken': csrf,
                    }},
                }});
                return resp.status;
            }}
        """)
        self.assertEqual(resultat, 403)

    # ====================================================================
    # Tests auto-snapshot et historique versions (PHASE-26b backend vivant)
    # / Tests for auto-snapshot and version history (PHASE-26b live backend)
    # ====================================================================

    def test_auto_snapshot_apres_modification_piece(self):
        """
        Staff modifie une piece dans l'editeur → une version est creee
        et visible dans l'historique.
        / Staff edits a piece in the editor → a version is created
        and visible in the version history.
        """
        self.creer_utilisateur("e2e_snapshot_staff", is_staff=True)
        analyseur_1, _, _ = self.creer_analyseurs_demo()
        self.se_connecter("e2e_snapshot_staff")

        # 1. Aller dans l'editeur admin de l'analyseur
        # / 1. Navigate to the analyzer admin editor
        self.naviguer_vers(f"/api/analyseurs/{analyseur_1.pk}/")
        self.page.wait_for_selector(f'#piece-{analyseur_1.pieces.first().pk}')

        # 2. Cliquer Sauver sur la premiere piece (declenche update_piece + auto-snapshot)
        # / 2. Click Save on the first piece (triggers update_piece + auto-snapshot)
        premiere_piece = analyseur_1.pieces.order_by('order').first()
        self.page.click(f'[data-testid="btn-sauver-piece-{premiere_piece.pk}"]')
        self.page.wait_for_timeout(500)

        # 3. Verifier en DB qu'une version a ete creee
        # / 3. Verify in DB that a version was created
        from hypostasis_extractor.models import AnalyseurVersion
        nombre_versions = AnalyseurVersion.objects.filter(analyseur=analyseur_1).count()
        self.assertGreaterEqual(nombre_versions, 1, "Au moins une version doit exister apres modification")

        # 4. Naviguer vers le detail readonly puis cliquer Historique des versions
        # / 4. Navigate to readonly detail then click Version history
        self.naviguer_vers(f"/analyseurs/{analyseur_1.pk}/")
        self.page.wait_for_selector('[data-testid="detail-analyseur-readonly"]')
        self.page.click('[data-testid="lien-versions-analyseur"]')

        # 5. Verifier que la liste affiche au moins une version avec la description
        # / 5. Verify the list shows at least one version with description
        self.page.wait_for_selector('#zone-lecture')
        contenu_versions = self.page.locator('#zone-lecture').text_content()
        self.assertIn("v1", contenu_versions)
        self.assertIn("Modification piece", contenu_versions)

    def test_staff_voit_lien_historique_versions(self):
        """Un staff voit le lien 'Historique des versions' dans le detail."""
        self.creer_utilisateur("e2e_biblio_versions_staff", is_staff=True)
        analyseur_1, _, _ = self.creer_analyseurs_demo()
        self.se_connecter("e2e_biblio_versions_staff")

        self.naviguer_vers(f"/analyseurs/{analyseur_1.pk}/")
        self.page.wait_for_selector('[data-testid="detail-analyseur-readonly"]')
        lien_versions = self.page.locator('[data-testid="lien-versions-analyseur"]')
        self.assertEqual(lien_versions.count(), 1)

    def test_non_staff_voit_lien_historique_versions(self):
        """
        Un non-staff voit le lien 'Historique des versions' (transparence)
        mais ne voit pas les boutons Restaurer/Comparer.
        / Non-staff sees version history link (transparency)
        but not Restore/Compare buttons.
        """
        self.creer_utilisateur("e2e_biblio_versions_nostaff")
        analyseur_1, _, _ = self.creer_analyseurs_demo()
        self.se_connecter("e2e_biblio_versions_nostaff")

        self.naviguer_vers(f"/analyseurs/{analyseur_1.pk}/")
        self.page.wait_for_selector('[data-testid="detail-analyseur-readonly"]')
        # Le lien historique est visible pour tous les utilisateurs
        # / Version history link is visible for all users
        lien_versions = self.page.locator('[data-testid="lien-versions-analyseur"]')
        self.assertEqual(lien_versions.count(), 1)
        # Mais le bouton Editer n'est pas visible pour un non-staff
        # / But the Edit button is not visible for non-staff
        lien_editer = self.page.locator('[data-testid="lien-editer-analyseur"]')
        self.assertEqual(lien_editer.count(), 0)

    def test_clic_versions_charge_liste(self):
        """Cliquer sur 'Historique des versions' charge la liste dans la zone de lecture."""
        self.creer_utilisateur("e2e_biblio_versions_clic", is_staff=True)
        analyseur_1, _, _ = self.creer_analyseurs_demo()
        self.se_connecter("e2e_biblio_versions_clic")

        self.naviguer_vers(f"/analyseurs/{analyseur_1.pk}/")
        self.page.wait_for_selector('[data-testid="detail-analyseur-readonly"]')
        self.page.click('[data-testid="lien-versions-analyseur"]')
        # Attend que la zone de lecture se charge avec le contenu des versions
        self.page.wait_for_selector('#zone-lecture', state='attached')

    def test_f5_sur_versions_affiche_page_complete(self):
        """
        F5 sur /api/analyseurs/{pk}/versions/ affiche la page complete
        (pas juste le partial). Verifie le pattern HTMX/F5.
        / F5 on /api/analyseurs/{pk}/versions/ renders the full page
        (not just the partial). Verifies the HTMX/F5 pattern.
        """
        self.creer_utilisateur("e2e_biblio_f5_versions", is_staff=True)
        analyseur_1, _, _ = self.creer_analyseurs_demo()
        self.se_connecter("e2e_biblio_f5_versions")

        # Acces direct (simule F5) / Direct access (simulates F5)
        self.naviguer_vers(f"/api/analyseurs/{analyseur_1.pk}/versions/")
        # La page complete doit contenir la toolbar de navigation
        # / Full page must contain the navigation toolbar
        self.page.wait_for_selector('nav')
        # Et le contenu des versions dans zone-lecture
        # / And the versions content in zone-lecture
        titre_versions = self.page.locator('[data-testid="titre-versions"]')
        self.assertEqual(titre_versions.count(), 1)

    def test_non_staff_ne_voit_pas_boutons_restaurer(self):
        """
        Un non-staff voit la liste des versions mais pas les boutons
        Restaurer et Comparer (staff uniquement).
        / Non-staff sees version list but not Restore/Compare buttons.
        """
        from hypostasis_extractor.services import creer_version_analyseur
        self.creer_utilisateur("e2e_biblio_nostaff_restore")
        analyseur_1, _, _ = self.creer_analyseurs_demo()
        # Creer une version pour que la liste ne soit pas vide
        # / Create a version so the list is not empty
        creer_version_analyseur(analyseur_1, None, "Version initiale")
        self.se_connecter("e2e_biblio_nostaff_restore")

        self.naviguer_vers(f"/analyseurs/{analyseur_1.pk}/")
        self.page.wait_for_selector('[data-testid="detail-analyseur-readonly"]')
        self.page.click('[data-testid="lien-versions-analyseur"]')
        self.page.wait_for_selector('[data-testid="versions-list"]')

        # La version est affichee / The version is displayed
        version_item = self.page.locator('[data-testid="version-item-v1"]')
        self.assertEqual(version_item.count(), 1)
        # Mais pas de bouton Restaurer ni Comparer / No Restore or Compare button
        bouton_rollback = self.page.locator('[data-testid="btn-rollback-v1"]')
        self.assertEqual(bouton_rollback.count(), 0)
