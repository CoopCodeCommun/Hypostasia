"""
Tests des BOUTONS d'operations d'element dans la lecture (U1).
/ Element operation buttons in the reading zone (U1).

LOCALISATION : front/tests/test_boutons_elements.py

Les endpoints BR-E existent et sont testes (test_views_element) ; ici
on verrouille leur SURFACE dans l'interface :
- un bouton a bascule « Modifier la structure » (mode-structure), rendu
  seulement pour qui PEUT ECRIRE la note (meme regle que les endpoints,
  _utilisateur_peut_ecrire_page) et seulement sur une page ELEMENT ;
- sur chaque bloc, un groupe de boutons (corriger, couper en deux,
  recoller avec le suivant, masquer) cache hors mode structure par le
  CSS — le DOM ne les porte PAS pour un simple lecteur ;
- un element MASQUE apparait en placeholder demasquable pour qui peut
  ecrire, et reste entierement absent pour un simple lecteur.
/ Buttons render server-side for writers only; masked elements become
un-hideable placeholders for writers, stay absent for readers.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import ElementDocument, Page, empreinte_du_texte

Utilisateur = get_user_model()


class BaseBoutonsElementsTest(TestCase):
    """
    Socle : une page ELEMENT a deux blocs, son proprietaire (qui peut
    ecrire) et un superuser tiers (qui peut LIRE — bypass superuser —
    mais pas ecrire : la regle d'ecriture n'a pas de bypass).
    / Owner can write; a non-owner superuser can only read.
    """

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="proprio-boutons", password="motdepasse",
        )
        self.lecteur_superuser = Utilisateur.objects.create_superuser(
            username="lecteur-boutons", password="motdepasse",
        )
        self.page = Page.objects.create(
            url="http://exemple.local/u1-boutons",
            html_original="<p>o</p>",
            html_readability="<p>Repli readability.</p>",
            text_readability="texte", content_hash="hash-u1-boutons",
            owner=self.proprietaire,
            status="completed",
        )
        self.element_titre = self._element(
            "Le grand titre", ordre=0, label="title",
        )
        self.element_corps = self._element(
            "Un paragraphe de corps.", ordre=1,

    )

    def _element(self, texte, ordre=0, label="text", masque=False):
        return ElementDocument.objects.create(
            page=self.page, ordre=ordre, label=label, texte=texte,
            empreinte_contenu=empreinte_du_texte(texte), masque=masque,

    )

    def _lire(self):
        return self.client.get(
            f"/lire/{self.page.pk}/", HTTP_HX_REQUEST="true").content.decode()


class BoutonsPourQuiPeutEcrireTest(BaseBoutonsElementsTest):
    """Le proprietaire voit la bascule et les boutons de chaque bloc."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.proprietaire,

    )

    def test_la_bascule_du_mode_structure_est_rendue(self):
        contenu = self._lire()
        self.assertIn('data-testid="bouton-mode-structure"', contenu,
        )
        # C'est un bouton a bascule : son etat est annonce.
        # / It is a toggle: its state is announced.
        self.assertIn('aria-pressed', contenu,

    )

    def test_chaque_bloc_porte_son_groupe_de_boutons(self):
        contenu = self._lire()
        self.assertIn('data-testid="actions-element-0"', contenu,
        )
        self.assertIn('data-testid="actions-element-1"', contenu)

    def test_les_boutons_visent_les_bons_endpoints(self):
        contenu = self._lire()
        pk = self.element_corps.pk
        # Corriger et scinder ouvrent un FORMULAIRE (GET) ; recoller et
        # masquer agissent directement (POST + confirmation HTMX).
        # / Correct & split fetch a form; merge & hide post directly.
        self.assertIn(f"/elements/{pk}/formulaire_correction/", contenu,
        )
        self.assertIn(f"/elements/{pk}/formulaire_scission/", contenu)
        self.assertIn(f"/elements/{pk}/masquer/", contenu,
        )
        # Recoller vise le SUIVANT : le bouton existe sur le premier
        # bloc, pas sur le dernier (il n'y a rien apres lui).
        # / Merge targets the NEXT one: present on the first block,
        # absent on the last.
        self.assertIn(
            f"/elements/{self.element_titre.pk}/fusionner_avec_le_suivant/",
            contenu,
        )
        self.assertNotIn(
            f"/elements/{pk}/fusionner_avec_le_suivant/", contenu,

    )

    def test_le_conteneur_du_dialogue_est_rendu(self):
        # Les formulaires (corriger, scinder) s'ouvrent dans un dialogue
        # injecte ici. / The forms open inside this dialog container.
        contenu = self._lire()
        self.assertIn('data-testid="zone-dialogue-element"', contenu,

    )

    def test_un_element_masque_apparait_en_placeholder_demasquable(self):
        masque = self._element("Pied de page repete.", ordre=2, masque=True,
        )
        contenu = self._lire()
        self.assertIn('data-testid="element-masque-2"', contenu,
        )
        self.assertIn(f"/elements/{masque.pk}/demasquer/", contenu)
        # Le texte est la, pour savoir CE QU'on demasque.
        # / The text is shown so one knows what gets restored.
        self.assertIn("Pied de page repete.", contenu,

    )

    def test_un_element_masque_n_est_pas_un_bloc_de_lecture(self):
        # Masque = hors du texte de lecture ; le placeholder est un
        # autre testid. / Hidden means out of the reading flow.
        self._element("Pied de page repete.", ordre=2, masque=True,
        )
        contenu = self._lire()
        self.assertNotIn('data-testid="bloc-element-2"', contenu,


)


