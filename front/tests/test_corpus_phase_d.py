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


# Le nombre de requetes de `/carnets/` (§ 5.3), MESURE le 12 aout 2026 :
# session + auth, les carnets visibles annotes, leurs appartenances de
# bases prefetchees, et les deux totaux de l'en-tete. Il est stable a
# 8 pour 3 carnets/10 notes ET pour 6 carnets/20 notes — c'est cette
# INDEPENDANCE que le test verrouille, pas le nombre lui-meme.
# / Measured query count for /carnets/: stable at 8 for 3 notebooks/10
# notes AND for 6 notebooks/20 notes. The test locks the independence.
NOMBRE_DE_REQUETES_DE_LA_COLLECTION = 8


class NoteDansPlusieursCarnetsTest(TestCase):
    """
    Une note rangee dans deux carnets apparait dans LES DEUX.
    / A note filed in two notebooks appears in BOTH.

    CE QUE CETTE CLASSE PROTEGE N'A PAS BOUGE : la phase D a fait passer
    l'affichage de la FK `page.dossier` a la table de liaison
    `AppartenancePageDossier`, et c'est ce basculement qu'on verrouille.

    CE QUI A BOUGE, C'EST LE LECTEUR. Les trois tests interrogeaient
    `/arbre/`, la route du tiroir lateral, retiree le 12 aout 2026. Ils
    interrogent desormais les deux ecrans qui montrent la meme chose :
    la page d'un carnet pour ses notes, la collection pour ses compteurs.
    / The rule is unchanged; only the reader moved from the removed
    /arbre/ route to /carnets/ and /carnets/<id>/.
    """

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
        # LE comportement que la phase D debloque : avant elle, la vue
        # lisait la FK et la note n'apparaissait que sous un seul carnet.
        # / THE behaviour phase D unlocks: the note under BOTH notebooks.
        note = creer_une_page("http://exemple.local/note-arbre-double")
        ranger_une_note_dans_un_carnet(note, self.carnet_conseil, self.utilisateur)
        ranger_une_note_dans_un_carnet(note, self.carnet_veille, self.utilisateur)

        for carnet in [self.carnet_conseil, self.carnet_veille]:
            reponse = self.client.get(
                f"/carnets/{carnet.pk}/", HTTP_HX_REQUEST="true",
            )
            self.assertEqual(reponse.status_code, 200)
            self.assertIn(
                f'data-page-id="{note.pk}"',
                reponse.content.decode("utf-8"),
                f"La note doit apparaitre dans « {carnet.name} » : elle "
                f"est rangee dans les DEUX carnets.",
            )

    def test_les_compteurs_suivent_les_appartenances(self):
        note = creer_une_page("http://exemple.local/note-compteur")
        ranger_une_note_dans_un_carnet(note, self.carnet_conseil, self.utilisateur)
        ranger_une_note_dans_un_carnet(note, self.carnet_veille, self.utilisateur)

        reponse = self.client.get("/carnets/", HTTP_HX_REQUEST="true")
        contenu = reponse.content.decode("utf-8")

        # On mesure LIGNE PAR LIGNE, pas sur la page entiere : l'en-tete
        # annonce lui aussi « 1 note » (le total DISTINCT — une note
        # rangee deux fois ne compte qu'une), et un simple `count()` sur
        # tout le document melangerait les deux registres.
        # / Measured row by row: the header also says "1 note" (the
        # DISTINCT total), so counting over the whole page would mix
        # two different statements.
        lignes_de_carnet = contenu.split('data-testid="corpus-carnet-item"')[1:]
        self.assertEqual(len(lignes_de_carnet), 2)
        for ligne in lignes_de_carnet:
            self.assertIn("1 note", ligne)

    def test_la_collection_ne_fait_pas_de_n_plus_un(self):
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

        # Compte MESURE sur la collection (les compteurs sont annotes en
        # une requete, les etiquettes prefetchees). Il est INDEPENDANT du
        # nombre de notes ET du nombre de carnets : c'est ce qu'il
        # verrouille. Toute derive future cassera ce test.
        # / Measured count, independent of note AND notebook counts.
        with self.assertNumQueries(NOMBRE_DE_REQUETES_DE_LA_COLLECTION):
            reponse = self.client.get("/carnets/", HTTP_HX_REQUEST="true")
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
