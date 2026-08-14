"""
Tests E2E — La carte du panneau, comparee a l'etalon.
/ E2E tests — The panel card, measured against the mockup.

LOCALISATION : front/tests/e2e/test_21_carte_du_panneau.py

CE QUE CES TESTS EPROUVENT

L'etalon (maquette.html § 14 « LA CARTE ») donne a chaque carte :

    background   var(--papier)          — PLUS SOMBRE que le panneau
    border       1px var(--filet)
    border-left  3px la couleur du STATUT
    radius       5px
    margin-bottom .5rem

Mesure du 12 aout, panneau du produit contre panneau de l'etalon :

    | | etalon | produit |
    | fond de la carte | rgb(22,21,26) | TRANSPARENT |
    | bord gauche      | 3px couleur du statut | 3px filet |
    | rayon            | 5px | 4px |
    | marge basse      | 8px | 2px (hypostasia.css:477) |

Le fond est le point qui compte : l'etalon pose la carte sur une teinte
plus sombre que le panneau, ce qui la DETACHE. Transparente, elle se
fond dans le panneau et la liste devient un bloc continu.
/ The card must sit on a darker fill than the panel, or the list reads
as one continuous block.
"""

from core.models import AIModel
from front.tests.e2e.base import PlaywrightLiveTestCase
from hypostasis_extractor.models import (
    CommentaireExtraction,
    ExtractedEntity,
    ExtractionJob,
)

# maquette.html § 14. / Mockup § 14.
RAYON_ATTENDU_EN_PIXELS = 5
MARGE_BASSE_ATTENDUE_EN_PIXELS = 8
EPAISSEUR_DU_BORD_DE_STATUT = 3

TOLERANCE_EN_PIXELS = 1