class BoutonsPourUnSimpleLecteurTest(BaseBoutonsElementsTest):
    """Un lecteur sans droit d'ecriture n'a RIEN de tout ca dans le DOM."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.lecteur_superuser,

    )

    def test_ni_bascule_ni_boutons_pour_un_lecteur(self):
        contenu = self._lire()
        self.assertNotIn('data-testid="bouton-mode-structure"', contenu,
        )
        self.assertNotIn('data-testid="actions-element-0"', contenu)
        self.assertNotIn("/formulaire_correction/", contenu,

    )

    def test_un_element_masque_reste_absent_pour_un_lecteur(self):
        self._element("Pied de page repete.", ordre=2, masque=True,
        )
        contenu = self._lire()
        self.assertNotIn("Pied de page repete.", contenu,
        )
        self.assertNotIn('data-testid="element-masque-2"', contenu)


class BoutonsSurUnePageAncienneTest(BaseBoutonsElementsTest):
    """Le mode structure n'existe que pour une page ELEMENT."""

    def test_pas_de_bascule_sur_une_page_ancienne(self):
        page_ancienne = Page.objects.create(
            url="http://exemple.local/u1-ancienne",
            html_original="<p>o</p>",
            html_readability="<p>Repli readability.</p>",
            text_readability="texte", content_hash="hash-u1-ancienne",
            owner=self.proprietaire,
            status="completed",
        )
        self.client.force_login(self.proprietaire)
        contenu = self.client.get(
            f"/lire/{page_ancienne.pk}/", HTTP_HX_REQUEST="true").content.decode()
        self.assertNotIn('data-testid="bouton-mode-structure"', contenu,


)


class CorrectifsRelectureU1Test(BaseBoutonsElementsTest):
    """
    Les correctifs de la relecture adverse U1 (10 aout) qui se
    verrouillent au rendu. / U1 adversarial-review fixes, template side.
    """

    def setUp(self):
        super().setUp()
        self.client.force_login(self.proprietaire,

    )

    def test_un_bloc_pre_ne_gagne_aucune_ligne_parasite(self):
        # H3 : l'include des boutons injectait ~24 retours a la ligne
        # VISIBLES dans un <pre> (contenu preformate). Le texte doit
        # etre immediatement suivi du groupe d'actions.
        # / The action include must not leak newlines into a <pre>.
        self._element("ligne un\nligne deux", ordre=2, label="code",
        )
        contenu = self._lire()
        self.assertIn("ligne un\nligne deux<span", contenu,

    )

    def test_le_bouton_recoller_est_absent_si_le_suivant_est_masque(self):
        # M8 : fusionner un visible avec un masque est toujours refuse
        # par le service — le bouton ne doit pas etre propose.
        # / No merge button when the NEXT element is hidden.
        masque = self._element("Pied de page.", ordre=2, masque=True,
        )
        dernier = self._element("Fin du texte.", ordre=3)
        contenu = self._lire()
        self.assertNotIn(
            f"/elements/{self.element_corps.pk}/fusionner_avec_le_suivant/",
            contenu,
        )
        # Le premier element, lui, garde son bouton (suivant visible).
        self.assertIn(
            f"/elements/{self.element_titre.pk}/fusionner_avec_le_suivant/",
            contenu,

    )

    def test_une_liste_entierement_masquee_ne_rend_pas_un_ul_vide(self):
        # B3 : pour un simple lecteur, une liste dont toutes les puces
        # sont masquees ne doit pas laisser un <ul></ul> vide.
        # / No empty <ul> for readers when every bullet is hidden.
        self._element("Puce cachee une.", ordre=2, label="list_item",
                      masque=True,
        )
        self._element("Puce cachee deux.", ordre=3, label="list_item",
                      masque=True,
        )
        self.client.force_login(self.lecteur_superuser)
        contenu = self._lire()
        import re
        self.assertNotRegex(contenu, r"<ul>\s*</ul>",

    )

    def test_l_etat_du_bouton_a_bascule_est_annonce_sur_le_bouton(self):
        # B4 : l'assertion d'origine acceptait un aria-pressed pose
        # n'importe ou. / aria-pressed must sit on the toggle itself.
        import re
        contenu = self._lire()
        bouton = re.search(
            r'<button[^>]*data-testid="bouton-mode-structure"[^>]*>',
            contenu,
        )
        self.assertIsNotNone(bouton)
        self.assertIn('aria-pressed="false"', bouton.group(0))
