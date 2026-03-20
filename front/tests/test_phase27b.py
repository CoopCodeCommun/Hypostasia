"""
Tests de validation pour la PHASE-27b : diff side-by-side entre versions de pages.
/ Validation tests for PHASE-27b: side-by-side diff between page versions.

Lancer avec : uv run python manage.py test front.tests.test_phase27b -v2
/ Run with:    uv run python manage.py test front.tests.test_phase27b -v2
"""

from django.contrib.auth.models import User
from django.test import TestCase, RequestFactory

from core.models import Dossier, Page
from front.views import _diff_inline_mots, _diff_paragraphes
from front.views_alignement import construire_alignement_versions
from hypostasis_extractor.models import ExtractionJob, ExtractedEntity


# =============================================================================
# Tests helpers diff
# / Diff helper tests
# =============================================================================


class DiffInlineMotsTest(TestCase):
    """Tests unitaires pour _diff_inline_mots.
    / Unit tests for _diff_inline_mots."""

    def test_textes_identiques(self):
        """Deux textes identiques ne produisent ni <del> ni <ins>."""
        html_ancien, html_nouveau = _diff_inline_mots("Bonjour le monde", "Bonjour le monde")
        self.assertNotIn("<del", html_ancien)
        self.assertNotIn("<ins", html_nouveau)
        self.assertIn("Bonjour", html_ancien)

    def test_mot_modifie(self):
        """Un mot change produit <del> a gauche et <ins> a droite."""
        html_ancien, html_nouveau = _diff_inline_mots("Bonjour le monde", "Bonjour le soleil")
        self.assertIn("<del", html_ancien)
        self.assertIn("monde", html_ancien)
        self.assertIn("<ins", html_nouveau)
        self.assertIn("soleil", html_nouveau)

    def test_echappement_html(self):
        """Les caracteres HTML sont echappes pour eviter les XSS."""
        html_ancien, html_nouveau = _diff_inline_mots(
            "<script>alert('xss')</script>",
            "<b>bold</b>",
        )
        self.assertNotIn("<script>", html_ancien)
        self.assertNotIn("<b>bold</b>", html_nouveau)
        self.assertIn("&lt;script&gt;", html_ancien)


class DiffParagraphesTest(TestCase):
    """Tests unitaires pour _diff_paragraphes.
    / Unit tests for _diff_paragraphes."""

    def test_textes_identiques(self):
        """Textes identiques → toutes les operations sont 'equal'."""
        resultats = _diff_paragraphes("Premier paragraphe\n\nDeuxieme paragraphe", "Premier paragraphe\n\nDeuxieme paragraphe")
        self.assertEqual(len(resultats), 2)
        for resultat in resultats:
            self.assertEqual(resultat["operation"], "equal")

    def test_paragraphe_ajoute(self):
        """Un paragraphe ajoute produit une operation 'insert'."""
        resultats = _diff_paragraphes("Premier", "Premier\n\nNouveau paragraphe")
        operations = [r["operation"] for r in resultats]
        self.assertIn("insert", operations)

    def test_paragraphe_supprime(self):
        """Un paragraphe supprime produit une operation 'delete'."""
        resultats = _diff_paragraphes("Premier\n\nDeuxieme", "Premier")
        operations = [r["operation"] for r in resultats]
        self.assertIn("delete", operations)

    def test_paragraphe_modifie(self):
        """Un paragraphe modifie produit une operation 'replace' avec du HTML."""
        resultats = _diff_paragraphes("Le chat dort", "Le chien dort")
        operations = [r["operation"] for r in resultats]
        self.assertIn("replace", operations)
        bloc_replace = [r for r in resultats if r["operation"] == "replace"][0]
        self.assertIn("<del", bloc_replace["contenu_gauche"])
        self.assertIn("<ins", bloc_replace["contenu_droite"])

    def test_textes_vides(self):
        """Deux textes vides retournent une liste vide."""
        resultats = _diff_paragraphes("", "")
        self.assertEqual(resultats, [])

    def test_texte_ancien_vide(self):
        """Texte ancien vide → tout est 'insert'."""
        resultats = _diff_paragraphes("", "Nouveau contenu")
        self.assertEqual(len(resultats), 1)
        self.assertEqual(resultats[0]["operation"], "insert")

    def test_texte_nouveau_vide(self):
        """Texte nouveau vide → tout est 'delete'."""
        resultats = _diff_paragraphes("Ancien contenu", "")
        self.assertEqual(len(resultats), 1)
        self.assertEqual(resultats[0]["operation"], "delete")


