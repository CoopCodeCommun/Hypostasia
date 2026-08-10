"""
Tests de l'UI carnet (phase F) contre les comportements de l'etalon.
/ Notebook UI tests (phase F) against the etalon's behaviours.

LOCALISATION : front/tests/test_corpus_phase_f.py
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (
    AppartenancePageDossier,
    CategorieDossier,
    Dossier,
    ListeDeCategories,
    Page,
    VisibiliteDossier,
)
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


class EcranCarnetTest(TestCase):
    """L'ecran carnet : integration, URL, resume. / The notebook screen."""

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="proprio_f_test", password="motdepasse"
        )
        self.carnet = Dossier.objects.create(
            name="Carnet F", owner=self.proprietaire,
            visibilite=VisibiliteDossier.PUBLIC,
            guide_de_redaction="Toujours citer la source.",
        )
        self.axe = ListeDeCategories.objects.create(
            nom="Type", dossier=self.carnet,
        )
        self.categorie_aap = CategorieDossier.objects.create(
            liste=self.axe, nom="AAP",
        )
        self.note_aap = creer_une_page("http://exemple.local/f-aap")
        self.note_nue = creer_une_page("http://exemple.local/f-nue")
        appartenance = ranger_une_note_dans_un_carnet(
            self.note_aap, self.carnet, self.proprietaire
        )
        appartenance.categories.add(self.categorie_aap)
        ranger_une_note_dans_un_carnet(self.note_nue, self.carnet, self.proprietaire)

    def test_acces_direct_rend_la_page_complete_du_site(self):
        # F5 -> base.html (avec htmx et CSRF), pas un document autonome.
        # / Direct hit -> base.html, not a standalone document.
        reponse = self.client.get(f"/carnets/{self.carnet.pk}/")
        contenu = reponse.content.decode("utf-8")

        self.assertIn("htmx", contenu)
        self.assertIn("corpus-carnet-detail", contenu)
        self.assertIn("Guide de rédaction de ce carnet", contenu)

    def test_requete_htmx_rend_le_contenu_seul(self):
        reponse = self.client.get(
            f"/carnets/{self.carnet.pk}/", HTTP_HX_REQUEST="true",
        )
        contenu = reponse.content.decode("utf-8")
        self.assertIn("corpus-carnet-detail", contenu)
        self.assertNotIn("<!DOCTYPE", contenu)

    def test_l_url_restaure_les_filtres(self):
        # § 8.2 : l'etat est dans l'URL. Un lien partage retrouve la case
        # cochee ET la liste filtree. / State lives in the URL.
        reponse = self.client.get(
            f"/carnets/{self.carnet.pk}/",
            {"categorie": [self.categorie_aap.pk]},
        )
        contenu = reponse.content.decode("utf-8")

        self.assertIn(f'value="{self.categorie_aap.pk}"\n                       checked', contenu.replace("\r", ""))
        self.assertIn(self.note_aap.title, contenu)
        self.assertNotIn(self.note_nue.title, contenu)

    def test_le_resume_des_filtres_ecrit_ou_et_et(self):
        # La phrase litterale rend la regle lisible sans documentation.
        # / The literal sentence makes the rule readable.
        axe_echeance = ListeDeCategories.objects.create(
            nom="Échéance", dossier=self.carnet,
        )
        categorie_mois = CategorieDossier.objects.create(
            liste=axe_echeance, nom="Ce mois-ci",
        )
        categorie_subvention = CategorieDossier.objects.create(
            liste=self.axe, nom="Subvention",
        )
        reponse = self.client.get(
            f"/carnets/{self.carnet.pk}/notes/",
            {"categorie": [self.categorie_aap.pk, categorie_subvention.pk,
                           categorie_mois.pk]},
        )
        contenu = reponse.content.decode("utf-8")

        self.assertIn("AAP OU Subvention", contenu)
        self.assertIn("ET", contenu)
        self.assertIn("Tout afficher", contenu)
        self.assertIn("sur 2 note", contenu)

    def test_les_compteurs_de_ligne_sont_annotes(self):
        reponse = self.client.get(f"/carnets/{self.carnet.pk}/notes/")
        contenu = reponse.content.decode("utf-8")
        self.assertIn("0 extraction", contenu)


