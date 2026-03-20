"""
Tests E2E — Tracabilite : historique des editions (PHASE-27a) + diff versions (PHASE-27b).
/ E2E tests — Traceability: edit history (PHASE-27a) + version diff (PHASE-27b).
"""
from front.tests.e2e.base import PlaywrightLiveTestCase
from core.models import Dossier, Page, PageEdit


class E2ETracabiliteTest(PlaywrightLiveTestCase):
    """Tests de tracabilite : bouton historique, timeline, F5, flux complet."""

    def setUp(self):
        super().setUp()
        # Creer un utilisateur et se connecter
        # / Create a user and log in
        self.utilisateur_test = self.creer_utilisateur_demo()
        self.se_connecter("testuser", "testpass123")

        # Creer un dossier et une page de test
        # / Create a test folder and page
        self.dossier_test = self.creer_dossier_demo("Tracabilite")
        self.dossier_test.owner = self.utilisateur_test
        self.dossier_test.save()
        self.page_test = self.creer_page_demo(
            "Page tracabilite",
            "<p>Contenu de test pour la tracabilite.</p>",
        )
        self.page_test.dossier = self.dossier_test
        self.page_test.save()

    def test_bouton_historique_visible_dans_lecture(self):
        """Le bouton Historique est visible dans la zone de lecture."""
        self.naviguer_vers(f"/lire/{self.page_test.pk}/")
        bouton_historique = self.page.locator('[data-testid="btn-historique"]')
        bouton_historique.wait_for(state="visible", timeout=5000)
        self.assertTrue(bouton_historique.is_visible())

    def test_historique_vide_affiche_message(self):
        """L'historique sans edits affiche le message vide."""
        self.naviguer_vers(f"/lire/{self.page_test.pk}/")
        # Cliquer sur le bouton Historique
        # / Click on the History button
        self.page.locator('[data-testid="btn-historique"]').click()
        self.page.wait_for_selector('[data-testid="historique-page"]', timeout=5000)

        # Pas d'edits → affiche le message vide
        # / No edits → displays the empty message
        etat_vide = self.page.locator('[data-testid="historique-vide"]')
        self.assertTrue(etat_vide.is_visible())

    def test_historique_affiche_entrees_pre_seedees(self):
        """L'historique affiche les entrees pre-creees."""
        # Creer des edits de test
        # / Create test edits
        PageEdit.objects.create(
            page=self.page_test,
            user=self.utilisateur_test,
            type_edit="titre",
            description="Titre changé : 'Ancien' → 'Page tracabilite'",
            donnees_avant={"titre": "Ancien"},
            donnees_apres={"titre": "Page tracabilite"},
        )
        PageEdit.objects.create(
            page=self.page_test,
            user=self.utilisateur_test,
            type_edit="locuteur",
            description="Locuteur renommé : 'Speaker 1' → 'Alice' (tous)",
            donnees_avant={"locuteur": "Speaker 1", "portee": "tous"},
            donnees_apres={"locuteur": "Alice"},
        )

        self.naviguer_vers(f"/lire/{self.page_test.pk}/")
        self.page.locator('[data-testid="btn-historique"]').click()
        self.page.wait_for_selector('[data-testid="historique-page"]', timeout=5000)

        # Verifier que les entrees sont presentes
        # / Verify entries are present
        entrees = self.page.locator('[data-testid="historique-entree"]')
        self.assertGreaterEqual(entrees.count(), 2)

        # Verifier les badges de type
        # / Verify type badges
        badges = self.page.locator('[data-testid="badge-type-edit"]')
        self.assertGreaterEqual(badges.count(), 2)

    def test_f5_historique_affiche_page_complete(self):
        """F5 sur /lire/{pk}/historique/ affiche la page complete."""
        # Creer au moins un edit pour eviter l'etat vide
        # / Create at least one edit to avoid the empty state
        PageEdit.objects.create(
            page=self.page_test,
            user=self.utilisateur_test,
            type_edit="titre",
            description="Test F5",
            donnees_avant={"titre": "A"},
            donnees_apres={"titre": "B"},
        )

        self.naviguer_vers(f"/lire/{self.page_test.pk}/historique/")
        # La page complete contient le shell Hypostasia
        # / The full page contains the Hypostasia shell
        self.page.wait_for_selector('[data-testid="historique-page"]', timeout=5000)
        contenu_page = self.page.content()
        self.assertIn("Hypostasia", contenu_page)
        self.assertIn("historique-page", contenu_page)
        self.assertIn("historique-entree", contenu_page)

    def test_flux_complet_editer_titre_puis_historique(self):
        """
        Flux complet : editer le titre inline → naviguer vers historique →
        verifier que l'entree apparait avec le bon diff → retour lecture.
        / Full flow: edit title inline → navigate to history →
        verify the entry appears with the correct diff → back to reading.
        """
        self.naviguer_vers(f"/lire/{self.page_test.pk}/")
        self.page.wait_for_selector('[data-testid="lecture-zone-principale"]', timeout=5000)

        # Etape 1 : cliquer sur le titre pour l'editer
        # / Step 1: click on the title to edit it
        titre_element = self.page.locator(".titre-page-cliquable")
        titre_element.wait_for(state="visible", timeout=5000)
        titre_element.click()

        # Attendre que l'input d'edition apparaisse (gere par JS hypostasia.js)
        # / Wait for the edit input to appear (managed by JS hypostasia.js)
        input_titre = self.page.locator("input.edit-titre-input")
        input_titre.wait_for(state="visible", timeout=3000)

        # Effacer et taper le nouveau titre
        # / Clear and type the new title
        input_titre.fill("Titre Modifié E2E")
        input_titre.press("Enter")

        # Attendre la reponse HTMX (le toast "Titre modifie" confirme)
        # / Wait for the HTMX response (the "Title modified" toast confirms)
        self.page.wait_for_timeout(1500)

        # Etape 2 : naviguer vers l'historique
        # / Step 2: navigate to history
        bouton_historique = self.page.locator('[data-testid="btn-historique"]')
        bouton_historique.wait_for(state="visible", timeout=5000)
        bouton_historique.click()
        self.page.wait_for_selector('[data-testid="historique-page"]', timeout=5000)

        # Etape 3 : verifier que l'entree d'edition du titre est presente
        # / Step 3: verify the title edit entry is present
        entrees = self.page.locator('[data-testid="historique-entree"]')
        self.assertGreaterEqual(entrees.count(), 1)

        # Verifier que le badge "Titre modifié" est present
        # / Verify the "Title modified" badge is present
        contenu_historique = self.page.content()
        self.assertIn("Titre modifi", contenu_historique)

        # Verifier que le diff del/ins est present avec le bon contenu
        # / Verify the del/ins diff is present with the correct content
        self.assertIn("Titre Modifi", contenu_historique)

        # Etape 4 : cliquer "Retour à la lecture"
        # / Step 4: click "Back to reading"
        bouton_retour = self.page.locator('[data-testid="btn-retour-lecture"]')
        bouton_retour.click()
        self.page.wait_for_selector('[data-testid="lecture-zone-principale"]', timeout=5000)

        # Verifier qu'on est bien revenu a la lecture
        # / Verify we're back to reading
        self.assertTrue(
            self.page.locator('[data-testid="lecture-zone-principale"]').is_visible()
        )

    def test_retour_lecture_depuis_historique(self):
        """Le bouton 'Retour a la lecture' ramene a la page de lecture."""
        # Creer un edit pour ne pas avoir l'etat vide
        # / Create an edit to avoid the empty state
        PageEdit.objects.create(
            page=self.page_test,
            user=self.utilisateur_test,
            type_edit="titre",
            description="Test retour",
            donnees_avant={"titre": "A"},
            donnees_apres={"titre": "B"},
        )

        self.naviguer_vers(f"/lire/{self.page_test.pk}/historique/")
        self.page.wait_for_selector('[data-testid="historique-page"]', timeout=5000)

        # Cliquer retour
        # / Click back
        self.page.locator('[data-testid="btn-retour-lecture"]').click()
        self.page.wait_for_selector('[data-testid="lecture-zone-principale"]', timeout=5000)
        self.assertTrue(
            self.page.locator('[data-testid="lecture-zone-principale"]').is_visible()
        )


