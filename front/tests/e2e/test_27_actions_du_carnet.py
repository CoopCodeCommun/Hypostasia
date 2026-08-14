"""
Tests E2E — LES ACTIONS QUE L'ARBRE LATERAL PORTAIT SEUL.
/ E2E tests — the actions the side tree was the only host for.

LOCALISATION : front/tests/e2e/test_27_actions_du_carnet.py

POURQUOI CE MODULE
------------------
Le tiroir lateral (`#arbre-overlay`) doit disparaitre : le burger mene
desormais a `/bases/` et le mainteneur ne veut plus d'arbre du tout.

Mais l'arbre n'etait pas qu'une navigation. Il etait le SEUL endroit du
produit ou l'on pouvait :

    creer un carnet  ..............  #btn-creer-dossier-overlay
    importer sur mobile  ..........  #input-import-fichier-overlay
                                     (la barre cache son import en
                                      dessous de 768 px)
    renommer un carnet  ...........  menu contextuel
    changer sa visibilite  ........  menu contextuel
    le partager  ..................  menu contextuel
    le supprimer  .................  menu contextuel
    quitter un partage recu  ......  .btn-quitter-partage
    supprimer une note  ...........  menu contextuel

Retirer l'arbre sans reloger ces huit gestes n'aurait pas simplifie le
produit : ca l'aurait AMPUTE, en silence, sans qu'aucun test ne tombe —
le meme accident que le dashboard qui portait le seul acces a la
synthese, rattrape de justesse la nuit du 11 au 12 aout.

Ce module verrouille le NOUVEAU domicile de chaque geste, AVANT que
l'arbre parte. Il ne connait plus l'arbre : il ne teste que les pages
`/carnets/` et `/carnets/<id>/`, qui sont les hotes naturels.

CE QUI N'EST PAS ICI, ET POURQUOI
---------------------------------
    naviguer carnet -> note  ......  deja sur /carnets/<id>/
    deplacer une note  ............  deja dans le bloc « Dans N
                                     carnets » de la page de la note
    aligner un carnet  ............  deja l'onglet « Alignement » de
                                     /carnets/<id>/
    voir les carnets publics  .....  deja /carnets/ (carnets_visibles_par)

Ces quatre-la avaient DEJA un second domicile : rien a reloger, donc
rien a verrouiller ici.
"""

from django.contrib.auth.models import User

from core.models import (
    Dossier,
    DossierPartage,
    Page,
    VisibiliteDossier,
)
from core.services.corpus import ranger_une_note_dans_un_carnet

from .base import PlaywrightLiveTestCase

# La largeur en dessous de laquelle la barre bascule en mode mobile
# (`.btn-desktop-only` se cache a 768 px, voir maquette.css).
# / The width below which the toolbar switches to mobile mode.
LARGEUR_MOBILE = 375
HAUTEUR_MOBILE = 667


class CreationDeCarnetDepuisLaListeTest(PlaywrightLiveTestCase):
    """
    « Creer un carnet » vit desormais sur /carnets/.
    / "Create a notebook" now lives on /carnets/.
    """

    def setUp(self):
        super().setUp()
        self.proprietaire = User.objects.create_user(
            username="jardinier", password="motdepasse1234",
        )

    def test_la_liste_des_carnets_porte_une_creation(self):
        """
        Un visiteur connecte trouve de quoi creer un carnet sur /carnets/.
        / A signed-in visitor finds a creation control on /carnets/.
        """
        self.se_connecter("jardinier", "motdepasse1234")
        self.naviguer_vers("/carnets/")

        formulaire = self.page.locator('[data-testid="corpus-carnet-creer-form"]')
        self.assertTrue(
            formulaire.is_visible(),
            "La liste des carnets doit porter un formulaire de creation : "
            "l'arbre etait le seul endroit ou creer un carnet.",
        )

    def test_la_creation_cree_vraiment_un_carnet(self):
        """
        Le formulaire cree le carnet et la liste le montre aussitot.
        / The form really creates the notebook and the list shows it.
        """
        self.se_connecter("jardinier", "motdepasse1234")
        self.naviguer_vers("/carnets/")

        self.page.fill(
            '[data-testid="corpus-carnet-creer-nom"]', "Conseil de quartier",
        )
        self.page.click('[data-testid="corpus-carnet-creer-bouton"]')
        self.attendre_htmx()

        self.assertTrue(
            Dossier.objects.filter(
                name="Conseil de quartier", owner=self.proprietaire,
            ).exists(),
            "Le carnet doit exister en base apres la soumission.",
        )
        self.page.wait_for_selector(
            'text=Conseil de quartier', timeout=5000,
        )

    def test_un_anonyme_ne_voit_pas_la_creation(self):
        """
        Un visiteur anonyme ne peut pas creer : le formulaire est absent.
        / An anonymous visitor gets no creation form.
        """
        self.naviguer_vers("/carnets/")
        self.assertEqual(
            self.page.locator('[data-testid="corpus-carnet-creer-form"]').count(),
            0,
            "Un anonyme ne doit pas voir le formulaire de creation.",
        )


