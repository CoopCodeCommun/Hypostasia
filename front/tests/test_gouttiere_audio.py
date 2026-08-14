"""
Tests du bouton d'ecoute de la gouttiere audio.
/ Tests for the audio gutter's play button.

LOCALISATION : front/tests/test_gouttiere_audio.py

CE QUE CES TESTS EPROUVENT

Remarque du mainteneur, 13 aout : « il manque le bouton play dans la
gouttiere ». L'etalon en pose un, distinct du minutage
(maquette.html:1725-1727) :

    <span class="ligne-minutage">
      <button class="bouton-ecouter" title="Écouter à partir d'ici">▶</button>
      <span>00:03</span>
    </span>

CE QUE LA PREMIERE VERSION FAISAIT, ET POURQUOI C'ETAIT MOINS BON

Elle transformait LE MINUTAGE LUI-MEME en bouton. Deux choses s'y
perdaient. Le minutage est un REPERE — on le lit pour situer un
passage, pour le citer, pour s'y retrouver — et un repere qui se
souligne au survol invite a un clic qu'on ne cherchait pas. Et
l'action, elle, n'etait ecrite nulle part : rien ne DISAIT « ecouter »,
il fallait le deviner du minutage.

Deux objets distincts, donc : un repere qui se lit, un bouton qui agit.

LE BOUTON S'EFFACE JUSQU'A CE QU'ON EN AIT BESOIN

`opacity: 0`, revele au survol du bloc et pendant la lecture du tour.
Une colonne de fleches ▶ le long du texte serait une barre d'outils
verticale, pas une marge de reperes.
/ The gutter needs a play button distinct from the timecode: one is a
marker you read, the other an action you take.
"""

from django.contrib.auth.models import User
from django.test import TestCase

from core.models import Page


class GouttiereAudioTest(TestCase):
    """
    LOCALISATION : front/tests/test_gouttiere_audio.py
    """

    def setUp(self):
        self.proprietaire = User.objects.create_user(
            username="gouttiere_audio_test", password="motdepasse",
        )
        self.client.force_login(self.proprietaire)

    def creer_une_note_audio(self, avec_fichier=True):
        note = Page.objects.create(
            title="Palais César",
            html_original="", html_readability="", text_readability="",
            owner=self.proprietaire,
            source_type="audio",
            source_file="sources/palais-cesar.mp3" if avec_fichier else "",
        )
        for rang, (locuteur, debut, fin, texte) in enumerate([
            ("speaker_1", 0.0, 0.5, "Une autre question ?"),
            ("speaker_2", 0.7, 1.1, "Bien sûr."),
        ]):
            note.elements.create(
                ordre=rang, label="text", texte=texte,
                provenance={"locuteur": locuteur, "debut": debut, "fin": fin},
                empreinte_contenu=f"empreinte-gouttiere-{rang}",
            )
        return note

    def lire(self, note):
        reponse = self.client.get(f"/lire/{note.pk}/")
        self.assertEqual(reponse.status_code, 200)
        return reponse.content.decode("utf-8")

    # -------------------------------------------------------------------

    def test_chaque_tour_porte_un_bouton_d_ecoute(self):
        """
        Le geste demande par le mainteneur : un play par tour de parole.
        / One play button per speech turn.
        """
        html = self.lire(self.creer_une_note_audio())

        self.assertEqual(html.count('class="bouton-ecouter"'), 2)
        self.assertIn('data-testid="bouton-ecouter-0"', html)
        self.assertIn('data-testid="bouton-ecouter-1"', html)

    def test_le_minutage_redevient_un_repere_qu_on_lit(self):
        """
        Il n'est plus lui-meme un bouton : un repere qui se souligne au
        survol invite a un clic qu'on ne cherchait pas.
        / The timecode is a marker again, not a control.
        """
        html = self.lire(self.creer_une_note_audio())

        self.assertNotIn("minutage-audio", html)
        self.assertIn('<span class="minutage">00:00</span>', html)

    def test_le_bouton_dit_ce_qu_il_fait(self):
        """
        Un ▶ nu ne nomme rien pour un lecteur d'ecran.
        / A bare ▶ names nothing to a screen reader.
        """
        html = self.lire(self.creer_une_note_audio())

        self.assertIn("Écouter à partir d", html)
        self.assertIn("aria-label", html)

    def test_pas_de_bouton_sans_media_attache(self):
        """
        LE CAS QUI FAIT MENTIR L'INTERFACE. Une transcription importee
        sans son media — la note 7 est dans ce cas — offrirait un play
        qui ne jouerait rien.
        / A transcription without media would offer a play that plays
        nothing.
        """
        html = self.lire(self.creer_une_note_audio(avec_fichier=False))

        self.assertNotIn("bouton-ecouter", html)
        # Le minutage, lui, RESTE : il situe le passage meme sans son.
        # / The timecode stays: it locates the passage even with no sound.
        self.assertIn('<span class="minutage">00:00</span>', html)

    def test_un_document_ecrit_n_a_ni_bouton_ni_minutage(self):
        """
        Un play dans la marge d'un PDF n'aurait aucun sens.
        / A play button in a PDF's margin means nothing.
        """
        note_ecrite = Page.objects.create(
            title="Un PDF",
            html_original="", html_readability="", text_readability="",
            owner=self.proprietaire, source_type="file",
        )
        note_ecrite.elements.create(
            ordre=0, label="text", texte="Un paragraphe.",
            provenance={"page_no": 1}, empreinte_contenu="empreinte-pdf-g",
        )

        html = self.lire(note_ecrite)

        self.assertNotIn("bouton-ecouter", html)
        self.assertNotIn('class="minutage"', html)
