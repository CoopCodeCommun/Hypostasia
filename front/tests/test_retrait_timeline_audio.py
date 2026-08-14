"""
Tests du retrait de la timeline et de la barre de progression audio.
/ Tests for the removal of the audio timeline and progress bar.

LOCALISATION : front/tests/test_retrait_timeline_audio.py

CE QUE LE MAINTENEUR A DEMANDE, 14 aout : « tu peux retirer la timeline
clic to scroll du haut et le rail, ils ne sont pas necessaires ».

CE QUE LA MESURE A MONTRE AVANT DE RETIRER — ET QUI CHANGE LE SENS DU
GESTE

Les trois dispositifs de PHASE-15 visaient `.speaker-block` et
`#speaker-block-N`, c'est-a-dire le HTML DIARISE FIGE que produisait
`construire_html_diarise` a l'ingestion. Or les pages passees au moteur
ELEMENT ne sont plus rendues depuis ce HTML : elles le sont depuis
leurs `ElementDocument`, en blocs `.bloc`. Mesure du 14 aout sur la
note 8 : **`speaker-block-` apparait 0 fois** dans la page.

Consequence, verifiee au navigateur :

  · la timeline affichait 7 segments dont le clic cherchait
    `#speaker-block-N` — introuvable, donc rien ne se passait ;
  · les points d'extraction n'etaient jamais rendus (0) ;
  · le FILTRE PAR LOCUTEUR grisait 3 segments de cette timeline morte
    et ne masquait AUCUN texte : 9 blocs visibles sur 9.

On ne retire donc pas trois fonctions : on retire trois dispositifs qui
avaient CESSE d'en etre. C'est une difference qui compte — le garde-fou
`test_aucun_geste_orphelin` existe parce qu'un retrait « propre » a
deja failli emporter des fonctions vivantes.

CE QUI EST REPARE PLUTOT QUE RETIRE

Le filtre par locuteur, lui, a un sens sur un debat : suivre une voix a
travers un echange. Il est rebranche sur les blocs REELS
(`.bloc[data-locuteur]`), ce qui lui rend son effet. Le retirer aurait
supprime une fonction utile au motif qu'elle etait cassee.
/ These devices targeted the frozen diarised HTML, which ELEMENT pages
no longer render: they had already stopped working. The speaker filter
is repaired rather than removed — following one voice through a debate
is worth having.
"""

import pathlib

from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase

from core.models import Page
from front.services.transcription_audio import construire_widgets_audio

TRANSCRIPTION_DE_DEUX_VOIX = {
    "segments": [
        {"speaker": "speaker_1", "start": 0.0, "end": 0.5,
         "text": "Une autre question ?"},
        {"speaker": "speaker_2", "start": 0.7, "end": 1.1,
         "text": "Bien sûr."},
    ],
}


