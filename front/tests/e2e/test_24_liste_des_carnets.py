"""
Tests E2E — LA LISTE DES CARNETS (/carnets/) confrontee a l'etalon.
/ E2E tests — the notebook list screen against the reference mockup.

LOCALISATION : front/tests/e2e/test_24_liste_des_carnets.py

POURQUOI CE MODULE
------------------
L'etalon `front/static/front/maquettes/corpus.html` (vue « base ») rend
chaque carnet avec une sous-ligne COMPLETE, mesuree au navigateur le
12 aout :

    « 9 notes · 2 wikis · 2 synthèses · 3 axes de classement »

Le produit, a la meme date, sur /carnets/ :

    « 6 notes · par jonas »

Manquaient donc : les wikis, les syntheses, les etiquettes du carnet
dans ses bases, et la DESCRIPTION du carnet — un champ qui existe sur
le modele (`Dossier.description`) et qu'aucun gabarit n'affichait.

Deux defauts de plus, trouves en confrontant les deux ecrans :

1. Le compteur de notes de la LISTE comptait aussi les wikis et les
   syntheses (l'annotation ne filtrait pas `type_de_note`), tandis que
   le DETAIL, lui, ne compte que les notes. Le meme carnet annoncait
   donc deux nombres differents selon l'ecran.
2. L'etalon affiche TOUJOURS « X sur Y notes » (mesure : « 5 sur 9
   notes » sans aucun filtre actif). Le produit ne l'affichait qu'une
   fois un filtre coche : sans filtre, aucun compteur.

Les tests MESURENT : texte exact, couleur calculee des etiquettes,
contraste WCAG en clair ET en sombre, et debordement horizontal en
pixels. Ils ne se contentent pas de constater la presence d'un noeud.
/ The tests measure: exact text, computed colours, WCAG contrast in
both themes, and horizontal overflow in pixels.
"""

from django.contrib.auth.models import User

from core.models import (
    AppartenanceDossierBase,
    BaseDeConnaissances,
    CategorieBase,
    CategorieDossier,
    Dossier,
    ListeDeCategories,
    Page,
    SyntheseDirigee,
    TypeDeNote,
    VisibiliteDossier,
    Wiki,
)
from core.services.corpus import ranger_une_note_dans_un_carnet

from .base import PlaywrightLiveTestCase

# WCAG 1.4.3 : 4,5:1 pour du texte normal. La description d'un carnet
# est du texte de lecture, pas un ornement.
# / WCAG 1.4.3: 4.5:1 for normal text. A description is reading text.
CONTRASTE_MINIMAL_DU_TEXTE = 4.5

# WCAG 1.4.11 : 3:1 pour un contour qui porte a lui seul une
# information — ici la teinte d'une etiquette de categorie.
# / WCAG 1.4.11: 3:1 for a boundary that carries information.
CONTRASTE_MINIMAL_DU_CONTOUR = 3.0