class ImportAtteignableSurMobileTest(PlaywrightLiveTestCase):
    """
    L'import sur mobile passait par l'arbre : la barre cache le sien en
    dessous de 768 px (« sur mobile on importe via l'arbre »).
    / Mobile import went through the tree; the toolbar hid its own.
    """

    def setUp(self):
        super().setUp()
        self.lecteur = User.objects.create_user(
            username="marcheur", password="motdepasse1234",
        )

    def test_l_import_de_la_barre_est_visible_sur_mobile(self):
        """
        Sur un ecran de telephone, l'import de la barre reste atteignable.
        / On a phone-sized screen the toolbar import stays reachable.
        """
        self.se_connecter("marcheur", "motdepasse1234")
        self.page.set_viewport_size(
            {"width": LARGEUR_MOBILE, "height": HAUTEUR_MOBILE},
        )
        self.naviguer_vers("/carnets/")

        bouton_import = self.page.locator('[data-testid="btn-toolbar-import"]')
        self.assertTrue(
            bouton_import.is_visible(),
            "L'import de la barre doit rester visible sur mobile : sans "
            "lui, un telephone n'a plus AUCUN moyen d'importer une fois "
            "l'arbre retire.",
        )

    def test_l_import_de_la_barre_reste_visible_sur_desktop(self):
        """
        Le rendre visible sur mobile ne doit pas le faire disparaitre
        ailleurs. / Showing it on mobile must not hide it elsewhere.
        """
        self.se_connecter("marcheur", "motdepasse1234")
        self.naviguer_vers("/carnets/")
        self.assertTrue(
            self.page.locator('[data-testid="btn-toolbar-import"]').is_visible(),
        )


