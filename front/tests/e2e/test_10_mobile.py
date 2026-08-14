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
    ExtractionAttribute)
from core.models import AIModel, Configuration


class E2EMobileTest(PlaywrightLiveTestCase):
    """Tests responsive mobile (390px) — PHASE-21."""

    VIEWPORT_MOBILE = {"width": 390, "height": 844}

    def setUp(self):
        super().setUp()
        # Creer un utilisateur de test et se connecter
        # / Create a test user and log in
        self.user_test = User.objects.create_user(username="e2e_test_user", password="test1234",
        )
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
            is_active=True)
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
            order=0)
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
        # A.8 : statut binaire (nouveau / commente). Le signal Django passera
        # automatiquement entite_commentee a "commente" lors du create du commentaire.
        # / A.8: binary status. Signal will flip entite_commentee to "commente".
        self.entite_discutable = ExtractedEntity.objects.create(
            job=job,
            extraction_class="axiome",
            extraction_text="Premier paragraphe pour test mobile",
            start_char=0,
            end_char=35,
            statut_debat="nouveau",
        )
        self.entite_commentee = ExtractedEntity.objects.create(
            job=job,
            extraction_class="hypothese",
            extraction_text="Deuxieme paragraphe avec du contenu",
            start_char=60,
            end_char=95,
            statut_debat="nouveau")
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
        self.page.set_viewport_size(self.VIEWPORT_MOBILE,
        )
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        # Le titre doit etre visible dans la toolbar
        # / The title must be visible in the toolbar
        titre = self.page.locator('[data-testid="titre-toolbar"]',
        )
        self.assertTrue(titre.is_visible())
        contenu_titre = titre.text_content()
        self.assertIn("Eric Sadin", contenu_titre,

    )

    def test_navbar_hypostasia_cache_sur_mobile(self):
        """Le mot 'Hypostasia' est cache sur mobile."""
        self.page.set_viewport_size(self.VIEWPORT_MOBILE,
        )
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        mot_hypostasia = self.page.locator(".titre-app-desktop",
        )
        est_cache = mot_hypostasia.evaluate("el => getComputedStyle(el).display === 'none'")
        self.assertTrue(est_cache, "Le mot Hypostasia doit etre cache sur mobile",

    )

    def test_navbar_bouton_toggle_mode_visible(self):
        """Le bouton toggle mode est visible sur mobile."""
        self.page.set_viewport_size(self.VIEWPORT_MOBILE,
        )
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        bouton_mode = self.page.locator('[data-testid="btn-toolbar-mode-mobile"]',
        )
        self.assertTrue(bouton_mode.is_visible())

    def test_navbar_bouton_aide_mobile_visible(self):
        """Le bouton aide mobile est visible sur mobile."""
        self.page.set_viewport_size(self.VIEWPORT_MOBILE,
        )
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        bouton_aide = self.page.locator('[data-testid="btn-toolbar-aide-mobile"]',
        )
        self.assertTrue(bouton_aide.is_visible())

    def test_navbar_boutons_desktop_caches_sur_mobile(self):
        """
        Les boutons `btn-desktop-only` sont caches sur mobile.

        Ce test a vise successivement « btn-toolbar-dashboard » (retire
        avec tout le dashboard) puis « btn-toolbar-extractions » (parti
        dans la note). Un locator qui ne trouve rien rend `False` : le
        test serait reste VERT en ne mesurant plus rien. D'ou le
        `count()` avant l'assertion — il vise maintenant l'aide, qui
        reste en barre.
        / It targeted a removed button; an empty locator returns False,
        so it would have stayed green while measuring nothing.
        """
        self.page.set_viewport_size(self.VIEWPORT_MOBILE,
        )
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        bouton_aide = self.page.locator('[data-testid="btn-toolbar-aide"]',
        )
        self.assertEqual(
            bouton_aide.count(),
            1,
            "Le bouton visé n'existe plus : ce test ne mesure rien.",
        )
        self.assertFalse(bouton_aide.is_visible())

    def test_navbar_boutons_dans_viewport(self):
        """Les boutons toggle mode et aide sont dans le viewport 390px (pas tronques)."""
        self.page.set_viewport_size(self.VIEWPORT_MOBILE,
        )
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        # Le bouton aide doit etre entierement dans le viewport
        # / The help button must be entirely within the viewport
        aide_box = self.page.locator('[data-testid="btn-toolbar-aide-mobile"]').bounding_box()
        bord_droit_aide = aide_box["x"] + aide_box["width"]
        self.assertLessEqual(bord_droit_aide, 390, "Le bouton aide doit etre dans le viewport",

    )

    # ================================================================
    # 2. Pas de scroll horizontal
    # / 2. No horizontal scroll
    # ================================================================

    def test_pas_de_scroll_horizontal(self):
        """Pas de scroll horizontal sur mobile."""
        self.page.set_viewport_size(self.VIEWPORT_MOBILE,
        )
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        deborde = self.page.evaluate(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )
        self.assertFalse(deborde,

    )

    # ================================================================
    # 3. Bottom sheet
    # / 3. Bottom sheet
    # ================================================================

    def test_bottom_sheet_present_dans_dom(self):
        """Le bottom sheet est present dans le DOM."""
        self.page.set_viewport_size(self.VIEWPORT_MOBILE,
        )
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        self.assertGreater(self.page.locator('[data-testid="bottom-sheet"]').count(), 0,

    )

    def test_bottom_sheet_ouvre_et_charge_carte(self):
        """Le bottom sheet s'ouvre et charge la carte d'extraction."""
        self.page.set_viewport_size(self.VIEWPORT_MOBILE,
        )
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        self.page.wait_for_function("() => typeof window.bottomSheet !== 'undefined'", timeout=5000,
        )
        self.page.evaluate(f"window.bottomSheet.ouvrir({self.entite_discutable.pk})")
        # La carte doit etre chargee (la citation source [...] est presente)
        # / The card must be loaded (source citation is present)
        self.page.wait_for_selector('[data-testid="bottom-sheet-carte"]', timeout=5000,
        )
        contenu = self.page.text_content('[data-testid="bottom-sheet-contenu"]')
        self.assertIn("Premier paragraphe pour test mobile", contenu,

    )

    def test_bottom_sheet_ferme_via_backdrop(self):
        """Le bottom sheet se ferme au clic backdrop."""
        self.page.set_viewport_size(self.VIEWPORT_MOBILE,
        )
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        self.page.wait_for_function("() => typeof window.bottomSheet !== 'undefined'", timeout=5000,
        )
        self.page.evaluate(f"window.bottomSheet.ouvrir({self.entite_discutable.pk})")
        # `ouvrir()` pose la classe `visible` sur le voile : c'est le
        # signe qu'il est la et cliquable.
        # / ouvrir() marks the backdrop `visible`; that is the sign it is
        # there and clickable.
        self.page.wait_for_selector('[data-testid="bottom-sheet-backdrop"].visible')
        self.page.click('[data-testid="bottom-sheet-backdrop"]')
        # On attend le retrait de la classe (le DOM), puis on interroge
        # l'etat de l'API (le JS) : deux choses distinctes, la seconde
        # reste donc une vraie verification.
        # / Wait on the DOM, then assert on the JS API: two distinct
        # things, so the assertion still verifies something.
        self.page.wait_for_selector(
            '[data-testid="bottom-sheet-backdrop"]:not(.visible)'
        )
        self.assertFalse(self.page.evaluate("window.bottomSheet.estOuvert()"))

    def test_bottom_sheet_affiche_commentaires(self):
        """A.8 : la carte mobile affiche les commentaires existants inline."""
        self.page.set_viewport_size(self.VIEWPORT_MOBILE,
        )
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        self.page.wait_for_function("() => typeof window.bottomSheet !== 'undefined'", timeout=5000,
        )
        self.page.evaluate(f"window.bottomSheet.ouvrir({self.entite_commentee.pk})")
        self.page.wait_for_selector('[data-testid="bottom-sheet-carte"]', timeout=5000,
        )
        contenu = self.page.text_content('[data-testid="bottom-sheet-contenu"]')
        # Le commentaire existant doit apparaitre inline dans la carte
        # / Existing comment must appear inline in card
        self.assertIn("Commentaire existant pour test mobile", contenu,

    )

    # A.8 : test_bottom_sheet_boutons_statut retire — les boutons statut riche
    # (consensuel, controverse, etc.) ont ete retires (statut binaire automatique).
    # / A.8: removed — rich status buttons removed (binary status, automatic).

    def test_bottom_sheet_bouton_fermer_visible(self):
        """Le bouton X de fermeture est visible dans le bottom sheet."""
        self.page.set_viewport_size(self.VIEWPORT_MOBILE,
        )
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        self.page.wait_for_function("() => typeof window.bottomSheet !== 'undefined'", timeout=5000,
        )
        self.page.evaluate(f"window.bottomSheet.ouvrir({self.entite_discutable.pk})")
        self.page.wait_for_selector('[data-testid="btn-fermer-bottom-sheet"]', timeout=5000,
        )
        bouton_fermer = self.page.locator('[data-testid="btn-fermer-bottom-sheet"]')
        self.assertTrue(bouton_fermer.is_visible(),

    )

    def test_bottom_sheet_ferme_via_bouton_x(self):
        """Le bouton X ferme le bottom sheet."""
        self.page.set_viewport_size(self.VIEWPORT_MOBILE,
        )
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        self.page.wait_for_function("() => typeof window.bottomSheet !== 'undefined'", timeout=5000,
        )
        self.page.evaluate(f"window.bottomSheet.ouvrir({self.entite_discutable.pk})")
        self.page.wait_for_selector('[data-testid="btn-fermer-bottom-sheet"]', timeout=5000,
        )
        self.page.click('[data-testid="btn-fermer-bottom-sheet"]')
        self.page.wait_for_selector(
            '[data-testid="bottom-sheet-backdrop"]:not(.visible)'
        )
        self.assertFalse(self.page.evaluate("window.bottomSheet.estOuvert()"))

    def test_bottom_sheet_pas_de_poignee(self):
        """La poignee de drag n'existe plus dans le bottom sheet."""
        self.page.set_viewport_size(self.VIEWPORT_MOBILE,
        )
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        poignee = self.page.locator('.bottom-sheet-poignee',
        )
        self.assertEqual(poignee.count(), 0, "La poignee ne doit plus exister")

    def test_bottom_sheet_scroll_paragraphe_source(self):
        """
        L'ouverture du bottom sheet scrolle le paragraphe source en vue.

        La page est batie sur le moteur ELEMENT — le seul qui reste. Ce
        test posait auparavant une page ANCIEN dont les surlignages
        venaient de `annoter_html_avec_barres` : sans blocs ni ancres, le
        bottom sheet n'avait aucun `.hl-extraction` vers quoi scroller.
        / Built on the ELEMENT engine, the only one left.
        """
        from core.models import AIModel, ElementDocument, empreinte_du_texte
        from hypostasis_extractor.models import (
            AncrageExtraction, EtatAncrage, ExtractionJob, ExtractedEntity,

        )

        paragraphes = [
            f"Paragraphe {i} avec du texte pour remplir la page."
            for i in range(20)
        ]
        contenu_long = "".join(f"<p>{p}</p>" for p in paragraphes)
        page_longue = self.creer_page_demo("Page longue", contenu_long)
        page_longue.text_readability = "\n\n".join(paragraphes)
        page_longue.save(update_fields=["text_readability"])

        elements = [
            ElementDocument.objects.create(
                page=page_longue, ordre=rang, label="text", texte=texte,
                empreinte_contenu=empreinte_du_texte(texte),
            )
            for rang, texte in enumerate(paragraphes)
        ]

        modele = AIModel.objects.filter(is_active=True).first()
        job = ExtractionJob.objects.create(
            page=page_longue, ai_model=modele, name="Job scroll",
            prompt_description="Test", status="completed", entities_count=1,
        )
        # L'extraction vise un bloc LOIN dans le texte : c'est ce qui
        # oblige la zone de lecture a scroller.
        # / The extraction targets a block far down, forcing a scroll.
        bloc_vise = elements[15]
        entite_loin = ExtractedEntity.objects.create(
            job=job, extraction_class="axiome",
            extraction_text=bloc_vise.texte,
            start_char=0, end_char=len(bloc_vise.texte),
            statut_debat="nouveau")
        AncrageExtraction.objects.create(
            extraction=entite_loin, element=bloc_vise,
            debut_dans_element=0, fin_dans_element=len(bloc_vise.texte),
            ordre_dans_extraction=0, etat_ancrage=EtatAncrage.ANCREE,

        )

        self.page.set_viewport_size(self.VIEWPORT_MOBILE)
        self.naviguer_vers(f"/lire/{page_longue.pk}/",
        )
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
        self.page.evaluate(f"window.bottomSheet.ouvrir({entite_loin.pk})",
        )
        # Le defilement part apres un `setTimeout` de 200 ms puis s'anime.
        # On attend qu'il ait commence — l'assertion qui suit dit de
        # combien il devait bouger.
        # / The scroll starts after a 200 ms timeout, then animates. Wait
        # for it to have started; the assertion below says how far.
        self.page.wait_for_function(
            "() => document.getElementById('zone-lecture').scrollTop > 0"
        )

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
        self.page.set_viewport_size(self.VIEWPORT_MOBILE,
        )
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        self.page.click('[data-testid="btn-toolbar-aide-mobile"]',
        )
        self.page.wait_for_selector('[data-testid="modale-aide"]', timeout=5000)
        contenu_modale = self.page.text_content('[data-testid="modale-aide"]',
        )
        # La modale doit contenir le mot "Tapez" (geste mobile)
        # / The modal must contain the word "Tapez" (mobile gesture)
        self.assertIn("Tapez", contenu_modale,

    )

    def test_aide_mobile_contient_gestes(self):
        """La modale d'aide mobile explique les gestes tactiles."""
        self.page.set_viewport_size(self.VIEWPORT_MOBILE,
        )
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        self.page.click('[data-testid="btn-toolbar-aide-mobile"]',
        )
        self.page.wait_for_selector('[data-testid="modale-aide"]', timeout=5000)
        contenu = self.page.text_content('[data-testid="modale-aide"]',
        )
        self.assertIn("souligné", contenu)
        self.assertIn("Commenter", contenu,
        )
        self.assertIn("Menu", contenu)

    def test_aide_mobile_ferme_au_clic_bouton(self):
        """La modale d'aide se ferme au clic sur le bouton fermer."""
        self.page.set_viewport_size(self.VIEWPORT_MOBILE,
        )
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        self.page.click('[data-testid="btn-toolbar-aide-mobile"]',
        )
        self.page.wait_for_selector('[data-testid="modale-aide"]', timeout=5000)
        # Cliquer sur le bouton fermer (x) dans la modale
        # / Click the close button (x) in the modal
        self.page.click('#btn-fermer-modale-raccourcis')
        self.page.wait_for_selector('[data-testid="modale-aide"]', state="detached")
        modale = self.page.locator('[data-testid="modale-aide"]')
        self.assertEqual(modale.count(), 0, "La modale doit disparaitre apres clic fermer",

    )

    # ================================================================
    # 5. Toggle mode (surlignage → lecture, refonte A.2)
    # / 5. Mode toggle (highlight → reading, A.2 refactor)
    # ================================================================

    def test_toggle_mode_lecture_masque_surlignage(self):
        """Le toggle mode passe en mode lecture (surlignage masque)."""
        self.page.set_viewport_size(self.VIEWPORT_MOBILE,
        )
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        # Cliquer une fois : passe en mode lecture
        # / Click once: switch to reading mode
        # Le gestionnaire de ce bouton pose la classe sur `body` de
        # facon synchrone (keyboard.js) : quand `click()` rend la main,
        # elle est deja posee. Il n'y a rien a attendre.
        # / The handler sets the body class synchronously (keyboard.js):
        # by the time click() returns it is already set. Nothing to wait for.
        self.page.click('[data-testid="btn-toolbar-mode-mobile"]')
        est_mode_lecture = self.page.evaluate(
            "document.body.classList.contains('mode-lecture-mobile')"
        )
        self.assertTrue(est_mode_lecture, "Le body doit avoir la classe mode-lecture-mobile",

    )

    def test_toggle_mode_retour_surlignage(self):
        """Deux clics sur toggle mode revient au mode surlignage."""
        self.page.set_viewport_size(self.VIEWPORT_MOBILE,
        )
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")
        # 2 clics : surlignage → lecture → surlignage (refonte A.2)
        # / 2 clicks: highlight → reading → highlight (A.2 refactor)
        self.page.click('[data-testid="btn-toolbar-mode-mobile"]',
        )
        self.page.click('[data-testid="btn-toolbar-mode-mobile"]')
        est_mode_lecture = self.page.evaluate(
            "document.body.classList.contains('mode-lecture-mobile')"
        )
        self.assertFalse(est_mode_lecture, "Apres 2 clics on doit etre revenu au mode surlignage",

    )

    # ================================================================
    # 6. La navigation mobile, sans tiroir
    # / 6. Mobile navigation, without the drawer
    # ================================================================

    def test_navigation_et_import_atteignables_sur_mobile(self):
        """
        Sur un telephone, on peut encore naviguer ET importer.

        Ce test verifiait que l'arbre lateral prenait tout l'ecran sur
        mobile. L'arbre est retire le 12 aout 2026, et avec lui le seul
        import qu'un telephone avait (la barre cachait le sien sous
        768 px). L'intention devient : le mobile n'est ampute de rien.
        / The test checked the full-screen mobile drawer. With it gone,
        the intent becomes: nothing is amputated on a phone.
        """
        self.page.set_viewport_size(self.VIEWPORT_MOBILE)
        self.naviguer_vers(f"/lire/{self.page_mobile.pk}/")

        for identifiant, ce_que_c_est in [
            ("lien-nav-bases", "les bases"),
            ("lien-nav-carnets", "les carnets"),
            ("btn-toolbar-import", "l'import"),
        ]:
            self.assertTrue(
                self.page.locator(f'[data-testid="{identifiant}"]').is_visible(),
                f"Sur mobile, {ce_que_c_est} doit rester atteignable : "
                f"le tiroir qui les portait a ete retire.",
            )