# Fonction de contraste WCAG evaluee DANS la page. Reprise telle quelle
# de test_19_toast_sombre.py : color-mix() rend des canaux en 0-1 la ou
# rgb() les rend en 0-255, et les confondre fausse le resultat d'un
# ordre de grandeur.
# / WCAG contrast helper, evaluated in-page (see test_19 for the
# color-mix() 0-1 versus rgb() 0-255 trap).
OUTILS_DE_CONTRASTE = """
    const versCanaux = (couleur) => {
        const nombres = couleur.match(/[\\d.]+/g).slice(0, 3).map(Number);
        return couleur.includes('color(')
            ? nombres.map((canal) => canal * 255)
            : nombres;
    };
    /* L'alpha d'une couleur, 1 par defaut. `color-mix(... , transparent)`
       — ce que rend .etiquette-categorie — sort avec un alpha, et lire
       ses trois premiers canaux revient a mesurer la teinte PURE au lieu
       du melange reellement affiche.
       / A colour's alpha; color-mix(..., transparent) carries one, and
       ignoring it measures the pure tint instead of what is shown. */
    const alphaDe = (couleur) => {
        const nombres = couleur.match(/[\\d.]+/g);
        if (couleur.startsWith('rgba') && nombres.length >= 4) {
            return Number(nombres[3]);
        }
        if (couleur.includes('/')) {
            return Number(couleur.split('/')[1].match(/[\\d.]+/)[0]);
        }
        return 1;
    };
    /* Compose une couleur semi-transparente SUR son fond : c'est la
       couleur que l'oeil recoit, donc la seule sur laquelle un
       contraste veuille dire quelque chose.
       / Composite a translucent colour over its backdrop. */
    const composer = (dessus, canauxDuFond) => {
        const a = alphaDe(dessus);
        if (a >= 1) { return versCanaux(dessus); }
        const haut = versCanaux(dessus);
        return haut.map(
            (canal, index) => canal * a + canauxDuFond[index] * (1 - a)
        );
    };
    const luminanceDesCanaux = (canaux) => {
        const [r, v, b] = canaux.map((canal) => {
            const proportion = canal / 255;
            return proportion <= 0.03928
                ? proportion / 12.92
                : Math.pow((proportion + 0.055) / 1.055, 2.4);
        });
        return 0.2126 * r + 0.7152 * v + 0.0722 * b;
    };
    /* `fond` est la surface reellement peinte derriere les deux
       couleurs — .zone-corpus, et non <body>, dont le fond peut etre
       transparent : un fond transparent rend un contraste absurde. */
    const contraste = (premiere, seconde, fond) => {
        const repere = fond || seconde;
        const a = luminanceDesCanaux(composer(premiere, versCanaux(repere)));
        const b = luminanceDesCanaux(composer(seconde, versCanaux(repere)));
        return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
    };
    /* La surface peinte du corpus : c'est elle qui porte --papier. */
    const fondDuCorpus = () => getComputedStyle(
        document.querySelector('.zone-corpus')
    ).backgroundColor;
"""


