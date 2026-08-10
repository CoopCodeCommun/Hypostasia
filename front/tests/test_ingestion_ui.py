"""
U2 — la surface UI de l'ingestion Docling.
/ U2 — the Docling ingestion UI surface.

LOCALISATION : front/tests/test_ingestion_ui.py

Dette § 5 du cahier de branchement : l'echec d'ingestion etait
SILENCIEUX (la page restait ANCIEN et lisible, mais rien ne le disait
et aucune relance n'existait — seul le journal Celery faisait foi).

Ce qui est verrouille ici :
- l'ETAT d'ingestion vit sur la Page (`ingestion_etat` : en_attente,
  en_cours, reussie, echouee + `ingestion_detail` FALC), ecrit par la
  vue d'import et par la tache ;
- la lecture montre une PUCE d'etat a qui peut ecrire (en attente / en
  cours / echec + bouton « Relancer »), qui s'auto-rafraichit avec un
  plafond d'essais (patron du retour de production F1/F2) ;
- la RELANCE manuelle existe, gardee (droit d'ecriture, pas pendant
  une ingestion active, pas sur une page deja ingeree).
/ Ingestion state on the Page, a status chip for writers with capped
polling, and a guarded manual relaunch.
"""

import json
import shutil
import tempfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import ElementDocument, EtatIngestion, MoteurDePage, Page, empreinte_du_texte

Utilisateur = get_user_model()

MEDIA_DE_TEST = tempfile.mkdtemp(prefix="test-ingestion-ui-")


@override_settings(MEDIA_ROOT=MEDIA_DE_TEST)
class BaseIngestionUITest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.addClassCleanup(shutil.rmtree, MEDIA_DE_TEST, ignore_errors=True)

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="proprio-ingestion", password="motdepasse",
        )
        self.lecteur_superuser = Utilisateur.objects.create_superuser(
            username="lecteur-ingestion", password="motdepasse",
        )
        self.client.force_login(self.proprietaire)

    def _creer_une_page(self, suffixe, moteur=MoteurDePage.ANCIEN,
                        etat="", detail="", nom_fichier="doc.md"):
        page = Page.objects.create(
            url=f"http://exemple.local/u2-{suffixe}",
            html_original="<p>o</p>",
            html_readability="<p>Lisible par l'ancien moteur.</p>",
            text_readability="texte", content_hash=f"hash-u2-{suffixe}",
            owner=self.proprietaire, moteur=moteur, status="completed",
            original_filename=nom_fichier,
            ingestion_etat=etat, ingestion_detail=detail,
        )
        if nom_fichier:
            page.source_file.save(
                nom_fichier, SimpleUploadedFile(nom_fichier, b"# t\n\ncorps"),
                save=True,
            )
        return page


