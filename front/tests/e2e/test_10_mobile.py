"""
Tests E2E — Mobile : navbar, bottom sheet, aide, toggle mode, surlignage.
Couvre les criteres de validation de la PHASE-21 du plan.
/ E2E tests — Mobile: navbar, bottom sheet, help, mode toggle, highlighting.
Covers the PHASE-21 validation criteria from the plan.
"""
from django.contrib.auth.models import User
from front.tests.e2e.base import PlaywrightLiveTestCase
from hypostasis_extractor.models import (
    ExtractionJob,
    ExtractedEntity,
    CommentaireExtraction,
    AnalyseurSyntaxique,
    PromptPiece,
    AnalyseurExample,
    ExampleExtraction,
    ExtractionAttribute,
)
from core.models import AIModel, Configuration


class E2EMobileTest(PlaywrightLiveTestCase):
    """Tests responsive mobile (390px) — PHASE-21."""

    VIEWPORT_MOBILE = {"width": 390, "height": 844}

    def setUp(self):
        super().setUp()
        # Creer un utilisateur de test et se connecter
        # / Create a test user and log in
        self.user_test = User.objects.create_user(username="e2e_test_user", password="test1234")
        self.se_connecter("e2e_test_user", "test1234")

        # Creer une page avec du contenu et des extractions pour tester le mobile
        # / Create a page with content and extractions to test mobile
        self.page_mobile = self.creer_page_demo(
            "Eric Sadin — Critique de la technologie et intelligence artificielle",
            "<p>Premier paragraphe pour test mobile bottom sheet extraction.</p>"
            "<p>Deuxieme paragraphe avec du contenu supplementaire.</p>",
            owner=self.user_test,
        )
        modele_mock = AIModel.objects.create(
            name="Mock Mobile",
            model_choice="mock_default",
            is_active=True,
        )

        # Configurer l'IA active pour les tests d'analyse
        # / Configure AI active for analysis tests
        configuration = Configuration.get_solo()
        configuration.ai_active = True
        configuration.ai_model = modele_mock
        configuration.save()

        # Creer un analyseur avec exemple few-shot pour les tests d'analyse
        # / Create an analyzer with few-shot example for analysis tests
        self.analyseur = AnalyseurSyntaxique.objects.create(
            name="Analyseur Mobile",
            type_analyseur="analyser",
            is_active=True,
        )
        PromptPiece.objects.create(
            analyseur=self.analyseur,
            name="Instruction",
            role="instruction",
            content="Analyse le texte.",
            order=0,
        )
        exemple = AnalyseurExample.objects.create(
            analyseur=self.analyseur,
            name="Exemple mobile",
            example_text="Texte exemple.",
            order=0,
        )
        extraction_exemple = ExampleExtraction.objects.create(
            example=exemple,
            extraction_class="hypostase",
            extraction_text="Texte exemple",
            order=0,
        )
        ExtractionAttribute.objects.create(
            extraction=extraction_exemple,
            key="Hypostases",
            value="axiome",
            order=0,
        )

        # Creer un job d'extraction avec des entites
        # / Create an extraction job with entities
        job = ExtractionJob.objects.create(
            page=self.page_mobile,
            ai_model=modele_mock,
            name="Extraction mobile",
            prompt_description="Test mobile",
            status="completed",
            entities_count=2,
        )
        self.entite_discutable = ExtractedEntity.objects.create(
            job=job,
            extraction_class="axiome",
            extraction_text="Premier paragraphe pour test mobile",
            start_char=0,
            end_char=35,
            statut_debat="discutable",
        )
        self.entite_commentee = ExtractedEntity.objects.create(
            job=job,
            extraction_class="hypothese",
            extraction_text="Deuxieme paragraphe avec du contenu",
            start_char=60,
            end_char=95,
            statut_debat="discute",
        )
        CommentaireExtraction.objects.create(
            entity=self.entite_commentee,
            user=self.user_test,
            commentaire="Commentaire existant pour test mobile.",
        )

    # ================================================================
    # 1. Navbar mobile : titre tronque, boutons visibles
    # / 1. Mobile navbar: truncated title, visible buttons
    # ================================================================

    def test_navbar_titre_tronque_visible(self):
        """Le titre du document est tronque et visible dans la navbar mobile."""
        self.page.set_viewport_size(self.VIEWPORT_MOBILE)
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        # Le titre doit etre visible dans la toolbar
        # / The title must be visible in the toolbar
        titre = self.page.locator('[data-testid="titre-toolbar"]')
        self.assertTrue(titre.is_visible())
        contenu_titre = titre.text_content()
        self.assertIn("Eric Sadin", contenu_titre)

    def test_navbar_hypostasia_cache_sur_mobile(self):
        """Le mot 'Hypostasia' est cache sur mobile."""
        self.page.set_viewport_size(self.VIEWPORT_MOBILE)
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        mot_hypostasia = self.page.locator(".titre-app-desktop")
        est_cache = mot_hypostasia.evaluate("el => getComputedStyle(el).display === 'none'")
        self.assertTrue(est_cache, "Le mot Hypostasia doit etre cache sur mobile")

    def test_navbar_bouton_toggle_mode_visible(self):
        """Le bouton toggle mode est visible sur mobile."""
        self.page.set_viewport_size(self.VIEWPORT_MOBILE)
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        bouton_mode = self.page.locator('[data-testid="btn-toolbar-mode-mobile"]')
        self.assertTrue(bouton_mode.is_visible())

    def test_navbar_bouton_aide_mobile_visible(self):
        """Le bouton aide mobile est visible sur mobile."""
        self.page.set_viewport_size(self.VIEWPORT_MOBILE)
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        bouton_aide = self.page.locator('[data-testid="btn-toolbar-aide-mobile"]')
        self.assertTrue(bouton_aide.is_visible())

    def test_navbar_boutons_desktop_caches_sur_mobile(self):
        """Les boutons desktop (Dashboard, Analyser, Extractions) sont caches sur mobile."""
        self.page.set_viewport_size(self.VIEWPORT_MOBILE)
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        bouton_dashboard = self.page.locator('[data-testid="btn-toolbar-dashboard"]')
        self.assertFalse(bouton_dashboard.is_visible())

    def test_navbar_boutons_dans_viewport(self):
        """Les boutons toggle mode et aide sont dans le viewport 390px (pas tronques)."""
        self.page.set_viewport_size(self.VIEWPORT_MOBILE)
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        # Le bouton aide doit etre entierement dans le viewport
        # / The help button must be entirely within the viewport
        aide_box = self.page.locator('[data-testid="btn-toolbar-aide-mobile"]').bounding_box()
        bord_droit_aide = aide_box["x"] + aide_box["width"]
        self.assertLessEqual(bord_droit_aide, 390, "Le bouton aide doit etre dans le viewport")

    # ================================================================
    # 2. Pas de scroll horizontal
    # / 2. No horizontal scroll
    # ================================================================

    def test_pas_de_scroll_horizontal(self):
        """Pas de scroll horizontal sur mobile."""
        self.page.set_viewport_size(self.VIEWPORT_MOBILE)
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        deborde = self.page.evaluate(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )
        self.assertFalse(deborde)

    # ================================================================
    # 3. Bottom sheet
    # / 3. Bottom sheet
    # ================================================================

    def test_bottom_sheet_present_dans_dom(self):
        """Le bottom sheet est present dans le DOM."""
        self.page.set_viewport_size(self.VIEWPORT_MOBILE)
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        self.assertGreater(self.page.locator('[data-testid="bottom-sheet"]').count(), 0)

    def test_bottom_sheet_ouvre_et_charge_carte(self):
        """Le bottom sheet s'ouvre et charge la carte d'extraction."""
        self.page.set_viewport_size(self.VIEWPORT_MOBILE)
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        self.page.wait_for_function("() => typeof window.bottomSheet !== 'undefined'", timeout=5000)
        self.page.evaluate(f"window.bottomSheet.ouvrir({self.entite_discutable.pk})")
        # La carte doit etre chargee (le statut et les boutons d'action sont presents)
        # / The card must be loaded (status and action buttons are present)
        self.page.wait_for_selector('[data-testid="bottom-sheet-carte"]', timeout=5000)
        contenu = self.page.text_content('[data-testid="bottom-sheet-contenu"]')
        self.assertIn("Consensuel", contenu)

    def test_bottom_sheet_ferme_via_backdrop(self):
        """Le bottom sheet se ferme au clic backdrop."""
        self.page.set_viewport_size(self.VIEWPORT_MOBILE)
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        self.page.wait_for_function("() => typeof window.bottomSheet !== 'undefined'", timeout=5000)
        self.page.evaluate(f"window.bottomSheet.ouvrir({self.entite_discutable.pk})")
        self.page.wait_for_timeout(500)
        self.page.click('[data-testid="bottom-sheet-backdrop"]')
        self.page.wait_for_timeout(500)
        self.assertFalse(self.page.evaluate("window.bottomSheet.estOuvert()"))

    def test_bottom_sheet_bouton_commenter(self):
        """Le bouton Commenter charge le fil de discussion."""
        self.page.set_viewport_size(self.VIEWPORT_MOBILE)
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        self.page.wait_for_function("() => typeof window.bottomSheet !== 'undefined'", timeout=5000)
        self.page.evaluate(f"window.bottomSheet.ouvrir({self.entite_commentee.pk})")
        self.page.wait_for_selector('[data-testid="bottom-sheet-btn-commenter"]', timeout=5000)
        self.page.click('[data-testid="bottom-sheet-btn-commenter"]')
        self.attendre_htmx()
        contenu = self.page.text_content('[data-testid="bottom-sheet-contenu"]')
        self.assertIn("e2e_test_user", contenu)

    def test_bottom_sheet_boutons_statut(self):
        """Les boutons de statut sont presents dans la carte."""
        self.page.set_viewport_size(self.VIEWPORT_MOBILE)
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        self.page.wait_for_function("() => typeof window.bottomSheet !== 'undefined'", timeout=5000)
        self.page.evaluate(f"window.bottomSheet.ouvrir({self.entite_discutable.pk})")
        self.page.wait_for_selector('[data-testid="bottom-sheet-btn-consensuel"]', timeout=5000)
        self.assertTrue(self.page.locator('[data-testid="bottom-sheet-btn-consensuel"]').is_visible())

    def test_bottom_sheet_bouton_fermer_visible(self):
        """Le bouton X de fermeture est visible dans le bottom sheet."""
        self.page.set_viewport_size(self.VIEWPORT_MOBILE)
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        self.page.wait_for_function("() => typeof window.bottomSheet !== 'undefined'", timeout=5000)
        self.page.evaluate(f"window.bottomSheet.ouvrir({self.entite_discutable.pk})")
        self.page.wait_for_selector('[data-testid="btn-fermer-bottom-sheet"]', timeout=5000)
        bouton_fermer = self.page.locator('[data-testid="btn-fermer-bottom-sheet"]')
        self.assertTrue(bouton_fermer.is_visible())

    def test_bottom_sheet_ferme_via_bouton_x(self):
        """Le bouton X ferme le bottom sheet."""
        self.page.set_viewport_size(self.VIEWPORT_MOBILE)
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        self.page.wait_for_function("() => typeof window.bottomSheet !== 'undefined'", timeout=5000)
        self.page.evaluate(f"window.bottomSheet.ouvrir({self.entite_discutable.pk})")
        self.page.wait_for_selector('[data-testid="btn-fermer-bottom-sheet"]', timeout=5000)
        self.page.click('[data-testid="btn-fermer-bottom-sheet"]')
        self.page.wait_for_timeout(500)
        self.assertFalse(self.page.evaluate("window.bottomSheet.estOuvert()"))

    def test_bottom_sheet_pas_de_poignee(self):
        """La poignee de drag n'existe plus dans le bottom sheet."""
        self.page.set_viewport_size(self.VIEWPORT_MOBILE)
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        poignee = self.page.locator('.bottom-sheet-poignee')
        self.assertEqual(poignee.count(), 0, "La poignee ne doit plus exister")

    def test_bottom_sheet_scroll_paragraphe_source(self):
        """L'ouverture du bottom sheet scrolle le paragraphe source en vue."""
        # Creer une page avec assez de contenu pour avoir du scroll
        # / Create a page with enough content to have scroll
        contenu_long = "".join(
            f"<p>Paragraphe {i} avec du texte pour remplir la page.</p>"
            for i in range(20)
        )
        page_longue = self.creer_page_demo("Page longue", contenu_long)
        from hypostasis_extractor.models import ExtractionJob, ExtractedEntity
        from core.models import AIModel
        modele = AIModel.objects.filter(is_active=True).first()
        job = ExtractionJob.objects.create(
            page=page_longue, ai_model=modele, name="Job scroll",
            prompt_description="Test", status="completed", entities_count=1,
        )
        # Creer une extraction sur un paragraphe loin dans le texte
        # / Create an extraction on a paragraph far down in the text
        entite_loin = ExtractedEntity.objects.create(
            job=job, extraction_class="axiome",
            extraction_text="Paragraphe 15 avec du texte",
            start_char=500, end_char=527, statut_debat="discutable",
        )

        self.page.set_viewport_size(self.VIEWPORT_MOBILE)
        self.naviguer_vers(f"/lire/{page_longue.pk}/")
        self.page.wait_for_function(
            "() => typeof window.bottomSheet !== 'undefined'", timeout=5000,
        )

        # Verifier que la zone de lecture est scrollable
        # / Check that the reading zone is scrollable
        peut_scroller = self.page.evaluate(
            "document.getElementById('zone-lecture').scrollHeight > "
            "document.getElementById('zone-lecture').clientHeight"
        )
        if not peut_scroller:
            # Pas assez de contenu pour scroller, skip
            return

        # Ouvrir le bottom sheet sur l'extraction loin dans le texte
        # / Open bottom sheet on the extraction far in the text
        self.page.evaluate(f"window.bottomSheet.ouvrir({entite_loin.pk})")
        self.page.wait_for_timeout(1500)

        # Le scroll de #zone-lecture doit avoir bouge
        # / The #zone-lecture scroll should have moved
        scroll_position = self.page.evaluate(
            "document.getElementById('zone-lecture').scrollTop"
        )
        self.assertGreater(
            scroll_position, 0,
            "Le scroll doit avoir bouge pour rendre le paragraphe source visible"
        )

    # ================================================================
    # 4. Aide mobile via HTMX
    # / 4. Mobile help via HTMX
    # ================================================================

    def test_aide_mobile_ouvre_modale(self):
        """Le bouton aide mobile charge la modale de gestes tactiles."""
        self.page.set_viewport_size(self.VIEWPORT_MOBILE)
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        self.page.click('[data-testid="btn-toolbar-aide-mobile"]')
        self.page.wait_for_selector('[data-testid="modale-aide"]', timeout=5000)
        contenu_modale = self.page.text_content('[data-testid="modale-aide"]')
        # La modale doit contenir le mot "Tapez" (geste mobile)
        # / The modal must contain the word "Tapez" (mobile gesture)
        self.assertIn("Tapez", contenu_modale)

    def test_aide_mobile_contient_gestes(self):
        """La modale d'aide mobile explique les gestes tactiles."""
        self.page.set_viewport_size(self.VIEWPORT_MOBILE)
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        self.page.click('[data-testid="btn-toolbar-aide-mobile"]')
        self.page.wait_for_selector('[data-testid="modale-aide"]', timeout=5000)
        contenu = self.page.text_content('[data-testid="modale-aide"]')
        self.assertIn("souligné", contenu)
        self.assertIn("Commenter", contenu)
        self.assertIn("Menu", contenu)

    def test_aide_mobile_ferme_au_clic_bouton(self):
        """La modale d'aide se ferme au clic sur le bouton fermer."""
        self.page.set_viewport_size(self.VIEWPORT_MOBILE)
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        self.page.click('[data-testid="btn-toolbar-aide-mobile"]')
        self.page.wait_for_selector('[data-testid="modale-aide"]', timeout=5000)
        # Cliquer sur le bouton fermer (x) dans la modale
        # / Click the close button (x) in the modal
        self.page.click('#btn-fermer-modale-raccourcis')
        self.page.wait_for_timeout(300)
        modale = self.page.locator('[data-testid="modale-aide"]')
        self.assertEqual(modale.count(), 0, "La modale doit disparaitre apres clic fermer")

    # ================================================================
    # 5. Toggle mode (surlignage → lecture, refonte A.2)
    # / 5. Mode toggle (highlight → reading, A.2 refactor)
    # ================================================================

    def test_toggle_mode_lecture_masque_surlignage(self):
        """Le toggle mode passe en mode lecture (surlignage masque)."""
        self.page.set_viewport_size(self.VIEWPORT_MOBILE)
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        # Cliquer une fois : passe en mode lecture
        # / Click once: switch to reading mode
        self.page.click('[data-testid="btn-toolbar-mode-mobile"]')
        self.page.wait_for_timeout(300)
        est_mode_lecture = self.page.evaluate(
            "document.body.classList.contains('mode-lecture-mobile')"
        )
        self.assertTrue(est_mode_lecture, "Le body doit avoir la classe mode-lecture-mobile")

    def test_toggle_mode_retour_surlignage(self):
        """Deux clics sur toggle mode revient au mode surlignage."""
        self.page.set_viewport_size(self.VIEWPORT_MOBILE)
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        # 2 clics : surlignage → lecture → surlignage (refonte A.2)
        # / 2 clicks: highlight → reading → highlight (A.2 refactor)
        self.page.click('[data-testid="btn-toolbar-mode-mobile"]')
        self.page.click('[data-testid="btn-toolbar-mode-mobile"]')
        self.page.wait_for_timeout(300)
        est_mode_lecture = self.page.evaluate(
            "document.body.classList.contains('mode-lecture-mobile')"
        )
        self.assertFalse(est_mode_lecture, "Apres 2 clics on doit etre revenu au mode surlignage")

    # ================================================================
    # 6. Arbre plein ecran mobile
    # / 6. Full-screen mobile tree
    # ================================================================

    def test_arbre_plein_ecran(self):
        """L'arbre prend tout l'ecran sur mobile."""
        self.page.set_viewport_size(self.VIEWPORT_MOBILE)
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        self.ouvrir_arbre()
        arbre = self.page.locator('[data-testid="arbre-overlay"]')
        self.assertTrue(arbre.is_visible())
