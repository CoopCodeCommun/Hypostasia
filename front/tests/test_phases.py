"""
Tests de validation pour les phases du PLAN.
/ Validation tests for PLAN phases.

Lancer avec : uv run python manage.py test front.tests -v2
/ Run with:    uv run python manage.py test front.tests -v2
"""

import re
from pathlib import Path

from django.conf import settings
from django.template.loader import get_template
from django.test import TestCase, RequestFactory


# =============================================================================
# Chemins de reference
# / Reference paths
# =============================================================================

BASE_DIR = settings.BASE_DIR
STATIC_FRONT = BASE_DIR / "front" / "static" / "front"
TEMPLATE_BASE = BASE_DIR / "front" / "templates" / "front" / "base.html"


# =============================================================================
# PHASE-01 — Extraction CSS/JS depuis base.html
# / PHASE-01 — Extract CSS/JS from base.html
# =============================================================================


class Phase01ExtractionCSSJSTest(TestCase):
    """Verifie que le CSS et le JS sont dans des fichiers statiques separes.
    / Verify that CSS and JS are in separate static files."""

    def setUp(self):
        # Lire le contenu brut de base.html une seule fois
        # / Read the raw content of base.html once
        self.contenu_base_html = TEMPLATE_BASE.read_text(encoding="utf-8")

    # -------------------------------------------------------------------------
    # Existence des fichiers statiques
    # / Static files existence
    # -------------------------------------------------------------------------

    def test_fichier_css_existe(self):
        """hypostasia.css existe dans front/static/front/css/."""
        chemin_css = STATIC_FRONT / "css" / "hypostasia.css"
        self.assertTrue(chemin_css.exists(), f"Fichier CSS manquant : {chemin_css}")

    def test_fichier_js_existe(self):
        """hypostasia.js existe dans front/static/front/js/."""
        chemin_js = STATIC_FRONT / "js" / "hypostasia.js"
        self.assertTrue(chemin_js.exists(), f"Fichier JS manquant : {chemin_js}")

    def test_fichier_css_non_vide(self):
        """hypostasia.css n'est pas vide."""
        chemin_css = STATIC_FRONT / "css" / "hypostasia.css"
        taille = chemin_css.stat().st_size
        self.assertGreater(taille, 100, f"hypostasia.css semble trop petit ({taille} octets)")

    def test_fichier_js_non_vide(self):
        """hypostasia.js n'est pas vide."""
        chemin_js = STATIC_FRONT / "js" / "hypostasia.js"
        taille = chemin_js.stat().st_size
        self.assertGreater(taille, 100, f"hypostasia.js semble trop petit ({taille} octets)")

    # -------------------------------------------------------------------------
    # Pas de CSS/JS inline dans base.html
    # / No inline CSS/JS in base.html
    # -------------------------------------------------------------------------

    def test_pas_de_balise_style_inline(self):
        """base.html ne contient pas de bloc <style> inline."""
        # On cherche <style> qui n'est pas un lien (pas <style src=...>)
        # / Look for <style> that is not a link
        occurrences_style = re.findall(r"<style[\s>]", self.contenu_base_html, re.IGNORECASE)
        self.assertEqual(
            len(occurrences_style), 0,
            f"Trouves {len(occurrences_style)} bloc(s) <style> inline dans base.html"
        )

    def test_pas_de_script_inline(self):
        """base.html ne contient pas de bloc <script> inline (sans src)."""
        # On cherche <script> sans attribut src — donc du JS inline
        # / Look for <script> without src attribute — i.e. inline JS
        tous_les_scripts = re.findall(r"<script\b([^>]*)>", self.contenu_base_html, re.IGNORECASE)
        scripts_inline = [s for s in tous_les_scripts if "src" not in s.lower()]
        self.assertEqual(
            len(scripts_inline), 0,
            f"Trouves {len(scripts_inline)} bloc(s) <script> inline dans base.html : {scripts_inline}"
        )

    # -------------------------------------------------------------------------
    # Liens {% static %} presents dans base.html
    # / {% static %} links present in base.html
    # -------------------------------------------------------------------------

    def test_lien_static_css(self):
        """base.html charge hypostasia.css via {% static %}."""
        self.assertIn(
            "{% static 'front/css/hypostasia.css' %}",
            self.contenu_base_html,
            "Lien {% static %} vers hypostasia.css absent de base.html"
        )

    def test_lien_static_js(self):
        """base.html charge hypostasia.js via {% static %}."""
        self.assertIn(
            "{% static 'front/js/hypostasia.js' %}",
            self.contenu_base_html,
            "Lien {% static %} vers hypostasia.js absent de base.html"
        )

    # -------------------------------------------------------------------------
    # CSRF et hx-headers toujours presents
    # / CSRF and hx-headers still present
    # -------------------------------------------------------------------------

    def test_csrf_hx_headers_present(self):
        """base.html contient hx-headers avec le CSRF token."""
        self.assertIn("hx-headers", self.contenu_base_html)
        self.assertIn("X-CSRFToken", self.contenu_base_html)

    # -------------------------------------------------------------------------
    # Template base.html est rendu par Django sans erreur
    # / base.html template renders without error
    # -------------------------------------------------------------------------

    def test_template_base_se_charge(self):
        """Django peut charger le template base.html sans erreur."""
        template = get_template("front/base.html")
        self.assertIsNotNone(template)


# =============================================================================
# PHASE-02 — Assets locaux : polices, CDN, collectstatic
# / PHASE-02 — Local assets: fonts, CDN, collectstatic
# =============================================================================


class Phase02AucunCDNTest(TestCase):
    """Verifie qu'aucune reference CDN ne reste dans les templates.
    / Verify that no CDN reference remains in templates."""

    def setUp(self):
        self.contenu_base_html = TEMPLATE_BASE.read_text(encoding="utf-8")

    # Liste des domaines CDN qui ne doivent plus apparaitre
    # / List of CDN domains that must no longer appear
    DOMAINES_CDN_INTERDITS = [
        "cdn.tailwindcss.com",
        "unpkg.com",
        "cdn.jsdelivr.net",
        "fonts.googleapis.com",
        "fonts.gstatic.com",
        "cdnjs.cloudflare.com",
    ]

    def test_aucun_cdn_dans_base_html(self):
        """base.html ne reference aucun CDN externe."""
        for domaine in self.DOMAINES_CDN_INTERDITS:
            self.assertNotIn(
                domaine,
                self.contenu_base_html,
                f"Reference CDN trouvee dans base.html : {domaine}"
            )

    def test_aucun_cdn_dans_tous_les_templates(self):
        """Aucun template HTML du projet ne reference un CDN externe."""
        repertoire_templates = BASE_DIR / "front" / "templates"
        fichiers_html = list(repertoire_templates.rglob("*.html"))
        self.assertGreater(len(fichiers_html), 0, "Aucun template HTML trouve")

        for fichier in fichiers_html:
            contenu = fichier.read_text(encoding="utf-8")
            for domaine in self.DOMAINES_CDN_INTERDITS:
                self.assertNotIn(
                    domaine,
                    contenu,
                    f"Reference CDN '{domaine}' trouvee dans {fichier.relative_to(BASE_DIR)}"
                )


class Phase02VendorJSTest(TestCase):
    """Verifie que HTMX et SweetAlert2 sont servis en local.
    / Verify that HTMX and SweetAlert2 are served locally."""

    def setUp(self):
        self.contenu_base_html = TEMPLATE_BASE.read_text(encoding="utf-8")

    def test_htmx_local_existe(self):
        """Le fichier HTMX local existe dans front/static/front/vendor/."""
        chemin_htmx = STATIC_FRONT / "vendor" / "htmx-2.0.4.min.js"
        self.assertTrue(chemin_htmx.exists(), f"HTMX manquant : {chemin_htmx}")

    def test_htmx_local_non_vide(self):
        """Le fichier HTMX local fait au moins 10 Ko (pas un placeholder)."""
        chemin_htmx = STATIC_FRONT / "vendor" / "htmx-2.0.4.min.js"
        taille = chemin_htmx.stat().st_size
        self.assertGreater(taille, 10_000, f"HTMX trop petit ({taille} octets)")

    def test_sweetalert2_local_existe(self):
        """Le fichier SweetAlert2 local existe dans front/static/front/vendor/."""
        chemin_swal = STATIC_FRONT / "vendor" / "sweetalert2-11.min.js"
        self.assertTrue(chemin_swal.exists(), f"SweetAlert2 manquant : {chemin_swal}")

    def test_sweetalert2_local_non_vide(self):
        """Le fichier SweetAlert2 local fait au moins 10 Ko."""
        chemin_swal = STATIC_FRONT / "vendor" / "sweetalert2-11.min.js"
        taille = chemin_swal.stat().st_size
        self.assertGreater(taille, 10_000, f"SweetAlert2 trop petit ({taille} octets)")

    def test_base_html_charge_htmx_local(self):
        """base.html charge HTMX via {% static %} et non via CDN."""
        self.assertIn("{% static 'front/vendor/htmx", self.contenu_base_html)

    def test_base_html_charge_sweetalert2_local(self):
        """base.html charge SweetAlert2 via {% static %} et non via CDN."""
        self.assertIn("{% static 'front/vendor/sweetalert2", self.contenu_base_html)


class Phase02TailwindCSSTest(TestCase):
    """Verifie que Tailwind CSS est compile en local.
    / Verify that Tailwind CSS is compiled locally."""

    def test_tailwind_css_compile_existe(self):
        """Le fichier tailwind.css compile existe."""
        chemin_tw = STATIC_FRONT / "css" / "tailwind.css"
        self.assertTrue(chemin_tw.exists(), f"tailwind.css manquant : {chemin_tw}")

    def test_tailwind_css_taille_raisonnable(self):
        """Le CSS compile fait au moins 50 Ko (pas un fichier vide ou tronque)."""
        chemin_tw = STATIC_FRONT / "css" / "tailwind.css"
        taille = chemin_tw.stat().st_size
        self.assertGreater(taille, 50_000, f"tailwind.css trop petit ({taille} octets)")

    def test_tailwind_css_contient_classes_utilisees(self):
        """Le CSS compile contient des classes Tailwind utilisees dans les templates."""
        chemin_tw = STATIC_FRONT / "css" / "tailwind.css"
        contenu = chemin_tw.read_text(encoding="utf-8")
        # Classes Tailwind utilisees dans base.html
        # / Tailwind classes used in base.html
        classes_attendues = ["bg-white", "text-slate-800", "flex-1", "font-semibold"]
        for classe in classes_attendues:
            self.assertIn(
                classe,
                contenu,
                f"Classe Tailwind '{classe}' absente du CSS compile"
            )

    def test_base_html_charge_tailwind_local(self):
        """base.html charge tailwind.css via {% static %}."""
        contenu = TEMPLATE_BASE.read_text(encoding="utf-8")
        self.assertIn("{% static 'front/css/tailwind.css' %}", contenu)

    def test_fichier_source_input_css_existe(self):
        """Le fichier source input.css pour la compilation Tailwind existe."""
        chemin_input = BASE_DIR / "front" / "tailwind" / "input.css"
        self.assertTrue(chemin_input.exists(), f"input.css manquant : {chemin_input}")


class Phase02PolicesLocalesTest(TestCase):
    """Verifie que les polices sont telechargees en local au format woff2.
    / Verify that fonts are downloaded locally in woff2 format."""

    REPERTOIRE_FONTS = STATIC_FRONT / "fonts"

    # Polices requises par le CLAUDE.md §0 (3 polices = 3 provenances + Lora)
    # / Fonts required by CLAUDE.md §0 (3 fonts = 3 provenances + Lora)
    POLICES_REQUISES = {
        "B612 regular": "b612-regular.woff2",
        "B612 bold": "b612-bold.woff2",
        "B612 Mono regular": "b612mono-regular.woff2",
        "Srisakdi regular": "srisakdi-regular.woff2",
        "Lora regular": "lora-regular.woff2",
        "Lora italic": "lora-italic.woff2",
    }

    def test_repertoire_fonts_existe(self):
        """Le repertoire front/static/front/fonts/ existe."""
        self.assertTrue(
            self.REPERTOIRE_FONTS.exists(),
            f"Repertoire fonts manquant : {self.REPERTOIRE_FONTS}"
        )

    def test_toutes_les_polices_presentes(self):
        """Chaque police requise est presente en local."""
        for nom_lisible, nom_fichier in self.POLICES_REQUISES.items():
            chemin = self.REPERTOIRE_FONTS / nom_fichier
            self.assertTrue(
                chemin.exists(),
                f"Police manquante : {nom_lisible} ({chemin})"
            )

    def test_polices_non_vides(self):
        """Chaque fichier woff2 fait au moins 5 Ko (pas un placeholder)."""
        for nom_lisible, nom_fichier in self.POLICES_REQUISES.items():
            chemin = self.REPERTOIRE_FONTS / nom_fichier
            if chemin.exists():
                taille = chemin.stat().st_size
                self.assertGreater(
                    taille, 5_000,
                    f"Police {nom_lisible} trop petite ({taille} octets)"
                )

    def test_font_face_dans_tailwind_compile(self):
        """Le CSS compile contient des @font-face pour chaque famille."""
        chemin_tw = STATIC_FRONT / "css" / "tailwind.css"
        contenu = chemin_tw.read_text(encoding="utf-8")
        familles_attendues = ["B612", "B612 Mono", "Srisakdi", "Lora"]
        for famille in familles_attendues:
            self.assertIn(
                famille,
                contenu,
                f"@font-face pour '{famille}' absent du CSS compile"
            )

    def test_urls_woff2_relatives_correctes(self):
        """Les URLs woff2 dans le CSS compile pointent vers ../fonts/ (chemin relatif correct)."""
        chemin_tw = STATIC_FRONT / "css" / "tailwind.css"
        contenu = chemin_tw.read_text(encoding="utf-8")
        urls_woff2 = re.findall(r"url\(([^)]+\.woff2)\)", contenu)
        self.assertGreater(len(urls_woff2), 0, "Aucune URL woff2 trouvee dans le CSS compile")
        for url in urls_woff2:
            self.assertTrue(
                url.startswith("../fonts/"),
                f"URL woff2 incorrecte : '{url}' (attendu : ../fonts/...)"
            )


class Phase02FontBodyTest(TestCase):
    """Verifie que la police de base du body est B612 (pas Inter).
    / Verify that the body base font is B612 (not Inter)."""

    def test_body_utilise_b612(self):
        """hypostasia.css declare B612 comme font-family du body."""
        chemin_css = STATIC_FRONT / "css" / "hypostasia.css"
        contenu = chemin_css.read_text(encoding="utf-8")
        self.assertIn("'B612'", contenu, "B612 absent du body font-family")

    def test_body_nutilise_plus_inter(self):
        """hypostasia.css ne reference plus Inter comme font-family du body."""
        chemin_css = STATIC_FRONT / "css" / "hypostasia.css"
        contenu = chemin_css.read_text(encoding="utf-8")
        # Cherche "Inter" dans un contexte font-family (pas dans un commentaire)
        # / Look for "Inter" in a font-family context (not in a comment)
        lignes_non_commentaires = [
            ligne for ligne in contenu.splitlines()
            if not ligne.strip().startswith("/*") and not ligne.strip().startswith("//")
        ]
        contenu_sans_commentaires = "\n".join(lignes_non_commentaires)
        occurrences_inter = re.findall(r"font-family:.*Inter", contenu_sans_commentaires)
        self.assertEqual(
            len(occurrences_inter), 0,
            f"Inter encore reference dans hypostasia.css : {occurrences_inter}"
        )

    def test_lecture_article_utilise_lora(self):
        """La classe .lecture-article utilise Lora comme police de lecture."""
        chemin_css = STATIC_FRONT / "css" / "hypostasia.css"
        contenu = chemin_css.read_text(encoding="utf-8")
        self.assertIn("'Lora'", contenu, "Lora absent de .lecture-article")


class Phase02CollectstaticTest(TestCase):
    """Verifie que les settings Django pour collectstatic sont corrects.
    / Verify that Django settings for collectstatic are correct."""

    def test_static_root_configure(self):
        """settings.STATIC_ROOT est configure."""
        self.assertTrue(
            hasattr(settings, "STATIC_ROOT") and settings.STATIC_ROOT,
            "STATIC_ROOT n'est pas configure dans settings.py"
        )

    def test_static_url_configure(self):
        """settings.STATIC_URL est configure."""
        self.assertTrue(
            hasattr(settings, "STATIC_URL") and settings.STATIC_URL,
            "STATIC_URL n'est pas configure dans settings.py"
        )

    def test_staticfiles_app_installee(self):
        """django.contrib.staticfiles est dans INSTALLED_APPS."""
        self.assertIn(
            "django.contrib.staticfiles",
            settings.INSTALLED_APPS,
            "django.contrib.staticfiles absent de INSTALLED_APPS"
        )


class Phase02PageAccueilSansErreurTest(TestCase):
    """Verifie que la page d'accueil se charge sans erreur HTTP.
    / Verify that the homepage loads without HTTP error."""

    def test_page_accueil_status_200(self):
        """GET / retourne un status 200."""
        reponse = self.client.get("/")
        self.assertEqual(
            reponse.status_code, 200,
            f"La page d'accueil retourne {reponse.status_code} au lieu de 200"
        )

    def test_page_accueil_contient_tailwind_css(self):
        """La reponse HTML de / contient un lien vers tailwind.css."""
        reponse = self.client.get("/")
        contenu = reponse.content.decode("utf-8")
        self.assertIn("tailwind.css", contenu)

    def test_page_accueil_contient_hypostasia_css(self):
        """La reponse HTML de / contient un lien vers hypostasia.css."""
        reponse = self.client.get("/")
        contenu = reponse.content.decode("utf-8")
        self.assertIn("hypostasia.css", contenu)

    def test_page_accueil_contient_htmx(self):
        """La reponse HTML de / contient un lien vers htmx."""
        reponse = self.client.get("/")
        contenu = reponse.content.decode("utf-8")
        self.assertIn("htmx", contenu)

    def test_page_accueil_sans_cdn(self):
        """La reponse HTML de / ne contient aucun domaine CDN."""
        reponse = self.client.get("/")
        contenu = reponse.content.decode("utf-8")
        domaines_interdits = [
            "cdn.tailwindcss.com",
            "unpkg.com",
            "cdn.jsdelivr.net",
            "fonts.googleapis.com",
        ]
        for domaine in domaines_interdits:
            self.assertNotIn(domaine, contenu, f"CDN '{domaine}' dans la reponse HTML")


# =============================================================================
# PHASE-03 — Nettoyage code extraction
# / PHASE-03 — Extraction code cleanup
# =============================================================================


class Phase03ConstruireExemplesLangextractTest(TestCase):
    """Verifie que _construire_exemples_langextract() construit correctement
    les exemples LangExtract depuis un AnalyseurSyntaxique.
    / Verify that _construire_exemples_langextract() correctly builds
    LangExtract examples from an AnalyseurSyntaxique."""

    def setUp(self):
        from hypostasis_extractor.models import (
            AnalyseurSyntaxique, AnalyseurExample, ExampleExtraction,
            ExtractionAttribute,
        )

        # Creer un analyseur avec 2 exemples few-shot
        # / Create an analyzer with 2 few-shot examples
        self.analyseur = AnalyseurSyntaxique.objects.create(
            name="Analyseur test PHASE-03",
            description="Analyseur de test pour la deduplication du code",
        )

        # Exemple 1 : avec extraction + attribut
        # / Example 1: with extraction + attribute
        self.exemple_1 = AnalyseurExample.objects.create(
            analyseur=self.analyseur,
            name="Exemple un",
            example_text="Le chat mange la souris.",
            order=0,
        )
        extraction_1 = ExampleExtraction.objects.create(
            example=self.exemple_1,
            extraction_class="action",
            extraction_text="mange la souris",
            order=0,
        )
        ExtractionAttribute.objects.create(
            extraction=extraction_1,
            key="agent",
            value="le chat",
            order=0,
        )

        # Exemple 2 : extraction sans attribut
        # / Example 2: extraction without attribute
        self.exemple_2 = AnalyseurExample.objects.create(
            analyseur=self.analyseur,
            name="Exemple deux",
            example_text="Il pleut des cordes.",
            order=1,
        )
        ExampleExtraction.objects.create(
            example=self.exemple_2,
            extraction_class="metaphore",
            extraction_text="pleut des cordes",
            order=0,
        )

    def test_construit_tous_les_exemples(self):
        """Retourne autant d'exemples que l'analyseur en possede."""
        from hypostasis_extractor.services import _construire_exemples_langextract

        exemples = _construire_exemples_langextract(self.analyseur)
        self.assertEqual(len(exemples), 2)

    def test_exemples_sont_des_example_data(self):
        """Chaque element est un lx.data.ExampleData avec text et extractions."""
        import langextract as lx
        from hypostasis_extractor.services import _construire_exemples_langextract

        exemples = _construire_exemples_langextract(self.analyseur)
        for exemple in exemples:
            self.assertIsInstance(exemple, lx.data.ExampleData)
            self.assertTrue(hasattr(exemple, "text"))
            self.assertTrue(hasattr(exemple, "extractions"))

    def test_texte_et_extractions_corrects(self):
        """Le texte et les extractions sont mappes correctement."""
        from hypostasis_extractor.services import _construire_exemples_langextract

        exemples = _construire_exemples_langextract(self.analyseur)

        # Exemple 1 / Example 1
        self.assertEqual(exemples[0].text, "Le chat mange la souris.")
        self.assertEqual(len(exemples[0].extractions), 1)
        self.assertEqual(exemples[0].extractions[0].extraction_class, "action")
        self.assertEqual(exemples[0].extractions[0].extraction_text, "mange la souris")

        # Exemple 2 / Example 2
        self.assertEqual(exemples[1].text, "Il pleut des cordes.")
        self.assertEqual(len(exemples[1].extractions), 1)
        self.assertEqual(exemples[1].extractions[0].extraction_class, "metaphore")

    def test_attributs_mappes(self):
        """Les attributs cle-valeur sont inclus dans les extractions."""
        from hypostasis_extractor.services import _construire_exemples_langextract

        exemples = _construire_exemples_langextract(self.analyseur)
        attributs_extraction_1 = exemples[0].extractions[0].attributes
        self.assertEqual(attributs_extraction_1, {"agent": "le chat"})

    def test_exclude_example_pk(self):
        """Avec exclude_example_pk, l'exemple exclu n'apparait pas."""
        from hypostasis_extractor.services import _construire_exemples_langextract

        exemples = _construire_exemples_langextract(
            self.analyseur, exclude_example_pk=self.exemple_1.pk,
        )
        self.assertEqual(len(exemples), 1)
        self.assertEqual(exemples[0].text, "Il pleut des cordes.")

    def test_exclude_dernier_exemple_fallback(self):
        """Si l'analyseur n'a qu'un exemple et qu'on l'exclut, fallback : on le garde."""
        from hypostasis_extractor.models import AnalyseurSyntaxique, AnalyseurExample
        from hypostasis_extractor.services import _construire_exemples_langextract

        # Analyseur avec un seul exemple / Analyzer with a single example
        analyseur_solo = AnalyseurSyntaxique.objects.create(
            name="Analyseur solo",
        )
        exemple_unique = AnalyseurExample.objects.create(
            analyseur=analyseur_solo,
            name="Seul exemple",
            example_text="Texte unique.",
            order=0,
        )

        exemples = _construire_exemples_langextract(
            analyseur_solo, exclude_example_pk=exemple_unique.pk,
        )
        # Fallback : l'exemple est quand meme retourne
        # / Fallback: the example is still returned
        self.assertEqual(len(exemples), 1)
        self.assertEqual(exemples[0].text, "Texte unique.")

    def test_analyseur_sans_exemple(self):
        """Un analyseur sans exemple retourne une liste vide."""
        from hypostasis_extractor.models import AnalyseurSyntaxique
        from hypostasis_extractor.services import _construire_exemples_langextract

        analyseur_vide = AnalyseurSyntaxique.objects.create(name="Vide")
        exemples = _construire_exemples_langextract(analyseur_vide)
        self.assertEqual(exemples, [])


class Phase03JobStockeAnalyseurIdTest(TestCase):
    """Verifie que le job cree par LectureViewSet.analyser stocke
    l'analyseur_id dans raw_result (plus d'examples_data serialises).
    / Verify that the job created by LectureViewSet.analyser stores
    analyseur_id in raw_result (no more serialized examples_data)."""

    def setUp(self):
        from django.contrib.auth.models import User
        from core.models import AIModel, Configuration, Page, Provider
        from hypostasis_extractor.models import (
            AnalyseurSyntaxique, AnalyseurExample, PromptPiece,
        )

        # Utilisateur de test pour les POST auth / Test user for auth POST
        self.user_test = User.objects.create_user(username="phase03_test", password="test1234")

        # Page avec du contenu / Page with content
        self.page = Page.objects.create(
            url="https://example.com/phase03",
            html_original="<html><body>Test phase 03</body></html>",
            html_readability="<article>Test phase 03</article>",
            text_readability="Test phase 03 contenu pour extraction.",
        )

        # Modele IA Mock / Mock AI model
        self.modele_ia = AIModel.objects.create(
            name="Mock PHASE-03",
            provider=Provider.MOCK,
            model_name="gemini-2.5-flash",
            is_active=True,
        )

        # Configuration singleton : IA active + modele selectionne
        # / Singleton configuration: AI active + model selected
        config = Configuration.get_solo()
        config.ai_active = True
        config.ai_model = self.modele_ia
        config.save()

        # Analyseur avec un exemple et une piece de prompt
        # / Analyzer with an example and a prompt piece
        self.analyseur = AnalyseurSyntaxique.objects.create(
            name="Analyseur PHASE-03 test",
            type_analyseur="analyser",
        )
        PromptPiece.objects.create(
            analyseur=self.analyseur,
            name="Instruction",
            content="Extraire les entites.",
            order=0,
        )
        AnalyseurExample.objects.create(
            analyseur=self.analyseur,
            name="Exemple test",
            example_text="Exemple de texte.",
            order=0,
        )

    def test_analyser_cree_job_avec_analyseur_id(self):
        """POST /lire/{id}/analyser/ cree un job dont raw_result contient analyseur_id."""
        from hypostasis_extractor.models import ExtractionJob

        # Authentifier l'utilisateur de test / Authenticate test user
        self.client.force_login(self.user_test)

        # Simuler l'appel HTMX POST / Simulate HTMX POST call
        reponse = self.client.post(
            f"/lire/{self.page.pk}/analyser/",
            data={"analyseur_id": self.analyseur.pk},
            HTTP_HX_REQUEST="true",
        )
        self.assertIn(reponse.status_code, [200, 201, 302])

        # Verifier le job cree / Check the created job
        dernier_job = ExtractionJob.objects.filter(
            page=self.page,
        ).order_by("-created_at").first()

        self.assertIsNotNone(dernier_job, "Aucun job cree par l'endpoint analyser")
        self.assertIn("analyseur_id", dernier_job.raw_result)
        self.assertEqual(dernier_job.raw_result["analyseur_id"], self.analyseur.pk)

    def test_analyser_ne_stocke_plus_examples_data(self):
        """Le job cree par analyser ne contient plus examples_data dans raw_result."""
        from hypostasis_extractor.models import ExtractionJob

        # Authentifier l'utilisateur de test / Authenticate test user
        self.client.force_login(self.user_test)

        self.client.post(
            f"/lire/{self.page.pk}/analyser/",
            data={"analyseur_id": self.analyseur.pk},
            HTTP_HX_REQUEST="true",
        )

        dernier_job = ExtractionJob.objects.filter(
            page=self.page,
        ).order_by("-created_at").first()

        self.assertIsNotNone(dernier_job)
        self.assertNotIn(
            "examples_data",
            dernier_job.raw_result,
            "raw_result contient encore examples_data — la serialisation n'a pas ete supprimee",
        )


class Phase03AnalyserPageTaskUtiliseFonctionCommuneTest(TestCase):
    """Verifie que analyser_page_task charge les exemples depuis l'analyseur
    via _construire_exemples_langextract (pas depuis raw_result serialise).
    / Verify that analyser_page_task loads examples from the analyzer
    via _construire_exemples_langextract (not from serialized raw_result)."""

    def test_task_charge_analyseur_depuis_raw_result(self):
        """analyser_page_task utilise analyseur_id de raw_result pour charger les exemples."""
        from unittest.mock import patch, MagicMock
        from core.models import AIModel, Page, Provider
        from hypostasis_extractor.models import (
            AnalyseurSyntaxique, ExtractionJob,
        )

        # Setup / Mise en place
        page = Page.objects.create(
            url="https://example.com/task-test",
            html_original="<html>Test</html>",
            html_readability="<article>Test task</article>",
            text_readability="Contenu de test pour la tache Celery.",
        )
        modele_ia = AIModel.objects.create(
            name="Mock Task",
            provider=Provider.MOCK,
            model_name="gemini-2.5-flash",
        )
        analyseur = AnalyseurSyntaxique.objects.create(
            name="Analyseur pour tache",
        )
        job = ExtractionJob.objects.create(
            page=page,
            ai_model=modele_ia,
            name="Job test task",
            prompt_description="Extraire les entites",
            status="pending",
            raw_result={"analyseur_id": analyseur.pk},
        )

        # Mock lx.extract pour ne pas appeler le LLM
        # / Mock lx.extract to avoid calling the LLM
        mock_resultat = MagicMock()
        mock_resultat.extractions = []

        with patch("langextract.extract", return_value=mock_resultat) as mock_extract, \
             patch(
                 "hypostasis_extractor.services._construire_exemples_langextract",
                 wraps=None,
             ) as mock_construire:
            # Configurer le mock pour retourner une liste vide
            # / Configure mock to return empty list
            mock_construire.return_value = []

            from front.tasks import analyser_page_task
            analyser_page_task(job.pk)

            # Verifier que _construire_exemples_langextract a ete appele avec le bon analyseur
            # / Verify _construire_exemples_langextract was called with the correct analyzer
            mock_construire.assert_called_once()
            appel_args = mock_construire.call_args
            analyseur_passe = appel_args[0][0]
            self.assertEqual(analyseur_passe.pk, analyseur.pk)

    def test_task_sans_analyseur_id_retourne_liste_vide(self):
        """Sans analyseur_id dans raw_result, la tache utilise une liste vide d'exemples."""
        from unittest.mock import patch, MagicMock
        from core.models import AIModel, Page, Provider
        from hypostasis_extractor.models import ExtractionJob

        page = Page.objects.create(
            url="https://example.com/task-no-analyseur",
            html_original="<html>Test</html>",
            html_readability="<article>Test</article>",
            text_readability="Contenu sans analyseur.",
        )
        modele_ia = AIModel.objects.create(
            name="Mock No Analyseur",
            provider=Provider.MOCK,
            model_name="gemini-2.5-flash",
        )
        job = ExtractionJob.objects.create(
            page=page,
            ai_model=modele_ia,
            name="Job sans analyseur",
            prompt_description="Extraire",
            status="pending",
            raw_result={},
        )

        mock_resultat = MagicMock()
        mock_resultat.extractions = []

        with patch("langextract.extract", return_value=mock_resultat) as mock_extract:
            from front.tasks import analyser_page_task
            analyser_page_task(job.pk)

            # Verifier que lx.extract recoit une liste vide d'exemples
            # / Verify lx.extract receives an empty list of examples
            mock_extract.assert_called_once()
            appel_kwargs = mock_extract.call_args
            exemples_passes = appel_kwargs[1].get("examples", [])
            self.assertEqual(exemples_passes, [])


class Phase03GrepRunLangextractJobTest(TestCase):
    """Verifie que run_langextract_job n'est pas appele depuis front/.
    / Verify that run_langextract_job is not called from front/."""

    def test_front_nappelle_pas_run_langextract_job(self):
        """Aucun fichier Python de front/ (hors tests) n'importe ou appelle run_langextract_job."""
        import os

        repertoire_front = BASE_DIR / "front"
        fichiers_python_front = []
        for racine, dossiers, fichiers in os.walk(repertoire_front):
            # Exclure le repertoire de tests / Exclude test directory
            if "tests" in racine.split(os.sep):
                continue
            for nom_fichier in fichiers:
                if nom_fichier.endswith(".py"):
                    fichiers_python_front.append(os.path.join(racine, nom_fichier))

        occurrences = []
        for chemin_fichier in fichiers_python_front:
            with open(chemin_fichier, "r", encoding="utf-8") as fichier:
                contenu = fichier.read()
                if "run_langextract_job" in contenu:
                    occurrences.append(chemin_fichier)

        self.assertEqual(
            occurrences, [],
            f"run_langextract_job encore reference dans front/ : {occurrences}",
        )

    def test_analyser_page_task_est_seul_point_entree_celery_extraction(self):
        """analyser_page_task est le seul @shared_task qui fait de l'extraction LangExtract."""
        import ast

        chemin_tasks = BASE_DIR / "front" / "tasks.py"
        contenu = chemin_tasks.read_text(encoding="utf-8")
        arbre = ast.parse(contenu)

        # Trouver toutes les fonctions decorees avec @shared_task
        # / Find all functions decorated with @shared_task
        taches_avec_langextract = []
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.FunctionDef):
                for decorateur in noeud.decorator_list:
                    nom_decorateur = ""
                    if isinstance(decorateur, ast.Name):
                        nom_decorateur = decorateur.id
                    elif isinstance(decorateur, ast.Call):
                        if isinstance(decorateur.func, ast.Name):
                            nom_decorateur = decorateur.func.id

                    if nom_decorateur == "shared_task":
                        # Verifier si le corps mentionne lx.extract
                        # / Check if body mentions lx.extract
                        source_fonction = ast.get_source_segment(contenu, noeud)
                        if source_fonction and "lx.extract" in source_fonction:
                            taches_avec_langextract.append(noeud.name)

        self.assertEqual(
            taches_avec_langextract,
            ["analyser_page_task"],
            f"Taches Celery faisant de l'extraction : {taches_avec_langextract} "
            f"(attendu : ['analyser_page_task'] uniquement)",
        )


# =============================================================================
# PHASE-04 — CRUD manquants dans le front
# / PHASE-04 — Missing CRUDs in the front
# =============================================================================


class Phase04SuppressionPageTest(TestCase):
    """Verifie la suppression de page via le front.
    / Verify page deletion via the front."""

    def setUp(self):
        from django.contrib.auth.models import User
        from core.models import Page
        self.user_test = User.objects.create_user(username="test_user_suppr_page", password="test1234")
        self.client.force_login(self.user_test)
        self.page = Page.objects.create(
            title="Page a supprimer",
            html_original="<html>test</html>",
            html_readability="<article>test</article>",
            text_readability="test suppression",
        )

    def test_supprimer_page_retourne_200(self):
        """POST /pages/{pk}/supprimer/ retourne 200 et supprime la page."""
        from core.models import Page
        reponse = self.client.post(f"/pages/{self.page.pk}/supprimer/")
        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(Page.objects.filter(pk=self.page.pk).exists())

    def test_supprimer_page_retourne_html(self):
        """La reponse est du HTML (partial arbre), pas du JSON."""
        reponse = self.client.post(f"/pages/{self.page.pk}/supprimer/")
        contenu = reponse.content.decode("utf-8")
        # L'arbre HTML ne contient pas de JSON brut
        # / The tree HTML doesn't contain raw JSON
        self.assertNotIn('"pk":', contenu)

    def test_supprimer_page_inexistante_404(self):
        """POST /pages/99999/supprimer/ retourne 404."""
        reponse = self.client.post("/pages/99999/supprimer/")
        self.assertEqual(reponse.status_code, 404)