class E2ECarteDuPanneauTest(PlaywrightLiveTestCase):
    """
    LOCALISATION : front/tests/e2e/test_21_carte_du_panneau.py
    """

    def setUp(self):
        super().setUp()
        self.utilisateur_test = self.creer_utilisateur_demo()
        self.se_connecter("testuser", "testpass123")

        self.note = self.creer_page_demo(
            "Note des cartes",
            "<p>Un paragraphe qui porte les idées.</p>",
            owner=self.utilisateur_test,
        )
        modele_simule = AIModel.objects.create(
            name="Mock cartes", model_choice="mock_default", is_active=True
        )
        job = ExtractionJob.objects.create(
            page=self.note,
            ai_model=modele_simule,
            name="Extraction des cartes",
            prompt_description="Support de mesure",
            status="completed",
            entities_count=2,
        )
        # Une idee sans commentaire : statut « nouveau ».
        # / One uncommented idea: status "nouveau".
        ExtractedEntity.objects.create(
            job=job,
            extraction_class="phenomene",
            extraction_text="Une idée que personne n'a encore commentée",
            start_char=0,
            end_char=42,
            attributes={"hypostases": "PHENOMENE", "resume": "Sans débat."},
        )
        # Une idee commentee : le signal la passe en « commente ».
        # / A commented idea: the signal flips it to "commente".
        idee_commentee = ExtractedEntity.objects.create(
            job=job,
            extraction_class="theorie",
            extraction_text="Une idée dont on débat",
            start_char=50,
            end_char=72,
            attributes={"hypostases": "THEORIE", "resume": "En débat."},
        )
        CommentaireExtraction.objects.create(
            entity=idee_commentee,
            user=self.utilisateur_test,
            commentaire="Je ne suis pas d'accord.",
        )

    def mesurer_les_cartes(self):
        """
        Ouvre la note en grand ecran et releve chaque carte avec les
        jetons de l'etalon, resolus dans la page.
        / Open wide and measure each card against page-resolved tokens.
        """
        self.page.set_viewport_size({"width": 1600, "height": 1000})
        self.naviguer_vers(f"/lire/{self.note.pk}/")
        # Les cartes vivent dans le panneau : tant qu'il n'a pas fini de
        # s'ouvrir, leurs boites bougent encore.
        # / The cards live in the panel: while it is still opening, their
        # boxes are still moving.
        self.attendre_la_mise_en_page("#drawer-overlay")

        return self.page.evaluate(
            """() => {
                const jeton = (nom) => {
                    const sonde = document.createElement('div');
                    sonde.style.color = 'var(' + nom + ')';
                    document.body.appendChild(sonde);
                    const resolu = getComputedStyle(sonde).color;
                    sonde.remove();
                    return resolu;
                };
                const cartes = [...document.querySelectorAll('.drawer-carte-compacte')];
                return {
                    papier: jeton('--papier'),
                    papierPanneau: jeton('--papier-panneau'),
                    statutNouveau: jeton('--statut-nouveau'),
                    statutCommente: jeton('--statut-commente'),
                    fondDuPanneau: getComputedStyle(
                        document.querySelector('#drawer-overlay')
                    ).backgroundColor,
                    cartes: cartes.map((carte) => {
                        const style = getComputedStyle(carte);
                        const indicateur = carte.querySelector('.indicateur-statut');
                        return {
                            statut: indicateur ? indicateur.dataset.statut : null,
                            fond: style.backgroundColor,
                            bordGauche: style.borderLeftColor,
                            epaisseurDuBordGauche: parseFloat(style.borderLeftWidth),
                            rayon: parseFloat(style.borderTopLeftRadius),
                            margeBasse: parseFloat(style.marginBottom),
                        };
                    }),
                };
            }"""
        )

    # -------------------------------------------------------------------

    def test_la_carte_se_detache_du_panneau(self):
        """
        Le point qui compte : l'etalon pose la carte sur `--papier`, plus
        sombre que le `--papier-panneau` du panneau. Transparente, la
        carte se fond dans le panneau.
        / The card sits on a darker fill than the panel.
        """
        mesures = self.mesurer_les_cartes()

        self.assertTrue(mesures["cartes"], "Aucune carte dans le panneau.")
        for carte in mesures["cartes"]:
            self.assertNotIn(
                carte["fond"],
                ("rgba(0, 0, 0, 0)", "transparent"),
                "La carte est transparente : elle se fond dans le panneau.",
            )
            self.assertEqual(
                carte["fond"],
                mesures["papier"],
                "Le fond de la carte n'est pas celui de l'étalon "
                "(`--papier`).",
            )
            self.assertNotEqual(
                carte["fond"],
                mesures["fondDuPanneau"],
                "La carte a exactement le fond du panneau.",
            )

    def test_le_bord_gauche_porte_la_couleur_du_statut(self):
        """
        L'etalon fait du bord gauche le porteur du statut — gris pour
        « nouveau », ambre pour « commente ». Sans lui, deux etats se
        ressemblent.
        / The left border carries the debate status in the mockup.
        """
        mesures = self.mesurer_les_cartes()

        couleur_attendue_par_statut = {
            "nouveau": mesures["statutNouveau"],
            "commente": mesures["statutCommente"],
        }
        statuts_rencontres = set()
        for carte in mesures["cartes"]:
            self.assertIn(carte["statut"], couleur_attendue_par_statut)
            statuts_rencontres.add(carte["statut"])
            self.assertAlmostEqual(
                carte["epaisseurDuBordGauche"],
                EPAISSEUR_DU_BORD_DE_STATUT,
                delta=TOLERANCE_EN_PIXELS,
            )
            self.assertEqual(
                carte["bordGauche"],
                couleur_attendue_par_statut[carte["statut"]],
                f"Carte « {carte['statut']} » : le bord gauche ne porte "
                f"pas la couleur de son statut.",
            )

        self.assertEqual(
            statuts_rencontres,
            {"nouveau", "commente"},
            "Les deux statuts doivent être présents pour que ce test "
            "prouve quelque chose.",
        )

    def test_le_panneau_porte_l_etat_du_debat_et_la_synthese(self):
        """
        Le bouton « Lancer la synthese » vivait dans le DASHBOARD de la
        barre d'outils — son seul point d'entree. Le mainteneur a demande
        le retrait du dashboard « et tout le code associe » : retire tel
        quel, il emportait l'acces a la synthese avec lui.

        Le panneau est desormais le lieu unique de l'analyse : les idees,
        l'etat du debat qu'elles dessinent, et la synthese qui en sort.
        C'est aussi ce que demande « tout doit etre integre dans la
        note ».
        / The synthesis button lived in the toolbar dashboard — its only
        entry point. Removing the dashboard would have taken it along.
        """
        self.page.set_viewport_size({"width": 1600, "height": 1000})
        self.naviguer_vers(f"/lire/{self.note.pk}/")
        # Les cartes vivent dans le panneau : tant qu'il n'a pas fini de
        # s'ouvrir, leurs boites bougent encore.
        # / The cards live in the panel: while it is still opening, their
        # boxes are still moving.
        self.attendre_la_mise_en_page("#drawer-overlay")

        pied = self.page.evaluate(
            """() => {
                const panneau = document.querySelector('#drawer-overlay');
                const bouton = panneau.querySelector(
                    '[data-testid="btn-lancer-synthese"]'
                );
                const etat = panneau.querySelector(
                    '[data-testid="etat-du-debat"]'
                );
                return {
                    boutonPresent: !!bouton,
                    boutonVisible: !!(bouton && bouton.offsetParent !== null),
                    etatPresent: !!etat,
                    texteDeLEtat: etat ? etat.innerText.replace(/\\s+/g, ' ').trim() : null,
                };
            }"""
        )

        self.assertTrue(
            pied["boutonPresent"],
            "Le bouton « Lancer la synthèse » n'est nulle part dans le "
            "panneau : l'accès à la synthèse est perdu.",
        )
        self.assertTrue(pied["boutonVisible"], "Le bouton est présent mais caché.")
        self.assertTrue(
            pied["etatPresent"],
            "L'état du débat, que le dashboard portait, a disparu.",
        )
        # Une idee commentee sur deux, posee au montage.
        # / One commented idea out of two, set up above.
        self.assertIn("1", pied["texteDeLEtat"])
        self.assertIn("2", pied["texteDeLEtat"])

    def test_le_rayon_et_la_marge_suivent_l_etalon(self):
        """5px et .5rem, pas 4px et 2px."""
        mesures = self.mesurer_les_cartes()

        for carte in mesures["cartes"]:
            self.assertAlmostEqual(
                carte["rayon"], RAYON_ATTENDU_EN_PIXELS, delta=TOLERANCE_EN_PIXELS
            )
            self.assertAlmostEqual(
                carte["margeBasse"],
                MARGE_BASSE_ATTENDUE_EN_PIXELS,
                delta=TOLERANCE_EN_PIXELS,
            )
