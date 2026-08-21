"""
Qui doit apprendre qu'un wiki a bouge.
/ Who must learn that a wiki moved.

LOCALISATION : core/tests/test_destinataires_de_wiki.py

SPEC-synthese, addendum du 21 aout 2026 : le perimetre est plus large
que celui du bouton « taches » — il porte aussi les PARTAGES du carnet,
utilisateurs directs et membres des groupes. Un collectif qui lit un
carnet doit apprendre que son article a change ; sinon seul le
proprietaire suit l'article, et les autres relisent a l'aveugle.
/ The scope includes notebook shares, unlike the tasks button.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (
    Dossier, DossierPartage, GroupeUtilisateurs, Page, TypeDeNote, Wiki,
)
from core.services.corpus import ranger_une_note_dans_un_carnet
from core.services.destinataires_de_wiki import destinataires_d_un_wiki

Utilisateur = get_user_model()


def creer_une_page(url_unique, **champs):
    """Cree une page minimale. / Minimal page."""
    return Page.objects.create(
        url=url_unique,
        html_original="<p>o</p>",
        html_readability="<p>l</p>",
        text_readability="texte",
        content_hash=f"hash-{url_unique}",
        title=f"Note {url_unique[-10:]}",
        **champs,
    )


class DestinatairesDUnWikiTest(TestCase):
    """destinataires_d_un_wiki : le perimetre. / The recipient scope."""

    def setUp(self):
        self.proprietaire_du_carnet = Utilisateur.objects.create_user(
            username="proprietaire_carnet", password="motdepasse",
            email="carnet@exemple.local",
        )
        self.proprietaire_de_l_article = Utilisateur.objects.create_user(
            username="proprietaire_article", password="motdepasse",
            email="article@exemple.local",
        )
        self.carnet = Dossier.objects.create(
            name="Carnet partagé", owner=self.proprietaire_du_carnet,
        )
        self.article = creer_une_page(
            "http://exemple.local/dw-article",
            type_de_note=TypeDeNote.WIKI,
            owner=self.proprietaire_de_l_article,
        )
        ranger_une_note_dans_un_carnet(
            self.article, self.carnet, self.proprietaire_du_carnet,
        )
        self.wiki = Wiki.objects.create(
            page=self.article, dossier=self.carnet, sujet="Le partage",
        )

    def test_le_proprietaire_de_l_article_et_celui_du_carnet(self):
        destinataires = destinataires_d_un_wiki(self.wiki)

        self.assertIn(self.proprietaire_de_l_article, destinataires)
        self.assertIn(self.proprietaire_du_carnet, destinataires)

    def test_un_partage_direct_est_destinataire(self):
        lectrice = Utilisateur.objects.create_user(
            username="lectrice_partagee", password="motdepasse",
            email="lectrice@exemple.local",
        )
        DossierPartage.objects.create(
            dossier=self.carnet, utilisateur=lectrice,
        )

        self.assertIn(lectrice, destinataires_d_un_wiki(self.wiki))

    def test_les_membres_d_un_groupe_partage_sont_destinataires(self):
        membre = Utilisateur.objects.create_user(
            username="membre_du_groupe", password="motdepasse",
            email="membre@exemple.local",
        )
        groupe = GroupeUtilisateurs.objects.create(
            nom="Groupe de lecture", owner=self.proprietaire_du_carnet,
        )
        groupe.membres.add(membre)
        DossierPartage.objects.create(dossier=self.carnet, groupe=groupe)

        self.assertIn(membre, destinataires_d_un_wiki(self.wiki))

    def test_un_destinataire_sans_adresse_est_ecarte(self):
        # Un mail ne part pas vers une adresse vide : le compter
        # ferait croire a un envoi qui n'a jamais eu lieu.
        # / No address, no recipient.
        sans_adresse = Utilisateur.objects.create_user(
            username="sans_adresse", password="motdepasse", email="",
        )
        DossierPartage.objects.create(
            dossier=self.carnet, utilisateur=sans_adresse,
        )

        self.assertNotIn(sans_adresse, destinataires_d_un_wiki(self.wiki))

    def test_personne_n_est_compte_deux_fois(self):
        # Le proprietaire du carnet peut aussi etre destinataire d'un
        # partage : un seul mail, pas deux. / Deduplicated.
        DossierPartage.objects.create(
            dossier=self.carnet, utilisateur=self.proprietaire_du_carnet,
        )

        destinataires = destinataires_d_un_wiki(self.wiki)
        identifiants = [utilisateur.pk for utilisateur in destinataires]

        self.assertEqual(len(identifiants), len(set(identifiants)))
