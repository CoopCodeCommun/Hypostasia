"""
Tests de la barre du lecteur audio — ce que le serveur rend.
/ Tests for the audio player bar as rendered by the server.

LOCALISATION : front/tests/test_barre_du_lecteur_audio.py

CE QUE CES TESTS EPROUVENT

L'ecart n°2 de l'etalon, le dernier ouvert : « 0 balise <audio>, aucune
tete de lecture, aucun rail », mesure le 12 aout sur la note 8. La
gouttiere audio, elle, faisait deja ses 96px et portait les locuteurs.

CE QUE LE PRODUIT AVAIT A LA PLACE, ET POURQUOI CE N'ETAIT PAS UN LECTEUR

`transcription_rythme.js` porte une « barre de progression de lecture »
depuis PHASE-15. Le nom trompe : elle suit le DEFILEMENT, pas l'audio.
On pouvait donc voir une progression avancer sans qu'aucun son ne sorte.
Le lecteur, lui, joue le fichier.

OU VIT LA BARRE, ET POURQUOI PAS DANS LA ZONE DE LECTURE

Dans `base.html`, redeposee par OOB swap a chaque navigation — le meme
chemin que le fil d'Ariane, et pour une raison de plus : `#zone-lecture`
est remplacee entierement par `lectureReload` apres chaque operation
d'element. Un lecteur qui vivrait dedans serait DETRUIT ET RECREE a
chaque extraction — l'audio repartirait a zero au milieu de l'ecoute.
/ The bar lives in base.html: a player inside #zone-lecture would be
destroyed and recreated on every element operation, restarting the audio.
"""

from django.contrib.auth.models import User
from django.test import TestCase

from core.models import Page


