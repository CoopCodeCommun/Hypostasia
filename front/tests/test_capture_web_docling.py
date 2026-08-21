"""
U4 — la capture web nourrit le moteur ELEMENT.
/ U4 — web capture feeds the ELEMENT engine.

LOCALISATION : front/tests/test_capture_web_docling.py

Decision D2 (ordre 2) du cahier de branchement : apres l'import
fichier (BR-B), c'est au tour de la capture web (extension navigateur,
POST /api/pages/). Meme patron que BR-B :
- pour une page capturee (html_original non vide), la vue lance
  `ingerer_une_capture_web_avec_docling` en arriere-plan EN PLUS de la
  creation synchrone (double ecriture : html_readability porte
  l'affichage ANCIEN jusqu'a ce que les elements existent) ;
- la tache convertit le HTML par Docling, cree les elements, pose le
  flag ELEMENT et l'etat d'ingestion (comme la tache fichier) ;
- un echec laisse une page ANCIEN parfaitement lisible (repli
  honnete), l'etat le dit (U2) ;
- broker en panne : la creation reste un succes, sans fausse promesse.
/ Same pattern as file import: background Docling ingestion of the
captured HTML, honest fallback, ingestion state surfaced.
"""

from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (
    Dossier, ElementDocument, EtatIngestion, Page, empreinte_du_texte,
)

Utilisateur = get_user_model()


class CaptureWebRouteVersDoclingTest(TestCase):
    """POST /api/pages/ lance l'ingestion element pour une capture web."""

    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            username="capteur", password="motdepasse",
        )
        self.client.force_login(self.utilisateur)
        self.carnet = Dossier.objects.create(
            name="Carnet de capture", owner=self.utilisateur,
        )

    def _capturer(self, html_readability="<h1>Titre</h1><p>Corps.</p>",
                 html_original="<html><body><h1>Titre</h1>"
                               "<p>Corps.</p></body></html>",
                 url="https://exemple.test/article"):
        return self.client.post(
            "/api/pages/",
            {
                "url": url,
                "title": "Un article capturé",
                "html_original": html_original,
                "html_readability": html_readability,
                # LE CARNET EST OBLIGATOIRE depuis le 21 aout 2026 : le
                # serveur n'a plus de destination par defaut.
                # / The notebook is mandatory: no default destination.
                "dossier_id": self.carnet.pk,
            },
            content_type="application/json",
)

    @mock.patch(
        "hypostasis_extractor.tasks_element"
        ".ingerer_une_capture_web_avec_docling.delay"
    )
    def test_une_capture_lance_l_ingestion_et_pose_l_etat(self, delay_mock):
        reponse = self._capturer()
        self.assertEqual(reponse.status_code, 201,
        )
        page = Page.objects.get(url="https://exemple.test/article")
        # Double ecriture : l'affichage reste ANCIEN a la creation.
        # / Double write: display stays OLD at creation time.
        self.assertFalse(page.elements.exists())
        delay_mock.assert_called_once_with(page.pk,
        )
        self.assertEqual(page.ingestion_etat, EtatIngestion.EN_ATTENTE)
        # Defaut 3 (revue de cloture du 11 aout) : les deux autres
        # endroits qui posent l'etat en_attente ecrivent aussi
        # ingestion_maj_le (front/views.py:2103 et 5657). Sans cet
        # horodatage, la detection du fantome (defaut 2) ne peut jamais
        # se declencher pour une capture web, et order_by("-ingestion_maj_le")
        # la classe en tete (NULL en premier sous PostgreSQL).
        # / The other two call sites that set en_attente also stamp
        # ingestion_maj_le; without it, ghost detection can never fire
        # for a web capture, and the dropdown's ordering misplaces it.
        self.assertIsNotNone(page.ingestion_maj_le)

    @mock.patch(
        "hypostasis_extractor.tasks_element"
        ".ingerer_une_capture_web_avec_docling.delay"
    )
    def test_un_broker_en_panne_ne_promet_rien(self, delay_mock):
        delay_mock.side_effect = Exception("broker indisponible",
        )
        reponse = self._capturer()
        self.assertEqual(reponse.status_code, 201,
        )
        page = Page.objects.get(url="https://exemple.test/article")
        self.assertEqual(page.ingestion_etat, "",
        )
        self.assertFalse(page.elements.exists())

    @mock.patch(
        "hypostasis_extractor.tasks_element"
        ".ingerer_une_capture_web_avec_docling.delay"
    )
    def test_une_capture_sans_html_original_ne_lance_rien(self, delay_mock):
        # Le serializer exige html_original : une capture en est
        # toujours pourvue. Sans lui, 400 et aucune tache. / The
        # serializer requires html_original; without it, 400 and no task.
        reponse = self._capturer(html_original="",
        )
        self.assertEqual(reponse.status_code, 400)
        delay_mock.assert_not_called()


