"""
Ingestion d'une transcription diarisee en elements (D2, ordre 3).
/ Ingesting a diarised transcript into elements.

LOCALISATION : hypostasis_extractor/tests/test_ingestion_audio.py

CE QUE CES TESTS PROTEGENT

La bascule audio etait le dernier flux a rejoindre le moteur ELEMENT
(decision D2 : fichier d'abord, capture web ensuite, AUDIO en dernier).
Elle n'avait jamais ete faite : les 36 pages audio de la base portaient
une transcription mais aucun element utilisable — leur gouttiere restait
donc muette, sans locuteur ni minutage, la ou l'etalon en affiche.

LA REGLE VIENT DE LA MESURE D3 (PLAN/mesure-D3-frontiere-audio),
pas d'une intuition :
  · UN element par TOUR DE PAROLE — la mesure a montre que le
    changement de locuteur ne fait pas une bonne frontiere de chunk,
    mais qu'il fait une excellente frontiere d'ELEMENT ;
  · un tour de plus de 1 500 caracteres est scinde au segment le plus
    proche du budget, jamais au milieu d'une phrase ;
  · le locuteur et le minutage voyagent dans `provenance`, la ou le PDF
    met sa page et ses boites.
/ One element per speaker turn; oversized turns split at a segment
boundary; speaker and timing travel in `provenance`.
"""

from django.test import TestCase

from core.models import Page
from hypostasis_extractor.services.ingestion_audio import (
    BUDGET_MAXIMUM_PAR_ELEMENT_AUDIO,
    ingerer_une_transcription_diarisee,
)


def creer_une_page_audio(suffixe, segments):
    return Page.objects.create(
        url=f"http://exemple.local/audio-{suffixe}",
        html_original="", html_readability="", text_readability="",
        content_hash=f"hash-audio-{suffixe}",
        title=f"Entretien {suffixe}",
        source_type="audio",
        transcription_raw={"text": "", "model": "mixtral", "segments": segments},
    )


class UnTourDeParoleDevientUnElementTest(TestCase):
    """La regle centrale de D3. / D3's central rule."""

    def test_chaque_tour_donne_un_element(self):
        page = creer_une_page_audio("simple", [
            {"start": 0.0, "end": 2.5, "text": "Bonjour a tous.", "speaker": "Ian"},
            {"start": 2.5, "end": 6.0, "text": "Merci de m'accueillir.", "speaker": "Marie"},
        ])

        resultat = ingerer_une_transcription_diarisee(page)

        self.assertEqual(resultat["elements_crees"], 2)
        elements = list(page.elements.order_by("ordre"))
        self.assertEqual(
            [element.texte for element in elements],
            ["Bonjour a tous.", "Merci de m'accueillir."],
        )

    def test_le_locuteur_et_le_minutage_voyagent_dans_la_provenance(self):
        # C'est ce que la gouttiere de l'etalon affiche : le nom du
        # locuteur et l'heure du tour. / What the mock's gutter shows.
        page = creer_une_page_audio("provenance", [
            {"start": 12.5, "end": 30.0, "text": "Je ne suis pas d'accord.",
             "speaker": "Marie-Christine"},
        ])

        ingerer_une_transcription_diarisee(page)

        provenance = page.elements.first().provenance
        self.assertEqual(provenance["locuteur"], "Marie-Christine")
        self.assertEqual(provenance["debut"], 12.5)
        self.assertEqual(provenance["fin"], 30.0)

    def test_les_tours_consecutifs_d_un_meme_locuteur_restent_distincts(self):
        # D3 : la frontiere est le TOUR, pas le locuteur. Deux tours du
        # meme locuteur restent deux elements — les recoller effacerait
        # une pause qui a un sens dans un debat.
        # / The boundary is the turn, not the speaker.
        page = creer_une_page_audio("consecutifs", [
            {"start": 0.0, "end": 2.0, "text": "Premier point.", "speaker": "Ian"},
            {"start": 5.0, "end": 7.0, "text": "Second point.", "speaker": "Ian"},
        ])

        ingerer_une_transcription_diarisee(page)

        self.assertEqual(page.elements.count(), 2)

    def test_un_tour_trop_long_est_scinde(self):
        # Un monologue de 4 000 caracteres ne peut pas etre UN element :
        # le chunking ne coupe jamais un element, il deborderait donc le
        # budget du modele. D3 : scinder au segment le plus proche.
        # / A 4 000-character monologue cannot be one element.
        phrase = "Je vais developper ce point longuement. "
        long_texte = phrase * 100  # 4 000 caracteres
        page = creer_une_page_audio("monologue", [
            {"start": 0.0, "end": 300.0, "text": long_texte, "speaker": "Ian"},
        ])

        ingerer_une_transcription_diarisee(page)

        elements = list(page.elements.order_by("ordre"))
        self.assertGreater(len(elements), 1)
        for element in elements:
            self.assertLessEqual(
                len(element.texte), BUDGET_MAXIMUM_PAR_ELEMENT_AUDIO,
            )
        # Rien ne se perd a la scission : le texte recolle est l'original.
        # / Nothing is lost: the pieces reconstitute the turn.
        self.assertEqual(
            " ".join(e.texte for e in elements).split(),
            long_texte.split(),
        )

    def test_les_morceaux_d_un_tour_scinde_gardent_son_locuteur(self):
        page = creer_une_page_audio("scinde-locuteur", [
            {"start": 0.0, "end": 300.0,
             "text": "Une phrase de test. " * 120, "speaker": "Ian"},
        ])

        ingerer_une_transcription_diarisee(page)

        for element in page.elements.all():
            self.assertEqual(element.provenance["locuteur"], "Ian")


