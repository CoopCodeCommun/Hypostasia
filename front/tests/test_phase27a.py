"""
Tests de validation pour la PHASE-27a : tracabilite (modeles + hooks + historique).
/ Validation tests for PHASE-27a: traceability (models + hooks + history).

Lancer avec : uv run python manage.py test front.tests.test_phase27a -v2
/ Run with:    uv run python manage.py test front.tests.test_phase27a -v2
"""

from django.contrib.auth.models import User
from django.test import TestCase, RequestFactory
from django.utils import timezone

from core.models import Dossier, Page, PageEdit, SourceLink, TypeEdit, TypeLien


# =============================================================================
# Tests modele PageEdit
# / PageEdit model tests
# =============================================================================


class PageEditModelTest(TestCase):
    """Verifie le modele PageEdit et ses proprietes.
    / Verify the PageEdit model and its properties."""

    def setUp(self):
        # Creer un utilisateur et une page de test
        # / Create a test user and page
        self.utilisateur_test = User.objects.create_user(
            username="testeur", password="testpass123",
        )
        self.dossier_test = Dossier.objects.create(
            name="Dossier test", owner=self.utilisateur_test,
        )
        self.page_test = Page.objects.create(
            url="https://example.com/test",
            title="Page de test",
            dossier=self.dossier_test,
        )

    def test_creation_page_edit_titre(self):
        """PageEdit peut etre cree avec type_edit=titre."""
        edit = PageEdit.objects.create(
            page=self.page_test,
            user=self.utilisateur_test,
            type_edit=TypeEdit.TITRE,
            description="Titre changé : 'Ancien' → 'Nouveau'",
            donnees_avant={"titre": "Ancien"},
            donnees_apres={"titre": "Nouveau"},
        )
        self.assertEqual(edit.type_edit, "titre")
        self.assertEqual(edit.page, self.page_test)
        self.assertEqual(edit.user, self.utilisateur_test)
        self.assertIn("titre", edit.donnees_avant)

    def test_creation_page_edit_locuteur(self):
        """PageEdit peut etre cree avec type_edit=locuteur."""
        edit = PageEdit.objects.create(
            page=self.page_test,
            user=self.utilisateur_test,
            type_edit=TypeEdit.LOCUTEUR,
            description="Locuteur renommé : 'Speaker 1' → 'Alice'",
            donnees_avant={"locuteur": "Speaker 1", "portee": "tous"},
            donnees_apres={"locuteur": "Alice"},
        )
        self.assertEqual(edit.type_edit, "locuteur")

    def test_creation_page_edit_bloc_transcription(self):
        """PageEdit peut etre cree avec type_edit=bloc_transcription."""
        edit = PageEdit.objects.create(
            page=self.page_test,
            user=self.utilisateur_test,
            type_edit=TypeEdit.BLOC_TRANSCRIPTION,
            description="Bloc 0 modifié (Alice)",
            donnees_avant={"index": 0, "texte": "avant", "locuteur": "Alice"},
            donnees_apres={"index": 0, "texte": "après"},
        )
        self.assertEqual(edit.type_edit, "bloc_transcription")

    def test_creation_page_edit_contenu(self):
        """PageEdit peut etre cree avec type_edit=contenu."""
        edit = PageEdit.objects.create(
            page=self.page_test,
            user=self.utilisateur_test,
            type_edit=TypeEdit.CONTENU,
            description="Contenu modifié manuellement",
            donnees_avant={"contenu": "avant"},
            donnees_apres={"contenu": "après"},
        )
        self.assertEqual(edit.type_edit, "contenu")

    def test_page_edit_accepte_user_none(self):
        """PageEdit accepte user=None (edition anonyme)."""
        edit = PageEdit.objects.create(
            page=self.page_test,
            user=None,
            type_edit=TypeEdit.TITRE,
            description="Edition anonyme",
            donnees_avant={},
            donnees_apres={},
        )
        self.assertIsNone(edit.user)

    def test_ordering_par_created_at_desc(self):
        """Les PageEdits sont ordonnes par -created_at (plus recent en premier)."""
        edit_ancien = PageEdit.objects.create(
            page=self.page_test,
            type_edit=TypeEdit.TITRE,
            description="Premier",
            donnees_avant={},
            donnees_apres={},
        )
        edit_recent = PageEdit.objects.create(
            page=self.page_test,
            type_edit=TypeEdit.LOCUTEUR,
            description="Second",
            donnees_avant={},
            donnees_apres={},
        )
        tous_les_edits = list(PageEdit.objects.filter(page=self.page_test))
        self.assertEqual(tous_les_edits[0].pk, edit_recent.pk)
        self.assertEqual(tous_les_edits[1].pk, edit_ancien.pk)

    def test_str_representation(self):
        """__str__ retourne une representation lisible."""
        edit = PageEdit.objects.create(
            page=self.page_test,
            type_edit=TypeEdit.TITRE,
            description="Test",
            donnees_avant={},
            donnees_apres={},
        )
        representation = str(edit)
        self.assertIn("PageEdit", representation)
        self.assertIn("Titre", representation)


