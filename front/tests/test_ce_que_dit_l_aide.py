"""
Ce que l'aide affirme doit etre vrai — verifie contre le code, pas relu.
/ What the help screens claim must be true — checked against the code.

LOCALISATION : front/tests/test_ce_que_dit_l_aide.py

POURQUOI CE FICHIER EXISTE

Le 21 aout 2026, un audit ligne a ligne de l'ecran « Aide » a trouve
SEPT affirmations fausses. Aucune n'avait jamais leve d'erreur — une
aide ne plante pas, elle ment.

  - « pastille en marge » et « cliquez sur une pastille » : les pastilles
    de marge sont mortes avec l'ancien moteur d'ancrage, le 10 aout 2026,
    et un test anti-retour verrouille deja leur disparition du CSS. Le
    geste reel est un clic sur le SURLIGNAGE INLINE.
  - « L'IA extrait les passages cles » : l'extraction a la main existe,
    par le crayon du menu de selection.
  - « Lancez la synthese » : elle se lance depuis le CARNET, en deux
    genres, jamais depuis une note.
  - raccourci `T` : `keyboard.js` porte a sa place un commentaire qui
    explique pourquoi il n'est PAS lie.
  - raccourci `S` : jamais lie, et « consensuelle » ne designe plus rien
    depuis la fusion des six statuts en deux, le 2 mai 2026. Il etait
    dans les DEUX listes d'aide du produit.
  - « Appuyez sur ? pour revoir cette aide » : `?` ouvre la modale des
    raccourcis, pas cet ecran.

CE QUE CES TESTS FONT, ET QU'UNE RELECTURE NE FAIT PAS

Ils comparent les listes de raccourcis aux touches REELLEMENT liees dans
`keyboard.js`. Un raccourci retire du JS fait desormais tomber la suite,
au lieu de survivre des mois dans une aide que personne ne rouvre.

IL Y A DEUX LISTES, ET C'EST VOULU : l'ecran « Aide » du menu et la
modale « ? ». Elles s'adressent a deux moments differents. Mais deux
listes derivent — c'est exactement ce qui est arrive a `S`, present dans
les deux. Les deux sont donc verrouillees ici, par la meme regle.
/ These tests compare the help lists to the keys keyboard.js actually
binds. There are two lists on purpose; both are locked by one rule.
"""

import pathlib
import re

from django.test import SimpleTestCase, TestCase

RACINE = pathlib.Path(__file__).resolve().parent.parent

ECRAN_AIDE = RACINE / "templates" / "front" / "includes" / "onboarding_vide.html"
CLAVIER_JS = RACINE / "static" / "front" / "js" / "keyboard.js"
VUES = RACINE / "views.py"

# Les touches que `keyboard.js` traite hors du `switch`, parce qu'elles
# doivent agir meme dans un champ de saisie. / Handled outside the switch.
TOUCHES_HORS_SWITCH = {"ESC"}


def touches_liees_dans_le_javascript():
    """
    Les touches que `keyboard.js` lie vraiment, en majuscules.
    / The keys keyboard.js actually binds, uppercased.

    LOCALISATION : front/tests/test_ce_que_dit_l_aide.py

    On lit les `case '<touche>':` du `switch` du gestionnaire clavier.
    C'est la SEULE source : une liste recopiee ici serait une troisieme
    copie a tenir d'accord, c'est-a-dire le defaut meme que ce fichier
    existe pour attraper.
    / Read from the switch itself: a copy here would be a third list to
    keep in sync — the very defect these tests catch.
    """
    source = CLAVIER_JS.read_text(encoding="utf-8")
    trouvees = re.findall(r"case '(.+?)':", source)
    return {touche.upper() for touche in trouvees} | TOUCHES_HORS_SWITCH


