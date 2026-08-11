"""
Tests de l'ecran note (phase G) : le bloc « Dans N carnets » editable.
/ Note screen tests (phase G): the editable "In N notebooks" block.

LOCALISATION : front/tests/test_corpus_phase_g.py
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import Dossier, Page, VisibiliteDossier
from core.services.corpus import ranger_une_note_dans_un_carnet

Utilisateur = get_user_model()


def creer_une_page(url_unique, owner=None):
    """Cree une page minimale pour les tests. / Minimal test page."""
    return Page.objects.create(
        url=url_unique,
        html_original="<p>o</p>",
        html_readability="<p>l</p>",
        text_readability="texte",
        content_hash=f"hash-{url_unique}",
        owner=owner,
        title=f"Note {url_unique[-10:]}",
    )


class BlocCarnetsTest(TestCase):
    """GET /notes/{id}/carnets/bloc/. / The lazy-loaded block."""

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="proprio_g_test", password="motdepasse"
        )
        self.carnet = Dossier.objects.create(
            name="Carnet G", owner=self.proprietaire,
            visibilite=VisibiliteDossier.PUBLIC,
        )
        self.note = creer_une_page(
            "http://exemple.local/g-note", owner=self.proprietaire,
        )
        ranger_une_note_dans_un_carnet(self.note, self.carnet, self.proprietaire)

    def test_le_bloc_se_charge_et_nomme_le_carnet(self):
        reponse = self.client.get(f"/notes/{self.note.pk}/carnets/bloc/")
        contenu = reponse.content.decode("utf-8")

        self.assertEqual(reponse.status_code, 200)
        self.assertIn("Dans 1 carnet", contenu)
        self.assertIn("Carnet G", contenu)

    def test_le_bloc_d_une_note_privee_est_refuse(self):
        note_privee = creer_une_page(
            "http://exemple.local/g-privee", owner=self.proprietaire,
        )
        carnet_prive = Dossier.objects.create(
            name="Privé G", owner=self.proprietaire,
            visibilite=VisibiliteDossier.PRIVE,
        )
        ranger_une_note_dans_un_carnet(note_privee, carnet_prive, self.proprietaire)

        reponse = self.client.get(f"/notes/{note_privee.pk}/carnets/bloc/")
        self.assertEqual(reponse.status_code, 403)

    def test_les_boutons_d_edition_exigent_le_droit(self):
        # Anonyme : lecture seule, aucun bouton retirer/epingler/crayon.
        # / Anonymous: read-only, no edit buttons.
        reponse = self.client.get(f"/notes/{self.note.pk}/carnets/bloc/")
        contenu = reponse.content.decode("utf-8")
        self.assertNotIn("corpus-bloc-retirer", contenu)

        self.client.force_login(self.proprietaire)
        reponse = self.client.get(f"/notes/{self.note.pk}/carnets/bloc/")
        contenu = reponse.content.decode("utf-8")
        self.assertIn("corpus-bloc-retirer", contenu)

    def test_derniere_appartenance_porte_l_avertissement(self):
        # § 9 : retirer la derniere appartenance doit avertir.
        # / Removing the last membership must warn.
        self.client.force_login(self.proprietaire)
        reponse = self.client.get(f"/notes/{self.note.pk}/carnets/bloc/")
        contenu = reponse.content.decode("utf-8")
        self.assertIn("DERNIER carnet", contenu)

    def test_l_option_d_un_carnet_public_porte_l_avertissement(self):
        # § 7.3 : l'avertissement est dit AU MOMENT du geste.
        # / The public-notebook warning is inline, at gesture time.
        Dossier.objects.create(
            name="Autre public G", owner=self.proprietaire,
            visibilite=VisibiliteDossier.PUBLIC,
        )
        self.client.force_login(self.proprietaire)
        reponse = self.client.get(f"/notes/{self.note.pk}/carnets/bloc/")
        contenu = reponse.content.decode("utf-8")
        self.assertIn("PUBLIC : la note y sera visible par tous", contenu)

    def test_ajouter_depuis_le_bloc_rafraichit_le_bloc(self):
        cible = Dossier.objects.create(
            name="Cible G", owner=self.proprietaire,
        )
        self.client.force_login(self.proprietaire)
        reponse = self.client.post(
            f"/notes/{self.note.pk}/carnets/",
            {"carnet_id": cible.pk},
        )
        contenu = reponse.content.decode("utf-8")
        self.assertIn("Dans 2 carnets", contenu)

    def test_l_ecran_de_lecture_charge_le_bloc(self):
        reponse = self.client.get(f"/lire/{self.note.pk}/")
        contenu = reponse.content.decode("utf-8")
        self.assertIn(f"/notes/{self.note.pk}/carnets/bloc/", contenu)
