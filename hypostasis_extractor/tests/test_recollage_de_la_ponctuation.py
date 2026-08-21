"""
L'ingestion recolle la ponctuation que Docling detache.
/ Ingestion re-attaches the punctuation Docling detaches.

LOCALISATION : hypostasis_extractor/tests/test_recollage_de_la_ponctuation.py

POURQUOI CE NETTOYAGE EXISTE. Docling rend regulierement un point ou
une virgule separes du mot qui les precede : « d'un territoire . »,
« par IMS Global , un consortium ». Le fichier source ne les porte pas
— verifie sur le markdown d'origine, qui est propre.

CE QUE CA CASSE. Un modele qui cite ce passage recolle spontanement la
ponctuation, comme le ferait un humain. Sa citation ne se retrouve alors
plus dans la source, le controle verbatim echoue, et la chaine de preuve
est declaree cassee — pour un espace que nous avons introduit nous-memes.
Mesure du 19 aout 2026 : c'est la cause dominante des citations
INTROUVABLE.

LA LIMITE QUI COMPTE, ET ELLE EST TYPOGRAPHIQUE. En francais, l'espace
AVANT « ? », « ! », « ; » et « : » est CORRECTE. La recoller serait une
faute, pas une reparation. Le nettoyage ne touche donc QUE le point et
la virgule.
"""

from django.test import SimpleTestCase

from hypostasis_extractor.services.ingestion_docling import (
    recoller_la_ponctuation_detachee,
)


class LeRecollageRepareCeQueDoclingDetache(SimpleTestCase):
    """Le point et la virgule, et rien d'autre. / Period and comma only."""

    def test_un_point_detache_est_recolle(self):
        """Le cas le plus frequent, mesure sur le corpus."""
        self.assertEqual(
            recoller_la_ponctuation_detachee(
                "mis en oeuvre au niveau d'un territoire . Soutenu depuis 2011",
            ),
            "mis en oeuvre au niveau d'un territoire. Soutenu depuis 2011",
        )

    def test_une_virgule_detachee_est_recollee(self):
        """Deuxieme cas le plus frequent."""
        self.assertEqual(
            recoller_la_ponctuation_detachee(
                "developpe par IMS Global , un consortium",
            ),
            "developpe par IMS Global, un consortium",
        )

    def test_plusieurs_detachements_dans_un_meme_texte(self):
        """Un element en porte souvent plusieurs."""
        self.assertEqual(
            recoller_la_ponctuation_detachee("un mot , un autre . Et la suite"),
            "un mot, un autre. Et la suite",
        )


class LeRecollageNeTouchePasALaTypographieFrancaise(SimpleTestCase):
    """
    LA PARTIE QUI PROTEGE. Recoller ces signes serait une FAUTE.
    / Re-attaching these marks would be an error.
    """

    def test_l_espace_avant_un_deux_points_est_conservee(self):
        """« suivantes : » est correct en francais."""
        texte = "les informations suivantes : recepteur, emetteur"

        self.assertEqual(recoller_la_ponctuation_detachee(texte), texte)

    def test_l_espace_avant_un_point_d_interrogation_est_conservee(self):
        """« ouverts ? » est correct en francais."""
        texte = "que sont les badges numeriques ouverts ?"

        self.assertEqual(recoller_la_ponctuation_detachee(texte), texte)

    def test_l_espace_avant_un_point_virgule_est_conservee(self):
        """« ouverts ; » est correct en francais."""
        texte = "identifier les apprentissages informels ;"

        self.assertEqual(recoller_la_ponctuation_detachee(texte), texte)

    def test_l_espace_avant_un_point_d_exclamation_est_conservee(self):
        """« enfin ! » est correct en francais."""
        texte = "et le voila enfin !"

        self.assertEqual(recoller_la_ponctuation_detachee(texte), texte)

    def test_un_decimal_n_est_JAMAIS_forge_entre_deux_chiffres(self):
        """
        LA GARDE DES CHIFFRES. « la valeur 3 ,5 » recolle donnerait
        « 3,5 » — un decimal que le document n'avance nulle part. Le
        nettoyage ne s'applique donc jamais entre deux chiffres.
        Vaut pour les dates, les montants, les versions.
        / Never between two digits: it would forge a decimal.
        """
        texte = "la valeur 3 ,5 est mesuree"

        self.assertEqual(recoller_la_ponctuation_detachee(texte), texte)

    def test_une_enumeration_de_nombres_est_recollee_SANS_danger(self):
        """
        LE CAS VOISIN, ET IL EST SUR. « les niveaux 3 , 5 et 8 » devient
        « les niveaux 3, 5 et 8 » : le nettoyage retire l'espace AVANT
        la virgule, jamais celui d'APRES. L'enumeration reste une
        enumeration, et aucun decimal n'apparait.

        C'est la difference avec la comparaison du verbatim
        (`core/services/verification.py`), qui ecrase les espaces des
        DEUX cotes et doit donc, elle, refuser ce cas.
        / Only the space BEFORE is removed: the enumeration survives.
        """
        self.assertEqual(
            recoller_la_ponctuation_detachee(
                "les niveaux 3 , 5 et 8 sont concernes",
            ),
            "les niveaux 3, 5 et 8 sont concernes",
        )

    def test_l_espace_apres_un_guillemet_OUVRANT_est_conservee(self):
        """
        MESURE SUR LE CORPUS : c'est le recollage fautif le plus
        frequent. Dans un tableau, « | « ...avec des chutes » deviendrait
        « | «...avec des chutes » — or l'espace apres un guillemet
        OUVRANT est correcte, et le point d'elision n'a rien a y coller.
        / The space after an OPENING quote is correct typography.
        """
        texte = "| Les explications CoT. | « ...avec des chutes de precision"

        self.assertEqual(recoller_la_ponctuation_detachee(texte), texte)

    def test_un_separateur_de_cellule_n_est_pas_recolle(self):
        """
        « | . | » deviendrait « |. | » : la structure de la cellule
        markdown serait cassee, et le tableau avec.
        / Gluing here would break the markdown cell structure.
        """
        texte = "| a | . | b |"

        self.assertEqual(recoller_la_ponctuation_detachee(texte), texte)

    def test_un_texte_deja_propre_n_est_pas_modifie(self):
        """Le nettoyage est sans effet sur ce qui va bien."""
        texte = "Une phrase normale, avec sa virgule et son point."

        self.assertEqual(recoller_la_ponctuation_detachee(texte), texte)

    def test_un_saut_de_ligne_avant_un_point_n_est_pas_recolle(self):
        """
        Une ponctuation en tete de ligne appartient a la mise en forme du
        document — une puce, une numerotation — pas a la phrase
        precedente. La recoller souderait deux blocs distincts.
        / A mark starting a line belongs to layout, not to the sentence.
        """
        # Un VRAI saut de ligne, et une espace avant le point : sans
        # les deux, ce test passerait avec n'importe quelle
        # implementation. / A real newline AND a space before the mark.
        texte = "premiere ligne \n. deuxieme ligne"

        self.assertEqual(recoller_la_ponctuation_detachee(texte), texte)
