"""
Ancrer un texte choisi a la main dans les elements d'une page.
/ Anchoring a hand-picked text into a page's elements.

LOCALISATION : hypostasis_extractor/tests/test_ancrage_d_un_texte_libre.py

Une extraction creee A LA MAIN, ou produite par l'action « IA sur la
selection », cherchait sa position dans `Page.text_readability`. Ce champ
est VIDE sur toute note ingeree par Docling : `find()` rendait -1, le
code retombait sur `start_char = 0`, et AUCUNE `AncrageExtraction`
n'etait creee. Resultat : une extraction sans preuve, qui renvoie en tete
de document au clic.

C'est l'incident du 13 aout 2026 consigne dans `PLAN/PASSATION.md`
(« neuf extractions sur douze ancrees a start_char = 0 »), dont la
commande de fixtures avait tire la lecon sans que les deux vues la
tirent.

Le service ci-dessous reutilise la machinerie du moteur ELEMENT — la
table des offsets et le decoupage en portions — au lieu d'en refaire une
seconde.
/ Manual extractions searched an empty field, landed at 0 and were never
anchored. This service reuses the ELEMENT machinery instead.
"""

from django.test import TestCase

from core.models import ElementDocument, Page


class AncrerUnTexteLibreTest(TestCase):
    """Le texte choisi retrouve ses portions. / The picked text finds them."""

    def setUp(self):
        # Une note comme Docling la laisse : elements remplis, texte plat
        # VIDE. / As Docling leaves it: elements filled, flat text empty.
        self.page = Page.objects.create(
            url="http://exemple.local/ancrage-manuel",
            html_original="", html_readability="", text_readability="",
            content_hash="hash-ancrage-manuel", title="Note ingérée",
        )
        self.premier = ElementDocument.objects.create(
            page=self.page, ordre=0, label="text",
            texte="Le seuil de dix mille euros déclenche le passage en "
                  "assemblée générale.",
            empreinte_contenu="a0",
        )
        self.second = ElementDocument.objects.create(
            page=self.page, ordre=1, label="text",
            texte="L'ajournement répété est présenté comme un coût en soi.",
            empreinte_contenu="a1",
        )

    def _ancrer(self, texte):
        from hypostasis_extractor.services.ancrage import (
            ancrer_un_texte_dans_une_page,
        )
        return ancrer_un_texte_dans_une_page(self.page, texte)

    def test_un_texte_dans_un_seul_element_donne_une_portion(self):
        portions = self._ancrer("dix mille euros")

        self.assertEqual(len(portions), 1)
        self.assertEqual(portions[0]["element"], self.premier)
        debut = portions[0]["debut_dans_element"]
        fin = portions[0]["fin_dans_element"]
        self.assertEqual(self.premier.texte[debut:fin], "dix mille euros")

    def test_un_texte_qui_enjambe_deux_elements_donne_deux_portions(self):
        # Une idee d'une phrase enjambe deja deux elements dans 7,5 % des
        # cas mesures sur ce projet. / Spanning is the normal case.
        portions = self._ancrer(
            "assemblée générale.\n\nL'ajournement répété"
        )

        self.assertEqual(len(portions), 2)
        self.assertEqual(portions[0]["element"], self.premier)
        self.assertEqual(portions[1]["element"], self.second)
        self.assertEqual(portions[0]["ordre_dans_extraction"], 0)
        self.assertEqual(portions[1]["ordre_dans_extraction"], 1)

    def test_un_texte_absent_ne_rend_aucune_portion(self):
        # On ne devine pas : rien trouve, rien d'ancre. Surtout PAS une
        # portion au debut du document. / Never guess, never anchor at 0.
        portions = self._ancrer("un texte qui n'est nulle part")

        self.assertEqual(portions, [])

    def test_la_typographie_ne_fait_pas_echouer_l_ancrage(self):
        # Le presse-papier d'un navigateur rend des apostrophes courbes
        # la ou l'element porte des droites, et inversement.
        # / Browser clipboards swap apostrophes.
        portions = self._ancrer("L’ajournement répété")

        self.assertEqual(len(portions), 1)
        self.assertEqual(portions[0]["element"], self.second)

    def test_une_page_sans_element_ne_rend_aucune_portion(self):
        ElementDocument.objects.filter(page=self.page).delete()

        self.assertEqual(self._ancrer("dix mille euros"), [])


class LaNormalisationNeDoitPasDecalerTest(TestCase):
    """
    La forme comparable doit etre STRICTEMENT 1:1 en longueur.
    / The comparable form must be strictly length-preserving.

    LOCALISATION : hypostasis_extractor/tests/test_ancrage_d_un_texte_libre.py

    NFKC N'EST PAS ISO-LONGUEUR : « … » devient « ... » (1 -> 3), la
    ligature « fi » devient « fi » (1 -> 2), « ½ » devient « 1/2 ».
    Chercher dans la forme normalisee puis reporter la position dans le
    texte REEL decale alors l'ancre — et une ancre decalee se donne pour
    une preuve, ce que ce service jure d'empecher.

    Le corpus etalon porte deja 5 caracteres « … » (mesure du 17 aout
    2026), donc le cas n'est pas theorique.
    / NFKC is not length-preserving; the reference corpus already holds 5
    ellipsis characters.
    """

    def setUp(self):
        self.page = Page.objects.create(
            url="http://exemple.local/normalisation",
            html_original="", html_readability="", text_readability="",
            content_hash="hash-normalisation", title="Note piégeuse",
        )

    def _element(self, texte):
        return ElementDocument.objects.create(
            page=self.page, ordre=0, label="text",
            texte=texte, empreinte_contenu="n0",
        )

    def _ancrer(self, texte):
        from hypostasis_extractor.services.ancrage import (
            ancrer_un_texte_dans_une_page,
        )
        return ancrer_un_texte_dans_une_page(self.page, texte)

    def test_des_points_de_suspension_en_amont_ne_decalent_pas_l_ancre(self):
        # « … » vaut UN caractere ; NFKC en ferait TROIS, et tout ce qui
        # suit serait decale de deux. / One char that NFKC turns into 3.
        element = self._element(
            "Il hésite… puis le passage visé arrive ici et se termine."
        )

        portions = self._ancrer("le passage visé arrive ici")

        self.assertEqual(len(portions), 1)
        debut = portions[0]["debut_dans_element"]
        fin = portions[0]["fin_dans_element"]
        self.assertEqual(
            element.texte[debut:fin], "le passage visé arrive ici",
            "l'ancre est décalée : la normalisation n'est pas iso-longueur",
        )

    def test_une_ligature_en_amont_ne_decale_pas_l_ancre(self):
        element = self._element(
            "La ﬁn du premier membre, puis le passage visé, et la suite."
        )

        portions = self._ancrer("le passage visé")

        self.assertEqual(len(portions), 1)
        debut = portions[0]["debut_dans_element"]
        fin = portions[0]["fin_dans_element"]
        self.assertEqual(element.texte[debut:fin], "le passage visé")

    def test_l_apostrophe_courbe_marche_toujours(self):
        # La substitution 1:1 qu'on garde. / The 1:1 substitution we keep.
        element = self._element("L'ajournement répété est un coût.")

        portions = self._ancrer("L’ajournement répété")

        self.assertEqual(len(portions), 1)
        debut = portions[0]["debut_dans_element"]
        fin = portions[0]["fin_dans_element"]
        self.assertEqual(element.texte[debut:fin], "L'ajournement répété")