class EtatPoseParLaVueEtLaTacheTest(BaseIngestionUITest):
    """La vue d'import et la tache ecrivent l'etat sur la page."""

    @mock.patch(
        "hypostasis_extractor.tasks_element"
        ".ingerer_un_fichier_avec_docling.delay"
    )
    def test_un_import_couvert_pose_l_etat_en_attente(self, delay_mock):
        reponse = self.client.post(
            reverse("front:import-fichier"),
            {"fichier": SimpleUploadedFile(
                "notes.md", "# Titre\n\nUn paragraphe.".encode("utf-8"),
            )},
        )
        self.assertEqual(reponse.status_code, 200)
        page = Page.objects.get(original_filename="notes.md")
        self.assertEqual(page.ingestion_etat, EtatIngestion.EN_ATTENTE)

    @mock.patch(
        "hypostasis_extractor.tasks_element"
        ".ingerer_un_fichier_avec_docling.delay"
    )
    def test_un_broker_en_panne_ne_promet_rien(self, delay_mock):
        delay_mock.side_effect = Exception("broker indisponible")
        reponse = self.client.post(
            reverse("front:import-fichier"),
            {"fichier": SimpleUploadedFile(
                "panne.md", "# Titre\n\nCorps.".encode("utf-8"),
            )},
        )
        self.assertEqual(reponse.status_code, 200)
        page = Page.objects.get(original_filename="panne.md")
        self.assertEqual(page.ingestion_etat, "")

    def test_la_tache_pose_reussie_puis_echouee(self):
        # On appelle la vraie tache avec le service mocke : succes ->
        # reussie ; echec -> echouee + detail FALC.
        # / Real task, mocked service: success and failure states.
        from hypostasis_extractor import tasks_element

        page = self._creer_une_page("tache", etat=EtatIngestion.EN_ATTENTE)

        with mock.patch(
            "hypostasis_extractor.services.ingestion_docling"
            ".ingerer_un_fichier", return_value=[object()],
        ):
            tasks_element.ingerer_un_fichier_avec_docling.apply(
                args=[page.pk],
            )
        page.refresh_from_db()
        self.assertEqual(page.ingestion_etat, EtatIngestion.REUSSIE)

        page_en_echec = self._creer_une_page(
            "tache-echec", etat=EtatIngestion.EN_ATTENTE,
        )
        with mock.patch(
            "hypostasis_extractor.services.ingestion_docling"
            ".ingerer_un_fichier",
            side_effect=RuntimeError("conversion impossible"),
        ):
            tasks_element.ingerer_un_fichier_avec_docling.apply(
                args=[page_en_echec.pk],
            )
        page_en_echec.refresh_from_db()
        self.assertEqual(page_en_echec.ingestion_etat, EtatIngestion.ECHOUEE)
        self.assertNotEqual(page_en_echec.ingestion_detail, "")

    def test_une_page_sans_fichier_source_echoue_proprement(self):
        from hypostasis_extractor import tasks_element

        page = self._creer_une_page(
            "sans-fichier", etat=EtatIngestion.EN_ATTENTE, nom_fichier="",
        )
        tasks_element.ingerer_un_fichier_avec_docling.apply(args=[page.pk])
        page.refresh_from_db()
        self.assertEqual(page.ingestion_etat, EtatIngestion.ECHOUEE)


class PuceDEtatDansLaLectureTest(BaseIngestionUITest):
    """La lecture montre l'etat a qui peut ecrire, et a lui seul."""

    def _lire(self, page):
        return self.client.get(
            f"/lire/{page.pk}/", HTTP_HX_REQUEST="true",
        ).content.decode()

    def test_un_echec_est_visible_avec_sa_relance(self):
        page = self._creer_une_page(
            "echec-visible", etat=EtatIngestion.ECHOUEE,
            detail="Le fichier est trop grand.",
        )
        contenu = self._lire(page)
        self.assertIn('data-testid="etat-ingestion"', contenu)
        self.assertIn("Le fichier est trop grand.", contenu)
        self.assertIn(f"/lire/{page.pk}/relancer_ingestion/", contenu)

    def test_une_ingestion_active_se_rafraichit(self):
        page = self._creer_une_page(
            "active", etat=EtatIngestion.EN_ATTENTE,
        )
        contenu = self._lire(page)
        self.assertIn('data-testid="etat-ingestion"', contenu)
        self.assertIn(f"/lire/{page.pk}/etat_ingestion/", contenu)

    def test_un_simple_lecteur_ne_voit_rien(self):
        page = self._creer_une_page(
            "lecteur", etat=EtatIngestion.ECHOUEE, detail="Panne.",
        )
        self.client.force_login(self.lecteur_superuser)
        contenu = self._lire(page)
        self.assertNotIn('data-testid="etat-ingestion"', contenu)
        self.assertNotIn("relancer_ingestion", contenu)

    def test_une_reussite_est_silencieuse(self):
        page = self._creer_une_page(
            "reussie", etat=EtatIngestion.REUSSIE,
        )
        contenu = self._lire(page)
        self.assertNotIn('data-testid="etat-ingestion"', contenu)


