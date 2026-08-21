"""
La consigne de sourcage exige un marqueur sur TOUTE affirmation.
/ The sourcing instruction requires a marker on EVERY claim.

LOCALISATION : front/tests/test_consigne_de_sourcage.py

CE QUE CE TEST PROTEGE. La consigne disait « chaque affirmation TIREE
D'UNE HYPOSTASE se termine par le marqueur de sa source ». Elle
conditionnait le marqueur au fait que la phrase soit tiree d'une
extraction — et une phrase de synthese generale n'est, du point de vue
du modele, tiree d'aucune extraction EN PARTICULIER. Elle echappait
donc a la regle sans la violer.

Mesure du 19 aout 2026 : `mistral-large` ecrivait UNE PHRASE SUR DEUX
sans aucun marqueur, et ce n'etaient pas des transitions mais des
affirmations factuelles. Une phrase sans marqueur ne porte aucune
source : le juge ne la voit pas, et rien ne la verifie.
"""

from django.test import SimpleTestCase

from front.tasks import CONSIGNE_DE_SOURCAGE


class LaConsigneDeSourcageNeLaissePasDePorteOuverte(SimpleTestCase):
    """La formulation, mot pour mot. / The wording, word for word."""

    def test_la_consigne_ne_conditionne_PLUS_le_marqueur_a_l_origine(self):
        """
        LA PORTE A FERMER. « tirée d'une hypostase » laissait au modele
        le soin de decider quelles phrases etaient concernees.
        / The old wording let the model decide which claims were covered.
        """
        self.assertNotIn("tirée d'une hypostase", CONSIGNE_DE_SOURCAGE)

    def test_la_consigne_exige_un_marqueur_sur_TOUTE_affirmation(self):
        """Elle doit le dire sans laisser de marge d'interpretation."""
        self.assertIn("TOUTE AFFIRMATION", CONSIGNE_DE_SOURCAGE.upper())

    def test_la_consigne_interdit_l_affirmation_non_sourcable(self):
        """
        Le corollaire, sans lequel le modele garderait ses affirmations
        en se contentant de ne pas les sourcer : une phrase qui ne peut
        pas porter de marqueur n'a pas sa place dans l'article.
        / Without this, the model could simply keep them unsourced.
        """
        self.assertIn("supprime", CONSIGNE_DE_SOURCAGE.lower())

    def test_la_consigne_laisse_vivre_les_titres_et_les_liaisons(self):
        """
        LA CONTREPARTIE, ET ELLE EST NECESSAIRE. Exiger un marqueur
        partout, titres compris, produirait des titres balises et des
        articles illisibles. Un texte a besoin de charpente.
        / Requiring markers everywhere would produce tagged headings.
        """
        consigne = CONSIGNE_DE_SOURCAGE.lower()
        self.assertIn("titre", consigne)
        self.assertIn("liaison", consigne)

    def test_le_format_du_marqueur_reste_enseigne(self):
        """
        Le contrat de format ne doit pas disparaitre dans la reecriture :
        marqueurs CONSECUTIFS, jamais groupes.
        / The format contract must survive the rewrite.
        """
        self.assertIn("[[ext:12]][[ext:15]]", CONSIGNE_DE_SOURCAGE)
        self.assertIn("consécutifs", CONSIGNE_DE_SOURCAGE)
