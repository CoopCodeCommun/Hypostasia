"""
Tests E2E — La bande de contexte : fil d'Ariane et titre du panneau.
/ E2E tests — The context strip: breadcrumb and panel title.

LOCALISATION : front/tests/e2e/test_31_bande_de_contexte.py

CE QUE CES TESTS EPROUVENT

Remarque du mainteneur, 12 aout : « La hauteur n'est pas la meme que le
menu du fil d'Ariane. Pour moi, ca devrait etre le meme menu, la meme
div. Et on peut mettre les barres de defilement en dessous, sur les deux
div de l'article et la div des extractions. »

Mesure avant correction : fil d'Ariane 32px (`min-height: 2rem`),
en-tete du panneau 40,6px. Deux bandes cote a cote, a deux hauteurs
differentes, separees par un decrochement de 8px que rien ne justifie.

CE QUE LA FUSION CHANGE, ET POURQUOI C'EST PLUS SOLIDE

Aligner deux bandes distinctes, c'est tenir deux regles egales a la
main : elles derivent des qu'on touche a l'une. Les fondre en UNE div
rend l'alignement vrai PAR CONSTRUCTION — il n'y a plus qu'une hauteur.

Sous la bande, les deux colonnes defilent chacune de son cote : le
texte long ne pousse pas les cartes, et la liste des idees ne pousse
pas le texte.

ECART ASSUME AVEC L'ETALON. `maquette.html` garde deux bandes : le fil
traverse la page, et le panneau porte son propre en-tete dessous.
Arbitrage du mainteneur, 12 aout.
/ Aligning two strips means keeping two rules equal by hand; merging
them makes the alignment true by construction. Deliberate departure
from the mockup, decided by the maintainer.
"""

from core.models import AIModel
from front.tests.e2e.base import PlaywrightLiveTestCase
from hypostasis_extractor.models import ExtractedEntity, ExtractionJob

# Au-dela du seuil, le panneau occupe sa colonne. / Above this, a column.
LARGEUR_AVEC_PANNEAU = 1600

TOLERANCE_EN_PIXELS = 2