class BarreDuLecteurAudioTest(TestCase):
    """
    LOCALISATION : front/tests/test_barre_du_lecteur_audio.py
    """

    def setUp(self):
        self.proprietaire = User.objects.create_user(
            username="barre_audio_test", password="motdepasse",
        )
        self.client.force_login(self.proprietaire)

    def creer_une_note_audio(self, avec_fichier=True):
        """
        Trois tours, deux locuteurs — de quoi eprouver le rail.
        / Three turns, two speakers: enough to exercise the rail.
        """
        note = Page.objects.create(
            title="Palais César",
            html_original="", html_readability="", text_readability="",
            owner=self.proprietaire,
            source_type="audio",
            source_file="sources/palais-cesar.mp3" if avec_fichier else "",
        )
        minutages = [
            ("speaker_1", 0.0, 0.5, "Une autre question ?"),
            ("speaker_2", 0.7, 1.1, "Bien sûr."),
            ("speaker_1", 1.9, 2.9, "On doit vous la poser souvent."),
        ]
        for rang, (locuteur, debut, fin, texte) in enumerate(minutages):
            note.elements.create(
                ordre=rang, label="text", texte=texte,
                provenance={"locuteur": locuteur, "debut": debut, "fin": fin},
                empreinte_contenu=f"empreinte-barre-{rang}",
            )
        return note

    def lire(self, note):
        """Le HTML de la page de lecture. / The reading page's HTML."""
        reponse = self.client.get(f"/lire/{note.pk}/")
        self.assertEqual(reponse.status_code, 200)
        return reponse.content.decode("utf-8")

    # -------------------------------------------------------------------

    def test_une_note_audio_rend_une_balise_audio_sur_son_fichier(self):
        """
        Le coeur de l'ecart n°2 : il n'y avait AUCUNE balise <audio>.
        / The heart of gap n°2: there was no <audio> tag at all.
        """
        html = self.lire(self.creer_une_note_audio())

        self.assertIn("<audio", html)
        self.assertIn("palais-cesar.mp3", html)

    def test_le_rail_porte_un_segment_par_tour_de_parole(self):
        """
        Le rail donne la FORME du debat avant qu'on l'ecoute : qui parle,
        combien de temps, et quand. Trois tours, trois segments.
        / The rail shows the debate's shape before you play it.
        """
        html = self.lire(self.creer_une_note_audio())

        self.assertEqual(html.count('class="segment-locuteur'), 3)

    def test_chaque_segment_porte_ses_bornes_en_secondes(self):
        """
        Le JS pose les largeurs quand la duree REELLE du fichier est
        connue (`loadedmetadata`) — pas avant. Il lui faut donc les
        bornes sur chaque segment.
        / The JS sizes segments once the file's real duration is known.
        """
        html = self.lire(self.creer_une_note_audio())

        self.assertIn('data-debut="0.7"', html)
        self.assertIn('data-fin="1.1"', html)

    def test_les_deux_locuteurs_n_ont_pas_la_meme_couleur(self):
        """
        Suivre un debat, c'est suivre qui parle. Un rail d'une seule
        teinte ne dit rien de plus qu'une barre de progression.
        / Following a debate means following who speaks.
        """
        html = self.lire(self.creer_une_note_audio())

        import re
        couleurs = re.findall(
            r'class="segment-locuteur[^"]*"[^>]*data-couleur="([^"]+)"', html
        )
        self.assertEqual(len(couleurs), 3)
        # Tours 0 et 2 : meme voix, donc meme couleur. Tour 1 : l'autre.
        # / Turns 0 and 2 are the same voice; turn 1 is the other.
        self.assertEqual(couleurs[0], couleurs[2])
        self.assertNotEqual(couleurs[0], couleurs[1])

    def test_la_barre_porte_les_reglages_de_STENOTYPIE(self):
        """
        SPEC-edition-par-blocs § 6.3 : les deux gestes qui manquaient
        vraiment sont la VITESSE de lecture et le RECUL A LA REPRISE.
        Ils vivent dans la barre, pas dans le mode d'édition : ils
        servent aussi à qui écoute sans corriger.
        / § 6.3: playback speed and rewind-on-resume live in the bar.
        """
        note = self.creer_une_note_audio()
        html = self.client.get(f"/lire/{note.pk}/").content.decode()
        self.assertIn('data-testid="vitesse-de-lecture"', html)
        self.assertIn('data-testid="btn-ralentir"', html)
        self.assertIn('data-testid="btn-accelerer"', html)
        self.assertIn('data-testid="recul-a-la-reprise"', html)

    def test_le_recul_a_la_reprise_peut_etre_mis_a_ZERO(self):
        """
        « Zéro le désactive » (§ 6.3). Sans cette valeur, le réglage
        impose un comportement au lieu de l'offrir.
        / Zero disables it: otherwise the setting imposes a behaviour.
        """
        note = self.creer_une_note_audio()
        html = self.client.get(f"/lire/{note.pk}/").content.decode()
        self.assertIn('value="0"', html)

    def test_la_vitesse_part_a_UN(self):
        """Le réglage se voit avant d'être touché. / Visible before use."""
        import html as entites_html

        note = self.creer_une_note_audio()
        page = self.client.get(f"/lire/{note.pk}/").content.decode()
        debut = page.index('data-testid="vitesse-de-lecture"')
        # On DÉCODE les entités : le gabarit écrit `&times;`, et ce qui
        # compte est ce que la personne LIT, pas la façon dont c'est
        # écrit. / Decode entities: what matters is what is read.
        self.assertIn("1×", entites_html.unescape(page[debut:debut + 200]))

    def test_un_document_ecrit_n_a_PAS_les_reglages(self):
        """
        Pas de son, pas de réglages : ce serait des commandes qui ne
        commandent rien. / No sound, no controls.
        """
        note = Page.objects.create(
            title="Un article", html_original="", html_readability="",
            text_readability="", owner=self.proprietaire,
            source_type="web",
        )
        html = self.client.get(f"/lire/{note.pk}/").content.decode()
        self.assertNotIn('data-testid="vitesse-de-lecture"', html)
        self.assertNotIn('data-testid="recul-a-la-reprise"', html)

    def test_un_document_ecrit_n_a_pas_de_barre(self):
        """
        Une barre de lecture sous un PDF promettrait un son qui n'existe
        pas. / A player under a PDF promises a sound that isn't there.
        """
        note_ecrite = Page.objects.create(
            title="Un PDF",
            html_original="", html_readability="", text_readability="",
            owner=self.proprietaire, source_type="file",
        )
        note_ecrite.elements.create(
            ordre=0, label="text", texte="Un paragraphe.",
            provenance={"page_no": 1}, empreinte_contenu="empreinte-pdf",
        )

        html = self.lire(note_ecrite)

        self.assertNotIn('data-testid="lecteur-audio"', html)

    def test_un_audio_sans_fichier_source_n_a_pas_de_barre(self):
        """
        LE CAS QUI FAIT MENTIR L'INTERFACE. Une transcription peut avoir
        ete importee sans son media — la note 7 est dans ce cas, son
        `source_file` est un `.json`. Rendre la barre quand meme
        afficherait un bouton « lecture » qui ne jouerait rien.
        / A transcription can arrive without its media; showing the bar
        would offer a play button that plays nothing.
        """
        html = self.lire(self.creer_une_note_audio(avec_fichier=False))

        self.assertNotIn('data-testid="lecteur-audio"', html)

    def test_la_barre_vit_hors_de_la_zone_de_lecture(self):
        """
        Sinon `lectureReload` la detruit a chaque operation d'element, et
        l'audio repart a zero au milieu de l'ecoute.
        / Otherwise lectureReload restarts the audio mid-listen.
        """
        html = self.lire(self.creer_une_note_audio())

        position_de_la_barre = html.index('data-testid="lecteur-audio"')
        position_de_la_fermeture_du_main = html.index("</main>")
        self.assertGreater(
            position_de_la_barre,
            position_de_la_fermeture_du_main,
            "La barre du lecteur est rendue DANS <main id='zone-lecture'> : "
            "chaque rechargement HTMX la détruirait et l'audio repartirait "
            "à zéro.",
        )