class CeQueLIngestionAudioRefuseTest(TestCase):
    """Les cas ou elle ne doit rien faire. / When it must do nothing."""

    def test_une_page_qui_a_deja_des_elements_est_refusee(self):
        # Meme garde que l'ingestion Docling : re-ingerer detacherait
        # les ancres existantes. / Same guard as Docling ingestion.
        page = creer_une_page_audio("deja", [
            {"start": 0.0, "end": 1.0, "text": "Un mot.", "speaker": "Ian"},
        ])
        ingerer_une_transcription_diarisee(page)

        resultat = ingerer_une_transcription_diarisee(page)

        self.assertIn("erreur", resultat)
        self.assertEqual(page.elements.count(), 1)

    def test_une_transcription_sans_segment_ne_cree_rien(self):
        page = creer_une_page_audio("vide", [])

        resultat = ingerer_une_transcription_diarisee(page)

        self.assertIn("erreur", resultat)
        self.assertEqual(page.elements.count(), 0)

    def test_un_segment_sans_texte_est_ignore(self):
        # Un blanc diarise (respiration, bruit) n'est pas un tour.
        # / A diarised silence is not a turn.
        page = creer_une_page_audio("blanc", [
            {"start": 0.0, "end": 1.0, "text": "   ", "speaker": "Ian"},
            {"start": 1.0, "end": 3.0, "text": "Un vrai tour.", "speaker": "Marie"},
        ])

        ingerer_une_transcription_diarisee(page)

        self.assertEqual(page.elements.count(), 1)
        self.assertEqual(page.elements.first().texte, "Un vrai tour.")

    def test_un_locuteur_absent_ne_fait_pas_echouer(self):
        # Toutes les diarisations ne nomment pas leurs locuteurs.
        # / Not every diarisation names its speakers.
        page = creer_une_page_audio("anonyme", [
            {"start": 0.0, "end": 2.0, "text": "Une voix sans nom."},
        ])

        ingerer_une_transcription_diarisee(page)

        self.assertEqual(page.elements.count(), 1)
        self.assertIsNone(page.elements.first().provenance.get("locuteur"))


class LeTexteDeLaPageSuitLesElementsTest(TestCase):
    """
    `text_readability` doit refleter la transcription : c'est lui que
    lisent le repli d'affichage et les anciennes estimations.
    / The page text must reflect the transcript.
    """

    def test_le_texte_de_la_page_est_reconstitue(self):
        page = creer_une_page_audio("texte", [
            {"start": 0.0, "end": 2.0, "text": "Premier tour.", "speaker": "Ian"},
            {"start": 2.0, "end": 4.0, "text": "Second tour.", "speaker": "Marie"},
        ])

        ingerer_une_transcription_diarisee(page)

        page.refresh_from_db()
        self.assertIn("Premier tour.", page.text_readability)
        self.assertIn("Second tour.", page.text_readability)