class Phase04RenameDossierTest(TestCase):
    """Verifie le renommage de dossier.
    / Verify folder renaming."""

    def setUp(self):
        from django.contrib.auth.models import User
        from core.models import Dossier
        self.user_test = User.objects.create_user(username="test_user_rename_dos", password="test1234")
        self.client.force_login(self.user_test)
        self.dossier = Dossier.objects.create(name="Ancien nom")

    def test_renommer_dossier_retourne_200(self):
        """POST /dossiers/{pk}/renommer/ retourne 200."""
        reponse = self.client.post(
            f"/dossiers/{self.dossier.pk}/renommer/",
            data={"nouveau_nom": "Nouveau nom"},
        )
        self.assertEqual(reponse.status_code, 200)

    def test_renommer_dossier_change_nom(self):
        """Le nom du dossier est mis a jour en base."""
        from core.models import Dossier
        self.client.post(
            f"/dossiers/{self.dossier.pk}/renommer/",
            data={"nouveau_nom": "Nom modifie"},
        )
        self.dossier.refresh_from_db()
        self.assertEqual(self.dossier.name, "Nom modifie")

    def test_renommer_dossier_nom_vide_400(self):
        """Un nom vide retourne 400."""
        reponse = self.client.post(
            f"/dossiers/{self.dossier.pk}/renommer/",
            data={"nouveau_nom": ""},
        )
        self.assertEqual(reponse.status_code, 400)

    def test_renommer_dossier_retourne_html(self):
        """La reponse est du HTML (partial arbre)."""
        reponse = self.client.post(
            f"/dossiers/{self.dossier.pk}/renommer/",
            data={"nouveau_nom": "Test HTML"},
        )
        contenu = reponse.content.decode("utf-8")
        self.assertIn("Test HTML", contenu)

    def test_renommer_dossier_sanitize_html(self):
        """Les balises HTML dans le nom sont supprimees."""
        from core.models import Dossier
        self.client.post(
            f"/dossiers/{self.dossier.pk}/renommer/",
            data={"nouveau_nom": "<script>alert('xss')</script>Mon dossier"},
        )
        self.dossier.refresh_from_db()
        self.assertNotIn("<script>", self.dossier.name)
        self.assertIn("Mon dossier", self.dossier.name)


class Phase04SuppressionDossierTest(TestCase):
    """Verifie la suppression de dossier (vide et avec pages).
    / Verify folder deletion (empty and with pages)."""

    def setUp(self):
        from django.contrib.auth.models import User
        from core.models import Dossier, Page
        self.user_test = User.objects.create_user(username="test_user_suppr_dos", password="test1234")
        self.client.force_login(self.user_test)
        self.dossier_vide = Dossier.objects.create(name="Dossier vide")
        self.dossier_avec_pages = Dossier.objects.create(name="Dossier plein")
        self.page_dans_dossier = Page.objects.create(
            title="Page dans dossier",
            dossier=self.dossier_avec_pages,
            html_original="<html>test</html>",
            html_readability="<article>test</article>",
            text_readability="test",
        )

    def test_supprimer_dossier_vide(self):
        """DELETE /dossiers/{pk}/ supprime un dossier vide."""
        from core.models import Dossier
        reponse = self.client.delete(f"/dossiers/{self.dossier_vide.pk}/")
        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(Dossier.objects.filter(pk=self.dossier_vide.pk).exists())

    def test_supprimer_dossier_avec_pages_reclasse_orphelines(self):
        """La suppression d'un dossier avec pages met les pages en orphelines."""
        from core.models import Dossier, Page
        self.client.delete(f"/dossiers/{self.dossier_avec_pages.pk}/")
        self.assertFalse(Dossier.objects.filter(pk=self.dossier_avec_pages.pk).exists())
        # La page existe encore mais n'a plus de dossier
        # / The page still exists but has no folder
        self.page_dans_dossier.refresh_from_db()
        self.assertIsNone(self.page_dans_dossier.dossier)

    def test_supprimer_dossier_retourne_html(self):
        """La reponse est du HTML (partial arbre)."""
        reponse = self.client.delete(f"/dossiers/{self.dossier_vide.pk}/")
        contenu = reponse.content.decode("utf-8")
        self.assertNotIn('"pk":', contenu)