# =============================================================================
# Tests action comparer()
# / comparer() action tests
# =============================================================================


class ComparerActionTest(TestCase):
    """Tests HTTP pour l'action comparer() du LectureViewSet.
    / HTTP tests for the LectureViewSet comparer() action."""

    def setUp(self):
        # Creer un utilisateur et se connecter
        # / Create a user and log in
        self.utilisateur_test = User.objects.create_user(
            username="testeur_diff", password="testpass123",
        )
        self.client.login(username="testeur_diff", password="testpass123")

        # Creer un dossier et deux versions de page
        # / Create a folder and two page versions
        self.dossier_test = Dossier.objects.create(
            name="Dossier diff", owner=self.utilisateur_test,
        )
        self.page_v1 = Page.objects.create(
            title="Page V1",
            text_readability="Premier paragraphe original.\n\nDeuxieme paragraphe.",
            dossier=self.dossier_test,
            version_number=1,
        )
        self.page_v2 = Page.objects.create(
            title="Page V2",
            text_readability="Premier paragraphe modifie.\n\nDeuxieme paragraphe.\n\nTroisieme paragraphe.",
            dossier=self.dossier_test,
            parent_page=self.page_v1,
            version_number=2,
        )

    def test_comparer_avec_v2_explicite(self):
        """Comparer avec ?v2=pk2 retourne le diff entre les deux versions."""
        reponse = self.client.get(
            f"/lire/{self.page_v1.pk}/comparer/?v2={self.page_v2.pk}",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode()
        self.assertIn("diff-versions-pages", contenu)
        self.assertIn("diff-colonne-gauche", contenu)

    def test_comparer_sans_v2_utilise_parent(self):
        """Comparer sans v2 sur la V2 compare avec le parent (V1)."""
        reponse = self.client.get(
            f"/lire/{self.page_v2.pk}/comparer/",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode()
        self.assertIn("diff-versions-pages", contenu)

    def test_comparer_sans_parent_affiche_message(self):
        """Comparer une page unique (sans parent ni enfant) affiche un message."""
        # Creer une page isolee sans version liee
        # / Create an isolated page with no linked version
        page_isolee = Page.objects.create(
            title="Page isolee",
            text_readability="Contenu unique.",
            dossier=self.dossier_test,
            version_number=1,
        )
        reponse = self.client.get(
            f"/lire/{page_isolee.pk}/comparer/",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode()
        self.assertIn("Pas d", contenu)

    def test_comparer_v1_sans_v2_trouve_enfant(self):
        """Comparer V1 sans v2 trouve automatiquement la V2 (enfant)."""
        reponse = self.client.get(
            f"/lire/{self.page_v1.pk}/comparer/",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode()
        self.assertIn("diff-versions-pages", contenu)

    def test_comparer_f5_page_complete(self):
        """Acces direct (F5) retourne la page complete avec le diff."""
        reponse = self.client.get(
            f"/lire/{self.page_v1.pk}/comparer/?v2={self.page_v2.pk}",
        )
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode()
        # La page complete contient le shell Hypostasia
        # / The full page contains the Hypostasia shell
        self.assertIn("Hypostasia", contenu)
        self.assertIn("diff-versions-pages", contenu)

    def test_comparer_chaines_differentes_refuse(self):
        """Comparer des pages de chaines differentes retourne une erreur 400."""
        page_autre_chaine = Page.objects.create(
            title="Page autre chaine",
            text_readability="Autre contenu.",
            dossier=self.dossier_test,
            version_number=1,
        )
        reponse = self.client.get(
            f"/lire/{self.page_v1.pk}/comparer/?v2={page_autre_chaine.pk}",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 400)


# =============================================================================
# Tests alignement des hypostases entre versions (PHASE-27b extension)
# / Version hypostase alignment tests (PHASE-27b extension)
# =============================================================================


class AlignementVersionsTest(TestCase):
    """Tests pour l'alignement des hypostases entre 2 versions.
    / Tests for hypostase alignment between 2 versions."""

    def setUp(self):
        # Creer un utilisateur et se connecter
        # / Create a user and log in
        self.utilisateur_test = User.objects.create_user(
            username="testeur_align", password="testpass123",
        )
        self.client.login(username="testeur_align", password="testpass123")

        # Creer un dossier et deux versions de page
        # / Create a folder and two page versions
        self.dossier_test = Dossier.objects.create(
            name="Dossier alignement", owner=self.utilisateur_test,
        )
        self.page_v1 = Page.objects.create(
            title="V1 Debat IA",
            text_readability="L'IA est un outil.",
            dossier=self.dossier_test,
            version_number=1,
        )
        self.page_v2 = Page.objects.create(
            title="V2 Synthese",
            text_readability="L'IA est un outil au service de l'humain.",
            dossier=self.dossier_test,
            parent_page=self.page_v1,
            version_number=2,
        )

    def _creer_extraction(self, page, hypostase, resume="Un resume", statut_debat="nouveau"):
        """Helper : cree un ExtractionJob completed + une ExtractedEntity avec l'hypostase donnee.
        / Helper: create a completed ExtractionJob + an ExtractedEntity with the given hypostase."""
        job = ExtractionJob.objects.create(
            page=page,
            status="completed",
        )
        entite = ExtractedEntity.objects.create(
            job=job,
            extraction_text="Texte source pour " + hypostase,
            attributes={"hypostase": hypostase, "resume": resume},
            statut_debat=statut_debat,
            start_char=0,
            end_char=10,
        )
        return entite

    def test_alignement_2_versions_avec_extractions(self):
        """Retourne le tableau avec les bonnes sections quand les 2 versions ont des extractions.
        / Returns the table with correct sections when both versions have extractions."""
        # V1 et V2 partagent 'hypothese', seul V1 a 'axiome'
        # / V1 and V2 share 'hypothese', only V1 has 'axiome'
        self._creer_extraction(self.page_v1, "hypothese", "Hyp v1")
        self._creer_extraction(self.page_v2, "hypothese", "Hyp v2")
        self._creer_extraction(self.page_v1, "axiome", "Axiome v1")

        resultat = construire_alignement_versions(self.page_v1, self.page_v2)

        self.assertIn('sections_tableau', resultat)
        self.assertGreater(len(resultat['sections_tableau']), 0)
        self.assertEqual(resultat['nombre_hypostases'], 2)

    def test_delta_supprime_si_hypostase_absente_v2(self):
        """Delta 'supprime' si l'hypostase est dans V1 mais pas V2.
        / Delta 'supprime' if the hypostase is in V1 but not V2."""
        self._creer_extraction(self.page_v1, "axiome", "Axiome v1 only")

        resultat = construire_alignement_versions(self.page_v1, self.page_v2)

        # Cherche la ligne 'axiome' et verifie son delta
        # / Find the 'axiome' row and check its delta
        ligne_axiome = None
        for section in resultat['sections_tableau']:
            for ligne in section['lignes']:
                if ligne['hypostase'] == 'axiome':
                    ligne_axiome = ligne
                    break
        self.assertIsNotNone(ligne_axiome)
        self.assertEqual(ligne_axiome['delta_type'], 'supprime')

    def test_delta_ajoute_si_hypostase_absente_v1(self):
        """Delta 'ajoute' si l'hypostase est dans V2 mais pas V1.
        / Delta 'ajoute' if the hypostase is in V2 but not V1."""
        self._creer_extraction(self.page_v2, "phenomene", "Pheno v2 only")

        resultat = construire_alignement_versions(self.page_v1, self.page_v2)

        ligne_phenomene = None
        for section in resultat['sections_tableau']:
            for ligne in section['lignes']:
                if ligne['hypostase'] == 'phenomene':
                    ligne_phenomene = ligne
                    break
        self.assertIsNotNone(ligne_phenomene)
        self.assertEqual(ligne_phenomene['delta_type'], 'ajoute')

    def test_sans_extraction_message_vide(self):
        """Si aucune extraction n'existe, sections_tableau est vide.
        / If no extraction exists, sections_tableau is empty."""
        resultat = construire_alignement_versions(self.page_v1, self.page_v2)

        self.assertEqual(resultat['sections_tableau'], [])
        self.assertEqual(resultat['nombre_hypostases'], 0)

    def test_comparer_hypostases_htmx_200(self):
        """L'action comparer_hypostases retourne 200 en HTMX.
        / The comparer_hypostases action returns 200 via HTMX."""
        self._creer_extraction(self.page_v1, "hypothese", "Hyp v1")

        reponse = self.client.get(
            f"/lire/{self.page_v1.pk}/comparer_hypostases/?v2={self.page_v2.pk}",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode()
        self.assertIn("alignement-versions", contenu)
