"""
Tests E2E — Le panneau integre : sa place, sa largeur, son seuil.
/ E2E tests — The integrated panel: its place, width and threshold.

LOCALISATION : front/tests/e2e/test_18_panneau_integre.py

CE QUE CES TESTS EPROUVENT

Au-dela de 1400px, l'etalon (maquette.html § 13 « PANNEAU / DRAWER ») donne au panneau une
COLONNE : 23rem, a droite du texte, sans voile, et surtout SANS RIEN
RECOUVRIR. En dessous, il redevient un tiroir superpose de 36rem.

Le produit avait deux ecarts mesures au navigateur le 12 aout :
  · le panneau, `fixed` a z-index 70, recouvrait la barre d'outils
    (z-index 30) sur 576px — la barre s'arretait visuellement a x=968
    dans une fenetre de 1600 ;
  · il faisait 576px la ou l'etalon en veut 368.

Ces tests MESURENT, ils ne lisent pas le DOM : c'est la geometrie qui
etait fausse, pas la structure.
/ These tests measure geometry; the DOM structure was never the problem.
"""

from core.models import AIModel
from front.tests.e2e.base import PlaywrightLiveTestCase
from hypostasis_extractor.models import ExtractedEntity, ExtractionJob

# Le seuil de l'etalon : au-dela, le panneau est une colonne.
# / The etalon's threshold: above it, the panel is a column.
SEUIL_DU_PANNEAU_EN_COLONNE = 1400

# 23rem a 16px/rem (maquette.html § 1 « JETONS », `--panneau: 23rem`).
# / 23rem at 16px/rem.
# 416px — `--preuve`, 26rem. UNE SEULE LARGEUR POUR LES DEUX PANNEAUX
# (decision du mainteneur, 20 aout) : celui des analyses mesurait 368px
# quand celui des preuves en faisait 416, et le bord de la zone de
# lecture sautait de 48px en passant d'une note a un article. Deux
# panneaux qui vivent au meme endroit, se basculent du meme bouton et se
# lisent l'un apres l'autre n'ont aucune raison d'avoir deux largeurs.
# / One width for both panels: the reading zone's edge jumped by 48px
# between a note and an article.
LARGEUR_ATTENDUE_DU_PANNEAU = 416

# La mesure d'un navigateur reel n'est pas au pixel : bordures,
# arrondis de sous-pixel. / Real-browser measurements are not pixel-exact.
TOLERANCE_EN_PIXELS = 2

# L'etalon lui-meme n'est pas parfaitement centre : son bloc tombe 13px a
# gauche du centre de l'espace, la barre de defilement du panneau n'etant
# pas comptee dans son calcul. On se donne la meme marge, arrondie.
# / The mockup itself sits 13px off-centre; we allow the same slack.
DECALAGE_TOLERE_DU_CENTRAGE = 15


