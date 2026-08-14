"""
Tests du minutage brut expose par le service de rendu, pour le lecteur.
/ Tests for the raw timing the render service exposes to the player.

LOCALISATION : front/tests/test_lecteur_audio.py

CE QUE CES TESTS EPROUVENT

C'est l'ecart n°2 de l'etalon, le dernier ouvert : mesure du 12 aout sur
la note 8, « 0 balise <audio>, aucune tete de lecture, aucun rail ». La
gouttiere audio, elle, faisait deja ses 96px et portait les locuteurs.

POURQUOI LE MINUTAGE BRUT, ET NON CELUI QUI EST DEJA LA

Le service rendait le minutage SEULEMENT formate — « 00:03 » — parce que
la gouttiere l'AFFICHE. Le lecteur, lui, doit CALCULER avec : la largeur
d'un segment de rail vaut `(fin - debut) / duree`, et le tour courant se
trouve en comparant l'instant de lecture aux bornes. Reparser « 00:03 »
pour retrouver 3,2 secondes perdrait les decimales — les tours de parole
de la note 8 durent 0,4 seconde.

Le service rend donc les DEUX : le formate pour l'oeil, le brut pour le
calcul. Ils viennent de la meme provenance, ils ne peuvent pas diverger.

CE QU'UN DOCUMENT ECRIT DOIT RENDRE

None, et non 0. Un `debut` a 0 sur un PDF se lirait comme « ce paragraphe
commence a la seconde zero » — la meme confusion que les neuf extractions
ancrees a `start_char = 0` qu'une relecture adverse a rattrapees le
12 aout. L'absence de temps s'ecrit None.
/ The service already rendered formatted timing for display; the player
needs raw seconds to compute with. Written documents get None, not 0.
"""

from django.contrib.auth.models import User
from django.test import TestCase

from core.models import Page
from front.services.rendu_elements import construire_les_blocs_de_lecture


class MinutageBrutDuLecteurTest(TestCase):
    """
    LOCALISATION : front/tests/test_lecteur_audio.py
    """

    def setUp(self):
        self.proprietaire = User.objects.create_user(
            username="lecteur_audio_test", password="motdepasse",
        )

    def creer_une_note_audio(self):
        """
        Deux tours de parole, minutes comme ceux de la note 8 : des
        durees inferieures a la seconde, avec des decimales.
        / Two speech turns timed like note 8's: sub-second, decimal.
        """
        note = Page.objects.create(
            title="Deux voix",
            html_original="", html_readability="", text_readability="",
            owner=self.proprietaire,
            source_type="audio",
        )
        note.elements.create(
            ordre=0, label="text", texte="Une autre question ?",
            provenance={"locuteur": "speaker_1", "debut": 0.0, "fin": 0.5},
            empreinte_contenu="empreinte-tour-0",
        )
        note.elements.create(
            ordre=1, label="text", texte="Bien sûr.",
            provenance={"locuteur": "speaker_2", "debut": 0.7, "fin": 1.1},
            empreinte_contenu="empreinte-tour-1",
        )
        return note

    # -------------------------------------------------------------------

    def test_un_tour_de_parole_porte_ses_bornes_en_secondes(self):
        """
        Le rail ne peut pas se construire sans elles.
        / The rail cannot be built without them.
        """
        blocs = construire_les_blocs_de_lecture(self.creer_une_note_audio())

        self.assertEqual(blocs[0]["debut"], 0.0)
        self.assertEqual(blocs[0]["fin"], 0.5)
        self.assertEqual(blocs[1]["debut"], 0.7)
        self.assertEqual(blocs[1]["fin"], 1.1)

    def test_les_decimales_survivent(self):
        """
        Un tour de 0,4 seconde arrondi a la seconde disparait du rail.
        Reparser le minutage formate « 00:00 » les aurait perdues.
        / A 0.4s turn rounded to the second vanishes from the rail.
        """
        blocs = construire_les_blocs_de_lecture(self.creer_une_note_audio())

        duree_du_second_tour = blocs[1]["fin"] - blocs[1]["debut"]
        self.assertAlmostEqual(duree_du_second_tour, 0.4, places=6)

    def test_le_minutage_lisible_reste_rendu_a_cote(self):
        """
        Le brut ne REMPLACE pas le formate : la gouttiere affiche l'un,
        le lecteur calcule avec l'autre, et tous deux viennent de la
        meme provenance. / Raw does not replace formatted.
        """
        blocs = construire_les_blocs_de_lecture(self.creer_une_note_audio())

        self.assertEqual(blocs[0]["minutage"], "00:00")
        self.assertEqual(blocs[0]["debut"], 0.0)

    def test_un_document_ecrit_n_a_pas_de_bornes(self):
        """
        None, et NON 0 : un `debut` a 0 sur un PDF se lirait comme
        « commence a la seconde zero ».
        / None, not 0: a 0 would read as "starts at second zero".
        """
        note_ecrite = Page.objects.create(
            title="Un PDF",
            html_original="", html_readability="", text_readability="",
            owner=self.proprietaire,
            source_type="file",
        )
        note_ecrite.elements.create(
            ordre=0, label="text", texte="Un paragraphe.",
            provenance={"page_no": 1},
            empreinte_contenu="empreinte-ecrit-0",
        )

        blocs = construire_les_blocs_de_lecture(note_ecrite)

        self.assertIsNone(blocs[0]["debut"])
        self.assertIsNone(blocs[0]["fin"])

    def test_un_tour_sans_minutage_rend_None_et_ne_casse_pas(self):
        """
        Une transcription peut livrer un tour sans bornes. Le rail doit
        pouvoir le sauter, pas planter — et surtout ne pas lui inventer
        un 0 qui le placerait au debut de l'enregistrement.
        / A turn may arrive untimed; skip it rather than inventing a 0.
        """
        note = Page.objects.create(
            title="Transcription incomplete",
            html_original="", html_readability="", text_readability="",
            owner=self.proprietaire,
            source_type="audio",
        )
        note.elements.create(
            ordre=0, label="text", texte="Sans minutage.",
            provenance={"locuteur": "speaker_1"},
            empreinte_contenu="empreinte-sans-minutage",
        )

        blocs = construire_les_blocs_de_lecture(note)

        self.assertIsNone(blocs[0]["debut"])
        self.assertIsNone(blocs[0]["fin"])