class RetraitDeLaTimelineTest(TestCase):
    """
    LOCALISATION : front/tests/test_retrait_timeline_audio.py
    """

    def setUp(self):
        self.proprietaire = User.objects.create_user(
            username="retrait_timeline_test", password="motdepasse",
        )
        self.client.force_login(self.proprietaire)

    def creer_une_note_audio(self):
        note = Page.objects.create(
            title="Palais César",
            html_original="", html_readability="", text_readability="",
            owner=self.proprietaire,
            source_type="audio",
            source_file="sources/palais-cesar.mp3",
            # SANS `transcription_raw`, AUCUN widget n'est construit
            # (views.py:1318) — et un test qui constate une absence sur
            # une page qui n'en produit aucun ne prouve rien.
            # / No transcription, no widgets at all: an absence proved on
            # a page that builds none proves nothing.
            transcription_raw=TRANSCRIPTION_DE_DEUX_VOIX,
        )
        for rang, (locuteur, debut, fin, texte) in enumerate([
            ("speaker_1", 0.0, 0.5, "Une autre question ?"),
            ("speaker_2", 0.7, 1.1, "Bien sûr."),
        ]):
            note.elements.create(
                ordre=rang, label="text", texte=texte,
                provenance={"locuteur": locuteur, "debut": debut, "fin": fin},
                empreinte_contenu=f"empreinte-retrait-{rang}",
            )
        return note

    # -------------------------------------------------------------------

    def test_la_timeline_a_disparu_de_la_page(self):
        """
        Son clic cherchait `#speaker-block-N`, absent des pages ELEMENT.
        / Its click looked for #speaker-block-N, absent from ELEMENT pages.
        """
        html = self.client.get(f"/lire/{self.creer_une_note_audio().pk}/") \
            .content.decode("utf-8")

        self.assertNotIn("timeline-audio", html)
        self.assertNotIn("timeline-segment", html)

    def test_la_barre_de_progression_a_disparu_de_la_page(self):
        """
        Elle doublait la barre de defilement du navigateur, et son nom
        — « progression de lecture » — a longtemps fait croire qu'un
        lecteur audio existait.
        / It duplicated the browser's own scrollbar, and its name made
        people believe an audio player existed.
        """
        html = self.client.get(f"/lire/{self.creer_une_note_audio().pk}/") \
            .content.decode("utf-8")

        self.assertNotIn("barre-progression-audio", html)
        self.assertNotIn("barre-progression-remplissage", html)

    def test_le_filtre_par_locuteur_reste_propose(self):
        """
        Lui n'est pas retire : suivre une voix a travers un echange a un
        sens. Il est REPARE — voir le test suivant.
        / Not removed: following one voice through a debate is useful.
        """
        html = self.client.get(f"/lire/{self.creer_une_note_audio().pk}/") \
            .content.decode("utf-8")

        self.assertIn("pilule-locuteur", html)
        self.assertIn('data-speaker-filter="speaker_1"', html)


class FiltreParLocuteurRebrancheTest(SimpleTestCase):
    """
    LOCALISATION : front/tests/test_retrait_timeline_audio.py
    """

    def test_le_filtre_ne_vise_plus_le_html_diarise_fige(self):
        """
        LE DEFAUT QUE CE TEST VERROUILLE. Le filtre visait
        `.speaker-block`, produit par `construire_html_diarise` a
        l'ingestion. Les pages ELEMENT ne rendent plus ce HTML : mesure
        du 14 aout, cliquer « speaker_1 » masquait 0 bloc de texte sur
        les 9 affiches. Un controle qui ne fait rien est pire qu'un
        controle absent : on croit avoir filtre.
        / The filter targeted the frozen diarised HTML; on ELEMENT pages
        it masked nothing. A control that does nothing is worse than no
        control: you believe you have filtered.
        """
        javascript = (
            pathlib.Path(settings.BASE_DIR)
            / "front" / "static" / "front" / "js" / "transcription_rythme.js"
        ).read_text(encoding="utf-8")

        self.assertNotIn(
            '.speaker-block"',
            javascript,
            "Le filtre par locuteur vise encore `.speaker-block`, qui "
            "n'existe plus dans les pages rendues depuis leurs éléments.",
        )
        self.assertIn(
            "[data-locuteur]",
            javascript,
            "Le filtre par locuteur ne vise pas les blocs réels.",
        )

    def test_les_widgets_ne_produisent_plus_de_timeline(self):
        """
        `construire_widgets_audio` ne rend plus qu'une chose : garder un
        second retour vide aurait laisse un appelant croire qu'il existe
        encore quelque chose a afficher.
        / The builder returns one thing now; an empty second return would
        have left callers believing there was still something to show.
        """
        html_des_pilules = construire_widgets_audio(TRANSCRIPTION_DE_DEUX_VOIX)

        self.assertIsInstance(html_des_pilules, str)
        self.assertIn("pilule-locuteur", html_des_pilules)
        self.assertNotIn("timeline", html_des_pilules)