# =============================================================================
# Tests modele SourceLink
# / SourceLink model tests
# =============================================================================


class SourceLinkModelTest(TestCase):
    """Verifie le modele SourceLink et ses proprietes.
    / Verify the SourceLink model and its properties."""

    def setUp(self):
        self.utilisateur_test = User.objects.create_user(
            username="testeur_sl", password="testpass123",
        )
        self.dossier_test = Dossier.objects.create(
            name="Dossier SL", owner=self.utilisateur_test,
        )
        self.page_source = Page.objects.create(
            url="https://example.com/source",
            title="Page source",
            dossier=self.dossier_test,
        )
        self.page_cible = Page.objects.create(
            url="https://example.com/cible",
            title="Page cible",
            dossier=self.dossier_test,
        )

    def test_creation_source_link_basique(self):
        """SourceLink peut etre cree avec les champs obligatoires."""
        lien = SourceLink.objects.create(
            page_cible=self.page_cible,
            start_char_cible=0,
            end_char_cible=100,
            type_lien=TypeLien.IDENTIQUE,
        )
        self.assertEqual(lien.page_cible, self.page_cible)
        self.assertIsNone(lien.page_source)

    def test_creation_source_link_avec_page_source(self):
        """SourceLink peut etre cree avec une page source."""
        lien = SourceLink.objects.create(
            page_cible=self.page_cible,
            start_char_cible=0,
            end_char_cible=100,
            page_source=self.page_source,
            start_char_source=50,
            end_char_source=150,
            type_lien=TypeLien.MODIFIE,
            justification="Passage reformulé",
        )
        self.assertEqual(lien.page_source, self.page_source)
        self.assertEqual(lien.type_lien, "modifie")
        self.assertEqual(lien.justification, "Passage reformulé")

    def test_type_lien_choices(self):
        """Les 4 types de lien sont disponibles."""
        self.assertEqual(len(TypeLien.choices), 4)
        valeurs = [choix[0] for choix in TypeLien.choices]
        self.assertIn("identique", valeurs)
        self.assertIn("modifie", valeurs)
        self.assertIn("nouveau", valeurs)
        self.assertIn("supprime", valeurs)


# =============================================================================
# Tests hook modifier_titre → PageEdit
# / modifier_titre hook → PageEdit tests
# =============================================================================


class ModifierTitrePageEditTest(TestCase):
    """Verifie que modifier_titre cree un PageEdit.
    / Verify that modifier_titre creates a PageEdit."""

    def setUp(self):
        self.utilisateur_test = User.objects.create_user(
            username="testeur_hook", password="testpass123",
        )
        self.dossier_test = Dossier.objects.create(
            name="Dossier hook", owner=self.utilisateur_test,
        )
        self.page_test = Page.objects.create(
            url="https://example.com/hook",
            title="Titre Original",
            dossier=self.dossier_test,
            html_readability="<p>Test</p>",
            text_readability="Test",
        )

    def test_modifier_titre_cree_page_edit(self):
        """L'appel API modifier_titre cree un PageEdit de type titre."""
        self.client.login(username="testeur_hook", password="testpass123")

        # Compter les edits avant
        # / Count edits before
        nombre_edits_avant = PageEdit.objects.filter(page=self.page_test).count()

        reponse = self.client.post(
            f"/lire/{self.page_test.pk}/modifier_titre/",
            {"nouveau_titre": "Nouveau Titre"},
            HTTP_HX_REQUEST="true",
        )
        self.assertIn(reponse.status_code, [200, 302])

        # Verifier qu'un PageEdit a ete cree
        # / Verify a PageEdit was created
        nombre_edits_apres = PageEdit.objects.filter(page=self.page_test).count()
        self.assertEqual(nombre_edits_apres, nombre_edits_avant + 1)

        dernier_edit = PageEdit.objects.filter(page=self.page_test).first()
        self.assertEqual(dernier_edit.type_edit, "titre")
        self.assertEqual(dernier_edit.donnees_avant["titre"], "Titre Original")
        self.assertEqual(dernier_edit.donnees_apres["titre"], "Nouveau Titre")
        self.assertEqual(dernier_edit.user, self.utilisateur_test)

    def test_modifier_titre_description_tronquee_si_trop_longue(self):
        """La description est tronquee a 500 caracteres si le titre est tres long."""
        self.client.login(username="testeur_hook", password="testpass123")
        titre_tres_long = "A" * 300
        reponse = self.client.post(
            f"/lire/{self.page_test.pk}/modifier_titre/",
            {"nouveau_titre": titre_tres_long},
            HTTP_HX_REQUEST="true",
        )
        self.assertIn(reponse.status_code, [200, 302])
        dernier_edit = PageEdit.objects.filter(page=self.page_test).first()
        self.assertLessEqual(len(dernier_edit.description), 500)