class IngestionCaptureWebTacheTest(TestCase):
    """La tache convertit le HTML capture en elements."""

    def setUp(self):
        self.page = Page.objects.create(
            url="https://exemple.test/tache",
            html_original="<html><body><h1>Titre</h1>"
                          "<p>Corps.</p></body></html>",
            html_readability="<h1>Titre</h1><p>Corps.</p>",
            text_readability="Titre Corps.",
            content_hash="hash-capture-tache",
            ingestion_etat=EtatIngestion.EN_ATTENTE,

    )

    def test_la_tache_convertit_le_html_en_elements(self):
        from hypostasis_extractor import tasks_element

        elements_factices = [
            {"label": "title", "texte": "Titre"},
            {"label": "text", "texte": "Corps."},
        ]
        with mock.patch(
            "hypostasis_extractor.services.ingestion_docling"
            ".convertir_du_html_avec_docling", return_value=object()), mock.patch(
            "hypostasis_extractor.services.ingestion_docling"
            ".extraire_les_elements_bruts", return_value=elements_factices):
            tasks_element.ingerer_une_capture_web_avec_docling.apply(
                args=[self.page.pk],

        )

        self.page.refresh_from_db()
        self.assertTrue(self.page.elements.exists(),
        )
        self.assertEqual(self.page.ingestion_etat, EtatIngestion.REUSSIE)
        self.assertEqual(self.page.elements.count(), 2,

    )

    def test_un_echec_laisse_la_page_ancienne_et_lisible(self):
        from hypostasis_extractor import tasks_element

        with mock.patch(
            "hypostasis_extractor.services.ingestion_docling"
            ".convertir_du_html_avec_docling",
            side_effect=RuntimeError("conversion HTML impossible")):
            tasks_element.ingerer_une_capture_web_avec_docling.apply(
                args=[self.page.pk],

        )

        self.page.refresh_from_db()
        self.assertFalse(self.page.elements.exists(),
        )
        self.assertEqual(self.page.ingestion_etat, EtatIngestion.ECHOUEE)
        self.assertNotEqual(self.page.ingestion_detail, "",
        )
        # La page reste lisible par l'ancien moteur.
        # / The page stays readable via the old engine.
        self.assertEqual(self.page.html_readability, "<h1>Titre</h1><p>Corps.</p>",

    )

    def test_une_page_sans_html_original_echoue_proprement(self):
        from hypostasis_extractor import tasks_element

        page_vide = Page.objects.create(
            url="https://exemple.test/vide",
            html_original="", html_readability="<p>x</p>",
            text_readability="x", content_hash="hash-capture-vide",
            ingestion_etat=EtatIngestion.EN_ATTENTE)
        tasks_element.ingerer_une_capture_web_avec_docling.apply(
            args=[page_vide.pk])
        page_vide.refresh_from_db()
        self.assertEqual(page_vide.ingestion_etat, EtatIngestion.ECHOUEE,

    )

    def test_une_page_deja_ingeree_n_est_pas_reconvertie(self):
        from hypostasis_extractor import tasks_element

        ElementDocument.objects.create(
            page=self.page, ordre=0, label="text", texte="deja la",
            empreinte_contenu=empreinte_du_texte("deja la"),
        )
        with mock.patch(
            "hypostasis_extractor.services.ingestion_docling"
            ".convertir_du_html_avec_docling") as conversion_mock:
            tasks_element.ingerer_une_capture_web_avec_docling.apply(
                args=[self.page.pk])
        conversion_mock.assert_not_called()