class E2EPanneauIntegreTest(PlaywrightLiveTestCase):
    """
    LOCALISATION : front/tests/e2e/test_18_panneau_integre.py
    """

    def setUp(self):
        super().setUp()
        self.utilisateur_test = self.creer_utilisateur_demo()
        self.se_connecter("testuser", "testpass123")

        self.note = self.creer_page_demo(
            "Note du panneau intégré",
            "<p>Un paragraphe qui sert de support au panneau.</p>",
            owner=self.utilisateur_test,
        )
        # Sans element, la note se rend sans `.bloc` : les mesures de
        # centrage et d'alignement n'auraient rien a mesurer.
        # / Without an element there is no `.bloc` to measure.
        self.note.elements.create(
            ordre=0,
            label="text",
            texte=(
                "Un paragraphe assez long pour occuper la colonne de "
                "lecture sur plusieurs lignes et rendre le centrage "
                "mesurable au pixel près."
            ),
            empreinte_contenu="empreinte-panneau-0",
        )
        modele_simule = AIModel.objects.create(
            name="Mock panneau", model_choice="mock_default", is_active=True
        )
        job = ExtractionJob.objects.create(
            page=self.note,
            ai_model=modele_simule,
            name="Extraction du panneau",
            prompt_description="Support de mesure",
            status="completed",
            entities_count=1,
        )
        ExtractedEntity.objects.create(
            job=job,
            extraction_class="axiome",
            extraction_text="Une idée posée pour peupler le panneau",
            start_char=0,
            end_char=38,
        )

    # -------------------------------------------------------------------
    # Helpers de mesure
    # / Measurement helpers
    # -------------------------------------------------------------------

    def ouvrir_la_note_en(self, largeur_de_fenetre, hauteur_de_fenetre=1000):
        """
        Regle la fenetre PUIS charge la note : c'est au chargement que le
        script decide d'ouvrir le panneau sur grand ecran.
        / Size first, then load: the open-on-wide-screen decision happens
        at load time.
        """
        self.page.set_viewport_size(
            {"width": largeur_de_fenetre, "height": hauteur_de_fenetre}
        )
        self.naviguer_vers(f"/lire/{self.note.pk}/")
        # La decision d'ouvrir le panneau se prend au chargement et
        # deplace la zone de lecture : on attend qu'elle soit posee.
        # / The open-on-load decision moves the reading zone; wait for it
        # to settle rather than sleeping through it.
        self.attendre_la_mise_en_page("#zone-lecture")

    def mesurer(self, selecteur):
        """Rend la boite d'un element. / Return an element's box."""
        return self.page.evaluate(
            """(selecteur) => {
                const element = document.querySelector(selecteur);
                if (!element) return null;
                const boite = element.getBoundingClientRect();
                const calcule = getComputedStyle(element);
                return {
                    haut: boite.top, bas: boite.bottom,
                    gauche: boite.left, droite: boite.right,
                    largeur: boite.width,
                    position: calcule.position,
                    paddingDroit: parseFloat(calcule.paddingRight),
                    visible: calcule.display !== 'none'
                        && calcule.visibility !== 'hidden',
                };
            }""",
            selecteur,
        )

    # -------------------------------------------------------------------
    # Au-dela du seuil : une colonne
    # / Above the threshold: a column
    # -------------------------------------------------------------------

    def test_le_panneau_vit_dans_le_corps_de_la_note(self):
        """
        Decision du mainteneur, 12 aout : « Elle doit vraiment etre
        integree dans la note, et non pas ailleurs. »

        Le panneau etait un enfant direct de `<body>`, place AVANT le
        conteneur de lecture : aucune grille ne pouvait le prendre dans
        son flux, et sa place etait simulee par un `padding-right` sur la
        zone de lecture. Il suivait donc l'utilisateur d'un ecran a
        l'autre — carnets, bases — alors qu'il ne parle que d'une note.
        / The panel was a direct child of <body>, so no grid could hold it.
        """
        self.ouvrir_la_note_en(1600)

        appartenance = self.page.evaluate(
            """() => {
                const panneau = document.querySelector('#drawer-overlay');
                const zone = document.querySelector('#zone-lecture');
                const plateau = document.querySelector('.plateau');
                return {
                    plateauExiste: !!plateau,
                    panneauDansLePlateau: !!(plateau && plateau.contains(panneau)),
                    lectureDansLePlateau: !!(plateau && plateau.contains(zone)),
                    barreHorsDuPlateau: !!(plateau
                        && !plateau.contains(document.querySelector('nav'))),
                };
            }"""
        )

        self.assertTrue(
            appartenance["plateauExiste"],
            "Aucune grille `.plateau` : le panneau ne peut pas être dans "
            "le flux.",
        )
        self.assertTrue(
            appartenance["panneauDansLePlateau"],
            "Le panneau vit toujours hors du corps de la note.",
        )
        self.assertTrue(appartenance["lectureDansLePlateau"])
        self.assertTrue(
            appartenance["barreHorsDuPlateau"],
            "La barre d'outils surplombe les deux colonnes : dans la "
            "grille, elle défilerait avec le texte.",
        )

    def test_le_panneau_et_son_bouton_n_existent_que_sur_une_note(self):
        """
        Deuxieme moitie de « tout doit etre integre dans la note » : le
        panneau parle d'UNE note, son bouton d'ouverture aussi. Tant que
        le bouton vivait dans la barre d'outils globale, il suivait
        l'utilisateur sur les carnets et les bases, ou il ne designait
        rien — le mainteneur : « Le bouton dans le menu n'a d'ailleurs
        pas de sens. »

        Ecart assume avec l'etalon, qui garde « Analyses » dans sa barre.
        / The panel speaks about one note; so must its button.
        """
        self.page.set_viewport_size({"width": 1600, "height": 1000})

        self.naviguer_vers(f"/lire/{self.note.pk}/")
        self.attendre_la_mise_en_page("#zone-lecture")
        sur_une_note = self.page.evaluate(
            """() => ({
                bouton: document.querySelectorAll('#btn-toolbar-drawer').length,
                panneau: document.querySelectorAll('#drawer-overlay').length,
            })"""
        )

        self.naviguer_vers("/carnets/")
        # Constater une absence n'a de sens que sur une page arrivee :
        # on attend la liste des carnets avant de conclure.
        # / Asserting an absence only means something once the page is
        # actually there.
        self.page.wait_for_selector('[data-testid="corpus-carnets-liste"]')
        # Le panneau reste dans le DOM — il est rendu par `base.html`, que
        # la navigation HTMX ne remplace jamais. Ce qui compte est qu'il
        # ne se VOIE pas, et qu'il ne reserve pas sa colonne.
        # / It stays in the DOM (base.html is never swapped); what matters
        # is that it is neither visible nor holding its grid column.
        hors_note = self.page.evaluate(
            """() => {
                const panneau = document.querySelector('#drawer-overlay');
                const plateau = document.querySelector('.plateau');
                return {
                    bouton: document.querySelectorAll('#btn-toolbar-drawer').length,
                    panneauVisible: !!(panneau && panneau.offsetParent !== null),
                    colonnesDuPlateau: plateau
                        ? getComputedStyle(plateau).gridTemplateColumns
                        : null,
                };
            }"""
        )

        self.assertEqual(sur_une_note["bouton"], 1, "Le bouton manque sur la note.")
        self.assertEqual(sur_une_note["panneau"], 1, "Le panneau manque sur la note.")
        self.assertEqual(
            hors_note["bouton"],
            0,
            "Le bouton d'ouverture du panneau suit l'utilisateur hors "
            "de la note.",
        )
        self.assertFalse(
            hors_note["panneauVisible"],
            "Le panneau se voit encore hors de la note.",
        )
        self.assertNotIn(
            " ",
            hors_note["colonnesDuPlateau"].strip(),
            f"Le plateau réserve encore une colonne à un panneau "
            f"invisible : {hors_note['colonnesDuPlateau']}.",
        )

    def test_le_panneau_est_dans_le_flux_et_non_pose_par_dessus(self):
        """
        Etre enfant du plateau ne suffit pas : un `position: fixed` y
        resterait hors flux. Au-dela du seuil, le panneau doit occuper sa
        colonne pour de bon.
        / Being a child is not enough; a fixed panel is still out of flow.
        """
        self.ouvrir_la_note_en(1600)

        panneau = self.mesurer("#drawer-overlay")

        self.assertNotEqual(
            panneau["position"],
            "fixed",
            "Le panneau est encore posé par-dessus la page.",
        )

    def test_le_panneau_ne_recouvre_pas_la_barre_d_outils(self):
        """
        Le defaut signale en passation : « le panneau s'ouvre par-dessus le
        reste ». Mesure du 12 aout — le panneau commencait a y=0, la barre
        d'outils aussi, et le panneau gagnait par son z-index.
        / The panel started at y=0 and outranked the toolbar by z-index.
        """
        self.ouvrir_la_note_en(1600)

        barre_d_outils = self.mesurer("nav")
        panneau = self.mesurer("#drawer-overlay")

        self.assertTrue(panneau["visible"], "Le panneau devrait être ouvert.")
        self.assertGreaterEqual(
            panneau["haut"],
            barre_d_outils["bas"] - TOLERANCE_EN_PIXELS,
            "Le panneau démarre au-dessus du bas de la barre d'outils : "
            "il la recouvre.",
        )

    def test_le_panneau_a_la_largeur_de_l_etalon(self):
        """23rem, pas 36rem. / 23rem, not 36rem."""
        self.ouvrir_la_note_en(1600)

        panneau = self.mesurer("#drawer-overlay")

        self.assertAlmostEqual(
            panneau["largeur"],
            LARGEUR_ATTENDUE_DU_PANNEAU,
            delta=TOLERANCE_EN_PIXELS,
        )

    def test_les_deux_colonnes_se_touchent_sans_se_recouvrir(self):
        """
        Depuis que le panneau est dans la grille, la place n'est plus
        « compensee » par un padding : elle est REPARTIE. Les deux
        colonnes doivent donc se succeder exactement — ni recouvrement,
        ni bande morte entre elles.

        Ce test remplace celui qui mesurait le `padding-right`
        compensatoire : il decrivait la mecanique d'avant, et serait
        reste vert sur une grille cassee.
        / Space is now allocated by the grid, not compensated by padding.
        """
        self.ouvrir_la_note_en(1600)

        panneau = self.mesurer("#drawer-overlay")
        zone_de_lecture = self.mesurer("#zone-lecture")

        self.assertLessEqual(
            zone_de_lecture["droite"],
            panneau["gauche"] + TOLERANCE_EN_PIXELS,
            "La zone de lecture passe sous le panneau.",
        )
        self.assertLess(
            panneau["gauche"] - zone_de_lecture["droite"],
            4,
            "Une bande morte sépare le texte du panneau.",
        )

    def test_rien_ne_passe_par_dessus_le_haut_du_panneau(self):
        """
        Regression introduite le 12 aout puis corrigee le meme jour : en
        descendant le panneau a `z-index: 20` pour qu'il cesse de recouvrir
        la barre d'outils, on l'a fait passer SOUS le fil d'Ariane, qui est
        `sticky` a `z-index: 66` et large de toute la zone de lecture.
        `elementFromPoint` dans le panneau rendait alors `#fil-ariane`.

        Le `top` suffit a proteger la barre d'outils — elle occupe y=0..48,
        le panneau commence a 48, ils ne se recouvrent plus. Le z-index n'a
        donc plus a etre bas, et il ne doit pas l'etre.
        / The `top` offset alone protects the toolbar; a low z-index only
        buried the panel under the sticky breadcrumb.
        """
        self.ouvrir_la_note_en(1600)

        elementRecouvrant = self.page.evaluate(
            """() => {
                const panneau = document.querySelector('#drawer-overlay');
                const boite = panneau.getBoundingClientRect();
                // Quelques pixels a l'interieur du coin haut-gauche : c'est
                // la que le fil d'Ariane mordait.
                const dessus = document.elementFromPoint(boite.x + 40, boite.y + 10);
                if (!dessus) return 'aucun élément';
                return panneau.contains(dessus)
                    ? null
                    : (dessus.id || dessus.className.toString() || dessus.tagName);
            }"""
        )

        self.assertIsNone(
            elementRecouvrant,
            f"« {elementRecouvrant} » est peint par-dessus le haut du "
            f"panneau : son contenu y est masqué et incliquable.",
        )

    def test_la_colonne_de_lecture_est_centree_dans_sa_place(self):
        """
        L'etalon centre sa colonne : boite de 742px, `margin: 0 auto`, et
        c'est l'EN-TETE qu'il decale vers la droite de la largeur de la
        gouttiere (`padding-left: calc(var(--gouttiere) + 1.5rem)`).

        Le produit faisait l'inverse — il tirait le CORPS vers la gauche
        par des marges negatives. Les deux alignent titre et texte, mais
        un seul centre l'ensemble : mesure du 12 aout, le centre du bloc
        tombait 42px a gauche du centre de l'espace disponible, contre
        13px dans l'etalon.
        / The mockup offsets its header right; the product pulled its body
        left. Both align title and text; only one centres the whole.
        """
        self.ouvrir_la_note_en(1600)

        centrage = self.page.evaluate(
            """() => {
                const zone = document.querySelector('#zone-lecture');
                const bloc = document.querySelector('.bloc');
                if (!bloc) return null;
                const style = getComputedStyle(zone);
                const boiteDeLaZone = zone.getBoundingClientRect();
                const gaucheUtile = boiteDeLaZone.left + parseFloat(style.paddingLeft);
                const droiteUtile = boiteDeLaZone.left + zone.clientWidth
                    - parseFloat(style.paddingRight);
                const boiteDuBloc = bloc.getBoundingClientRect();
                return {
                    centreDeLEspace: (gaucheUtile + droiteUtile) / 2,
                    centreDuBloc: boiteDuBloc.left + boiteDuBloc.width / 2,
                    largeurDuBloc: boiteDuBloc.width,
                };
            }"""
        )

        self.assertIsNotNone(centrage, "Aucun bloc de lecture sur la page.")
        decalage = abs(centrage["centreDuBloc"] - centrage["centreDeLEspace"])
        self.assertLessEqual(
            decalage,
            DECALAGE_TOLERE_DU_CENTRAGE,
            f"La colonne de lecture est décalée de {decalage:.0f}px "
            f"(bloc de {centrage['largeurDuBloc']:.0f}px). L'étalon tient "
            f"dans {DECALAGE_TOLERE_DU_CENTRAGE}px.",
        )

    def test_le_titre_reste_aligne_sur_le_corps_du_texte(self):
        """
        Le garde-fou du test precedent : on peut centrer la colonne en
        cassant l'alignement du titre sur le texte, ce qui serait pire.
        L'etalon tient les deux.
        / Guard-rail: centring must not break title/body alignment.
        """
        self.ouvrir_la_note_en(1600)

        alignement = self.page.evaluate(
            """() => {
                const titre = document.querySelector('.titre-page-cliquable');
                const corps = document.querySelector('.bloc > .corps');
                if (!titre || !corps) return null;
                return {
                    gaucheDuTitre: titre.getBoundingClientRect().left
                        + parseFloat(getComputedStyle(titre).paddingLeft),
                    gaucheDuCorps: corps.getBoundingClientRect().left,
                };
            }"""
        )

        self.assertIsNotNone(alignement, "Titre ou corps introuvable.")
        ecart = abs(alignement["gaucheDuTitre"] - alignement["gaucheDuCorps"])
        self.assertLessEqual(
            ecart,
            4,
            f"Le titre et le corps du texte ne s'alignent plus : "
            f"{ecart:.0f}px d'écart.",
        )

    def test_un_menu_de_la_barre_ne_passe_pas_sous_le_panneau(self):
        """
        Un menu deroulant de barre d'outils deborde sur la colonne de
        droite. S'il passe SOUS le panneau, il s'ouvre a moitie sans le
        dire — il a juste l'air vide.

        Mesure faite le 12 aout sur le menu « Dashboard », retire depuis :
        il commencait a x=1121, faisait 352px, et le panneau demarrait a
        1233 — 240px tronques. Defaut preexistant, le panneau etant deja
        au-dessus (z-index 70 contre 50). Le test vise desormais le menu
        des taches, seul menu de barre restant, de meme geometrie.
        / A toolbar dropdown must not fall behind the panel.
        """
        self.ouvrir_la_note_en(1600)

        empilement = self.page.evaluate(
            """() => {
                const menu = document.querySelector('.taches-dropdown-wrapper');
                const panneau = document.querySelector('#drawer-overlay');
                if (!menu) return 'menu absent';
                const rangDuMenu = parseInt(getComputedStyle(menu).zIndex, 10);
                const rangDuPanneau = parseInt(
                    getComputedStyle(panneau).zIndex, 10
                );
                return {
                    rangDuMenu,
                    rangDuPanneau: Number.isNaN(rangDuPanneau) ? 0 : rangDuPanneau,
                };
            }"""
        )

        self.assertNotEqual(
            empilement, "menu absent", "Le menu des tâches a disparu de la barre."
        )
        self.assertGreater(
            empilement["rangDuMenu"],
            empilement["rangDuPanneau"],
            "Le menu de la barre passe sous le panneau : il se fera "
            "tronquer.",
        )

    def test_le_voile_disparait_quand_le_panneau_est_une_colonne(self):
        """
        Un voile sur un panneau non modal empeche de lire et de cliquer le
        texte — exactement ce qu'un panneau de preuve ne doit pas faire.
        / A scrim over a non-modal panel blocks the very text it documents.
        """
        self.ouvrir_la_note_en(1600)

        voile = self.mesurer("#drawer-backdrop")

        self.assertFalse(
            voile["visible"], "Le voile masque le texte à côté du panneau."
        )

    # -------------------------------------------------------------------
    # Sous le seuil : un tiroir
    # / Below the threshold: a drawer
    # -------------------------------------------------------------------

    def test_un_tableau_large_defile_dans_sa_boite_et_non_dans_la_page(self):
        """
        Les tableaux sortaient du service en `<pre>` : un `<pre>` ne se
        replie pas, celui du PDF etalon mesurait 3 162px et poussait toute
        la zone de lecture a 3 419px pour 1 586 de large — une barre de
        defilement horizontale sous un texte de lecture, mesuree le 12 aout.

        L'ecart n°6 a depuis ete comble : le service rend un vrai `<table>`
        dans un `.cadre-tableau` en `overflow-x: auto`. CE TEST N'EN
        DEPEND PAS, et c'est voulu — il ne nomme aucune balise. Il eprouve
        la regle d'ossature, qui survit au changement de rendu : un
        contenu large, QUEL QU'IL SOIT, defile DANS SA BOITE plutot que
        d'emporter la page. Le second element le prouve par un autre
        chemin qu'un tableau : un mot insecable de 400 signes.
        / Wide content must scroll inside its own box, not drag the page.
        The rule outlives the <pre> → <table> change: this test names no
        tag, and a 400-char unbreakable word exercises a second route.
        """
        note_a_tableau = self.creer_page_demo(
            "Note à tableau large",
            "<p>Support.</p>",
            owner=self.utilisateur_test,
        )
        note_a_tableau.elements.create(
            ordre=0,
            label="table",
            texte="| colonne |" + " valeur très longue |" * 60,
            empreinte_contenu="empreinte-tableau-large",
        )
        # Un mot insecable long — une URL dans une note web — deborde par un
        # autre chemin que le `<pre>` : rendre la piste de corps retrecissable
        # (`min-width: 0`) sans autoriser la coupure le laisserait pousser la
        # zone de lecture exactement pareil.
        # / A long unbreakable word overflows by a different route than <pre>.
        note_a_tableau.elements.create(
            ordre=1,
            label="text",
            texte="Source : https://exemple.test/" + "a" * 400,
            empreinte_contenu="empreinte-mot-insecable",
        )

        self.page.set_viewport_size({"width": 1600, "height": 1000})
        self.naviguer_vers(f"/lire/{note_a_tableau.pk}/")
        self.attendre_la_mise_en_page("#zone-lecture")

        defilement = self.page.evaluate(
            """() => {
                const zone = document.querySelector('#zone-lecture');
                return {
                    contenu: zone.scrollWidth,
                    visible: zone.clientWidth,
                    page: document.documentElement.scrollWidth,
                    fenetre: window.innerWidth,
                };
            }"""
        )

        self.assertLessEqual(
            defilement["contenu"],
            defilement["visible"] + TOLERANCE_EN_PIXELS,
            "La zone de lecture défile horizontalement : un contenu large "
            "déborde au lieu de défiler dans sa propre boîte.",
        )
        self.assertLessEqual(
            defilement["page"],
            defilement["fenetre"] + TOLERANCE_EN_PIXELS,
            "La page entière défile horizontalement.",
        )

    def test_sous_le_seuil_le_panneau_reste_un_tiroir_large(self):
        """
        Sous 1400px, l'etalon garde le tiroir superpose de 36rem : sur un
        ecran etroit, ceder 368px au panneau rendrait le texte illisible.
        / Below 1400px the wide sliding drawer is the right answer.
        """
        self.ouvrir_la_note_en(SEUIL_DU_PANNEAU_EN_COLONNE - 200)

        # Il faut OUVRIR le tiroir pour l'eprouver. Une premiere version se
        # contentait de le mesurer ferme : `getBoundingClientRect` rend la
        # meme largeur sur un element `translate-x-full`, et `position`
        # vient de la classe Tailwind. Le test passait donc sur un tiroir
        # qui ne s'ouvre jamais.
        # / Measured closed, this test passed on a drawer that never opens.
        self.page.click("#btn-toolbar-drawer")
        # Le tiroir glisse : le mesurer en cours de route donnerait une
        # position intermediaire. On attend qu'il soit immobile.
        # / The drawer slides; wait until it stops instead of guessing.
        self.attendre_la_mise_en_page("#drawer-overlay")

        panneau = self.mesurer("#drawer-overlay")
        voile = self.mesurer("#drawer-backdrop")

        self.assertEqual(panneau["position"], "fixed")
        self.assertGreater(
            panneau["largeur"],
            LARGEUR_ATTENDUE_DU_PANNEAU,
            "Sous le seuil, le tiroir doit rester large.",
        )
        # Ouvert, il doit etre A L'ECRAN, pas seulement large.
        # / Open means on screen, not merely wide.
        self.assertLess(
            panneau["gauche"],
            SEUIL_DU_PANNEAU_EN_COLONNE - 200,
            "Le tiroir est resté hors de l'écran malgré l'ouverture.",
        )
        # AUCUN VOILE, A AUCUNE LARGEUR — decision du mainteneur, 20 aout.
        #
        # Il en revenait un sous le seuil : le tiroir y etait modal, et
        # grisait le texte. Or le panneau existe pour qu'on lise le texte
        # ET ce qui s'y rapporte EN MEME TEMPS — une preuve se compare a
        # l'affirmation qu'elle porte, une extraction au passage dont
        # elle est tiree. Griser le texte pendant qu'on lit la carte
        # retire precisement ce qu'on est venu comparer.
        # / No scrim at any width: the panel exists so that text and what
        # refers to it can be read together.
        self.assertFalse(
            voile["visible"],
            "Un voile grise le texte : le panneau existe pour qu'on lise "
            "les deux en même temps.",
        )
