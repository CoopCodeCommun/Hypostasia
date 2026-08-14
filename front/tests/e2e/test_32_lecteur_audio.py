"""
Tests E2E — Le lecteur audio, ecart n°2 de l'etalon.
/ E2E tests — The audio player, gap n°2 of the reference mockup.

LOCALISATION : front/tests/e2e/test_32_lecteur_audio.py

CE QUE CES TESTS EPROUVENT

Mesure du 12 aout sur la note 8 : « 0 balise <audio>, aucune tete de
lecture, aucun rail ». C'etait la derniere ligne ouverte du tableau des
sept ecarts.

POURQUOI UN WAV FABRIQUE ICI, ET NON LE .MP3 DES FIXTURES

Le rail se met a l'echelle sur `audio.duration`, que le navigateur ne
connait qu'apres avoir lu les metadonnees du fichier. Un test qui
dependrait d'un media de fixture dependrait de sa presence sur le
disque, de son format, et de la capacite de Chromium a le decoder.

Un WAV PCM est le seul format qu'on puisse fabriquer a l'octet pres en
quelques lignes, sans encodeur : son en-tete DIT la duree, et tout
navigateur le lit. Le test porte alors sur le LECTEUR, pas sur la
chaine de decodage.
/ A hand-built PCM WAV states its own duration in its header and needs
no encoder: the test then exercises the player, not the codec chain.
"""

import struct

from django.core.files.base import ContentFile

from core.models import Page
from front.tests.e2e.base import PlaywrightLiveTestCase

# Assez long pour que les tours de parole occupent des fractions
# distinctes du rail. / Long enough for turns to occupy distinct parts.
DUREE_DU_WAV_EN_SECONDES = 4
FREQUENCE_ECHANTILLONNAGE = 8000

TOLERANCE_EN_PIXELS = 2
HAUTEUR_ATTENDUE_DE_LA_BARRE = 62


def fabriquer_un_wav_silencieux(duree_en_secondes):
    """
    Un WAV PCM mono 8 bits de silence, en-tete compris.
    / A mono 8-bit PCM WAV of silence, header included.

    L'octet de silence d'un PCM 8 bits NON SIGNE est 128, pas 0 : zero y
    vaut l'amplitude minimale, c'est-a-dire un claquement continu.
    / Silence in unsigned 8-bit PCM is 128, not 0.
    """
    nombre_d_echantillons = FREQUENCE_ECHANTILLONNAGE * duree_en_secondes
    donnees = bytes([128]) * nombre_d_echantillons

    en_tete = b"RIFF"
    en_tete += struct.pack("<I", 36 + len(donnees))
    en_tete += b"WAVEfmt "
    en_tete += struct.pack("<IHHIIHH",
                           16,                        # taille du bloc fmt
                           1,                         # PCM
                           1,                         # mono
                           FREQUENCE_ECHANTILLONNAGE,
                           FREQUENCE_ECHANTILLONNAGE,  # octets par seconde
                           1,                         # alignement de bloc
                           8)                         # bits par echantillon
    en_tete += b"data" + struct.pack("<I", len(donnees))
    return en_tete + donnees