class OrdreNarratifTest(TestCase):
    """Les boutons monter/descendre. / The up/down buttons."""

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="ordre_f_test", password="motdepasse"
        )
        self.carnet = Dossier.objects.create(
            name="Carnet ordre F", owner=self.proprietaire,
        )
        self.premiere = creer_une_page("http://exemple.local/f-ordre-1")
        self.seconde = creer_une_page("http://exemple.local/f-ordre-2")
        self.appartenance_premiere = ranger_une_note_dans_un_carnet(
            self.premiere, self.carnet, self.proprietaire
        )
        self.appartenance_seconde = ranger_une_note_dans_un_carnet(
            self.seconde, self.carnet, self.proprietaire
        )
        self.client.force_login(self.proprietaire)

    def test_monter_echange_avec_la_voisine_et_fige_l_ordre(self):
        # Les ordres etaient a 0 (pas d'ordre impose) : le premier geste
        # fige l'ordre courant puis echange. / First gesture materializes
        # the current order, then swaps.
        # Ordre courant (0 partout -> chronologique inverse) :
        # seconde (plus recente) puis premiere.
        reponse = self.client.post(
            f"/carnets/{self.carnet.pk}/reordonner/",
            {"deplacer": self.premiere.pk, "direction": "monter"},
        )

        self.assertEqual(reponse.status_code, 200)
        self.appartenance_premiere.refresh_from_db()
        self.appartenance_seconde.refresh_from_db()
        self.assertEqual(self.appartenance_premiere.ordre_manuel, 1)
        self.assertEqual(self.appartenance_seconde.ordre_manuel, 2)

    def test_monter_a_l_extremite_ne_change_rien(self):
        self.client.post(
            f"/carnets/{self.carnet.pk}/reordonner/",
            {"deplacer": self.premiere.pk, "direction": "monter"},
        )
        # premiere est maintenant en tete ; re-monter = no-op, 200.
        # / Now first; moving up again is a no-op, 200.
        reponse = self.client.post(
            f"/carnets/{self.carnet.pk}/reordonner/",
            {"deplacer": self.premiere.pk, "direction": "monter"},
        )
        self.assertEqual(reponse.status_code, 200)
        self.appartenance_premiere.refresh_from_db()
        self.assertEqual(self.appartenance_premiere.ordre_manuel, 1)

    def test_l_epingle_est_transferee_quand_on_croise_la_frontiere(self):
        # Etalon corpus.html:1194 : si la voisine est epinglee et pas la
        # note, l'echange transfere l'epingle — sinon le tri epinglees-
        # d'abord annulerait l'echange a l'affichage.
        # / The pin is transferred across the boundary.
        self.appartenance_seconde.epinglee = True
        self.appartenance_seconde.save(update_fields=["epinglee"])

        self.client.post(
            f"/carnets/{self.carnet.pk}/reordonner/",
            {"deplacer": self.premiere.pk, "direction": "monter"},
        )

        self.appartenance_premiere.refresh_from_db()
        self.appartenance_seconde.refresh_from_db()
        self.assertTrue(self.appartenance_premiere.epinglee)
        self.assertFalse(self.appartenance_seconde.epinglee)


class CibleSelonLEcranTest(TestCase):
    """epingler/categoriser renvoient le bon partial. / Screen targeting."""

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="cible_f_test", password="motdepasse"
        )
        self.carnet = Dossier.objects.create(
            name="Carnet cible F", owner=self.proprietaire,
        )
        self.note = creer_une_page("http://exemple.local/f-cible")
        ranger_une_note_dans_un_carnet(self.note, self.carnet, self.proprietaire)
        self.client.force_login(self.proprietaire)

    def test_epingler_depuis_l_ecran_carnet_rend_la_liste(self):
        reponse = self.client.post(
            f"/notes/{self.note.pk}/carnets/{self.carnet.pk}/epingler/",
            {"ecran": "carnet"},
        )
        contenu = reponse.content.decode("utf-8")
        self.assertIn("corpus-notes-liste", contenu)
        self.assertNotIn("corpus-bloc-carnets", contenu)

    def test_epingler_depuis_l_ecran_note_rend_le_bloc(self):
        reponse = self.client.post(
            f"/notes/{self.note.pk}/carnets/{self.carnet.pk}/epingler/"
        )
        contenu = reponse.content.decode("utf-8")
        self.assertIn("corpus-bloc-carnets", contenu)


class ListeDesCarnetsTest(TestCase):
    """Les compteurs derives de /carnets/. / Derived counters."""

    def test_la_liste_affiche_notes_et_axes(self):
        proprietaire = Utilisateur.objects.create_user(
            username="liste_f_test", password="motdepasse"
        )
        carnet = Dossier.objects.create(
            name="Carnet liste F", owner=proprietaire,
            visibilite=VisibiliteDossier.PUBLIC,
        )
        ListeDeCategories.objects.create(nom="Type", dossier=carnet)
        note = creer_une_page("http://exemple.local/f-liste")
        ranger_une_note_dans_un_carnet(note, carnet, proprietaire)

        reponse = self.client.get("/carnets/", HTTP_HX_REQUEST="true")
        contenu = reponse.content.decode("utf-8")

        self.assertIn("1 note", contenu)
        self.assertIn("1 axe de classement", contenu)