def touches_annoncees_par_l_ecran():
    """
    Les touches listees dans l'ecran « Aide » du menu.
    / The keys listed on the menu's Help screen.
    """
    source = ECRAN_AIDE.read_text(encoding="utf-8")
    dans_les_raccourcis = source[source.index('class="onboarding-raccourcis"'):]
    trouvees = re.findall(
        r'<kbd class="aide-kbd">(.+?)</kbd>', dans_les_raccourcis
    )
    return {touche.strip().upper() for touche in trouvees}


def touches_annoncees_par_la_modale():
    """
    Les touches listees par `LectureViewSet.aide`, que la modale « ? »
    rend. / The keys LectureViewSet.aide passes to the "?" modal.
    """
    source = VUES.read_text(encoding="utf-8")
    debut = source.index("liste_raccourcis = [")
    fin = source.index("]", debut)
    trouvees = re.findall(r'\(\s*"(.+?)"\s*,', source[debut:fin])
    return {touche.strip().upper() for touche in trouvees}


class LesRaccourcisAnnoncesSontLiesTest(SimpleTestCase):
    """
    LOCALISATION : front/tests/test_ce_que_dit_l_aide.py
    """

    def test_l_ecran_aide_n_annonce_que_des_touches_liees(self):
        """
        Une aide qui annonce un raccourci mort est pire qu'une aide
        incomplete : elle fait douter de tout le reste.
        / A help screen listing a dead shortcut discredits the rest.
        """
        annoncees = touches_annoncees_par_l_ecran()
        liees = touches_liees_dans_le_javascript()

        mortes = sorted(annoncees - liees)

        self.assertEqual(
            mortes,
            [],
            f"L'écran « Aide » annonce {mortes}, qui n'est lié nulle part "
            f"dans keyboard.js. Touches réellement liées : "
            f"{sorted(liees)}.",
        )

    def test_la_modale_n_annonce_que_des_touches_liees(self):
        """
        La seconde liste, soumise a la meme regle : c'est en n'en
        verrouillant qu'une seule que `S` a survecu dans l'autre.
        / The second list, under the same rule.
        """
        annoncees = touches_annoncees_par_la_modale()
        liees = touches_liees_dans_le_javascript()

        mortes = sorted(annoncees - liees)

        self.assertEqual(
            mortes,
            [],
            f"La modale « ? » annonce {mortes}, qui n'est lié nulle part "
            f"dans keyboard.js.",
        )

    def test_le_javascript_lie_bien_ce_qu_on_croit(self):
        """
        LA CONTRE-EPREUVE. Sans elle, une lecture qui rendrait un
        ensemble VIDE ferait passer les deux tests ci-dessus au vert —
        et l'audit ne protegerait plus rien.
        / The counterpart: an empty parse would make both tests pass.
        """
        liees = touches_liees_dans_le_javascript()

        for touche_attendue in ("E", "J", "K", "C", "X", "A", "Z", "?", "ESC"):
            self.assertIn(
                touche_attendue,
                liees,
                f"La lecture de keyboard.js ne trouve plus « "
                f"{touche_attendue} » : le motif de lecture est casse, ou "
                f"le raccourci a disparu.",
            )

    def test_les_deux_touches_de_l_audit_restent_dehors(self):
        """
        `T` et `S`, nommement. Elles ont vecu des mois dans l'aide sans
        etre liees ; ce test dit pourquoi elles n'y reviennent pas.
        / T and S, by name: months in the help, bound nowhere.
        """
        liees = touches_liees_dans_le_javascript()

        self.assertNotIn("T", liees)
        self.assertNotIn("S", liees)

        for lecture, nom in (
            (touches_annoncees_par_l_ecran(), "l'écran « Aide »"),
            (touches_annoncees_par_la_modale(), "la modale « ? »"),
        ):
            self.assertNotIn(
                "T", lecture,
                f"« T » (bibliothèque) revient dans {nom} : elle ouvrait "
                f"l'arbre latéral, retiré le 12 août 2026.",
            )
            self.assertNotIn(
                "S", lecture,
                f"« S » (consensuelle) revient dans {nom} : les six "
                f"statuts ont fusionné en deux le 2 mai 2026.",
            )