class SondeDEtatTest(BaseIngestionUITest):
    """GET /lire/{pk}/etat_ingestion/ — la sonde du patron F1/F2."""

    def test_la_sonde_active_se_renvoie_elle_meme(self):
        page = self._creer_une_page("sonde", etat=EtatIngestion.EN_COURS)
        reponse = self.client.get(f"/lire/{page.pk}/etat_ingestion/")
        contenu = reponse.content.decode()
        self.assertIn('data-testid="etat-ingestion"', contenu)
        self.assertIn("etat_ingestion", contenu)

    def test_la_sonde_annonce_la_reussite_et_recharge(self):
        page = self._creer_une_page(
            "sonde-ok", moteur=MoteurDePage.ELEMENT,
            etat=EtatIngestion.REUSSIE,
        )
        reponse = self.client.get(f"/lire/{page.pk}/etat_ingestion/")
        declencheurs = json.loads(reponse["HX-Trigger"])
        self.assertIn("lectureReload", declencheurs)

    def test_la_sonde_a_un_plafond_d_essais(self):
        # Un worker mort ne doit pas faire interroger le serveur pour
        # toujours (garde-fou du patron F1). / Capped polling.
        page = self._creer_une_page("sonde-cap", etat=EtatIngestion.EN_COURS)
        reponse = self.client.get(
            f"/lire/{page.pk}/etat_ingestion/?essai=200",
        )
        contenu = reponse.content.decode()
        self.assertNotIn("hx-trigger", contenu.lower())

    def test_la_sonde_d_une_note_interdite_est_introuvable(self):
        page = self._creer_une_page("sonde-privee", etat=EtatIngestion.EN_COURS)
        self.client.logout()
        autre = Utilisateur.objects.create_user(
            username="autre-ingestion", password="motdepasse",
        )
        self.client.force_login(autre)
        reponse = self.client.get(f"/lire/{page.pk}/etat_ingestion/")
        self.assertEqual(reponse.status_code, 404)