class E2ELecteurAudioTest(PlaywrightLiveTestCase):
    """
    LOCALISATION : front/tests/e2e/test_32_lecteur_audio.py
    """

    def setUp(self):
        super().setUp()
        self.utilisateur_test = self.creer_utilisateur_demo()
        self.se_connecter("testuser", "testpass123")

        self.note_audio = Page.objects.create(
            title="Palais César — deux locuteurs",
            html_original="", html_readability="", text_readability="",
            owner=self.utilisateur_test,
            source_type="audio",
            status="completed",
        )
        self.note_audio.source_file.save(
            "palais-cesar-test.wav",
            ContentFile(fabriquer_un_wav_silencieux(DUREE_DU_WAV_EN_SECONDES)),
            save=True,
        )

        tours = [
            ("speaker_1", 0.0, 0.5, "Une autre question ?"),
            ("speaker_2", 0.7, 1.1, "Bien sûr."),
            ("speaker_1", 1.9, 2.9, "On doit vous la poser souvent."),
            ("speaker_2", 3.2, 3.9, "Je ne comprends pas."),
        ]
        for rang, (locuteur, debut, fin, texte) in enumerate(tours):
            self.note_audio.elements.create(
                ordre=rang, label="text", texte=texte,
                provenance={"locuteur": locuteur, "debut": debut, "fin": fin},
                empreinte_contenu=f"empreinte-e2e-audio-{rang}",
            )

    def ouvrir_la_note_audio(self):
        """
        Charge la note et attend que le rail soit A L'ECHELLE.

        Attendre la barre ne suffit pas : elle est dans le HTML initial,
        alors que les largeurs des segments ne sont posees qu'apres
        `loadedmetadata`. Mesurer entre les deux donnerait des segments
        de largeur nulle et un test qui echoue au hasard.
        / Waiting for the bar is not enough: segments are sized only
        after loadedmetadata.
        """
        self.page.set_viewport_size({"width": 1600, "height": 900})
        self.naviguer_vers(f"/lire/{self.note_audio.pk}/")
        self.page.wait_for_function(
            """() => {
                const segment = document.querySelector('.segment-locuteur');
                return segment && segment.style.width !== '';
            }"""
        )

    def attendre_que_le_deplacement_soit_possible(self):
        """
        Force le telechargement COMPLET du media avant d'eprouver un
        deplacement.

        POURQUOI CE HELPER EXISTE — ET CE QU'IL REVELE

        Se deplacer dans un audio demande, au navigateur, l'un des deux :
        le fichier entier en memoire, ou un serveur qui repond aux
        requetes `Range`. Le produit rend `preload="metadata"` — il ne
        telecharge donc PAS le fichier — et le serveur de test est
        Django, qui ne gere pas `Range`. Sans ce helper, le clic sur le
        rail est silencieusement ignore et le test mesure 0.

        CE N'EST PAS UN DEFAUT DU LECTEUR, MAIS UNE LIMITE DE
        L'ENVIRONNEMENT DE DEV : en production, `/media/` est servi par
        nginx (nginx/default.conf:25), qui gere `Range` nativement. En
        dev, `hypostasia/urls.py:32` le confie a `django.views.static`,
        qui ne le gere pas — un enregistrement d'une heure y serait donc
        illisible en avance rapide.

        Le helper met `preload="auto"`, recharge, et attend que la plage
        bufferisee couvre toute la duree.
        / Seeking needs either the whole file in memory or a server that
        answers Range requests. Dev serves media through Django, which
        does not. Not a player defect — an environment limit, documented
        here rather than hidden behind a sleep.
        """
        self.page.evaluate(
            """() => {
                const audio = document.getElementById('audio-source');
                audio.preload = 'auto';
                audio.load();
            }"""
        )
        self.page.wait_for_function(
            """() => {
                const audio = document.getElementById('audio-source');
                if (!audio || !audio.buffered.length) return false;
                return audio.buffered.end(audio.buffered.length - 1)
                    >= audio.duration - 0.01;
            }"""
        )

    def mesurer(self):
        return self.page.evaluate(
            """() => {
                const boite = (selecteur) => {
                    const element = document.querySelector(selecteur);
                    if (!element) return null;
                    const rect = element.getBoundingClientRect();
                    return {
                        haut: rect.top, bas: rect.bottom,
                        gauche: rect.left, droite: rect.right,
                        hauteur: rect.height, largeur: rect.width,
                    };
                };
                const audio = document.getElementById('audio-source');
                return {
                    barre: boite('[data-testid="lecteur-audio"]'),
                    rail: boite('#rail'),
                    duree: audio ? audio.duration : null,
                    enPause: audio ? audio.paused : null,
                    instant: audio ? audio.currentTime : null,
                    minutage: (document.getElementById('minutage') || {}).textContent,
                    fenetre: {largeur: window.innerWidth, hauteur: window.innerHeight},
                };
            }"""
        )

    # -------------------------------------------------------------------

    def test_la_barre_est_posee_en_bas_et_traverse_la_page(self):
        """
        L'ecart n°2 dans sa forme la plus simple : elle existe, elle est
        en bas, elle couvre la largeur. / It exists, at the bottom.
        """
        self.ouvrir_la_note_audio()
        mesures = self.mesurer()

        self.assertIsNotNone(mesures["barre"], "Aucune barre de lecteur.")
        self.assertAlmostEqual(
            mesures["barre"]["bas"], mesures["fenetre"]["hauteur"],
            delta=TOLERANCE_EN_PIXELS,
            msg="La barre ne touche pas le bas de la fenêtre.",
        )
        self.assertAlmostEqual(
            mesures["barre"]["largeur"], mesures["fenetre"]["largeur"],
            delta=TOLERANCE_EN_PIXELS,
            msg="La barre ne traverse pas la page.",
        )
        self.assertAlmostEqual(
            mesures["barre"]["hauteur"], HAUTEUR_ATTENDUE_DE_LA_BARRE,
            delta=TOLERANCE_EN_PIXELS,
        )

    def test_le_texte_n_est_pas_recouvert_par_la_barre(self):
        """
        LA BARRE EST `fixed`, DONC HORS DU FLUX. Sans reserve de place,
        elle recouvre les derniers tours de parole — ceux qu'on lit
        justement quand on ecoute la fin.
        / Fixed means out of flow: without a reserve it covers the last
        turns, the very ones read while listening to the end.
        """
        self.ouvrir_la_note_audio()

        dernier_visible = self.page.evaluate(
            """() => {
                const blocs = document.querySelectorAll('#readability-content .bloc');
                if (!blocs.length) return null;
                const zone = document.querySelector('#zone-lecture');
                zone.scrollTop = zone.scrollHeight;
                const dernier = blocs[blocs.length - 1];
                const barre = document.querySelector('[data-testid="lecteur-audio"]');
                return {
                    basDuDernierBloc: dernier.getBoundingClientRect().bottom,
                    hautDeLaBarre: barre.getBoundingClientRect().top,
                };
            }"""
        )

        self.assertIsNotNone(dernier_visible)
        self.assertLessEqual(
            dernier_visible["basDuDernierBloc"],
            dernier_visible["hautDeLaBarre"] + TOLERANCE_EN_PIXELS,
            "Le dernier tour de parole passe sous la barre du lecteur : "
            "la réserve de place (--barre-audio) ne joue pas.",
        )

    def test_le_rail_porte_un_segment_par_tour_a_sa_place_temporelle(self):
        """
        LE POINT LE PLUS DELICAT, et l'ecart assume avec l'etalon.

        L'etalon empile les segments dans un `flex` en ne leur donnant
        qu'une largeur — ce qui suppose que les tours se touchent. Ils ne
        se touchent pas : le premier finit a 0,5s, le second commence a
        0,7s. En flex, ce silence disparait et TOUS les segments
        suivants derivent. Positionnes en absolu, chacun tombe a sa
        vraie place.
        / The mock's flex-stacking assumes contiguous turns; they are
        not, so every later segment would drift by the sum of the gaps.
        """
        self.ouvrir_la_note_audio()

        segments = self.page.evaluate(
            """() => [...document.querySelectorAll('.segment-locuteur')]
                .map((s) => ({
                    debut: parseFloat(s.dataset.debut),
                    gauche: parseFloat(s.style.left),
                }))"""
        )

        self.assertEqual(len(segments), 4, "Un segment par tour de parole.")

        duree = self.mesurer()["duree"]
        for segment in segments:
            position_attendue = segment["debut"] / duree * 100
            self.assertAlmostEqual(
                segment["gauche"], position_attendue, delta=0.5,
                msg=(
                    f"Le segment du tour commençant à {segment['debut']}s "
                    f"est posé à {segment['gauche']:.1f}% au lieu de "
                    f"{position_attendue:.1f}% : les segments dérivent."
                ),
            )

    def test_cliquer_le_rail_deplace_la_lecture(self):
        """
        Le geste de deplacement le plus direct. Un rail qu'on ne peut
        pas viser n'est qu'une barre de progression.
        / A rail you cannot aim at is just a progress bar.
        """
        self.ouvrir_la_note_audio()
        self.attendre_que_le_deplacement_soit_possible()

        boite_du_rail = self.page.evaluate(
            """() => {
                const rect = document.getElementById('rail').getBoundingClientRect();
                return {x: rect.left, y: rect.top, largeur: rect.width,
                        hauteur: rect.height};
            }"""
        )
        # Aux trois quarts du rail : loin du bord, donc insensible a un
        # pixel pres. / Three quarters along: far from any edge.
        self.page.mouse.click(
            boite_du_rail["x"] + boite_du_rail["largeur"] * 0.75,
            boite_du_rail["y"] + boite_du_rail["hauteur"] / 2,
        )

        mesures = self.mesurer()
        self.assertAlmostEqual(
            mesures["instant"], mesures["duree"] * 0.75,
            delta=0.4,
            msg="Le clic sur le rail n'a pas déplacé la lecture.",
        )

    def test_le_bouton_de_la_gouttiere_lance_l_ecoute_a_cet_instant(self):
        """
        C'est ce qui relie le texte au son : sans lui, le lecteur et la
        transcription restent deux objets cote a cote.

        Le bouton est efface (`opacity: 0`) tant qu'on ne survole pas le
        bloc. `click()` de Playwright survole avant de cliquer, comme le
        ferait la main — le geste teste est donc bien le vrai.
        / Playwright hovers before clicking, as a hand would, so the
        faded button is exercised exactly as a person would use it.
        """
        self.ouvrir_la_note_audio()
        self.attendre_que_le_deplacement_soit_possible()

        # Le troisieme tour commence a 1,9s.
        # / The third turn starts at 1.9s.
        self.page.click('[data-testid="bouton-ecouter-2"]')
        self.page.wait_for_function(
            """() => document.getElementById('audio-source').currentTime >= 1.9"""
        )

        mesures = self.mesurer()
        self.assertAlmostEqual(mesures["instant"], 1.9, delta=0.3)
        self.assertFalse(
            mesures["enPause"],
            "Cliquer un minutage place la lecture mais ne la lance pas.",
        )

    def test_le_bouton_lance_et_arrete_la_lecture(self):
        """
        Le geste le plus attendu, et son glyphe qui DIT ce qu'il fera.
        / The most expected gesture, and the glyph that says what's next.
        """
        self.ouvrir_la_note_audio()

        self.assertTrue(self.mesurer()["enPause"])

        # ON ATTEND LE GLYPHE, PAS L'ETAT. `pause()` bascule `paused`
        # immediatement, alors que l'evenement `pause` n'arrive qu'au
        # tour suivant : attendre l'etat rendait la main AVANT que le
        # bouton n'ait pu se redessiner, et le test lisait l'ancien
        # glyphe. C'est ce decalage qui a fait ajouter un marquage
        # immediat dans le gestionnaire de clic.
        # / Wait for the glyph, not the state: `paused` flips a tick
        # before the event that repaints the button.
        self.page.click('[data-testid="bouton-lecture"]')
        self.page.wait_for_function(
            """() => document.querySelector('[data-testid="bouton-lecture"]')
                .textContent.indexOf('❚') !== -1"""
        )
        self.assertFalse(self.mesurer()["enPause"])

        self.page.click('[data-testid="bouton-lecture"]')
        self.page.wait_for_function(
            """() => document.querySelector('[data-testid="bouton-lecture"]')
                .textContent.indexOf('▶') !== -1"""
        )
        self.assertTrue(self.mesurer()["enPause"])

    def test_le_tour_entendu_se_surligne_en_entier(self):
        """
        Demande du mainteneur, 13 aout : « lorsque l'audio est lu, on a
        un surlignage leger sur toute la div de la ligne ». C'est le
        patron de l'etalon (maquette.html:559) : un fond ambre a 7 % sur
        TOUT le bloc.

        Une premiere version posait un liseré dans la gouttiere, par
        crainte qu'un fond n'abaisse le contraste du texte. Ce test
        MESURE ce contraste plutot que de le craindre.
        / The maintainer asked for the mock's 7% amber wash over the
        whole block; this test measures the contrast rather than fearing
        it.
        """
        self.ouvrir_la_note_audio()
        self.attendre_que_le_deplacement_soit_possible()

        self.page.click('[data-testid="bouton-ecouter-2"]')
        self.page.wait_for_selector("#readability-content .bloc.bloc-en-lecture")

        mesures = self.page.evaluate(
            """() => {
                const enLecture = document.querySelectorAll(
                    '#readability-content .bloc.bloc-en-lecture');
                const blocs = document.querySelectorAll(
                    '#readability-content .bloc[data-debut]');
                const voisin = [...blocs].find(
                    (b) => !b.classList.contains('bloc-en-lecture'));
                const fond = (element) =>
                    getComputedStyle(element).backgroundColor;
                return {
                    combien: enLecture.length,
                    debutDuTourSurligne: enLecture.length
                        ? enLecture[0].dataset.debut : null,
                    fondDuTour: enLecture.length ? fond(enLecture[0]) : null,
                    fondDuVoisin: voisin ? fond(voisin) : null,
                    couleurDuTexte: enLecture.length
                        ? getComputedStyle(
                            enLecture[0].querySelector('.corps')).color
                        : null,
                };
            }"""
        )

        # UN SEUL tour a la fois : deux blocs surlignes voudraient dire
        # que l'ancien n'a pas ete efface, et le surlignage cesserait de
        # designer quoi que ce soit.
        # / Exactly one at a time, or the wash designates nothing.
        self.assertEqual(mesures["combien"], 1)
        self.assertEqual(float(mesures["debutDuTourSurligne"]), 1.9)

        # Le fond est POSE, et il differe de celui des autres blocs.
        # / The wash is applied, and differs from its neighbours'.
        self.assertNotEqual(
            mesures["fondDuTour"], mesures["fondDuVoisin"],
            "Le tour en cours d'écoute a le même fond que les autres : "
            "le surlignage ne se voit pas.",
        )
        self.assertNotIn(
            mesures["fondDuTour"], ("rgba(0, 0, 0, 0)", "transparent"),
            "Le tour en cours d'écoute n'a aucun fond.",
        )

    def test_la_barre_ne_survit_pas_a_la_note_qu_elle_joue(self):
        """
        LE DEFAUT QUE LE PATRON OOB DOIT EMPECHER. La barre vit dans
        `base.html`, hors de `#zone-lecture` — sans quoi chaque
        rechargement HTMX la detruirait et l'audio repartirait a zero.
        Mais vivre dehors veut dire qu'elle ne part pas toute seule :
        naviguer vers un carnet laisserait une barre proposant de lire
        un enregistrement que l'ecran n'affiche plus.
        / Living outside #zone-lecture means it does not leave on its
        own: every screen must re-deposit an (empty) container.
        """
        self.ouvrir_la_note_audio()
        self.assertIsNotNone(self.mesurer()["barre"])

        self.page.click('[data-testid="lien-nav-carnets"]')
        self.page.wait_for_selector('[data-testid="corpus-carnets-liste"]')

        self.assertIsNone(
            self.mesurer()["barre"],
            "La barre du lecteur a survécu à la navigation vers les "
            "carnets : elle propose d'écouter une note qui n'est plus "
            "à l'écran.",
        )
