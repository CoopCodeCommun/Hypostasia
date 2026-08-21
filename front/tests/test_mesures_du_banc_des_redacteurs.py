"""
Les mesures que le banc des redacteurs avait oubliees.
/ The measures the writers' bench had left out.

LOCALISATION : front/tests/test_mesures_du_banc_des_redacteurs.py

POURQUOI CES TESTS EXISTENT. La campagne du 19 aout 2026 a publie un
classement de redacteurs qui reposait sur un job ECHOUE que personne
n'avait vu : la boucle attendait que « pending/processing » tombe a
zero, et un job en `error` satisfait cette condition. Un article est
donc reste celui d'une passe anterieure, ecrit sur un autre perimetre.

Elle a aussi annonce une « part de prose sans marqueur » sans en donner
la definition — et aucune definition essayee depuis ne reproduit ses
chiffres. Une mesure sans definition n'est pas une mesure.

Les deux fonctions verrouillees ici repondent a ces deux manques.
"""

import importlib.util
from pathlib import Path

from django.test import SimpleTestCase

CHEMIN_DU_MODULE = (
    Path(__file__).resolve().parents[2]
    / "benchmarks" / "redaction" / "mesurer_les_redacteurs.py"
)


def _charger_le_module_du_banc():
    """Charge le banc par son chemin. / Loads the bench by path."""
    specification = importlib.util.spec_from_file_location(
        "mesurer_les_redacteurs", CHEMIN_DU_MODULE,
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


part_de_prose_sans_marqueur = (
    _charger_le_module_du_banc().part_de_prose_sans_marqueur
)


class LaPartDeProseQuiNeCiteRien(SimpleTestCase):
    """
    LA DEFINITION EST PUBLIEE AVEC LE CHIFFRE, sinon le chiffre ne veut
    rien dire. Une phrase « sans marqueur » est une phrase qui ne porte
    aucun `[[ext:N]]`. On compte par PHRASE et par PARAGRAPHE : les deux
    repondent a des questions differentes, et un article peut etre bon
    sur l'une et mauvais sur l'autre.
    / The definition ships with the number.
    """

    def test_un_texte_entierement_source_ne_porte_aucune_prose_nue(self):
        """Chaque phrase cite : rien n'est sans marqueur."""
        texte = "Le badge est un objet [[ext:1]]. Il se partage [[ext:2]]."

        mesure = part_de_prose_sans_marqueur(texte)

        self.assertEqual(mesure["phrases_sans_marqueur"], 0)
        self.assertEqual(mesure["part_des_phrases"], 0.0)

    def test_une_phrase_sur_deux_sans_marqueur_donne_la_moitie(self):
        """Le cas arithmetique le plus simple, pour fixer l'unite."""
        texte = "Le badge est un objet [[ext:1]]. Il change tout."

        mesure = part_de_prose_sans_marqueur(texte)

        self.assertEqual(mesure["phrases_sans_marqueur"], 1)
        self.assertEqual(mesure["phrases"], 2)
        self.assertEqual(mesure["part_des_phrases"], 0.5)

    def test_un_paragraphe_compte_meme_si_une_seule_phrase_cite(self):
        """
        Un paragraphe qui porte UN marqueur n'est pas « sans marqueur »,
        meme si ses autres phrases n'en portent pas : c'est ce qui rend
        les deux unites complementaires.
        / A paragraph with one marker is not unsourced.
        """
        texte = (
            "Le badge est un objet [[ext:1]]. Il change tout.\n\n"
            "Un paragraphe entier qui ne cite personne."
        )

        mesure = part_de_prose_sans_marqueur(texte)

        self.assertEqual(mesure["paragraphes"], 2)
        self.assertEqual(mesure["paragraphes_sans_marqueur"], 1)

    def test_un_titre_de_section_n_est_PAS_de_la_prose(self):
        """
        UN TITRE NE CITE JAMAIS, et c'est normal. Le compter gonflerait
        mecaniquement la prose nue de tout article bien structure — et
        punirait le modele qui decoupe le mieux.
        / A heading never cites; counting it would punish good structure.
        """
        texte = "## Les open badges\n\nLe badge est un objet [[ext:1]]."

        mesure = part_de_prose_sans_marqueur(texte)

        self.assertEqual(mesure["paragraphes"], 1)
        self.assertEqual(mesure["paragraphes_sans_marqueur"], 0)

    def test_le_marqueur_se_place_APRES_le_point_et_la_decoupe_le_sait(self):
        """
        LE PIEGE DE LA DECOUPE, ET IL FAUSSE TOUT. Les redacteurs
        ecrivent « … informels.[[ext:13]] Un Open Badge est… » : le
        marqueur vient APRES le point, colle a lui. Une decoupe qui
        cherche une ponctuation suivie d'une ESPACE ne coupe donc nulle
        part, et rend un article entier comme UNE phrase — qui porte un
        marqueur, donc « 0 % de prose nue ».

        Mesure : sur le wiki de Medium, la version fautive comptait
        10 phrases la ou il y en a une trentaine, et annoncait 0 %.
        / The marker sits AFTER the period; the split must know.
        """
        texte = (
            "Les badges datent de 2011.[[ext:13]] "
            "Un badge est une image.[[ext:14]][[ext:15]] "
            "Cette affirmation ne cite personne."
        )

        mesure = part_de_prose_sans_marqueur(texte)

        self.assertEqual(mesure["phrases"], 3)
        self.assertEqual(mesure["phrases_sans_marqueur"], 1)

    def test_un_texte_vide_ne_fait_pas_lever(self):
        """Un article vide se mesure a zero, il ne plante pas."""
        mesure = part_de_prose_sans_marqueur("")

        self.assertEqual(mesure["phrases"], 0)
        self.assertEqual(mesure["part_des_phrases"], 0.0)