class RelanceManuelleTest(BaseIngestionUITest):
    """POST /lire/{pk}/relancer_ingestion/ — gardee et honnete."""

    @mock.patch(
        "hypostasis_extractor.tasks_element"
        ".ingerer_un_fichier_avec_docling.delay"
    )
    def test_relancer_une_ingestion_echouee(self, delay_mock):
        page = self._creer_une_page(
            "relance", etat=EtatIngestion.ECHOUEE, detail="Panne.",
        )
        reponse = self.client.post(f"/lire/{page.pk}/relancer_ingestion/")
        self.assertEqual(reponse.status_code, 200)
        delay_mock.assert_called_once_with(page.pk)
        page.refresh_from_db()
        self.assertEqual(page.ingestion_etat, EtatIngestion.EN_ATTENTE)

    @mock.patch(
        "hypostasis_extractor.tasks_element"
        ".ingerer_un_fichier_avec_docling.delay"
    )
    def test_pas_de_relance_pendant_une_ingestion_active(self, delay_mock):
        page = self._creer_une_page(
            "relance-active", etat=EtatIngestion.EN_COURS,
        )
        reponse = self.client.post(f"/lire/{page.pk}/relancer_ingestion/")
        self.assertEqual(reponse.status_code, 409)
        delay_mock.assert_not_called()

    @mock.patch(
        "hypostasis_extractor.tasks_element"
        ".ingerer_un_fichier_avec_docling.delay"
    )
    def test_pas_de_relance_sur_une_page_deja_ingeree(self, delay_mock):
        page = self._creer_une_page(
            "relance-ingeree", moteur=MoteurDePage.ELEMENT,
            etat=EtatIngestion.ECHOUEE,
        )
        ElementDocument.objects.create(
            page=page, ordre=0, label="text", texte="deja la",
            empreinte_contenu=empreinte_du_texte("deja la"),
        )
        reponse = self.client.post(f"/lire/{page.pk}/relancer_ingestion/")
        self.assertEqual(reponse.status_code, 409)
        delay_mock.assert_not_called()

    @mock.patch(
        "hypostasis_extractor.tasks_element"
        ".ingerer_un_fichier_avec_docling.delay"
    )
    def test_un_tiers_ne_relance_pas(self, delay_mock):
        page = self._creer_une_page(
            "relance-tiers", etat=EtatIngestion.ECHOUEE,
        )
        self.client.force_login(self.lecteur_superuser)
        reponse = self.client.post(f"/lire/{page.pk}/relancer_ingestion/")
        self.assertEqual(reponse.status_code, 403)
        delay_mock.assert_not_called()

    @mock.patch(
        "hypostasis_extractor.tasks_element"
        ".ingerer_un_fichier_avec_docling.delay"
    )
    def test_un_type_non_couvert_ne_se_relance_pas(self, delay_mock):
        page = self._creer_une_page(
            "relance-txt", etat=EtatIngestion.ECHOUEE,
            nom_fichier="notes.txt",
        )
        reponse = self.client.post(f"/lire/{page.pk}/relancer_ingestion/")
        self.assertEqual(reponse.status_code, 409)
        delay_mock.assert_not_called()

    @mock.patch(
        "hypostasis_extractor.tasks_element"
        ".ingerer_un_fichier_avec_docling.delay"
    )
    def test_une_ingestion_active_fantome_se_relance(self, delay_mock):
        # H2 : un worker tue laisse « en cours » pour toujours. Au-dela
        # du delai, la relance est de nouveau permise — sinon impasse.
        # / A dead worker leaves an active state forever; past the delay
        # relaunch is allowed again.
        from datetime import timedelta

        from django.utils import timezone

        page = self._creer_une_page(
            "relance-fantome", etat=EtatIngestion.EN_COURS,
        )
        Page.objects.filter(pk=page.pk).update(
            ingestion_maj_le=timezone.now() - timedelta(minutes=30),
        )
        reponse = self.client.post(f"/lire/{page.pk}/relancer_ingestion/")
        self.assertEqual(reponse.status_code, 200)
        delay_mock.assert_called_once_with(page.pk)

    @mock.patch(
        "hypostasis_extractor.tasks_element"
        ".ingerer_un_fichier_avec_docling.delay"
    )
    def test_une_ingestion_active_recente_ne_se_relance_pas(self, delay_mock):
        from django.utils import timezone

        page = self._creer_une_page(
            "relance-recente", etat=EtatIngestion.EN_COURS,
        )
        Page.objects.filter(pk=page.pk).update(
            ingestion_maj_le=timezone.now(),
        )
        reponse = self.client.post(f"/lire/{page.pk}/relancer_ingestion/")
        self.assertEqual(reponse.status_code, 409)
        delay_mock.assert_not_called()

    @mock.patch(
        "hypostasis_extractor.tasks_element"
        ".ingerer_un_fichier_avec_docling.delay"
    )
    def test_un_tiers_sans_acces_ne_distingue_pas_absent_d_interdit(
        self, delay_mock,
    ):
        # M1 : doctrine du 404 — un tiers sans acces lecture recoit 404,
        # comme sur une page absente ; pas d'enumeration des pk prives.
        # / 404 doctrine: no-access outsider cannot enumerate private pks.
        page = self._creer_une_page(
            "relance-privee", etat=EtatIngestion.ECHOUEE,
        )
        # Une note vraiment privee : owner autre, aucun carnet partage.
        autre_proprietaire = Utilisateur.objects.create_user(
            username="autre-proprio-ingestion", password="motdepasse",
        )
        page.owner = autre_proprietaire
        page.save(update_fields=["owner"])

        self.client.logout()
        intrus = Utilisateur.objects.create_user(
            username="intrus-ingestion", password="motdepasse",
        )
        self.client.force_login(intrus)
        reponse = self.client.post(f"/lire/{page.pk}/relancer_ingestion/")
        self.assertEqual(reponse.status_code, 404)
        delay_mock.assert_not_called()
