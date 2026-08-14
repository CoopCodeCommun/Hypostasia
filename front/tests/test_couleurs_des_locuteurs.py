"""
Test : un locuteur a UNE couleur, partout sur l'ecran.
/ Test: a speaker has ONE colour, everywhere on screen.

LOCALISATION : front/tests/test_couleurs_des_locuteurs.py

CE QUE CE TEST EPROUVE, ET COMMENT LE DEFAUT EST APPARU

Le 13 aout, la barre du lecteur audio a ete posee en bas de l'ecran,
avec un rail dont chaque segment porte la couleur de son locuteur. Elle
a rendu VISIBLE un desaccord qui existait deja, mais que rien ne
mettait cote a cote :

  · la gouttiere et le rail attribuent les couleurs par la palette de
    WONG (rendu_elements.py:585, huit teintes distinguables par les
    daltoniens) : speaker_1 en orange ;
  · les pilules de filtre et la timeline les attribuaient par la
    palette TAILWIND (transcription_audio.py:23) : speaker_1 en bleu.

Le meme locuteur portait donc DEUX couleurs sur le meme ecran, a 700
pixels d'ecart. La capture du 13 aout le montre sans ambiguite.

POURQUOI C'EST PLUS QU'UNE INELEGANCE

Suivre un debat, c'est suivre qui parle. La pastille ne sert a rien si
elle ne reste pas LA MEME d'un bout a l'autre : deux codes couleur
contradictoires ne valent pas mieux qu'aucun code — ils coutent meme
plus cher, puisqu'il faut apprendre lequel vaut ou.

MISE A JOUR DU 14 AOUT : LA TIMELINE A DISPARU

Ces tests portaient sur les DEUX widgets. La timeline a ete retiree le
14 aout — son clic visait un HTML que les pages ELEMENT ne rendent plus
(voir `test_retrait_timeline_audio`). Ils portent donc desormais sur les
pilules seules. L'invariant, lui, n'a pas bouge : une voix, une couleur,
la meme que celle de la gouttiere.

CE QUE CES TESTS NE FONT PAS

Ils ne touchent pas au HTML de transcription FIGE en base
(`construire_html_diarise`, fonds pales compris) : ces pages existent
deja, leur HTML est ecrit, et le rendu principal passe desormais par
les `ElementDocument`.
/ The player's rail made an existing disagreement visible: gutter and
rail use Wong, pills and timeline used Tailwind. One speaker, two
colours, 700px apart.
"""

from django.test import SimpleTestCase

from core.models import CategorieDossier
from front.services.transcription_audio import construire_widgets_audio

TRANSCRIPTION_DE_DEUX_VOIX = {
    "segments": [
        {"speaker": "speaker_1", "start": 0.0, "end": 0.5,
         "text": "Une autre question ?"},
        {"speaker": "speaker_2", "start": 0.7, "end": 1.1,
         "text": "Bien sûr."},
        {"speaker": "speaker_1", "start": 1.9, "end": 2.9,
         "text": "On doit vous la poser souvent."},
    ],
}


class CouleursDesLocuteursTest(SimpleTestCase):
    """
    LOCALISATION : front/tests/test_couleurs_des_locuteurs.py
    """

    def test_les_pilules_prennent_la_palette_de_la_gouttiere(self):
        """
        Le premier locuteur rencontre prend la premiere teinte de Wong —
        la meme que celle que la gouttiere lui donnera.
        / The first speaker takes Wong's first hue, as the gutter does.
        """
        html_pilules = construire_widgets_audio(TRANSCRIPTION_DE_DEUX_VOIX)

        premiere_teinte = CategorieDossier.PALETTE_WONG[0]
        seconde_teinte = CategorieDossier.PALETTE_WONG[1]

        self.assertIn(premiere_teinte, html_pilules)
        self.assertIn(seconde_teinte, html_pilules)

    def test_aucune_teinte_tailwind_ne_subsiste_dans_les_widgets(self):
        """
        LE TEST QUI ATTRAPE UNE CORRECTION A MOITIE FAITE. Corriger les
        pilules sans la timeline, ou l'inverse, laisserait exactement le
        defaut qu'on repare — a un endroit de moins.
        / Catches a half-done fix: pills without timeline, or the reverse.
        """
        html_pilules = construire_widgets_audio(TRANSCRIPTION_DE_DEUX_VOIX)

        for teinte_tailwind in ("#3b82f6", "#ef4444", "#10b981"):
            self.assertNotIn(teinte_tailwind, html_pilules)

    def test_une_voix_n_a_qu_une_pilule(self):
        """
        Le troisieme tour revient au premier locuteur, et ne lui vaut pas
        une seconde pilule : le filtre liste des VOIX, pas des tours.

        Ce test remplace `test_le_meme_locuteur_garde_sa_teinte_sur_tous
        _ses_tours`, qui comptait les segments de la timeline retiree le
        14 aout. L'invariant qu'il protegeait — une voix, une couleur —
        se verifie ici sur l'unicite de la pilule, et dans la gouttiere
        sur `couleur_du_locuteur` (test_rendu_elements).
        / Replaces a test that counted timeline segments: the filter
        lists voices, not turns.
        """
        html_pilules = construire_widgets_audio(TRANSCRIPTION_DE_DEUX_VOIX)

        premiere_teinte = CategorieDossier.PALETTE_WONG[0]
        self.assertEqual(html_pilules.count(premiere_teinte), 1)
        self.assertEqual(html_pilules.count('data-speaker-filter="speaker_1"'), 1)
