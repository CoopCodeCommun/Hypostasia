"""
Tests de la bascule des lecteurs vers la table de liaison (phase D).
/ Reader-conversion tests to the link table (phase D).

LOCALISATION : front/tests/test_corpus_phase_d.py

SPEC-corpus § 4.3 : apres la bascule, toute lecture passe par la table de
liaison. Le comportement NOUVEAU verrouille ici : une note rangee dans deux
carnets apparait dans les deux, le perimetre de dedup et l'alignement la
voient par ses appartenances, et l'arbre se rend sans N+1.
/ After the switch, every read goes through the link table.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import Dossier, Page, VisibiliteDossier
from core.services.corpus import ranger_une_note_dans_un_carnet
from front.tasks import _destinataires_de_notification

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
        title=f"Note {url_unique[-12:]}",
    )


class ArbreMultiCarnetsTest(TestCase):
    """L'arbre montre une note dans CHACUN de ses carnets. / Tree shows both."""

    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            username="arboriste_test", password="motdepasse"
        )
        self.client.force_login(self.utilisateur)
        self.carnet_conseil = Dossier.objects.create(
            name="Conseil arbre test", owner=self.utilisateur
        )
        self.carnet_veille = Dossier.objects.create(
            name="Veille arbre test", owner=self.utilisateur
        )

    def test_une_note_dans_deux_carnets_apparait_sous_les_deux(self):
        # LE comportement que la phase D debloque : avant elle, l'arbre
        # lisait la FK et la note n'apparaissait que sous un seul carnet.
        # / THE behaviour phase D unlocks: the note under BOTH notebooks.
        note = creer_une_page("http://exemple.local/note-arbre-double")
        ranger_une_note_dans_un_carnet(note, self.carnet_conseil, self.utilisateur)
        ranger_une_note_dans_un_carnet(note, self.carnet_veille, self.utilisateur)

        reponse = self.client.get("/arbre/")
        contenu = reponse.content.decode("utf-8")

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(
            contenu.count(f'data-page-id="{note.pk}"'),
            2,
            "La note doit apparaitre sous ses DEUX carnets",
        )

    def test_les_compteurs_de_l_arbre_suivent_les_appartenances(self):
        note = creer_une_page("http://exemple.local/note-compteur")
        ranger_une_note_dans_un_carnet(note, self.carnet_conseil, self.utilisateur)
        ranger_une_note_dans_un_carnet(note, self.carnet_veille, self.utilisateur)

        reponse = self.client.get("/arbre/")
        contenu = reponse.content.decode("utf-8")

        # Chaque carnet compte 1 : data-ctx-pages="1" present pour les deux.
        # / Each notebook counts 1.
        self.assertEqual(contenu.count('data-ctx-pages="1"'), 2)

    def test_l_arbre_ne_fait_pas_de_n_plus_un(self):
        # § 5.3 : le compte de requetes de la vue de liste principale est
        # verrouille. 10 notes dans 3 carnets ne doivent pas ajouter une
        # requete par note ni par compteur affiche.
        # / § 5.3: the main list view's query count is locked.
        troisieme_carnet = Dossier.objects.create(
            name="Troisième arbre test", owner=self.utilisateur
        )
        for numero in range(10):
            note = creer_une_page(f"http://exemple.local/note-n1-{numero}")
            ranger_une_note_dans_un_carnet(
                note, [self.carnet_conseil, self.carnet_veille, troisieme_carnet][numero % 3],
                self.utilisateur,
            )

        # 9 requetes mesurees (session/auth + les 3 sections et leur
        # prefetch), INDEPENDANT du nombre de notes ET du nombre de
        # dossiers — les en-tetes comptent dans les appartenances
        # prechargees (relecture D : l'ancienne version a 12 absorbait
        # 1 COUNT par dossier). Toute derive future cassera ce test.
        # / 9 queries, independent of note AND folder counts — headers
        # count from the prefetched memberships.
        with self.assertNumQueries(9):
            reponse = self.client.get("/arbre/")
        self.assertEqual(reponse.status_code, 200)


