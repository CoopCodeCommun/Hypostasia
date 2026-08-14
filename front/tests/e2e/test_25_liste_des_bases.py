"""
Tests E2E — LA LISTE DES BASES DE CONNAISSANCES (/bases/) en cartes.
/ E2E tests — the knowledge-base directory (/bases/) as a card grid.

LOCALISATION : front/tests/e2e/test_25_liste_des_bases.py

POURQUOI CE MODULE
------------------
Le menu burger va mener ICI. /bases/ cesse d'etre un ecran secondaire
pour devenir une PORTE D'ENTREE : c'est souvent le premier ecran qu'un
visiteur voit. Or, mesure au navigateur le 12 aout 2026, la page rendait
un titre, un compteur, un lien, et UNE LIGNE de liste :

    « Bases de connaissances / 1 base visible / → Voir les carnets »
    « 🌐 public  Démonstration  1 carnet · par jonas »

Trois manques, dans l'ordre de gravite :

1. Rien n'explique CE QU'EST une base. Le mot « base de connaissances »
   ne dit pas qu'elle rassemble des carnets d'un collectif — et le seul
   endroit ou le produit l'expliquait etait l'etat VIDE, c'est-a-dire
   l'ecran que personne ne voit une fois qu'une base existe.
2. `BaseDeConnaissances.description` existe sur le modele et n'etait
   affiche NULLE PART — meme defaut que `Dossier.description` avant la
   confrontation du 12 aout sur /carnets/.
3. Une ligne de liste ne dit pas ce que la base CONTIENT. Or dans la
   base de developpement la description est vide : sans un substitut,
   la carte serait un cartouche vide. Le substitut retenu est le
   SOMMAIRE — les carnets reellement dedans, ceux que le visiteur peut
   ouvrir. C'est de la donnee reelle, jamais un texte d'attente.

Ces tests MESURENT : texte exact, nombre de colonnes calcule par la
grille, teinte calculee de la cote, contraste WCAG en clair ET en
sombre, et debordement horizontal en pixels. Ils ne se contentent pas
de constater la presence d'un noeud.
/ The tests measure computed values, not node presence.

LA NON-FUITE EST TESTEE
-----------------------
Le sommaire NOMME des carnets. La doctrine du corpus est qu'on ne nomme
jamais un carnet que le demandeur ne peut pas lire (front/views_corpus.py,
`retrieve`). Un test dedie verifie qu'un carnet prive d'autrui n'apparait
ni dans le compteur, ni dans le sommaire.
/ The summary NAMES notebooks, so it is tested for leaks.
"""

from django.contrib.auth.models import User
from django.core.files.base import ContentFile

from core.models import (
    AppartenanceDossierBase,
    BaseDeConnaissances,
    Dossier,
    VisibiliteDossier,
)

from .base import PlaywrightLiveTestCase

# WCAG 1.4.3 : 4,5:1 pour du texte normal. La description d'une base et
# son pied de carte sont du texte lu, pas des ornements.
# / WCAG 1.4.3: 4.5:1 for normal text.
CONTRASTE_MINIMAL_DU_TEXTE = 4.5

# WCAG 1.4.11 : 3:1 pour une limite qui porte a elle seule une
# information — ici le filet de cote, qui distingue une base d'une autre
# dans la grille. / WCAG 1.4.11: 3:1 for an informative boundary.
CONTRASTE_MINIMAL_DU_CONTOUR = 3.0

