"""
Tests E2E PHASE-26a / PHASE-26a-bis — Filtre multi-contributeurs (pilules toggle).
/ E2E tests PHASE-26a / PHASE-26a-bis — Multi-contributor filter (toggle pills).

Lancer avec : uv run python manage.py test front.tests.e2e.test_17_filtre_contributeur -v2
"""

from front.tests.e2e.base import PlaywrightLiveTestCase


class Phase26aBisFiltreContributeurE2ETest(PlaywrightLiveTestCase):
    """Tests E2E pour le filtre multi-contributeurs dans le drawer (pilules toggle)."""

    # ====================================================================
    # Helpers
    # ====================================================================

    def creer_utilisateur(self, username, password="test1234"):
        """Cree un utilisateur via l'ORM.
        / Create a user via ORM."""
        from django.contrib.auth.models import User
        return User.objects.create_user(username=username, password=password)

    def se_connecter(self, username, password="test1234"):
        """Navigue vers /auth/login/, remplit le formulaire et se connecte.
        / Navigate to /auth/login/, fill form and log in."""
        self.naviguer_vers("/auth/login/")
        self.page.fill('[data-testid="input-username"]', username)
        self.page.fill('[data-testid="input-password"]', password)
        self.page.click('[data-testid="btn-submit-login"]')
        self.page.wait_for_url("**/")

    def creer_document_avec_commentaires(self):
        """
        Cree un document avec des extractions commentees par 2 contributeurs.
        Retourne (page, alice, bob).
        / Create a document with extractions commented by 2 contributors.
        Returns (page, alice, bob).
        """
        from core.models import Dossier, Page, VisibiliteDossier
        from hypostasis_extractor.models import (
            AnalyseurSyntaxique, CommentaireExtraction, ExtractedEntity, ExtractionJob,
        )

        owner = self.creer_utilisateur("e2e_p26a_owner")
        alice = self.creer_utilisateur("e2e_alice")
        bob = self.creer_utilisateur("e2e_bob")

        dossier = Dossier.objects.create(
            name="Dossier E2E 26a", owner=owner, visibilite=VisibiliteDossier.PUBLIC,
        )
        page_doc = Page.objects.create(
            url="https://example.com/e2e-26a",
            title="Document E2E 26a",
            html_readability="<p>Premier paragraphe test.</p><p>Deuxieme paragraphe test.</p>",
            text_readability="Premier paragraphe test. Deuxieme paragraphe test.",
            dossier=dossier,
        )
        analyseur = AnalyseurSyntaxique.objects.create(
            name="Test E2E", type_analyseur="analyser", is_active=True,
        )
        job = ExtractionJob.objects.create(
            page=page_doc, analyseur=analyseur, status="completed",
        )

        # Entite commentee par Alice et Bob
        # / Entity commented by Alice and Bob
        entite_1 = ExtractedEntity.objects.create(
            job=job, extraction_text="Premier extrait",
            start_char=0, end_char=15, statut_debat="discutable",
        )
        CommentaireExtraction.objects.create(
            entity=entite_1, user=alice, commentaire="Avis Alice",
        )
        CommentaireExtraction.objects.create(
            entity=entite_1, user=bob, commentaire="Avis Bob",
        )

        # Entite commentee par Alice seulement
        # / Entity commented by Alice only
        entite_2 = ExtractedEntity.objects.create(
            job=job, extraction_text="Deuxieme extrait",
            start_char=27, end_char=45, statut_debat="consensuel",
        )
        CommentaireExtraction.objects.create(
            entity=entite_2, user=alice, commentaire="Avis Alice 2",
        )

        # Entite commentee par Bob seulement
        # / Entity commented by Bob only
        entite_3 = ExtractedEntity.objects.create(
            job=job, extraction_text="Troisieme extrait",
            start_char=50, end_char=68, statut_debat="discute",
        )
        CommentaireExtraction.objects.create(
            entity=entite_3, user=bob, commentaire="Avis Bob 3",
        )

        return page_doc, alice, bob

    def ouvrir_drawer_et_attendre_pilules(self, page_doc):
        """
        Navigue vers le document, ouvre le drawer et attend les pilules contributeurs.
        / Navigate to document, open drawer and wait for contributor pills.
        """
        self.naviguer_vers(f"/lire/{page_doc.pk}/")
        self.page.wait_for_load_state("networkidle")
        self.page.click('[data-testid="btn-toolbar-drawer"]')
        self.page.wait_for_selector('[data-testid="pilules-contributeurs"]', timeout=5000)

    # ====================================================================
    # Tests
    # ====================================================================

    def test_01_pilules_contributeurs_visibles(self):
        """Ouvrir le drawer → pilules contributeurs visibles avec noms et counts.
        / Open drawer → contributor pills visible with names and counts."""
        page_doc, alice, bob = self.creer_document_avec_commentaires()
        self.se_connecter("e2e_p26a_owner")
        self.ouvrir_drawer_et_attendre_pilules(page_doc)

        # Verifier la presence des pilules contributeurs
        # / Check contributor pills presence
        conteneur_pilules = self.page.locator('[data-testid="pilules-contributeurs"]')
        self.assertTrue(conteneur_pilules.is_visible())

        # Verifier les noms dans les pilules / Check names in pills
        contenu_html = conteneur_pilules.inner_html()
        self.assertIn("e2e_alice", contenu_html)
        self.assertIn("e2e_bob", contenu_html)

    def test_02_clic_pilule_filtre_mono(self):
        """Cliquer une pilule → seules les cartes de ce contributeur apparaissent.
        / Click a pill → only that contributor's cards appear."""
        page_doc, alice, bob = self.creer_document_avec_commentaires()
        self.se_connecter("e2e_p26a_owner")
        self.ouvrir_drawer_et_attendre_pilules(page_doc)

        # Cliquer sur la pilule Alice / Click Alice pill
        self.page.click(f'[data-testid="pilule-contributeur-{alice.pk}"]')
        self.page.wait_for_timeout(1500)

        # Alice a commente 2 entites (entite_1 et entite_2) → 2 cartes
        # / Alice commented 2 entities → 2 cards
        cartes = self.page.locator('[data-testid="drawer-carte"]')
        nombre_cartes = cartes.count()
        self.assertEqual(nombre_cartes, 2)

    def test_03_commentaires_autres_dimmes(self):
        """Commentaires des autres → opacite reduite via classe CSS.
        / Other contributors' comments → reduced opacity via CSS class."""
        page_doc, alice, bob = self.creer_document_avec_commentaires()
        self.se_connecter("e2e_p26a_owner")
        self.ouvrir_drawer_et_attendre_pilules(page_doc)

        # Cliquer sur la pilule Alice / Click Alice pill
        self.page.click(f'[data-testid="pilule-contributeur-{alice.pk}"]')
        self.page.wait_for_timeout(1500)

        # Les commentaires de Bob doivent avoir la classe commentaire-hors-filtre
        # / Bob's comments must have the commentaire-hors-filtre class
        commentaires_dimmes = self.page.locator('.commentaire-hors-filtre')
        self.assertGreater(commentaires_dimmes.count(), 0)

    def test_04_pastilles_api_marginalia(self):
        """L'API window.marginalia est bien exposee apres filtre.
        / window.marginalia API is properly exposed after filtering."""
        page_doc, alice, bob = self.creer_document_avec_commentaires()
        self.se_connecter("e2e_p26a_owner")
        self.ouvrir_drawer_et_attendre_pilules(page_doc)

        # Cliquer sur la pilule Bob / Click Bob pill
        self.page.click(f'[data-testid="pilule-contributeur-{bob.pk}"]')
        self.page.wait_for_timeout(1000)

        # Verifier que l'API marginalia existe et retourne un tableau
        # / Check marginalia API exists and returns an array
        self.assertEqual(self.page.evaluate("() => typeof window.marginalia"), "object")
        resultat_filtre = self.page.evaluate("() => Array.isArray(window.marginalia.getContributeurFiltre())")
        self.assertTrue(resultat_filtre)

    def test_05_bouton_tous_restaure_tout(self):
        """Cliquer 'Tous x' → tous les commentaires restaures.
        / Click 'Tous x' → all comments restored."""
        page_doc, alice, bob = self.creer_document_avec_commentaires()
        self.se_connecter("e2e_p26a_owner")
        self.ouvrir_drawer_et_attendre_pilules(page_doc)

        # Filtrer par Alice / Filter by Alice
        self.page.click(f'[data-testid="pilule-contributeur-{alice.pk}"]')
        self.page.wait_for_timeout(1500)

        # Le bouton "Tous x" doit etre visible / "Tous x" button must be visible
        bouton_reset = self.page.locator('[data-testid="btn-reset-contributeurs"]')
        self.assertTrue(bouton_reset.is_visible())

        # Cliquer "Tous x" / Click "Tous x"
        bouton_reset.click()
        self.page.wait_for_timeout(1500)

        # Tous les commentaires doivent etre restaures (pas de dimming)
        # / All comments must be restored (no dimming)
        commentaires_dimmes = self.page.locator('.commentaire-hors-filtre')
        self.assertEqual(commentaires_dimmes.count(), 0)

    def test_06_marginalia_api_expose(self):
        """L'API window.marginalia contient les methodes de filtre.
        / window.marginalia API contains filter methods."""
        page_doc, _, _ = self.creer_document_avec_commentaires()
        self.se_connecter("e2e_p26a_owner")
        self.naviguer_vers(f"/lire/{page_doc.pk}/")
        self.page.wait_for_load_state("networkidle")

        # Verifier que les methodes sont exposees
        # / Check that methods are exposed
        has_get = self.page.evaluate("() => typeof window.marginalia.getContributeurFiltre === 'function'")
        has_reset = self.page.evaluate("() => typeof window.marginalia.resetContributeurFiltre === 'function'")
        self.assertTrue(has_get)
        self.assertTrue(has_reset)

    def test_07_multi_contributeurs_union(self):
        """Cliquer 2 pilules → union des cartes des 2 contributeurs.
        / Click 2 pills → union of cards from both contributors."""
        page_doc, alice, bob = self.creer_document_avec_commentaires()
        self.se_connecter("e2e_p26a_owner")
        self.ouvrir_drawer_et_attendre_pilules(page_doc)

        # Cliquer sur Alice / Click Alice
        self.page.click(f'[data-testid="pilule-contributeur-{alice.pk}"]')
        self.page.wait_for_timeout(1500)

        # Cliquer sur Bob (les 2 pilules sont actives) / Click Bob (both pills active)
        self.page.click(f'[data-testid="pilule-contributeur-{bob.pk}"]')
        self.page.wait_for_timeout(1500)

        # Alice commente entites 1,2 + Bob commente entites 1,3 → union = 3 cartes
        # / Alice commented entities 1,2 + Bob commented entities 1,3 → union = 3 cards
        cartes = self.page.locator('[data-testid="drawer-carte"]')
        nombre_cartes = cartes.count()
        self.assertEqual(nombre_cartes, 3)

    def test_08_pilule_toggle_deselect(self):
        """Cliquer 2 fois sur la meme pilule → desactive le filtre.
        / Click same pill twice → deactivates the filter."""
        page_doc, alice, bob = self.creer_document_avec_commentaires()
        self.se_connecter("e2e_p26a_owner")
        self.ouvrir_drawer_et_attendre_pilules(page_doc)

        # Cliquer Alice (active) / Click Alice (activate)
        self.page.click(f'[data-testid="pilule-contributeur-{alice.pk}"]')
        self.page.wait_for_timeout(1500)

        # Verifier filtre actif : 2 cartes / Verify filter active: 2 cards
        cartes_filtrees = self.page.locator('[data-testid="drawer-carte"]')
        self.assertEqual(cartes_filtrees.count(), 2)

        # Recliquer Alice (desactive) / Click Alice again (deactivate)
        self.page.click(f'[data-testid="pilule-contributeur-{alice.pk}"]')
        self.page.wait_for_timeout(1500)

        # Plus de filtre actif : toutes les cartes (3 entites commentees + 0 sans comm = 3)
        # Sauf si l'entite sans commentaire est aussi affichee... verifions avec le compteur
        # / No active filter: all cards visible
        compteur = self.page.locator('[data-testid="drawer-compteur"]')
        texte_compteur = compteur.inner_text()
        # Sans filtre, doit afficher "N extractions" (pas "N sur M")
        # / Without filter, must show "N extractions" (not "N out of M")
        self.assertIn("extraction", texte_compteur)
        self.assertNotIn("sur", texte_compteur)