class DedupParLesAppartenancesTest(TestCase):
    """Le perimetre de dedup de POST /api/pages/ lit la liaison. / Dedup scope."""

    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            username="dedup_test", password="motdepasse"
        )
        self.carnet = Dossier.objects.create(
            name="Carnet dedup", owner=self.utilisateur
        )

    def test_un_contenu_range_dans_mon_carnet_en_second_est_vu_par_la_dedup(self):
        # LE CAS QUE SEULE LA TABLE DE LIAISON VOIT : la note d'un autre
        # utilisateur, dont la FK pointe SON carnet, est aussi rangee dans
        # le mien (second carnet). L'ancienne dedup (FK) ne la voyait pas ;
        # la nouvelle (appartenances) la voit → 409.
        # / THE case only the link table sees: another user's note whose
        # FK points to THEIR notebook, also filed in mine. Old FK-based
        # dedup missed it; the membership-based one catches it.
        from rest_framework.authtoken.models import Token

        auteur = Utilisateur.objects.create_user(
            username="auteur_dedup_test", password="motdepasse"
        )
        carnet_de_l_auteur = Dossier.objects.create(
            name="Carnet de l'auteur", owner=auteur
        )
        note_partagee = Page.objects.create(
            url="http://exemple.local/page-de-l-auteur",
            html_original="<p>o</p>",
            html_readability="<p>l</p>",
            text_readability="texte",
            content_hash="hash-commun-dedup",
            owner=auteur,
        )
        # FK -> carnet de l'auteur (premier carnet), puis rangement dans
        # MON carnet (second). / FK to author's notebook, then mine.
        ranger_une_note_dans_un_carnet(note_partagee, carnet_de_l_auteur, auteur)
        ranger_une_note_dans_un_carnet(note_partagee, self.carnet, auteur)

        jeton = Token.objects.create(user=self.utilisateur)
        reponse = self.client.post(
            "/api/pages/",
            data={
                "url": "http://exemple.local/ma-recapture-du-meme-contenu",
                "title": "Recapture",
                "html_original": "<p>o</p>",
                "html_readability": "<p>l</p>",
                "text_readability": "texte",
                "content_hash": "hash-commun-dedup",
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Token {jeton.key}",
        )
        self.assertEqual(reponse.status_code, 409)


class NotificationsElargiesTest(TestCase):
    """§ 11 : owner + proprietaires des carnets, dedoublonnes. / Widened targets."""

    def setUp(self):
        self.auteur = Utilisateur.objects.create_user(
            username="auteur_notif_test", password="motdepasse"
        )
        self.proprietaire_de_carnet = Utilisateur.objects.create_user(
            username="proprio_notif_test", password="motdepasse"
        )

    def test_owner_et_proprietaires_de_carnets_dedoublonnes(self):
        carnet_du_proprio = Dossier.objects.create(
            name="Carnet notif", owner=self.proprietaire_de_carnet
        )
        carnet_de_l_auteur = Dossier.objects.create(
            name="Carnet auteur notif", owner=self.auteur
        )
        note = creer_une_page(
            "http://exemple.local/note-notif", owner=self.auteur,
        )
        ranger_une_note_dans_un_carnet(note, carnet_du_proprio, self.auteur)
        ranger_une_note_dans_un_carnet(note, carnet_de_l_auteur, self.auteur)

        destinataires = _destinataires_de_notification(note)

        # L'auteur n'apparait qu'une fois malgre ses deux titres (owner de
        # la note ET d'un carnet). / The author appears only once.
        self.assertEqual(
            destinataires,
            sorted([self.auteur.pk, self.proprietaire_de_carnet.pk]),
        )

    def test_aucun_destinataire_donne_none(self):
        note_orpheline = creer_une_page("http://exemple.local/note-notif-orpheline")
        self.assertEqual(
            _destinataires_de_notification(note_orpheline), [None]
        )
