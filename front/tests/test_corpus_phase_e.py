"""
Tests des endpoints de la couche corpus (phase E).
/ Corpus layer endpoint tests (phase E).

LOCALISATION : front/tests/test_corpus_phase_e.py

SPEC-corpus § 9 : CarnetViewSet (AllowAny, controle PAR OBJET, reponses
HTML) et les endpoints de note (ajouter, retirer, categoriser, epingler).
/ CarnetViewSet (AllowAny, per-object control, HTML responses) and the
note endpoints.
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


class CarnetListeEtDetailTest(TestCase):
    """GET /carnets/ et GET /carnets/{id}/. / List and detail."""

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="proprio_e_test", password="motdepasse"
        )
        self.carnet_prive = Dossier.objects.create(
            name="Carnet privé E", owner=self.proprietaire,
            visibilite=VisibiliteDossier.PRIVE,
        )
        self.carnet_public = Dossier.objects.create(
            name="Carnet public E", owner=self.proprietaire,
            visibilite=VisibiliteDossier.PUBLIC,
        )
        self.note = creer_une_page("http://exemple.local/note-e-detail")
        ranger_une_note_dans_un_carnet(self.note, self.carnet_public, self.proprietaire)

    def test_anonyme_liste_les_carnets_publics_seulement(self):
        reponse = self.client.get("/carnets/")
        contenu = reponse.content.decode("utf-8")

        self.assertEqual(reponse.status_code, 200)
        self.assertIn("Carnet public E", contenu)
        self.assertNotIn("Carnet privé E", contenu)

    def test_le_proprietaire_liste_ses_carnets(self):
        self.client.force_login(self.proprietaire)
        reponse = self.client.get("/carnets/")
        contenu = reponse.content.decode("utf-8")

        self.assertIn("Carnet privé E", contenu)
        self.assertIn("Carnet public E", contenu)

    def test_anonyme_lit_un_carnet_public(self):
        reponse = self.client.get(f"/carnets/{self.carnet_public.pk}/")
        contenu = reponse.content.decode("utf-8")

        self.assertEqual(reponse.status_code, 200)
        self.assertIn(self.note.title, contenu)

    def test_anonyme_refuse_sur_un_carnet_prive(self):
        reponse = self.client.get(f"/carnets/{self.carnet_prive.pk}/")
        self.assertEqual(reponse.status_code, 403)

    def test_les_reponses_sont_du_html_jamais_du_json(self):
        reponse = self.client.get(f"/carnets/{self.carnet_public.pk}/")
        self.assertIn("text/html", reponse["Content-Type"])


class NotesFiltreesParFacettesTest(TestCase):
    """GET /carnets/{id}/notes/ — ET entre axes, OU dans un axe (§ 8.2)."""

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="filtreur_e_test", password="motdepasse"
        )
        self.carnet = Dossier.objects.create(
            name="Veille E", owner=self.proprietaire,
            visibilite=VisibiliteDossier.PUBLIC,
        )
        self.axe_type = ListeDeCategories.objects.create(
            nom="Type", dossier=self.carnet,
        )
        self.axe_echeance = ListeDeCategories.objects.create(
            nom="Échéance", dossier=self.carnet,
        )
        self.categorie_aap = CategorieDossier.objects.create(
            liste=self.axe_type, nom="AAP",
        )
        self.categorie_subvention = CategorieDossier.objects.create(
            liste=self.axe_type, nom="Subvention",
        )
        self.categorie_ce_mois = CategorieDossier.objects.create(
            liste=self.axe_echeance, nom="Ce mois-ci",
        )

        # Trois notes aux classements distincts / Three notes, distinct tags
        self.note_aap_ce_mois = creer_une_page("http://exemple.local/aap-ce-mois")
        self.note_subvention = creer_une_page("http://exemple.local/subvention")
        self.note_sans_categorie = creer_une_page("http://exemple.local/sans-cat")

        appartenance_1 = ranger_une_note_dans_un_carnet(
            self.note_aap_ce_mois, self.carnet, self.proprietaire
        )
        appartenance_1.categories.add(self.categorie_aap, self.categorie_ce_mois)
        appartenance_2 = ranger_une_note_dans_un_carnet(
            self.note_subvention, self.carnet, self.proprietaire
        )
        appartenance_2.categories.add(self.categorie_subvention)
        ranger_une_note_dans_un_carnet(
            self.note_sans_categorie, self.carnet, self.proprietaire
        )

    def test_sans_filtre_toutes_les_notes(self):
        reponse = self.client.get(f"/carnets/{self.carnet.pk}/notes/")
        contenu = reponse.content.decode("utf-8")

        self.assertIn(self.note_aap_ce_mois.title, contenu)
        self.assertIn(self.note_subvention.title, contenu)
        self.assertIn(self.note_sans_categorie.title, contenu)

    def test_ou_dans_un_meme_axe(self):
        # AAP OU Subvention -> les deux notes categorisees, pas la nue.
        # / OR within one axis.
        reponse = self.client.get(
            f"/carnets/{self.carnet.pk}/notes/",
            {"categorie": [self.categorie_aap.pk, self.categorie_subvention.pk]},
        )
        contenu = reponse.content.decode("utf-8")

        self.assertIn(self.note_aap_ce_mois.title, contenu)
        self.assertIn(self.note_subvention.title, contenu)
        self.assertNotIn(self.note_sans_categorie.title, contenu)

    def test_et_entre_deux_axes(self):
        # (AAP) ET (Ce mois-ci) -> seule la note qui porte les deux.
        # / AND across two axes.
        reponse = self.client.get(
            f"/carnets/{self.carnet.pk}/notes/",
            {"categorie": [self.categorie_aap.pk, self.categorie_ce_mois.pk]},
        )
        contenu = reponse.content.decode("utf-8")

        self.assertIn(self.note_aap_ce_mois.title, contenu)
        self.assertNotIn(self.note_subvention.title, contenu)
        self.assertNotIn(self.note_sans_categorie.title, contenu)


class AjouterEtRetirerDUnCarnetTest(TestCase):
    """POST /notes/{id}/carnets/ et DELETE /notes/{id}/carnets/{carnet_id}/."""

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="rangeur_e_test", password="motdepasse"
        )
        self.autre = Utilisateur.objects.create_user(
            username="autre_e_test", password="motdepasse"
        )
        self.carnet_origine = Dossier.objects.create(
            name="Origine E", owner=self.proprietaire,
        )
        self.carnet_cible = Dossier.objects.create(
            name="Cible E", owner=self.proprietaire,
        )
        self.note = creer_une_page(
            "http://exemple.local/note-e-rangement", owner=self.proprietaire,
        )
        ranger_une_note_dans_un_carnet(
            self.note, self.carnet_origine, self.proprietaire
        )

    def test_ajouter_a_un_second_carnet(self):
        self.client.force_login(self.proprietaire)
        reponse = self.client.post(
            f"/notes/{self.note.pk}/carnets/",
            {"carnet_id": self.carnet_cible.pk},
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(self.note.appartenances_dossiers.count(), 2)

    def test_ajouter_exige_l_ecriture_sur_le_carnet_cible(self):
        carnet_d_autrui = Dossier.objects.create(
            name="Carnet d'autrui E", owner=self.autre,
        )
        self.client.force_login(self.proprietaire)
        reponse = self.client.post(
            f"/notes/{self.note.pk}/carnets/",
            {"carnet_id": carnet_d_autrui.pk},
        )

        self.assertEqual(reponse.status_code, 403)
        self.assertEqual(self.note.appartenances_dossiers.count(), 1)

    def test_ajouter_exige_l_acces_a_la_note(self):
        # On ne peut pas ranger (et donc exposer) une note qu'on ne peut
        # pas lire. / You cannot file (and expose) a note you cannot read.
        note_privee_d_autrui = creer_une_page(
            "http://exemple.local/note-privee-autrui", owner=self.autre,
        )
        carnet_prive_d_autrui = Dossier.objects.create(
            name="Privé d'autrui E", owner=self.autre,
            visibilite=VisibiliteDossier.PRIVE,
        )
        ranger_une_note_dans_un_carnet(
            note_privee_d_autrui, carnet_prive_d_autrui, self.autre
        )

        self.client.force_login(self.proprietaire)
        reponse = self.client.post(
            f"/notes/{note_privee_d_autrui.pk}/carnets/",
            {"carnet_id": self.carnet_cible.pk},
        )

        self.assertEqual(reponse.status_code, 403)

    def test_retirer_d_un_carnet_ne_supprime_jamais_la_note(self):
        ranger_une_note_dans_un_carnet(
            self.note, self.carnet_cible, self.proprietaire
        )
        self.client.force_login(self.proprietaire)

        reponse = self.client.delete(
            f"/notes/{self.note.pk}/carnets/{self.carnet_origine.pk}/"
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(self.note.appartenances_dossiers.count(), 1)
        self.assertTrue(Page.objects.filter(pk=self.note.pk).exists())
        self.note.refresh_from_db()
        self.assertEqual(self.note.dossier_id, self.carnet_cible.pk)

    def test_le_proprietaire_retire_sa_note_d_un_carnet_qu_il_n_ecrit_pas(self):
        # DECISION (8 aout, securite d'abord) : un tiers peut ranger ma
        # note dans son carnet public et la rendre publique — je dois
        # pouvoir l'en sortir MEME sans ecriture sur ce carnet.
        # Regle : ecriture sur le carnet OU propriete de la note.
        # / DECISION: note owner can remove their note from any notebook,
        # even without write access to it.
        carnet_public_d_autrui = Dossier.objects.create(
            name="Public d'autrui E", owner=self.autre,
            visibilite=VisibiliteDossier.PUBLIC,
        )
        ranger_une_note_dans_un_carnet(
            self.note, carnet_public_d_autrui, self.autre
        )

        self.client.force_login(self.proprietaire)
        reponse = self.client.delete(
            f"/notes/{self.note.pk}/carnets/{carnet_public_d_autrui.pk}/"
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(
            self.note.appartenances_dossiers.filter(
                dossier=carnet_public_d_autrui
            ).exists()
        )

    def test_un_tiers_sans_droit_ne_retire_rien(self):
        # Le symetrique : ni ecriture sur le carnet, ni propriete de la
        # note -> refus. / Neither right -> refusal.
        tiers = Utilisateur.objects.create_user(
            username="tiers_retrait_e", password="motdepasse"
        )
        self.client.force_login(tiers)
        reponse = self.client.delete(
            f"/notes/{self.note.pk}/carnets/{self.carnet_origine.pk}/"
        )
        self.assertEqual(reponse.status_code, 403)
        self.assertTrue(
            self.note.appartenances_dossiers.filter(
                dossier=self.carnet_origine
            ).exists()
        )

    def test_anonyme_ne_range_rien(self):
        reponse = self.client.post(
            f"/notes/{self.note.pk}/carnets/",
            {"carnet_id": self.carnet_cible.pk},
        )
        self.assertIn(reponse.status_code, (401, 403))


class SecuriteDesEndpointsTest(TestCase):
    """
    Les trous releves par la relecture E : IDOR, fuites, entrees hostiles.
    / Holes raised by review E: IDOR, leaks, hostile input.
    """

    def setUp(self):
        self.curieux = Utilisateur.objects.create_user(
            username="curieux_e_test", password="motdepasse"
        )
        self.discret = Utilisateur.objects.create_user(
            username="discret_e_test", password="motdepasse"
        )
        self.carnet_du_curieux = Dossier.objects.create(
            name="Carnet du curieux", owner=self.curieux,
        )
        self.carnet_prive_du_discret = Dossier.objects.create(
            name="Carnet secret du discret", owner=self.discret,
            visibilite=VisibiliteDossier.PRIVE,
        )
        self.carnet_public = Dossier.objects.create(
            name="Carnet public partagé", owner=self.discret,
            visibilite=VisibiliteDossier.PUBLIC,
        )
        # La note du discret : dans SON carnet prive ET dans un public.
        # / The discreet user's note: in THEIR private notebook AND a
        # public one.
        self.note_du_discret = creer_une_page(
            "http://exemple.local/note-discrete", owner=self.discret,
        )
        ranger_une_note_dans_un_carnet(
            self.note_du_discret, self.carnet_prive_du_discret, self.discret
        )
        ranger_une_note_dans_un_carnet(
            self.note_du_discret, self.carnet_public, self.discret
        )

    def test_retirer_une_note_absente_du_carnet_donne_404(self):
        # IDOR (relecture E, bloquant 1) : retirer une note d'un carnet ou
        # elle n'est PAS ne doit rien reveler — 404, pas le bloc des
        # carnets de la note. / Removing from a notebook the note is NOT
        # in must reveal nothing — 404.
        self.client.force_login(self.curieux)
        reponse = self.client.delete(
            f"/notes/{self.note_du_discret.pk}/carnets/{self.carnet_du_curieux.pk}/"
        )

        self.assertEqual(reponse.status_code, 404)
        contenu = reponse.content.decode("utf-8")
        self.assertNotIn("Carnet secret du discret", contenu)

    def test_le_bloc_carnets_ne_montre_que_les_carnets_accessibles(self):
        # Fuite (relecture E, bloquant 2) : le bloc « Dans N carnets »
        # rendu au curieux ne doit pas nommer le carnet prive du discret.
        # / The "In N notebooks" block must not name another user's
        # private notebook.
        self.client.force_login(self.curieux)
        reponse = self.client.post(
            f"/notes/{self.note_du_discret.pk}/carnets/",
            {"carnet_id": self.carnet_du_curieux.pk},
        )

        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode("utf-8")
        self.assertIn("Carnet du curieux", contenu)
        self.assertIn("Carnet public partagé", contenu)
        self.assertNotIn("Carnet secret du discret", contenu)

    def test_categorie_non_numerique_ne_fait_pas_de_500(self):
        # Entree hostile (relecture E, bloquant 3) : ?categorie=abc doit
        # etre ignore, jamais un 500. / Hostile input must never 500.
        reponse = self.client.get(
            f"/carnets/{self.carnet_public.pk}/notes/",
            {"categorie": ["abc", "1e9", ""]},
        )
        self.assertEqual(reponse.status_code, 200)

    def test_notes_filtrees_d_un_carnet_prive_refusees_a_l_anonyme(self):
        reponse = self.client.get(
            f"/carnets/{self.carnet_prive_du_discret.pk}/notes/"
        )
        self.assertEqual(reponse.status_code, 403)

    def test_creer_une_categorie_exige_l_ecriture(self):
        self.client.force_login(self.curieux)
        reponse = self.client.post(
            f"/carnets/{self.carnet_prive_du_discret.pk}/categories/",
            {"action": "creer_liste", "nom": "Intrusion"},
        )
        self.assertEqual(reponse.status_code, 403)
        self.assertFalse(
            ListeDeCategories.objects.filter(
                dossier=self.carnet_prive_du_discret
            ).exists()
        )

    def test_une_version_ne_se_range_pas(self):
        # Spec § 11 : l'interface n'offre pas de ranger une version
        # separement — l'endpoint non plus. / Versions cannot be filed.
        version = Page.objects.create(
            url=None,
            html_original="<p>o</p>",
            html_readability="<p>l</p>",
            text_readability="texte",
            content_hash="hash-version-e",
            parent_page=self.note_du_discret,
            version_number=2,
            owner=self.discret,
        )
        self.client.force_login(self.discret)
        reponse = self.client.post(
            f"/notes/{version.pk}/carnets/",
            {"carnet_id": self.carnet_public.pk},
        )
        self.assertEqual(reponse.status_code, 404)
        self.assertEqual(version.appartenances_dossiers.count(), 0)


class CategoriserEtEpinglerTest(TestCase):
    """POST .../categories/ et .../epingler/. / Categorize and pin."""

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="categoriseur_e_test", password="motdepasse"
        )
        self.carnet = Dossier.objects.create(
            name="Carnet catégories E", owner=self.proprietaire,
        )
        self.autre_carnet = Dossier.objects.create(
            name="Autre carnet E", owner=self.proprietaire,
        )
        self.liste = ListeDeCategories.objects.create(
            nom="Type", dossier=self.carnet,
        )
        self.categorie = CategorieDossier.objects.create(
            liste=self.liste, nom="Budget",
        )
        liste_de_l_autre = ListeDeCategories.objects.create(
            nom="Type", dossier=self.autre_carnet,
        )
        self.categorie_etrangere = CategorieDossier.objects.create(
            liste=liste_de_l_autre, nom="Étrangère",
        )
        self.note = creer_une_page("http://exemple.local/note-e-categories")
        self.appartenance = ranger_une_note_dans_un_carnet(
            self.note, self.carnet, self.proprietaire
        )

    def test_categoriser_pose_les_categories_de_la_relation(self):
        self.client.force_login(self.proprietaire)
        reponse = self.client.post(
            f"/notes/{self.note.pk}/carnets/{self.carnet.pk}/categories/",
            {"categorie_ids": [self.categorie.pk]},
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(
            list(self.appartenance.categories.values_list("nom", flat=True)),
            ["Budget"],
        )

    def test_categorie_etrangere_refusee_en_erreur_de_formulaire(self):
        self.client.force_login(self.proprietaire)
        reponse = self.client.post(
            f"/notes/{self.note.pk}/carnets/{self.carnet.pk}/categories/",
            {"categorie_ids": [self.categorie_etrangere.pk]},
        )

        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(self.appartenance.categories.count(), 0)

    def test_liste_vide_decoche_tout(self):
        self.appartenance.categories.add(self.categorie)
        self.client.force_login(self.proprietaire)

        reponse = self.client.post(
            f"/notes/{self.note.pk}/carnets/{self.carnet.pk}/categories/",
            {"categorie_ids": []},
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(self.appartenance.categories.count(), 0)

    def test_epingler_bascule(self):
        self.client.force_login(self.proprietaire)

        self.client.post(
            f"/notes/{self.note.pk}/carnets/{self.carnet.pk}/epingler/"
        )
        self.appartenance.refresh_from_db()
        self.assertTrue(self.appartenance.epinglee)

        self.client.post(
            f"/notes/{self.note.pk}/carnets/{self.carnet.pk}/epingler/"
        )
        self.appartenance.refresh_from_db()
        self.assertFalse(self.appartenance.epinglee)


class ReordonnerTest(TestCase):
    """POST /carnets/{id}/reordonner/. / Manual reordering."""

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="ordonnateur_e_test", password="motdepasse"
        )
        self.carnet = Dossier.objects.create(
            name="Carnet ordre E", owner=self.proprietaire,
        )
        self.premiere = creer_une_page("http://exemple.local/ordre-1")
        self.seconde = creer_une_page("http://exemple.local/ordre-2")
        self.appartenance_premiere = ranger_une_note_dans_un_carnet(
            self.premiere, self.carnet, self.proprietaire
        )
        self.appartenance_seconde = ranger_une_note_dans_un_carnet(
            self.seconde, self.carnet, self.proprietaire
        )

    def test_reordonner_ecrit_l_ordre_manuel(self):
        self.client.force_login(self.proprietaire)
        reponse = self.client.post(
            f"/carnets/{self.carnet.pk}/reordonner/",
            {"page_ids": [self.seconde.pk, self.premiere.pk]},
        )

        self.assertEqual(reponse.status_code, 200)
        self.appartenance_premiere.refresh_from_db()
        self.appartenance_seconde.refresh_from_db()
        self.assertEqual(self.appartenance_seconde.ordre_manuel, 1)
        self.assertEqual(self.appartenance_premiere.ordre_manuel, 2)

    def test_reordonner_exige_l_ecriture(self):
        visiteur = Utilisateur.objects.create_user(
            username="visiteur_ordre_e", password="motdepasse"
        )
        self.client.force_login(visiteur)
        reponse = self.client.post(
            f"/carnets/{self.carnet.pk}/reordonner/",
            {"page_ids": [self.seconde.pk, self.premiere.pk]},
        )
        self.assertEqual(reponse.status_code, 403)


class GererCategoriesTest(TestCase):
    """GET/POST /carnets/{id}/categories/. / Axis and category management."""

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="gestionnaire_e_test", password="motdepasse"
        )
        self.carnet = Dossier.objects.create(
            name="Carnet gestion E", owner=self.proprietaire,
        )

    def test_creer_un_axe_et_une_categorie(self):
        self.client.force_login(self.proprietaire)

        reponse_axe = self.client.post(
            f"/carnets/{self.carnet.pk}/categories/",
            {"action": "creer_liste", "nom": "Territoire"},
        )
        self.assertEqual(reponse_axe.status_code, 200)
        liste_creee = ListeDeCategories.objects.get(
            dossier=self.carnet, nom="Territoire"
        )

        reponse_categorie = self.client.post(
            f"/carnets/{self.carnet.pk}/categories/",
            {"action": "creer_categorie", "liste_id": liste_creee.pk,
             "nom": "Régional"},
        )
        self.assertEqual(reponse_categorie.status_code, 200)
        self.assertTrue(
            CategorieDossier.objects.filter(
                liste=liste_creee, nom="Régional"
            ).exists()
        )

    def test_lecture_des_axes(self):
        liste = ListeDeCategories.objects.create(nom="Type", dossier=self.carnet)
        CategorieDossier.objects.create(liste=liste, nom="Budget")

        self.client.force_login(self.proprietaire)
        reponse = self.client.get(f"/carnets/{self.carnet.pk}/categories/")
        contenu = reponse.content.decode("utf-8")

        self.assertIn("Type", contenu)
        self.assertIn("Budget", contenu)
