"""
La position d'une note dans la file d'ingestion Docling.
/ A note's position in the Docling ingestion queue.

LOCALISATION : front/tests/test_position_en_file_ingestion.py

Lancer avec :
    docker exec -w /app hypostasia_web python manage.py test \\
        front.tests.test_position_en_file_ingestion \\
        --settings=hypostasia.settings_test_opus

POURQUOI UN RANG, ET POURQUOI IL TRAVERSE LES UTILISATEURS

Une ingestion Docling dure 83 s a froid et la file est servie par UN
worker a concurrence 1 : la note importee en cinquieme position attend
plusieurs minutes sans que rien ne l'explique. « En cours… » pendant six
minutes se lit comme une panne.

Le rang est le seul affichage honnete, et il oblige a compter les pages
des AUTRES utilisateurs — la file est globale, elle ne connait que des
cles de page. Decision du mainteneur (14 aout 2026) : afficher la
POSITION SEULE, sans le total. Ce qui est divulgue est un entier de
charge ; jamais un titre, un proprietaire, ni un contenu. C'est
exactement ce que dirait un temps d'attente estime.
/ The queue is global and one-at-a-time; the rank is the only honest
display. It leaks one integer of load, never a title or an owner.

LE PIEGE DU FANTOME

Un rang naif compterait les pages abandonnees par un worker mort. Une
seule d'entre elles bloquerait le compteur de tout le monde, pour
toujours. Le rang applique donc la meme regle de peremption que le reste
du fichier (DELAI_INGESTION_FANTOME_MIN).
/ A single abandoned page would freeze everyone's counter forever.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.models import EtatIngestion, Page
from front.views import DELAI_INGESTION_FANTOME_MIN

User = get_user_model()


def _creer_page_en_file(proprietaire, titre, ingestion_maj_le,
                        etat=EtatIngestion.EN_ATTENTE):
    """
    Cree une note dans un etat d'ingestion donne.
    / Creates a note in a given ingestion state.

    LOCALISATION : front/tests/test_position_en_file_ingestion.py
    """
    return Page.objects.create(
        title=titre, source_type="file", original_filename="doc.pdf",
        html_original="", html_readability="", text_readability="",
        content_hash=f"hash-{titre}", owner=proprietaire,
        ingestion_etat=etat, ingestion_maj_le=ingestion_maj_le,
    )


class RangDansLaFileDIngestionTest(TestCase):
    """
    Le calcul du rang, independamment de son affichage.
    / Rank computation, independently of its display.

    LOCALISATION : front/tests/test_position_en_file_ingestion.py
    """

    def setUp(self):
        self.moi = User.objects.create_user(username="moi", password="x")
        # Nom volontairement distinctif : un test verifie plus bas qu'il
        # n'apparait NULLE PART dans le menu, et « autre » serait un mot
        # trop courant pour que l'absence prouve quoi que ce soit.
        # / Deliberately distinctive: a test asserts it appears nowhere.
        self.quelqu_un_d_autre = User.objects.create_user(
            username="tisserand-des-neiges", password="x",
        )
        self.maintenant = timezone.now()

    def test_le_rang_compte_les_pages_des_autres_utilisateurs(self):
        # Le coeur de la decision du mainteneur : la file est globale,
        # un rang qui ne compterait que mes pages afficherait « 1er »
        # pendant que quatre notes d'autrui passent devant.
        # / The queue is global: a self-only rank would say "1st" while
        # four other people's notes go first.
        from front.views_taches import _rangs_dans_la_file_d_ingestion

        _creer_page_en_file(
            self.quelqu_un_d_autre, "devant-1",
            self.maintenant - timedelta(seconds=30),
        )
        _creer_page_en_file(
            self.quelqu_un_d_autre, "devant-2",
            self.maintenant - timedelta(seconds=20),
        )
        ma_page = _creer_page_en_file(
            self.moi, "la-mienne", self.maintenant - timedelta(seconds=10),
        )

        rangs = _rangs_dans_la_file_d_ingestion()

        self.assertEqual(rangs[ma_page.pk], 3)

    def test_une_page_fantome_ne_bloque_pas_le_compteur(self):
        # Sans cette exclusion, une note abandonnee par un worker mort
        # decalerait le rang de TOUS les utilisateurs, definitivement.
        # / Without this, one abandoned note shifts everyone's rank
        # forever.
        from front.views_taches import _rangs_dans_la_file_d_ingestion

        _creer_page_en_file(
            self.quelqu_un_d_autre, "fantome",
            self.maintenant - timedelta(minutes=DELAI_INGESTION_FANTOME_MIN + 1),
        )
        ma_page = _creer_page_en_file(
            self.moi, "la-mienne", self.maintenant,
        )

        rangs = _rangs_dans_la_file_d_ingestion()

        self.assertEqual(rangs[ma_page.pk], 1)

    def test_une_page_sans_date_ne_compte_pas(self):
        # Meme regle que _calculer_etat_bouton : sans date, rien ne
        # prouve la recence — c'est un fantome.
        # / Same rule as the badge counter: no date, no proof of recency.
        from front.views_taches import _rangs_dans_la_file_d_ingestion

        _creer_page_en_file(self.quelqu_un_d_autre, "sans-date", None)
        ma_page = _creer_page_en_file(self.moi, "la-mienne", self.maintenant)

        rangs = _rangs_dans_la_file_d_ingestion()

        self.assertEqual(rangs[ma_page.pk], 1)

    def test_une_page_en_cours_n_est_plus_dans_la_file(self):
        # EN_COURS = deja sortie de la file, elle est sur le worker.
        # La compter reculerait tout le monde d'un cran.
        # / EN_COURS has already left the queue; counting it would push
        # everyone back one place.
        from front.views_taches import _rangs_dans_la_file_d_ingestion

        page_en_cours = _creer_page_en_file(
            self.quelqu_un_d_autre, "sur-le-worker",
            self.maintenant - timedelta(seconds=30),
            etat=EtatIngestion.EN_COURS,
        )
        ma_page = _creer_page_en_file(self.moi, "la-mienne", self.maintenant)

        rangs = _rangs_dans_la_file_d_ingestion()

        self.assertEqual(rangs[ma_page.pk], 1)
        self.assertNotIn(page_en_cours.pk, rangs)

    def test_le_rang_est_deterministe_a_date_egale(self):
        """
        Deux imports dans la meme microseconde recoivent deux rangs.
        / Two same-microsecond imports get two distinct ranks.

        LOCALISATION : front/tests/test_position_en_file_ingestion.py

        TEST DISCRIMINANT, ET IL A FALLU LE RENDRE TEL

        Une premiere version creait les deux pages dans l'ordre des pk
        croissants. Elle passait au vert MEME sans `"pk"` dans le
        `order_by` : sur une table fraiche, PostgreSQL rend les lignes
        dans l'ordre d'insertion, qui coincide alors avec l'ordre voulu
        (relecture adverse du 14 aout 2026).

        Ici, la page qui doit sortir PREMIERE est creee EN SECOND. Son
        pk est donc le plus grand, et l'ordre d'insertion joue CONTRE le
        resultat attendu : seul un tri effectif peut le produire.
        / The page that must come first is created second, so insertion
        order works against the expected result.
        """
        from front.views_taches import _rangs_dans_la_file_d_ingestion

        creee_en_premier = _creer_page_en_file(self.moi, "a", self.maintenant)
        creee_en_second = _creer_page_en_file(self.moi, "b", self.maintenant)

        rangs = _rangs_dans_la_file_d_ingestion()

        self.assertEqual(
            sorted([rangs[creee_en_premier.pk], rangs[creee_en_second.pk]]),
            [1, 2],
        )
        # A date egale, le plus petit pk passe devant : c'est la seule
        # regle stable d'un rafraichissement a l'autre.
        # / Smallest pk wins: the only rule stable across refreshes.
        self.assertLess(rangs[creee_en_premier.pk], rangs[creee_en_second.pk])

    def test_le_rang_suit_la_date_et_non_l_ordre_de_creation(self):
        # Le vrai depart : une page mise en file APRES coup (pk plus
        # grand) mais horodatee AVANT doit passer devant. Sans tri
        # effectif sur la date, l'ordre d'insertion l'emporterait.
        # / A later-created but earlier-dated page must come first.
        from front.views_taches import _rangs_dans_la_file_d_ingestion

        arrivee_en_second = _creer_page_en_file(
            self.moi, "arrivee-apres", self.maintenant,
        )
        arrivee_en_premier = _creer_page_en_file(
            self.moi, "arrivee-avant", self.maintenant - timedelta(seconds=60),
        )

        rangs = _rangs_dans_la_file_d_ingestion()

        self.assertEqual(rangs[arrivee_en_premier.pk], 1)
        self.assertEqual(rangs[arrivee_en_second.pk], 2)


class AffichageDeLaPositionDansLeDropdownTest(TestCase):
    """
    Ce que l'utilisateur lit dans le menu des taches.
    / What the user reads in the tasks dropdown.

    LOCALISATION : front/tests/test_position_en_file_ingestion.py
    """

    def setUp(self):
        self.moi = User.objects.create_user(username="moi", password="x")
        # Nom volontairement distinctif : un test verifie plus bas qu'il
        # n'apparait NULLE PART dans le menu, et « autre » serait un mot
        # trop courant pour que l'absence prouve quoi que ce soit.
        # / Deliberately distinctive: a test asserts it appears nowhere.
        self.quelqu_un_d_autre = User.objects.create_user(
            username="tisserand-des-neiges", password="x",
        )
        self.client.force_login(self.moi)
        self.maintenant = timezone.now()

    def test_une_note_en_attente_affiche_sa_position(self):
        for numero in range(2):
            _creer_page_en_file(
                self.quelqu_un_d_autre, f"devant-{numero}",
                self.maintenant - timedelta(seconds=30 - numero),
            )
        _creer_page_en_file(self.moi, "la-mienne", self.maintenant)

        reponse = self.client.get("/taches/dropdown/")

        self.assertContains(reponse, "3ᵉ dans la file")

    def test_la_premiere_de_la_file_est_annoncee_au_masculin(self):
        # « 1ᵉʳ », pas « 1ᵉ » : c'est du francais, pas une numerotation.
        # / French ordinals: first is written differently.
        _creer_page_en_file(self.moi, "la-mienne", self.maintenant)

        reponse = self.client.get("/taches/dropdown/")

        self.assertContains(reponse, "1ᵉʳ dans la file")

    def test_une_note_en_cours_n_affiche_pas_de_position(self):
        # Elle n'attend plus : elle est sur le worker.
        # / It is no longer waiting; it is on the worker.
        _creer_page_en_file(
            self.moi, "la-mienne", self.maintenant,
            etat=EtatIngestion.EN_COURS,
        )

        reponse = self.client.get("/taches/dropdown/")

        self.assertNotContains(reponse, "dans la file")
        self.assertContains(reponse, "En cours")

    def test_rien_des_notes_d_autrui_ne_fuit_hors_le_rang(self):
        """
        Ce qui sort est UN ENTIER. Pas un titre, pas un pk, pas un nom.
        / What leaks is ONE integer. No title, no pk, no name.

        LOCALISATION : front/tests/test_position_en_file_ingestion.py

        L'assertion sur le PK est la plus importante des trois, et c'est
        celle qui manquait (relecture adverse du 14 aout 2026) :
        `_rangs_dans_la_file_d_ingestion` manipule des pk de pages
        etrangeres, et c'est precisement l'objet de la decision du
        mainteneur. Le gabarit n'en rend aucun aujourd'hui — mais rien
        ne l'empechait, et un futur `data-rang="{{ pk }}"` serait passe
        inapercu.
        / The pk assertion is the important one, and it was missing.
        """
        page_d_autrui = _creer_page_en_file(
            self.quelqu_un_d_autre, "Rapport confidentiel de la direction",
            self.maintenant - timedelta(seconds=30),
        )
        _creer_page_en_file(self.moi, "la-mienne", self.maintenant)

        reponse = self.client.get("/taches/dropdown/")

        self.assertContains(reponse, "2ᵉ dans la file")
        self.assertNotContains(reponse, "Rapport confidentiel")
        self.assertNotContains(reponse, self.quelqu_un_d_autre.username)
        # Le pk d'autrui ne doit apparaitre dans AUCUN attribut : ni
        # data-testid, ni href, ni identifiant de ligne.
        # / The foreign pk must appear in no attribute at all.
        for gabarit_d_attribut in (
            f'data-testid="taches-item-{page_d_autrui.pk}"',
            f"/lire/{page_d_autrui.pk}/",
            f'marquer_lue={page_d_autrui.pk}',
        ):
            self.assertNotContains(reponse, gabarit_d_attribut)

    def test_le_rang_ne_coute_qu_une_requete_quel_que_soit_le_nombre_en_file(self):
        # Le rang se calcule pour TOUT le menu en une fois. Le calculer
        # ligne par ligne rendrait le menu quadratique le jour ou la
        # file s'allonge — precisement le jour ou il sert.
        # / Computed once for the whole menu, not per row.
        for numero in range(20):
            _creer_page_en_file(
                self.quelqu_un_d_autre, f"devant-{numero}",
                self.maintenant - timedelta(seconds=60 - numero),
            )
        for numero in range(5):
            _creer_page_en_file(
                self.moi, f"a-moi-{numero}",
                self.maintenant - timedelta(seconds=10 - numero),
            )

        # 15 requetes : les 14 d'avant le rang (voir
        # test_pas_de_n_plus_1_sur_le_dropdown dans
        # front/tests/test_taches_ingestion.py) plus UNE seule pour
        # ranger toute la file. / One extra query, not one per row.
        with self.assertNumQueries(15):
            self.client.get("/taches/dropdown/")