class E2ELaListeDesCarnetsTest(PlaywrightLiveTestCase):
    """
    LOCALISATION : front/tests/e2e/test_24_liste_des_carnets.py

    Un jeu de donnees qui ressemble a celui de l'etalon : une base, un
    carnet riche (description, guide, axes, wikis, syntheses, etiquettes
    de base) et un carnet nu, pour verifier que les compteurs a zero
    restent tus.
    / A dataset shaped like the reference: one base, one rich notebook,
    one bare notebook to check that zero counters stay silent.
    """

    DESCRIPTION_DU_CARNET = (
        "Les seances du conseil, une note par seance, dans l'ordre du fil."
    )

    def setUp(self):
        super().setUp()
        self.utilisateur = User.objects.create_user(
            username="e2e_liste_carnets", password="test1234",
        )

        # LE CARNET RICHE — celui qui doit tout montrer.
        # / The rich notebook: it must show everything.
        self.carnet_riche = Dossier.objects.create(
            name="Conseil d'administration",
            owner=self.utilisateur,
            visibilite=VisibiliteDossier.PUBLIC,
            description=self.DESCRIPTION_DU_CARNET,
            guide_de_redaction="Une note par seance. Le titre porte la date.",
        )
        # UN CARNET NU — aucun wiki, aucune synthese, aucun axe : ses
        # compteurs a zero doivent rester invisibles (audit UX D7).
        # / A bare notebook: its zero counters must stay invisible.
        self.carnet_nu = Dossier.objects.create(
            name="Zzz carnet nu",
            owner=self.utilisateur,
            visibilite=VisibiliteDossier.PUBLIC,
        )

        # TROIS NOTES SOURCES dans le carnet riche. Elles portent un nom
        # de fichier d'origine : c'est ce qui donne a leur sous-ligne
        # plus d'un element, donc de quoi mesurer les separateurs.
        # / Three source notes, with an original filename so their
        # sub-line has more than one item to separate.
        for numero in range(3):
            note = self.creer_page_demo(
                titre=f"Seance n°{numero + 1}",
                owner=self.utilisateur,
                dossier=self.carnet_riche,
            )
            note.original_filename = f"seance-{numero + 1}.pdf"
            note.save(update_fields=["original_filename"])

        # DEUX WIKIS ET UNE SYNTHESE. Leurs pages sont RANGEES dans le
        # carnet, exactement comme le fait le produit
        # (front/views_synthese.py:454 et :837) : c'est ce rangement qui
        # faisait gonfler le compteur de notes de la liste.
        # / Two wikis and one synthesis, filed exactly as the product
        # files them — which is what inflated the list's note counter.
        for numero in range(2):
            page_de_wiki = Page.objects.create(
                title=f"Wiki n°{numero + 1}",
                owner=self.utilisateur,
                type_de_note=TypeDeNote.WIKI,
                status="completed",
            )
            ranger_une_note_dans_un_carnet(
                page_de_wiki, self.carnet_riche, self.utilisateur,
            )
            Wiki.objects.create(
                page=page_de_wiki,
                dossier=self.carnet_riche,
                sujet=f"Sujet du wiki {numero + 1}",
            )

        page_de_synthese = Page.objects.create(
            title="Synthese du conseil",
            owner=self.utilisateur,
            type_de_note=TypeDeNote.SYNTHESE,
            status="completed",
        )
        ranger_une_note_dans_un_carnet(
            page_de_synthese, self.carnet_riche, self.utilisateur,
        )
        SyntheseDirigee.objects.create(
            page=page_de_synthese,
            dossier=self.carnet_riche,
            produite_par=self.utilisateur,
        )

        # UN AXE DE CLASSEMENT sur le carnet (compteur « N axes »).
        # / One classification axis on the notebook.
        axe_du_carnet = ListeDeCategories.objects.create(
            nom="Type", dossier=self.carnet_riche,
        )
        CategorieDossier.objects.create(liste=axe_du_carnet, nom="Compte rendu")

        # LA BASE ET SES ETIQUETTES : les « tags » d'un carnet vivent sur
        # la RELATION carnet<->base, comme ceux d'une note vivent sur la
        # relation note<->carnet (SPEC-corpus § 3.2).
        # / A notebook's tags live on the notebook<->base relation.
        self.base = BaseDeConnaissances.objects.create(
            nom="Cooperative des Trois Vallees",
            slug="cooperative-trois-vallees",
            owner=self.utilisateur,
            visibilite=VisibiliteDossier.PUBLIC,
        )
        axe_de_la_base = ListeDeCategories.objects.create(
            nom="Instance", base=self.base,
        )
        self.categorie_gouvernance = CategorieBase.objects.create(
            liste=axe_de_la_base, nom="Gouvernance", couleur="#0072B2", ordre=0,
        )
        self.categorie_budget = CategorieBase.objects.create(
            liste=axe_de_la_base, nom="Budget", couleur="#D55E00", ordre=1,
        )
        appartenance_de_base = AppartenanceDossierBase.objects.create(
            dossier=self.carnet_riche, base=self.base,
            integre_par=self.utilisateur,
        )
        appartenance_de_base.categories.add(
            self.categorie_gouvernance, self.categorie_budget,
        )

        self.se_connecter("e2e_liste_carnets", "test1234")

    # ------------------------------------------------------------------
    # Helpers de mesure / measurement helpers
    # ------------------------------------------------------------------

    def ouvrir_la_liste(self):
        """
        Ouvre /carnets/ en 1400 px de large — la largeur ou l'etalon a
        ete mesure. / Open /carnets/ at the width the reference was
        measured at.
        """
        self.page.set_viewport_size({"width": 1400, "height": 1000})
        self.naviguer_vers("/carnets/")
        self.page.wait_for_selector('[data-testid="corpus-carnets-liste"]')

    def ligne_du_carnet(self, carnet):
        """
        La ligne <li> d'un carnet donne. / A given notebook's row.
        """
        return self.page.wait_for_selector(
            f'[data-testid="corpus-carnet-item"][data-carnet-id="{carnet.pk}"]'
        )

    def texte_condense(self, element):
        """
        Le texte d'un element, espaces normalises — sans quoi les sauts
        de ligne du gabarit rendent toute comparaison illisible.
        / An element's text with whitespace collapsed.
        """
        if element is None:
            return ""
        return " ".join(element.inner_text().split())

    # ------------------------------------------------------------------
    # 1. LA DESCRIPTION DU CARNET
    # ------------------------------------------------------------------

    def test_la_ligne_porte_la_description_du_carnet(self):
        """
        `Dossier.description` existe depuis la phase corpus et n'etait
        affichee NULLE PART. Une liste de carnets sans description
        oblige a ouvrir chaque carnet pour savoir ce qu'il contient.
        / The description field existed and was displayed nowhere.
        """
        self.ouvrir_la_liste()
        ligne = self.ligne_du_carnet(self.carnet_riche)
        description = ligne.query_selector(
            '[data-testid="corpus-carnet-description"]'
        )
        self.assertIsNotNone(
            description,
            "La ligne du carnet ne porte aucune description alors que "
            f"le carnet en a une : « {self.DESCRIPTION_DU_CARNET} »",
        )
        self.assertEqual(
            self.texte_condense(description), self.DESCRIPTION_DU_CARNET,
        )

    def test_un_carnet_sans_description_n_affiche_pas_de_bloc_vide(self):
        """
        Pas de bloc vide qui pousse la ligne suivante : le carnet nu ne
        doit rien reserver. / No empty block on a description-less row.
        """
        self.ouvrir_la_liste()
        ligne = self.ligne_du_carnet(self.carnet_nu)
        self.assertIsNone(
            ligne.query_selector('[data-testid="corpus-carnet-description"]'),
            "Un carnet sans description ne doit pas rendre le bloc.",
        )

    # ------------------------------------------------------------------
    # 2. LES ETIQUETTES (« LES TAGS »)
    # ------------------------------------------------------------------

    def test_la_ligne_porte_les_etiquettes_du_carnet(self):
        """
        Les etiquettes d'un carnet — ses categories dans les bases
        auxquelles il appartient — n'apparaissaient que dans le detail
        d'UNE base. La liste des carnets les ignorait.
        / A notebook's tags only showed inside one base's detail.
        """
        self.ouvrir_la_liste()
        ligne = self.ligne_du_carnet(self.carnet_riche)
        etiquettes = ligne.query_selector_all(
            '[data-testid="corpus-carnet-categorie"]'
        )
        noms = sorted(self.texte_condense(e) for e in etiquettes)
        self.assertEqual(
            noms, ["Budget", "Gouvernance"],
            "Les deux etiquettes du carnet dans sa base sont absentes "
            f"de la liste (trouve : {noms}).",
        )

    def test_l_etiquette_porte_la_teinte_de_sa_categorie(self):
        """
        MESURE et non lecture du DOM : la couleur calculee du contour
        doit etre celle de la categorie, pas le filet par defaut. Le
        remappage `.border-slate-*` de maquette.css a deja efface des
        teintes posees en style inline.
        / Measured, not read: the computed border colour must be the
        category's, not the default rule.
        """
        self.ouvrir_la_liste()
        mesures = self.page.evaluate(
            OUTILS_DE_CONTRASTE
            + """
            (identifiantDuCarnet) => {
                const ligne = document.querySelector(
                    '[data-testid="corpus-carnet-item"]'
                    + '[data-carnet-id="' + identifiantDuCarnet + '"]'
                );
                if (!ligne) { return null; }
                const etiquettes = Array.from(ligne.querySelectorAll(
                    '[data-testid="corpus-carnet-categorie"]'
                ));
                const fond = fondDuCorpus();
                return etiquettes.map((etiquette) => {
                    const style = getComputedStyle(etiquette);
                    return {
                        nom: etiquette.textContent.trim(),
                        couleurDuContour: style.borderTopColor,
                        contrasteDuContour: contraste(
                            style.borderTopColor, fond, fond
                        ),
                        contrasteDuTexte: contraste(
                            style.color, style.backgroundColor, fond
                        ),
                    };
                });
            }""",
            str(self.carnet_riche.pk),
        )
        self.assertTrue(
            mesures, "Aucune etiquette mesurable sur la ligne du carnet.",
        )
        couleurs_attendues = {
            "Gouvernance": "rgb(0, 114, 178)",   # #0072B2
            "Budget": "rgb(213, 94, 0)",         # #D55E00
        }
        for mesure in mesures:
            self.assertEqual(
                mesure["couleurDuContour"], couleurs_attendues[mesure["nom"]],
                f"L'etiquette « {mesure['nom']} » n'a pas la teinte de sa "
                f"categorie : {mesure['couleurDuContour']}",
            )
            self.assertGreaterEqual(
                mesure["contrasteDuTexte"], CONTRASTE_MINIMAL_DU_TEXTE,
                f"Texte de l'etiquette « {mesure['nom']} » peu lisible : "
                f"{mesure['contrasteDuTexte']:.2f}:1",
            )

    # ------------------------------------------------------------------
    # 3. LES COMPTEURS DERIVES
    # ------------------------------------------------------------------

    def test_la_sous_ligne_compte_notes_wikis_syntheses_et_axes(self):
        """
        La sous-ligne de l'etalon, mesuree : « 9 notes · 2 wikis ·
        2 synthèses · 3 axes de classement ». Le produit s'arretait aux
        notes. / The reference's sub-line, measured.
        """
        self.ouvrir_la_liste()
        ligne = self.ligne_du_carnet(self.carnet_riche)
        sous_ligne = self.texte_condense(ligne.query_selector(".sous-note"))
        self.assertEqual(
            sous_ligne,
            "3 notes · 2 wikis · 1 synthèse · 1 axe de classement "
            "· par e2e_liste_carnets",
            "La sous-ligne du carnet ne dit pas ce que dit l'etalon.",
        )

    def test_le_compteur_de_notes_ignore_wikis_et_syntheses(self):
        """
        Le carnet porte 3 notes, 2 wikis et 1 synthese, soit 6
        appartenances. La LISTE annoncait « 6 notes » quand le DETAIL
        annoncait « 3 notes » : deux nombres pour un meme carnet.
        / The list said 6, the detail said 3, for the same notebook.
        """
        self.ouvrir_la_liste()
        ligne = self.ligne_du_carnet(self.carnet_riche)
        self.assertIn(
            "3 notes", self.texte_condense(ligne.query_selector(".sous-note")),
        )

        self.naviguer_vers(f"/carnets/{self.carnet_riche.pk}/")
        meta_du_detail = self.texte_condense(
            self.page.wait_for_selector(
                '[data-testid="corpus-carnet-detail"] .meta'
            )
        )
        self.assertIn(
            "3 notes", meta_du_detail,
            "Le detail et la liste doivent annoncer le meme nombre.",
        )

    def test_les_compteurs_a_zero_restent_tus(self):
        """
        Dire « 0 wiki · 0 synthèse · 0 axe » vingt fois n'informe
        personne (audit UX D7). L'etalon lui-meme tait les wikis et les
        syntheses a zero. / Zero counters stay silent.
        """
        self.ouvrir_la_liste()
        sous_ligne = self.texte_condense(
            self.ligne_du_carnet(self.carnet_nu).query_selector(".sous-note")
        )
        for mot_interdit in ("wiki", "synthèse", "axe"):
            self.assertNotIn(
                mot_interdit, sous_ligne,
                f"Le carnet nu annonce « {mot_interdit} » a zero : "
                f"« {sous_ligne} »",
            )

    def test_l_entete_totalise_les_notes_et_les_syntheses(self):
        """
        L'etalon, vue base, mesure : « 4 carnets · 10 notes ·
        4 synthèses ». Le produit disait « 1 carnet visible », sans
        aucun total. / The reference totals notes and syntheses.
        """
        self.ouvrir_la_liste()
        meta = self.texte_condense(
            self.page.query_selector(
                '[data-testid="corpus-carnets-liste"] .entete-zone .meta'
            )
        )
        self.assertEqual(
            meta, "2 carnets visibles · 3 notes · 3 synthèses",
            "L'en-tete de la liste ne totalise pas comme l'etalon.",
        )

    # ------------------------------------------------------------------
    # 4. LE DETAIL DU CARNET
    # ------------------------------------------------------------------

    def test_le_detail_montre_la_description_du_carnet(self):
        """
        Le detail affichait le guide de redaction mais jamais la
        description. / The detail showed the guide, never the
        description.
        """
        self.page.set_viewport_size({"width": 1400, "height": 1000})
        self.naviguer_vers(f"/carnets/{self.carnet_riche.pk}/")
        description = self.page.wait_for_selector(
            '[data-testid="corpus-carnet-description"]'
        )
        self.assertEqual(
            self.texte_condense(description), self.DESCRIPTION_DU_CARNET,
        )

    def test_le_compteur_de_notes_s_affiche_sans_aucun_filtre(self):
        """
        Mesure de l'etalon SANS filtre actif : « 5 sur 9 notes ». Le
        produit n'affichait le resume qu'une fois un filtre coche : sans
        filtre, le lecteur ne savait pas combien de notes il regardait.
        / Measured on the reference with no filter: "5 sur 9 notes".
        """
        self.page.set_viewport_size({"width": 1400, "height": 1000})
        self.naviguer_vers(f"/carnets/{self.carnet_riche.pk}/")
        resume = self.page.wait_for_selector(
            '[data-testid="corpus-resume-filtres"]'
        )
        self.assertEqual(
            self.texte_condense(resume), "3 sur 3 notes",
            "Sans filtre, le compteur de notes doit rester affiche.",
        )

    def test_la_sous_ligne_d_une_note_est_ponctuee_de_separateurs(self):
        """
        L'etalon ponctue : « conseil.m4a · 3 min 12 · 10 extractions ».
        Le produit collait « fichier presentation.pdf 0 extractions ».
        Le separateur etant desormais un ::before, on MESURE la propriete
        `content` calculee — innerText ne voit pas le contenu genere.
        / The separator is a ::before, so we measure the computed
        `content`: innerText cannot see generated content.
        """
        self.page.set_viewport_size({"width": 1400, "height": 1000})
        self.naviguer_vers(f"/carnets/{self.carnet_riche.pk}/")
        self.page.wait_for_selector('[data-testid="corpus-note-item"]')
        mesures = self.page.evaluate(
            """() => {
                const sousLigne = document.querySelector(
                    '[data-testid="corpus-note-item"] .sous-note'
                );
                const morceaux = Array.from(sousLigne.children);
                return morceaux.map((morceau, rang) => ({
                    rang,
                    contenuGenere: getComputedStyle(
                        morceau, '::before'
                    ).content,
                }));
            }"""
        )
        self.assertGreaterEqual(
            len(mesures), 2,
            "Il faut au moins deux elements pour qu'un separateur ait un "
            "sens.",
        )
        # Le PREMIER n'a pas de separateur — c'est tout l'interet de le
        # poser en CSS. / The first item carries none: that is the point.
        self.assertNotIn(
            "·", mesures[0]["contenuGenere"],
            "Le premier element de la sous-ligne ne doit pas etre "
            f"precede d'un point : {mesures[0]['contenuGenere']}",
        )
        for mesure in mesures[1:]:
            self.assertIn(
                "·", mesure["contenuGenere"],
                f"L'element n°{mesure['rang']} n'est pas separe du "
                f"precedent : {mesure['contenuGenere']}",
            )

    # ------------------------------------------------------------------
    # 5. LISIBILITE ET GEOMETRIE — mesurees, en clair et en sombre
    # ------------------------------------------------------------------

    def mesurer_la_ligne_en(self, theme):
        """
        Force le theme, puis rend les mesures de la ligne du carnet
        riche. / Force the theme, then measure the rich notebook's row.
        """
        self.ouvrir_la_liste()
        return self.page.evaluate(
            OUTILS_DE_CONTRASTE
            + """
            ([theme, identifiantDuCarnet]) => {
                document.documentElement.setAttribute('data-theme', theme);
                const ligne = document.querySelector(
                    '[data-testid="corpus-carnet-item"]'
                    + '[data-carnet-id="' + identifiantDuCarnet + '"]'
                );
                const description = ligne.querySelector(
                    '[data-testid="corpus-carnet-description"]'
                );
                const zone = document.querySelector('.zone-corpus');
                const fond = fondDuCorpus();
                return {
                    contrasteDeLaDescription: description
                        ? contraste(
                            getComputedStyle(description).color, fond, fond
                        )
                        : null,
                    tailleDeLaDescription: description
                        ? parseFloat(getComputedStyle(description).fontSize)
                        : null,
                    debordementDeLaZone:
                        zone.scrollWidth - zone.clientWidth,
                    debordementDeLaLigne:
                        ligne.scrollWidth - ligne.clientWidth,
                };
            }""",
            [theme, str(self.carnet_riche.pk)],
        )

    def verifier_la_lisibilite_en(self, theme):
        """
        Une description illisible ne vaut pas mieux qu'une description
        absente. / An unreadable description is no better than none.
        """
        mesures = self.mesurer_la_ligne_en(theme)
        self.assertIsNotNone(
            mesures["contrasteDeLaDescription"],
            f"[{theme}] Pas de description a mesurer.",
        )
        self.assertGreaterEqual(
            mesures["contrasteDeLaDescription"], CONTRASTE_MINIMAL_DU_TEXTE,
            f"[{theme}] Description peu lisible : "
            f"{mesures['contrasteDeLaDescription']:.2f}:1",
        )
        # 12 px est le plancher que le reste du design system respecte
        # (0.8rem = 12,8 px). En dessous, le texte n'est plus du texte.
        # / 12px is the floor the rest of the design system holds.
        self.assertGreaterEqual(
            mesures["tailleDeLaDescription"], 12.0,
            f"[{theme}] Description trop petite : "
            f"{mesures['tailleDeLaDescription']} px",
        )

    def test_la_description_reste_lisible_en_clair(self):
        self.verifier_la_lisibilite_en("light")

    def test_la_description_reste_lisible_en_sombre(self):
        self.verifier_la_lisibilite_en("dark")

    def test_la_ligne_enrichie_ne_deborde_pas_horizontalement(self):
        """
        Quatre compteurs, deux etiquettes et une description sur la
        meme ligne : on verifie EN PIXELS que rien ne pousse une barre
        de defilement horizontale.
        / Measured in pixels: nothing must force a horizontal scrollbar.
        """
        mesures = self.mesurer_la_ligne_en("light")
        self.assertLessEqual(
            mesures["debordementDeLaZone"], 0,
            "La zone corpus deborde horizontalement de "
            f"{mesures['debordementDeLaZone']} px.",
        )
        self.assertLessEqual(
            mesures["debordementDeLaLigne"], 0,
            "La ligne du carnet deborde horizontalement de "
            f"{mesures['debordementDeLaLigne']} px.",
        )