class E2EBandeDeContexteTest(PlaywrightLiveTestCase):
    """
    LOCALISATION : front/tests/e2e/test_31_bande_de_contexte.py
    """

    def setUp(self):
        super().setUp()
        self.utilisateur_test = self.creer_utilisateur_demo()
        self.se_connecter("testuser", "testpass123")

        # LA NOTE DOIT VIVRE DANS UN CARNET. Sans carnet, pas de chemin,
        # donc pas de fil d'Ariane — et la bande s'efface d'elle-meme
        # (`:not(:has(.fil-ariane))`), ce qui est le comportement voulu :
        # une bande vide serait une barre grise sans raison d'etre.
        # / No notebook, no path, no breadcrumb — and the strip steps
        # aside, which is intended: an empty strip is a pointless bar.
        self.carnet = self.creer_dossier_demo(
            nom="Carnet de la bande", owner=self.utilisateur_test,
        )
        self.note = self.creer_page_demo(
            "Note de la bande",
            "<p>Un paragraphe.</p>",
            owner=self.utilisateur_test,
            dossier=self.carnet,
        )
        # Assez de texte pour que la colonne de lecture ait de quoi
        # defiler : sans cela, le test du defilement ne mesure rien.
        # / Enough text for the reading column to actually scroll.
        for rang in range(30):
            self.note.elements.create(
                ordre=rang,
                label="text",
                texte=(
                    f"Paragraphe {rang}. Du texte en quantite suffisante "
                    f"pour que la colonne de lecture deborde de la hauteur "
                    f"de la fenetre et doive defiler."
                ),
                empreinte_contenu=f"empreinte-bande-{rang}",
            )
        modele_simule = AIModel.objects.create(
            name="Mock bande", model_choice="mock_default", is_active=True
        )
        job = ExtractionJob.objects.create(
            page=self.note,
            ai_model=modele_simule,
            name="Extraction de la bande",
            prompt_description="Support",
            status="completed",
            entities_count=1,
        )
        ExtractedEntity.objects.create(
            job=job,
            extraction_class="phenomene",
            extraction_text="Une idée",
            start_char=0,
            end_char=8,
            attributes={"hypostases": "PHENOMENE", "resume": "Une idée."},
        )

    def mesurer(self):
        """Releve la bande et les deux colonnes. / Measure strip and columns."""
        self.page.set_viewport_size(
            {"width": LARGEUR_AVEC_PANNEAU, "height": 900}
        )
        self.naviguer_vers(f"/lire/{self.note.pk}/")
        # La bande est l'objet meme de la mesure : on attend qu'elle soit
        # posee, plutot que de dormir le temps qu'elle le soit peut-etre.
        # / Wait for the very thing being measured to settle.
        self.attendre_la_mise_en_page('[data-testid="bande-de-contexte"]')

        return self.page.evaluate(
            """() => {
                const boite = (selecteur) => {
                    const element = document.querySelector(selecteur);
                    if (!element) return null;
                    const rect = element.getBoundingClientRect();
                    const style = getComputedStyle(element);
                    return {
                        haut: rect.top, bas: rect.bottom,
                        gauche: rect.left, droite: rect.right,
                        hauteur: rect.height, largeur: rect.width,
                        defileVerticalement: element.scrollHeight
                            > element.clientHeight + 2,
                        overflowY: style.overflowY,
                    };
                };
                const bande = document.querySelector('[data-testid="bande-de-contexte"]');
                const fil = document.querySelector('#fil-ariane');
                const titre = document.querySelector('#drawer-titre');
                return {
                    bande: boite('[data-testid="bande-de-contexte"]'),
                    filDansLaBande: !!(bande && fil && bande.contains(fil)),
                    titreDansLaBande: !!(bande && titre && bande.contains(titre)),
                    lecture: boite('#zone-lecture'),
                    panneau: boite('#drawer-contenu'),
                };
            }"""
        )

    # -------------------------------------------------------------------

    def test_le_fil_et_le_titre_du_panneau_partagent_une_seule_bande(self):
        """
        Le coeur de la demande : une seule div, donc une seule hauteur.
        / One div, therefore one height.
        """
        mesures = self.mesurer()

        self.assertIsNotNone(
            mesures["bande"], "Aucune bande de contexte sur la page."
        )
        self.assertTrue(
            mesures["filDansLaBande"],
            "Le fil d'Ariane vit hors de la bande de contexte.",
        )
        self.assertTrue(
            mesures["titreDansLaBande"],
            "Le titre du panneau vit hors de la bande de contexte.",
        )

    def test_la_bande_traverse_toute_la_page(self):
        """
        Elle porte le contexte des DEUX colonnes : elle doit les couvrir.
        / It carries the context of both columns, so it must span them.
        """
        mesures = self.mesurer()

        self.assertAlmostEqual(
            mesures["bande"]["largeur"],
            LARGEUR_AVEC_PANNEAU,
            delta=20,
            msg="La bande ne traverse pas la page.",
        )

    def test_les_deux_colonnes_commencent_sous_la_bande(self):
        """
        Rien ne passe derriere elle : c'est ce qui distingue une bande
        d'un bandeau flottant. / Nothing slides under it.
        """
        mesures = self.mesurer()

        self.assertGreaterEqual(
            mesures["lecture"]["haut"],
            mesures["bande"]["bas"] - TOLERANCE_EN_PIXELS,
            "La zone de lecture démarre au-dessus du bas de la bande.",
        )
        self.assertGreaterEqual(
            mesures["panneau"]["haut"],
            mesures["bande"]["bas"] - TOLERANCE_EN_PIXELS,
            "Le panneau démarre au-dessus du bas de la bande.",
        )

    def test_les_deux_colonnes_defilent_chacune_de_son_cote(self):
        """
        « les barres de defilement en dessous, sur les deux div ». Un
        texte long ne doit pas pousser les cartes, ni l'inverse.
        / A long text must not push the cards, nor the reverse.
        """
        mesures = self.mesurer()

        self.assertIn(
            mesures["lecture"]["overflowY"],
            ("auto", "scroll"),
            "La colonne de lecture ne défile pas d'elle-même.",
        )
        self.assertIn(
            mesures["panneau"]["overflowY"],
            ("auto", "scroll"),
            "La colonne des extractions ne défile pas d'elle-même.",
        )
        self.assertTrue(
            mesures["lecture"]["defileVerticalement"],
            "Le décor de test ne produit pas assez de texte pour que la "
            "lecture défile : ce test ne mesure rien.",
        )

    def test_la_bande_reste_visible_quand_le_texte_defile(self):
        """
        Le fil dit OU l'on est : il doit rester lisible pendant qu'on
        descend dans le document.
        / The breadcrumb says where you are: it must stay legible.
        """
        mesures_avant = self.mesurer()
        haut_avant = mesures_avant["bande"]["haut"]

        self.page.evaluate(
            """() => {
                document.querySelector('#zone-lecture').scrollTop = 1200;
            }"""
        )
        self.attendre_la_mise_en_page('[data-testid="bande-de-contexte"]')

        haut_apres = self.page.evaluate(
            """() => document
                .querySelector('[data-testid="bande-de-contexte"]')
                .getBoundingClientRect().top"""
        )

        self.assertAlmostEqual(
            haut_apres,
            haut_avant,
            delta=TOLERANCE_EN_PIXELS,
            msg="La bande de contexte est partie avec le défilement.",
        )
