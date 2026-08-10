"""
Tests du flag moteur d'une Page (branchement BR-A).
/ Page engine flag tests (wiring phase BR-A).

LOCALISATION : core/tests/test_moteur_flag.py

SPEC-ancrage-par-element-v2 § 9 : les DEUX moteurs coexistent, une Page
porte un flag « moteur » — ANCIEN ou ELEMENT. Decision D1 du cahier des
charges du branchement (9 aout) : un CHAMP explicite, pas le
discriminant implicite `page.elements.exists()` qui casse sur une page
ELEMENT a zero element (ingestion echouee).
/ Explicit engine field; the implicit discriminant breaks on a
zero-element ELEMENT page.
"""

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase

from core.models import MoteurDePage, Page

Utilisateur = get_user_model()


def creer_une_page(url_unique, **champs):
    """Cree une page minimale. / Minimal page."""
    return Page.objects.create(
        url=url_unique,
        html_original="<p>o</p>",
        html_readability="<p>l</p>",
        text_readability="texte",
        content_hash=f"hash-{url_unique}",
        title=f"Note {url_unique[-12:]}",
        **champs,
    )


class FlagMoteurTest(TestCase):
    """Le champ Page.moteur. / The Page.moteur field."""

    def test_le_moteur_par_defaut_est_l_ancien(self):
        # Toute page creee sans rien dire reste sur l'ANCIEN moteur :
        # aucune regression sur l'existant (§ 9.2).
        # / Default is the OLD engine: zero regression.
        page = creer_une_page("http://exemple.local/bra-defaut")
        self.assertEqual(page.moteur, MoteurDePage.ANCIEN)

    def test_les_deux_moteurs_existent(self):
        self.assertEqual(MoteurDePage.ANCIEN, "ancien")
        self.assertEqual(MoteurDePage.ELEMENT, "element")

    def test_une_page_element_sans_element_reste_element(self):
        # LE cas qui justifie le champ (D1) : une ingestion ELEMENT qui
        # echoue laisse zero element — le discriminant implicite
        # `elements.exists()` la prendrait pour une page ANCIEN.
        # / A failed ELEMENT ingestion has zero elements; the implicit
        # discriminant would misread it.
        page = creer_une_page(
            "http://exemple.local/bra-vide", moteur=MoteurDePage.ELEMENT,
        )
        self.assertFalse(page.elements.exists())
        self.assertEqual(page.moteur, MoteurDePage.ELEMENT)


ETAT_AVANT_FLAG = [("core", "0052_provenance_du_verdict")]
ETAT_APRES_FLAG = [("core", "0053_page_moteur")]


class MigrationDuFlagMoteurTest(TransactionTestCase):
    """
    La migration ne bascule RIEN (§ 9.2) : tout l'existant reste
    ANCIEN, elements dormants compris. Le flag vient des ingestions.
    / The migration flips nothing: all existing pages stay ANCIEN.
    """

    def _migrer_vers(self, cibles):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(cibles)
        return executor.loader.project_state(cibles).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_l_existant_reste_ancien_meme_avec_des_elements(self):
        apps_avant = self._migrer_vers(ETAT_AVANT_FLAG)
        PageHistorique = apps_avant.get_model("core", "Page")
        ElementHistorique = apps_avant.get_model("core", "ElementDocument")

        page_ancienne = PageHistorique.objects.create(
            url="http://exemple.local/bra-mig-ancienne",
            html_original="<p>o</p>", html_readability="<p>l</p>",
            text_readability="texte", content_hash="hash-bra-1",
        )
        page_element = PageHistorique.objects.create(
            url="http://exemple.local/bra-mig-element",
            html_original="<p>o</p>", html_readability="<p>l</p>",
            text_readability="texte", content_hash="hash-bra-2",
        )
        ElementHistorique.objects.create(
            page_id=page_element.pk, ordre=0, label="text",
            texte="un element", empreinte_contenu="e" * 64,
        )

        apps_apres = self._migrer_vers(ETAT_APRES_FLAG)
        PageApres = apps_apres.get_model("core", "Page")

        # § 9.2 : TOUT l'existant reste ANCIEN — meme une page qui
        # porte deja des elements (537/541 en dev ont des elements
        # DORMANTS issus des phases de test : les basculer ferait
        # changer le rendu du corpus entier d'un coup). La bascule est
        # une reconversion explicite (§ 9.5), pas une migration.
        # / Existing pages ALL stay ANCIEN, even element-bearing ones.
        self.assertEqual(
            PageApres.objects.get(pk=page_ancienne.pk).moteur, "ancien",
        )
        self.assertEqual(
            PageApres.objects.get(pk=page_element.pk).moteur, "ancien",
        )


class PoseDuFlagALIngestionTest(TestCase):
    """
    BR-A : l'ingestion ELEMENT pose le flag — le champ est ecrit au
    SEUL endroit par lequel toute ingestion element passe.
    / ELEMENT ingestion stamps the flag at its single choke point.
    """

    def test_creer_les_elements_pose_le_moteur_element(self):
        from hypostasis_extractor.services.ingestion_docling import (
            creer_les_elements_d_une_page,
        )

        page = creer_une_page("http://exemple.local/bra-ingestion")
        self.assertEqual(page.moteur, MoteurDePage.ANCIEN)

        creer_les_elements_d_une_page(page, [
            {"texte": "Premier élément.", "label": "text"},
        ])

        page.refresh_from_db()
        self.assertEqual(page.moteur, MoteurDePage.ELEMENT)
        self.assertEqual(page.elements.count(), 1)