# =============================================================================
# Tests E2E — Diff side-by-side entre versions (PHASE-27b)
# / E2E tests — Side-by-side diff between versions (PHASE-27b)
# =============================================================================


class E2EDiffVersionsTest(PlaywrightLiveTestCase):
    """Tests du diff side-by-side entre versions de pages."""

    def setUp(self):
        super().setUp()
        # Creer un utilisateur et se connecter
        # / Create a user and log in
        self.utilisateur_test = self.creer_utilisateur_demo()
        self.se_connecter("testuser", "testpass123")

        # Creer un dossier avec une page V1
        # / Create a folder with a V1 page
        self.dossier_test = self.creer_dossier_demo("Diff versions")
        self.dossier_test.owner = self.utilisateur_test
        self.dossier_test.save()

        self.page_v1 = self.creer_page_demo(
            "Page diff V1",
            "<p>Premier paragraphe original.</p><p>Deuxieme paragraphe.</p>",
        )
        self.page_v1.text_readability = "Premier paragraphe original.\n\nDeuxieme paragraphe."
        self.page_v1.dossier = self.dossier_test
        self.page_v1.version_number = 1
        self.page_v1.save()

    def _creer_version_2(self):
        """Cree une deuxieme version de la page.
        / Create a second version of the page."""
        self.page_v2 = Page.objects.create(
            title="Page diff V2",
            html_readability="<p>Premier paragraphe modifie.</p><p>Deuxieme paragraphe.</p><p>Troisieme.</p>",
            text_readability="Premier paragraphe modifie.\n\nDeuxieme paragraphe.\n\nTroisieme.",
            dossier=self.dossier_test,
            parent_page=self.page_v1,
            version_number=2,
        )

    def test_bouton_comparer_visible_si_2_versions(self):
        """La pilule Comparer est visible quand il y a >= 2 versions."""
        self._creer_version_2()
        self.naviguer_vers(f"/lire/{self.page_v1.pk}/")
        bouton = self.page.locator('[data-testid="btn-comparer-versions"]')
        bouton.wait_for(state="visible", timeout=5000)
        self.assertTrue(bouton.is_visible())

    def test_bouton_comparer_absent_si_1_version(self):
        """La pilule Comparer n'est pas visible quand il y a 1 seule version."""
        self.naviguer_vers(f"/lire/{self.page_v1.pk}/")
        self.page.wait_for_selector('[data-testid="lecture-zone-principale"]', timeout=5000)
        bouton = self.page.locator('[data-testid="btn-comparer-versions"]')
        self.assertEqual(bouton.count(), 0)

    def test_clic_comparer_affiche_diff(self):
        """Cliquer sur Comparer affiche la vue 2 colonnes."""
        self._creer_version_2()
        self.naviguer_vers(f"/lire/{self.page_v1.pk}/")
        self.page.locator('[data-testid="btn-comparer-versions"]').click()
        self.page.wait_for_selector('[data-testid="diff-versions-pages"]', timeout=5000)
        self.assertTrue(
            self.page.locator('[data-testid="diff-colonnes"]').is_visible()
        )

    def test_f5_diff_affiche_page_complete(self):
        """F5 sur /lire/{pk}/comparer/?v2={pk2} affiche la page complete."""
        self._creer_version_2()
        self.naviguer_vers(f"/lire/{self.page_v1.pk}/comparer/?v2={self.page_v2.pk}")
        self.page.wait_for_selector('[data-testid="diff-versions-pages"]', timeout=5000)
        contenu = self.page.content()
        self.assertIn("Hypostasia", contenu)
        self.assertIn("diff-versions-pages", contenu)

    def test_retour_lecture_depuis_diff(self):
        """Le bouton retour ramene a la page de lecture."""
        self._creer_version_2()
        self.naviguer_vers(f"/lire/{self.page_v1.pk}/comparer/?v2={self.page_v2.pk}")
        self.page.wait_for_selector('[data-testid="diff-versions-pages"]', timeout=5000)
        self.page.locator('[data-testid="btn-retour-lecture-diff"]').click()
        self.page.wait_for_selector('[data-testid="lecture-zone-principale"]', timeout=5000)
        self.assertTrue(
            self.page.locator('[data-testid="lecture-zone-principale"]').is_visible()
        )

    def test_dropdowns_changent_versions(self):
        """Les selects de version sont presents et ont les bonnes options."""
        self._creer_version_2()
        self.naviguer_vers(f"/lire/{self.page_v1.pk}/comparer/?v2={self.page_v2.pk}")
        self.page.wait_for_selector('[data-testid="diff-versions-pages"]', timeout=5000)
        select_gauche = self.page.locator('[data-testid="select-version-gauche"]')
        select_droite = self.page.locator('[data-testid="select-version-droite"]')
        self.assertTrue(select_gauche.is_visible())
        self.assertTrue(select_droite.is_visible())
        # Verifier que les options contiennent V1 et V2
        # / Verify options contain V1 and V2
        options = select_gauche.locator("option")
        self.assertGreaterEqual(options.count(), 2)
