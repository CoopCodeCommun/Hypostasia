"""
Le controle d'acces des lectures d'extractions (drawer, cartes,
dashboard, formulaire de promotion).
/ Access control for extraction READ endpoints.

LOCALISATION : front/tests/test_extractions_permissions.py

CE QUI EST VERROUILLE ICI (correctif du 10 aout 2026, decouvert en
preparant U3). Quatre actions GET d'ExtractionViewSet ne verifiaient
AUCUNE permission :
- `/extractions/drawer_contenu/?page_id=N` : le TEXTE de toutes les
  extractions d'une page, plus les noms des contributeurs — sans etre
  connecte. La pire.
- `/extractions/carte_mobile/?entity_id=N` : une extraction et son
  activite.
- `/extractions/dashboard/?page_id=N` : les stats de debat de la page.
- `/extractions/formulaire_promouvoir/?page_id=N` : le titre de la
  page (et un oracle d'existence).

La regle appliquee est CELLE DU PRODUIT (`_utilisateur_a_acces_page`,
SPEC-corpus § 5.2), et l'interdit est indistinguable de l'absent, au
meme octet : doctrine du 404 plutot que du 403 (meme methode que
front/tests/test_alignement_permissions.py).
/ Same product rule as everywhere; forbidden is byte-identical to
missing (404 doctrine).
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import Dossier, Page, VisibiliteDossier
from core.services.corpus import ranger_une_note_dans_un_carnet
from hypostasis_extractor.models import ExtractedEntity, ExtractionJob

Utilisateur = get_user_model()


def _creer_une_note(suffixe, titre, owner=None):
    return Page.objects.create(
        url=f"https://exemple.test/extr-{suffixe}",
        html_original="<p>o</p>",
        html_readability="<p>l</p>",
        text_readability="Le texte de la note.",
        content_hash=f"hash-extr-{suffixe}",
        owner=owner,
        title=titre,
    )


def _ajouter_une_extraction(page, texte):
    job = ExtractionJob.objects.create(page=page, status="completed")
    return ExtractedEntity.objects.create(
        job=job, extraction_class="principe",
        extraction_text=texte, start_char=0, end_char=len(texte),
    )


class ExtractionsPermissionsTest(TestCase):
    """Personne ne lit par ces endpoints ce qu'il ne peut lire ailleurs."""

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            "proprio_extr", "proprio@exemple.test", "motdepasse123",
        )
        self.intrus = Utilisateur.objects.create_user(
            "intrus_extr", "intrus@exemple.test", "motdepasse123",
        )

        self.carnet_prive = Dossier.objects.create(
            name="Carnet prive extr", owner=self.proprietaire,
            visibilite=VisibiliteDossier.PRIVE,
        )
        self.note_privee = _creer_une_note(
            "privee", "Secret industriel", owner=self.proprietaire,
        )
        ranger_une_note_dans_un_carnet(
            self.note_privee, self.carnet_prive,
            utilisateur=self.proprietaire,
        )
        self.extraction_privee = _ajouter_une_extraction(
            self.note_privee, "Le secret que personne ne doit lire.",
        )

        self.carnet_public = Dossier.objects.create(
            name="Carnet public extr", owner=self.proprietaire,
            visibilite=VisibiliteDossier.PUBLIC,
        )
        self.note_publique = _creer_une_note(
            "publique", "Note publique", owner=self.proprietaire,
        )
        ranger_une_note_dans_un_carnet(
            self.note_publique, self.carnet_public,
            utilisateur=self.proprietaire,
        )
        self.extraction_publique = _ajouter_une_extraction(
            self.note_publique, "Un contenu offert a tous.",
        )

    # ---- drawer_contenu : la fuite principale ----

    def test_le_proprietaire_lit_son_drawer(self):
        self.client.force_login(self.proprietaire)
        reponse = self.client.get(
            f"/extractions/drawer_contenu/?page_id={self.note_privee.pk}",
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertIn(
            "Le secret que personne ne doit lire.",
            reponse.content.decode(),
        )

    def test_le_drawer_d_une_note_interdite_est_introuvable(self):
        self.client.force_login(self.intrus)
        reponse = self.client.get(
            f"/extractions/drawer_contenu/?page_id={self.note_privee.pk}",
        )
        self.assertEqual(reponse.status_code, 404)
        self.assertNotIn(
            "secret", reponse.content.decode().lower(),
        )

    def test_le_drawer_anonyme_d_une_note_privee_est_introuvable(self):
        reponse = self.client.get(
            f"/extractions/drawer_contenu/?page_id={self.note_privee.pk}",
        )
        self.assertEqual(reponse.status_code, 404)
        self.assertNotIn("secret", reponse.content.decode().lower())

    def test_interdit_et_absent_sont_le_meme_octet(self):
        # L'oracle d'existence : une note interdite doit repondre
        # EXACTEMENT comme une note qui n'existe pas.
        # / Forbidden must be byte-identical to missing.
        self.client.force_login(self.intrus)
        reponse_interdite = self.client.get(
            f"/extractions/drawer_contenu/?page_id={self.note_privee.pk}",
        )
        reponse_absente = self.client.get(
            "/extractions/drawer_contenu/?page_id=999999",
        )
        self.assertEqual(reponse_interdite.status_code, 404)
        self.assertEqual(
            reponse_interdite.content, reponse_absente.content,
        )

    def test_le_drawer_d_une_note_publique_reste_lisible(self):
        # La regle du produit, pas un mur de connexion : une note d'un
        # carnet public se lit. / The product rule, not a login wall.
        self.client.force_login(self.intrus)
        reponse = self.client.get(
            f"/extractions/drawer_contenu/?page_id={self.note_publique.pk}",
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertIn("Un contenu offert a tous.", reponse.content.decode())

    # ---- carte_mobile ----

    def test_la_carte_mobile_d_une_note_interdite_est_introuvable(self):
        self.client.force_login(self.intrus)
        reponse = self.client.get(
            f"/extractions/carte_mobile/?entity_id={self.extraction_privee.pk}",
        )
        self.assertEqual(reponse.status_code, 404)

    def test_la_carte_mobile_du_proprietaire_repond(self):
        self.client.force_login(self.proprietaire)
        reponse = self.client.get(
            f"/extractions/carte_mobile/?entity_id={self.extraction_privee.pk}",
        )
        self.assertEqual(reponse.status_code, 200)

    # ---- dashboard ----

    def test_le_dashboard_d_une_note_interdite_est_introuvable(self):
        self.client.force_login(self.intrus)
        reponse = self.client.get(
            f"/extractions/dashboard/?page_id={self.note_privee.pk}",
        )
        self.assertEqual(reponse.status_code, 404)

    # ---- formulaire_promouvoir ----

    def test_le_formulaire_promouvoir_d_une_note_interdite_est_introuvable(self):
        self.client.force_login(self.intrus)
        reponse = self.client.get(
            f"/extractions/formulaire_promouvoir/?page_id={self.note_privee.pk}",
        )
        self.assertEqual(reponse.status_code, 404)