class ActionsDuCarnetSurSaPageTest(PlaywrightLiveTestCase):
    """
    Renommer, visibilite, partager, supprimer : le menu contextuel de
    l'arbre relogé sur la page du carnet.
    / The tree's context menu, rehoused on the notebook's own page.
    """

    def setUp(self):
        super().setUp()
        self.proprietaire = User.objects.create_user(
            username="proprio", password="motdepasse1234",
        )
        self.passant = User.objects.create_user(
            username="passant", password="motdepasse1234",
        )
        self.carnet = Dossier.objects.create(
            name="Carnet du conseil",
            owner=self.proprietaire,
            visibilite=VisibiliteDossier.PUBLIC,
        )

    def ouvrir_la_gouvernance(self):
        """
        Deplie « Gerer ce carnet ».

        Le bloc est un `<details>` REPLIE : on vient sur un carnet pour
        le lire, pas pour l'administrer. Le geste d'ouverture est donc
        une etape reelle du parcours, pas un contournement de test — et
        contrairement au clic droit de l'arbre, le controle qui l'ouvre
        est VISIBLE et porte son nom.
        / The block is a collapsed <details>; opening it is a real step
        of the journey, and unlike the tree's right-click the control
        that opens it is visible and named.
        """
        self.page.click(
            '[data-testid="corpus-carnet-gouvernance"] > summary'
        )

    def test_le_proprietaire_voit_le_bloc_de_gouvernance(self):
        """
        Le bloc « Gerer ce carnet » est VISIBLE sans rien deplier : c'est
        lui qui remplace le clic droit de l'arbre, il doit donc se voir.
        / The block itself is visible with nothing unfolded: it replaces
        a right-click, so it must be seen.
        """
        self.se_connecter("proprio", "motdepasse1234")
        self.naviguer_vers(f"/carnets/{self.carnet.pk}/")
        self.assertTrue(
            self.page.locator(
                '[data-testid="corpus-carnet-gouvernance"] > summary'
            ).is_visible(),
            "« Gerer ce carnet » doit se voir sans rien deplier.",
        )

    def test_le_proprietaire_voit_les_quatre_actions(self):
        """
        Le proprietaire retrouve les quatre gestes du menu contextuel.
        / The owner finds the four context-menu gestures.
        """
        self.se_connecter("proprio", "motdepasse1234")
        self.naviguer_vers(f"/carnets/{self.carnet.pk}/")
        self.ouvrir_la_gouvernance()

        # `corpus-carnet-visibilite` est DEJA pris : c'est le mot qui
        # AFFICHE la visibilite dans l'en-tete. Le controle qui la CHANGE
        # porte donc un autre nom — confondre les deux ferait passer le
        # test sur l'affichage seul, sans qu'aucun controle existe.
        # / The display testid already exists; the control needs its own,
        # or the test would pass on the label alone.
        for identifiant, ce_que_c_est in [
            ("corpus-carnet-renommer", "renommer"),
            ("corpus-carnet-changer-visibilite", "changer la visibilite"),
            ("corpus-carnet-partager", "partager"),
            ("corpus-carnet-supprimer", "supprimer"),
        ]:
            self.assertTrue(
                self.page.locator(f'[data-testid="{identifiant}"]').is_visible(),
                f"La page du carnet doit porter de quoi {ce_que_c_est} : "
                f"l'arbre en etait le seul point d'entree. (On mesure la "
                f"VISIBILITE : replie, le bloc contient deja les noeuds, "
                f"et un simple compte passerait meme s'il ne s'ouvrait "
                f"jamais.)",
            )

    def test_un_passant_ne_voit_aucune_action(self):
        """
        Un visiteur qui n'est pas proprietaire n'a aucune de ces actions.
        / A non-owner sees none of them.
        """
        self.se_connecter("passant", "motdepasse1234")
        self.naviguer_vers(f"/carnets/{self.carnet.pk}/")

        for identifiant in [
            "corpus-carnet-renommer",
            "corpus-carnet-changer-visibilite",
            "corpus-carnet-partager",
            "corpus-carnet-supprimer",
        ]:
            self.assertEqual(
                self.page.locator(f'[data-testid="{identifiant}"]').count(),
                0,
                f"« {identifiant} » ne doit pas etre offert a un passant.",
            )

    def test_renommer_depuis_la_page_du_carnet(self):
        """
        Le renommage marche et la page rendue porte le nouveau nom.
        / Renaming works and the rendered page carries the new name.
        """
        self.se_connecter("proprio", "motdepasse1234")
        self.naviguer_vers(f"/carnets/{self.carnet.pk}/")

        self.ouvrir_la_gouvernance()
        self.page.fill(
            '[data-testid="corpus-carnet-renommer-nom"]', "Carnet renomme",
        )
        self.page.click('[data-testid="corpus-carnet-renommer-bouton"]')
        self.attendre_htmx()

        self.carnet.refresh_from_db()
        self.assertEqual(self.carnet.name, "Carnet renomme")
        self.page.wait_for_selector("text=Carnet renomme", timeout=5000)

    def test_changer_la_visibilite_depuis_la_page_du_carnet(self):
        """
        La visibilite bascule et la page le dit.
        / Visibility switches and the page says so.
        """
        self.se_connecter("proprio", "motdepasse1234")
        self.naviguer_vers(f"/carnets/{self.carnet.pk}/")

        self.ouvrir_la_gouvernance()
        self.page.click('[data-testid="corpus-carnet-visibilite-choix-prive"]')
        self.attendre_htmx()

        self.carnet.refresh_from_db()
        self.assertEqual(self.carnet.visibilite, VisibiliteDossier.PRIVE)

    def test_partager_ouvre_le_formulaire_de_partage(self):
        """
        Le geste « partager » charge le formulaire de partage existant.
        / The share gesture loads the existing sharing form.
        """
        self.se_connecter("proprio", "motdepasse1234")
        self.naviguer_vers(f"/carnets/{self.carnet.pk}/")

        self.ouvrir_la_gouvernance()
        self.page.click('[data-testid="corpus-carnet-partager"]')
        self.page.wait_for_selector(
            '[data-testid="partage-dossier-form"]', timeout=5000,
        )

    def test_supprimer_depuis_la_page_du_carnet(self):
        """
        La suppression efface le carnet et ramene a la liste.
        / Deleting removes the notebook and lands back on the list.
        """
        self.se_connecter("proprio", "motdepasse1234")
        self.naviguer_vers(f"/carnets/{self.carnet.pk}/")

        # hx-confirm ouvre un confirm() natif : on l'accepte.
        # / hx-confirm opens a native confirm(): accept it.
        self.ouvrir_la_gouvernance()
        self.page.on("dialog", lambda boite: boite.accept())
        self.page.click('[data-testid="corpus-carnet-supprimer"]')
        self.attendre_htmx()

        self.assertFalse(
            Dossier.objects.filter(pk=self.carnet.pk).exists(),
            "Le carnet doit avoir ete supprime.",
        )
        self.page.wait_for_selector(
            '[data-testid="corpus-carnets-liste"]', timeout=5000,
        )


