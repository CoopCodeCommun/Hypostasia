"""
Test : aucun geste de l'arbre lateral n'a perdu son point d'entree.
/ Test: no gesture from the removed side tree lost its entry point.

LOCALISATION : front/tests/test_aucun_geste_orphelin.py

POURQUOI CE TEST EXISTE

L'arbre lateral a ete retire le 12 aout. Il ne servait pas qu'a
naviguer : son menu contextuel et son pied portaient des gestes dont il
etait, pour certains, le SEUL point d'entree.

Deux fois dans la meme journee, un retrait « propre » aurait supprime
une fonction entiere sans que personne ne le voie : le dashboard portait
le seul acces a la synthese, et le bouton « Analyses » le seul moyen de
rouvrir le panneau. Les deux ont ete rattrapes de justesse, en lisant le
gabarit juste avant de le supprimer.

Ce test transforme cette vigilance en garde-fou : il liste les gestes
que l'arbre portait et verifie que chacun a un point d'entree quelque
part. Il echouera si un futur nettoyage en fait disparaitre un.

CE QU'IL NE FAIT PAS

Il ne verifie pas que le geste FONCTIONNE — les suites e2e s'en
chargent. Il verifie qu'il est ATTEIGNABLE. Un geste qui marche mais
qu'aucun ecran ne propose n'existe pas pour l'utilisateur.
/ It checks reachability, not behaviour: a gesture no screen offers does
not exist for the user.
"""

import pathlib

from django.conf import settings
from django.test import SimpleTestCase

GABARITS = pathlib.Path(settings.BASE_DIR) / "front" / "templates" / "front"

# Chaque geste que l'arbre portait, et le marqueur qui prouve qu'un
# ecran le propose encore. / Each gesture the tree hosted, and the marker
# proving a screen still offers it.
GESTES_ET_LEUR_POINT_D_ENTREE = {
    "Créer un carnet": "corpus-carnet-creer-bouton",
    "Renommer un carnet": "corpus-carnet-renommer",
    "Changer la visibilité d'un carnet": "corpus-carnet-visibilite-choix-",
    "Partager un carnet": "corpus-carnet-partager",
    "Supprimer un carnet": "corpus-carnet-supprimer",
    "Supprimer définitivement une note": "corpus-note-supprimer",
    # Le menu contextuel avait un « Deplacer ». Avec le N-N, une note n'a
    # pas de parent unique : deplacer n'a plus de sens, le couple
    # ajouter/retirer le remplace.
    # / The N-N killed "move": a note has no single parent.
    "Ranger une note dans un carnet": "corpus-bloc-ajouter-bouton",
    "Retirer une note d'un carnet": "corpus-bloc-retirer",
    # LE GESTE A DEMENAGE, ET C'EST TOUT L'INTERET DE CE TEST. Il
    # vivait dans la barre d'outils (« btn-toolbar-import »), global :
    # on cliquait sans savoir dans quel carnet le fichier atterrissait,
    # et il tombait dans un fourre-tout invisible. Il vit desormais sur
    # la ligne du titre de chaque carnet, ou la destination est la chose
    # qu'on regarde. Le marqueur change ; le geste, lui, existe toujours
    # — c'est exactement ce que ce test verifie.
    # / The gesture moved from the global toolbar to each notebook's
    # title line; the marker changes, the gesture remains.
    "Importer un fichier": "corpus-carnet-importer",
}


class AucunGesteOrphelinTest(SimpleTestCase):
    """
    LOCALISATION : front/tests/test_aucun_geste_orphelin.py
    """

    def test_chaque_geste_de_l_arbre_a_garde_un_point_d_entree(self):
        """
        Un geste sans point d'entree n'existe pas pour l'utilisateur.
        / A gesture with no entry point does not exist for the user.
        """
        contenu_de_tous_les_gabarits = "\n".join(
            gabarit.read_text(encoding="utf-8")
            for gabarit in GABARITS.rglob("*.html")
        )

        gestes_orphelins = [
            f"{nom_du_geste} (marqueur « {marqueur} »)"
            for nom_du_geste, marqueur in GESTES_ET_LEUR_POINT_D_ENTREE.items()
            if marqueur not in contenu_de_tous_les_gabarits
        ]

        self.assertEqual(
            gestes_orphelins,
            [],
            "Ces gestes n'ont plus de point d'entrée dans l'interface :\n  "
            + "\n  ".join(gestes_orphelins)
            + "\n\nIls étaient portés par l'arbre latéral, retiré le "
            "12 août. Un geste qui fonctionne mais qu'aucun écran ne "
            "propose n'existe pas pour l'utilisateur.",
        )

    def test_l_arbre_lateral_a_bien_disparu(self):
        """
        Le pendant du test precedent : on verifie que le retrait est
        complet, pour qu'aucun gabarit ne cible un arbre absent.
        / The counterpart: no template may still target a gone tree.
        """
        contenu_de_tous_les_gabarits = "\n".join(
            gabarit.read_text(encoding="utf-8")
            for gabarit in GABARITS.rglob("*.html")
        )

        for reste in ("arbre-overlay", "btn-hamburger-arbre", "arbre-ctx-menu"):
            self.assertNotIn(
                f'id="{reste}"',
                contenu_de_tous_les_gabarits,
                f"« {reste} » subsiste dans un gabarit alors que l'arbre "
                f"latéral a été retiré.",
            )
