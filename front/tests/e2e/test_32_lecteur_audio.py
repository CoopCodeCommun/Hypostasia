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

        POURQUOI CE HELPER EXISTE, ET CE QU'IL NE PROUVE PAS

        Se deplacer dans un audio demande, au navigateur, l'un des deux :
        le fichier entier en memoire, ou un serveur qui repond aux
        requetes `Range`. Le produit rend `preload="metadata"` — il ne
        telecharge donc PAS le fichier — et le serveur de CE TEST est
        `StaticLiveServerTestCase`, c'est-a-dire Django, qui ne gere pas
        `Range`. Sans ce helper, le clic sur le rail serait
        silencieusement ignore et le test mesurerait 0.

        L'APPLICATION, ELLE, NE PASSE PLUS PAR LA. Depuis le 14 aout,
        `/media/` est servi par nginx en dev comme en prod
        (`nginx/dev.conf`, `nginx/default.conf`), et nginx repond `206
        Partial Content` : le deplacement y marche sans rien forcer.
        C'est `test_les_medias_sont_servis_par_nginx` (front/tests/
        test_service_des_medias.py) qui protege cette conf — un test
        e2e ne peut pas le faire, puisque nginx n'est pas dans sa boucle.

        Ce helper compense donc un ecart entre le serveur de test et le
        serveur reel. Il ne dit rien de la qualite du lecteur, et c'est
        pourquoi il est ecrit ici plutot que cache derriere une attente.
        / Django's test server ignores Range; nginx (dev and prod) does
        not. This helper compensates for that gap and proves nothing
        about the player — hence the explicit name and this note.
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

    def test_la_carte_d_une_idee_ecoute_le_passage_dont_elle_vient(self):
        """
        Demande du mainteneur, 14 aout : le meme bouton play sur les
        cartes d'extraction, a droite de « Commenter ».

        CE QUE CE GESTE AJOUTE. Une carte affirme quelque chose et cite
        un passage. Sur un audio, la citation est une TRANSCRIPTION —
        c'est-a-dire deja une interpretation. Pouvoir entendre le
        passage d'ou l'idee vient, c'est pouvoir verifier la source
        plutot que de croire la carte sur parole.

        L'INSTANT N'EST PAS RECOPIE DANS LA CARTE. Le bouton ne porte
        que l'identifiant de l'idee ; le JS retrouve sa marque dans le
        texte et lit le minutage du bloc qui la contient. Une donnee
        ecrite a un seul endroit ne peut pas diverger de son autre
        copie, puisqu'il n'y en a pas.
        / A card asserts something and quotes a passage; on audio that
        quote is a transcription, hence already an interpretation. The
        instant is not copied into the card: the button carries only the
        idea's id, and the JS reads the timing off the text.
        """
        from core.models import AIModel
        from hypostasis_extractor.models import (
            AncrageExtraction, ExtractedEntity, ExtractionJob,
        )

        troisieme_tour = self.note_audio.elements.get(ordre=2)
        modele_simule = AIModel.objects.create(
            name="Mock lecteur", model_choice="mock_default", is_active=True,
        )
        job = ExtractionJob.objects.create(
            page=self.note_audio, ai_model=modele_simule,
            name="Extraction du lecteur", prompt_description="Support",
            status="completed", entities_count=1,
        )
        idee = ExtractedEntity.objects.create(
            job=job, extraction_class="phenomene",
            extraction_text="On doit vous la poser souvent",
            start_char=0, end_char=29,
            attributes={"hypostases": "PHENOMENE", "resume": "Une question."},
        )
        AncrageExtraction.objects.create(
            extraction=idee, element=troisieme_tour,
            ordre_dans_extraction=0,
            debut_dans_element=0, fin_dans_element=29,
        )

        # A 1600px le panneau EST une colonne, ouverte par defaut : une
        # premiere version cliquait `#btn-toolbar-drawer` pour l'ouvrir
        # et le FERMAIT, si bien que le bouton restait hors de l'ecran.
        # / Above the threshold the panel is an open column; clicking the
        # toolbar button closed it.
        self.ouvrir_la_note_audio()
        self.attendre_que_le_deplacement_soit_possible()
        # ON VISE LE PANNEAU, ET NON N'IMPORTE QUELLE CARTE. Les cartes
        # sont rendues DEUX FOIS : dans `#drawer-contenu`, qu'on voit, et
        # dans `#sidebar-right`, cache et conserve comme cible d'OOB
        # swaps. Les `data-testid` y sont donc en double, et un selecteur
        # nu tombe sur l'invisible une fois sur deux.
        # / Cards render twice — the visible panel and the hidden OOB
        # target — so a bare selector hits the invisible one half the time.
        bouton = self.page.wait_for_selector(
            '#drawer-contenu [data-testid="btn-ecouter-extraction"]')
        # La carte peut etre sous le pli du panneau : on l'amene a
        # l'ecran, comme le ferait la personne en faisant defiler.
        # / The card may sit below the panel's fold; scroll to it.
        bouton.scroll_into_view_if_needed()
        bouton.click()
        self.page.wait_for_function(
            """() => !document.getElementById('audio-source').paused""",
            timeout=10000,
        )
        self.page.wait_for_timeout(500)

        instant = self.mesurer()["instant"]
        self.assertGreaterEqual(
            instant, 1.85,
            f"La carte a lancé la lecture à {instant:.2f}s au lieu de "
            f"1,9s : elle n'écoute pas le passage dont elle vient.",
        )

        # UN SEUL TOUR SURLIGNE, MEME APRES LE SWAP HTMX QUE CE CLIC
        # DECLENCHE. C'est ici que le defaut se voyait : `brancherLeLecteur`
        # oubliait le tour courant a chaque swap sans effacer sa marque,
        # laissant un surlignage orphelin — mesure du 14 aout, lecture a
        # 4,63s et bloc surligne a 0,0s.
        # / One wash at a time, even after the swap this click triggers.
        combien_surlignes = self.page.evaluate(
            """() => document.querySelectorAll(
                '#readability-content .bloc.bloc-en-lecture').length"""
        )
        self.assertLessEqual(
            combien_surlignes, 1,
            f"{combien_surlignes} tours surlignés en même temps : un "
            f"surlignage orphelin a survécu au rafraîchissement du panneau.",
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
