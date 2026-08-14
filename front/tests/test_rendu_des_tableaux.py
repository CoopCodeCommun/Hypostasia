"""
Tests de la conversion d'un tableau markdown en `<table>`.
/ Tests for converting a markdown table into a real <table>.

LOCALISATION : front/tests/test_rendu_des_tableaux.py

CE QUE CES TESTS EPROUVENT

Dernier morceau de l'ecart n°6 de l'etalon. Docling rend un tableau en
markdown « pipe » ; le service le servait dans un `<pre>`. Un `<pre>` n'a
ni ligne ni colonne : illisible au lecteur d'ecran, il ne se replie pas,
et celui du PDF etalon mesurait 3 162px.

LA DIFFICULTE, ET POURQUOI CE N'EST PAS UN SIMPLE CHANGEMENT DE BALISE

Le texte arrive DEJA balise : les marques d'ancrage (`<mark>`) y sont
posees aux positions des idees. Decouper ce HTML en cellules coupe donc
potentiellement une marque en plein milieu — et une balise ouverte dans
une cellule, fermee dans la suivante, produit du HTML invalide.

La regle appliquee est celle que le moteur suit deja quand une ancre
enjambe deux elements : on FERME les marques ouvertes a la frontiere, et
on les ROUVRE de l'autre cote. Une idee qui traverse deux cellules
produit donc deux `<mark>`, comme elle produit deux `<mark>` quand elle
traverse deux paragraphes. Le modele reste coherent.
/ The text arrives already marked up; splitting it into cells can cut a
<mark> in half. We close open marks at each boundary and reopen them
after — the same rule the engine already applies across elements.
"""

from django.test import SimpleTestCase

from front.services.rendu_elements import convertir_un_tableau_markdown


class RenduDesTableauxTest(SimpleTestCase):
    """
    LOCALISATION : front/tests/test_rendu_des_tableaux.py
    """

    def test_un_tableau_simple_devient_une_table(self):
        """La forme de base : en-tete, separateur, corps."""
        markdown = (
            "| Poste | 2023 | 2024 |\n"
            "|-------|------|------|\n"
            "| Loyer | 100 | 120 |"
        )

        html = convertir_un_tableau_markdown(markdown)

        self.assertIn("<table", html)
        self.assertIn("<thead>", html)
        self.assertIn("<th>Poste</th>", html)
        self.assertIn("<tbody>", html)
        self.assertIn("<td>Loyer</td>", html)
        # La ligne de tirets est une CONVENTION d'ecriture, pas une
        # donnee : elle ne doit pas devenir une ligne du tableau.
        # / The dashes row is syntax, not data.
        self.assertNotIn("---", html)

    def test_le_nombre_de_colonnes_est_respecte(self):
        """Trois colonnes en entree, trois cellules par ligne."""
        markdown = (
            "| a | b | c |\n"
            "|---|---|---|\n"
            "| 1 | 2 | 3 |"
        )

        html = convertir_un_tableau_markdown(markdown)

        self.assertEqual(html.count("<th>"), 3)
        self.assertEqual(html.count("<td>"), 3)

    def test_une_marque_entierement_dans_une_cellule_est_intacte(self):
        """Le cas courant : l'idee tient dans une cellule."""
        markdown = (
            '| Poste | Montant |\n'
            '|-------|---------|\n'
            '| <mark class="hl">Loyer</mark> | 120 |'
        )

        html = convertir_un_tableau_markdown(markdown)

        self.assertIn('<td><mark class="hl">Loyer</mark></td>', html)

    def test_une_marque_qui_traverse_deux_cellules_est_refermee(self):
        """
        Le cas qui produit du HTML invalide si on n'y prend pas garde :
        une balise ouverte dans une cellule et fermee dans la suivante.
        On ferme a la frontiere et on rouvre apres.
        / The case that yields invalid HTML if left alone.
        """
        markdown = (
            "| a | b |\n"
            "|---|---|\n"
            '| <mark class="hl">debut | fin</mark> |'
        )

        html = convertir_un_tableau_markdown(markdown)

        # Deux marques, une par cellule, chacune bien fermee : c'est le
        # seul point qui compte. Un HTML ou une balise s'ouvre dans une
        # cellule et se ferme dans la suivante est invalide, et chaque
        # navigateur le repare a sa facon.
        # / Two marks, one per cell, each properly closed.
        self.assertEqual(html.count("<mark"), 2)
        self.assertEqual(html.count("</mark>"), 2)
        self.assertEqual(html.count("<td>"), 2)

        # Les espaces qui bordent le contenu d'une cellule appartiennent
        # au TEXTE du document : `| <mark>debut | fin</mark> |` porte bien
        # un espace apres « debut ». Les retirer DANS la marque
        # reviendrait a demander au rendu de reecrire le contenu qu'il
        # affiche — et les positions d'ancrage sont comptees sur ce
        # contenu.
        # / Padding spaces belong to the document's text; stripping them
        # inside the mark would rewrite content the offsets are counted on.
        self.assertIn("<td><mark", html)
        self.assertIn("debut", html)
        self.assertIn("fin", html)
        self.assertNotIn("|", html)

    def test_un_texte_qui_n_est_pas_un_tableau_est_rendu_tel_quel(self):
        """
        Un label `table` sur un contenu qui n'en est pas un ne doit pas
        produire une table vide : mieux vaut le texte que rien.
        / A `table` label on non-table content must not yield an empty
        table: the text is better than nothing.
        """
        html = convertir_un_tableau_markdown("Juste une phrase.")

        self.assertNotIn("<table", html)
        self.assertIn("Juste une phrase.", html)

    def test_les_cellules_vides_sont_conservees(self):
        """
        Une cellule vide porte une information — « rien ici » — et sa
        disparition decalerait toute la ligne.
        / An empty cell carries meaning; dropping it shifts the row.
        """
        markdown = (
            "| a | b | c |\n"
            "|---|---|---|\n"
            "| 1 |  | 3 |"
        )

        html = convertir_un_tableau_markdown(markdown)

        self.assertEqual(html.count("<td>"), 3)
