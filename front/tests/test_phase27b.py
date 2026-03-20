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
        """Comparer une page V1 sans v2 et sans parent affiche un message."""
        reponse = self.client.get(
            f"/lire/{self.page_v1.pk}/comparer/",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode()
        self.assertIn("Pas d", contenu)

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