class QuitterUnPartageDepuisLeCarnetTest(PlaywrightLiveTestCase):
    """
    « Quitter ce partage » ne vivait que dans l'arbre (.btn-quitter-partage).
    / "Leave this share" lived only in the tree.
    """

    def setUp(self):
        super().setUp()
        self.proprietaire = User.objects.create_user(
            username="pretteur", password="motdepasse1234",
        )
        self.invite = User.objects.create_user(
            username="invite", password="motdepasse1234",
        )
        self.carnet = Dossier.objects.create(
            name="Carnet pret",
            owner=self.proprietaire,
            visibilite=VisibiliteDossier.PARTAGE,
        )
        DossierPartage.objects.create(
            dossier=self.carnet, utilisateur=self.invite,
        )

    def test_l_invite_peut_quitter_le_partage(self):
        """
        L'invite trouve le geste sur la page du carnet, et il agit.
        / The guest finds the gesture on the notebook page, and it works.
        """
        self.se_connecter("invite", "motdepasse1234")
        self.naviguer_vers(f"/carnets/{self.carnet.pk}/")

        self.page.on("dialog", lambda boite: boite.accept())
        self.page.click('[data-testid="corpus-carnet-quitter"]')
        self.attendre_htmx()

        self.assertFalse(
            DossierPartage.objects.filter(
                dossier=self.carnet, utilisateur=self.invite,
            ).exists(),
            "Le partage doit avoir ete quitte.",
        )

    def test_le_proprietaire_ne_voit_pas_quitter(self):
        """
        On ne quitte pas son propre carnet : le geste n'a pas de sens.
        / You do not leave your own notebook.
        """
        self.se_connecter("pretteur", "motdepasse1234")
        self.naviguer_vers(f"/carnets/{self.carnet.pk}/")
        self.assertEqual(
            self.page.locator('[data-testid="corpus-carnet-quitter"]').count(),
            0,
        )


class SuppressionDUneNoteDepuisLeCarnetTest(PlaywrightLiveTestCase):
    """
    « Supprimer » sur une note ne vivait que dans le menu contextuel de
    l'arbre. Il est relogé dans la liste des notes du carnet, ou la note
    apparait deja — et distingue de « retirer du carnet », qui ne
    supprime rien.
    / Deleting a note lived only in the tree's context menu.
    """

    def setUp(self):
        super().setUp()
        self.proprietaire = User.objects.create_user(
            username="auteur", password="motdepasse1234",
        )
        self.carnet = Dossier.objects.create(
            name="Carnet a notes", owner=self.proprietaire,
        )
        self.note = Page.objects.create(
            title="Note jetable",
            html_readability="<p>Rien.</p>",
            text_readability="Rien.",
            source_type="file",
            status="completed",
            owner=self.proprietaire,
            dossier=self.carnet,
        )
        ranger_une_note_dans_un_carnet(
            self.note, self.carnet, self.proprietaire,
        )

    def test_le_proprietaire_peut_supprimer_une_note(self):
        """
        La note disparait de la base et de la liste.
        / The note leaves both the database and the list.
        """
        self.se_connecter("auteur", "motdepasse1234")
        self.naviguer_vers(f"/carnets/{self.carnet.pk}/")

        self.page.on("dialog", lambda boite: boite.accept())
        self.page.click('[data-testid="corpus-note-supprimer"]')
        self.attendre_htmx()

        self.assertFalse(
            Page.objects.filter(pk=self.note.pk).exists(),
            "La note doit avoir ete supprimee.",
        )