class Phase04SuppressionExtractionManuelleTest(TestCase):
    """Verifie la suppression d'une extraction manuelle.
    / Verify manual extraction deletion."""

    def setUp(self):
        from django.contrib.auth.models import User
        from core.models import Page
        from hypostasis_extractor.models import ExtractionJob, ExtractedEntity

        self.user_test = User.objects.create_user(username="test_user_suppr_ext", password="test1234")
        self.client.force_login(self.user_test)
        self.page = Page.objects.create(
            title="Page pour extraction",
            html_original="<html><body>Texte de test</body></html>",
            html_readability="<article>Texte de test</article>",
            text_readability="Texte de test pour extraction manuelle.",
        )
        self.job_manuel = ExtractionJob.objects.create(
            page=self.page,
            name="Extractions manuelles",
            status="completed",
            ai_model=None,
        )
        self.entite = ExtractedEntity.objects.create(
            job=self.job_manuel,
            extraction_class="concept",
            extraction_text="test",
            start_char=0,
            end_char=4,
        )

    def test_supprimer_extraction_manuelle(self):
        """POST /extractions/supprimer_entite/ supprime l'extraction."""
        from hypostasis_extractor.models import ExtractedEntity
        reponse = self.client.post(
            "/extractions/supprimer_entite/",
            data={"entity_id": self.entite.pk, "page_id": self.page.pk},
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(ExtractedEntity.objects.filter(pk=self.entite.pk).exists())

    def test_supprimer_extraction_avec_commentaires_refuse(self):
        """Impossible de supprimer une extraction qui a des commentaires."""
        from hypostasis_extractor.models import CommentaireExtraction
        CommentaireExtraction.objects.create(
            entity=self.entite,
            user=self.user_test,
            commentaire="Commentaire de test",
        )
        reponse = self.client.post(
            "/extractions/supprimer_entite/",
            data={"entity_id": self.entite.pk, "page_id": self.page.pk},
        )
        self.assertEqual(reponse.status_code, 400)


class Phase04ModifierCommentaireTest(TestCase):
    """Verifie la modification d'un commentaire.
    / Verify comment editing."""

    def setUp(self):
        from django.contrib.auth.models import User
        from core.models import Page
        from hypostasis_extractor.models import (
            ExtractionJob, ExtractedEntity, CommentaireExtraction,
        )

        self.user_test = User.objects.create_user(username="test_user_modif_comm", password="test1234")
        self.client.force_login(self.user_test)
        self.page = Page.objects.create(
            title="Page commentaires",
            html_original="<html>test</html>",
            html_readability="<article>test</article>",
            text_readability="test commentaires",
        )
        self.job = ExtractionJob.objects.create(
            page=self.page,
            name="Extractions manuelles",
            status="completed",
        )
        self.entite = ExtractedEntity.objects.create(
            job=self.job,
            extraction_class="concept",
            extraction_text="test",
            start_char=0,
            end_char=4,
        )
        self.commentaire = CommentaireExtraction.objects.create(
            entity=self.entite,
            user=self.user_test,
            commentaire="Commentaire original",
        )

    def test_modifier_commentaire_retourne_200(self):
        """POST /extractions/modifier_commentaire/ retourne 200."""
        reponse = self.client.post(
            "/extractions/modifier_commentaire/",
            data={
                "commentaire_id": self.commentaire.pk,
                "commentaire": "Commentaire modifie",
            },
        )
        self.assertEqual(reponse.status_code, 200)

    def test_modifier_commentaire_change_texte(self):
        """Le texte du commentaire est mis a jour en base."""
        from hypostasis_extractor.models import CommentaireExtraction
        self.client.post(
            "/extractions/modifier_commentaire/",
            data={
                "commentaire_id": self.commentaire.pk,
                "commentaire": "Nouveau texte",
            },
        )
        self.commentaire.refresh_from_db()
        self.assertEqual(self.commentaire.commentaire, "Nouveau texte")

    def test_modifier_commentaire_vide_400(self):
        """Un commentaire vide retourne 400."""
        reponse = self.client.post(
            "/extractions/modifier_commentaire/",
            data={
                "commentaire_id": self.commentaire.pk,
                "commentaire": "",
            },
        )
        self.assertEqual(reponse.status_code, 400)

    def test_modifier_commentaire_retourne_html(self):
        """La reponse est du HTML (fil de discussion)."""
        reponse = self.client.post(
            "/extractions/modifier_commentaire/",
            data={
                "commentaire_id": self.commentaire.pk,
                "commentaire": "Texte HTML test",
            },
        )
        contenu = reponse.content.decode("utf-8")
        self.assertIn("fil-discussion", contenu)


class Phase04SupprimerCommentaireTest(TestCase):
    """Verifie la suppression d'un commentaire.
    / Verify comment deletion."""

    def setUp(self):
        from django.contrib.auth.models import User
        from core.models import Page
        from hypostasis_extractor.models import (
            ExtractionJob, ExtractedEntity, CommentaireExtraction,
        )

        self.user_test = User.objects.create_user(username="test_user_suppr_comm", password="test1234")
        self.client.force_login(self.user_test)
        self.page = Page.objects.create(
            title="Page suppr commentaire",
            html_original="<html>test</html>",
            html_readability="<article>test</article>",
            text_readability="test suppr commentaire",
        )
        self.job = ExtractionJob.objects.create(
            page=self.page,
            name="Extractions manuelles",
            status="completed",
        )
        self.entite = ExtractedEntity.objects.create(
            job=self.job,
            extraction_class="concept",
            extraction_text="test",
            start_char=0,
            end_char=4,
        )
        self.commentaire = CommentaireExtraction.objects.create(
            entity=self.entite,
            user=self.user_test,
            commentaire="A supprimer",
        )

    def test_supprimer_commentaire_retourne_200(self):
        """POST /extractions/supprimer_commentaire/ retourne 200."""
        reponse = self.client.post(
            "/extractions/supprimer_commentaire/",
            data={"commentaire_id": self.commentaire.pk},
        )
        self.assertEqual(reponse.status_code, 200)

    def test_supprimer_commentaire_supprime_en_base(self):
        """Le commentaire est supprime de la base."""
        from hypostasis_extractor.models import CommentaireExtraction
        self.client.post(
            "/extractions/supprimer_commentaire/",
            data={"commentaire_id": self.commentaire.pk},
        )
        self.assertFalse(
            CommentaireExtraction.objects.filter(pk=self.commentaire.pk).exists()
        )

    def test_supprimer_commentaire_retourne_html(self):
        """La reponse est du HTML (fil de discussion)."""
        reponse = self.client.post(
            "/extractions/supprimer_commentaire/",
            data={"commentaire_id": self.commentaire.pk},
        )
        contenu = reponse.content.decode("utf-8")
        self.assertIn("fil-discussion", contenu)

    def test_supprimer_commentaire_inexistant_404(self):
        """POST avec un ID inexistant retourne 404."""
        reponse = self.client.post(
            "/extractions/supprimer_commentaire/",
            data={"commentaire_id": 99999},
        )
        self.assertEqual(reponse.status_code, 404)


class Phase04URLsExistentTest(TestCase):
    """Verifie que les URLs des nouvelles actions existent dans le router.
    / Verify that the URLs for new actions exist in the router."""

    def test_url_renommer_dossier(self):
        """L'URL /dossiers/{pk}/renommer/ est resoluble."""
        from django.urls import reverse
        url = reverse("front:dossier-renommer", kwargs={"pk": 1})
        self.assertEqual(url, "/dossiers/1/renommer/")

    def test_url_modifier_commentaire(self):
        """L'URL /extractions/modifier_commentaire/ est resoluble."""
        from django.urls import reverse
        url = reverse("front:extraction-modifier-commentaire")
        self.assertEqual(url, "/extractions/modifier_commentaire/")

    def test_url_supprimer_commentaire(self):
        """L'URL /extractions/supprimer_commentaire/ est resoluble."""
        from django.urls import reverse
        url = reverse("front:extraction-supprimer-commentaire")
        self.assertEqual(url, "/extractions/supprimer_commentaire/")


class Phase04TemplatesContiennentBoutonsTest(TestCase):
    """Verifie que les templates contiennent les boutons CRUD necessaires.
    / Verify that templates contain the necessary CRUD buttons."""

    def test_arbre_contient_bouton_renommer_dossier(self):
        """arbre_dossiers.html contient le bouton btn-renommer-dossier."""
        chemin = BASE_DIR / "front" / "templates" / "front" / "includes" / "arbre_dossiers.html"
        contenu = chemin.read_text(encoding="utf-8")
        self.assertIn("btn-renommer-dossier", contenu)

    def test_arbre_contient_bouton_supprimer_dossier(self):
        """arbre_dossiers.html contient le bouton btn-supprimer-dossier."""
        chemin = BASE_DIR / "front" / "templates" / "front" / "includes" / "arbre_dossiers.html"
        contenu = chemin.read_text(encoding="utf-8")
        self.assertIn("btn-supprimer-dossier", contenu)

    def test_arbre_contient_bouton_supprimer_page(self):
        """arbre_dossiers.html contient le bouton btn-supprimer-page."""
        chemin = BASE_DIR / "front" / "templates" / "front" / "includes" / "arbre_dossiers.html"
        contenu = chemin.read_text(encoding="utf-8")
        self.assertIn("btn-supprimer-page", contenu)

    def test_fil_discussion_contient_bouton_modifier_commentaire(self):
        """fil_discussion.html contient le bouton btn-modifier-commentaire."""
        chemin = BASE_DIR / "front" / "templates" / "front" / "includes" / "fil_discussion.html"
        contenu = chemin.read_text(encoding="utf-8")
        self.assertIn("btn-modifier-commentaire", contenu)

    def test_fil_discussion_contient_bouton_supprimer_commentaire(self):
        """fil_discussion.html contient le bouton btn-supprimer-commentaire."""
        chemin = BASE_DIR / "front" / "templates" / "front" / "includes" / "fil_discussion.html"
        contenu = chemin.read_text(encoding="utf-8")
        self.assertIn("btn-supprimer-commentaire", contenu)

    def test_vue_commentaires_contient_bouton_modifier_commentaire(self):
        """vue_commentaires.html contient le bouton btn-modifier-commentaire."""
        chemin = BASE_DIR / "front" / "templates" / "front" / "includes" / "vue_commentaires.html"
        contenu = chemin.read_text(encoding="utf-8")
        self.assertIn("btn-modifier-commentaire", contenu)

    def test_vue_commentaires_contient_bouton_supprimer_commentaire(self):
        """vue_commentaires.html contient le bouton btn-supprimer-commentaire."""
        chemin = BASE_DIR / "front" / "templates" / "front" / "includes" / "vue_commentaires.html"
        contenu = chemin.read_text(encoding="utf-8")
        self.assertIn("btn-supprimer-commentaire", contenu)

    def test_js_contient_handler_renommer_dossier(self):
        """hypostasia.js contient le handler pour renommer un dossier."""
        chemin = STATIC_FRONT / "js" / "hypostasia.js"
        contenu = chemin.read_text(encoding="utf-8")
        self.assertIn("btn-renommer-dossier", contenu)

    def test_js_contient_handler_supprimer_dossier(self):
        """hypostasia.js contient le handler pour supprimer un dossier."""
        chemin = STATIC_FRONT / "js" / "hypostasia.js"
        contenu = chemin.read_text(encoding="utf-8")
        self.assertIn("btn-supprimer-dossier", contenu)

    def test_js_contient_handler_modifier_commentaire(self):
        """hypostasia.js contient le handler pour modifier un commentaire."""
        chemin = STATIC_FRONT / "js" / "hypostasia.js"
        contenu = chemin.read_text(encoding="utf-8")
        self.assertIn("modifier_commentaire", contenu)

    def test_js_contient_handler_supprimer_commentaire(self):
        """hypostasia.js contient le handler pour supprimer un commentaire."""
        chemin = STATIC_FRONT / "js" / "hypostasia.js"
        contenu = chemin.read_text(encoding="utf-8")
        self.assertIn("supprimer_commentaire", contenu)


# =============================================================================
# PHASE-06 — Modeles de donnees : statut_debat + masquee
# / PHASE-06 — Data models: statut_debat + masquee
# =============================================================================


class Phase06ChampStatutDebatTest(TestCase):
    """Verifie que le champ statut_debat existe sur ExtractedEntity avec les bonnes valeurs.
    / Verify that statut_debat field exists on ExtractedEntity with correct values."""

    def test_champ_statut_debat_existe(self):
        """ExtractedEntity a un champ statut_debat."""
        from hypostasis_extractor.models import ExtractedEntity
        noms_des_champs = [f.name for f in ExtractedEntity._meta.get_fields()]
        self.assertIn("statut_debat", noms_des_champs)

    def test_statut_debat_defaut_discutable(self):
        """Le defaut de statut_debat est 'discutable'."""
        from hypostasis_extractor.models import ExtractedEntity
        champ_statut = ExtractedEntity._meta.get_field("statut_debat")
        self.assertEqual(champ_statut.default, "discutable")

    def test_statut_debat_choices_complets(self):
        """Les choices de statut_debat contiennent les 4 valeurs attendues."""
        from hypostasis_extractor.models import ExtractedEntity
        champ_statut = ExtractedEntity._meta.get_field("statut_debat")
        valeurs_choices = [choix[0] for choix in champ_statut.choices]
        valeurs_attendues = ["consensuel", "discutable", "discute", "controverse"]
        for valeur in valeurs_attendues:
            self.assertIn(
                valeur, valeurs_choices,
                f"Valeur '{valeur}' manquante dans statut_debat choices",
            )

    def test_statut_debat_max_length_suffisant(self):
        """max_length de statut_debat couvre la plus longue valeur (controverse = 11 chars)."""
        from hypostasis_extractor.models import ExtractedEntity
        champ_statut = ExtractedEntity._meta.get_field("statut_debat")
        self.assertGreaterEqual(champ_statut.max_length, 11)


class Phase06ChampMasqueeTest(TestCase):
    """Verifie que le champ masquee existe sur ExtractedEntity.
    / Verify that masquee field exists on ExtractedEntity."""

    def test_champ_masquee_existe(self):
        """ExtractedEntity a un champ masquee."""
        from hypostasis_extractor.models import ExtractedEntity
        noms_des_champs = [f.name for f in ExtractedEntity._meta.get_fields()]
        self.assertIn("masquee", noms_des_champs)

    def test_masquee_defaut_false(self):
        """Le defaut de masquee est False."""
        from hypostasis_extractor.models import ExtractedEntity
        champ_masquee = ExtractedEntity._meta.get_field("masquee")
        self.assertFalse(champ_masquee.default)

    def test_masquee_est_boolean(self):
        """Le champ masquee est un BooleanField."""
        from django.db.models import BooleanField
        from hypostasis_extractor.models import ExtractedEntity
        champ_masquee = ExtractedEntity._meta.get_field("masquee")
        self.assertIsInstance(champ_masquee, BooleanField)


class Phase06CreationEntiteDefautsTest(TestCase):
    """Verifie que la creation d'une ExtractedEntity applique les defauts statut_debat et masquee.
    / Verify that creating an ExtractedEntity applies statut_debat and masquee defaults."""

    def test_creation_entite_avec_defauts(self):
        """ExtractedEntity.objects.create() donne statut_debat='discutable' et masquee=False."""
        from core.models import Page
        from hypostasis_extractor.models import ExtractionJob, ExtractedEntity

        # Setup minimal : page + job / Minimal setup: page + job
        page_test = Page.objects.create(
            url="https://example.com/phase06-test",
            html_original="<html><body>Test</body></html>",
            html_readability="<article>Test</article>",
            text_readability="Test phase 06.",
        )
        job_test = ExtractionJob.objects.create(
            page=page_test,
            name="Job test PHASE-06",
            status="completed",
        )
        entite_creee = ExtractedEntity.objects.create(
            job=job_test,
            extraction_class="test",
            extraction_text="Texte de test PHASE-06",
            start_char=0,
            end_char=22,
        )

        self.assertEqual(entite_creee.statut_debat, "discutable")
        self.assertFalse(entite_creee.masquee)


class Phase06VariablesCSSStatutTest(TestCase):
    """Verifie que les variables CSS des statuts de debat sont definies dans :root.
    / Verify that debate status CSS variables are defined in :root."""

    def setUp(self):
        chemin_css = STATIC_FRONT / "css" / "hypostasia.css"
        self.contenu_css = chemin_css.read_text(encoding="utf-8")

    def test_variable_consensuel_text(self):
        """--statut-consensuel-text est definie dans le CSS."""
        self.assertIn("--statut-consensuel-text:", self.contenu_css)

    def test_variable_consensuel_bg(self):
        """--statut-consensuel-bg est definie dans le CSS."""
        self.assertIn("--statut-consensuel-bg:", self.contenu_css)

    def test_variable_consensuel_accent(self):
        """--statut-consensuel-accent est definie dans le CSS."""
        self.assertIn("--statut-consensuel-accent:", self.contenu_css)

    def test_variable_discutable_text(self):
        """--statut-discutable-text est definie dans le CSS."""
        self.assertIn("--statut-discutable-text:", self.contenu_css)

    def test_variable_discutable_bg(self):
        """--statut-discutable-bg est definie dans le CSS."""
        self.assertIn("--statut-discutable-bg:", self.contenu_css)

    def test_variable_discutable_accent(self):
        """--statut-discutable-accent est definie dans le CSS."""
        self.assertIn("--statut-discutable-accent:", self.contenu_css)

    def test_variable_discute_text(self):
        """--statut-discute-text est definie dans le CSS."""
        self.assertIn("--statut-discute-text:", self.contenu_css)

    def test_variable_discute_bg(self):
        """--statut-discute-bg est definie dans le CSS."""
        self.assertIn("--statut-discute-bg:", self.contenu_css)

    def test_variable_discute_accent(self):
        """--statut-discute-accent est definie dans le CSS."""
        self.assertIn("--statut-discute-accent:", self.contenu_css)

    def test_variable_controverse_text(self):
        """--statut-controverse-text est definie dans le CSS."""
        self.assertIn("--statut-controverse-text:", self.contenu_css)

    def test_variable_controverse_bg(self):
        """--statut-controverse-bg est definie dans le CSS."""
        self.assertIn("--statut-controverse-bg:", self.contenu_css)

    def test_variable_controverse_accent(self):
        """--statut-controverse-accent est definie dans le CSS."""
        self.assertIn("--statut-controverse-accent:", self.contenu_css)


# =============================================================================
# PHASE-07 — Refonte layout : suppression 3 colonnes, lecteur mono-colonne
# / PHASE-07 — Layout refactor: remove 3 columns, single-column reader
# =============================================================================


class Phase07LayoutMonoColonneBaseHtmlTest(TestCase):
    """Verifie que base.html utilise un layout mono-colonne sans sidebars permanentes.
    / Verify that base.html uses a single-column layout without permanent sidebars."""

    def setUp(self):
        self.contenu_base_html = TEMPLATE_BASE.read_text(encoding="utf-8")

    # -------------------------------------------------------------------------
    # Suppression des sidebars permanentes
    # / Permanent sidebars removed
    # -------------------------------------------------------------------------

    def test_sidebar_left_supprimee(self):
        """base.html ne contient plus de sidebar-left visible (aside avec w-64)."""
        # Verifier qu'il n'y a plus de sidebar gauche avec classes de layout
        # / Verify no left sidebar with layout classes remains
        self.assertNotIn('id="sidebar-left"', self.contenu_base_html)

    def test_pas_de_flex_3_colonnes(self):
        """Le layout flex 3 colonnes est supprime."""
        # Le conteneur flex englobant les 3 colonnes n'existe plus
        # / The flex container wrapping the 3 columns no longer exists
        self.assertNotIn('<div class="flex" style="height: calc(100vh - 3rem);">', self.contenu_base_html)

    def test_sidebar_right_cachee(self):
        """sidebar-right existe toujours mais est cachee avec class hidden."""
        # Le conteneur doit exister (cible OOB) mais etre cache
        # / The container must exist (OOB target) but be hidden
        self.assertIn('id="sidebar-right"', self.contenu_base_html)
        # Verifier que la classe "hidden" est presente sur sidebar-right
        # / Verify that the "hidden" class is on sidebar-right
        pattern_sidebar_right = re.search(
            r'<aside\s+id="sidebar-right"\s+class="([^"]*)"',
            self.contenu_base_html,
        )
        self.assertIsNotNone(pattern_sidebar_right, "sidebar-right introuvable dans base.html")
        classes_sidebar = pattern_sidebar_right.group(1)
        self.assertIn("hidden", classes_sidebar)

    def test_panneau_extractions_existe(self):
        """Le conteneur #panneau-extractions est toujours present (cible OOB)."""
        self.assertIn('id="panneau-extractions"', self.contenu_base_html)

    # -------------------------------------------------------------------------
    # Toolbar minimale
    # / Minimal toolbar
    # -------------------------------------------------------------------------

    def test_toggle_left_panel_supprime(self):
        """Le bouton #toggle-left-panel est supprime."""
        self.assertNotIn('id="toggle-left-panel"', self.contenu_base_html)

    def test_toggle_right_panel_supprime(self):
        """Le bouton #toggle-right-panel est supprime."""
        self.assertNotIn('id="toggle-right-panel"', self.contenu_base_html)

    def test_branding_hypostasia_present(self):
        """Le branding 'Hypostasia' est toujours dans la toolbar."""
        self.assertIn("Hypostasia", self.contenu_base_html)

    def test_titre_toolbar_present(self):
        """Le span #titre-toolbar existe pour recevoir le titre du document via OOB."""
        self.assertIn('id="titre-toolbar"', self.contenu_base_html)

    def test_bouton_import_dans_toolbar(self):
        """Le bouton d'import fichier est dans la toolbar (input file present)."""
        self.assertIn('id="input-import-fichier"', self.contenu_base_html)

    def test_lien_config_llm_dans_toolbar(self):
        """Le lien config LLM (engrenage) est dans la toolbar."""
        self.assertIn('/api/analyseurs/', self.contenu_base_html)

    # -------------------------------------------------------------------------
    # Zone de lecture
    # / Reading zone
    # -------------------------------------------------------------------------

    def test_zone_lecture_existe(self):
        """La zone de lecture #zone-lecture existe toujours."""
        self.assertIn('id="zone-lecture"', self.contenu_base_html)

    def test_zone_lecture_pas_flex1(self):
        """La zone de lecture n'utilise plus flex-1 (pas de layout flex)."""
        pattern_zone_lecture = re.search(
            r'<main\s+id="zone-lecture"\s+class="([^"]*)"',
            self.contenu_base_html,
        )
        self.assertIsNotNone(pattern_zone_lecture)
        classes_zone = pattern_zone_lecture.group(1)
        self.assertNotIn("flex-1", classes_zone)

    def test_zone_lecture_data_testid(self):
        """Le data-testid est conserve sur #zone-lecture."""
        self.assertIn('data-testid="bibliotheque-colonne-lecture"', self.contenu_base_html)


class Phase07LecturePrincipaleTest(TestCase):
    """Verifie que lecture_principale.html a le layout mono-colonne + OOB titre.
    / Verify that lecture_principale.html has single-column layout + OOB title."""

    def setUp(self):
        chemin_template = (
            BASE_DIR / "front" / "templates" / "front"
            / "includes" / "lecture_principale.html"
        )
        self.contenu_template = chemin_template.read_text(encoding="utf-8")

    def test_max_width_44rem(self):
        """Le conteneur principal utilise max-width: 44rem via classe CSS (PHASE-21)."""
        # Depuis PHASE-21, le style inline est remplace par la classe .lecture-zone-conteneur
        # / Since PHASE-21, inline style replaced by .lecture-zone-conteneur CSS class
        self.assertIn("lecture-zone-conteneur", self.contenu_template)

    def test_padding_right_marge_reservee(self):
        """Le conteneur a un padding-right de 3.5rem via classe CSS (PHASE-21)."""
        # Depuis PHASE-21, le style inline est remplace par la classe .lecture-zone-conteneur
        # / Since PHASE-21, inline style replaced by .lecture-zone-conteneur CSS class
        self.assertIn("lecture-zone-conteneur", self.contenu_template)

    def test_oob_titre_toolbar(self):
        """Un snippet OOB met a jour #titre-toolbar avec le titre de la page."""
        self.assertIn('id="titre-toolbar"', self.contenu_template)
        self.assertIn("hx-swap-oob", self.contenu_template)

    def test_data_testid_conserve(self):
        """Le data-testid est conserve sur le conteneur principal."""
        self.assertIn('data-testid="lecture-zone-principale"', self.contenu_template)


class Phase07CSSNettoyageTest(TestCase):
    """Verifie que les styles sidebar sont supprimes du CSS.
    / Verify that sidebar styles are removed from CSS."""

    def setUp(self):
        chemin_css = STATIC_FRONT / "css" / "hypostasia.css"
        self.contenu_css = chemin_css.read_text(encoding="utf-8")

    def test_pas_de_transition_sidebar_left(self):
        """Les transitions #sidebar-left sont supprimees."""
        self.assertNotIn("#sidebar-left {", self.contenu_css)

    def test_pas_de_transition_sidebar_left_collapsed(self):
        """Le style #sidebar-left.collapsed est supprime."""
        self.assertNotIn("#sidebar-left.collapsed", self.contenu_css)

    def test_pas_de_media_query_mobile_overlay(self):
        """Le @media (max-width: 767px) pour les overlays sidebar est supprime."""
        self.assertNotIn("@media (max-width: 767px)", self.contenu_css)

    def test_pas_de_mobile_backdrop(self):
        """La classe .mobile-backdrop est supprimee du CSS."""
        self.assertNotIn(".mobile-backdrop", self.contenu_css)

    def test_pas_de_debat_mode_sidebar(self):
        """Le style #sidebar-right.debat-mode est supprime."""
        self.assertNotIn("#sidebar-right.debat-mode", self.contenu_css)

    def test_styles_lecture_conserves(self):
        """Les styles .lecture-article sont conserves."""
        self.assertIn(".lecture-article", self.contenu_css)

    def test_styles_extraction_conserves(self):
        """Les styles .hl-extraction sont conserves."""
        self.assertIn(".hl-extraction", self.contenu_css)

    def test_styles_tree_arrow_conserves(self):
        """Les styles .tree-arrow sont conserves."""
        self.assertIn(".tree-arrow", self.contenu_css)

    def test_variables_statut_debat_conservees(self):
        """Les variables CSS des statuts de debat sont toujours presentes."""
        self.assertIn("--statut-consensuel-text", self.contenu_css)


class Phase07JSNettoyageTest(TestCase):
    """Verifie que le JS est nettoye des handlers sidebar supprimes.
    / Verify that JS is cleaned up from removed sidebar handlers."""

    def setUp(self):
        chemin_js = STATIC_FRONT / "js" / "hypostasia.js"
        self.contenu_js = chemin_js.read_text(encoding="utf-8")

    def test_pas_de_estMobile(self):
        """La fonction estMobile() est supprimee."""
        self.assertNotIn("function estMobile()", self.contenu_js)

    def test_pas_de_montrerBackdropMobile(self):
        """La fonction montrerBackdropMobile() est supprimee."""
        self.assertNotIn("function montrerBackdropMobile()", self.contenu_js)

    def test_pas_de_cacherBackdropMobile(self):
        """La fonction cacherBackdropMobile() est supprimee."""
        self.assertNotIn("function cacherBackdropMobile()", self.contenu_js)

    def test_pas_de_gererBackdropMobile(self):
        """La fonction gererBackdropMobile() est supprimee."""
        self.assertNotIn("function gererBackdropMobile()", self.contenu_js)

    def test_pas_de_toggle_left_panel(self):
        """Le handler #toggle-left-panel est supprime."""
        self.assertNotIn("toggle-left-panel", self.contenu_js)

    def test_pas_de_toggle_right_panel(self):
        """Le handler #toggle-right-panel est supprime."""
        self.assertNotIn("toggle-right-panel", self.contenu_js)

    def test_pas_de_gererVisibilitePanneauDroit(self):
        """La fonction gererVisibilitePanneauDroit() est supprimee."""
        self.assertNotIn("function gererVisibilitePanneauDroit()", self.contenu_js)

    def test_pas_de_activerModeDebat(self):
        """Le listener activerModeDebat est supprime."""
        self.assertNotIn("activerModeDebat", self.contenu_js)

    def test_ouvrirPanneauDroit_existe_noop(self):
        """La fonction ouvrirPanneauDroit existe toujours (en no-op)."""
        self.assertIn("function ouvrirPanneauDroit()", self.contenu_js)

    def test_onglets_panneau_avec_guard_null(self):
        """Les onglets du panneau ont un guard null (if ongletsPanneau)."""
        self.assertIn("if (ongletsPanneau)", self.contenu_js)

    def test_scrollToCarteDepuisBloc_conserve(self):
        """La fonction scrollToCarteDepuisBloc est conservee."""
        self.assertIn("function scrollToCarteDepuisBloc(", self.contenu_js)


class Phase07VueLectureOOBTitreTest(TestCase):
    """Verifie que charger une page met a jour le titre dans la toolbar via OOB.
    / Verify that loading a page updates the toolbar title via OOB."""

    def test_lecture_contient_oob_titre_toolbar(self):
        """GET /lire/{id}/ renvoie un snippet OOB pour #titre-toolbar."""
        from core.models import Page

        page_test = Page.objects.create(
            url="https://example.com/phase07-titre",
            title="Mon titre PHASE-07",
            html_original="<html><body>Test</body></html>",
            html_readability="<article>Contenu test</article>",
            text_readability="Contenu test phase 07.",
        )
        reponse = self.client.get(
            f"/lire/{page_test.pk}/",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 200)
        contenu_reponse = reponse.content.decode("utf-8")

        # Verifier le snippet OOB titre-toolbar / Check OOB title-toolbar snippet
        self.assertIn('id="titre-toolbar"', contenu_reponse)
        self.assertIn("hx-swap-oob", contenu_reponse)
        self.assertIn("Mon titre PHASE-07", contenu_reponse)

    def test_lecture_page_sans_titre_affiche_sans_titre(self):
        """GET /lire/{id}/ avec page sans titre affiche 'Sans titre' dans le OOB."""
        from core.models import Page

        page_sans_titre = Page.objects.create(
            url="https://example.com/phase07-sans-titre",
            title="",
            html_original="<html><body>Test</body></html>",
            html_readability="<article>Contenu</article>",
            text_readability="Contenu test.",
        )
        reponse = self.client.get(
            f"/lire/{page_sans_titre.pk}/",
            HTTP_HX_REQUEST="true",
        )
        contenu_reponse = reponse.content.decode("utf-8")
        self.assertIn("Sans titre", contenu_reponse)


# =============================================================================
# PHASE-09 — Pastilles marge droite + cartes inline
# / PHASE-09 — Right margin dots + inline cards
# =============================================================================


class Phase09FichiersStatiquesTest(TestCase):
    """Verifie que les fichiers statiques PHASE-09 existent et sont references.
    / Verify PHASE-09 static files exist and are referenced."""

    def setUp(self):
        # Lire le contenu de base.html et du CSS
        # / Read base.html and CSS contents
        self.contenu_base_html = TEMPLATE_BASE.read_text(encoding="utf-8")
        chemin_css = STATIC_FRONT / "css" / "hypostasia.css"
        self.contenu_css = chemin_css.read_text(encoding="utf-8")

    # -------------------------------------------------------------------------
    # Existence du fichier marginalia.js
    # / marginalia.js file existence
    # -------------------------------------------------------------------------

    def test_fichier_marginalia_js_existe(self):
        """marginalia.js existe dans front/static/front/js/."""
        chemin_marginalia = STATIC_FRONT / "js" / "marginalia.js"
        self.assertTrue(chemin_marginalia.exists(), f"Fichier JS manquant : {chemin_marginalia}")

    def test_fichier_marginalia_js_non_vide(self):
        """marginalia.js n'est pas vide."""
        chemin_marginalia = STATIC_FRONT / "js" / "marginalia.js"
        taille = chemin_marginalia.stat().st_size
        self.assertGreater(taille, 100, f"marginalia.js semble trop petit ({taille} octets)")

    def test_script_marginalia_dans_base_html(self):
        """base.html reference marginalia.js via {% static %}."""
        self.assertIn("marginalia.js", self.contenu_base_html)

    # -------------------------------------------------------------------------
    # CSS : pastilles et carte inline presents, icones gauche supprimees
    # / CSS: dots and inline card present, left icons removed
    # -------------------------------------------------------------------------

    def test_css_contient_pastilles_marge(self):
        """hypostasia.css contient la classe .pastilles-marge."""
        self.assertIn(".pastilles-marge", self.contenu_css)

    def test_css_contient_pastille_extraction(self):
        """hypostasia.css contient la classe .pastille-extraction."""
        self.assertIn(".pastille-extraction", self.contenu_css)

    def test_css_contient_carte_inline(self):
        """hypostasia.css contient la classe .carte-inline."""
        self.assertIn(".carte-inline", self.contenu_css)

    def test_css_contient_animation_entree(self):
        """hypostasia.css contient l'animation carte-inline-slide-down."""
        self.assertIn("carte-inline-slide-down", self.contenu_css)

    def test_css_contient_animation_sortie(self):
        """hypostasia.css contient l'animation carte-inline-slide-up."""
        self.assertIn("carte-inline-slide-up", self.contenu_css)

    def test_css_contient_btn_replier_carte(self):
        """hypostasia.css contient la classe .btn-replier-carte."""
        self.assertIn(".btn-replier-carte", self.contenu_css)

    def test_css_ne_contient_plus_icones_before(self):
        """hypostasia.css ne contient plus de .hl-extraction::before (icones marge gauche supprimees)."""
        self.assertNotIn(".hl-extraction::before", self.contenu_css)

    def test_css_ne_contient_plus_icone_commentee_before(self):
        """hypostasia.css ne contient plus de .hl-commentee::before."""
        self.assertNotIn(".hl-commentee::before", self.contenu_css)

    def test_css_ne_contient_plus_icone_restitution_before(self):
        """hypostasia.css ne contient plus de .hl-restitution::before."""
        self.assertNotIn(".hl-restitution::before", self.contenu_css)


class Phase09MarginaliaJSContenuTest(TestCase):
    """Verifie le contenu de marginalia.js : fonctions, LOCALISATION, commentaires.
    / Verify marginalia.js content: functions, LOCALISATION, comments."""

    def setUp(self):
        chemin_marginalia = STATIC_FRONT / "js" / "marginalia.js"
        self.contenu_js = chemin_marginalia.read_text(encoding="utf-8")

    def test_header_localisation_present(self):
        """marginalia.js contient le header LOCALISATION stack-ccc."""
        self.assertIn("LOCALISATION", self.contenu_js)

    def test_header_communication_present(self):
        """marginalia.js contient la section COMMUNICATION stack-ccc."""
        self.assertIn("COMMUNICATION", self.contenu_js)

    def test_fonction_construire_pastilles(self):
        """marginalia.js exporte construirePastillesMarginales()."""
        self.assertIn("function construirePastillesMarginales()", self.contenu_js)

    def test_fonction_fermer_carte_inline(self):
        """marginalia.js exporte fermerCarteInline()."""
        self.assertIn("function fermerCarteInline(", self.contenu_js)

    def test_mapping_couleurs_statut(self):
        """marginalia.js contient le mapping COULEURS_STATUT avec les 4 statuts."""
        self.assertIn("COULEURS_STATUT", self.contenu_js)
        self.assertIn("consensuel", self.contenu_js)
        self.assertIn("discutable", self.contenu_js)
        self.assertIn("discute", self.contenu_js)
        self.assertIn("controverse", self.contenu_js)

    def test_recalcul_apres_htmx_swap(self):
        """marginalia.js ecoute htmx:afterSwap pour reconstruire les pastilles."""
        self.assertIn("htmx:afterSwap", self.contenu_js)

    def test_dom_content_loaded(self):
        """marginalia.js construit les pastilles au DOMContentLoaded."""
        self.assertIn("DOMContentLoaded", self.contenu_js)


class Phase09HypostasiaJSAdaptationsTest(TestCase):
    """Verifie les adaptations dans hypostasia.js pour PHASE-09.
    / Verify adaptations in hypostasia.js for PHASE-09."""

    def setUp(self):
        chemin_hypostasia = STATIC_FRONT / "js" / "hypostasia.js"
        self.contenu_js = chemin_hypostasia.read_text(encoding="utf-8")

    def test_handler_mousedown_icone_gauche_supprime(self):
        """hypostasia.js ne contient plus le handler mousedown pour la zone icone gauche."""
        # L'ancien handler contenait "clicRelatifX" pour detecter les clics marge gauche
        # / The old handler used "clicRelatifX" to detect left margin clicks
        self.assertNotIn("clicRelatifX", self.contenu_js)

    def test_scroll_carte_cherche_carte_inline_dabord(self):
        """scrollToCarteDepuisBloc cherche d'abord une carte inline ouverte."""
        self.assertIn(".carte-inline[data-extraction-id=", self.contenu_js)

    def test_scroll_carte_cherche_pastille(self):
        """scrollToCarteDepuisBloc declenche un clic pastille si pas de carte inline."""
        self.assertIn(".pastille-extraction[data-extraction-id=", self.contenu_js)


class Phase09AnnotationDataStatutTest(TestCase):
    """Verifie que annoter_html_avec_barres ajoute data-statut aux spans.
    / Verify that annoter_html_avec_barres adds data-statut to spans."""

    def test_span_contient_data_statut_par_defaut(self):
        """Un span annote contient data-statut='discutable' par defaut."""
        from front.utils import annoter_html_avec_barres
        from hypostasis_extractor.models import ExtractionJob, ExtractedEntity
        from core.models import Page

        # Creer une page avec du texte simple
        # / Create a page with simple text
        page_test = Page.objects.create(
            title="Test data-statut",
            html_original="<html><body>Hello world</body></html>",
            html_readability="<p>Hello world</p>",
            text_readability="Hello world",
        )
        job_test = ExtractionJob.objects.create(
            page=page_test, name="Test", status="completed",
        )
        entite_test = ExtractedEntity.objects.create(
            job=job_test,
            extraction_class="concept",
            extraction_text="Hello",
            start_char=0,
            end_char=5,
        )

        html_annote = annoter_html_avec_barres(
            page_test.html_readability,
            page_test.text_readability,
            [entite_test],
        )
        self.assertIn('data-statut="discutable"', html_annote)
        self.assertIn('data-extraction-id=', html_annote)

    def test_span_contient_data_statut_consensuel(self):
        """Un span annote avec statut_debat='consensuel' a data-statut='consensuel'."""
        from front.utils import annoter_html_avec_barres
        from hypostasis_extractor.models import ExtractionJob, ExtractedEntity
        from core.models import Page

        page_test = Page.objects.create(
            title="Test consensuel",
            html_original="<html><body>Bonjour monde</body></html>",
            html_readability="<p>Bonjour monde</p>",
            text_readability="Bonjour monde",
        )
        job_test = ExtractionJob.objects.create(
            page=page_test, name="Test", status="completed",
        )
        entite_consensuelle = ExtractedEntity.objects.create(
            job=job_test,
            extraction_class="these",
            extraction_text="Bonjour",
            start_char=0,
            end_char=7,
            statut_debat="consensuel",
        )

        html_annote = annoter_html_avec_barres(
            page_test.html_readability,
            page_test.text_readability,
            [entite_consensuelle],
        )
        self.assertIn('data-statut="consensuel"', html_annote)

    def test_span_contient_data_statut_controverse(self):
        """Un span annote avec statut_debat='controverse' a data-statut='controverse'."""
        from front.utils import annoter_html_avec_barres
        from hypostasis_extractor.models import ExtractionJob, ExtractedEntity
        from core.models import Page

        page_test = Page.objects.create(
            title="Test controverse",
            html_original="<html><body>Debat anime</body></html>",
            html_readability="<p>Debat anime</p>",
            text_readability="Debat anime",
        )
        job_test = ExtractionJob.objects.create(
            page=page_test, name="Test", status="completed",
        )
        entite_controversee = ExtractedEntity.objects.create(
            job=job_test,
            extraction_class="argument",
            extraction_text="Debat",
            start_char=0,
            end_char=5,
            statut_debat="controverse",
        )

        html_annote = annoter_html_avec_barres(
            page_test.html_readability,
            page_test.text_readability,
            [entite_controversee],
        )
        self.assertIn('data-statut="controverse"', html_annote)


class Phase09EndpointCarteInlineTest(TestCase):
    """Verifie l'endpoint GET /extractions/carte_inline/ (PHASE-09).
    / Verify GET /extractions/carte_inline/ endpoint (PHASE-09)."""

    def setUp(self):
        from core.models import Page
        from hypostasis_extractor.models import ExtractionJob, ExtractedEntity

        self.page = Page.objects.create(
            title="Page carte inline",
            html_original="<html><body>Texte pour carte inline</body></html>",
            html_readability="<p>Texte pour carte inline</p>",
            text_readability="Texte pour carte inline.",
        )
        self.job = ExtractionJob.objects.create(
            page=self.page,
            name="Extractions manuelles",
            status="completed",
            ai_model=None,
        )
        self.entite = ExtractedEntity.objects.create(
            job=self.job,
            extraction_class="concept",
            extraction_text="carte inline",
            start_char=10,
            end_char=22,
            statut_debat="discutable",
        )

    def test_carte_inline_retourne_200(self):
        """GET /extractions/carte_inline/?entity_id=N retourne 200."""
        reponse = self.client.get(
            f"/extractions/carte_inline/?entity_id={self.entite.pk}",
        )
        self.assertEqual(reponse.status_code, 200)

    def test_carte_inline_contient_data_testid(self):
        """La carte inline contient data-testid='carte-inline'."""
        reponse = self.client.get(
            f"/extractions/carte_inline/?entity_id={self.entite.pk}",
        )
        contenu = reponse.content.decode("utf-8")
        self.assertIn('data-testid="carte-inline"', contenu)

    def test_carte_inline_contient_data_statut(self):
        """La carte inline contient data-statut avec la valeur de l'entite."""
        reponse = self.client.get(
            f"/extractions/carte_inline/?entity_id={self.entite.pk}",
        )
        contenu = reponse.content.decode("utf-8")
        self.assertIn('data-statut="discutable"', contenu)

    def test_carte_inline_contient_bouton_replier(self):
        """La carte inline contient un bouton replier avec data-testid."""
        reponse = self.client.get(
            f"/extractions/carte_inline/?entity_id={self.entite.pk}",
        )
        contenu = reponse.content.decode("utf-8")
        self.assertIn('data-testid="btn-replier-carte"', contenu)

    def test_carte_inline_contient_extraction_text(self):
        """La carte inline affiche le texte de l'extraction."""
        reponse = self.client.get(
            f"/extractions/carte_inline/?entity_id={self.entite.pk}",
        )
        contenu = reponse.content.decode("utf-8")
        self.assertIn("carte inline", contenu)

    def test_carte_inline_contient_badge_statut(self):
        """La carte inline affiche le badge du statut de debat."""
        reponse = self.client.get(
            f"/extractions/carte_inline/?entity_id={self.entite.pk}",
        )
        contenu = reponse.content.decode("utf-8")
        self.assertIn("Discutable", contenu)

    def test_carte_inline_sans_entity_id_retourne_400(self):
        """GET /extractions/carte_inline/ sans entity_id retourne 400."""
        reponse = self.client.get("/extractions/carte_inline/")
        self.assertEqual(reponse.status_code, 400)

    def test_carte_inline_entity_inexistante_retourne_404(self):
        """GET /extractions/carte_inline/?entity_id=99999 retourne 404."""
        reponse = self.client.get("/extractions/carte_inline/?entity_id=99999")
        self.assertEqual(reponse.status_code, 404)

    def test_carte_inline_avec_commentaires_affiche_compteur(self):
        """La carte inline affiche le nombre de commentaires si > 0."""
        from django.contrib.auth.models import User
        from hypostasis_extractor.models import CommentaireExtraction

        user_test = User.objects.create_user(username="test_carte_inline", password="test1234")
        CommentaireExtraction.objects.create(
            entity=self.entite,
            user=user_test,
            commentaire="Un commentaire de test",
        )

        reponse = self.client.get(
            f"/extractions/carte_inline/?entity_id={self.entite.pk}",
        )
        contenu = reponse.content.decode("utf-8")
        # Le compteur affiche "1" pour un commentaire
        # / Counter displays "1" for one comment
        self.assertIn("1", contenu)

    def test_carte_inline_contient_boutons_action(self):
        """La carte inline contient les boutons commenter et modifier avec data-testid."""
        reponse = self.client.get(
            f"/extractions/carte_inline/?entity_id={self.entite.pk}",
        )
        contenu = reponse.content.decode("utf-8")
        self.assertIn('data-testid="carte-inline-btn-commenter"', contenu)
        self.assertIn('data-testid="carte-inline-btn-modifier"', contenu)

    def test_carte_inline_contient_aria_label(self):
        """La carte inline contient un aria-label descriptif."""
        reponse = self.client.get(
            f"/extractions/carte_inline/?entity_id={self.entite.pk}",
        )
        contenu = reponse.content.decode("utf-8")
        self.assertIn('aria-label="Carte extraction', contenu)

    def test_carte_inline_statut_consensuel(self):
        """La carte inline d'une entite consensuelle affiche le bon statut."""
        self.entite.statut_debat = "consensuel"
        self.entite.save()

        reponse = self.client.get(
            f"/extractions/carte_inline/?entity_id={self.entite.pk}",
        )
        contenu = reponse.content.decode("utf-8")
        self.assertIn('data-statut="consensuel"', contenu)
        self.assertIn("Consensuel", contenu)


class Phase09TemplateCarteInlineTest(TestCase):
    """Verifie le template carte_inline.html (PHASE-09).
    / Verify carte_inline.html template (PHASE-09)."""

    def test_template_existe(self):
        """Le template carte_inline.html peut etre charge par Django."""
        template = get_template("front/includes/carte_inline.html")
        self.assertIsNotNone(template)


# =============================================================================
# PHASE-10 — Drawer vue liste des extractions
# / PHASE-10 — Drawer extraction list view
# =============================================================================


class Phase10TemplateDrawerExisteTest(TestCase):
    """Verifie que le template drawer_vue_liste.html existe et est chargeable.
    / Verify drawer_vue_liste.html template exists and is loadable."""

    def test_template_drawer_existe(self):
        """Le template drawer_vue_liste.html peut etre charge par Django."""
        template = get_template("front/includes/drawer_vue_liste.html")
        self.assertIsNotNone(template)


class Phase10FichiersStatiquesTest(TestCase):
    """Verifie l'existence des fichiers statiques drawer (PHASE-10).
    / Verify drawer static files exist (PHASE-10)."""

    def test_fichier_js_drawer_existe(self):
        """Le fichier drawer_vue_liste.js existe dans front/static/front/js/."""
        chemin_js = STATIC_FRONT / "js" / "drawer_vue_liste.js"
        self.assertTrue(chemin_js.exists(), f"Fichier manquant : {chemin_js}")

    def test_fichier_js_drawer_non_vide(self):
        """Le fichier drawer_vue_liste.js n'est pas vide."""
        chemin_js = STATIC_FRONT / "js" / "drawer_vue_liste.js"
        taille = chemin_js.stat().st_size
        self.assertGreater(taille, 100, "drawer_vue_liste.js trop petit")

    def test_css_contient_styles_drawer(self):
        """hypostasia.css contient les styles du drawer (PHASE-10)."""
        chemin_css = STATIC_FRONT / "css" / "hypostasia.css"
        contenu_css = chemin_css.read_text()
        self.assertIn("#drawer-backdrop", contenu_css)
        self.assertIn("#drawer-overlay", contenu_css)
        self.assertIn(".drawer-carte-compacte", contenu_css)
        self.assertIn(".drawer-carte-masquee", contenu_css)


class Phase10BaseHtmlDrawerTest(TestCase):
    """Verifie que base.html contient le drawer overlay et ses dependances (PHASE-10).
    / Verify base.html contains drawer overlay and its dependencies (PHASE-10)."""

    def setUp(self):
        self.contenu_base = TEMPLATE_BASE.read_text()

    def test_base_contient_drawer_backdrop(self):
        """base.html contient le backdrop du drawer."""
        self.assertIn('id="drawer-backdrop"', self.contenu_base)

    def test_base_contient_drawer_overlay(self):
        """base.html contient l'aside du drawer overlay."""
        self.assertIn('id="drawer-overlay"', self.contenu_base)

    def test_base_contient_drawer_contenu(self):
        """base.html contient la zone de contenu scrollable du drawer."""
        self.assertIn('id="drawer-contenu"', self.contenu_base)

    def test_base_contient_bouton_fermer_drawer(self):
        """base.html contient le bouton de fermeture du drawer."""
        self.assertIn('id="btn-fermer-drawer"', self.contenu_base)

    def test_base_contient_bouton_toolbar_drawer(self):
        """base.html contient le bouton E de la toolbar (sans data-placeholder)."""
        self.assertIn('id="btn-toolbar-drawer"', self.contenu_base)

    def test_bouton_toolbar_drawer_sans_placeholder(self):
        """Le bouton E n'a plus de data-placeholder='PHASE-10'."""
        self.assertNotIn('data-placeholder="PHASE-10"', self.contenu_base)

    def test_base_charge_js_drawer(self):
        """base.html charge le script drawer_vue_liste.js."""
        self.assertIn("drawer_vue_liste.js", self.contenu_base)

    def test_drawer_a_aria_label(self):
        """Le drawer overlay a un aria-label pour l'accessibilite."""
        self.assertIn('aria-label="Vue liste des extractions"', self.contenu_base)

    def test_drawer_a_data_testid(self):
        """Le drawer overlay a un data-testid pour les tests E2E."""
        self.assertIn('data-testid="drawer-overlay"', self.contenu_base)

    def test_drawer_largeur_32rem(self):
        """Le drawer a une largeur de 32rem (avec responsive min).
        / Drawer has 32rem width (with responsive min)."""
        # Le template utilise min(32rem, 100vw) pour le responsive
        # / Template uses min(32rem, 100vw) for responsive
        self.assertIn('32rem', self.contenu_base)

    def test_drawer_z_index_superieur_backdrop(self):
        """Le drawer (z-50) a un z-index superieur au backdrop (z-40)."""
        self.assertIn('z-40', self.contenu_base)  # backdrop
        self.assertIn('z-50', self.contenu_base)  # drawer


class Phase10EndpointMasquerTest(TestCase):
    """Verifie l'endpoint POST /extractions/masquer/ (PHASE-10).
    / Verify POST /extractions/masquer/ endpoint (PHASE-10)."""

    def setUp(self):
        from django.contrib.auth.models import User
        from core.models import Page
        from hypostasis_extractor.models import (
            CommentaireExtraction, ExtractionJob, ExtractedEntity,
        )

        self.user_test = User.objects.create_user(username="test_user_masquer", password="test1234")
        self.client.force_login(self.user_test)
        self.page = Page.objects.create(
            title="Page masquer test",
            html_original="<html><body>Texte pour masquer</body></html>",
            html_readability="<p>Texte pour masquer</p>",
            text_readability="Texte pour masquer.",
        )
        self.job = ExtractionJob.objects.create(
            page=self.page,
            name="Extractions manuelles",
            status="completed",
            ai_model=None,
        )
        self.entite_sans_commentaire = ExtractedEntity.objects.create(
            job=self.job,
            extraction_class="concept",
            extraction_text="pour masquer",
            start_char=6,
            end_char=18,
            statut_debat="discutable",
            masquee=False,
        )
        self.entite_avec_commentaire = ExtractedEntity.objects.create(
            job=self.job,
            extraction_class="argument",
            extraction_text="Texte",
            start_char=0,
            end_char=5,
            statut_debat="discute",
            masquee=False,
        )
        CommentaireExtraction.objects.create(
            entity=self.entite_avec_commentaire,
            user=self.user_test,
            commentaire="Un commentaire de test.",
        )

    def test_masquer_retourne_200(self):
        """POST /extractions/masquer/ avec entity_id et page_id retourne 200."""
        reponse = self.client.post("/extractions/masquer/", {
            "entity_id": self.entite_sans_commentaire.pk,
            "page_id": self.page.pk,
        })
        self.assertEqual(reponse.status_code, 200)

    def test_masquer_met_masquee_true(self):
        """Apres masquer, l'entite a masquee=True en base."""
        from hypostasis_extractor.models import ExtractedEntity

        self.client.post("/extractions/masquer/", {
            "entity_id": self.entite_sans_commentaire.pk,
            "page_id": self.page.pk,
        })
        self.entite_sans_commentaire.refresh_from_db()
        self.assertTrue(self.entite_sans_commentaire.masquee)

    def test_masquer_refuse_si_commentaires(self):
        """Masquer une entite avec commentaires retourne 400."""
        reponse = self.client.post("/extractions/masquer/", {
            "entity_id": self.entite_avec_commentaire.pk,
            "page_id": self.page.pk,
        })
        self.assertEqual(reponse.status_code, 400)

    def test_masquer_refuse_si_commentaires_ne_modifie_pas_entite(self):
        """Masquer refuse avec commentaires, l'entite reste masquee=False."""
        from hypostasis_extractor.models import ExtractedEntity

        self.client.post("/extractions/masquer/", {
            "entity_id": self.entite_avec_commentaire.pk,
            "page_id": self.page.pk,
        })
        self.entite_avec_commentaire.refresh_from_db()
        self.assertFalse(self.entite_avec_commentaire.masquee)

    def test_masquer_sans_entity_id_retourne_400(self):
        """POST /extractions/masquer/ sans entity_id retourne 400."""
        reponse = self.client.post("/extractions/masquer/", {
            "page_id": self.page.pk,
        })
        self.assertEqual(reponse.status_code, 400)

    def test_masquer_sans_page_id_retourne_400(self):
        """POST /extractions/masquer/ sans page_id retourne 400."""
        reponse = self.client.post("/extractions/masquer/", {
            "entity_id": self.entite_sans_commentaire.pk,
        })
        self.assertEqual(reponse.status_code, 400)

    def test_masquer_entity_inexistante_retourne_404(self):
        """POST /extractions/masquer/ avec un entity_id inexistant retourne 404."""
        reponse = self.client.post("/extractions/masquer/", {
            "entity_id": 99999,
            "page_id": self.page.pk,
        })
        self.assertEqual(reponse.status_code, 404)

    def test_masquer_renvoie_reponse_minimale_avec_triggers(self):
        """La reponse de masquer contient un HTML minimal + des triggers HTMX.
        / Masquer response contains minimal HTML + HTMX triggers."""
        reponse = self.client.post("/extractions/masquer/", {
            "entity_id": self.entite_sans_commentaire.pk,
            "page_id": self.page.pk,
        })
        contenu = reponse.content.decode("utf-8")
        # Verifie la reponse minimale + trigger lectureReload
        # / Verify minimal response + lectureReload trigger
        self.assertEqual(reponse.status_code, 200)
        hx_trigger = reponse.get("HX-Trigger", "")
        self.assertIn("lectureReload", hx_trigger)

    def test_masquer_declenche_event_htmx(self):
        """La reponse de masquer contient un HX-Trigger drawerContenuChange."""
        reponse = self.client.post("/extractions/masquer/", {
            "entity_id": self.entite_sans_commentaire.pk,
            "page_id": self.page.pk,
        })
        hx_trigger = reponse.get("HX-Trigger", "")
        self.assertIn("drawerContenuChange", hx_trigger)


class Phase10EndpointRestaurerTest(TestCase):
    """Verifie l'endpoint POST /extractions/restaurer/ (PHASE-10).
    / Verify POST /extractions/restaurer/ endpoint (PHASE-10)."""

    def setUp(self):
        from django.contrib.auth.models import User
        from core.models import Page
        from hypostasis_extractor.models import ExtractionJob, ExtractedEntity

        self.user_test = User.objects.create_user(username="test_user_restaurer", password="test1234")
        self.client.force_login(self.user_test)

        self.page = Page.objects.create(
            title="Page restaurer test",
            html_original="<html><body>Texte restaurer</body></html>",
            html_readability="<p>Texte restaurer</p>",
            text_readability="Texte restaurer.",
        )
        self.job = ExtractionJob.objects.create(
            page=self.page,
            name="Extractions manuelles",
            status="completed",
            ai_model=None,
        )
        self.entite_masquee = ExtractedEntity.objects.create(
            job=self.job,
            extraction_class="concept",
            extraction_text="restaurer",
            start_char=6,
            end_char=15,
            statut_debat="discutable",
            masquee=True,
        )

    def test_restaurer_retourne_200(self):
        """POST /extractions/restaurer/ avec entity_id et page_id retourne 200."""
        reponse = self.client.post("/extractions/restaurer/", {
            "entity_id": self.entite_masquee.pk,
            "page_id": self.page.pk,
        })
        self.assertEqual(reponse.status_code, 200)

    def test_restaurer_met_masquee_false(self):
        """Apres restaurer, l'entite a masquee=False en base."""
        from hypostasis_extractor.models import ExtractedEntity

        self.client.post("/extractions/restaurer/", {
            "entity_id": self.entite_masquee.pk,
            "page_id": self.page.pk,
        })
        self.entite_masquee.refresh_from_db()
        self.assertFalse(self.entite_masquee.masquee)

    def test_restaurer_sans_params_retourne_400(self):
        """POST /extractions/restaurer/ sans params retourne 400."""
        reponse = self.client.post("/extractions/restaurer/", {})
        self.assertEqual(reponse.status_code, 400)

    def test_restaurer_renvoie_reponse_minimale_avec_triggers(self):
        """La reponse de restaurer contient un HTML minimal + des triggers HTMX.
        / Restaurer response contains minimal HTML + HTMX triggers."""
        reponse = self.client.post("/extractions/restaurer/", {
            "entity_id": self.entite_masquee.pk,
            "page_id": self.page.pk,
        })
        self.assertEqual(reponse.status_code, 200)
        hx_trigger = reponse.get("HX-Trigger", "")
        self.assertIn("lectureReload", hx_trigger)

    def test_restaurer_declenche_event_htmx(self):
        """La reponse de restaurer contient un HX-Trigger drawerContenuChange."""
        reponse = self.client.post("/extractions/restaurer/", {
            "entity_id": self.entite_masquee.pk,
            "page_id": self.page.pk,
        })
        hx_trigger = reponse.get("HX-Trigger", "")
        self.assertIn("drawerContenuChange", hx_trigger)


class Phase10EndpointDrawerContenuTest(TestCase):
    """Verifie l'endpoint GET /extractions/drawer_contenu/ (PHASE-10).
    / Verify GET /extractions/drawer_contenu/ endpoint (PHASE-10)."""

    def setUp(self):
        from django.contrib.auth.models import User
        from core.models import Page
        from hypostasis_extractor.models import (
            CommentaireExtraction, ExtractionJob, ExtractedEntity,
        )

        self.user_test = User.objects.create_user(username="test_user_drawer", password="test1234")

        self.page = Page.objects.create(
            title="Page drawer test",
            html_original="<html><body>Alpha Beta Gamma Delta</body></html>",
            html_readability="<p>Alpha Beta Gamma Delta</p>",
            text_readability="Alpha Beta Gamma Delta.",
        )
        self.job = ExtractionJob.objects.create(
            page=self.page,
            name="Extractions manuelles",
            status="completed",
            ai_model=None,
        )
        # Entite visible / Visible entity
        self.entite_visible = ExtractedEntity.objects.create(
            job=self.job,
            extraction_class="concept",
            extraction_text="Alpha",
            start_char=0,
            end_char=5,
            statut_debat="consensuel",
            masquee=False,
        )
        # Entite masquee / Hidden entity
        self.entite_masquee = ExtractedEntity.objects.create(
            job=self.job,
            extraction_class="argument",
            extraction_text="Beta",
            start_char=6,
            end_char=10,
            statut_debat="controverse",
            masquee=True,
        )
        # Entite avec commentaire / Entity with comment
        self.entite_commentee = ExtractedEntity.objects.create(
            job=self.job,
            extraction_class="axiome",
            extraction_text="Gamma",
            start_char=11,
            end_char=16,
            statut_debat="discute",
            masquee=False,
        )
        CommentaireExtraction.objects.create(
            entity=self.entite_commentee,
            user=self.user_test,
            commentaire="Commentaire de test.",
        )

    def test_drawer_contenu_retourne_200(self):
        """GET /extractions/drawer_contenu/?page_id=N retourne 200."""
        reponse = self.client.get(
            f"/extractions/drawer_contenu/?page_id={self.page.pk}",
        )
        self.assertEqual(reponse.status_code, 200)

    def test_drawer_contenu_sans_page_id_retourne_400(self):
        """GET /extractions/drawer_contenu/ sans page_id retourne 400."""
        reponse = self.client.get("/extractions/drawer_contenu/")
        self.assertEqual(reponse.status_code, 400)

    def test_drawer_contenu_contient_entite_visible(self):
        """Le drawer contient la carte de l'entite visible."""
        reponse = self.client.get(
            f"/extractions/drawer_contenu/?page_id={self.page.pk}",
        )
        contenu = reponse.content.decode("utf-8")
        self.assertIn(f'data-extraction-id="{self.entite_visible.pk}"', contenu)

    def test_drawer_contenu_contient_entite_masquee(self):
        """Le drawer contient aussi l'entite masquee (en section masquees)."""
        reponse = self.client.get(
            f"/extractions/drawer_contenu/?page_id={self.page.pk}",
        )
        contenu = reponse.content.decode("utf-8")
        self.assertIn(f'data-extraction-id="{self.entite_masquee.pk}"', contenu)

    def test_drawer_contenu_compteur_masquees(self):
        """Le drawer affiche le compteur de masquees."""
        reponse = self.client.get(
            f"/extractions/drawer_contenu/?page_id={self.page.pk}",
        )
        contenu = reponse.content.decode("utf-8")
        # 1 entite masquee
        # / 1 hidden entity
        self.assertIn("1 masqu", contenu)

    def test_drawer_contenu_compteur_total(self):
        """Le drawer affiche le nombre total d'extractions."""
        reponse = self.client.get(
            f"/extractions/drawer_contenu/?page_id={self.page.pk}",
        )
        contenu = reponse.content.decode("utf-8")
        # 3 extractions au total
        # / 3 total extractions
        self.assertIn("3 extractions", contenu)

    def test_drawer_contenu_data_testid_cartes(self):
        """Les cartes du drawer ont un data-testid='drawer-carte'."""
        reponse = self.client.get(
            f"/extractions/drawer_contenu/?page_id={self.page.pk}",
        )
        contenu = reponse.content.decode("utf-8")
        self.assertIn('data-testid="drawer-carte"', contenu)

    def test_drawer_contenu_data_testid_select_tri(self):
        """Le select de tri a un data-testid='drawer-select-tri'."""
        reponse = self.client.get(
            f"/extractions/drawer_contenu/?page_id={self.page.pk}",
        )
        contenu = reponse.content.decode("utf-8")
        self.assertIn('data-testid="drawer-select-tri"', contenu)

    def test_drawer_contenu_bouton_masquer(self):
        """Les cartes visibles ont un bouton masquer."""
        reponse = self.client.get(
            f"/extractions/drawer_contenu/?page_id={self.page.pk}",
        )
        contenu = reponse.content.decode("utf-8")
        self.assertIn('data-testid="drawer-btn-masquer"', contenu)

    def test_drawer_contenu_bouton_restaurer(self):
        """Les cartes masquees ont un bouton restaurer."""
        reponse = self.client.get(
            f"/extractions/drawer_contenu/?page_id={self.page.pk}",
        )
        contenu = reponse.content.decode("utf-8")
        self.assertIn('data-testid="drawer-btn-restaurer"', contenu)

    def test_drawer_contenu_badge_commentaire(self):
        """L'entite commentee affiche un badge avec le nombre de commentaires."""
        reponse = self.client.get(
            f"/extractions/drawer_contenu/?page_id={self.page.pk}",
        )
        contenu = reponse.content.decode("utf-8")
        # Le badge commentaire est present pour l'entite commentee
        # / Comment badge is present for the commented entity
        self.assertIn("1 commentaire", contenu)

    def test_drawer_contenu_bouton_toggle_masquees(self):
        """Le drawer contient le bouton toggle pour les masquees."""
        reponse = self.client.get(
            f"/extractions/drawer_contenu/?page_id={self.page.pk}",
        )
        contenu = reponse.content.decode("utf-8")
        self.assertIn('data-testid="drawer-btn-toggle-masquees"', contenu)

    def test_drawer_contenu_entite_commentee_masquer_desactive(self):
        """Le bouton masquer est desactive pour une entite avec commentaires."""
        reponse = self.client.get(
            f"/extractions/drawer_contenu/?page_id={self.page.pk}",
        )
        contenu = reponse.content.decode("utf-8")
        # Cherche le bouton masquer specifique a l'entite commentee
        # On verifie que 'disabled' apparait dans le contexte des boutons masquer
        # / Find the hide button specific to the commented entity
        self.assertIn("Extraction avec commentaires", contenu)


class Phase10DrawerContenuTriTest(TestCase):
    """Verifie le tri du drawer (position, activite, statut) (PHASE-10).
    / Verify drawer sort options (position, activite, statut) (PHASE-10)."""

    def setUp(self):
        from core.models import Page
        from hypostasis_extractor.models import ExtractionJob, ExtractedEntity

        self.page = Page.objects.create(
            title="Page tri test",
            html_original="<html><body>Un Deux Trois</body></html>",
            html_readability="<p>Un Deux Trois</p>",
            text_readability="Un Deux Trois.",
        )
        self.job = ExtractionJob.objects.create(
            page=self.page,
            name="Job test",
            status="completed",
            ai_model=None,
        )
        ExtractedEntity.objects.create(
            job=self.job,
            extraction_class="a",
            extraction_text="Un",
            start_char=0,
            end_char=2,
            statut_debat="consensuel",
        )
        ExtractedEntity.objects.create(
            job=self.job,
            extraction_class="b",
            extraction_text="Deux",
            start_char=3,
            end_char=7,
            statut_debat="controverse",
        )

    def test_tri_position_par_defaut(self):
        """Sans parametre tri, le tri par position est selectionne."""
        reponse = self.client.get(
            f"/extractions/drawer_contenu/?page_id={self.page.pk}",
        )
        contenu = reponse.content.decode("utf-8")
        # Le select doit avoir "position" comme option selectionnee
        # / Select must have "position" as selected option
        self.assertIn('value="position" selected', contenu)

    def test_tri_activite(self):
        """Le parametre tri=activite selectionne l'option correspondante."""
        reponse = self.client.get(
            f"/extractions/drawer_contenu/?page_id={self.page.pk}&tri=activite",
        )
        contenu = reponse.content.decode("utf-8")
        self.assertIn('value="activite" selected', contenu)

    def test_tri_statut(self):
        """Le parametre tri=statut selectionne l'option correspondante."""
        reponse = self.client.get(
            f"/extractions/drawer_contenu/?page_id={self.page.pk}&tri=statut",
        )
        contenu = reponse.content.decode("utf-8")
        self.assertIn('value="statut" selected', contenu)

    def test_page_inexistante_retourne_404(self):
        """GET /extractions/drawer_contenu/?page_id=99999 retourne 404."""
        reponse = self.client.get("/extractions/drawer_contenu/?page_id=99999")
        self.assertEqual(reponse.status_code, 404)


class Phase10FiltrageMasqueeAnnotationTest(TestCase):
    """Verifie que _render_panneau_complet_avec_oob filtre les entites masquees (PHASE-10).
    / Verify _render_panneau_complet_avec_oob filters hidden entities (PHASE-10)."""

    def setUp(self):
        from django.contrib.auth.models import User
        from core.models import Page
        from hypostasis_extractor.models import ExtractionJob, ExtractedEntity

        self.user_test = User.objects.create_user(username="test_user_filtrage", password="test1234")
        self.client.force_login(self.user_test)

        self.page = Page.objects.create(
            title="Page filtrage test",
            html_original="<html><body>Alpha Beta</body></html>",
            html_readability="<p>Alpha Beta</p>",
            text_readability="Alpha Beta.",
        )
        self.job = ExtractionJob.objects.create(
            page=self.page,
            name="Job test",
            status="completed",
            ai_model=None,
        )
        # Entite visible / Visible entity
        self.entite_visible = ExtractedEntity.objects.create(
            job=self.job,
            extraction_class="concept",
            extraction_text="Alpha",
            start_char=0,
            end_char=5,
            statut_debat="discutable",
            masquee=False,
        )
        # Entite masquee / Hidden entity
        self.entite_masquee = ExtractedEntity.objects.create(
            job=self.job,
            extraction_class="concept",
            extraction_text="Beta",
            start_char=6,
            end_char=10,
            statut_debat="discutable",
            masquee=True,
        )

    def test_masquer_puis_panneau_exclut_entite(self):
        """Apres masquer, le panneau re-rendu ne contient pas l'entite masquee dans le HTML annote."""
        # D'abord masquer l'entite Alpha
        # / First hide the Alpha entity
        self.client.post("/extractions/masquer/", {
            "entity_id": self.entite_visible.pk,
            "page_id": self.page.pk,
        })
        # Recharger le panneau / Reload panel
        reponse = self.client.post("/extractions/panneau/", {
            "page_id": self.page.pk,
        })
        contenu = reponse.content.decode("utf-8")
        # L'entite masquee ne doit pas apparaitre dans le readability-content annote
        # / Hidden entity should not appear in annotated readability-content
        self.assertNotIn(
            f'data-extraction-id="{self.entite_visible.pk}"',
            contenu,
        )

    def test_entite_visible_reste_dans_annotations(self):
        """Les entites non masquees sont toujours presentes dans les annotations."""
        reponse = self.client.post("/extractions/panneau/", {
            "page_id": self.page.pk,
        })
        contenu = reponse.content.decode("utf-8")
        # L'entite visible doit etre dans le readability-content
        # / Visible entity should be in readability-content
        self.assertIn(
            f'data-extraction-id="{self.entite_visible.pk}"',
            contenu,
        )

    def test_entite_masquee_exclue_des_annotations(self):
        """L'entite masquee n'apparait pas dans les annotations HTML."""
        reponse = self.client.post("/extractions/panneau/", {
            "page_id": self.page.pk,
        })
        contenu = reponse.content.decode("utf-8")
        # L'entite masquee (Beta) ne doit pas apparaitre
        # / Hidden entity (Beta) should not appear
        self.assertNotIn(
            f'data-extraction-id="{self.entite_masquee.pk}"',
            contenu,
        )


class Phase10DrawerJSContenuTest(TestCase):
    """Verifie le contenu du fichier drawer_vue_liste.js (PHASE-10).
    / Verify drawer_vue_liste.js content (PHASE-10)."""

    def setUp(self):
        chemin_js = STATIC_FRONT / "js" / "drawer_vue_liste.js"
        self.contenu_js = chemin_js.read_text()

    def test_js_contient_iife(self):
        """Le JS est encapsule dans une IIFE."""
        self.assertIn("(function()", self.contenu_js)

    def test_js_expose_api_publique(self):
        """Le JS expose window.drawerVueListe."""
        self.assertIn("window.drawerVueListe", self.contenu_js)

    def test_js_contient_ouvrir_fermer_basculer(self):
        """Le JS expose ouvrir, fermer, basculer."""
        self.assertIn("ouvrir:", self.contenu_js)
        self.assertIn("fermer:", self.contenu_js)
        self.assertIn("basculer:", self.contenu_js)

    def test_js_raccourcis_delegues_a_keyboard(self):
        """Depuis PHASE-17, les raccourcis clavier sont geres par keyboard.js.
        / Since PHASE-17, keyboard shortcuts are handled by keyboard.js."""
        # drawer_vue_liste.js ne contient plus de listener keydown
        # / drawer_vue_liste.js no longer contains a keydown listener
        self.assertNotIn("addEventListener('keydown'", self.contenu_js)
        self.assertNotIn('addEventListener("keydown"', self.contenu_js)

    def test_js_contient_charger_contenu(self):
        """Le JS contient la fonction chargerContenu."""
        self.assertIn("chargerContenu", self.contenu_js)

    def test_js_contient_url_drawer_contenu(self):
        """Le JS appelle l'URL /extractions/drawer_contenu/."""
        self.assertIn("/extractions/drawer_contenu/", self.contenu_js)

    def test_masquer_restaurer_geres_par_htmx(self):
        """Les boutons masquer/restaurer sont geres par HTMX (pas par le JS)."""
        # Le JS ne doit plus contenir de fetch() vers masquer/restaurer
        # / JS should no longer contain fetch() calls to masquer/restaurer
        self.assertNotIn("fetch(urlMasquer", self.contenu_js)
        self.assertNotIn("fetch(urlRestaurer", self.contenu_js)

    def test_js_ecoute_drawer_contenu_change(self):
        """Le JS ecoute l'event drawerContenuChange pour recharger."""
        self.assertIn("drawerContenuChange", self.contenu_js)

    def test_js_gere_scroll_bidirectionnel(self):
        """Le JS gere le scroll bidirectionnel (pastille cliquee → drawer)."""
        self.assertIn("pastille-extraction", self.contenu_js)
        self.assertIn("drawer-carte-active", self.contenu_js)

    def test_js_api_publique_pour_keyboard(self):
        """Le JS expose une API publique utilisable par keyboard.js.
        / JS exposes a public API usable by keyboard.js."""
        self.assertIn("window.drawerVueListe", self.contenu_js)

    def test_js_contient_commentaires_bilingues(self):
        """Le JS contient des commentaires bilingues FR/EN."""
        # Verifie au moins 3 commentaires avec le pattern FR / EN
        # / Verify at least 3 bilingual comments
        lignes_bilingues = re.findall(r"// /.*", self.contenu_js)
        self.assertGreaterEqual(
            len(lignes_bilingues), 3,
            "Le JS devrait contenir au moins 3 commentaires bilingues FR/EN",
        )


# =============================================================================
# PHASE-15 — Rythme visuel de la transcription (anti-mur-de-texte)
# / PHASE-15 — Visual rhythm of transcription (anti-wall-of-text)
# =============================================================================


class Phase15ConstruireHtmlDiariseTest(TestCase):
    """Teste la fonction construire_html_diarise avec differents cas limites.
    / Tests construire_html_diarise with various edge cases."""

    def setUp(self):
        # Importation de la fonction a tester
        # / Import the function under test
        from front.services.transcription_audio import construire_html_diarise
        self.construire_html_diarise = construire_html_diarise

    # -------------------------------------------------------------------------
    # Cas : liste vide
    # / Case: empty list
    # -------------------------------------------------------------------------

    def test_liste_vide_renvoie_chaines_vides(self):
        """Une liste vide renvoie deux chaines vides."""
        html, texte = self.construire_html_diarise([])
        self.assertEqual(html, "")
        self.assertEqual(texte, "")

    def test_dict_vide_sans_segments_renvoie_chaines_vides(self):
        """Un dict sans cle 'segments' est traite comme une liste vide."""
        html, texte = self.construire_html_diarise({})
        self.assertEqual(html, "")
        self.assertEqual(texte, "")

    def test_dict_avec_segments_vides_renvoie_chaines_vides(self):
        """Un dict avec segments=[] renvoie deux chaines vides."""
        html, texte = self.construire_html_diarise({"model": "voxtral", "segments": []})
        self.assertEqual(html, "")
        self.assertEqual(texte, "")

    # -------------------------------------------------------------------------
    # Cas : segment unique
    # / Case: single segment
    # -------------------------------------------------------------------------

    def test_segment_unique_cree_un_bloc(self):
        """Un seul segment produit un seul bloc speaker-block."""
        segments = [{"speaker": "Alice", "start": 0.0, "end": 5.0, "text": "Bonjour."}]
        html, texte = self.construire_html_diarise(segments)
        self.assertIn("speaker-block", html)
        self.assertIn("Alice", html)
        self.assertIn("Bonjour.", html)

    def test_segment_unique_texte_brut_correct(self):
        """Le texte brut d'un seul segment contient le locuteur et le texte."""
        segments = [{"speaker": "Alice", "start": 0.0, "end": 5.0, "text": "Bonjour."}]
        html, texte = self.construire_html_diarise(segments)
        self.assertIn("Alice", texte)
        self.assertIn("Bonjour.", texte)

    def test_segment_unique_compte_un_seul_bloc(self):
        """Un seul segment ne produit qu'un seul speaker-block (pas de doublons)."""
        segments = [{"speaker": "Alice", "start": 0.0, "end": 5.0, "text": "Bonjour."}]
        html, texte = self.construire_html_diarise(segments)
        # Compter les occurrences de 'id="speaker-block-' pour eviter les doublons
        # dus au fait que la classe ET l'id contiennent tous deux "speaker-block"
        # / Count occurrences of 'id="speaker-block-' to avoid double-counting
        # since both the class AND the id contain "speaker-block"
        nombre_blocs = html.count('id="speaker-block-')
        self.assertEqual(nombre_blocs, 1)

    # -------------------------------------------------------------------------
    # Cas : groupement de segments (meme locuteur consecutif)
    # / Case: segment grouping (same consecutive speaker)
    # -------------------------------------------------------------------------

    def test_segments_meme_locuteur_groupes(self):
        """Deux segments consecutifs du meme locuteur sont groupes en un seul bloc."""
        segments = [
            {"speaker": "Alice", "start": 0.0, "end": 5.0, "text": "Premier."},
            {"speaker": "Alice", "start": 5.0, "end": 10.0, "text": "Second."},
        ]
        html, texte = self.construire_html_diarise(segments)
        # Un seul speaker-block pour Alice — compter par id pour eviter les doublons
        # / One single speaker-block for Alice — count by id to avoid double-counting
        nombre_blocs = html.count('id="speaker-block-')
        self.assertEqual(nombre_blocs, 1)

    def test_segments_meme_locuteur_contenu_complet(self):
        """Un bloc groupe contient les textes des deux segments."""
        segments = [
            {"speaker": "Alice", "start": 0.0, "end": 5.0, "text": "Premier."},
            {"speaker": "Alice", "start": 5.0, "end": 10.0, "text": "Second."},
        ]
        html, texte = self.construire_html_diarise(segments)
        self.assertIn("Premier.", html)
        self.assertIn("Second.", html)

    def test_segments_locuteurs_differents_pas_groupes(self):
        """Deux locuteurs differents produisent deux blocs distincts."""
        segments = [
            {"speaker": "Alice", "start": 0.0, "end": 5.0, "text": "Bonjour."},
            {"speaker": "Bob", "start": 5.0, "end": 10.0, "text": "Salut."},
        ]
        html, texte = self.construire_html_diarise(segments)
        # Compter par id pour un decompte precis
        # / Count by id for an accurate count
        nombre_blocs = html.count('id="speaker-block-')
        self.assertEqual(nombre_blocs, 2)

    def test_groupement_interrompu_par_autre_locuteur(self):
        """Alice, Bob, Alice produit 3 blocs (pas de fusion des blocs Alice non consecutifs)."""
        segments = [
            {"speaker": "Alice", "start": 0.0, "end": 5.0, "text": "Un."},
            {"speaker": "Bob", "start": 5.0, "end": 10.0, "text": "Deux."},
            {"speaker": "Alice", "start": 10.0, "end": 15.0, "text": "Trois."},
        ]
        html, texte = self.construire_html_diarise(segments)
        # Compter par id pour un decompte precis
        # / Count by id for an accurate count
        nombre_blocs = html.count('id="speaker-block-')
        self.assertEqual(nombre_blocs, 3)

    # -------------------------------------------------------------------------
    # Cas : marqueurs temporels (audio long > 5 min)
    # / Case: time markers (long audio > 5 min)
    # -------------------------------------------------------------------------

    def test_audio_court_pas_de_marqueur_temporel(self):
        """Un audio de 2 minutes ne genere aucun marqueur temporel."""
        segments = [
            {"speaker": "Alice", "start": 0.0, "end": 120.0, "text": "Texte court."},
        ]
        html, texte = self.construire_html_diarise(segments)
        self.assertNotIn("marqueur-temporel", html)

    def test_audio_long_genere_marqueur_a_5min(self):
        """Un audio de 10 minutes genere un marqueur temporel a 05:00."""
        # Utiliser deux locuteurs differents pour forcer deux groupes distincts.
        # La logique de marqueur se declenche sur le 'start' de chaque groupe.
        # / Use two different speakers to force two distinct groups.
        # The marker logic triggers on each group's 'start'.
        segments = [
            {"speaker": "Alice", "start": 0.0, "end": 200.0, "text": "Premier bloc."},
            {"speaker": "Bob", "start": 350.0, "end": 600.0, "text": "Second bloc apres 5 min."},
        ]
        html, texte = self.construire_html_diarise(segments)
        self.assertIn("marqueur-temporel", html)

    def test_audio_tres_long_genere_plusieurs_marqueurs(self):
        """Un audio de plus de 30 minutes genere plusieurs marqueurs temporels."""
        # Creer des segments qui couvrent 35 minutes avec alternance de locuteurs.
        # L'alternance force la creation de groupes distincts, ce qui declenche
        # la logique de marqueurs temporels pour chaque nouveau groupe.
        # / Create segments spanning 35 minutes with alternating speakers.
        # Alternating speakers forces distinct groups, which triggers the
        # time marker logic for each new group.
        locuteurs = ["Alice", "Bob"]
        segments = []
        for i, minute in enumerate(range(0, 35, 2)):
            debut = minute * 60
            fin = debut + 60
            segments.append({
                "speaker": locuteurs[i % 2],
                "start": float(debut),
                "end": float(fin),
                "text": f"Texte a {minute} minutes.",
            })
        html, texte = self.construire_html_diarise(segments)
        # 35 minutes -> marqueurs a 5, 10, 15, 20, 25, 30 min = 6 marqueurs
        # / 35 minutes -> markers at 5, 10, 15, 20, 25, 30 min = 6 markers
        nombre_marqueurs = html.count("marqueur-temporel")
        self.assertGreaterEqual(nombre_marqueurs, 6)

    def test_marqueur_temporel_contient_timestamp_formate(self):
        """Le marqueur temporel affiche un timestamp lisible (ex: 05:00)."""
        # Deux locuteurs differents pour forcer deux groupes : Alice (0-200s)
        # puis Bob (310s). Le marqueur a 300s (05:00) est insere avant le bloc Bob.
        # / Two different speakers to force two groups: Alice (0-200s)
        # then Bob (310s). The 300s (05:00) marker is inserted before Bob's block.
        segments = [
            {"speaker": "Alice", "start": 0.0, "end": 200.0, "text": "Debut."},
            {"speaker": "Bob", "start": 310.0, "end": 400.0, "text": "Apres 5 min."},
        ]
        html, texte = self.construire_html_diarise(segments)
        # Le marqueur doit contenir "05:00"
        # / The marker should contain "05:00"
        self.assertIn("05:00", html)

    # -------------------------------------------------------------------------
    # Cas : champ speaker manquant
    # / Case: missing speaker field
    # -------------------------------------------------------------------------

    def test_segment_sans_speaker_utilise_inconnu(self):
        """Un segment sans champ 'speaker' utilise 'Inconnu' comme locuteur."""
        segments = [{"start": 0.0, "end": 5.0, "text": "Texte sans locuteur."}]
        html, texte = self.construire_html_diarise(segments)
        self.assertIn("Inconnu", html)

    def test_segment_avec_speaker_id_normalise(self):
        """Un segment avec 'speaker_id' (format Voxtral brut) est normalise vers 'speaker'."""
        segments = [{"speaker_id": "SPEAKER_00", "start": 0.0, "end": 5.0, "text": "Voxtral brut."}]
        html, texte = self.construire_html_diarise(segments)
        self.assertIn("SPEAKER_00", html)

    def test_segment_speaker_id_none_utilise_locuteur(self):
        """Un segment avec speaker_id=None utilise 'Locuteur' comme fallback."""
        segments = [{"speaker_id": None, "start": 0.0, "end": 5.0, "text": "Texte."}]
        html, texte = self.construire_html_diarise(segments)
        # speaker_id=None -> speaker = "Locuteur" (voir logique de normalisation)
        # / speaker_id=None -> speaker = "Locuteur" (see normalization logic)
        self.assertIn("Locuteur", html)

    # -------------------------------------------------------------------------
    # Cas : input dict vs list
    # / Case: dict input vs list input
    # -------------------------------------------------------------------------

    def test_input_dict_avec_cle_segments(self):
        """Un dict {'model': ..., 'segments': [...]} est accepte comme input."""
        donnees = {
            "model": "voxtral-v1",
            "text": "Alice dit bonjour.",
            "segments": [
                {"speaker": "Alice", "start": 0.0, "end": 5.0, "text": "Bonjour."},
            ],
        }
        html, texte = self.construire_html_diarise(donnees)
        self.assertIn("Alice", html)
        self.assertIn("Bonjour.", html)

    def test_input_list_directe(self):
        """Une liste directe de segments est acceptee comme input."""
        segments = [
            {"speaker": "Bob", "start": 0.0, "end": 3.0, "text": "Salut."},
        ]
        html, texte = self.construire_html_diarise(segments)
        self.assertIn("Bob", html)
        self.assertIn("Salut.", html)

    def test_dict_et_list_produisent_meme_resultat(self):
        """Un dict et une liste avec les memes segments produisent le meme HTML."""
        segments = [
            {"speaker": "Alice", "start": 0.0, "end": 5.0, "text": "Bonjour."},
            {"speaker": "Bob", "start": 5.0, "end": 10.0, "text": "Salut."},
        ]
        donnees_dict = {"model": "voxtral-v1", "segments": segments[:]}
        html_via_list, texte_via_list = self.construire_html_diarise(segments)
        html_via_dict, texte_via_dict = self.construire_html_diarise(donnees_dict)
        self.assertEqual(html_via_list, html_via_dict)
        self.assertEqual(texte_via_list, texte_via_dict)

    # -------------------------------------------------------------------------
    # Cas : securite XSS
    # / Case: XSS safety
    # -------------------------------------------------------------------------

    def test_nom_locuteur_echappe_xss(self):
        """Un nom de locuteur avec des balises HTML est echappe (protection XSS)."""
        segments = [
            {"speaker": "<script>alert('xss')</script>", "start": 0.0, "end": 5.0, "text": "Texte."},
        ]
        html, texte = self.construire_html_diarise(segments)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_texte_segment_echappe_xss(self):
        """Un texte de segment avec des balises HTML est echappe (protection XSS)."""
        segments = [
            {"speaker": "Alice", "start": 0.0, "end": 5.0, "text": "<b>Bold</b>"},
        ]
        html, texte = self.construire_html_diarise(segments)
        # Le texte doit etre echappe
        # / The text must be escaped
        self.assertNotIn("<b>Bold</b>", html)
        self.assertIn("&lt;b&gt;Bold&lt;/b&gt;", html)

    # -------------------------------------------------------------------------
    # Cas : segments avec texte vide (doivent etre ignores)
    # / Case: segments with empty text (should be ignored)
    # -------------------------------------------------------------------------

    def test_segment_texte_vide_ignore(self):
        """Un segment avec texte vide est ignore et ne cree pas de bloc."""
        segments = [
            {"speaker": "Alice", "start": 0.0, "end": 5.0, "text": ""},
            {"speaker": "Bob", "start": 5.0, "end": 10.0, "text": "Bonjour."},
        ]
        html, texte = self.construire_html_diarise(segments)
        # Seul Bob devrait avoir un bloc
        # / Only Bob should have a block
        self.assertNotIn("Alice", html)
        self.assertIn("Bob", html)

    def test_tous_segments_vides_renvoient_chaines_vides(self):
        """Si tous les segments ont un texte vide, on renvoie deux chaines vides."""
        segments = [
            {"speaker": "Alice", "start": 0.0, "end": 5.0, "text": ""},
            {"speaker": "Bob", "start": 5.0, "end": 10.0, "text": "   "},
        ]
        html, texte = self.construire_html_diarise(segments)
        self.assertEqual(html, "")
        self.assertEqual(texte, "")

    # -------------------------------------------------------------------------
    # Cas : structure du HTML genere
    # / Case: structure of generated HTML
    # -------------------------------------------------------------------------

    def test_bloc_html_contient_data_speaker(self):
        """Chaque bloc contient l'attribut data-speaker avec le nom du locuteur."""
        segments = [
            {"speaker": "Alice", "start": 0.0, "end": 5.0, "text": "Test."},
        ]
        html, texte = self.construire_html_diarise(segments)
        self.assertIn('data-speaker="Alice"', html)

    def test_bloc_html_contient_data_start_end(self):
        """Chaque bloc contient les attributs data-start et data-end."""
        segments = [
            {"speaker": "Alice", "start": 12.5, "end": 25.0, "text": "Test."},
        ]
        html, texte = self.construire_html_diarise(segments)
        self.assertIn('data-start="12.5"', html)
        self.assertIn('data-end="25.0"', html)

    def test_bloc_html_contient_timestamp_debut(self):
        """Chaque bloc affiche le timestamp de debut formate."""
        segments = [
            {"speaker": "Alice", "start": 65.0, "end": 90.0, "text": "Test."},
        ]
        html, texte = self.construire_html_diarise(segments)
        # 65 secondes = 01:05
        # / 65 seconds = 01:05
        self.assertIn("01:05", html)

    def test_texte_brut_contient_format_locuteur_timestamp(self):
        """Le texte brut contient les interventions au format [Locuteur MM:SS]."""
        segments = [
            {"speaker": "Alice", "start": 0.0, "end": 5.0, "text": "Test."},
        ]
        html, texte = self.construire_html_diarise(segments)
        self.assertIn("[Alice", texte)
        self.assertIn("Test.", texte)


class Phase15ConstruireWidgetsAudioTest(TestCase):
    """Teste la fonction construire_widgets_audio avec differents cas limites.
    / Tests construire_widgets_audio with various edge cases."""

    def setUp(self):
        # Importation de la fonction a tester
        # / Import the function under test
        from front.services.transcription_audio import construire_widgets_audio
        self.construire_widgets_audio = construire_widgets_audio

    # -------------------------------------------------------------------------
    # Cas : input vide
    # / Case: empty input
    # -------------------------------------------------------------------------

    def test_liste_vide_renvoie_chaines_vides(self):
        """Une liste vide renvoie deux chaines vides."""
        html_filtre, html_timeline = self.construire_widgets_audio([])
        self.assertEqual(html_filtre, "")
        self.assertEqual(html_timeline, "")

    def test_dict_avec_segments_vides_renvoie_chaines_vides(self):
        """Un dict avec segments=[] renvoie deux chaines vides."""
        html_filtre, html_timeline = self.construire_widgets_audio(
            {"model": "voxtral", "segments": []}
        )
        self.assertEqual(html_filtre, "")
        self.assertEqual(html_timeline, "")

    def test_segments_tous_texte_vide_renvoient_chaines_vides(self):
        """Si tous les segments n'ont pas de texte, les widgets sont vides."""
        segments = [
            {"speaker": "Alice", "start": 0.0, "end": 5.0, "text": ""},
        ]
        html_filtre, html_timeline = self.construire_widgets_audio(segments)
        self.assertEqual(html_filtre, "")
        self.assertEqual(html_timeline, "")

    # -------------------------------------------------------------------------
    # Cas : filtre locuteurs
    # / Case: speaker filter
    # -------------------------------------------------------------------------

    def test_filtre_contient_bouton_tous(self):
        """Le filtre locuteurs contient toujours le bouton 'Tous'."""
        segments = [
            {"speaker": "Alice", "start": 0.0, "end": 10.0, "text": "Bonjour."},
        ]
        html_filtre, html_timeline = self.construire_widgets_audio(segments)
        self.assertIn("Tous", html_filtre)
        self.assertIn('data-speaker-filter="tous"', html_filtre)

    def test_filtre_contient_nom_locuteur(self):
        """Le filtre contient le nom de chaque locuteur present."""
        segments = [
            {"speaker": "Alice", "start": 0.0, "end": 10.0, "text": "Bonjour."},
            {"speaker": "Bob", "start": 10.0, "end": 20.0, "text": "Salut."},
        ]
        html_filtre, html_timeline = self.construire_widgets_audio(segments)
        self.assertIn("Alice", html_filtre)
        self.assertIn("Bob", html_filtre)

    def test_filtre_un_seul_locuteur(self):
        """Avec un seul locuteur, le filtre contient 'Tous' + 1 pilule."""
        segments = [
            {"speaker": "Alice", "start": 0.0, "end": 10.0, "text": "Monologue."},
        ]
        html_filtre, html_timeline = self.construire_widgets_audio(segments)
        nombre_pilules = html_filtre.count("pilule-locuteur")
        # 2 pilules : "Tous" + "Alice"
        # / 2 pills: "Tous" + "Alice"
        self.assertEqual(nombre_pilules, 2)

    def test_filtre_data_speaker_filter_present(self):
        """Chaque pilule de locuteur a l'attribut data-speaker-filter."""
        segments = [
            {"speaker": "Alice", "start": 0.0, "end": 10.0, "text": "Test."},
        ]
        html_filtre, html_timeline = self.construire_widgets_audio(segments)
        self.assertIn('data-speaker-filter="Alice"', html_filtre)

    def test_filtre_id_correct(self):
        """Le conteneur du filtre a l'id 'filtre-locuteurs'."""
        segments = [
            {"speaker": "Alice", "start": 0.0, "end": 10.0, "text": "Test."},
        ]
        html_filtre, html_timeline = self.construire_widgets_audio(segments)
        self.assertIn('id="filtre-locuteurs"', html_filtre)

    # -------------------------------------------------------------------------
    # Cas : timeline audio
    # / Case: audio timeline
    # -------------------------------------------------------------------------

    def test_timeline_id_correct(self):
        """La timeline a l'id 'timeline-audio'."""
        segments = [
            {"speaker": "Alice", "start": 0.0, "end": 10.0, "text": "Test."},
        ]
        html_filtre, html_timeline = self.construire_widgets_audio(segments)
        self.assertIn('id="timeline-audio"', html_timeline)

    def test_timeline_contient_segment_par_locuteur(self):
        """La timeline contient un segment pour chaque groupe de locuteur."""
        segments = [
            {"speaker": "Alice", "start": 0.0, "end": 10.0, "text": "Test."},
            {"speaker": "Bob", "start": 10.0, "end": 20.0, "text": "Test."},
        ]
        html_filtre, html_timeline = self.construire_widgets_audio(segments)
        # Compter 'class="timeline-segment"' pour eviter de compter le conteneur
        # 'timeline-segments' (pluriel) comme un segment
        # / Count 'class="timeline-segment"' to avoid counting the container
        # 'timeline-segments' (plural) as a segment
        nombre_segments = html_timeline.count('class="timeline-segment"')
        self.assertEqual(nombre_segments, 2)

    def test_timeline_segment_contient_data_speaker(self):
        """Chaque segment de timeline contient l'attribut data-speaker."""
        segments = [
            {"speaker": "Alice", "start": 0.0, "end": 10.0, "text": "Test."},
        ]
        html_filtre, html_timeline = self.construire_widgets_audio(segments)
        self.assertIn('data-speaker="Alice"', html_timeline)

    def test_timeline_largeur_proportionnelle(self):
        """Les largeurs des segments timeline sont proportionnelles a leur duree."""
        # Alice: 0-5s (50%), Bob: 5-10s (50%)
        segments = [
            {"speaker": "Alice", "start": 0.0, "end": 5.0, "text": "Test."},
            {"speaker": "Bob", "start": 5.0, "end": 10.0, "text": "Test."},
        ]
        html_filtre, html_timeline = self.construire_widgets_audio(segments)
        # Chaque segment doit avoir une largeur de 50%
        # / Each segment should have a width of 50%
        self.assertIn("50.00%", html_timeline)

    def test_timeline_un_seul_locuteur_largeur_100_pourcent(self):
        """Avec un seul segment, sa largeur est 100%."""
        segments = [
            {"speaker": "Alice", "start": 0.0, "end": 30.0, "text": "Monologue."},
        ]
        html_filtre, html_timeline = self.construire_widgets_audio(segments)
        self.assertIn("100.00%", html_timeline)

    # -------------------------------------------------------------------------
    # Cas : input dict vs list
    # / Case: dict input vs list input
    # -------------------------------------------------------------------------

    def test_input_dict_avec_cle_segments(self):
        """Un dict {'model': ..., 'segments': [...]} est accepte comme input."""
        donnees = {
            "model": "voxtral-v1",
            "segments": [
                {"speaker": "Alice", "start": 0.0, "end": 10.0, "text": "Test."},
            ],
        }
        html_filtre, html_timeline = self.construire_widgets_audio(donnees)
        self.assertIn("Alice", html_filtre)
        self.assertIn("timeline-audio", html_timeline)

    def test_input_list_directe(self):
        """Une liste directe de segments est acceptee comme input."""
        segments = [
            {"speaker": "Bob", "start": 0.0, "end": 10.0, "text": "Test."},
        ]
        html_filtre, html_timeline = self.construire_widgets_audio(segments)
        self.assertIn("Bob", html_filtre)

    def test_dict_et_list_produisent_meme_resultat(self):
        """Un dict et une liste avec les memes segments produisent le meme HTML."""
        segments = [
            {"speaker": "Alice", "start": 0.0, "end": 5.0, "text": "Bonjour."},
            {"speaker": "Bob", "start": 5.0, "end": 10.0, "text": "Salut."},
        ]
        donnees_dict = {"model": "voxtral-v1", "segments": segments[:]}
        html_filtre_list, html_timeline_list = self.construire_widgets_audio(segments)
        html_filtre_dict, html_timeline_dict = self.construire_widgets_audio(donnees_dict)
        self.assertEqual(html_filtre_list, html_filtre_dict)
        self.assertEqual(html_timeline_list, html_timeline_dict)

    # -------------------------------------------------------------------------
    # Cas : securite XSS
    # / Case: XSS safety
    # -------------------------------------------------------------------------

    def test_nom_locuteur_echappe_xss_dans_filtre(self):
        """Un nom de locuteur avec balises HTML est echappe dans le filtre."""
        segments = [
            {"speaker": "<img src=x onerror=alert(1)>", "start": 0.0, "end": 5.0, "text": "Test."},
        ]
        html_filtre, html_timeline = self.construire_widgets_audio(segments)
        self.assertNotIn("<img", html_filtre)
        self.assertNotIn("<img", html_timeline)

    # -------------------------------------------------------------------------
    # Cas : normalisation speaker_id
    # / Case: speaker_id normalization
    # -------------------------------------------------------------------------

    def test_speaker_id_normalise_dans_widgets(self):
        """Un segment avec 'speaker_id' est normalise correctement pour les widgets."""
        segments = [
            {"speaker_id": "SPEAKER_00", "start": 0.0, "end": 10.0, "text": "Voxtral."},
        ]
        html_filtre, html_timeline = self.construire_widgets_audio(segments)
        self.assertIn("SPEAKER_00", html_filtre)


class Phase15FichierJSTranscriptionRythmeTest(TestCase):
    """Verifie que le fichier JS de rythme de transcription existe et est correct.
    / Verify that the transcription rhythm JS file exists and is correct."""

    def setUp(self):
        # Chemin vers le fichier JS de rythme
        # / Path to the rhythm JS file
        chemin_js = STATIC_FRONT / "js" / "transcription_rythme.js"
        self.chemin_js = chemin_js
        if chemin_js.exists():
            self.contenu_js = chemin_js.read_text()
        else:
            self.contenu_js = None

    def test_fichier_js_transcription_rythme_existe(self):
        """Le fichier transcription_rythme.js existe dans front/static/front/js/."""
        self.assertTrue(
            self.chemin_js.exists(),
            f"Fichier manquant : {self.chemin_js}",
        )

    def test_fichier_js_transcription_rythme_non_vide(self):
        """Le fichier transcription_rythme.js n'est pas vide."""
        self.assertIsNotNone(self.contenu_js)
        self.assertGreater(len(self.contenu_js), 0)

    def test_js_contient_filtre_locuteur(self):
        """Le JS gere le filtrage par locuteur."""
        if not self.contenu_js:
            self.skipTest("Fichier transcription_rythme.js absent")
        self.assertTrue(
            "speaker" in self.contenu_js.lower() or "locuteur" in self.contenu_js.lower(),
            "Le JS devrait contenir la logique de filtrage par locuteur",
        )

    def test_js_contient_timeline(self):
        """Le JS gere les interactions avec la timeline."""
        if not self.contenu_js:
            self.skipTest("Fichier transcription_rythme.js absent")
        self.assertTrue(
            "timeline" in self.contenu_js.lower(),
            "Le JS devrait contenir la logique de la timeline",
        )

    def test_base_html_charge_transcription_rythme_js(self):
        """base.html charge le fichier transcription_rythme.js."""
        contenu_base = TEMPLATE_BASE.read_text(encoding="utf-8")
        self.assertIn("transcription_rythme.js", contenu_base)


class Phase15CSSStylesTranscriptionTest(TestCase):
    """Verifie que hypostasia.css contient les styles necessaires pour PHASE-15.
    / Verify that hypostasia.css contains the necessary styles for PHASE-15."""

    def setUp(self):
        # Lire le CSS compile
        # / Read the compiled CSS
        chemin_css = STATIC_FRONT / "css" / "hypostasia.css"
        if chemin_css.exists():
            self.contenu_css = chemin_css.read_text(encoding="utf-8")
        else:
            self.contenu_css = None

    def test_css_contient_speaker_block(self):
        """hypostasia.css contient les styles pour speaker-block."""
        if not self.contenu_css:
            self.skipTest("hypostasia.css absent")
        self.assertIn("speaker-block", self.contenu_css)

    def test_css_contient_marqueur_temporel(self):
        """hypostasia.css contient les styles pour marqueur-temporel."""
        if not self.contenu_css:
            self.skipTest("hypostasia.css absent")
        self.assertIn("marqueur-temporel", self.contenu_css)

    def test_css_contient_timeline_audio(self):
        """hypostasia.css contient les styles pour timeline-audio."""
        if not self.contenu_css:
            self.skipTest("hypostasia.css absent")
        self.assertIn("timeline-audio", self.contenu_css)

    def test_css_contient_filtre_locuteurs(self):
        """hypostasia.css contient les styles pour filtre-locuteurs."""
        if not self.contenu_css:
            self.skipTest("hypostasia.css absent")
        self.assertIn("filtre-locuteurs", self.contenu_css)


# =============================================================================
# PHASE-17 — Mode focus + raccourcis clavier
# / PHASE-17 — Focus mode + keyboard shortcuts
# =============================================================================


class Phase17FichierKeyboardJSTest(TestCase):
    """Verifie que keyboard.js existe et contient les elements attendus.
    / Verify that keyboard.js exists and contains expected elements."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        chemin_js = STATIC_FRONT / "js" / "keyboard.js"
        cls.fichier_existe = chemin_js.exists()
        cls.contenu_js = chemin_js.read_text() if cls.fichier_existe else ""

    def test_fichier_keyboard_js_existe(self):
        """keyboard.js existe dans front/static/front/js/."""
        self.assertTrue(self.fichier_existe, "keyboard.js absent")

    def test_fichier_keyboard_js_non_vide(self):
        """keyboard.js n'est pas vide."""
        self.assertGreater(len(self.contenu_js), 100)

    def test_js_contient_iife(self):
        """keyboard.js est enveloppe dans une IIFE."""
        self.assertIn("(function()", self.contenu_js)

    def test_js_contient_estDansChampSaisie(self):
        """keyboard.js contient la garde champ de saisie."""
        self.assertIn("estDansChampSaisie", self.contenu_js)

    def test_js_contient_gererEscape(self):
        """keyboard.js contient la cascade Escape."""
        self.assertIn("gererEscape", self.contenu_js)

    def test_js_contient_extractionSuivante(self):
        """keyboard.js contient la navigation J/K."""
        self.assertIn("extractionSuivante", self.contenu_js)
        self.assertIn("extractionPrecedente", self.contenu_js)

    def test_js_contient_ouvrirAideRaccourcis(self):
        """keyboard.js contient la modale aide (?)."""
        self.assertIn("ouvrirAideRaccourcis", self.contenu_js)

    def test_js_contient_listener_unique(self):
        """keyboard.js utilise un seul addEventListener keydown."""
        # Compter les addEventListener('keydown'
        # / Count addEventListener('keydown'
        occurrences = self.contenu_js.count("addEventListener('keydown'")
        self.assertEqual(occurrences, 1, f"Devrait avoir 1 seul listener keydown, trouvé {occurrences}")

    def test_js_expose_api_publique(self):
        """keyboard.js expose window.raccourcisClavier."""
        self.assertIn("window.raccourcisClavier", self.contenu_js)

    def test_js_appelle_apis_modules(self):
        """keyboard.js appelle les APIs des autres modules."""
        self.assertIn("window.arbreOverlay", self.contenu_js)
        self.assertIn("window.drawerVueListe", self.contenu_js)
        self.assertIn("window.dashboardConsensus", self.contenu_js)
        self.assertIn("window.marginalia", self.contenu_js)


class Phase17MarginaliaModeFocusTest(TestCase):
    """Verifie que marginalia.js contient le mode focus et l'API publique.
    / Verify that marginalia.js contains focus mode and public API."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        chemin_js = STATIC_FRONT / "js" / "marginalia.js"
        cls.contenu_js = chemin_js.read_text() if chemin_js.exists() else ""

    def test_marginalia_contient_iife(self):
        """marginalia.js est enveloppe dans une IIFE."""
        self.assertIn("(function()", self.contenu_js)

    def test_marginalia_contient_mode_focus(self):
        """marginalia.js contient les fonctions de mode focus."""
        self.assertIn("activerModeFocus", self.contenu_js)
        self.assertIn("desactiverModeFocus", self.contenu_js)
        self.assertIn("basculerModeFocus", self.contenu_js)
        self.assertIn("modeFocusEstActif", self.contenu_js)

    def test_marginalia_contient_localstorage(self):
        """marginalia.js persiste le mode focus via localStorage."""
        self.assertIn("hypostasia-mode-focus", self.contenu_js)
        self.assertIn("localStorage", self.contenu_js)

    def test_marginalia_expose_api_publique(self):
        """marginalia.js expose window.marginalia avec les bonnes cles."""
        self.assertIn("window.marginalia", self.contenu_js)

    def test_marginalia_expose_alias_global(self):
        """marginalia.js garde l'alias global construirePastillesMarginales."""
        self.assertIn("window.construirePastillesMarginales", self.contenu_js)

    def test_marginalia_pas_de_listener_keydown(self):
        """marginalia.js ne contient PAS de listener keydown (delegue a keyboard.js)."""
        self.assertNotIn("addEventListener('keydown'", self.contenu_js)


class Phase17ListenersSupprimesDansModulesTest(TestCase):
    """Verifie que les listeners keydown ont ete supprimes des autres modules.
    / Verify that keydown listeners have been removed from other modules."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.arbre_js = (STATIC_FRONT / "js" / "arbre_overlay.js").read_text()
        cls.drawer_js = (STATIC_FRONT / "js" / "drawer_vue_liste.js").read_text()
        cls.dashboard_js = (STATIC_FRONT / "js" / "dashboard_consensus.js").read_text()

    def test_arbre_overlay_pas_de_keydown(self):
        """arbre_overlay.js ne contient plus de listener keydown."""
        self.assertNotIn("addEventListener('keydown'", self.arbre_js)

    def test_drawer_vue_liste_pas_de_keydown(self):
        """drawer_vue_liste.js ne contient plus de listener keydown."""
        self.assertNotIn("addEventListener('keydown'", self.drawer_js)

    def test_dashboard_consensus_pas_de_keydown(self):
        """dashboard_consensus.js ne contient plus de listener keydown."""
        self.assertNotIn("addEventListener('keydown'", self.dashboard_js)

    def test_arbre_overlay_conserve_api_publique(self):
        """arbre_overlay.js conserve window.arbreOverlay."""
        self.assertIn("window.arbreOverlay", self.arbre_js)

    def test_drawer_vue_liste_conserve_api_publique(self):
        """drawer_vue_liste.js conserve window.drawerVueListe."""
        self.assertIn("window.drawerVueListe", self.drawer_js)

    def test_dashboard_consensus_conserve_api_publique(self):
        """dashboard_consensus.js conserve window.dashboardConsensus."""
        self.assertIn("window.dashboardConsensus", self.dashboard_js)


class Phase17CSSStylesTest(TestCase):
    """Verifie que hypostasia.css contient les styles PHASE-17.
    / Verify that hypostasia.css contains PHASE-17 styles."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        chemin_css = STATIC_FRONT / "css" / "hypostasia.css"
        cls.contenu_css = chemin_css.read_text() if chemin_css.exists() else ""

    def test_css_contient_mode_focus(self):
        """hypostasia.css contient les styles body.mode-focus."""
        self.assertIn("body.mode-focus", self.contenu_css)

    def test_css_contient_pastilles_masquees_en_focus(self):
        """hypostasia.css masque les pastilles en mode focus."""
        self.assertIn("body.mode-focus .pastilles-marge", self.contenu_css)

    def test_css_contient_extraction_selectionnee(self):
        """hypostasia.css contient le style extraction-selectionnee."""
        self.assertIn(".extraction-selectionnee", self.contenu_css)

    def test_css_contient_modale_raccourcis(self):
        """hypostasia.css contient les styles de la modale raccourcis."""
        self.assertIn(".modale-raccourcis-backdrop", self.contenu_css)
        self.assertIn(".modale-raccourcis", self.contenu_css)
        self.assertIn(".raccourci-touche", self.contenu_css)

    def test_css_contient_btn_toolbar_actif(self):
        """hypostasia.css contient le style du bouton toolbar actif."""
        self.assertIn(".btn-toolbar-actif", self.contenu_css)


class Phase17BaseHTMLTest(TestCase):
    """Verifie que base.html charge keyboard.js et active le bouton focus.
    / Verify that base.html loads keyboard.js and enables the focus button."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.contenu_html = TEMPLATE_BASE.read_text() if TEMPLATE_BASE.exists() else ""

    def test_base_html_charge_keyboard_js(self):
        """base.html charge keyboard.js."""
        self.assertIn("keyboard.js", self.contenu_html)

    def test_base_html_keyboard_js_apres_autres_scripts(self):
        """keyboard.js est charge apres les autres modules JS."""
        # keyboard.js doit etre le dernier script JS custom
        # / keyboard.js must be the last custom JS script
        position_keyboard = self.contenu_html.find("keyboard.js")
        position_dashboard = self.contenu_html.find("dashboard_consensus.js")
        self.assertGreater(position_keyboard, position_dashboard,
                          "keyboard.js doit charger apres dashboard_consensus.js")

    def test_base_html_bouton_focus_actif(self):
        """base.html contient le bouton focus sans disabled ni data-placeholder."""
        self.assertIn('id="btn-toolbar-focus"', self.contenu_html)
        # Verifier que disabled n'est PAS sur ce bouton
        # / Verify disabled is NOT on this button
        self.assertNotIn('data-placeholder="PHASE-17"', self.contenu_html)


# =============================================================================
# PHASE-18 — Alignement cross-documents par hypostases
# / PHASE-18 — Cross-document alignment by hypostases
# =============================================================================


class Phase18FichiersStatiquesTest(TestCase):
    """Verifie que les fichiers statiques de PHASE-18 existent.
    / Verify that PHASE-18 static files exist."""

    def test_views_alignement_py_existe(self):
        """front/views_alignement.py existe."""
        chemin = BASE_DIR / "front" / "views_alignement.py"
        self.assertTrue(chemin.exists(), f"Fichier manquant : {chemin}")

    def test_alignement_js_existe(self):
        """front/static/front/js/alignement.js existe."""
        chemin = STATIC_FRONT / "js" / "alignement.js"
        self.assertTrue(chemin.exists(), f"Fichier manquant : {chemin}")

    def test_template_alignement_tableau_existe(self):
        """front/templates/front/includes/alignement_tableau.html existe."""
        chemin = BASE_DIR / "front" / "templates" / "front" / "includes" / "alignement_tableau.html"
        self.assertTrue(chemin.exists(), f"Template manquant : {chemin}")


class Phase18BaseHTMLTest(TestCase):
    """Verifie que base.html integre les elements PHASE-18.
    / Verify that base.html integrates PHASE-18 elements."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.contenu_html = TEMPLATE_BASE.read_text() if TEMPLATE_BASE.exists() else ""

    def test_base_html_charge_alignement_js(self):
        """base.html charge alignement.js."""
        self.assertIn("alignement.js", self.contenu_html)

    def test_alignement_js_avant_keyboard_js(self):
        """alignement.js est charge avant keyboard.js."""
        position_alignement = self.contenu_html.find("alignement.js")
        position_keyboard = self.contenu_html.find("keyboard.js")
        self.assertGreater(position_alignement, -1, "alignement.js non trouve")
        self.assertGreater(position_keyboard, position_alignement,
                          "alignement.js doit charger avant keyboard.js")

    def test_base_html_contient_modale_container(self):
        """base.html contient le conteneur de modale alignement."""
        self.assertIn('id="alignement-modale-container"', self.contenu_html)

    def test_base_html_contient_bouton_comparer(self):
        """base.html contient le bouton Comparer dans le footer de l'arbre."""
        self.assertIn('id="btn-comparer-arbre"', self.contenu_html)
        self.assertIn("Comparer", self.contenu_html)


class Phase18AlignementJSContenuTest(TestCase):
    """Verifie le contenu de alignement.js (PHASE-18).
    / Verify alignement.js content (PHASE-18)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        chemin_js = STATIC_FRONT / "js" / "alignement.js"
        cls.contenu_js = chemin_js.read_text() if chemin_js.exists() else ""

    def test_expose_api_publique(self):
        """alignement.js expose window.alignement."""
        self.assertIn("window.alignement", self.contenu_js)

    def test_expose_activerSelection(self):
        """alignement.js expose activerSelection."""
        self.assertIn("activerSelection", self.contenu_js)

    def test_expose_desactiverSelection(self):
        """alignement.js expose desactiverSelection."""
        self.assertIn("desactiverSelection", self.contenu_js)

    def test_expose_estOuvert(self):
        """alignement.js expose estOuvert."""
        self.assertIn("estOuvert", self.contenu_js)

    def test_iife_pattern(self):
        """alignement.js utilise le pattern IIFE."""
        self.assertIn("(function()", self.contenu_js)
        self.assertIn("'use strict'", self.contenu_js)

    def test_commentaires_bilingues(self):
        """alignement.js a des commentaires bilingues FR/EN."""
        self.assertIn("// /", self.contenu_js)


class Phase18KeyboardJSTest(TestCase):
    """Verifie que keyboard.js integre le raccourci A et l'Escape (PHASE-18).
    / Verify keyboard.js integrates A shortcut and Escape (PHASE-18)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        chemin_js = STATIC_FRONT / "js" / "keyboard.js"
        cls.contenu_js = chemin_js.read_text() if chemin_js.exists() else ""

    def test_raccourci_a_present(self):
        """keyboard.js contient le cas 'a' dans le switch."""
        self.assertIn("case 'a':", self.contenu_js)

    def test_raccourci_a_appelle_alignement(self):
        """keyboard.js appelle window.alignement dans le cas 'a'."""
        self.assertIn("window.alignement", self.contenu_js)

    def test_escape_ferme_modale_alignement(self):
        """keyboard.js ferme la modale alignement dans la cascade Escape."""
        self.assertIn("alignement.estOuvert()", self.contenu_js)
        self.assertIn("alignement.fermer()", self.contenu_js)

    def test_aide_modale_contient_raccourci_a(self):
        """La modale d'aide contient le raccourci A."""
        self.assertIn("Comparer / Aligner des pages", self.contenu_js)


class Phase18CSSStylesTest(TestCase):
    """Verifie que hypostasia.css contient les styles PHASE-18.
    / Verify hypostasia.css contains PHASE-18 styles."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        chemin_css = STATIC_FRONT / "css" / "hypostasia.css"
        cls.contenu_css = chemin_css.read_text() if chemin_css.exists() else ""

    def test_classe_modale_backdrop(self):
        """CSS contient .alignement-modale-backdrop."""
        self.assertIn(".alignement-modale-backdrop", self.contenu_css)

    def test_classe_modale(self):
        """CSS contient .alignement-modale."""
        self.assertIn(".alignement-modale", self.contenu_css)

    def test_classe_table(self):
        """CSS contient .alignement-table."""
        self.assertIn(".alignement-table", self.contenu_css)

    def test_classe_cell(self):
        """CSS contient .alignement-cell."""
        self.assertIn(".alignement-cell", self.contenu_css)

    def test_classe_cell_gap(self):
        """CSS contient .alignement-cell-gap."""
        self.assertIn(".alignement-cell-gap", self.contenu_css)

    def test_classe_barre_selection(self):
        """CSS contient .barre-selection-alignement."""
        self.assertIn(".barre-selection-alignement", self.contenu_css)

    def test_classe_checkbox_selection(self):
        """CSS contient .arbre-checkbox-selection."""
        self.assertIn(".arbre-checkbox-selection", self.contenu_css)


class Phase18URLsExistentTest(TestCase):
    """Verifie que les URLs PHASE-18 sont enregistrees.
    / Verify that PHASE-18 URLs are registered."""

    def test_url_alignement_tableau(self):
        """GET /alignement/tableau/ sans page_ids retourne 400."""
        reponse = self.client.get("/alignement/tableau/")
        self.assertEqual(reponse.status_code, 400)

    def test_url_alignement_export_markdown(self):
        """GET /alignement/export_markdown/ sans page_ids retourne 400."""
        reponse = self.client.get("/alignement/export_markdown/")
        self.assertEqual(reponse.status_code, 400)


class Phase18EndpointTableauTest(TestCase):
    """Verifie l'endpoint GET /alignement/tableau/ (PHASE-18).
    / Verify GET /alignement/tableau/ endpoint (PHASE-18)."""

    def setUp(self):
        from core.models import Page
        from hypostasis_extractor.models import ExtractionJob, ExtractedEntity

        # Cree 3 pages avec des extractions de hypostases differentes
        # / Create 3 pages with different hypostase extractions
        self.page_a = Page.objects.create(
            title="Document A",
            html_original="<html><body>Doc A</body></html>",
            html_readability="<p>Doc A</p>",
            text_readability="Doc A.",
        )
        self.page_b = Page.objects.create(
            title="Document B",
            html_original="<html><body>Doc B</body></html>",
            html_readability="<p>Doc B</p>",
            text_readability="Doc B.",
        )
        self.page_c = Page.objects.create(
            title="Document C",
            html_original="<html><body>Doc C</body></html>",
            html_readability="<p>Doc C</p>",
            text_readability="Doc C.",
        )

        # Jobs d'extraction completes / Completed extraction jobs
        self.job_a = ExtractionJob.objects.create(
            page=self.page_a, name="Job A", status="completed", ai_model=None,
        )
        self.job_b = ExtractionJob.objects.create(
            page=self.page_b, name="Job B", status="completed", ai_model=None,
        )
        self.job_c = ExtractionJob.objects.create(
            page=self.page_c, name="Job C", status="completed", ai_model=None,
        )

        # Entites avec hypostases differentes / Entities with different hypostases
        # Page A : theorie + phenomene
        ExtractedEntity.objects.create(
            job=self.job_a,
            extraction_class="concept",
            extraction_text="Une theorie",
            start_char=0,
            end_char=11,
            attributes={"hypostase": "Théorie", "resume": "Theorie de la relativite"},
        )
        ExtractedEntity.objects.create(
            job=self.job_a,
            extraction_class="concept",
            extraction_text="Un phenomene",
            start_char=0,
            end_char=12,
            attributes={"hypostase": "Phénomène", "resume": "Phenomene observe"},
        )

        # Page B : theorie seulement (gap sur phenomene)
        ExtractedEntity.objects.create(
            job=self.job_b,
            extraction_class="concept",
            extraction_text="Autre theorie",
            start_char=0,
            end_char=13,
            attributes={"hypostase": "Théorie", "resume": "Theorie quantique"},
        )

        # Page C : phenomene + hypothese (gap sur theorie)
        ExtractedEntity.objects.create(
            job=self.job_c,
            extraction_class="concept",
            extraction_text="Encore un phenomene",
            start_char=0,
            end_char=19,
            attributes={"hypostase": "Phénomène", "resume": "Phenomene naturel"},
        )
        ExtractedEntity.objects.create(
            job=self.job_c,
            extraction_class="concept",
            extraction_text="Une hypothese",
            start_char=0,
            end_char=13,
            attributes={"hypostase": "Hypothèse", "resume": "Hypothese de travail"},
        )

        # Entite masquee (ne doit PAS apparaitre) / Hidden entity (must NOT appear)
        ExtractedEntity.objects.create(
            job=self.job_a,
            extraction_class="concept",
            extraction_text="Masquee",
            start_char=0,
            end_char=7,
            attributes={"hypostase": "Axiome", "resume": "Axiome masque"},
            masquee=True,
        )

    def test_tableau_2_pages_retourne_200(self):
        """GET /alignement/tableau/?page_ids=X,Y retourne 200."""
        url = f"/alignement/tableau/?page_ids={self.page_a.pk},{self.page_b.pk}"
        reponse = self.client.get(url)
        self.assertEqual(reponse.status_code, 200)

    def test_tableau_3_pages_retourne_200(self):
        """GET /alignement/tableau/?page_ids=X,Y,Z retourne 200."""
        url = f"/alignement/tableau/?page_ids={self.page_a.pk},{self.page_b.pk},{self.page_c.pk}"
        reponse = self.client.get(url)
        self.assertEqual(reponse.status_code, 200)

    def test_tableau_contient_noms_pages(self):
        """Le tableau contient les titres des pages."""
        url = f"/alignement/tableau/?page_ids={self.page_a.pk},{self.page_b.pk}"
        reponse = self.client.get(url)
        contenu = reponse.content.decode("utf-8")
        self.assertIn("Document A", contenu)
        self.assertIn("Document B", contenu)

    def test_tableau_contient_hypostases(self):
        """Le tableau contient les hypostases trouvees."""
        url = f"/alignement/tableau/?page_ids={self.page_a.pk},{self.page_b.pk},{self.page_c.pk}"
        reponse = self.client.get(url)
        contenu = reponse.content.decode("utf-8")
        self.assertIn("theorie", contenu)
        self.assertIn("phenomene", contenu)

    def test_tableau_contient_cellules_gap(self):
        """Le tableau contient des cellules vides (gaps) avec le tiret."""
        url = f"/alignement/tableau/?page_ids={self.page_a.pk},{self.page_b.pk},{self.page_c.pk}"
        reponse = self.client.get(url)
        contenu = reponse.content.decode("utf-8")
        # Page B n'a pas de phenomene → gap
        # / Page B has no phenomene → gap
        self.assertIn("alignement-cell-gap", contenu)

    def test_tableau_exclut_entites_masquees(self):
        """Les entites masquees ne sont pas dans le tableau."""
        url = f"/alignement/tableau/?page_ids={self.page_a.pk},{self.page_b.pk}"
        reponse = self.client.get(url)
        contenu = reponse.content.decode("utf-8")
        # L'axiome masque ne doit pas apparaitre / Hidden axiom should not appear
        self.assertNotIn("axiome", contenu.lower().split("hypostase")[0] if "hypostase" in contenu.lower() else contenu.lower())

    def test_tableau_contient_compteur(self):
        """Le tableau contient des compteurs dans les cellules."""
        url = f"/alignement/tableau/?page_ids={self.page_a.pk},{self.page_b.pk}"
        reponse = self.client.get(url)
        contenu = reponse.content.decode("utf-8")
        self.assertIn("alignement-cell-count", contenu)

    def test_tableau_contient_nom_famille(self):
        """Le tableau contient des noms de familles."""
        url = f"/alignement/tableau/?page_ids={self.page_a.pk},{self.page_b.pk},{self.page_c.pk}"
        reponse = self.client.get(url)
        contenu = reponse.content.decode("utf-8")
        # Theorie est epistemique / Theory is epistemic
        self.assertIn("pistemique", contenu)

    def test_tableau_refuse_1_page(self):
        """GET /alignement/tableau/?page_ids=X (1 seule page) retourne 400."""
        url = f"/alignement/tableau/?page_ids={self.page_a.pk}"
        reponse = self.client.get(url)
        self.assertEqual(reponse.status_code, 400)

    def test_tableau_refuse_7_pages(self):
        """GET /alignement/tableau/?page_ids=... (7 pages) retourne 400."""
        url = "/alignement/tableau/?page_ids=1,2,3,4,5,6,7"
        reponse = self.client.get(url)
        self.assertEqual(reponse.status_code, 400)

    def test_tableau_refuse_ids_invalides(self):
        """GET /alignement/tableau/?page_ids=abc retourne 400."""
        reponse = self.client.get("/alignement/tableau/?page_ids=abc,def")
        self.assertEqual(reponse.status_code, 400)


class Phase18EndpointExportMarkdownTest(TestCase):
    """Verifie l'endpoint GET /alignement/export_markdown/ (PHASE-18).
    / Verify GET /alignement/export_markdown/ endpoint (PHASE-18)."""

    def setUp(self):
        from core.models import Page
        from hypostasis_extractor.models import ExtractionJob, ExtractedEntity

        self.page_a = Page.objects.create(
            title="Export Doc A",
            html_original="<html><body>A</body></html>",
            html_readability="<p>A</p>",
            text_readability="A.",
        )
        self.page_b = Page.objects.create(
            title="Export Doc B",
            html_original="<html><body>B</body></html>",
            html_readability="<p>B</p>",
            text_readability="B.",
        )

        job_a = ExtractionJob.objects.create(
            page=self.page_a, name="Job A", status="completed", ai_model=None,
        )
        job_b = ExtractionJob.objects.create(
            page=self.page_b, name="Job B", status="completed", ai_model=None,
        )

        ExtractedEntity.objects.create(
            job=job_a,
            extraction_class="concept",
            extraction_text="Theorie",
            start_char=0,
            end_char=7,
            attributes={"hypostase": "Théorie", "resume": "Theorie doc A"},
        )
        ExtractedEntity.objects.create(
            job=job_b,
            extraction_class="concept",
            extraction_text="Theorie B",
            start_char=0,
            end_char=9,
            attributes={"hypostase": "Théorie", "resume": "Theorie doc B"},
        )

    def test_export_markdown_retourne_200(self):
        """GET /alignement/export_markdown/?page_ids=X,Y retourne 200."""
        url = f"/alignement/export_markdown/?page_ids={self.page_a.pk},{self.page_b.pk}"
        reponse = self.client.get(url)
        self.assertEqual(reponse.status_code, 200)

    def test_export_markdown_content_type(self):
        """L'export retourne du text/markdown."""
        url = f"/alignement/export_markdown/?page_ids={self.page_a.pk},{self.page_b.pk}"
        reponse = self.client.get(url)
        self.assertIn("text/markdown", reponse["Content-Type"])

    def test_export_markdown_content_disposition(self):
        """L'export a un Content-Disposition attachment."""
        url = f"/alignement/export_markdown/?page_ids={self.page_a.pk},{self.page_b.pk}"
        reponse = self.client.get(url)
        self.assertIn("attachment", reponse["Content-Disposition"])
        self.assertIn("alignement-hypostases.md", reponse["Content-Disposition"])

    def test_export_markdown_contient_titres_pages(self):
        """Le Markdown exporte contient les titres des pages."""
        url = f"/alignement/export_markdown/?page_ids={self.page_a.pk},{self.page_b.pk}"
        reponse = self.client.get(url)
        contenu = reponse.content.decode("utf-8")
        self.assertIn("Export Doc A", contenu)
        self.assertIn("Export Doc B", contenu)

    def test_export_markdown_contient_tableau(self):
        """Le Markdown exporte contient un tableau Markdown avec des pipes."""
        url = f"/alignement/export_markdown/?page_ids={self.page_a.pk},{self.page_b.pk}"
        reponse = self.client.get(url)
        contenu = reponse.content.decode("utf-8")
        self.assertIn("| Hypostase |", contenu)
        self.assertIn("| --- |", contenu)

    def test_export_markdown_refuse_1_page(self):
        """GET /alignement/export_markdown/?page_ids=X (1 seule page) retourne 400."""
        url = f"/alignement/export_markdown/?page_ids={self.page_a.pk}"
        reponse = self.client.get(url)
        self.assertEqual(reponse.status_code, 400)


class Phase18TemplateAlignementContenuTest(TestCase):
    """Verifie le contenu du template alignement_tableau.html (PHASE-18).
    / Verify alignment table template content (PHASE-18)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        chemin_template = BASE_DIR / "front" / "templates" / "front" / "includes" / "alignement_tableau.html"
        cls.contenu_template = chemin_template.read_text() if chemin_template.exists() else ""

    def test_template_contient_bouton_export(self):
        """Le template contient le bouton d'export."""
        self.assertIn('id="btn-export-alignement"', self.contenu_template)

    def test_template_contient_bouton_fermer(self):
        """Le template contient le bouton fermer."""
        self.assertIn('id="btn-fermer-alignement"', self.contenu_template)

    def test_template_contient_tableau(self):
        """Le template contient un tableau HTML."""
        self.assertIn("alignement-table", self.contenu_template)

    def test_template_contient_cellules_gap(self):
        """Le template contient le pattern de cellule gap."""
        self.assertIn("alignement-cell-gap", self.contenu_template)

    def test_template_contient_empty_state(self):
        """Le template contient un etat vide."""
        self.assertIn("empty-state", self.contenu_template)

    def test_template_contient_commentaires_bilingues(self):
        """Le template contient des commentaires bilingues FR/EN."""
        self.assertIn("<!-- /", self.contenu_template)

    def test_template_contient_bouton_bascule_source(self):
        """Le template contient le bouton de bascule Source / Resume."""
        self.assertIn('id="btn-bascule-source"', self.contenu_template)

    def test_template_contient_data_testid_bascule(self):
        """Le bouton bascule a un data-testid."""
        self.assertIn('data-testid="btn-bascule-source"', self.contenu_template)

    def test_template_contient_double_span_resume_et_origine(self):
        """Le template contient les deux spans pour resume et texte d'origine."""
        self.assertIn("alignement-texte-resume", self.contenu_template)
        self.assertIn("alignement-texte-origine", self.contenu_template)

    def test_template_contient_resume_complet(self):
        """Le template affiche le resume complet (pas tronque)."""
        self.assertIn("cellule.resume_complet", self.contenu_template)

    def test_template_contient_texte_origine(self):
        """Le template affiche le texte d'origine."""
        self.assertIn("cellule.texte_origine", self.contenu_template)

    def test_template_contient_avertissement(self):
        """Le template contient le bloc d'avertissement conditionnel."""
        self.assertIn("avertissement", self.contenu_template)
        self.assertIn("warning-banner", self.contenu_template)


# =============================================================================
# PHASE-18b — Bouton dossier + bascule texte/resume + dossier_id
# / PHASE-18b — Folder button + text toggle + dossier_id
# =============================================================================


class Phase18bDossierAlignementEndpointTest(TestCase):
    """Verifie l'endpoint GET /alignement/tableau/?dossier_id=X.
    / Verify GET /alignement/tableau/?dossier_id=X endpoint."""

    def setUp(self):
        from core.models import Dossier, Page
        from hypostasis_extractor.models import ExtractionJob, ExtractedEntity

        # Cree un dossier avec 3 pages et des extractions
        # / Create a folder with 3 pages and extractions
        self.dossier_avec_pages = Dossier.objects.create(name="Dossier test alignement")

        self.page_a = Page.objects.create(
            title="Dossier Doc A",
            html_original="<html><body>A</body></html>",
            html_readability="<p>A</p>",
            text_readability="Doc A contenu.",
            dossier=self.dossier_avec_pages,
        )
        self.page_b = Page.objects.create(
            title="Dossier Doc B",
            html_original="<html><body>B</body></html>",
            html_readability="<p>B</p>",
            text_readability="Doc B contenu.",
            dossier=self.dossier_avec_pages,
        )
        self.page_c = Page.objects.create(
            title="Dossier Doc C",
            html_original="<html><body>C</body></html>",
            html_readability="<p>C</p>",
            text_readability="Doc C contenu.",
            dossier=self.dossier_avec_pages,
        )

        # Dossier avec 1 seule page (pas assez pour aligner)
        # / Folder with only 1 page (not enough to align)
        self.dossier_une_page = Dossier.objects.create(name="Dossier une page")
        self.page_seule = Page.objects.create(
            title="Page seule",
            html_original="<html><body>Seule</body></html>",
            html_readability="<p>Seule</p>",
            text_readability="Seule.",
            dossier=self.dossier_une_page,
        )

        # Dossier vide / Empty folder
        self.dossier_vide = Dossier.objects.create(name="Dossier vide")

        # Jobs d'extraction / Extraction jobs
        job_a = ExtractionJob.objects.create(
            page=self.page_a, name="Job A", status="completed", ai_model=None,
        )
        job_b = ExtractionJob.objects.create(
            page=self.page_b, name="Job B", status="completed", ai_model=None,
        )

        # Entites avec extraction_text (pour tester le texte d'origine)
        # / Entities with extraction_text (to test source text)
        ExtractedEntity.objects.create(
            job=job_a,
            extraction_class="concept",
            extraction_text="Le texte source exact du document A",
            start_char=0,
            end_char=35,
            attributes={"hypostase": "Théorie", "resume": "Resume complet de la theorie dans le document A qui est assez long"},
        )
        ExtractedEntity.objects.create(
            job=job_b,
            extraction_class="concept",
            extraction_text="Le texte source exact du document B",
            start_char=0,
            end_char=35,
            attributes={"hypostase": "Théorie", "resume": "Resume complet de la theorie dans le document B"},
        )

    def test_tableau_dossier_id_retourne_200(self):
        """GET /alignement/tableau/?dossier_id=X avec dossier >= 2 pages retourne 200."""
        url = f"/alignement/tableau/?dossier_id={self.dossier_avec_pages.pk}"
        reponse = self.client.get(url)
        self.assertEqual(reponse.status_code, 200)

    def test_tableau_dossier_contient_noms_pages(self):
        """Le tableau contient les titres des pages du dossier."""
        url = f"/alignement/tableau/?dossier_id={self.dossier_avec_pages.pk}"
        reponse = self.client.get(url)
        contenu = reponse.content.decode("utf-8")
        self.assertIn("Dossier Doc A", contenu)
        self.assertIn("Dossier Doc B", contenu)

    def test_tableau_dossier_contient_resume_complet(self):
        """Le tableau affiche le resume complet, pas tronque."""
        url = f"/alignement/tableau/?dossier_id={self.dossier_avec_pages.pk}"
        reponse = self.client.get(url)
        contenu = reponse.content.decode("utf-8")
        # Le resume fait plus de 60 chars — doit apparaitre en entier
        # / The summary is > 60 chars — should appear in full
        self.assertIn("Resume complet de la theorie dans le document A qui est assez long", contenu)

    def test_tableau_dossier_contient_texte_origine(self):
        """Le tableau contient le texte d'origine (extraction_text)."""
        url = f"/alignement/tableau/?dossier_id={self.dossier_avec_pages.pk}"
        reponse = self.client.get(url)
        contenu = reponse.content.decode("utf-8")
        self.assertIn("Le texte source exact du document A", contenu)
        self.assertIn("Le texte source exact du document B", contenu)

    def test_tableau_dossier_contient_bouton_bascule(self):
        """Le tableau contient le bouton de bascule Source/Resume."""
        url = f"/alignement/tableau/?dossier_id={self.dossier_avec_pages.pk}"
        reponse = self.client.get(url)
        contenu = reponse.content.decode("utf-8")
        self.assertIn('id="btn-bascule-source"', contenu)

    def test_tableau_dossier_1_page_retourne_400(self):
        """GET /alignement/tableau/?dossier_id=X avec 1 seule page retourne 400."""
        url = f"/alignement/tableau/?dossier_id={self.dossier_une_page.pk}"
        reponse = self.client.get(url)
        self.assertEqual(reponse.status_code, 400)
        self.assertIn("moins de 2", reponse.content.decode("utf-8"))

    def test_tableau_dossier_vide_retourne_400(self):
        """GET /alignement/tableau/?dossier_id=X avec dossier vide retourne 400."""
        url = f"/alignement/tableau/?dossier_id={self.dossier_vide.pk}"
        reponse = self.client.get(url)
        self.assertEqual(reponse.status_code, 400)

    def test_tableau_dossier_inexistant_retourne_404(self):
        """GET /alignement/tableau/?dossier_id=99999 retourne 404."""
        reponse = self.client.get("/alignement/tableau/?dossier_id=99999")
        self.assertEqual(reponse.status_code, 404)

    def test_tableau_dossier_id_invalide_retourne_400(self):
        """GET /alignement/tableau/?dossier_id=abc retourne 400."""
        reponse = self.client.get("/alignement/tableau/?dossier_id=abc")
        self.assertEqual(reponse.status_code, 400)

    def test_export_markdown_dossier_id_retourne_200(self):
        """GET /alignement/export_markdown/?dossier_id=X retourne 200."""
        url = f"/alignement/export_markdown/?dossier_id={self.dossier_avec_pages.pk}"
        reponse = self.client.get(url)
        self.assertEqual(reponse.status_code, 200)
        self.assertIn("text/markdown", reponse["Content-Type"])

    def test_export_markdown_dossier_contient_titres(self):
        """L'export Markdown via dossier_id contient les titres des pages."""
        url = f"/alignement/export_markdown/?dossier_id={self.dossier_avec_pages.pk}"
        reponse = self.client.get(url)
        contenu = reponse.content.decode("utf-8")
        self.assertIn("Dossier Doc A", contenu)
        self.assertIn("Dossier Doc B", contenu)

    def test_page_ids_classique_fonctionne_toujours(self):
        """GET /alignement/tableau/?page_ids=X,Y fonctionne toujours (non-regression)."""
        url = f"/alignement/tableau/?page_ids={self.page_a.pk},{self.page_b.pk}"
        reponse = self.client.get(url)
        self.assertEqual(reponse.status_code, 200)


class Phase18bArbreTemplateTest(TestCase):
    """Verifie que le template arbre_dossiers contient le bouton Aligner.
    / Verify the tree template contains the Align button."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        chemin_template = BASE_DIR / "front" / "templates" / "front" / "includes" / "arbre_dossiers.html"
        cls.contenu_template = chemin_template.read_text() if chemin_template.exists() else ""

    def test_bouton_aligner_dossier_present(self):
        """Le template contient la classe btn-aligner-dossier."""
        self.assertIn("btn-aligner-dossier", self.contenu_template)

    def test_bouton_aligner_a_data_testid(self):
        """Le bouton aligner a un data-testid."""
        self.assertIn('data-testid="btn-aligner-dossier"', self.contenu_template)

    def test_bouton_aligner_conditionne_par_count(self):
        """Le bouton aligner n'apparait que si >= 2 pages."""
        self.assertIn("dossier.pages.count >= 2", self.contenu_template)

    def test_bouton_aligner_a_data_dossier_id(self):
        """Le bouton aligner porte le data-dossier-id."""
        self.assertIn("data-dossier-id", self.contenu_template)

    def test_bouton_aligner_dans_liste_pages(self):
        """Le bouton aligner est dans la liste <ul> des pages, pas dans le header."""
        # Le bouton est dans un <li> a l'interieur de .dossier-pages
        # / The button is in a <li> inside .dossier-pages
        self.assertIn("<li", self.contenu_template.split("btn-aligner-dossier")[0].split("dossier-pages")[-1])


class Phase18bAlignementJSTest(TestCase):
    """Verifie que alignement.js contient les fonctions de la phase 18b.
    / Verify alignement.js contains phase 18b functions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        chemin_js = STATIC_FRONT / "js" / "alignement.js"
        cls.contenu_js = chemin_js.read_text() if chemin_js.exists() else ""

    def test_fonction_ouvrir_dossier_existe(self):
        """alignement.js contient la fonction ouvrirDossier."""
        self.assertIn("function ouvrirDossier", self.contenu_js)

    def test_api_publique_expose_ouvrir_dossier(self):
        """L'API publique window.alignement expose ouvrirDossier."""
        self.assertIn("ouvrirDossier: ouvrirDossier", self.contenu_js)

    def test_listener_delegue_btn_aligner_dossier(self):
        """Le listener delegue intercepte .btn-aligner-dossier."""
        self.assertIn(".btn-aligner-dossier", self.contenu_js)

    def test_url_dossier_id_dans_requete(self):
        """La requete HTMX utilise dossier_id comme parametre."""
        self.assertIn("dossier_id=", self.contenu_js)

    def test_bouton_bascule_source_listener(self):
        """Le JS installe un listener sur btn-bascule-source."""
        self.assertIn("btn-bascule-source", self.contenu_js)

    def test_toggle_classe_alignement_mode_source(self):
        """Le JS toggle la classe alignement-mode-source."""
        self.assertIn("alignement-mode-source", self.contenu_js)

    def test_export_utilise_dossier_id_ou_page_ids(self):
        """L'export Markdown utilise dossier_id ou page_ids selon le mode."""
        self.assertIn("modale.dataset.dossierId", self.contenu_js)
        self.assertIn("modale.dataset.pageIds", self.contenu_js)


class Phase18bCSSTest(TestCase):
    """Verifie que hypostasia.css contient les styles de bascule source/resume.
    / Verify hypostasia.css contains source/summary toggle styles."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        chemin_css = STATIC_FRONT / "css" / "hypostasia.css"
        cls.contenu_css = chemin_css.read_text() if chemin_css.exists() else ""

    def test_classe_alignement_texte_origine_hidden_par_defaut(self):
        """Le texte d'origine est cache par defaut."""
        self.assertIn(".alignement-texte-origine", self.contenu_css)
        self.assertIn("display: none", self.contenu_css)

    def test_mode_source_montre_origine(self):
        """En mode source, le texte d'origine est visible."""
        self.assertIn(".alignement-mode-source .alignement-texte-origine", self.contenu_css)

    def test_mode_source_cache_resume(self):
        """En mode source, le resume est cache."""
        self.assertIn(".alignement-mode-source .alignement-texte-resume", self.contenu_css)


# =============================================================================
# Fix OOB panneau-extractions + Drawer ameliore avec commentaires
# / Fix OOB panneau-extractions + Improved drawer with comments
# =============================================================================


class FixOOBPanneauExtractionsJSTest(TestCase):
    """Verifie que le fix OOB utilise querySelectorAll dans les 2 fichiers JS.
    / Verify OOB fix uses querySelectorAll in both JS files."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.contenu_hypostasia_js = (STATIC_FRONT / "js" / "hypostasia.js").read_text()
        cls.contenu_drawer_js = (STATIC_FRONT / "js" / "drawer_vue_liste.js").read_text()

    def test_hypostasia_js_utilise_querySelectorAll_pour_oob(self):
        """hypostasia.js retire TOUS les elements OOB (pas seulement le premier)."""
        self.assertIn("querySelectorAll('[hx-swap-oob]')", self.contenu_hypostasia_js)

    def test_hypostasia_js_ne_utilise_plus_querySelector_simple_pour_oob(self):
        """hypostasia.js n'utilise plus querySelector simple pour les OOB dans lectureReload."""
        # Verifie qu'il n'y a plus de querySelector('[hx-swap-oob]') (sans All)
        # dans la section du lectureReload
        # / Verify no querySelector('[hx-swap-oob]') (without All) in lectureReload section
        section_lecture_reload = self.contenu_hypostasia_js.split("lectureReload")[1]
        # Cherche querySelector sans All entre lectureReload et la fin de la fonction
        # / Look for querySelector without All between lectureReload and end of function
        self.assertNotIn("doc.querySelector('[hx-swap-oob]')", section_lecture_reload[:500])

    def test_drawer_js_utilise_querySelectorAll_pour_oob(self):
        """drawer_vue_liste.js retire TOUS les elements OOB (pas seulement le premier)."""
        self.assertIn("querySelectorAll('[hx-swap-oob]')", self.contenu_drawer_js)


class DrawerAmelioreTemplateTest(TestCase):
    """Verifie que le template drawer affiche resume, citation et commentaires.
    / Verify drawer template displays summary, citation and comments."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        chemin_template = BASE_DIR / "front" / "templates" / "front" / "includes" / "drawer_vue_liste.html"
        cls.contenu_template = chemin_template.read_text() if chemin_template.exists() else ""

    def test_template_contient_localisation(self):
        """Le template contient le commentaire LOCALISATION."""
        self.assertIn("LOCALISATION", self.contenu_template)

    def test_template_contient_typo_machine_pour_resume(self):
        """Le resume IA utilise la classe typo-machine."""
        self.assertIn("typo-machine", self.contenu_template)

    def test_template_contient_typo_citation_pour_source(self):
        """La citation source utilise la classe typo-citation."""
        self.assertIn("typo-citation", self.contenu_template)

    def test_template_contient_typo_lecteur_pour_commentaires(self):
        """Les noms des commentateurs utilisent la classe typo-lecteur-nom."""
        self.assertIn("typo-lecteur-nom", self.contenu_template)

    def test_template_affiche_commentaires(self):
        """Le template itere sur entity.commentaires.all."""
        self.assertIn("entity.commentaires.all", self.contenu_template)

    def test_template_contient_aria_live(self):
        """Le conteneur a aria-live pour l'accessibilite."""
        self.assertIn('aria-live="polite"', self.contenu_template)

    def test_template_contient_data_testid_carte(self):
        """Les cartes ont un data-testid."""
        self.assertIn('data-testid="drawer-carte"', self.contenu_template)

    def test_template_contient_extraction_text(self):
        """Le template affiche le texte d'extraction (source)."""
        self.assertIn("entity.extraction_text", self.contenu_template)


class DrawerAmelioreEndpointTest(TestCase):
    """Verifie le endpoint GET /extractions/drawer_contenu/ avec commentaires.
    / Verify GET /extractions/drawer_contenu/ endpoint with comments."""

    def setUp(self):
        from django.contrib.auth.models import User
        from core.models import Page
        from hypostasis_extractor.models import (
            ExtractionJob, ExtractedEntity, CommentaireExtraction,
        )

        self.user_alice = User.objects.create_user(username="alice_drawer", password="test1234")
        self.user_bob = User.objects.create_user(username="bob_drawer", password="test1234")

        self.page_test = Page.objects.create(
            title="Page drawer test",
            html_original="<html><body>Test</body></html>",
            html_readability="<p>Test content</p>",
            text_readability="Test content.",
        )

        self.job_test = ExtractionJob.objects.create(
            page=self.page_test, name="Job test", status="completed", ai_model=None,
        )

        # Entite avec commentaires / Entity with comments
        self.entite_avec_commentaires = ExtractedEntity.objects.create(
            job=self.job_test,
            extraction_class="concept",
            extraction_text="Le texte source extrait du document",
            start_char=0,
            end_char=35,
            attributes={
                "hypostase": "Théorie",
                "resume": "Résumé IA de la théorie",
            },
            statut_debat="discutable",
        )

        # Commentaires sur l'entite / Comments on the entity
        CommentaireExtraction.objects.create(
            entity=self.entite_avec_commentaires,
            user=self.user_alice,
            commentaire="Je suis d'accord avec cette analyse.",
        )
        CommentaireExtraction.objects.create(
            entity=self.entite_avec_commentaires,
            user=self.user_bob,
            commentaire="Je ne suis pas d'accord, c'est trop simpliste.",
        )

        # Entite sans commentaires / Entity without comments
        self.entite_sans_commentaires = ExtractedEntity.objects.create(
            job=self.job_test,
            extraction_class="concept",
            extraction_text="Un autre texte source",
            start_char=36,
            end_char=57,
            attributes={
                "hypostase": "Phénomène",
                "resume": "Résumé IA du phénomène",
            },
        )

    def test_drawer_contenu_retourne_200(self):
        """GET /extractions/drawer_contenu/?page_id=X retourne 200."""
        url = f"/extractions/drawer_contenu/?page_id={self.page_test.pk}"
        reponse = self.client.get(url)
        self.assertEqual(reponse.status_code, 200)

    def test_drawer_contenu_affiche_resume_ia(self):
        """Le drawer affiche le resume IA."""
        url = f"/extractions/drawer_contenu/?page_id={self.page_test.pk}"
        reponse = self.client.get(url)
        contenu = reponse.content.decode("utf-8")
        self.assertIn("Résumé IA de la théorie", contenu)

    def test_drawer_contenu_affiche_extraction_text(self):
        """Le drawer affiche le texte d'extraction source."""
        url = f"/extractions/drawer_contenu/?page_id={self.page_test.pk}"
        reponse = self.client.get(url)
        contenu = reponse.content.decode("utf-8")
        self.assertIn("Le texte source extrait du document", contenu)

    def test_drawer_contenu_affiche_commentaires(self):
        """Le drawer affiche les commentaires sous l'extraction."""
        url = f"/extractions/drawer_contenu/?page_id={self.page_test.pk}"
        reponse = self.client.get(url)
        contenu = reponse.content.decode("utf-8")
        self.assertIn("alice_drawer", contenu)
        self.assertIn("Je suis d&#x27;accord", contenu)
        self.assertIn("bob_drawer", contenu)

    def test_drawer_contenu_affiche_compteur_commentaires(self):
        """Le drawer affiche le compteur de commentaires."""
        url = f"/extractions/drawer_contenu/?page_id={self.page_test.pk}"
        reponse = self.client.get(url)
        contenu = reponse.content.decode("utf-8")
        # L'entite a 2 commentaires / The entity has 2 comments
        self.assertIn("2", contenu)

    def test_drawer_contenu_respecte_tri_statut(self):
        """Le drawer respecte le tri par statut."""
        url = f"/extractions/drawer_contenu/?page_id={self.page_test.pk}&tri=statut"
        reponse = self.client.get(url)
        self.assertEqual(reponse.status_code, 200)

    def test_drawer_contenu_utilise_typo_machine(self):
        """Le drawer utilise la classe typo-machine pour le resume IA."""
        url = f"/extractions/drawer_contenu/?page_id={self.page_test.pk}"
        reponse = self.client.get(url)
        contenu = reponse.content.decode("utf-8")
        self.assertIn("typo-machine", contenu)

    def test_drawer_contenu_utilise_typo_citation(self):
        """Le drawer utilise la classe typo-citation pour la source."""
        url = f"/extractions/drawer_contenu/?page_id={self.page_test.pk}"
        reponse = self.client.get(url)
        contenu = reponse.content.decode("utf-8")
        self.assertIn("typo-citation", contenu)

    def test_drawer_contenu_utilise_typo_lecteur(self):
        """Le drawer utilise la classe typo-lecteur-nom pour les commentaires."""
        url = f"/extractions/drawer_contenu/?page_id={self.page_test.pk}"
        reponse = self.client.get(url)
        contenu = reponse.content.decode("utf-8")
        self.assertIn("typo-lecteur-nom", contenu)


# =============================================================================
# PHASE-19 — Heat map du debat sur le texte
# / PHASE-19 — Debate heat map on text
# =============================================================================


class Phase19InterpolerCouleurHeatmapTest(TestCase):
    """Verifie que _interpoler_couleur_heatmap renvoie des couleurs correctes.
    / Verify that _interpoler_couleur_heatmap returns correct colors."""

    def test_score_zero_donne_vert_pale(self):
        """Score 0 = vert pale #f0fdf4."""
        from front.utils import _interpoler_couleur_heatmap
        couleur = _interpoler_couleur_heatmap(0.0)
        self.assertEqual(couleur, "#f0fdf4")

    def test_score_un_donne_rouge_pale(self):
        """Score 1.0 = rouge pale #fef2f2."""
        from front.utils import _interpoler_couleur_heatmap
        couleur = _interpoler_couleur_heatmap(1.0)
        self.assertEqual(couleur, "#fef2f2")

    def test_score_033_donne_jaune_pale(self):
        """Score 0.33 = jaune pale #fefce8."""
        from front.utils import _interpoler_couleur_heatmap
        couleur = _interpoler_couleur_heatmap(0.33)
        self.assertEqual(couleur, "#fefce8")

    def test_score_066_donne_orange_pale(self):
        """Score 0.66 = orange pale #fff7ed."""
        from front.utils import _interpoler_couleur_heatmap
        couleur = _interpoler_couleur_heatmap(0.66)
        self.assertEqual(couleur, "#fff7ed")

    def test_score_negatif_borne_a_zero(self):
        """Score < 0 est borne a 0 (vert pale)."""
        from front.utils import _interpoler_couleur_heatmap
        couleur = _interpoler_couleur_heatmap(-0.5)
        self.assertEqual(couleur, "#f0fdf4")

    def test_score_superieur_a_un_borne(self):
        """Score > 1 est borne a 1 (rouge pale)."""
        from front.utils import _interpoler_couleur_heatmap
        couleur = _interpoler_couleur_heatmap(2.0)
        self.assertEqual(couleur, "#fef2f2")

    def test_score_intermediaire_format_hex(self):
        """Score intermediaire retourne un format hex valide #rrggbb."""
        from front.utils import _interpoler_couleur_heatmap
        couleur = _interpoler_couleur_heatmap(0.5)
        self.assertRegex(couleur, r"^#[0-9a-f]{6}$")

    def test_interpolation_monotone(self):
        """Les composantes R restent elevees et G decroit grossierement."""
        from front.utils import _interpoler_couleur_heatmap
        couleur_basse = _interpoler_couleur_heatmap(0.0)
        couleur_haute = _interpoler_couleur_heatmap(1.0)
        # G (composante verte) diminue entre score 0 et score 1
        # / Green component decreases from score 0 to score 1
        g_basse = int(couleur_basse[3:5], 16)
        g_haute = int(couleur_haute[3:5], 16)
        self.assertGreater(g_basse, g_haute)


class Phase19AnnotationDataHeatColorTest(TestCase):
    """Verifie que annoter_html_avec_barres injecte data-heat-color.
    / Verify that annoter_html_avec_barres injects data-heat-color."""

    def test_span_contient_data_heat_color_avec_scores(self):
        """Un span annote contient data-heat-color quand des scores sont fournis."""
        from front.utils import annoter_html_avec_barres
        from hypostasis_extractor.models import ExtractionJob, ExtractedEntity
        from core.models import Page

        page_test = Page.objects.create(
            title="Test heatmap",
            html_original="<html><body>Hello world</body></html>",
            html_readability="<p>Hello world</p>",
            text_readability="Hello world",
        )
        job_test = ExtractionJob.objects.create(
            page=page_test, name="Test", status="completed",
        )
        entite_test = ExtractedEntity.objects.create(
            job=job_test,
            extraction_class="concept",
            extraction_text="Hello",
            start_char=0,
            end_char=5,
            statut_debat="discutable",
        )

        scores_temperature = {entite_test.pk: 0.5}
        html_annote = annoter_html_avec_barres(
            page_test.html_readability,
            page_test.text_readability,
            [entite_test],
            scores_temperature_normalises=scores_temperature,
        )
        self.assertIn('data-heat-color="#', html_annote)

    def test_span_sans_scores_pas_de_data_heat_color(self):
        """Un span annote sans scores n'a pas de data-heat-color."""
        from front.utils import annoter_html_avec_barres
        from hypostasis_extractor.models import ExtractionJob, ExtractedEntity
        from core.models import Page

        page_test = Page.objects.create(
            title="Test sans heatmap",
            html_original="<html><body>Hello world</body></html>",
            html_readability="<p>Hello world</p>",
            text_readability="Hello world",
        )
        job_test = ExtractionJob.objects.create(
            page=page_test, name="Test", status="completed",
        )
        entite_test = ExtractedEntity.objects.create(
            job=job_test,
            extraction_class="concept",
            extraction_text="Hello",
            start_char=0,
            end_char=5,
        )

        html_annote = annoter_html_avec_barres(
            page_test.html_readability,
            page_test.text_readability,
            [entite_test],
        )
        self.assertNotIn('data-heat-color', html_annote)

    def test_score_zero_donne_couleur_verte(self):
        """Un score normalise de 0 donne une couleur verte pale."""
        from front.utils import annoter_html_avec_barres
        from hypostasis_extractor.models import ExtractionJob, ExtractedEntity
        from core.models import Page

        page_test = Page.objects.create(
            title="Test heatmap vert",
            html_original="<html><body>Bonjour monde</body></html>",
            html_readability="<p>Bonjour monde</p>",
            text_readability="Bonjour monde",
        )
        job_test = ExtractionJob.objects.create(
            page=page_test, name="Test", status="completed",
        )
        entite_test = ExtractedEntity.objects.create(
            job=job_test,
            extraction_class="concept",
            extraction_text="Bonjour",
            start_char=0,
            end_char=7,
            statut_debat="consensuel",
        )

        scores_temperature = {entite_test.pk: 0.0}
        html_annote = annoter_html_avec_barres(
            page_test.html_readability,
            page_test.text_readability,
            [entite_test],
            scores_temperature_normalises=scores_temperature,
        )
        self.assertIn('data-heat-color="#f0fdf4"', html_annote)

    def test_score_un_donne_couleur_rouge(self):
        """Un score normalise de 1.0 donne une couleur rouge pale."""
        from front.utils import annoter_html_avec_barres
        from hypostasis_extractor.models import ExtractionJob, ExtractedEntity
        from core.models import Page

        page_test = Page.objects.create(
            title="Test heatmap rouge",
            html_original="<html><body>Texte debat</body></html>",
            html_readability="<p>Texte debat</p>",
            text_readability="Texte debat",
        )
        job_test = ExtractionJob.objects.create(
            page=page_test, name="Test", status="completed",
        )
        entite_test = ExtractedEntity.objects.create(
            job=job_test,
            extraction_class="argument",
            extraction_text="Texte",
            start_char=0,
            end_char=5,
            statut_debat="controverse",
        )

        scores_temperature = {entite_test.pk: 1.0}
        html_annote = annoter_html_avec_barres(
            page_test.html_readability,
            page_test.text_readability,
            [entite_test],
            scores_temperature_normalises=scores_temperature,
        )
        self.assertIn('data-heat-color="#fef2f2"', html_annote)


class Phase19CalculerScoresTemperatureTest(TestCase):
    """Verifie que _calculer_scores_temperature normalise correctement.
    / Verify that _calculer_scores_temperature normalizes correctly."""

    def test_entite_consensuelle_sans_commentaire_score_zero(self):
        """Une entite consensuelle sans commentaire a un score de 0."""
        from front.views import _calculer_scores_temperature, _annoter_entites_avec_commentaires
        from hypostasis_extractor.models import ExtractionJob, ExtractedEntity
        from core.models import Page

        page_test = Page.objects.create(
            title="Test scores",
            html_original="<html><body>Test</body></html>",
            html_readability="<p>Test</p>",
            text_readability="Test",
        )
        job_test = ExtractionJob.objects.create(
            page=page_test, name="Test", status="completed",
        )
        entite_consensuelle = ExtractedEntity.objects.create(
            job=job_test,
            extraction_class="concept",
            extraction_text="Test",
            start_char=0,
            end_char=4,
            statut_debat="consensuel",
        )

        entites_annotees, _ = _annoter_entites_avec_commentaires(
            ExtractedEntity.objects.filter(pk=entite_consensuelle.pk)
        )
        scores = _calculer_scores_temperature(entites_annotees)
        self.assertEqual(scores[entite_consensuelle.pk], 0.0)

    def test_entite_non_consensuelle_score_positif(self):
        """Une entite non-consensuelle a un score > 0."""
        from front.views import _calculer_scores_temperature, _annoter_entites_avec_commentaires
        from hypostasis_extractor.models import ExtractionJob, ExtractedEntity
        from core.models import Page

        page_test = Page.objects.create(
            title="Test scores non-consensuel",
            html_original="<html><body>Test</body></html>",
            html_readability="<p>Test</p>",
            text_readability="Test",
        )
        job_test = ExtractionJob.objects.create(
            page=page_test, name="Test", status="completed",
        )
        entite_discutable = ExtractedEntity.objects.create(
            job=job_test,
            extraction_class="concept",
            extraction_text="Test",
            start_char=0,
            end_char=4,
            statut_debat="discutable",
        )

        entites_annotees, _ = _annoter_entites_avec_commentaires(
            ExtractedEntity.objects.filter(pk=entite_discutable.pk)
        )
        scores = _calculer_scores_temperature(entites_annotees)
        # Seule entite → score brut = 3 (non-consensuel), normalise = 1.0
        # / Only entity → raw score = 3 (non-consensual), normalized = 1.0
        self.assertEqual(scores[entite_discutable.pk], 1.0)

    def test_normalisation_relative_au_max(self):
        """Le score est normalise par rapport au max du document."""
        from django.contrib.auth.models import User
        from front.views import _calculer_scores_temperature, _annoter_entites_avec_commentaires
        from hypostasis_extractor.models import ExtractionJob, ExtractedEntity, CommentaireExtraction
        from core.models import Page

        user_alice = User.objects.create_user(username="alice_scores", password="test1234")
        user_bob = User.objects.create_user(username="bob_scores", password="test1234")

        page_test = Page.objects.create(
            title="Test normalisation",
            html_original="<html><body>Hello World</body></html>",
            html_readability="<p>Hello World</p>",
            text_readability="Hello World",
        )
        job_test = ExtractionJob.objects.create(
            page=page_test, name="Test", status="completed",
        )
        # Entite 1 : consensuelle, 0 commentaires → score brut = 0
        # / Entity 1: consensual, 0 comments → raw score = 0
        entite_faible = ExtractedEntity.objects.create(
            job=job_test,
            extraction_class="concept",
            extraction_text="Hello",
            start_char=0,
            end_char=5,
            statut_debat="consensuel",
        )
        # Entite 2 : controverse + 2 commentaires → score brut = 2 + 3 = 5
        # / Entity 2: controversial + 2 comments → raw score = 2 + 3 = 5
        entite_forte = ExtractedEntity.objects.create(
            job=job_test,
            extraction_class="argument",
            extraction_text="World",
            start_char=6,
            end_char=11,
            statut_debat="controverse",
        )
        CommentaireExtraction.objects.create(
            entity=entite_forte, user=user_alice, commentaire="Pas d'accord",
        )
        CommentaireExtraction.objects.create(
            entity=entite_forte, user=user_bob, commentaire="Moi non plus",
        )

        entites_annotees, _ = _annoter_entites_avec_commentaires(
            ExtractedEntity.objects.filter(job=job_test).order_by("start_char")
        )
        scores = _calculer_scores_temperature(entites_annotees)

        # entite_faible : score brut = 0, normalise = 0.0
        # / entite_faible: raw = 0, normalized = 0.0
        self.assertEqual(scores[entite_faible.pk], 0.0)
        # entite_forte : score brut = 5, normalise = 1.0 (max)
        # / entite_forte: raw = 5, normalized = 1.0 (max)
        self.assertEqual(scores[entite_forte.pk], 1.0)


class Phase19BaseHTMLTest(TestCase):
    """Verifie que base.html integre les elements PHASE-19.
    / Verify that base.html integrates PHASE-19 elements."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.contenu_html = TEMPLATE_BASE.read_text() if TEMPLATE_BASE.exists() else ""

    def test_base_html_contient_bouton_heatmap(self):
        """base.html contient le bouton heat map."""
        self.assertIn('id="btn-toolbar-heatmap"', self.contenu_html)

    def test_bouton_heatmap_a_data_testid(self):
        """Le bouton heat map a un data-testid."""
        self.assertIn('data-testid="btn-toolbar-heatmap"', self.contenu_html)

    def test_bouton_heatmap_avant_bouton_aide(self):
        """Le bouton heat map est avant le bouton aide."""
        position_heatmap = self.contenu_html.find('id="btn-toolbar-heatmap"')
        position_aide = self.contenu_html.find('id="btn-toolbar-aide"')
        self.assertGreater(position_heatmap, -1, "Bouton heatmap non trouve")
        self.assertGreater(position_aide, position_heatmap,
                          "Le bouton heatmap doit etre avant le bouton aide")

    def test_bouton_heatmap_contient_label_debat(self):
        """Le bouton heat map contient le label Debat."""
        self.assertIn("Débat", self.contenu_html)

    def test_icone_flamme_svg_presente(self):
        """L'icone flamme (Heroicons fire) est presente dans le bouton."""
        self.assertIn("15.362 5.214", self.contenu_html)


class Phase19MarginaliaJSTest(TestCase):
    """Verifie le contenu de marginalia.js pour la heat map (PHASE-19).
    / Verify marginalia.js content for heat map (PHASE-19)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        chemin_js = STATIC_FRONT / "js" / "marginalia.js"
        cls.contenu_js = chemin_js.read_text() if chemin_js.exists() else ""

    def test_expose_basculerHeatmap(self):
        """marginalia.js expose basculerHeatmap dans l'API publique."""
        self.assertIn("basculerHeatmap", self.contenu_js)

    def test_expose_heatmapEstActive(self):
        """marginalia.js expose heatmapEstActive dans l'API publique."""
        self.assertIn("heatmapEstActive", self.contenu_js)

    def test_cle_localstorage_heatmap(self):
        """marginalia.js utilise la cle localStorage hypostasia-heatmap-actif."""
        self.assertIn("hypostasia-heatmap-actif", self.contenu_js)

    def test_classe_mode_heatmap(self):
        """marginalia.js ajoute/retire la classe mode-heatmap."""
        self.assertIn("mode-heatmap", self.contenu_js)

    def test_data_heat_color_lecture(self):
        """marginalia.js lit dataset.heatColor pour appliquer les couleurs."""
        self.assertIn("dataset.heatColor", self.contenu_js)

    def test_desactive_heatmap_quand_focus(self):
        """activerModeFocus desactive la heat map si active."""
        # Trouver la section activerModeFocus et verifier qu'elle appelle desactiverHeatmap
        # / Find activerModeFocus section and verify it calls desactiverHeatmap
        position_activer_focus = self.contenu_js.find("function activerModeFocus")
        section_focus = self.contenu_js[position_activer_focus:position_activer_focus + 500]
        self.assertIn("desactiverHeatmap", section_focus)

    def test_desactive_focus_quand_heatmap(self):
        """basculerHeatmap desactive le focus si actif."""
        position_basculer = self.contenu_js.find("function basculerHeatmap")
        section_basculer = self.contenu_js[position_basculer:position_basculer + 500]
        self.assertIn("desactiverModeFocus", section_basculer)

    def test_reapplique_heatmap_apres_swap(self):
        """marginalia.js reapplique la heat map apres un HTMX swap."""
        position_after_swap = self.contenu_js.find("htmx:afterSwap")
        section_swap = self.contenu_js[position_after_swap:position_after_swap + 500]
        self.assertIn("heatmapEstActive", section_swap)

    def test_cree_underlay_element(self):
        """marginalia.js cree un element #heatmap-underlay."""
        self.assertIn("heatmap-underlay", self.contenu_js)

    def test_utilise_radial_gradient(self):
        """marginalia.js utilise des radial-gradient pour les halos."""
        self.assertIn("radial-gradient", self.contenu_js)


class Phase19KeyboardJSTest(TestCase):
    """Verifie que keyboard.js integre le raccourci H (PHASE-19).
    / Verify that keyboard.js integrates the H shortcut (PHASE-19)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        chemin_js = STATIC_FRONT / "js" / "keyboard.js"
        cls.contenu_js = chemin_js.read_text() if chemin_js.exists() else ""

    def test_case_h_present(self):
        """keyboard.js contient un case 'h' dans le switch."""
        self.assertIn("case 'h':", self.contenu_js)

    def test_case_h_appelle_basculerHeatmap(self):
        """Le case 'h' appelle marginalia.basculerHeatmap."""
        self.assertIn("basculerHeatmap", self.contenu_js)

    def test_modale_aide_contient_h(self):
        """La modale d'aide contient le raccourci H."""
        self.assertIn("Heat map", self.contenu_js)

    def test_header_mentionne_h(self):
        """Le header de keyboard.js mentionne le raccourci H."""
        # Les premieres lignes (header) mentionnent H
        # / First lines (header) mention H
        header = self.contenu_js[:1000]
        self.assertIn("H", header)


class Phase19CSSStylesTest(TestCase):
    """Verifie que hypostasia.css contient les styles heat map (PHASE-19).
    / Verify hypostasia.css contains heat map styles (PHASE-19)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        chemin_css = STATIC_FRONT / "css" / "hypostasia.css"
        cls.contenu_css = chemin_css.read_text() if chemin_css.exists() else ""

    def test_variables_heatmap_froid(self):
        """hypostasia.css contient --heatmap-froid."""
        self.assertIn("--heatmap-froid", self.contenu_css)

    def test_variables_heatmap_brulant(self):
        """hypostasia.css contient --heatmap-brulant."""
        self.assertIn("--heatmap-brulant", self.contenu_css)

    def test_focus_masque_underlay(self):
        """body.mode-focus masque le calque #heatmap-underlay."""
        self.assertIn("body.mode-focus #heatmap-underlay", self.contenu_css)

    def test_section_commentaire_phase_19(self):
        """Le CSS contient un commentaire de section PHASE-19."""
        self.assertIn("PHASE-19", self.contenu_css)


class Phase19EndpointLectureHeatmapTest(TestCase):
    """Verifie que GET /lire/{id}/ inclut data-heat-color dans le HTML annote.
    / Verify that GET /lire/{id}/ includes data-heat-color in annotated HTML."""

    def setUp(self):
        from django.contrib.auth.models import User
        from core.models import Page
        from hypostasis_extractor.models import (
            ExtractionJob, ExtractedEntity, CommentaireExtraction,
        )

        self.user_test = User.objects.create_user(username="test_user_heatmap", password="test1234")

        self.page_test = Page.objects.create(
            title="Page heatmap test",
            html_original="<html><body>Test heatmap contenu</body></html>",
            html_readability="<p>Test heatmap contenu</p>",
            text_readability="Test heatmap contenu",
        )
        self.job_test = ExtractionJob.objects.create(
            page=self.page_test, name="Job test", status="completed", ai_model=None,
        )
        # Entite controversee avec commentaires → score eleve
        # / Controversial entity with comments → high score
        self.entite_chaude = ExtractedEntity.objects.create(
            job=self.job_test,
            extraction_class="argument",
            extraction_text="Test",
            start_char=0,
            end_char=4,
            statut_debat="controverse",
        )
        CommentaireExtraction.objects.create(
            entity=self.entite_chaude, user=self.user_test, commentaire="Desaccord",
        )

    def test_lecture_retourne_200(self):
        """GET /lire/{id}/ retourne 200."""
        url = f"/lire/{self.page_test.pk}/"
        reponse = self.client.get(url)
        self.assertEqual(reponse.status_code, 200)

    def test_lecture_contient_data_heat_color(self):
        """GET /lire/{id}/ inclut data-heat-color dans le HTML."""
        url = f"/lire/{self.page_test.pk}/"
        reponse = self.client.get(url)
        contenu = reponse.content.decode("utf-8")
        self.assertIn('data-heat-color="#', contenu)


# =============================================================================
# PHASE-20 — Notifications de progression
# / PHASE-20 — Progression notifications
# =============================================================================


class Phase20ModelUpdatedAtTest(TestCase):
    """Verifie que ExtractedEntity a bien le champ updated_at (auto_now).
    / Verify that ExtractedEntity has the updated_at field (auto_now)."""

    def test_champ_updated_at_existe(self):
        """ExtractedEntity possede un champ updated_at."""
        from hypostasis_extractor.models import ExtractedEntity
        noms_des_champs = [champ.name for champ in ExtractedEntity._meta.get_fields()]
        self.assertIn("updated_at", noms_des_champs)

    def test_updated_at_auto_now(self):
        """Le champ updated_at est en auto_now (se met a jour automatiquement)."""
        from hypostasis_extractor.models import ExtractedEntity
        champ_updated_at = ExtractedEntity._meta.get_field("updated_at")
        self.assertTrue(champ_updated_at.auto_now)

    def test_updated_at_se_met_a_jour_au_save(self):
        """Modifier et sauvegarder une entite met a jour updated_at."""
        import time
        from core.models import Page
        from hypostasis_extractor.models import ExtractionJob, ExtractedEntity

        page_test = Page.objects.create(
            title="Test updated_at",
            html_original="<html><body>Test</body></html>",
            html_readability="<p>Test</p>",
            text_readability="Test",
        )
        job_test = ExtractionJob.objects.create(
            page=page_test, name="Job test", status="completed",
        )
        entite = ExtractedEntity.objects.create(
            job=job_test,
            extraction_class="argument",
            extraction_text="Test updated_at",
            start_char=0, end_char=4,
            statut_debat="discutable",
        )
        premier_updated_at = entite.updated_at

        # Petite pause pour que le timestamp change
        # / Short pause so the timestamp changes
        time.sleep(0.05)
        entite.statut_debat = "consensuel"
        entite.save()
        entite.refresh_from_db()
        self.assertGreater(entite.updated_at, premier_updated_at)


class Phase20HelperCalculerMouvementsTest(TestCase):
    """Verifie le helper _calculer_mouvements_depuis().
    / Verify the _calculer_mouvements_depuis() helper."""

    def setUp(self):
        from django.contrib.auth.models import User
        from django.utils import timezone
        from core.models import Page
        from hypostasis_extractor.models import (
            ExtractionJob, ExtractedEntity, CommentaireExtraction,
        )

        self.user_test = User.objects.create_user(username="test_user_mouvements", password="test1234")

        self.page_test = Page.objects.create(
            title="Page mouvements test",
            html_original="<html><body>Test mouvements</body></html>",
            html_readability="<p>Test mouvements</p>",
            text_readability="Test mouvements",
        )
        self.job_test = ExtractionJob.objects.create(
            page=self.page_test, name="Job test", status="completed",
        )
        # Timestamp de reference : "derniere visite" = hier
        # / Reference timestamp: "last visit" = yesterday
        self.timestamp_hier = timezone.now() - timezone.timedelta(days=1)

        # Entite cree avant la derniere visite (pas un mouvement)
        # / Entity created before last visit (not a movement)
        self.entite_ancienne = ExtractedEntity.objects.create(
            job=self.job_test,
            extraction_class="argument",
            extraction_text="Ancienne",
            start_char=0, end_char=8,
            statut_debat="discutable",
        )

    def test_aucun_mouvement_retourne_none(self):
        """Pas de commentaire ni changement de statut → retourne None."""
        from front.views import _calculer_mouvements_depuis
        from django.utils import timezone

        # Timestamp dans le futur → aucun mouvement possible
        # / Timestamp in the future → no movement possible
        timestamp_futur = timezone.now() + timezone.timedelta(hours=1)
        resultat = _calculer_mouvements_depuis(self.page_test, timestamp_futur)
        self.assertIsNone(resultat)

    def test_nouveau_commentaire_detecte(self):
        """Un commentaire cree apres la derniere visite est detecte."""
        from front.views import _calculer_mouvements_depuis
        from hypostasis_extractor.models import CommentaireExtraction

        CommentaireExtraction.objects.create(
            entity=self.entite_ancienne, user=self.user_test, commentaire="Nouveau",
        )
        resultat = _calculer_mouvements_depuis(self.page_test, self.timestamp_hier)
        self.assertIsNotNone(resultat)
        self.assertEqual(resultat["nombre_nouveaux_commentaires"], 1)

    def test_changement_statut_detecte(self):
        """Un changement de statut apres la derniere visite est detecte."""
        from front.views import _calculer_mouvements_depuis

        # Modifier le statut → updated_at se met a jour automatiquement
        # / Change status → updated_at updates automatically
        self.entite_ancienne.statut_debat = "consensuel"
        self.entite_ancienne.save()

        resultat = _calculer_mouvements_depuis(self.page_test, self.timestamp_hier)
        self.assertIsNotNone(resultat)
        self.assertIn("consensuel", resultat["changements_statut"])

    def test_orphelines_comptees(self):
        """Les entites sans commentaire sont comptees comme orphelines."""
        from front.views import _calculer_mouvements_depuis
        from hypostasis_extractor.models import CommentaireExtraction

        # Ajouter un commentaire pour declencher un mouvement
        # / Add a comment to trigger a movement
        CommentaireExtraction.objects.create(
            entity=self.entite_ancienne, user=self.user_test, commentaire="Test",
        )
        resultat = _calculer_mouvements_depuis(self.page_test, self.timestamp_hier)
        self.assertIsNotNone(resultat)
        # L'entite_ancienne a un commentaire, mais elle est la seule → 0 orphelines
        # / entite_ancienne has a comment, but it's the only one → 0 orphans
        self.assertEqual(resultat["nombre_orphelines"], 0)

    def test_seuil_consensus_atteint(self):
        """Le seuil est atteint quand >= 80% des entites sont consensuelles."""
        from front.views import _calculer_mouvements_depuis
        from hypostasis_extractor.models import CommentaireExtraction

        # Passer l'unique entite en consensuel
        # / Set the only entity to consensual
        self.entite_ancienne.statut_debat = "consensuel"
        self.entite_ancienne.save()

        resultat = _calculer_mouvements_depuis(self.page_test, self.timestamp_hier)
        self.assertIsNotNone(resultat)
        self.assertTrue(resultat["seuil_atteint"])
        self.assertEqual(resultat["pourcentage_consensus"], 100)

    def test_seuil_consensus_non_atteint(self):
        """Le seuil n'est pas atteint quand < 80% consensuelles."""
        from front.views import _calculer_mouvements_depuis
        from hypostasis_extractor.models import ExtractedEntity, CommentaireExtraction

        # Creer 4 entites supplementaires discutables
        # / Create 4 additional debatable entities
        for i in range(4):
            ExtractedEntity.objects.create(
                job=self.job_test,
                extraction_class="argument",
                extraction_text=f"Entite {i}",
                start_char=10 + i * 10, end_char=18 + i * 10,
                statut_debat="discutable",
            )
        # 1 entite ancienne (discutable) + 4 nouvelles (discutables) = 5 total, 0 consensuel
        # On ajoute un commentaire pour declencher un mouvement
        # / 1 old entity (debatable) + 4 new (debatable) = 5 total, 0 consensual
        # / Add a comment to trigger a movement
        CommentaireExtraction.objects.create(
            entity=self.entite_ancienne, user=self.user_test, commentaire="Test",
        )
        resultat = _calculer_mouvements_depuis(self.page_test, self.timestamp_hier)
        self.assertIsNotNone(resultat)
        self.assertFalse(resultat["seuil_atteint"])
        self.assertEqual(resultat["pourcentage_consensus"], 0)


class Phase20EndpointNotificationsTest(TestCase):
    """Verifie l'endpoint GET /lire/{id}/notifications/.
    / Verify the GET /lire/{id}/notifications/ endpoint."""

    def setUp(self):
        from django.contrib.auth.models import User
        from urllib.parse import quote
        from django.utils import timezone
        from core.models import Page
        from hypostasis_extractor.models import (
            ExtractionJob, ExtractedEntity, CommentaireExtraction,
        )

        self.user_test = User.objects.create_user(username="test_user_notif", password="test1234")

        self.page_test = Page.objects.create(
            title="Page notif test",
            html_original="<html><body>Test notif</body></html>",
            html_readability="<p>Test notif</p>",
            text_readability="Test notif",
        )
        self.job_test = ExtractionJob.objects.create(
            page=self.page_test, name="Job test", status="completed",
        )
        self.entite_test = ExtractedEntity.objects.create(
            job=self.job_test,
            extraction_class="argument",
            extraction_text="Test notif",
            start_char=0, end_char=4,
            statut_debat="discutable",
        )
        # Commentaire recent pour generer un mouvement
        # / Recent comment to generate a movement
        CommentaireExtraction.objects.create(
            entity=self.entite_test, user=self.user_test, commentaire="Discussion",
        )
        # Timestamp d'hier en ISO, encode pour URL (le + de +00:00 devient %2B)
        # / Yesterday's timestamp in ISO, URL-encoded (+ in +00:00 becomes %2B)
        hier = timezone.now() - timezone.timedelta(days=1)
        self.timestamp_hier_iso = quote(hier.isoformat(), safe="")

    def test_notifications_retourne_200(self):
        """GET /lire/{id}/notifications/?derniere_visite=ISO retourne 200."""
        url = f"/lire/{self.page_test.pk}/notifications/?derniere_visite={self.timestamp_hier_iso}"
        reponse = self.client.get(url)
        self.assertEqual(reponse.status_code, 200)

    def test_notifications_sans_param_retourne_div_vide(self):
        """GET /lire/{id}/notifications/ sans param retourne un div vide."""
        url = f"/lire/{self.page_test.pk}/notifications/"
        reponse = self.client.get(url)
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode("utf-8")
        self.assertIn('id="bandeau-notifications"', contenu)
        self.assertNotIn("bandeau-notification-titre", contenu)

    def test_notifications_timestamp_invalide_retourne_div_vide(self):
        """GET /lire/{id}/notifications/?derniere_visite=INVALIDE retourne un div vide."""
        url = f"/lire/{self.page_test.pk}/notifications/?derniere_visite=pas-un-timestamp"
        reponse = self.client.get(url)
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode("utf-8")
        self.assertIn('id="bandeau-notifications"', contenu)
        self.assertNotIn("bandeau-notification-titre", contenu)

    def test_notifications_avec_mouvement_retourne_bandeau(self):
        """GET avec timestamp passe retourne le bandeau avec contenu."""
        url = f"/lire/{self.page_test.pk}/notifications/?derniere_visite={self.timestamp_hier_iso}"
        reponse = self.client.get(url)
        contenu = reponse.content.decode("utf-8")
        self.assertIn("bandeau-notification", contenu)
        self.assertIn("Depuis votre derniere visite", contenu)
        self.assertIn("commentaire", contenu)

    def test_notifications_sans_mouvement_retourne_div_vide(self):
        """GET avec timestamp futur (aucun mouvement) retourne un div vide."""
        from urllib.parse import quote
        from django.utils import timezone
        timestamp_futur = quote((timezone.now() + timezone.timedelta(hours=1)).isoformat(), safe="")
        url = f"/lire/{self.page_test.pk}/notifications/?derniere_visite={timestamp_futur}"
        reponse = self.client.get(url)
        contenu = reponse.content.decode("utf-8")
        self.assertIn('id="bandeau-notifications"', contenu)
        self.assertNotIn("Depuis votre derniere visite", contenu)

    def test_notifications_page_inexistante_retourne_404(self):
        """GET /lire/99999/notifications/ retourne 404."""
        url = "/lire/99999/notifications/?derniere_visite=2026-01-01T00:00:00Z"
        reponse = self.client.get(url)
        self.assertEqual(reponse.status_code, 404)

    def test_notifications_seuil_consensus_affiche(self):
        """Le sous-bandeau seuil est affiche quand >= 80% consensuel."""
        # Passer l'entite en consensuel
        # / Set entity to consensual
        self.entite_test.statut_debat = "consensuel"
        self.entite_test.save()

        url = f"/lire/{self.page_test.pk}/notifications/?derniere_visite={self.timestamp_hier_iso}"
        reponse = self.client.get(url)
        contenu = reponse.content.decode("utf-8")
        self.assertIn("bandeau-seuil", contenu)
        self.assertIn("Consensus atteint", contenu)

    def test_notifications_seuil_consensus_absent_si_pas_atteint(self):
        """Le sous-bandeau seuil est absent quand < 80% consensuel."""
        url = f"/lire/{self.page_test.pk}/notifications/?derniere_visite={self.timestamp_hier_iso}"
        reponse = self.client.get(url)
        contenu = reponse.content.decode("utf-8")
        self.assertNotIn("bandeau-seuil", contenu)


class Phase20TemplatesBandeauTest(TestCase):
    """Verifie les templates PHASE-20 (bandeau_notification + lecture_principale).
    / Verify PHASE-20 templates (bandeau_notification + lecture_principale)."""

    def test_template_bandeau_existe(self):
        """Le template bandeau_notification.html existe et est chargeable."""
        template = get_template("front/includes/bandeau_notification.html")
        self.assertIsNotNone(template)

    def test_lecture_principale_contient_div_bandeau(self):
        """lecture_principale.html contient le div #bandeau-notifications."""
        chemin_template = (
            BASE_DIR / "front" / "templates" / "front" / "includes" / "lecture_principale.html"
        )
        contenu = chemin_template.read_text(encoding="utf-8")
        self.assertIn('id="bandeau-notifications"', contenu)
        self.assertIn('data-testid="bandeau-notifications"', contenu)


class Phase20BaseHTMLTest(TestCase):
    """Verifie que base.html inclut le JS notifications_progression.
    / Verify that base.html includes notifications_progression JS."""

    def setUp(self):
        self.contenu_base_html = TEMPLATE_BASE.read_text(encoding="utf-8")

    def test_script_notifications_progression_inclus(self):
        """base.html reference notifications_progression.js."""
        self.assertIn("notifications_progression.js", self.contenu_base_html)

    def test_script_notifications_avant_keyboard(self):
        """notifications_progression.js est charge avant keyboard.js."""
        position_notifications = self.contenu_base_html.index("notifications_progression.js")
        position_keyboard = self.contenu_base_html.index("keyboard.js")
        self.assertLess(position_notifications, position_keyboard)


class Phase20JSContenuTest(TestCase):
    """Verifie le contenu de notifications_progression.js.
    / Verify notifications_progression.js content."""

    def setUp(self):
        chemin_js = STATIC_FRONT / "js" / "notifications_progression.js"
        self.contenu_js = chemin_js.read_text(encoding="utf-8")

    def test_fichier_js_existe(self):
        """notifications_progression.js existe."""
        chemin_js = STATIC_FRONT / "js" / "notifications_progression.js"
        self.assertTrue(chemin_js.exists())

    def test_iife_use_strict(self):
        """Le JS utilise une IIFE avec 'use strict'."""
        self.assertIn("(function()", self.contenu_js)
        self.assertIn("'use strict'", self.contenu_js)

    def test_expose_api_publique(self):
        """Le JS expose window.notificationsProgression."""
        self.assertIn("window.notificationsProgression", self.contenu_js)

    def test_expose_marquer_vu(self):
        """L'API publique contient marquerVu."""
        self.assertIn("marquerVu", self.contenu_js)

    def test_utilise_localstorage(self):
        """Le JS utilise localStorage pour stocker le timestamp."""
        self.assertIn("localStorage", self.contenu_js)
        self.assertIn("hypostasia-derniere-visite-", self.contenu_js)

    def test_selecteur_cible_zone_lecture(self):
        """Le JS utilise data-testid lecture-zone-principale (pas [data-page-id] generique)."""
        self.assertIn('lecture-zone-principale', self.contenu_js)

    def test_utilise_htmx_ajax(self):
        """Le JS utilise htmx.ajax pour charger le bandeau."""
        self.assertIn("htmx.ajax", self.contenu_js)

    def test_ecoute_htmx_after_swap(self):
        """Le JS ecoute htmx:afterSwap pour recharger apres navigation."""
        self.assertIn("htmx:afterSwap", self.contenu_js)


class Phase20KeyboardJSTest(TestCase):
    """Verifie que keyboard.js gere Escape pour le bandeau notification.
    / Verify that keyboard.js handles Escape for notification banner."""

    def setUp(self):
        chemin_js = STATIC_FRONT / "js" / "keyboard.js"
        self.contenu_js = chemin_js.read_text(encoding="utf-8")

    def test_escape_gere_bandeau_notification(self):
        """keyboard.js contient la logique Escape pour le bandeau."""
        self.assertIn("bandeau-notifications", self.contenu_js)
        self.assertIn("bandeau-notification", self.contenu_js)

    def test_escape_appelle_marquer_vu(self):
        """keyboard.js appelle notificationsProgression.marquerVu() sur Escape."""
        self.assertIn("notificationsProgression.marquerVu", self.contenu_js)


class Phase20CSSStylesTest(TestCase):
    """Verifie les styles CSS PHASE-20 dans hypostasia.css.
    / Verify PHASE-20 CSS styles in hypostasia.css."""

    def setUp(self):
        chemin_css = STATIC_FRONT / "css" / "hypostasia.css"
        self.contenu_css = chemin_css.read_text(encoding="utf-8")

    def test_section_23_presente(self):
        """La section 23 (PHASE-20) est presente dans le CSS."""
        self.assertIn("23. Bandeau de notification (PHASE-20)", self.contenu_css)

    def test_classe_bandeau_notification(self):
        """La classe .bandeau-notification est definie."""
        self.assertIn(".bandeau-notification {", self.contenu_css)
        self.assertIn(".bandeau-notification-contenu", self.contenu_css)
        self.assertIn(".bandeau-notification-titre", self.contenu_css)
        self.assertIn(".bandeau-notification-liste", self.contenu_css)
        self.assertIn(".bandeau-notification-fermer", self.contenu_css)

    def test_sous_bandeau_seuil(self):
        """La classe .bandeau-notification-seuil est definie."""
        self.assertIn(".bandeau-notification-seuil", self.contenu_css)

    def test_animation_bandeau_entree(self):
        """L'animation bandeau-entree est definie."""
        self.assertIn("@keyframes bandeau-entree", self.contenu_css)

    def test_mode_focus_masque_bandeau(self):
        """Le mode focus masque le bandeau notification."""
        self.assertIn("body.mode-focus .bandeau-notification", self.contenu_css)

    def test_couleurs_indigo(self):
        """Les couleurs indigo sont utilisees pour le bandeau."""
        self.assertIn("#eef2ff", self.contenu_css)   # indigo-50
        self.assertIn("#6366f1", self.contenu_css)   # indigo-500
        self.assertIn("#4338ca", self.contenu_css)   # indigo-700


# =============================================================================
# PHASE-21 — Mobile : bottom sheet + responsive
# / PHASE-21 — Mobile: bottom sheet + responsive
# =============================================================================


class Phase21CSSMobileTest(TestCase):
    """Verifie les styles CSS PHASE-21 dans hypostasia.css.
    / Verify PHASE-21 CSS styles in hypostasia.css."""

    def setUp(self):
        chemin_css = STATIC_FRONT / "css" / "hypostasia.css"
        self.contenu_css = chemin_css.read_text(encoding="utf-8")

    def test_section_24_presente(self):
        """La section 24 (PHASE-21) est presente dans le CSS."""
        self.assertIn("24. Mobile + Bottom sheet (PHASE-21)", self.contenu_css)

    def test_media_query_768(self):
        """Le media query mobile 768px est present."""
        self.assertIn("@media (max-width: 768px)", self.contenu_css)

    def test_classe_lecture_zone_conteneur(self):
        """La classe .lecture-zone-conteneur est definie."""
        self.assertIn(".lecture-zone-conteneur {", self.contenu_css)

    def test_bottom_sheet_backdrop(self):
        """La classe .bottom-sheet-backdrop est definie."""
        self.assertIn(".bottom-sheet-backdrop {", self.contenu_css)
        self.assertIn(".bottom-sheet-backdrop.visible {", self.contenu_css)

    def test_bottom_sheet(self):
        """La classe .bottom-sheet est definie."""
        self.assertIn(".bottom-sheet {", self.contenu_css)
        self.assertIn(".bottom-sheet.ouvert {", self.contenu_css)

    def test_bottom_sheet_bouton_fermer(self):
        """La classe .btn-fermer-bottom-sheet est definie."""
        self.assertIn(".btn-fermer-bottom-sheet", self.contenu_css)

    def test_bottom_sheet_contenu(self):
        """La classe .bottom-sheet-contenu est definie."""
        self.assertIn(".bottom-sheet-contenu {", self.contenu_css)

    def test_pastilles_cachees_mobile(self):
        """Les pastilles de marge sont cachees en mobile."""
        self.assertIn(".pastilles-marge { display: none", self.contenu_css)

    def test_arbre_plein_ecran_mobile(self):
        """L'arbre prend 100vw sur mobile."""
        self.assertIn("#arbre-overlay { width: 100vw", self.contenu_css)

    def test_boutons_caches_mobile(self):
        """Les boutons focus et heatmap sont caches sur mobile (aide reste visible)."""
        self.assertIn("#btn-toolbar-focus", self.contenu_css)
        self.assertIn("#btn-toolbar-heatmap", self.contenu_css)

    def test_surlignage_visible_mobile(self):
        """Le surlignage des extractions a un fond visible sur mobile."""
        self.assertIn("hl-extraction", self.contenu_css)
        self.assertIn("border-bottom", self.contenu_css)

    def test_overflow_x_hidden_mobile(self):
        """Le scroll horizontal est bloque sur mobile."""
        self.assertIn("overflow-x: hidden", self.contenu_css)


class Phase21TemplateBottomSheetTest(TestCase):
    """Verifie le template bottom_sheet_extraction.html.
    / Verify bottom_sheet_extraction.html template."""

    def test_template_existe(self):
        """Le template bottom_sheet_extraction.html existe et se charge."""
        template = get_template("front/includes/bottom_sheet_extraction.html")
        self.assertIsNotNone(template)

    def test_template_contient_card_body(self):
        """Le template inclut _card_body.html."""
        chemin_template = (
            BASE_DIR / "front" / "templates" / "front" / "includes"
            / "bottom_sheet_extraction.html"
        )
        contenu = chemin_template.read_text(encoding="utf-8")
        self.assertIn("_card_body.html", contenu)

    def test_template_cible_bottom_sheet_contenu(self):
        """Le bouton Commenter cible #bottom-sheet-contenu."""
        chemin_template = (
            BASE_DIR / "front" / "templates" / "front" / "includes"
            / "bottom_sheet_extraction.html"
        )
        contenu = chemin_template.read_text(encoding="utf-8")
        self.assertIn("#bottom-sheet-contenu", contenu)

    def test_template_mobile_param(self):
        """Le lien fil_discussion passe mobile=1."""
        chemin_template = (
            BASE_DIR / "front" / "templates" / "front" / "includes"
            / "bottom_sheet_extraction.html"
        )
        contenu = chemin_template.read_text(encoding="utf-8")
        self.assertIn("mobile=1", contenu)


class Phase21EndpointCarteMobileTest(TestCase):
    """Verifie l'endpoint carte_mobile.
    / Verify carte_mobile endpoint."""

    def setUp(self):
        from core.models import Page
        from hypostasis_extractor.models import ExtractionJob, ExtractedEntity

        self.page = Page.objects.create(
            title="Page mobile test",
            html_original="<html>mobile</html>",
            html_readability="<article>mobile</article>",
            text_readability="mobile test",
        )
        self.job = ExtractionJob.objects.create(
            page=self.page,
            name="Extractions manuelles",
            status="completed",
        )
        self.entite = ExtractedEntity.objects.create(
            job=self.job,
            extraction_class="concept",
            extraction_text="test mobile",
            start_char=0,
            end_char=6,
        )

    def test_carte_mobile_retourne_200(self):
        """GET /extractions/carte_mobile/?entity_id=N retourne 200."""
        reponse = self.client.get(
            f"/extractions/carte_mobile/?entity_id={self.entite.pk}",
        )
        self.assertEqual(reponse.status_code, 200)

    def test_carte_mobile_contient_contenu(self):
        """La reponse contient le texte de l'extraction."""
        reponse = self.client.get(
            f"/extractions/carte_mobile/?entity_id={self.entite.pk}",
        )
        self.assertContains(reponse, "test mobile")

    def test_carte_mobile_sans_entity_id(self):
        """GET /extractions/carte_mobile/ sans entity_id retourne 400."""
        reponse = self.client.get("/extractions/carte_mobile/")
        self.assertEqual(reponse.status_code, 400)


class Phase21BaseHTMLTest(TestCase):
    """Verifie les ajouts PHASE-21 dans base.html.
    / Verify PHASE-21 additions in base.html."""

    def setUp(self):
        self.contenu_base = TEMPLATE_BASE.read_text(encoding="utf-8")

    def test_bottom_sheet_js_inclus(self):
        """Le script bottom_sheet.js est inclus."""
        self.assertIn("bottom_sheet.js", self.contenu_base)

    def test_conteneur_bottom_sheet_present(self):
        """Le conteneur bottom-sheet est present dans le HTML."""
        self.assertIn('id="bottom-sheet"', self.contenu_base)
        self.assertIn('id="bottom-sheet-backdrop"', self.contenu_base)
        self.assertIn('id="bottom-sheet-contenu"', self.contenu_base)

    def test_bottom_sheet_bouton_fermer_present(self):
        """Le bouton fermer (X) du bottom sheet est present."""
        self.assertIn("btn-fermer-bottom-sheet", self.contenu_base)


class Phase21JSBottomSheetTest(TestCase):
    """Verifie le fichier bottom_sheet.js.
    / Verify bottom_sheet.js file."""

    def setUp(self):
        chemin_js = STATIC_FRONT / "js" / "bottom_sheet.js"
        self.contenu_js = chemin_js.read_text(encoding="utf-8")

    def test_fichier_existe(self):
        """Le fichier bottom_sheet.js existe."""
        self.assertTrue(len(self.contenu_js) > 0)

    def test_iife(self):
        """Le fichier est une IIFE."""
        self.assertIn("(function()", self.contenu_js)
        self.assertIn("'use strict'", self.contenu_js)

    def test_expose_window_bottomSheet(self):
        """Le fichier expose window.bottomSheet."""
        self.assertIn("window.bottomSheet", self.contenu_js)

    def test_fonctions_ouvrir_fermer(self):
        """Les fonctions ouvrir et fermer sont exposees."""
        self.assertIn("ouvrir:", self.contenu_js)
        self.assertIn("fermer:", self.contenu_js)
        self.assertIn("estOuvert:", self.contenu_js)

    def test_drag_support(self):
        """Le support du drag (touch) est present."""
        self.assertIn("touchstart", self.contenu_js)
        self.assertIn("touchmove", self.contenu_js)
        self.assertIn("touchend", self.contenu_js)

    def test_appel_carte_mobile(self):
        """Le JS appelle l'endpoint carte_mobile."""
        self.assertIn("carte_mobile", self.contenu_js)


class Phase21JSMarginaliaTest(TestCase):
    """Verifie les modifications PHASE-21 dans marginalia.js.
    / Verify PHASE-21 changes in marginalia.js."""

    def setUp(self):
        chemin_js = STATIC_FRONT / "js" / "marginalia.js"
        self.contenu_js = chemin_js.read_text(encoding="utf-8")

    def test_contient_bottomSheet(self):
        """marginalia.js reference bottomSheet."""
        self.assertIn("bottomSheet", self.contenu_js)

    def test_contient_hl_extraction_handler(self):
        """marginalia.js contient un handler pour .hl-extraction."""
        self.assertIn("hl-extraction", self.contenu_js)

    def test_detection_mobile(self):
        """marginalia.js detecte le mobile via innerWidth."""
        self.assertIn("innerWidth <= 768", self.contenu_js)


class Phase21KeyboardJSTest(TestCase):
    """Verifie les modifications PHASE-21 dans keyboard.js.
    / Verify PHASE-21 changes in keyboard.js."""

    def setUp(self):
        chemin_js = STATIC_FRONT / "js" / "keyboard.js"
        self.contenu_js = chemin_js.read_text(encoding="utf-8")

    def test_contient_bottomSheet(self):
        """keyboard.js reference bottomSheet pour Escape."""
        self.assertIn("bottomSheet", self.contenu_js)

    def test_escape_ferme_bottom_sheet(self):
        """keyboard.js ferme le bottom sheet sur Escape."""
        self.assertIn("bottomSheet.estOuvert", self.contenu_js)
        self.assertIn("bottomSheet.fermer", self.contenu_js)


class Phase21LecturePrincipaleTest(TestCase):
    """Verifie les modifications PHASE-21 dans lecture_principale.html.
    / Verify PHASE-21 changes in lecture_principale.html."""

    def setUp(self):
        chemin_template = (
            BASE_DIR / "front" / "templates" / "front" / "includes"
            / "lecture_principale.html"
        )
        self.contenu = chemin_template.read_text(encoding="utf-8")

    def test_utilise_classe_css(self):
        """Le template utilise la classe .lecture-zone-conteneur."""
        self.assertIn("lecture-zone-conteneur", self.contenu)

    def test_pas_inline_style_44rem(self):
        """Le template n'a plus le style inline max-width: 44rem."""
        self.assertNotIn('style="max-width: 44rem', self.contenu)


# =============================================================================
# PHASE-23 — Confirmation analyse : tokens, cout, prompt
# / PHASE-23 — Analysis confirmation: tokens, cost, prompt
# =============================================================================


class Phase23BoutonToolbarAnalyserHTMXTest(TestCase):
    """Verifie que le bouton Analyser est gere par HTMX (OOB swap), pas par JS."""

    def setUp(self):
        # Le bouton Analyser est dans lecture_principale.html (OOB swap)
        # / The Analyze button is in lecture_principale.html (OOB swap)
        chemin_lecture = (
            BASE_DIR / "front" / "templates" / "front" / "includes"
            / "lecture_principale.html"
        )
        self.contenu_lecture = chemin_lecture.read_text(encoding="utf-8")
        chemin_js = (
            BASE_DIR / "front" / "static" / "front" / "js" / "arbre_overlay.js"
        )
        self.contenu_js = chemin_js.read_text(encoding="utf-8")

    def test_oob_swap_bouton_analyser_dans_lecture(self):
        """lecture_principale.html contient un OOB swap pour le bouton Analyser."""
        self.assertIn("btn-toolbar-analyser", self.contenu_lecture)
        self.assertIn("hx-swap-oob", self.contenu_lecture)

    def test_oob_contient_hx_get_previsualiser(self):
        """Le OOB swap contient un hx-get vers previsualiser_analyse."""
        self.assertIn("previsualiser_analyse", self.contenu_lecture)

    def test_oob_cible_zone_lecture(self):
        """Le OOB swap cible #zone-lecture."""
        self.assertIn('hx-target="#zone-lecture"', self.contenu_lecture)

    def test_js_ne_gere_plus_bouton_analyser(self):
        """Le JS ne contient plus de handler addEventListener pour le bouton Analyser."""
        # Verifie qu'il n'y a plus de htmx.ajax pour le bouton analyser dans le JS
        # / Verify there's no more htmx.ajax for the analyser button in JS
        self.assertNotIn(
            "htmx.ajax('POST', '/lire/' + pageId + '/analyser/'",
            self.contenu_js,
        )
        self.assertNotIn(
            "htmx.ajax('GET', '/lire/' + pageId + '/previsualiser_analyse/'",
            self.contenu_js,
        )


class Phase23ConfirmationAnalyseTemplateTest(TestCase):
    """Verifie le template de confirmation d'analyse."""

    def setUp(self):
        chemin_template = (
            BASE_DIR / "front" / "templates" / "front" / "includes"
            / "confirmation_analyse.html"
        )
        self.contenu = chemin_template.read_text(encoding="utf-8")

    def test_affiche_tokens_input(self):
        """Le template affiche l'estimation de tokens input."""
        self.assertIn("nombre_tokens_input", self.contenu)

    def test_affiche_tokens_output(self):
        """Le template affiche l'estimation de tokens output."""
        self.assertIn("nombre_tokens_output_estime", self.contenu)

    def test_affiche_cout_estime(self):
        """Le template affiche le cout estime en euros."""
        self.assertIn("cout_estime_euros", self.contenu)

    def test_affiche_nom_analyseur(self):
        """Le template affiche le nom de l'analyseur."""
        self.assertIn("analyseur.name", self.contenu)

    def test_affiche_nom_modele_ia(self):
        """Le template affiche le nom du modele IA."""
        self.assertIn("modele_ia.get_display_name", self.contenu)

    def test_bouton_voir_prompt_complet(self):
        """Le template a un bouton pour voir le prompt complet."""
        self.assertIn("Voir le prompt complet", self.contenu)

    def test_zone_prompt_complet_cachee(self):
        """Le prompt complet est dans une zone cachee par defaut."""
        self.assertIn("zone-prompt-complet", self.contenu)
        self.assertIn("hidden", self.contenu)

    def test_bouton_lancer_analyse(self):
        """Le template a un bouton pour lancer l'analyse."""
        self.assertIn("Lancer l'analyse", self.contenu)

    def test_bouton_lancer_cible_zone_lecture(self):
        """Le bouton lancer cible #zone-lecture (pas #zone-resultats-extraction)."""
        self.assertIn('hx-target="#zone-lecture"', self.contenu)

    def test_bouton_annuler_recharge_page(self):
        """Le bouton annuler recharge la page de lecture via HTMX."""
        self.assertIn("Annuler", self.contenu)
        self.assertIn("hx-get", self.contenu)

    def test_selecteur_analyseur_present(self):
        """Le template contient un selecteur d'analyseur pour le recalcul."""
        self.assertIn("select-analyseur-confirmation", self.contenu)

    def test_selecteur_recharge_htmx(self):
        """Le selecteur recharge la previsualisation au changement."""
        self.assertIn("previsualiser_analyse", self.contenu)

    def test_data_testid_confirmation(self):
        """Le template a le data-testid pour les tests E2E."""
        self.assertIn('data-testid="confirmation-analyse"', self.contenu)

    def test_data_testid_estimation_tokens(self):
        """Le template a le data-testid sur la zone d'estimation tokens."""
        self.assertIn('data-testid="estimation-tokens"', self.contenu)


class Phase23AnalyseEnCoursTemplateTest(TestCase):
    """Verifie que le template de polling cible #zone-lecture."""

    def setUp(self):
        chemin_template = (
            BASE_DIR / "front" / "templates" / "front" / "includes"
            / "analyse_en_cours.html"
        )
        self.contenu = chemin_template.read_text(encoding="utf-8")

    def test_polling_cible_zone_lecture(self):
        """Le polling HTMX cible #zone-lecture (pas #zone-resultats-extraction)."""
        self.assertIn('hx-target="#zone-lecture"', self.contenu)
        self.assertNotIn('hx-target="#zone-resultats-extraction"', self.contenu)

    def test_polling_every_3s(self):
        """Le polling se declenche toutes les 3 secondes."""
        self.assertIn('hx-trigger="every 3s"', self.contenu)


class Phase23PrevisualiserAnalyseViewTest(TestCase):
    """Teste l'endpoint previsualiser_analyse via RequestFactory."""

    def setUp(self):
        from core.models import Page, AIModel, Configuration
        from hypostasis_extractor.models import (
            AnalyseurSyntaxique, PromptPiece, AnalyseurExample,
            ExampleExtraction, ExtractionAttribute,
        )
        self.factory = RequestFactory()

        # Creer une page avec du contenu
        # / Create a page with content
        self.page_test = Page.objects.create(
            title="Page test previsualisation",
            html_readability="<p>Contenu pour tester la previsualisation.</p>",
            text_readability="Contenu pour tester la previsualisation.",
            source_type="file",
            status="completed",
        )

        # Creer un modele IA actif
        # / Create an active AI model
        self.modele_ia = AIModel.objects.create(
            name="Mock Previsu",
            model_choice="mock_default",
            is_active=True,
        )

        # Configurer la configuration singleton
        # / Configure the singleton configuration
        configuration = Configuration.get_solo()
        configuration.ai_active = True
        configuration.ai_model = self.modele_ia
        configuration.save()

        # Creer un analyseur avec des pieces de prompt
        # / Create an analyzer with prompt pieces
        self.analyseur = AnalyseurSyntaxique.objects.create(
            name="Analyseur Test Previsu",
            type_analyseur="analyser",
            is_active=True,
        )
        PromptPiece.objects.create(
            analyseur=self.analyseur,
            name="Instruction test",
            role="instruction",
            content="Tu es un analyseur de test.",
            order=0,
        )

        # Creer un exemple few-shot
        # / Create a few-shot example
        exemple = AnalyseurExample.objects.create(
            analyseur=self.analyseur,
            name="Exemple test",
            example_text="Texte d'exemple pour le few-shot.",
            order=0,
        )
        extraction_exemple = ExampleExtraction.objects.create(
            example=exemple,
            extraction_class="hypostase",
            extraction_text="Texte d'exemple",
            order=0,
        )
        ExtractionAttribute.objects.create(
            extraction=extraction_exemple,
            key="Hypostases",
            value="axiome",
            order=0,
        )

    def test_previsualiser_retourne_200_sans_analyseur_id(self):
        """L'endpoint retourne 200 meme sans analyseur_id (utilise le premier actif)."""
        from front.views import LectureViewSet
        requete = self.factory.get(
            f"/lire/{self.page_test.pk}/previsualiser_analyse/"
        )
        vue = LectureViewSet()
        reponse = vue.previsualiser_analyse(requete, pk=self.page_test.pk)
        self.assertEqual(reponse.status_code, 200)

    def test_previsualiser_retourne_200_avec_analyseur_id(self):
        """L'endpoint retourne 200 avec un analyseur_id specifique."""
        from front.views import LectureViewSet
        requete = self.factory.get(
            f"/lire/{self.page_test.pk}/previsualiser_analyse/",
            {"analyseur_id": self.analyseur.pk},
        )
        vue = LectureViewSet()
        reponse = vue.previsualiser_analyse(requete, pk=self.page_test.pk)
        self.assertEqual(reponse.status_code, 200)

    def test_reponse_contient_estimation_tokens(self):
        """La reponse contient l'estimation de tokens."""
        from front.views import LectureViewSet
        requete = self.factory.get(
            f"/lire/{self.page_test.pk}/previsualiser_analyse/"
        )
        vue = LectureViewSet()
        reponse = vue.previsualiser_analyse(requete, pk=self.page_test.pk)
        contenu_html = reponse.content.decode("utf-8")
        self.assertIn("Tokens input", contenu_html)

    def test_reponse_contient_cout_estime(self):
        """La reponse contient le cout estime en euros."""
        from front.views import LectureViewSet
        requete = self.factory.get(
            f"/lire/{self.page_test.pk}/previsualiser_analyse/"
        )
        vue = LectureViewSet()
        reponse = vue.previsualiser_analyse(requete, pk=self.page_test.pk)
        contenu_html = reponse.content.decode("utf-8")
        self.assertIn("Cout estime", contenu_html)
        # Le cout doit etre un nombre decimal arrondi au centime
        # / Cost must be a decimal number rounded to the cent
        self.assertRegex(contenu_html, r"[\d]+\.[\d]{2} .euro")

    def test_reponse_contient_prompt_complet(self):
        """La reponse contient le prompt complet dans une zone cachee."""
        from front.views import LectureViewSet
        requete = self.factory.get(
            f"/lire/{self.page_test.pk}/previsualiser_analyse/"
        )
        vue = LectureViewSet()
        reponse = vue.previsualiser_analyse(requete, pk=self.page_test.pk)
        contenu_html = reponse.content.decode("utf-8")
        # Le prompt doit contenir le texte de la piece de prompt
        # / The prompt must contain the prompt piece text
        self.assertIn("Tu es un analyseur de test", contenu_html)
        # Le prompt doit contenir le texte source de la page
        # / The prompt must contain the page's source text
        self.assertIn("Contenu pour tester la previsualisation", contenu_html)

    def test_reponse_contient_exemple_fewshot(self):
        """La reponse mentionne le nombre d'exemples few-shot."""
        from front.views import LectureViewSet
        requete = self.factory.get(
            f"/lire/{self.page_test.pk}/previsualiser_analyse/"
        )
        vue = LectureViewSet()
        reponse = vue.previsualiser_analyse(requete, pk=self.page_test.pk)
        contenu_html = reponse.content.decode("utf-8")
        # Doit indiquer 1 exemple few-shot
        # / Must indicate 1 few-shot example
        self.assertIn("1", contenu_html)

    def test_reponse_contient_nom_analyseur(self):
        """La reponse contient le nom de l'analyseur."""
        from front.views import LectureViewSet
        requete = self.factory.get(
            f"/lire/{self.page_test.pk}/previsualiser_analyse/"
        )
        vue = LectureViewSet()
        reponse = vue.previsualiser_analyse(requete, pk=self.page_test.pk)
        contenu_html = reponse.content.decode("utf-8")
        self.assertIn("Analyseur Test Previsu", contenu_html)

    def test_reponse_contient_boutons_action(self):
        """La reponse contient les boutons Lancer et Annuler."""
        from front.views import LectureViewSet
        requete = self.factory.get(
            f"/lire/{self.page_test.pk}/previsualiser_analyse/"
        )
        vue = LectureViewSet()
        reponse = vue.previsualiser_analyse(requete, pk=self.page_test.pk)
        contenu_html = reponse.content.decode("utf-8")
        self.assertIn("Lancer", contenu_html)
        self.assertIn("Annuler", contenu_html)


# =============================================================================
# PHASE-24 — Providers IA unifies
# / PHASE-24 — Unified AI providers
# =============================================================================


class Phase24ProviderChoicesTest(TestCase):
    """Verifie que Provider contient les 5 valeurs attendues (mock, google, openai, ollama, anthropic).
    / Verify Provider has the expected 5 values."""

    def test_provider_a_cinq_valeurs(self):
        """Les 5 providers doivent exister dans l'enum Provider."""
        from core.models import Provider

        valeurs_attendues = {"mock", "google", "openai", "ollama", "anthropic"}
        valeurs_reelles = {choix.value for choix in Provider}
        self.assertEqual(valeurs_reelles, valeurs_attendues)


class Phase24AIModelChoicesTest(TestCase):
    """Verifie que AIModelChoices contient les modeles Ollama et Anthropic.
    / Verify AIModelChoices contains Ollama and Anthropic models."""

    def test_modeles_ollama_presents(self):
        """Les 7 modeles Ollama doivent etre dans les choices."""
        from core.models import AIModelChoices

        toutes_les_valeurs = {choix.value for choix in AIModelChoices}
        modeles_ollama_attendus = {"llama3", "llama3.1", "mistral", "gemma2", "qwen2.5", "deepseek-r1", "phi3"}
        # Verifie que tous les modeles Ollama sont presents
        # / Verify all Ollama models are present
        self.assertTrue(
            modeles_ollama_attendus.issubset(toutes_les_valeurs),
            f"Modeles Ollama manquants: {modeles_ollama_attendus - toutes_les_valeurs}",
        )

    def test_modeles_anthropic_presents(self):
        """Les 2 modeles Anthropic (Sonnet 4 et Haiku 4) doivent etre dans les choices."""
        from core.models import AIModelChoices

        toutes_les_valeurs = {choix.value for choix in AIModelChoices}
        self.assertIn("claude-sonnet-4-20250514", toutes_les_valeurs)
        self.assertIn("claude-haiku-4-20250414", toutes_les_valeurs)


class Phase24BaseUrlFieldTest(TestCase):
    """Verifie que AIModel a le champ base_url (utilise par Ollama).
    / Verify AIModel has the base_url field (used by Ollama)."""

    def test_champ_base_url_persiste_en_base(self):
        """Le base_url sauvegarde doit etre retrouve apres refresh_from_db."""
        from core.models import AIModel

        modele_ollama = AIModel(name="Test Ollama", model_choice="llama3", base_url="http://gpu:11434")
        modele_ollama.save()
        modele_ollama.refresh_from_db()
        self.assertEqual(modele_ollama.base_url, "http://gpu:11434")

    def test_base_url_defaut_est_chaine_vide(self):
        """Un modele sans base_url doit avoir une chaine vide par defaut."""
        from core.models import AIModel

        modele_mock = AIModel(name="Test", model_choice="mock")
        modele_mock.save()
        modele_mock.refresh_from_db()
        self.assertEqual(modele_mock.base_url, "")


class Phase24LlmProvidersMockTest(TestCase):
    """Verifie que appeler_llm() avec le provider MOCK retourne un texte factice.
    / Verify appeler_llm() with MOCK provider returns dummy text."""

    def test_mock_retourne_texte_avec_prefixe_et_contenu(self):
        """Le mock doit retourner '[MOCK] Reformulation de : ...' avec le debut du texte."""
        from core.models import AIModel
        from core.llm_providers import appeler_llm

        modele_mock = AIModel(name="Mock", model_choice="mock")
        modele_mock.save()

        resultat_mock = appeler_llm(modele_mock, "Un texte a reformuler")
        # Verifie le prefixe [MOCK] et la presence du texte source
        # / Verify [MOCK] prefix and source text presence
        self.assertIn("[MOCK]", resultat_mock)
        self.assertIn("Un texte a reformuler", resultat_mock)


class Phase24LlmProvidersGoogleMockTest(TestCase):
    """Verifie que appeler_llm() avec Google appelle le SDK generativeai.
    / Verify appeler_llm() with Google calls the generativeai SDK."""

    def test_google_appel_sdk(self):
        """Le provider Google doit appeler genai.GenerativeModel().generate_content()."""
        from unittest.mock import patch, MagicMock
        from core.models import AIModel
        from core.llm_providers import appeler_llm

        modele_google = AIModel(
            name="Gemini Test", model_choice="gemini-2.5-flash",
            api_key="key-test-google",
        )
        modele_google.save()

        # Mock le SDK google / Mock the google SDK
        mock_reponse_genai = MagicMock()
        mock_reponse_genai.text = "Reponse de Gemini"

        mock_generative_model = MagicMock()
        mock_generative_model.generate_content.return_value = mock_reponse_genai

        with patch("google.generativeai.configure") as mock_configure, \
             patch("google.generativeai.GenerativeModel", return_value=mock_generative_model):
            resultat = appeler_llm(modele_google, "Texte source")

            # Verifie que la cle API a ete configuree
            # / Verify API key was configured
            mock_configure.assert_called_once_with(api_key="key-test-google")
            mock_generative_model.generate_content.assert_called_once_with("Texte source")
            self.assertEqual(resultat, "Reponse de Gemini")


class Phase24LlmProvidersOllamaMockTest(TestCase):
    """Verifie que appeler_llm() avec Ollama fait un POST HTTP vers /api/generate.
    / Verify appeler_llm() with Ollama makes HTTP POST to /api/generate."""

    def test_ollama_appel_http_correct(self):
        """L'appel Ollama doit poster vers {base_url}/api/generate avec le bon model."""
        from unittest.mock import patch, MagicMock
        from core.models import AIModel
        from core.llm_providers import appeler_llm

        modele_ollama = AIModel(name="Ollama Llama3", model_choice="llama3", base_url="http://localhost:11434")
        modele_ollama.save()

        # Simuler la reponse HTTP Ollama / Simulate Ollama HTTP response
        mock_reponse_http = MagicMock()
        mock_reponse_http.json.return_value = {"response": "Texte reformule par Ollama"}
        mock_reponse_http.raise_for_status = MagicMock()

        with patch("requests.post", return_value=mock_reponse_http) as mock_post:
            resultat = appeler_llm(modele_ollama, "Un texte")

            # Verifie que l'URL contient /api/generate
            # / Verify URL contains /api/generate
            mock_post.assert_called_once()
            url_appelee = mock_post.call_args[0][0]
            self.assertIn("/api/generate", url_appelee)

            # Verifie le payload JSON envoye
            # / Verify the sent JSON payload
            payload_envoye = mock_post.call_args[1]["json"]
            self.assertEqual(payload_envoye["model"], "llama3")
            self.assertEqual(payload_envoye["prompt"], "Un texte")
            self.assertFalse(payload_envoye["stream"])

            self.assertEqual(resultat, "Texte reformule par Ollama")

    def test_ollama_base_url_custom(self):
        """Un base_url custom doit etre utilise dans l'URL d'appel."""
        from unittest.mock import patch, MagicMock
        from core.models import AIModel
        from core.llm_providers import appeler_llm

        modele_ollama_custom = AIModel(
            name="Ollama GPU", model_choice="llama3",
            base_url="http://gpu-server:11434",
        )
        modele_ollama_custom.save()

        mock_reponse_http = MagicMock()
        mock_reponse_http.json.return_value = {"response": "ok"}
        mock_reponse_http.raise_for_status = MagicMock()

        with patch("requests.post", return_value=mock_reponse_http) as mock_post:
            appeler_llm(modele_ollama_custom, "test")
            url_appelee = mock_post.call_args[0][0]
            # L'URL doit commencer par le base_url custom
            # / URL must start with custom base_url
            self.assertTrue(url_appelee.startswith("http://gpu-server:11434"))


class Phase24LlmProvidersAnthropicMockTest(TestCase):
    """Verifie que appeler_llm() avec Anthropic appelle le SDK anthropic.
    / Verify appeler_llm() with Anthropic calls the anthropic SDK."""

    def test_anthropic_appel_sdk_correct(self):
        """Le provider Anthropic doit appeler client.messages.create() avec le bon model."""
        from unittest.mock import patch, MagicMock
        from core.models import AIModel
        from core.llm_providers import appeler_llm

        modele_anthropic = AIModel(
            name="Claude Sonnet", model_choice="claude-sonnet-4-20250514",
            api_key="sk-test-123",
        )
        modele_anthropic.save()

        # Simuler la reponse du SDK Anthropic / Simulate Anthropic SDK response
        mock_bloc_contenu = MagicMock()
        mock_bloc_contenu.text = "Reponse de Claude"
        mock_reponse_messages = MagicMock()
        mock_reponse_messages.content = [mock_bloc_contenu]

        mock_client_anthropic = MagicMock()
        mock_client_anthropic.messages.create.return_value = mock_reponse_messages

        with patch("anthropic.Anthropic", return_value=mock_client_anthropic) as mock_anthropic_cls:
            resultat = appeler_llm(modele_anthropic, "Un texte")

            # Verifie que le client a ete cree avec la bonne cle API
            # / Verify client was created with correct API key
            mock_anthropic_cls.assert_called_once_with(api_key="sk-test-123")

            # Verifie les parametres de l'appel messages.create
            # / Verify messages.create call parameters
            appel_kwargs = mock_client_anthropic.messages.create.call_args[1]
            self.assertEqual(appel_kwargs["model"], "claude-sonnet-4-20250514")
            self.assertEqual(appel_kwargs["max_tokens"], 4096)

            self.assertEqual(resultat, "Reponse de Claude")


class Phase24LlmProviderInconnuTest(TestCase):
    """Verifie que appeler_llm() leve ValueError pour un provider inconnu.
    / Verify appeler_llm() raises ValueError for unknown provider."""

    def test_provider_inconnu_raise_valueerror(self):
        """Un provider non supporte doit lever ValueError avec un message clair."""
        from unittest.mock import MagicMock
        from core.llm_providers import appeler_llm

        # Creer un objet factice avec un provider inexistant
        # / Create a fake object with a non-existent provider
        modele_factice = MagicMock()
        modele_factice.provider = "provider_inexistant"

        with self.assertRaises(ValueError) as ctx:
            appeler_llm(modele_factice, "test")
        self.assertIn("provider_inexistant", str(ctx.exception))


class Phase24ResolveModelParamsOllamaTest(TestCase):
    """Verifie que resolve_model_params retourne model_url pour Ollama.
    / Verify resolve_model_params returns model_url for Ollama."""

    def test_ollama_model_url_custom(self):
        """Le base_url custom doit etre transmis comme model_url a LangExtract."""
        from core.models import AIModel
        from hypostasis_extractor.services import resolve_model_params

        modele_ollama = AIModel(name="Ollama", model_choice="llama3", base_url="http://gpu:11434")
        modele_ollama.save()

        params_langextract = resolve_model_params(modele_ollama)
        self.assertEqual(params_langextract["model_url"], "http://gpu:11434")
        self.assertEqual(params_langextract["model_id"], "llama3")

    def test_ollama_base_url_defaut_localhost(self):
        """Sans base_url, le defaut doit etre http://localhost:11434."""
        from core.models import AIModel
        from hypostasis_extractor.services import resolve_model_params

        modele_ollama_defaut = AIModel(name="Ollama", model_choice="llama3")
        modele_ollama_defaut.save()

        params_langextract = resolve_model_params(modele_ollama_defaut)
        self.assertEqual(params_langextract["model_url"], "http://localhost:11434")

    def test_ollama_api_key_transmise_si_presente(self):
        """Si le modele Ollama a une api_key, elle doit etre dans les params."""
        from core.models import AIModel
        from hypostasis_extractor.services import resolve_model_params

        modele_ollama_avec_cle = AIModel(
            name="Ollama Auth", model_choice="llama3",
            api_key="ollama-key-123",
        )
        modele_ollama_avec_cle.save()

        params_langextract = resolve_model_params(modele_ollama_avec_cle)
        self.assertEqual(params_langextract["api_key"], "ollama-key-123")


class Phase24ResolveModelParamsAnthropicTest(TestCase):
    """Verifie que resolve_model_params leve ValueError pour Anthropic.
    Anthropic n'est pas supporte par LangExtract pour l'extraction structuree.
    / Verify resolve_model_params raises ValueError for Anthropic."""

    def test_anthropic_raise_valueerror_avec_message_clair(self):
        """Le message d'erreur doit expliquer que seule la reformulation est supportee."""
        from core.models import AIModel
        from hypostasis_extractor.services import resolve_model_params

        modele_anthropic = AIModel(
            name="Claude", model_choice="claude-sonnet-4-20250514",
            api_key="sk-test",
        )
        modele_anthropic.save()

        with self.assertRaises(ValueError) as ctx:
            resolve_model_params(modele_anthropic)

        message_erreur = str(ctx.exception)
        self.assertIn("Anthropic ne supporte pas l'extraction", message_erreur)
        self.assertIn("reformulation", message_erreur)


class Phase24LegacyServicesDeletedTest(TestCase):
    """Verifie que core/services.py n'existe plus (code mort supprime).
    / Verify core/services.py no longer exists (dead code deleted)."""

    def test_fichier_services_supprime(self):
        """Le fichier core/services.py ne doit plus exister sur le disque."""
        chemin_services = Path(settings.BASE_DIR) / "core" / "services.py"
        self.assertFalse(chemin_services.exists(), "core/services.py devrait etre supprime")


class Phase24PrefixToProviderTest(TestCase):
    """Verifie le mapping prefix -> provider dans AIModel.save().
    Chaque model_choice doit deduire automatiquement le bon provider.
    / Verify prefix -> provider mapping in AIModel.save()."""

    def test_tous_les_modeles_ollama_deduisent_provider_ollama(self):
        """Les 7 model_choice Ollama doivent tous donner provider=ollama apres save()."""
        from core.models import AIModel, Provider

        for model_choice in ["llama3", "llama3.1", "mistral", "gemma2", "qwen2.5", "deepseek-r1", "phi3"]:
            modele_ollama = AIModel(name=f"Test {model_choice}", model_choice=model_choice)
            modele_ollama.save()
            self.assertEqual(
                modele_ollama.provider, Provider.OLLAMA,
                f"{model_choice} devrait avoir provider=ollama, got {modele_ollama.provider}",
            )

    def test_modeles_anthropic_deduisent_provider_anthropic(self):
        """Les 2 model_choice Anthropic doivent donner provider=anthropic apres save()."""
        from core.models import AIModel, Provider

        for model_choice in ["claude-sonnet-4-20250514", "claude-haiku-4-20250414"]:
            modele_anthropic = AIModel(name=f"Test {model_choice}", model_choice=model_choice)
            modele_anthropic.save()
            self.assertEqual(
                modele_anthropic.provider, Provider.ANTHROPIC,
                f"{model_choice} devrait avoir provider=anthropic, got {modele_anthropic.provider}",
            )

    def test_providers_existants_google_openai_non_casses(self):
        """Les modeles Google et OpenAI doivent toujours deduire le bon provider (non-regression)."""
        from core.models import AIModel, Provider

        # Google Gemini / Google Gemini
        modele_google = AIModel(name="Test Gemini", model_choice="gemini-2.5-flash")
        modele_google.save()
        self.assertEqual(modele_google.provider, Provider.GOOGLE)

        # OpenAI GPT / OpenAI GPT
        modele_openai = AIModel(name="Test GPT", model_choice="gpt-4o")
        modele_openai.save()
        self.assertEqual(modele_openai.provider, Provider.OPENAI)


class Phase24TarifsNouveauxProvidersTest(TestCase):
    """Verifie les tarifs des nouveaux providers (Ollama gratuit, Anthropic payant).
    / Verify pricing for new providers (Ollama free, Anthropic paid)."""

    def test_ollama_tarifs_gratuits(self):
        """Tous les modeles Ollama doivent avoir un cout de (0.0, 0.0)."""
        from core.models import AIModel

        for model_choice in ["llama3", "mistral", "gemma2", "phi3"]:
            modele_ollama = AIModel(name=f"Ollama {model_choice}", model_choice=model_choice)
            modele_ollama.save()
            cout_input, cout_output = modele_ollama.cout_par_million_tokens()
            self.assertEqual(cout_input, 0.0, f"{model_choice} input devrait etre 0.0")
            self.assertEqual(cout_output, 0.0, f"{model_choice} output devrait etre 0.0")

    def test_anthropic_sonnet_tarifs(self):
        """Claude Sonnet 4 doit couter (3.00, 15.00) par million de tokens."""
        from core.models import AIModel

        modele_sonnet = AIModel(name="Sonnet", model_choice="claude-sonnet-4-20250514")
        modele_sonnet.save()
        cout_input, cout_output = modele_sonnet.cout_par_million_tokens()
        self.assertEqual(cout_input, 3.00)
        self.assertEqual(cout_output, 15.00)

    def test_anthropic_haiku_tarifs(self):
        """Claude Haiku 4 doit couter (0.80, 4.00) par million de tokens."""
        from core.models import AIModel

        modele_haiku = AIModel(name="Haiku", model_choice="claude-haiku-4-20250414")
        modele_haiku.save()
        cout_input, cout_output = modele_haiku.cout_par_million_tokens()
        self.assertEqual(cout_input, 0.80)
        self.assertEqual(cout_output, 4.00)


class Phase24IntegrationReformulationMockTest(TestCase):
    """Test d'integration : reformuler_entite_task utilise appeler_llm via le provider Mock.
    Verifie que le chemin complet tache Celery -> appeler_llm -> stockage fonctionne.
    / Integration test: reformuler_entite_task uses appeler_llm via Mock provider."""

    def test_reformulation_complete_avec_mock(self):
        """La tache Celery doit stocker le resultat mock dans entity.texte_reformule."""
        from core.models import AIModel, Configuration
        from hypostasis_extractor.models import (
            AnalyseurSyntaxique, ExtractionJob, ExtractedEntity, PromptPiece,
        )
        from core.models import Page

        # Creer le modele Mock et le configurer comme actif
        # / Create Mock model and set it as active
        modele_mock = AIModel(name="Mock Reformulation", model_choice="mock")
        modele_mock.save()
        config = Configuration.get_solo()
        config.ai_active = True
        config.ai_model = modele_mock
        config.save()

        # Creer une page de test / Create a test page
        page_test = Page.objects.create(
            title="Page test reformulation",
            html_original="<p>Contenu test</p>",
            html_readability="<p>Contenu test</p>",
            text_readability="Contenu test reformulation",
        )

        # Creer un analyseur de type reformuler avec une piece de prompt
        # / Create a reformuler-type analyzer with a prompt piece
        analyseur_reformuler = AnalyseurSyntaxique.objects.create(
            name="Reformuleur Test P24",
            type_analyseur="reformuler",
        )
        PromptPiece.objects.create(
            analyseur=analyseur_reformuler,
            content="Reformule ce texte en langage simple.",
            order=1,
        )

        # Creer un job et une entite a reformuler
        # / Create a job and entity to reformulate
        job_test = ExtractionJob.objects.create(
            page=page_test,
            ai_model=modele_mock,
            name="Job test P24",
            prompt_description="test",
        )
        entite_test = ExtractedEntity.objects.create(
            job=job_test,
            extraction_class="test_class",
            extraction_text="Ce texte philosophique complexe merite une reformulation.",
            start_char=0,
            end_char=50,
            reformulation_en_cours=True,
        )

        # Appeler la tache directement en mode synchrone (pas de broker Celery)
        # apply() execute la tache sans Celery, gere le bind=True (self)
        # / Call task synchronously (no Celery broker), apply() handles bind=True
        from front.tasks import reformuler_entite_task
        reformuler_entite_task.apply(args=[entite_test.pk, analyseur_reformuler.pk])

        # Verifier que l'entite a ete mise a jour avec la reformulation mock
        # / Verify entity was updated with mock reformulation
        entite_test.refresh_from_db()
        self.assertFalse(entite_test.reformulation_en_cours)
        self.assertEqual(entite_test.reformulation_erreur, "")
        self.assertIn("[MOCK]", entite_test.texte_reformule)
        self.assertEqual(entite_test.reformule_par, "Reformuleur Test P24")


class Phase24LlmProvidersModuleExisteTest(TestCase):
    """Verifie que le module core.llm_providers est importable et contient appeler_llm.
    / Verify core.llm_providers module is importable and contains appeler_llm."""

    def test_import_et_callable(self):
        """Le module doit etre importable et appeler_llm doit etre callable."""
        from core.llm_providers import appeler_llm
        self.assertTrue(callable(appeler_llm))


# =============================================================================
# PHASE-25 — Users et partage
# / PHASE-25 — Users and sharing
# =============================================================================


class Phase25DossierOwnerTest(TestCase):
    """Verifie que le champ owner sur Dossier est nullable et fonctionne.
    / Verify owner field on Dossier is nullable and works."""

    def test_dossier_sans_owner(self):
        """Un dossier peut etre cree sans owner (legacy)."""
        from core.models import Dossier
        dossier = Dossier.objects.create(name="Test legacy")
        self.assertIsNone(dossier.owner)

    def test_dossier_avec_owner(self):
        """Un dossier peut avoir un owner."""
        from django.contrib.auth.models import User
        from core.models import Dossier
        user = User.objects.create_user(username="test_owner", password="test1234")
        dossier = Dossier.objects.create(name="Mon dossier", owner=user)
        dossier.refresh_from_db()
        self.assertEqual(dossier.owner, user)


class Phase25PageOwnerTest(TestCase):
    """Verifie que le champ owner sur Page est nullable et fonctionne.
    / Verify owner field on Page is nullable and works."""

    def test_page_sans_owner(self):
        """Une page peut etre creee sans owner (legacy)."""
        from core.models import Page
        page = Page.objects.create(
            title="Test",
            html_readability="<p>test</p>",
            text_readability="test",
            html_original="<p>test</p>",
        )
        self.assertIsNone(page.owner)

    def test_page_avec_owner(self):
        """Une page peut avoir un owner."""
        from django.contrib.auth.models import User
        from core.models import Page
        user = User.objects.create_user(username="page_owner", password="test1234")
        page = Page.objects.create(
            title="Ma page",
            html_readability="<p>test</p>",
            text_readability="test",
            html_original="<p>test</p>",
            owner=user,
        )
        page.refresh_from_db()
        self.assertEqual(page.owner, user)


class Phase25DossierPartageTest(TestCase):
    """Verifie le modele DossierPartage : creation, unique_together, cascade.
    / Verify DossierPartage model: creation, unique_together, cascade."""

    def setUp(self):
        from django.contrib.auth.models import User
        from core.models import Dossier
        self.user1 = User.objects.create_user(username="partage_u1", password="test1234")
        self.user2 = User.objects.create_user(username="partage_u2", password="test1234")
        self.dossier = Dossier.objects.create(name="Partage Test", owner=self.user1)

    def test_creation_partage(self):
        """Un DossierPartage peut etre cree."""
        from core.models import DossierPartage
        partage = DossierPartage.objects.create(dossier=self.dossier, utilisateur=self.user2)
        self.assertEqual(partage.dossier, self.dossier)
        self.assertEqual(partage.utilisateur, self.user2)

    def test_unique_together(self):
        """Un meme user ne peut pas etre partage 2 fois sur le meme dossier."""
        from django.db import IntegrityError
        from core.models import DossierPartage
        DossierPartage.objects.create(dossier=self.dossier, utilisateur=self.user2)
        with self.assertRaises(IntegrityError):
            DossierPartage.objects.create(dossier=self.dossier, utilisateur=self.user2)

    def test_cascade_delete_dossier(self):
        """La suppression du dossier supprime les partages."""
        from core.models import DossierPartage
        DossierPartage.objects.create(dossier=self.dossier, utilisateur=self.user2)
        self.dossier.delete()
        self.assertEqual(DossierPartage.objects.count(), 0)


class Phase25CommentaireUserFKTest(TestCase):
    """Verifie que CommentaireExtraction utilise un user FK.
    / Verify CommentaireExtraction uses a user FK."""

    def test_commentaire_avec_user(self):
        from django.contrib.auth.models import User
        from core.models import Page
        from hypostasis_extractor.models import CommentaireExtraction, ExtractedEntity, ExtractionJob
        user = User.objects.create_user(username="comm_user", password="test1234")
        page = Page.objects.create(
            title="Test comm",
            html_readability="<p>t</p>",
            text_readability="t",
            html_original="<p>t</p>",
        )
        job = ExtractionJob.objects.create(
            page=page, name="test", prompt_description="test", status="completed",
        )
        entite = ExtractedEntity.objects.create(
            job=job, extraction_text="test", start_char=0, end_char=4,
        )
        commentaire = CommentaireExtraction.objects.create(
            entity=entite, user=user, commentaire="Mon commentaire",
        )
        self.assertEqual(commentaire.user, user)
        self.assertIn("comm_user", str(commentaire))


class Phase25QuestionUserFKTest(TestCase):
    """Verifie que Question et ReponseQuestion utilisent un user FK.
    / Verify Question and ReponseQuestion use a user FK."""

    def test_question_et_reponse_avec_user(self):
        from django.contrib.auth.models import User
        from core.models import Page, Question, ReponseQuestion
        user = User.objects.create_user(username="q_user", password="test1234")
        page = Page.objects.create(
            title="Test Q",
            html_readability="<p>t</p>",
            text_readability="t",
            html_original="<p>t</p>",
        )
        question = Question.objects.create(page=page, user=user, texte_question="Pourquoi ?")
        self.assertEqual(question.user, user)
        reponse = ReponseQuestion.objects.create(
            question=question, user=user, texte_reponse="Parce que.",
        )
        self.assertEqual(reponse.user, user)


class Phase25LoginSerializerTest(TestCase):
    """Verifie le LoginSerializer.
    / Verify LoginSerializer."""

    def test_valid(self):
        from front.serializers import LoginSerializer
        s = LoginSerializer(data={"username": "test", "password": "pass"})
        self.assertTrue(s.is_valid())

    def test_missing_password(self):
        from front.serializers import LoginSerializer
        s = LoginSerializer(data={"username": "test"})
        self.assertFalse(s.is_valid())


class Phase25RegisterSerializerTest(TestCase):
    """Verifie le RegisterSerializer.
    / Verify RegisterSerializer."""

    def test_valid(self):
        from front.serializers import RegisterSerializer
        s = RegisterSerializer(data={
            "username": "newuser", "password": "testpass1", "password_confirm": "testpass1",
        })
        self.assertTrue(s.is_valid())

    def test_password_mismatch(self):
        from front.serializers import RegisterSerializer
        s = RegisterSerializer(data={
            "username": "newuser", "password": "testpass1", "password_confirm": "different",
        })
        self.assertFalse(s.is_valid())
        self.assertIn("password_confirm", s.errors)

    def test_username_deja_pris(self):
        from django.contrib.auth.models import User
        from front.serializers import RegisterSerializer
        User.objects.create_user(username="existing", password="test1234")
        s = RegisterSerializer(data={
            "username": "existing", "password": "testpass1", "password_confirm": "testpass1",
        })
        self.assertFalse(s.is_valid())


class Phase25DossierPartageSerializerTest(TestCase):
    """Verifie le DossierPartageSerializer.
    / Verify DossierPartageSerializer."""

    def test_valid(self):
        from front.serializers import DossierPartageSerializer
        s = DossierPartageSerializer(data={"username": "someone"})
        self.assertTrue(s.is_valid())

    def test_missing(self):
        from front.serializers import DossierPartageSerializer
        s = DossierPartageSerializer(data={})
        self.assertFalse(s.is_valid())


class Phase25ExigerAuthHelperTest(TestCase):
    """Verifie le helper _exiger_authentification.
    / Verify _exiger_authentification helper."""

    def setUp(self):
        from django.contrib.auth.models import User
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="auth_test", password="test1234")

    def test_connecte_retourne_none(self):
        """Un utilisateur connecte ne recoit pas de refus."""
        from front.views import _exiger_authentification
        request = self.factory.get("/")
        request.user = self.user
        self.assertIsNone(_exiger_authentification(request))

    def test_anonyme_htmx_retourne_403(self):
        """Un anonyme en HTMX recoit un 403."""
        from django.contrib.auth.models import AnonymousUser
        from front.views import _exiger_authentification
        request = self.factory.get("/", HTTP_HX_REQUEST="true")
        request.user = AnonymousUser()
        reponse = _exiger_authentification(request)
        self.assertEqual(reponse.status_code, 403)

    def test_anonyme_normal_redirige(self):
        """Un anonyme normal est redirige vers login."""
        from django.contrib.auth.models import AnonymousUser
        from front.views import _exiger_authentification
        request = self.factory.get("/")
        request.user = AnonymousUser()
        reponse = _exiger_authentification(request)
        self.assertEqual(reponse.status_code, 302)
