"""
Apres une ingestion reussie, le texte plat est une PROJECTION des elements.
/ After a successful ingestion, the flat text is a PROJECTION of the elements.

LOCALISATION : hypostasis_extractor/tests/test_texte_plat_derive_des_elements.py

L'import d'un fichier ecrivait DEUX textes concurrents : `text_readability`
par MarkItDown (conversion synchrone, avant la file), puis les
`ElementDocument` par Docling. Mesure du 17 aout 2026 : la note
« Présentation Hypostasia V3 » portait 58 524 signes de texte plat ET
189 elements — deux verites, dont les offsets n'avaient aucun rapport.

C'est plus insidieux qu'un champ vide : un lecteur du champ plat y trouve
un texte NON VIDE mais FAUX. Une note ingeree par Docling, elle, laissait
le champ a zero — d'ou les verdicts « citation introuvable » et les
ancres a `start_char = 0`.

La reponse n'est ni de garder deux textes, ni de supprimer le champ (il
porte l'empreinte de deduplication et sert de repli aux pages sans
element) : c'est d'en faire une PROJECTION DERIVEE des elements, ecrite
au moment ou l'ingestion reussit. Une seule verite, et le repli devient
juste au lieu d'etre un piege.
/ Neither two texts nor no field: the flat text becomes a derived
projection of the elements, written when ingestion succeeds.
"""

from django.test import TestCase

from core.models import ElementDocument, EtatIngestion, Page


class TextePlatDeriveDesElementsTest(TestCase):
    """Le champ plat suit les elements, il ne les concurrence plus."""

    def setUp(self):
        self.page = Page.objects.create(
            url="http://exemple.local/projection",
            title="Document importé",
            html_original="", html_readability="",
            # Le texte divergent qu'ecrivait la conversion synchrone.
            # / The divergent text the synchronous conversion wrote.
            text_readability="UN TEXTE MARKITDOWN QUI NE CORRESPOND A RIEN",
            content_hash="hash-projection",
        )
        ElementDocument.objects.create(
            page=self.page, ordre=0, label="section_header",
            texte="Titre de la première section",
            empreinte_contenu="p0",
        )
        ElementDocument.objects.create(
            page=self.page, ordre=1, label="text",
            texte="Le paragraphe que Docling a réellement produit.",
            empreinte_contenu="p1",
        )

    def _noter_la_reussite(self):
        from hypostasis_extractor.tasks_element import (
            _noter_l_etat_d_ingestion,
        )
        _noter_l_etat_d_ingestion(self.page.pk, EtatIngestion.REUSSIE)
        self.page.refresh_from_db()

    def test_le_texte_plat_porte_le_texte_des_elements(self):
        self._noter_la_reussite()

        self.assertIn(
            "Le paragraphe que Docling a réellement produit.",
            self.page.text_readability,
        )
        self.assertIn(
            "Titre de la première section", self.page.text_readability,
        )

    def test_le_texte_divergent_a_disparu(self):
        self._noter_la_reussite()

        self.assertNotIn(
            "MARKITDOWN", self.page.text_readability,
            "les deux textes coexistent encore",
        )

    def test_les_elements_sont_dans_l_ordre_du_document(self):
        self._noter_la_reussite()

        position_du_titre = self.page.text_readability.index("Titre de la")
        position_du_corps = self.page.text_readability.index("Le paragraphe")
        self.assertLess(position_du_titre, position_du_corps)

    def test_un_etat_qui_n_est_pas_la_reussite_ne_touche_pas_le_texte(self):
        # Une ingestion EN COURS ne doit pas effacer le texte de secours :
        # la note serait blanche a l'ecran pendant la conversion.
        # / An in-progress ingestion must not blank the placeholder.
        from hypostasis_extractor.tasks_element import (
            _noter_l_etat_d_ingestion,
        )
        _noter_l_etat_d_ingestion(self.page.pk, EtatIngestion.EN_COURS)
        self.page.refresh_from_db()

        self.assertIn("MARKITDOWN", self.page.text_readability)

    def test_une_page_sans_element_garde_son_texte(self):
        # Une reussite sans element ne doit pas vider le champ : ce serait
        # perdre le seul texte disponible. / Never blank a page that has
        # no element to project from.
        ElementDocument.objects.filter(page=self.page).delete()

        self._noter_la_reussite()

        self.assertIn("MARKITDOWN", self.page.text_readability)


class UnSimpleGetNeDoitPasDetruireLaProjectionTest(TestCase):
    """
    Lire une note audio ne doit pas réécrire son texte plat.
    / Reading an audio note must not rewrite its flat text.

    LOCALISATION : hypostasis_extractor/tests/test_texte_plat_derive_des_elements.py

    `LectureViewSet.retrieve` regenerait le HTML diarise ET le texte plat
    a CHAQUE lecture, pour garantir des attributs de PHASE-15 dont les
    dispositifs ont ete retires le 14 aout 2026. Sur une note a elements,
    cette regeneration ne sert plus rien — le lecteur rend les elements —
    et elle DETRUIT la projection posee a l'ingestion : un troisieme
    ecrivain concurrent, sur un GET.
    / A GET regenerated the flat text on every read, destroying the
    projection: a third concurrent writer, on a read request.
    """

    def setUp(self):
        from django.contrib.auth import get_user_model

        Utilisateur = get_user_model()
        self.proprietaire = Utilisateur.objects.create_user(
            username="lecteur_projection", password="motdepasse",
        )
        self.client.force_login(self.proprietaire)
        self.page = Page.objects.create(
            url="http://exemple.local/audio-projete",
            title="Débat enregistré", source_type="audio",
            html_original="", html_readability="",
            text_readability="", content_hash="hash-audio-projete",
            owner=self.proprietaire,
            transcription_raw={"segments": [
                {"speaker": "Laurent", "text": "Le premier tour de parole.",
                 "start": 0.0, "end": 10.0},
            ]},
        )
        ElementDocument.objects.create(
            page=self.page, ordre=0, label="text",
            texte="Le premier tour de parole.", empreinte_contenu="a0",
            provenance={"debut": 0.0, "fin": 10.0, "locuteur": "Laurent"},
        )
        from hypostasis_extractor.tasks_element import (
            _noter_l_etat_d_ingestion,
        )
        _noter_l_etat_d_ingestion(self.page.pk, EtatIngestion.REUSSIE)
        self.page.refresh_from_db()
        self.projection = self.page.text_readability

    def test_la_projection_survit_a_une_lecture(self):
        self.assertEqual(self.projection, "Le premier tour de parole.")

        self.client.get(f"/lire/{self.page.pk}/")
        self.page.refresh_from_db()

        self.assertEqual(
            self.page.text_readability, self.projection,
            "un simple GET a réécrit le texte plat",
        )