class L_aideNeParlePasDUnProduitDisparuTest(TestCase):
    """
    Le vocabulaire mort. / Dead vocabulary.

    LOCALISATION : front/tests/test_ce_que_dit_l_aide.py

    CES TESTS LISENT LE RENDU, PAS LE GABARIT. Django retire les
    `{% comment %}` a la compilation : les lire dans le fichier source
    ferait tomber la suite sur les commentaires qui EXPLIQUENT pourquoi
    un mot a ete retire. Mesure du 21 aout : la premiere version de ce
    test s'est cassee sur son propre commentaire.

    Et c'est de toute facon la bonne mesure — ce qui compte est ce que
    l'utilisateur LIT, pas ce que le gabarit contient.
    / They read the rendered page: Django strips {% comment %}, so
    reading the source would trip over the comments explaining the
    removal. And the rendered text is what the reader actually gets.
    """

    def rendu_de_l_ecran_aide(self):
        """
        Le partial de `/aide/`, tel que HTMX le pose dans la page.
        / The /aide/ partial, as HTMX drops it into the page.
        """
        reponse = self.client.get("/aide/", HTTP_HX_REQUEST="true")
        return reponse.content.decode().lower()

    def test_l_ecran_aide_ne_parle_plus_de_pastilles(self):
        """
        Les pastilles de marge appartenaient a l'ancien moteur
        d'ancrage, retire le 10 aout 2026. `test_phases.py` verrouille
        deja la disparition de leur CSS ; ce test-ci verrouille la
        disparition du MOT, qui avait survecu onze jours de plus dans
        l'ecran cense expliquer le produit.
        / The CSS was already guarded; the WORD outlived it by eleven
        days in the very screen that explains the product.
        """
        self.assertNotIn("pastille", self.rendu_de_l_ecran_aide())

    def test_l_ecran_aide_ne_parle_plus_de_statut_consensuel(self):
        """
        Deux statuts depuis le 2 mai 2026 : nouveau et commente.
        / Two statuses since 2 May 2026.
        """
        rendu = self.rendu_de_l_ecran_aide()

        for mot_mort in ("consensuel", "discutable", "controvers"):
            self.assertNotIn(
                mot_mort,
                rendu,
                f"« {mot_mort} » revient dans l'écran « Aide » : les six "
                f"statuts ont fusionné en deux le 2 mai 2026.",
            )

    def test_l_ecran_aide_nomme_le_geste_reel(self):
        """
        La contre-epreuve du test des pastilles : avoir retire le mot ne
        suffit pas, il faut que le bon soit la. Le geste est un clic sur
        le SURLIGNAGE, et la gouttiere porte le compteur.
        / Removing the wrong word is not enough; the right one must be
        there.
        """
        rendu = self.rendu_de_l_ecran_aide()

        self.assertIn("surlign", rendu)
        self.assertIn("goutti", rendu)

    def test_l_ecran_aide_situe_la_synthese_au_carnet(self):
        """
        Une synthese est une note DU CARNET, en deux genres. Le dire
        etait le seul moyen de rendre visible le choix que
        l'utilisateur a a faire.
        / A synthesis is a note OF THE NOTEBOOK, in two genres.
        """
        rendu = self.rendu_de_l_ecran_aide()

        self.assertIn("wiki", rendu)
        self.assertIn("dirig", rendu)
        self.assertIn("carnet", rendu)

    def test_l_ecran_aide_n_annonce_pas_la_capture_web_par_le_bouton(self):
        """
        L'attribut `accept` du bouton n'admet aucune extension de page
        web : une capture passe par l'EXTENSION NAVIGATEUR. L'aide
        listait « page web » parmi ce que le bouton accepte.
        / The accept attribute admits no web page format: captures come
        from the browser extension.
        """
        rendu = self.rendu_de_l_ecran_aide()

        self.assertIn("extension navigateur", rendu)
