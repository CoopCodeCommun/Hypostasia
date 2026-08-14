"""
Tests des formes rendues pour chaque label Docling.
/ Tests for the shape rendered per Docling label.

LOCALISATION : front/tests/test_formes_par_label.py

CE QUE CES TESTS EPROUVENT

C'est l'ecart n°6 de l'etalon, ouvert depuis le 11 aout : le service
rendait les tableaux en `<pre>`, et `blockquote`, `formula`, `picture`
et `utterance` tombaient tous dans le `<p>` par defaut, faute de figurer
dans `BALISE_PAR_LABEL`.

CE QU'UNE BALISE FAUSSE COUTE

Un tableau en `<pre>` n'est pas seulement laid : il n'a ni lignes ni
colonnes pour un lecteur d'ecran, il ne se replie pas, et le PDF etalon
en produisait un de 3 162px qui faisait defiler toute la page. Une
citation en `<p>` ne se distingue pas du texte qui la commente. Une
formule en `<p>` se coupe au milieu.

CE QUE CES TESTS NE TRANCHENT PAS

Le DECOUPAGE d'un tableau reste entier : un tableau est toujours UN
`ElementDocument` — 4 471 signes pour le premier du PDF etalon — et une
idee ancree dessus designe donc tout le tableau. Rendre un `<table>` ne
change pas cela ; c'est une decision de modele, laissee au mainteneur.
/ These tests fix the SHAPE, not the anchoring granularity: a table is
still one element, and an idea anchored on it still points at the whole.
"""

from django.test import SimpleTestCase

from front.services.rendu_elements import BALISE_PAR_DEFAUT, BALISE_PAR_LABEL

# Ce que l'etalon dessine pour chaque label (maquette.html § 8,
# « FORMES PAR LABEL »). / What the mockup draws per label.
FORME_ATTENDUE_PAR_LABEL = {
    "title": "h2",
    "section_header": "h3",
    "list_item": "li",
    # `<pre>` ne porte ni ligne ni colonne : illisible au lecteur
    # d'ecran, et il ne se replie pas.
    # / <pre> carries neither rows nor columns.
    "table": "table",
    "code": "pre",
    # Une citation qui a la forme du texte qui la commente n'est plus une
    # citation. / A quote shaped like the prose around it is not a quote.
    "blockquote": "blockquote",
    # Centree entre deux filets dans l'etalon, et jamais coupee.
    # / Centred between two rules, never broken mid-line.
    "formula": "figure",
    "picture": "figure",
    # Un tour de parole n'est pas un paragraphe : il porte un locuteur.
    # / A speech turn is not a paragraph: it carries a speaker.
    "utterance": "p",
}


class FormesParLabelTest(SimpleTestCase):
    """
    LOCALISATION : front/tests/test_formes_par_label.py
    """

    def test_chaque_label_de_l_etalon_a_sa_forme(self):
        """
        Un label absent de la table retombe silencieusement sur `<p>` :
        rien ne signale que la forme est fausse.
        / A missing label silently falls back to <p>.
        """
        formes_manquantes = {}
        for label, forme_attendue in FORME_ATTENDUE_PAR_LABEL.items():
            forme_rendue = BALISE_PAR_LABEL.get(label, BALISE_PAR_DEFAUT)
            if forme_rendue != forme_attendue:
                formes_manquantes[label] = (forme_rendue, forme_attendue)

        self.assertEqual(
            formes_manquantes,
            {},
            "Ces labels ne prennent pas la forme de l'étalon "
            "(rendu → attendu) :\n  "
            + "\n  ".join(
                f"{label} : <{rendu}> → <{attendu}>"
                for label, (rendu, attendu) in formes_manquantes.items()
            ),
        )

    def test_un_label_inconnu_retombe_sur_un_paragraphe(self):
        """
        Le repli doit rester : Docling peut produire un label qu'on n'a
        jamais vu, et le rendu ne doit pas planter dessus.
        / Docling may emit an unseen label; rendering must not break.
        """
        self.assertEqual(
            BALISE_PAR_LABEL.get("un_label_inedit", BALISE_PAR_DEFAUT),
            "p",
        )