# Fonction de contraste WCAG evaluee DANS la page. Reprise de
# test_24_liste_des_carnets.py : `color-mix()` rend des canaux en 0-1 la
# ou `rgb()` les rend en 0-255, et les confondre fausse le resultat d'un
# ordre de grandeur.
# / In-page WCAG contrast helper (see test_24 for the 0-1 vs 0-255 trap).
OUTILS_DE_CONTRASTE = """
    const versCanaux = (couleur) => {
        const nombres = couleur.match(/[\\d.]+/g).slice(0, 3).map(Number);
        return couleur.includes('color(')
            ? nombres.map((canal) => canal * 255)
            : nombres;
    };
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


class E2ELaListeDesBasesTest(PlaywrightLiveTestCase):
    """
    LOCALISATION : front/tests/e2e/test_25_liste_des_bases.py

    Un jeu de donnees qui couvre les TROIS etats d'une carte :
    une base decrite, une base sans description (le cas de la base de
    developpement), et une base sans aucun carnet.
    / A dataset covering the three card states.
    """

    DESCRIPTION_DE_LA_BASE = (
        "Les carnets de veille du reseau : un carnet par territoire, "
        "plus un carnet transversal pour les appels a projets."
    )

    def setUp(self):
        super().setUp()
        self.utilisateur = User.objects.create_user(
            username="e2e_liste_bases", password="test1234",
        )
        self.autre_utilisateur = User.objects.create_user(
            username="e2e_bases_autrui", password="test1234",
        )

        # LA BASE DECRITE — celle qui doit tout montrer.
        # / The described base: it must show everything.
        self.base_decrite = BaseDeConnaissances.objects.create(
            nom="Reseau des tiers-lieux",
            slug="reseau-des-tiers-lieux",
            description=self.DESCRIPTION_DE_LA_BASE,
            owner=self.utilisateur,
            visibilite=VisibiliteDossier.PUBLIC,
        )
        # LA BASE SANS DESCRIPTION — le cas reel de la base de
        # developpement. Sa carte doit rester pleine grace au sommaire.
        # / The description-less base: the real dev-database case.
        self.base_nue = BaseDeConnaissances.objects.create(
            nom="Lycee Jean Moulin",
            slug="lycee-jean-moulin",
            owner=self.utilisateur,
            visibilite=VisibiliteDossier.PUBLIC,
        )
        # LA BASE SANS CARNET — ni description, ni contenu : le pire cas.
        # / The empty base: neither description nor content.
        self.base_sans_carnet = BaseDeConnaissances.objects.create(
            nom="Zzz base sans carnet",
            slug="zzz-base-sans-carnet",
            owner=self.utilisateur,
            visibilite=VisibiliteDossier.PUBLIC,
        )

        # Deux carnets LISIBLES dans la base decrite, et deux notes dans
        # le premier — de quoi mesurer les compteurs derives.
        # / Two readable notebooks, two notes in the first one.
        self.carnet_visible = Dossier.objects.create(
            name="Veille Occitanie", owner=self.utilisateur,
            visibilite=VisibiliteDossier.PUBLIC,
        )
        self.second_carnet_visible = Dossier.objects.create(
            name="Appels a projets", owner=self.utilisateur,
            visibilite=VisibiliteDossier.PUBLIC,
        )
        for numero in range(2):
            self.creer_page_demo(
                titre=f"Compte rendu n°{numero + 1}",
                owner=self.utilisateur,
                dossier=self.carnet_visible,
            )
        # UN CARNET PRIVE D'AUTRUI, range dans la meme base : il ne doit
        # etre ni compte ni NOMME (doctrine de non-fuite du corpus).
        # / A stranger's private notebook: never counted, never named.
        self.carnet_d_autrui = Dossier.objects.create(
            name="Carnet confidentiel d'autrui", owner=self.autre_utilisateur,
            visibilite=VisibiliteDossier.PRIVE,
        )
        for carnet in (self.carnet_visible, self.second_carnet_visible,
                       self.carnet_d_autrui):
            AppartenanceDossierBase.objects.create(
                dossier=carnet, base=self.base_decrite,
            )

        # Un carnet dans la base nue, pour que son sommaire ait de quoi
        # remplacer la description. / One notebook in the bare base.
        self.carnet_du_lycee = Dossier.objects.create(
            name="Terminale B — projet climat", owner=self.utilisateur,
            visibilite=VisibiliteDossier.PUBLIC,
        )
        AppartenanceDossierBase.objects.create(
            dossier=self.carnet_du_lycee, base=self.base_nue,
        )

        # UNE SEULE des quatre bases porte une couverture. C'est le bon
        # ratio : le champ vient d'etre ajoute, il sera vide partout
        # ailleurs pendant longtemps. La carte sans image est donc le cas
        # NORMAL, pas le cas degrade.
        # / Only one of the four bases has a cover: the coverless card is
        # the normal case, not the degraded one.
        self.base_illustree = BaseDeConnaissances.objects.create(
            nom="Cooperative des Trois Vallees",
            slug="cooperative-des-trois-vallees",
            description="Les carnets de la cooperative, saison par saison.",
            owner=self.utilisateur,
            visibilite=VisibiliteDossier.PUBLIC,
        )
        self.base_illustree.image_de_couverture.save(
            "couverture_de_test.png",
            ContentFile(self._png_de_test()),
            save=True,
        )

        self.se_connecter("e2e_liste_bases", "test1234")

    def tearDown(self):
        # Le fichier televerse vit dans MEDIA_ROOT, hors base de donnees :
        # le rollback de transaction ne l'efface pas. Sans ce nettoyage,
        # chaque execution laisse un PNG de plus dans media/.
        # / The uploaded file lives outside the database; the transaction
        # rollback does not remove it.
        if self.base_illustree.image_de_couverture:
            self.base_illustree.image_de_couverture.delete(save=False)
        super().tearDown()

    @staticmethod
    def _png_de_test():
        """
        Un PNG minuscule, fabrique a la volee : `ImageField` valide
        l'image a l'enregistrement, un faux octet ne passerait pas.
        / A tiny real PNG: ImageField validates on save.
        """
        from io import BytesIO

        from PIL import Image

        tampon = BytesIO()
        Image.new("RGB", (240, 120), (120, 140, 110)).save(tampon, format="PNG")
        return tampon.getvalue()

    # ------------------------------------------------------------------
    # Helpers de mesure / measurement helpers
    # ------------------------------------------------------------------

    def ouvrir_la_liste(self, largeur=1400):
        """
        Ouvre /bases/ a une largeur donnee. 1400 px est la largeur ou la
        maquette de reference a ete mesuree.
        / Open /bases/ at a given width.
        """
        self.page.set_viewport_size({"width": largeur, "height": 1000})
        self.naviguer_vers("/bases/")
        self.page.wait_for_selector('[data-testid="corpus-bases-liste"]')

    def carte_de_la_base(self, base):
        """La carte d'une base donnee. / A given base's card."""
        return self.page.wait_for_selector(
            f'[data-testid="corpus-base-item"][data-base-slug="{base.slug}"]'
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

    def basculer_en_sombre(self):
        """
        Force le theme sombre par l'attribut que pose le selecteur du
        produit (`#bascule-theme` ecrit data-theme sur <html>), puis
        laisse un tour de boucle au navigateur pour recalculer.
        / Force the dark theme the way the product's toggle does.
        """
        self.page.evaluate(
            "() => document.documentElement.setAttribute('data-theme', 'dark')"
        )
        self.page.wait_for_timeout(120)

    # ------------------------------------------------------------------
    # 1. LA PAGE EXPLIQUE CE QU'ELLE LISTE
    # ------------------------------------------------------------------

    def test_l_entete_explique_ce_qu_est_une_base(self):
        """
        Le burger menera ici : c'est souvent le PREMIER ecran. Le seul
        endroit ou le produit expliquait le mot « base » etait l'etat
        vide — donc l'ecran que plus personne ne voit des qu'une base
        existe. L'explication doit etre permanente.
        / The burger will land here; the explanation must be permanent.
        """
        self.ouvrir_la_liste()
        introduction = self.page.query_selector(
            '[data-testid="corpus-bases-intro"]'
        )
        self.assertIsNotNone(
            introduction,
            "L'en-tete ne porte aucune introduction : un visiteur qui "
            "arrive par le burger ne sait pas ce qu'est une base.",
        )
        texte = self.texte_condense(introduction)
        self.assertIn(
            "carnet", texte.lower(),
            "L'introduction doit dire qu'une base rassemble des CARNETS "
            f"— lu : « {texte} »",
        )
        self.assertGreater(
            len(texte), 80,
            f"Introduction trop courte pour expliquer quoi que ce soit : "
            f"« {texte} »",
        )

    def test_l_entete_totalise_la_collection(self):
        """
        L'etalon totalise dans son en-tete (« 12 bases de connaissances »),
        et /carnets/ le fait deja. Savoir ce que pese la collection AVANT
        d'ouvrir quoi que ce soit.
        / The header totals the collection, as /carnets/ already does.
        """
        self.ouvrir_la_liste()
        compteur = self.page.query_selector('[data-testid="corpus-bases-compteur"]')
        self.assertIsNotNone(compteur, "Aucun compteur dans l'en-tete.")
        texte = self.texte_condense(compteur)
        self.assertIn("4 bases", texte, f"Lu : « {texte} »")
        # 3 carnets visibles au total (2 dans la base decrite + 1 dans la
        # base nue), le carnet prive d'autrui exclu.
        self.assertIn("3 carnets", texte, f"Lu : « {texte} »")

    # ------------------------------------------------------------------
    # 2. LA GRILLE DE CARTES
    # ------------------------------------------------------------------

    def test_les_bases_sont_rendues_en_grille_de_cartes(self):
        """
        Une vue par carte, demandee par le mainteneur. La grille doit
        VRAIMENT etre une grille : on mesure les colonnes calculees, pas
        la presence d'une classe (le build Tailwind est fige, une classe
        arbitraire y serait inerte).
        / Measure the computed columns, not the presence of a class:
        the Tailwind build is frozen and arbitrary classes are inert.
        """
        self.ouvrir_la_liste(largeur=1400)
        grille = self.page.query_selector('[data-testid="corpus-bases-grille"]')
        self.assertIsNotNone(grille, "Aucune grille de cartes.")
        colonnes = self.page.evaluate(
            "(element) => getComputedStyle(element).gridTemplateColumns",
            grille,
        )
        self.assertGreaterEqual(
            len(colonnes.split()), 2,
            f"La grille ne fait qu'une colonne en 1400 px : « {colonnes} ». "
            "La regle CSS n'agit pas.",
        )

    def test_la_grille_retombe_a_une_colonne_sur_mobile(self):
        """
        375 px : une carte par rang, sans debordement horizontal.
        / One card per row on a phone, with no horizontal overflow.
        """
        self.ouvrir_la_liste(largeur=375)
        grille = self.page.query_selector('[data-testid="corpus-bases-grille"]')
        colonnes = self.page.evaluate(
            "(element) => getComputedStyle(element).gridTemplateColumns",
            grille,
        )
        self.assertEqual(
            len(colonnes.split()), 1,
            f"La grille garde {len(colonnes.split())} colonnes en 375 px : "
            f"« {colonnes} »",
        )
        debordement = self.page.evaluate(
            "() => document.documentElement.scrollWidth"
            " - document.documentElement.clientWidth"
        )
        self.assertLessEqual(
            debordement, 0,
            f"La page deborde de {debordement} px en 375 px de large.",
        )

    # ------------------------------------------------------------------
    # 3. LA DESCRIPTION, ET SON SUBSTITUT
    # ------------------------------------------------------------------

    def test_la_carte_porte_la_description_de_la_base(self):
        """
        `BaseDeConnaissances.description` existe sur le modele et n'etait
        affiche nulle part. / The field existed and was shown nowhere.
        """
        self.ouvrir_la_liste()
        carte = self.carte_de_la_base(self.base_decrite)
        description = carte.query_selector(
            '[data-testid="corpus-base-description"]'
        )
        self.assertIsNotNone(
            description,
            "La carte ne porte pas la description alors que la base en a "
            f"une : « {self.DESCRIPTION_DE_LA_BASE} »",
        )
        self.assertIn(
            "carnet par territoire", self.texte_condense(description),
        )

    def test_une_base_sans_description_montre_son_sommaire(self):
        """
        LE CAS DE LA BASE DE DEVELOPPEMENT : `description=""`. Sans
        substitut, la carte serait vide. Le substitut est de la DONNEE
        REELLE — les carnets dedans — jamais un texte d'attente.
        / The dev-database case: a real-data substitute, never filler.
        """
        self.ouvrir_la_liste()
        carte = self.carte_de_la_base(self.base_nue)
        self.assertIsNone(
            carte.query_selector('[data-testid="corpus-base-description"]'),
            "Une base sans description ne doit pas rendre le bloc vide.",
        )
        sommaire = carte.query_selector('[data-testid="corpus-base-sommaire"]')
        self.assertIsNotNone(
            sommaire,
            "Une base sans description doit montrer ce qu'elle CONTIENT.",
        )
        self.assertIn(
            "Terminale B", self.texte_condense(sommaire),
        )

    def test_le_sommaire_ne_nomme_aucun_carnet_interdit(self):
        """
        LA NON-FUITE. Le sommaire nomme des carnets : il ne doit jamais
        nommer celui d'autrui reste prive. Meme doctrine que « dans N
        carnets » et que le detail d'une base.
        / The summary names notebooks; it must never name a stranger's
        private one.
        """
        self.ouvrir_la_liste()
        carte = self.carte_de_la_base(self.base_decrite)
        texte_de_la_carte = self.texte_condense(carte)
        self.assertNotIn(
            "confidentiel", texte_de_la_carte.lower(),
            "Le carnet prive d'un autre utilisateur est NOMME dans la "
            f"carte : « {texte_de_la_carte} »",
        )

    def test_une_base_sans_carnet_le_dit_au_lieu_de_se_taire(self):
        """
        Ni description ni carnet : la carte doit rester lisible et dire
        l'etat, pas laisser un trou. / Neither description nor notebook:
        the card states the fact instead of leaving a hole.
        """
        self.ouvrir_la_liste()
        carte = self.carte_de_la_base(self.base_sans_carnet)
        texte = self.texte_condense(carte)
        self.assertIn(
            "aucun carnet", texte.lower(),
            f"La carte d'une base vide ne dit rien de son etat : « {texte} »",
        )

    # ------------------------------------------------------------------
    # 4. LE PIED DE CARTE — LES COMPTEURS DERIVES
    # ------------------------------------------------------------------

    def test_le_pied_de_carte_porte_les_compteurs_derives(self):
        """
        Carnets, notes, proprietaire : les seules metadonnees que le
        modele porte vraiment (il n'a ni image ni type de base).
        / The only metadata the model really carries.
        """
        self.ouvrir_la_liste()
        carte = self.carte_de_la_base(self.base_decrite)
        pied = carte.query_selector('[data-testid="corpus-base-pied"]')
        self.assertIsNotNone(pied, "La carte n'a pas de pied de metadonnees.")
        # `inner_text` rend le texte TEL QU'AFFICHE, donc en capitales :
        # le pied est mis en capitales par le CSS, pas par le gabarit.
        # Que le balisage garde bien « 1 carnet » en minuscules est
        # verifie ailleurs, par test_corpus_phase_h (lecture du HTML).
        # / inner_text returns the rendered text, uppercased by CSS.
        texte = self.texte_condense(pied).lower()
        # 2 carnets visibles (le carnet prive d'autrui est exclu).
        self.assertIn("2 carnets", texte, f"Lu : « {texte} »")
        self.assertIn("2 notes", texte, f"Lu : « {texte} »")
        self.assertIn("e2e_liste_bases", texte, f"Lu : « {texte} »")

    def test_le_pied_est_en_monospace_et_le_titre_en_serif(self):
        """
        « La police dit la provenance » : monospace = donnee DERIVEE
        (compteurs), serif = texte ECRIT par un humain (nom,
        description). Confondre les deux ferait passer une phrase pour
        un compteur. / The typeface states the provenance.
        """
        self.ouvrir_la_liste()
        carte = self.carte_de_la_base(self.base_decrite)
        police_du_pied = self.page.evaluate(
            "(carte) => getComputedStyle("
            "carte.querySelector('[data-testid=\"corpus-base-pied\"]')"
            ").fontFamily",
            carte,
        )
        police_du_titre = self.page.evaluate(
            "(carte) => getComputedStyle("
            "carte.querySelector('[data-testid=\"corpus-base-lien\"]')"
            ").fontFamily",
            carte,
        )
        self.assertIn("mono", police_du_pied.lower(), police_du_pied)
        self.assertIn("georgia", police_du_titre.lower(), police_du_titre)

    # ------------------------------------------------------------------
    # 5. LA COTE — L'IDENTITE VISUELLE SANS IMAGE
    # ------------------------------------------------------------------

    def test_la_cote_est_teintee_et_deterministe(self):
        """
        Le modele n'a pas d'image de couverture. La carte porte donc un
        filet de COTE, teinte derivee du slug : deux bases differentes
        se distinguent d'un coup d'oeil dans la grille, et la meme base
        garde sa teinte d'un chargement a l'autre.
        / No cover image on the model: a slug-derived tint distinguishes
        the cards, and it must be stable across loads.
        """
        toutes_les_bases = (
            self.base_decrite, self.base_nue,
            self.base_sans_carnet, self.base_illustree,
        )
        self.ouvrir_la_liste()
        teintes = {}
        for base in toutes_les_bases:
            carte = self.carte_de_la_base(base)
            cote = carte.query_selector('[data-testid="corpus-base-cote"]')
            self.assertIsNotNone(
                cote, f"Pas de cote sur la carte « {base.nom} »",
            )
            teintes[base.slug] = self.page.evaluate(
                "(element) => getComputedStyle(element).backgroundColor",
                cote,
            )
        # Huit teintes disponibles : une collision reste possible et
        # acceptee (la cote aide a distinguer, elle n'identifie pas — le
        # NOM identifie). Ce qu'on refuse, c'est une grille monochrome.
        # / Eight tints: a collision is possible and accepted; a
        # monochrome grid is not.
        self.assertGreaterEqual(
            len(set(teintes.values())), 3,
            f"Les quatre bases se partagent moins de trois teintes : "
            f"{teintes}",
        )

        # DETERMINISME : on recharge, la teinte ne bouge pas. Le piege
        # est `hash()`, sale par processus en Python — deux workers
        # gunicorn donneraient deux couleurs a la meme base.
        # / Determinism: Python's hash() is per-process salted.
        premieres_teintes = dict(teintes)
        self.ouvrir_la_liste()
        for base in toutes_les_bases:
            carte = self.carte_de_la_base(base)
            cote = carte.query_selector('[data-testid="corpus-base-cote"]')
            teinte_rechargee = self.page.evaluate(
                "(element) => getComputedStyle(element).backgroundColor",
                cote,
            )
            self.assertEqual(
                teinte_rechargee, premieres_teintes[base.slug],
                f"La teinte de « {base.nom} » change d'un chargement a "
                "l'autre.",
            )

    # ------------------------------------------------------------------
    # 5 bis. LA COUVERTURE FACULTATIVE
    # ------------------------------------------------------------------

    def test_une_base_avec_couverture_affiche_son_image(self):
        """
        Le champ `image_de_couverture` a ete ajoute au modele : quand il
        est rempli, la carte le montre. / When the field is filled, the
        card shows it.
        """
        self.ouvrir_la_liste()
        carte = self.carte_de_la_base(self.base_illustree)
        couverture = carte.query_selector(
            '[data-testid="corpus-base-couverture"]'
        )
        self.assertIsNotNone(
            couverture,
            "La base porte une image de couverture et la carte ne "
            "l'affiche pas.",
        )
        # Chargee pour de bon : un <img> casse a naturalWidth == 0.
        # / Actually loaded: a broken <img> has naturalWidth == 0.
        largeur_naturelle = self.page.evaluate(
            "(element) => element.naturalWidth", couverture,
        )
        self.assertGreater(
            largeur_naturelle, 0,
            "L'image de couverture ne se charge pas (URL media fausse ?).",
        )

    def test_une_base_sans_couverture_ne_reserve_aucun_cadre_vide(self):
        """
        LA CONDITION DU MAINTENEUR. Le champ sera vide sur toute base
        existante : une carte sans image ne doit pas ressembler a une
        carte a laquelle il manque quelque chose. Elle ne reserve donc
        AUCUNE place — elle commence directement a sa cote.
        / A coverless card must not look like a card with something
        missing: it reserves no slot, it starts at its call-number band.
        """
        self.ouvrir_la_liste()
        carte_nue = self.carte_de_la_base(self.base_nue)
        self.assertIsNone(
            carte_nue.query_selector('[data-testid="corpus-base-couverture"]'),
            "Une base sans couverture rend quand meme un cadre d'image.",
        )
        # Le premier enfant peint de la carte est la cote : rien ne
        # s'intercale. / Nothing sits above the call-number band.
        premier_bloc = self.page.evaluate(
            "(carte) => carte.firstElementChild.getAttribute('data-testid')",
            carte_nue,
        )
        self.assertEqual(
            premier_bloc, "corpus-base-cote",
            f"Le premier bloc de la carte sans image est « {premier_bloc} » "
            "et non la cote : un emplacement vide subsiste.",
        )

    def test_la_cote_tient_le_contraste_en_clair_et_en_sombre(self):
        """
        Le filet de cote distingue les cartes : WCAG 1.4.11 lui demande
        3:1. Mesure DANS la page, dans les deux themes — le mode sombre
        se verifie, il ne se suppose pas.
        / Measured in-page, in both themes.
        """
        self.ouvrir_la_liste()
        for theme in ("clair", "sombre"):
            if theme == "sombre":
                self.basculer_en_sombre()
            for base in (self.base_decrite, self.base_nue,
                         self.base_sans_carnet):
                carte = self.carte_de_la_base(base)
                cote = carte.query_selector('[data-testid="corpus-base-cote"]')
                ratio = self.page.evaluate(
                    OUTILS_DE_CONTRASTE + """
                    (element) => {
                        const fond = getComputedStyle(
                            element.closest('[data-testid="corpus-base-item"]')
                        ).backgroundColor;
                        return contraste(
                            getComputedStyle(element).backgroundColor,
                            fond,
                            fondDuCorpus(),
                        );
                    }
                    """,
                    cote,
                )
                self.assertGreaterEqual(
                    ratio, CONTRASTE_MINIMAL_DU_CONTOUR,
                    f"Cote de « {base.nom} » en {theme} : {ratio:.2f}:1, "
                    f"sous le seuil de {CONTRASTE_MINIMAL_DU_CONTOUR}:1.",
                )

    def test_le_texte_des_cartes_tient_le_contraste_dans_les_deux_themes(self):
        """
        Description (serif) et pied (monospace) sont du texte lu :
        WCAG 1.4.3 leur demande 4,5:1, en clair comme en sombre.
        / Reading text needs 4.5:1 in both themes.
        """
        self.ouvrir_la_liste()
        for theme in ("clair", "sombre"):
            if theme == "sombre":
                self.basculer_en_sombre()
            carte = self.carte_de_la_base(self.base_decrite)
            for testid in ("corpus-base-description", "corpus-base-pied",
                           "corpus-base-lien"):
                ratio = self.page.evaluate(
                    OUTILS_DE_CONTRASTE + """
                    ([carte, testid]) => {
                        const cible = carte.querySelector(
                            '[data-testid="' + testid + '"]'
                        );
                        return contraste(
                            getComputedStyle(cible).color,
                            getComputedStyle(carte).backgroundColor,
                            fondDuCorpus(),
                        );
                    }
                    """,
                    [carte, testid],
                )
                self.assertGreaterEqual(
                    ratio, CONTRASTE_MINIMAL_DU_TEXTE,
                    f"« {testid} » en {theme} : {ratio:.2f}:1, sous le "
                    f"seuil de {CONTRASTE_MINIMAL_DU_TEXTE}:1.",
                )

    def test_la_carte_suit_les_tokens_en_sombre(self):
        """
        Le piege du mode sombre est la couleur ecrite en dur : une carte
        peinte en blanc reste blanche quand tout le reste bascule. On
        verifie que le fond de la carte a CHANGE entre les deux themes.
        / The dark-mode trap is a hard-coded colour.
        """
        self.ouvrir_la_liste()
        carte = self.carte_de_la_base(self.base_decrite)
        fond_clair = self.page.evaluate(
            "(element) => getComputedStyle(element).backgroundColor", carte,
        )
        self.basculer_en_sombre()
        carte = self.carte_de_la_base(self.base_decrite)
        fond_sombre = self.page.evaluate(
            "(element) => getComputedStyle(element).backgroundColor", carte,
        )
        self.assertNotEqual(
            fond_clair, fond_sombre,
            f"Le fond de la carte ne bascule pas : {fond_clair} dans les "
            "deux themes — une couleur est ecrite en dur.",
        )

    # ------------------------------------------------------------------
    # 6. CREER UNE BASE — L'ACTION RESTE DANS LA GRILLE
    # ------------------------------------------------------------------

    def test_la_creation_est_la_derniere_cellule_de_la_grille(self):
        """
        Sur une porte d'entree, « + Nouvelle base » ne doit pas passer
        AVANT la collection. L'action prend la forme d'une carte, en fin
        de grille : on lit d'abord ce qui existe.
        / On an entry point, the create affordance follows the
        collection instead of preceding it.
        """
        self.ouvrir_la_liste()
        formulaire = self.page.query_selector(
            '[data-testid="corpus-base-creer-form"]'
        )
        self.assertIsNotNone(formulaire, "Le formulaire de creation a disparu.")
        est_dans_la_grille = self.page.evaluate(
            "(element) => element.closest("
            "'[data-testid=\"corpus-bases-grille\"]') !== null",
            formulaire,
        )
        self.assertTrue(
            est_dans_la_grille,
            "Le formulaire de creation n'est pas une cellule de la grille.",
        )
        position_du_formulaire = self.page.evaluate(
            "(element) => element.getBoundingClientRect().top", formulaire,
        )
        premiere_carte = self.carte_de_la_base(self.base_decrite)
        position_de_la_carte = self.page.evaluate(
            "(element) => element.getBoundingClientRect().top", premiere_carte,
        )
        self.assertGreaterEqual(
            position_du_formulaire, position_de_la_carte,
            "La carte de creation passe avant la collection.",
        )


class E2ELaListeDesBasesVideTest(PlaywrightLiveTestCase):
    """
    L'ETAT VIDE, qui a sa propre classe faute de pouvoir vider le jeu de
    donnees de la precedente.
    / The empty state, in its own class.

    LOCALISATION : front/tests/e2e/test_25_liste_des_bases.py

    C'est le premier ecran d'une installation neuve — et, le burger y
    menant, le tout premier ecran d'un nouvel utilisateur. Il doit
    EXPLIQUER, pas constater (audit UX D4), et laisser l'action a portee.
    / This is a fresh install's first screen: it must explain, not just
    state, and keep the action within reach.
    """

    def setUp(self):
        super().setUp()
        self.utilisateur = User.objects.create_user(
            username="e2e_bases_vide", password="test1234",
        )
        self.se_connecter("e2e_bases_vide", "test1234")

    def test_l_etat_vide_explique_et_laisse_creer(self):
        self.page.set_viewport_size({"width": 1400, "height": 1000})
        self.naviguer_vers("/bases/")
        self.page.wait_for_selector('[data-testid="corpus-bases-liste"]')

        bloc_vide = self.page.query_selector('[data-testid="corpus-bases-vide"]')
        self.assertIsNotNone(bloc_vide, "Aucun etat vide sur une liste vide.")
        texte = " ".join(bloc_vide.inner_text().split())
        self.assertIn("Aucune base", texte, f"Lu : « {texte} »")

        # L'explication de l'en-tete reste la : c'est elle qui dit ce
        # qu'est une base, l'etat vide n'a plus qu'a dire quoi faire.
        # / The header keeps explaining; the empty state only acts.
        self.assertIsNotNone(
            self.page.query_selector('[data-testid="corpus-bases-intro"]'),
            "L'introduction disparait quand la liste est vide.",
        )
        # Et la carte de creation reste offerte.
        # / And the create card is still offered.
        self.assertIsNotNone(
            self.page.query_selector('[data-testid="corpus-base-creer-form"]'),
            "Rien ne permet de creer la premiere base.",
        )
        self.assertEqual(
            0,
            self.page.evaluate(
                "() => document.documentElement.scrollWidth"
                " - document.documentElement.clientWidth"
            ),
        )

    def test_un_visiteur_anonyme_n_a_pas_de_formulaire_mais_une_consigne(self):
        """
        Anonyme : pas de formulaire, mais on lui dit pourquoi et quoi
        faire — un ecran vide sans explication est un cul-de-sac.
        / Anonymous: no form, but a reason and a next step.
        """
        self.page.goto(f"{self.live_server_url}/auth/logout/")
        self.page.set_viewport_size({"width": 1400, "height": 1000})
        self.naviguer_vers("/bases/")
        self.page.wait_for_selector('[data-testid="corpus-bases-liste"]')
        self.assertIsNone(
            self.page.query_selector('[data-testid="corpus-base-creer-form"]'),
            "Un visiteur anonyme se voit offrir le formulaire de creation.",
        )
        texte = " ".join(
            self.page.inner_text('[data-testid="corpus-bases-vide"]').split()
        )
        self.assertIn("Connectez-vous", texte, f"Lu : « {texte} »")

    def test_creer_une_base_rend_la_grille_mise_a_jour(self):
        """
        LE TOUR COMPLET HTMX. `create` renvoie `self.list(request)` : le
        gabarit refondu est donc rendu une seconde fois, par un chemin
        different (POST). Si le contexte de `list` oubliait une des
        variables neuves — `nombre_de_bases`, `numero_de_cote` — la
        grille reviendrait muette apres une creation, et aucun test de
        GET ne le verrait.
        / The full HTMX round trip: create() re-renders the rebuilt
        template through a different path, so a context variable missing
        there would go unseen by any GET test.
        """
        self.page.set_viewport_size({"width": 1400, "height": 1000})
        self.naviguer_vers("/bases/")
        self.page.wait_for_selector('[data-testid="corpus-bases-liste"]')

        self.page.fill('[data-testid="corpus-base-creer-nom"]',
                       "Cooperative du Haut Pays")
        self.page.click('[data-testid="corpus-base-creer-form"] button')
        carte = self.page.wait_for_selector(
            '[data-testid="corpus-base-item"]'
            '[data-base-slug="cooperative-du-haut-pays"]',
            timeout=5000,
        )
        self.assertIn(
            "Cooperative du Haut Pays", " ".join(carte.inner_text().split()),
        )
        # La cote est peinte des la creation : le numero vient de la vue,
        # pas d'une valeur par defaut du gabarit.
        # / The tint is painted from creation on.
        cote = carte.query_selector('[data-testid="corpus-base-cote"]')
        self.assertIsNotNone(cote, "La base creee n'a pas de cote.")
        # Le compteur d'en-tete a suivi. / The header counter followed.
        self.assertIn(
            "1 base",
            " ".join(
                self.page.inner_text(
                    '[data-testid="corpus-bases-compteur"]'
                ).split()
            ),
        )
