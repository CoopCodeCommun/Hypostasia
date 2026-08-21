"""
Verrouille l'outil qui TYPE un ecart entre une extraction et sa source.
/ Locks the tool that TYPES a gap between an extraction and its source.

LOCALISATION : hypostasis_extractor/tests/test_typage_des_non_verbatim.py

POURQUOI CE TEST EXISTE. Le banc d'extraction annonce un taux de
verbatim. Ce taux ne dit pas COMMENT le modele echoue — or c'est la
seule chose qui permet de corriger le prompt. L'outil type donc chaque
ecart, et ce test fige la definition de chaque type : sans lui, un
reglage de seuil deplacerait silencieusement des cas d'une colonne a
l'autre, et la mesure publiee changerait de sens sans changer de
chiffre.

Le module mesure vit hors des apps Django (`benchmarks/`), qui n'est pas
un paquet importable : on le charge donc par son chemin.
/ The bench module lives outside Django apps; loaded by path.
"""

import importlib.util
from pathlib import Path

from django.test import SimpleTestCase

CHEMIN_DU_MODULE = (
    Path(__file__).resolve().parents[2]
    / "benchmarks" / "extraction_format" / "typer_les_non_verbatim.py"
)


def _charger_le_module_de_typage():
    """Charge le module de banc par son chemin. / Loads bench module by path."""
    specification = importlib.util.spec_from_file_location(
        "typer_les_non_verbatim", CHEMIN_DU_MODULE,
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


# Une source courte mais realiste : deux phrases separees par une phrase
# intercalaire, ce qui permet de fabriquer un vrai saut.
# / A short but realistic source, with an intervening sentence.
SOURCE = (
    "Le badge est un objet technique simple. "
    "Il a ete concu en 2011 par la Badge Alliance. "
    "Il peut etre mis en oeuvre au niveau d'un etablissement."
)


class TypageDUnEcartEntreUneExtractionEtSaSource(SimpleTestCase):
    """Chaque type d'ecart, un test. / One test per gap type."""

    def setUp(self):
        self.typer = _charger_le_module_de_typage().typer_l_ecart

    def test_une_citation_recopiee_mot_pour_mot_est_verbatim(self):
        """Le cas nominal : le modele a recopie. / The nominal case."""
        resultat = self.typer(SOURCE, "Le badge est un objet technique simple.")

        self.assertEqual(resultat["categorie"], "verbatim")
        self.assertEqual(resultat["sauts"], 0)
        self.assertEqual(resultat["mots_hors_source"], [])

    def test_deux_passages_eloignes_colles_sans_marque_est_un_saut(self):
        """
        Le modele colle une amorce a un passage qui la suit de loin, sans
        rien signaler. C'est le mode d'echec soupconne chez Mistral.
        / The model glues two distant passages with no marker.
        """
        extraction = (
            "Le badge est un objet technique simple. "
            "Il peut etre mis en oeuvre au niveau d'un etablissement."
        )

        resultat = self.typer(SOURCE, extraction)

        self.assertEqual(resultat["categorie"], "saut")
        self.assertEqual(resultat["sauts"], 1)
        self.assertEqual(resultat["mots_hors_source"], [])

    def test_un_saut_signale_par_des_points_de_suspension_est_une_ellipse(self):
        """
        Meme geometrie que le saut, mais le modele POSE la marque. La
        distinction compte : une ellipse est une desobeissance avouee,
        un saut est une desobeissance invisible.
        / Same geometry, but the model marks it.
        """
        extraction = (
            "Le badge est un objet technique simple... "
            "au niveau d'un etablissement."
        )

        resultat = self.typer(SOURCE, extraction)

        self.assertEqual(resultat["categorie"], "ellipse")

    def test_un_mot_absent_de_la_source_est_une_reformulation(self):
        """Le modele a ecrit un mot que la source ne porte pas."""
        extraction = "Le badge est un objet technique tres simple."

        resultat = self.typer(SOURCE, extraction)

        self.assertEqual(resultat["categorie"], "reformulation")
        self.assertIn("tres", resultat["mots_hors_source"])

    def test_un_texte_etranger_a_la_source_est_hors_source(self):
        """Rien de commun : le modele a invente son passage."""
        extraction = "La photosynthese transforme la lumiere en sucre."

        resultat = self.typer(SOURCE, extraction)

        self.assertEqual(resultat["categorie"], "hors_source")

    def test_les_apostrophes_et_les_espaces_ne_font_pas_un_ecart(self):
        """
        La normalisation suit celle de la verification (NFKC,
        apostrophes droites, espaces ecrases) : sans elle, on compterait
        comme reformulation ce que la chaine de preuve accepte. Elle
        n'est pas identique — la verification traite en plus les
        guillemets courbes.
        / Follows the verification's normalisation, minus curly quotes.
        """
        source = "Il s’agit d’un objet   technique."
        extraction = "Il s'agit d'un objet technique."

        resultat = self.typer(source, extraction)

        self.assertEqual(resultat["categorie"], "verbatim")


class LaRetoucheTypographiqueQuiSuffiraitARetrouverUneCitation(SimpleTestCase):
    """
    Verrouille les TROIS regles d'assouplissement du verbatim.
    / Locks the THREE verbatim-relaxing rules.

    POURQUOI CES TESTS EXISTENT. La chaine de preuve marque INTROUVABLE
    toute citation qui n'est pas litteralement dans sa source. La mesure
    du 19 aout 2026 montre que la majorite de ces INTROUVABLE tiennent a
    une retouche que le modele a faite sur la FORME : un point final
    ajoute, une majuscule d'amorce, un espace parasite de la source
    corrige.

    Assouplir la comparaison est un ARBITRAGE, pas un correctif : ca
    deplace la frontiere de ce que « verbatim » veut dire. Ces tests
    figent la frontiere exacte, et surtout ce qu'elle NE doit PAS
    laisser passer.
    """

    def setUp(self):
        self.reparation = _charger_le_module_de_typage().reparation_qui_suffit

    def test_un_point_final_ajoute_par_le_modele_est_une_retouche(self):
        """Le modele cite un item de liste et le termine par un point."""
        source = "Les usages : l'aide a la redaction, l'evaluation automatisee"
        extrait = "l'aide a la redaction, l'evaluation automatisee."

        self.assertEqual(self.reparation(source, extrait), "point final")

    def test_une_majuscule_d_amorce_est_une_retouche(self):
        """Le modele capitalise le premier mot de ce qu'il cite."""
        source = "on distingue trois categories d'usage de l'IA."
        extrait = "On distingue trois categories"

        self.assertEqual(self.reparation(source, extrait), "majuscule initiale")

    def test_un_espace_parasite_de_la_source_est_une_retouche(self):
        """
        C'est la SOURCE qui est fautive — un artefact d'ingestion — et
        c'est le modele qui la repare. Le refuser reviendrait a punir le
        modele pour la qualite de notre propre extraction de document.
        / The SOURCE is at fault; the model repairs it.
        """
        source = "developpe par IMS Global , un consortium international"
        extrait = "developpe par IMS Global, un consortium international"

        self.assertEqual(
            self.reparation(source, extrait), "espace de ponctuation",
        )

    def test_une_citation_deja_verbatim_ne_demande_aucune_retouche(self):
        """Le cas nominal ne passe par aucune regle. / Nominal case."""
        source = "On distingue trois categories d'usage."
        extrait = "trois categories d'usage"

        self.assertIsNone(self.reparation(source, extrait))

    def test_une_vraie_reformulation_reste_irrecuperable(self):
        """
        Le modele a change un MOT : aucune regle de forme ne doit le
        rattraper, sinon l'assouplissement blanchirait le fond.
        / A changed WORD must never be repaired by a shape rule.
        """
        source = "On distingue trois categories d'usage."
        extrait = "On distingue quatre categories d'usage."

        self.assertEqual(self.reparation(source, extrait), "IRRECUPERABLE")

    def test_une_enumeration_ne_doit_JAMAIS_blanchir_un_nombre_decimal(self):
        """
        LE CONTRE-EXEMPLE QUI JUSTIFIE LA GARDE. Sans elle, ecraser
        l'espace autour d'une virgule transforme l'enumeration « les
        niveaux 3, 5 et 8 » en decimal « les niveaux 3,5 » — un chiffre
        que la source n'avance NULLE PART. La regle ne s'applique donc
        jamais entre deux chiffres.

        Vaut pour les dates, les montants, les versions et les
        references d'article.
        / An enumeration must never launder a decimal the source never
        states: the rule never applies between two digits.
        """
        source = "Les niveaux 3, 5 et 8 sont concernes"
        extrait = "Les niveaux 3,5"

        self.assertEqual(self.reparation(source, extrait), "IRRECUPERABLE")

    def test_un_point_d_interrogation_change_en_point_reste_irrecuperable(self):
        """
        Passer d'une question a une affirmation change ce que la source
        DIT. Aucune regle de forme ne doit l'absorber.
        / Turning a question into a statement changes the meaning.
        """
        source = "Comment evaluer un travail dont on ignore l'auteur ?"
        extrait = "Comment evaluer un travail dont on ignore l'auteur."

        self.assertEqual(self.reparation(source, extrait), "IRRECUPERABLE")


class LesTroisPiegesQueLaRelectureAdverseATrouves(SimpleTestCase):
    """
    Trois cas ou la reparation repondait FAUX. / Three wrong answers.

    Ils ne sont pas theoriques : les deux premiers changent la
    REPARTITION publiee des causes, et le troisieme ouvrirait dans la
    chaine de preuve le trou exact que la garde des chiffres existe pour
    fermer.
    """

    def setUp(self):
        module = _charger_le_module_de_typage()
        self.reparation = module.reparation_qui_suffit

    def test_un_point_deja_dans_la_source_n_est_pas_un_point_AJOUTE(self):
        """
        LA SOURCE PORTE DEJA SON POINT, detache par un espace fautif
        d'ingestion : « d'un territoire . Soutenu depuis 2011 ». Le
        modele n'ajoute rien — il recolle un point qui trainait.

        Repondre « point final » ici deplace 13 cas sur 21 dans la
        mauvaise colonne : ca fait croire que le modele met en phrase ce
        qu'il cite (defaut de PROMPT) alors qu'il repare notre
        typographie (defaut d'INGESTION). Les deux se corrigent a des
        endroits opposes.
        / A period already in the source, detached by a faulty space, is
        not an added period: prompt defect vs ingestion defect.
        """
        source = "au niveau d'un territoire . Soutenu depuis 2011 par la Badge"
        extrait = "au niveau d'un territoire."

        self.assertEqual(
            self.reparation(source, extrait), "espace de ponctuation",
        )

    def test_une_enumeration_entre_parentheses_ne_blanchit_pas_un_decimal(self):
        """
        MEME PIEGE QUE LE DECIMAL, AUTRE DISPOSITION. La parenthese
        ouvrante est collee la premiere ; si l'ecrasement CONSOMME le
        chiffre qui suit, la virgule ne voit plus qu'un voisin et la
        garde tombe. « les niveaux ( 3 , 5 ) » accepterait « 3,5 ».
        / Same laundering, different layout: the bracket must not eat
        the digit that the comma's guard needs to see.
        """
        source = "les niveaux ( 3 , 5 ) sont concernes"

        self.assertEqual(self.reparation(source, "3,5"), "IRRECUPERABLE")

    def test_une_enumeration_de_trois_nombres_ne_blanchit_pas_un_decimal(self):
        """
        Troisieme disposition : deux virgules qui se suivent. La
        premiere ne doit pas consommer le chiffre dont la seconde a
        besoin. « les niveaux 1 , 2 , 3 » accepterait « 2,3 ».
        / Two consecutive commas: the first must not eat the second's
        left-hand digit.
        """
        source = "les niveaux 1 , 2 , 3 sont concernes"

        self.assertEqual(self.reparation(source, "2,3"), "IRRECUPERABLE")

    def test_une_citation_vide_n_est_jamais_reparable(self):
        """
        Une chaine vide est sous-chaine de TOUT : sans garde, un extrait
        vide — ou reduit a un point — se declarerait retrouve.
        / The empty string is a substring of everything.
        """
        self.assertEqual(self.reparation("un texte source", ""),
                         "IRRECUPERABLE")
        self.assertEqual(self.reparation("un texte source", "."),
                         "IRRECUPERABLE")

    def test_une_ellipse_de_la_source_n_est_pas_un_point_ajoute(self):
        """
        NFKC rend « … » (U+2026) en trois points : une garde qui ne
        cherche que le caractere unique ne le verrait JAMAIS. Une source
        qui suspend son propos ne doit pas voir ce suspens remplace par
        un point ferme.
        / NFKC turns U+2026 into three dots; a guard on the single
        character would never fire.
        """
        source = "il viendra … mais on ignore quand"
        extrait = "il viendra."

        self.assertEqual(self.reparation(source, extrait), "IRRECUPERABLE")


class LeComptageDesRetouchesCaractereParCaractere(SimpleTestCase):
    """
    Verrouille le compteur qui alimente le tableau des retouches.
    / Locks the counter behind the touch-up table.

    IL EST DESCRIPTIF, PAS EXPLICATIF. Il dit ce que l'extrait porte que
    la fenetre source ne porte pas — jamais QUI l'a mis la. Un point que
    la source portait deja, detache par un espace d'ingestion, s'y lit
    comme un ajout : c'est `reparation_qui_suffit` qui tranche, pas lui.
    """

    def setUp(self):
        self.compter = _charger_le_module_de_typage().compter_les_retouches

    def test_un_point_final_ajoute_se_lit_comme_une_insertion(self):
        """Le cas nominal du compteur. / The counter's nominal case."""
        source = "l'aide a la redaction et l'evaluation automatisee"
        extrait = "l'aide a la redaction."

        self.assertIn(("insert", "", "."), self.compter(source, extrait))

    def test_un_espace_de_la_source_absent_de_l_extrait_se_lit(self):
        """L'espace fautif de la source, vu du cote de l'extrait."""
        source = "developpe par IMS Global , un consortium"
        extrait = "developpe par IMS Global, un consortium"

        self.assertIn(("delete", " ", ""), self.compter(source, extrait))

    def test_une_citation_verbatim_ne_porte_aucune_retouche(self):
        """
        Sans mot en trop ni caractere en trop, la liste est vide.
        / Nothing touched, nothing counted.
        """
        source = "On distingue trois categories d'usage de l'IA"
        extrait = "trois categories d'usage"

        self.assertEqual(self.compter(source, extrait), [])

    def test_une_citation_etrangere_a_la_source_ne_fait_pas_lever(self):
        """
        Aucun bloc commun : le compteur rend une liste vide au lieu de
        lever sur une fenetre introuvable.
        / No common block: empty list, not a crash.
        """
        self.assertEqual(
            self.compter("un texte source", "photosynthese chlorophylle"), [],
        )