# =============================================================================
# Tests hook renommer_locuteur → PageEdit
# / renommer_locuteur hook → PageEdit tests
# =============================================================================


class RenommerLocuteurPageEditTest(TestCase):
    """Verifie que renommer_locuteur cree un PageEdit.
    / Verify that renommer_locuteur creates a PageEdit."""

    def setUp(self):
        self.utilisateur_test = User.objects.create_user(
            username="testeur_locuteur", password="testpass123",
        )
        self.dossier_test = Dossier.objects.create(
            name="Dossier locuteur", owner=self.utilisateur_test,
        )
        # Page audio avec transcription_raw contenant des segments
        # / Audio page with transcription_raw containing segments
        self.page_audio = Page.objects.create(
            url="",
            title="Transcription test",
            dossier=self.dossier_test,
            source_type="audio",
            html_readability="<p>Speaker 1: Bonjour</p>",
            text_readability="Speaker 1: Bonjour",
            transcription_raw={
                "segments": [
                    {"speaker": "Speaker 1", "start": 0.0, "end": 2.0, "text": "Bonjour"},
                    {"speaker": "Speaker 1", "start": 2.0, "end": 4.0, "text": "Comment allez-vous"},
                    {"speaker": "Speaker 2", "start": 4.0, "end": 6.0, "text": "Tres bien merci"},
                ],
            },
        )

    def test_renommer_locuteur_cree_page_edit(self):
        """L'appel API renommer_locuteur cree un PageEdit de type locuteur."""
        self.client.login(username="testeur_locuteur", password="testpass123")

        nombre_edits_avant = PageEdit.objects.filter(page=self.page_audio).count()

        reponse = self.client.post(
            f"/lire/{self.page_audio.pk}/renommer_locuteur/",
            {
                "ancien_nom": "Speaker 1",
                "nouveau_nom": "Alice",
                "portee": "tous",
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertIn(reponse.status_code, [200, 302])

        nombre_edits_apres = PageEdit.objects.filter(page=self.page_audio).count()
        self.assertEqual(nombre_edits_apres, nombre_edits_avant + 1)

        dernier_edit = PageEdit.objects.filter(page=self.page_audio).first()
        self.assertEqual(dernier_edit.type_edit, "locuteur")
        self.assertEqual(dernier_edit.donnees_avant["locuteur"], "Speaker 1")
        self.assertEqual(dernier_edit.donnees_apres["locuteur"], "Alice")


# =============================================================================
# Tests hook editer_bloc → PageEdit
# / editer_bloc hook → PageEdit tests
# =============================================================================


class EditerBlocPageEditTest(TestCase):
    """Verifie que editer_bloc cree un PageEdit.
    / Verify that editer_bloc creates a PageEdit."""

    def setUp(self):
        self.utilisateur_test = User.objects.create_user(
            username="testeur_bloc", password="testpass123",
        )
        self.dossier_test = Dossier.objects.create(
            name="Dossier bloc", owner=self.utilisateur_test,
        )
        self.page_audio = Page.objects.create(
            url="",
            title="Transcription editer bloc",
            dossier=self.dossier_test,
            source_type="audio",
            html_readability="<p>Speaker 1: Texte original du bloc</p>",
            text_readability="Speaker 1: Texte original du bloc",
            transcription_raw={
                "segments": [
                    {"speaker": "Speaker 1", "start": 0.0, "end": 3.0, "text": "Texte original du bloc"},
                    {"speaker": "Speaker 2", "start": 3.0, "end": 6.0, "text": "Autre bloc"},
                ],
            },
        )

    def test_editer_bloc_cree_page_edit(self):
        """L'appel API editer_bloc cree un PageEdit de type bloc_transcription."""
        self.client.login(username="testeur_bloc", password="testpass123")

        nombre_edits_avant = PageEdit.objects.filter(page=self.page_audio).count()

        reponse = self.client.post(
            f"/lire/{self.page_audio.pk}/editer_bloc/",
            {
                "index_bloc": 0,
                "nouveau_texte": "Texte modifie du bloc",
            },
            HTTP_HX_REQUEST="true",
        )
        self.assertIn(reponse.status_code, [200, 302])

        nombre_edits_apres = PageEdit.objects.filter(page=self.page_audio).count()
        self.assertEqual(nombre_edits_apres, nombre_edits_avant + 1)

        dernier_edit = PageEdit.objects.filter(page=self.page_audio).first()
        self.assertEqual(dernier_edit.type_edit, "bloc_transcription")
        self.assertEqual(dernier_edit.donnees_avant["texte"], "Texte original du bloc")
        self.assertEqual(dernier_edit.donnees_apres["texte"], "Texte modifie du bloc")
        self.assertEqual(dernier_edit.donnees_avant["locuteur"], "Speaker 1")


# =============================================================================
# Tests contenu du diff dans le template historique
# / Diff content in the historique template tests
# =============================================================================


class HistoriqueContenuDiffTest(TestCase):
    """Verifie que le template historique affiche correctement le diff del/ins.
    / Verify that the historique template correctly displays del/ins diff."""

    def setUp(self):
        self.utilisateur_test = User.objects.create_user(
            username="testeur_diff", password="testpass123",
        )
        self.dossier_test = Dossier.objects.create(
            name="Dossier diff", owner=self.utilisateur_test,
        )
        self.page_test = Page.objects.create(
            url="https://example.com/diff",
            title="Page diff",
            dossier=self.dossier_test,
            html_readability="<p>Test</p>",
            text_readability="Test",
        )
        PageEdit.objects.create(
            page=self.page_test,
            user=self.utilisateur_test,
            type_edit="titre",
            description="Titre changé : 'Ancien' → 'Nouveau'",
            donnees_avant={"titre": "Ancien Titre"},
            donnees_apres={"titre": "Nouveau Titre"},
        )

    def test_diff_titre_contient_del_et_ins(self):
        """Le diff d'un titre contient les balises del et ins avec les valeurs."""
        self.client.login(username="testeur_diff", password="testpass123")
        reponse = self.client.get(
            f"/lire/{self.page_test.pk}/historique/",
            HTTP_HX_REQUEST="true",
        )
        contenu = reponse.content.decode()
        # Verifier que le del contient l'ancien titre
        # / Verify that del contains the old title
        self.assertIn("<del>Ancien Titre</del>", contenu)
        # Verifier que le ins contient le nouveau titre
        # / Verify that ins contains the new title
        self.assertIn("<ins>Nouveau Titre</ins>", contenu)


# =============================================================================
# Tests vue historique
# / Historique view tests
# =============================================================================


class HistoriqueViewTest(TestCase):
    """Verifie la vue historique.
    / Verify the historique view."""

    def setUp(self):
        self.utilisateur_test = User.objects.create_user(
            username="testeur_histo", password="testpass123",
        )
        self.dossier_test = Dossier.objects.create(
            name="Dossier histo", owner=self.utilisateur_test,
        )
        self.page_test = Page.objects.create(
            url="https://example.com/histo",
            title="Page historique",
            dossier=self.dossier_test,
            html_readability="<p>Test</p>",
            text_readability="Test",
        )
        # Creer quelques edits de test
        # / Create some test edits
        PageEdit.objects.create(
            page=self.page_test,
            user=self.utilisateur_test,
            type_edit="titre",
            description="Titre changé : 'A' → 'B'",
            donnees_avant={"titre": "A"},
            donnees_apres={"titre": "B"},
        )

    def test_historique_retourne_200_authentifie(self):
        """La vue historique retourne 200 pour un utilisateur authentifié."""
        self.client.login(username="testeur_histo", password="testpass123")
        reponse = self.client.get(
            f"/lire/{self.page_test.pk}/historique/",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 200)

    def test_historique_htmx_contient_data_testid(self):
        """La reponse HTMX contient data-testid="historique-page"."""
        self.client.login(username="testeur_histo", password="testpass123")
        reponse = self.client.get(
            f"/lire/{self.page_test.pk}/historique/",
            HTTP_HX_REQUEST="true",
        )
        contenu = reponse.content.decode()
        self.assertIn('data-testid="historique-page"', contenu)
        self.assertIn('data-testid="historique-entree"', contenu)

    def test_historique_f5_retourne_page_complete(self):
        """L'acces direct (F5) retourne la page complete base.html."""
        self.client.login(username="testeur_histo", password="testpass123")
        reponse = self.client.get(f"/lire/{self.page_test.pk}/historique/")
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode()
        # La page complete contient le shell base.html
        # / The full page contains the base.html shell
        self.assertIn("Hypostasia", contenu)
        self.assertIn('data-testid="historique-page"', contenu)

    def test_historique_vide_affiche_message(self):
        """Une page sans edits affiche le message 'Aucune edition'."""
        page_vierge = Page.objects.create(
            url="https://example.com/vierge",
            title="Vierge",
            dossier=self.dossier_test,
            html_readability="<p>Vierge</p>",
            text_readability="Vierge",
        )
        self.client.login(username="testeur_histo", password="testpass123")
        reponse = self.client.get(
            f"/lire/{page_vierge.pk}/historique/",
            HTTP_HX_REQUEST="true",
        )
        contenu = reponse.content.decode()
        self.assertIn('data-testid="historique-vide"', contenu)
