"""
Tests de l'edition d'une base : description et couverture.
/ Tests for editing a knowledge base: description and cover.

LOCALISATION : front/tests/test_edition_d_une_base.py

POURQUOI CES TESTS EXISTENT

La carte d'une base montre sa description et, si elle en a une, sa
couverture. Les deux champs existaient en base — mais RIEN dans
l'interface ne permettait de les renseigner : l'admin Django est
desactive, et le formulaire de creation ne prend que le nom.

Un champ qu'aucun ecran ne remplit est un champ mort. La carte serait
restee au substitut typographique pour toujours, non par choix de
conception mais faute de porte d'entree.
/ Both fields existed but no screen could fill them: the Django admin is
disabled and the creation form only takes a name. A field no screen
fills is a dead field.
"""

import io

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from core.models import BaseDeConnaissances, VisibiliteDossier

User = get_user_model()


def fabriquer_une_image(largeur=40, hauteur=30):
    """Rend les octets d'un PNG uni. / Return the bytes of a plain PNG."""
    from PIL import Image

    tampon = io.BytesIO()
    Image.new("RGB", (largeur, hauteur), (28, 27, 25)).save(tampon, format="PNG")
    return tampon.getvalue()


class EditionDUneBaseTest(TestCase):
    """
    LOCALISATION : front/tests/test_edition_d_une_base.py
    """

    def setUp(self):
        self.proprietaire = User.objects.create_user(
            username="proprietaire", password="motdepasse"
        )
        self.passant = User.objects.create_user(
            username="passant", password="motdepasse"
        )
        self.base = BaseDeConnaissances.objects.create(
            nom="Base à éditer",
            slug="base-a-editer",
            owner=self.proprietaire,
            visibilite=VisibiliteDossier.PUBLIC,
        )

    # -------------------------------------------------------------------
    # Ce que le proprietaire peut faire
    # / What the owner can do
    # -------------------------------------------------------------------

    def test_le_proprietaire_ecrit_la_description(self):
        """Sans cet endpoint, le champ `description` reste mort."""
        self.client.force_login(self.proprietaire)

        reponse = self.client.post(
            f"/bases/{self.base.slug}/editer/",
            {"description": "Ce que cette base rassemble."},
        )

        self.assertEqual(reponse.status_code, 200)
        self.base.refresh_from_db()
        self.assertEqual(self.base.description, "Ce que cette base rassemble.")

    def test_le_proprietaire_televerse_une_couverture(self):
        """
        Le champ `image_de_couverture` a ete ajoute le 12 aout ; il
        n'avait aucun moyen d'etre rempli.
        / The cover field had no way of being filled.
        """
        self.client.force_login(self.proprietaire)

        reponse = self.client.post(
            f"/bases/{self.base.slug}/editer/",
            {
                "description": "Avec une couverture.",
                "image_de_couverture": SimpleUploadedFile(
                    "couverture.png", fabriquer_une_image(), content_type="image/png",
                ),
            },
        )

        self.assertEqual(reponse.status_code, 200)
        self.base.refresh_from_db()
        self.assertTrue(self.base.image_de_couverture)

    def test_televerser_une_couverture_n_efface_pas_la_description(self):
        """
        Les deux champs voyagent dans le meme formulaire : oublier l'un
        ne doit pas vider l'autre.
        / Both fields share one form; omitting one must not blank it.
        """
        self.base.description = "Une description déjà écrite."
        self.base.save(update_fields=["description"])
        self.client.force_login(self.proprietaire)

        self.client.post(
            f"/bases/{self.base.slug}/editer/",
            {
                "description": "Une description déjà écrite.",
                "image_de_couverture": SimpleUploadedFile(
                    "c.png", fabriquer_une_image(), content_type="image/png",
                ),
            },
        )

        self.base.refresh_from_db()
        self.assertEqual(self.base.description, "Une description déjà écrite.")
        self.assertTrue(self.base.image_de_couverture)

    def test_un_fichier_qui_n_est_pas_une_image_est_refuse(self):
        """
        `ImageField` valide le contenu, pas seulement l'extension. Sans
        cette verification, un fichier arbitraire finirait dans `media/`
        et la carte afficherait une image brisee.
        / Content is validated, not just the extension.
        """
        self.client.force_login(self.proprietaire)

        reponse = self.client.post(
            f"/bases/{self.base.slug}/editer/",
            {
                "description": "",
                "image_de_couverture": SimpleUploadedFile(
                    "piege.png", b"ceci n'est pas une image",
                    content_type="image/png",
                ),
            },
        )

        self.assertEqual(reponse.status_code, 400)
        self.base.refresh_from_db()
        self.assertFalse(self.base.image_de_couverture)

    # -------------------------------------------------------------------
    # Le point d'entree dans l'interface
    # / The entry point in the interface
    # -------------------------------------------------------------------

    def test_le_proprietaire_voit_le_formulaire_d_edition(self):
        """
        Un endpoint sans formulaire est aussi inaccessible que le champ
        qu'il remplit. Le geste doit exister A L'ECRAN.
        / An endpoint with no form is as unreachable as the field it fills.
        """
        self.client.force_login(self.proprietaire)

        reponse = self.client.get(f"/bases/{self.base.slug}/")
        contenu = reponse.content.decode()

        self.assertEqual(reponse.status_code, 200)
        self.assertIn("corpus-base-editer-form", contenu)
        self.assertIn("corpus-base-editer-description", contenu)
        self.assertIn("corpus-base-editer-couverture", contenu)

    def test_le_formulaire_accepte_un_fichier(self):
        """
        Un formulaire qui televerse doit etre en `multipart/form-data` :
        sans cet encodage, le fichier n'arrive jamais au serveur et
        l'echec est silencieux — la description passe, l'image non.
        / Without multipart encoding the file never reaches the server,
        and the failure is silent.
        """
        self.client.force_login(self.proprietaire)

        contenu = self.client.get(f"/bases/{self.base.slug}/").content.decode()

        bloc_du_formulaire = contenu.split("corpus-base-editer-form")[0][-600:]
        self.assertIn("multipart/form-data", bloc_du_formulaire)

    def test_un_passant_ne_voit_pas_le_formulaire(self):
        """
        Montrer un formulaire qu'on ne peut pas soumettre est une
        promesse non tenue. / Showing an unusable form is a broken promise.
        """
        self.client.force_login(self.passant)

        contenu = self.client.get(f"/bases/{self.base.slug}/").content.decode()

        self.assertNotIn("corpus-base-editer-form", contenu)

    # -------------------------------------------------------------------
    # Ce que les autres ne peuvent pas faire
    # / What others cannot do
    # -------------------------------------------------------------------

    def test_un_passant_ne_peut_pas_editer_la_base_d_un_autre(self):
        """
        La base est PUBLIQUE : elle se lit, elle ne s'ecrit pas pour
        autant. / Public means readable, not writable.
        """
        self.client.force_login(self.passant)

        reponse = self.client.post(
            f"/bases/{self.base.slug}/editer/",
            {"description": "Je passais par là."},
        )

        self.assertIn(reponse.status_code, (403, 404))
        self.base.refresh_from_db()
        self.assertEqual(self.base.description, "")

    def test_un_anonyme_ne_peut_pas_editer(self):
        """Sans compte, aucune ecriture."""
        reponse = self.client.post(
            f"/bases/{self.base.slug}/editer/",
            {"description": "Anonyme."},
        )

        self.assertIn(reponse.status_code, (302, 403, 404))
        self.base.refresh_from_db()
        self.assertEqual(self.base.description, "")

    def test_editer_une_base_privee_d_autrui_est_introuvable(self):
        """
        Doctrine du 404 : un 403 confirmerait l'existence d'une base
        privee a qui sonde des slugs.
        / 404, never 403: a 403 would confirm the base exists.
        """
        base_privee = BaseDeConnaissances.objects.create(
            nom="Base privée", slug="base-privee",
            owner=self.proprietaire, visibilite=VisibiliteDossier.PRIVE,
        )
        self.client.force_login(self.passant)

        reponse = self.client.post(
            f"/bases/{base_privee.slug}/editer/",
            {"description": "Sonde."},
        )

        self.assertEqual(reponse.status_code, 404)


class NomEtVisibiliteDUneBaseTest(TestCase):
    """
    Le nom et la visibilite d'une base, modifiables depuis le 15 aout.
    / A base's name and visibility, editable since 15 Aug.

    LOCALISATION : front/tests/test_edition_d_une_base.py

    POURQUOI CES DEUX CHAMPS ONT REJOINT LE FORMULAIRE

    Ils n'etaient atteignables NULLE PART. L'admin Django est ferme, et
    la creation d'une base est la seule occasion ou son nom s'ecrivait :
    une faute de frappe y devenait definitive. Sa visibilite, elle,
    restait a `prive` a jamais — une base ne pouvait pas s'ouvrir.
    Un carnet, lui, se renomme et change de visibilite depuis « Gerer ce
    carnet » ; les deux objets sont maintenant symetriques.
    / Neither field was reachable anywhere: a typo in a base's name was
    permanent and a base could never be opened up. A notebook already
    had both gestures.
    """

    def setUp(self):
        self.proprietaire = User.objects.create_user(
            username="proprietaire", password="motdepasse"
        )
        self.passant = User.objects.create_user(
            username="passant", password="motdepasse"
        )
        self.base = BaseDeConnaissances.objects.create(
            nom="Nom de départ",
            slug="nom-de-depart",
            owner=self.proprietaire,
            visibilite=VisibiliteDossier.PRIVE,
        )

    # -------------------------------------------------------------------
    # Le nom
    # / The name
    # -------------------------------------------------------------------

    def test_le_proprietaire_renomme_sa_base(self):
        self.client.force_login(self.proprietaire)

        reponse = self.client.post(
            f"/bases/{self.base.slug}/editer/", {"nom": "Nom corrigé"},
        )

        self.assertEqual(reponse.status_code, 200)
        self.base.refresh_from_db()
        self.assertEqual(self.base.nom, "Nom corrigé")

    def test_renommer_ne_change_pas_le_slug(self):
        """
        LE SLUG EST L'ADRESSE PUBLIQUE de la base. Le regenerer au
        renommage casserait toute URL deja partagee, sans redirection
        pour la rattraper. Ce test verrouille ce choix : le jour ou
        quelqu'un ajoutera un `slugify` ici, il saura ce qu'il casse.
        / The slug is the base's public address; regenerating it on
        rename would break every shared link with no redirect.
        """
        self.client.force_login(self.proprietaire)

        self.client.post(
            f"/bases/{self.base.slug}/editer/", {"nom": "Un tout autre nom"},
        )

        self.base.refresh_from_db()
        self.assertEqual(self.base.slug, "nom-de-depart")
        # L'ancienne adresse ouvre toujours la base.
        # / The old address still opens the base.
        self.assertEqual(
            self.client.get("/bases/nom-de-depart/").status_code, 200,
        )

    def test_un_nom_vide_est_refuse_et_n_ecrase_rien(self):
        self.client.force_login(self.proprietaire)

        reponse = self.client.post(f"/bases/{self.base.slug}/editer/", {"nom": "   "})

        self.assertEqual(reponse.status_code, 400)
        self.base.refresh_from_db()
        self.assertEqual(self.base.nom, "Nom de départ")

    def test_les_balises_html_sont_retirees_du_nom(self):
        """
        Le nom s'affiche dans la carte, le fil d'Ariane et le titre de
        page. Meme nettoyage que le renommage d'un carnet.
        / The name is displayed in three places; same cleaning as a
        notebook's rename.
        """
        self.client.force_login(self.proprietaire)

        self.client.post(
            f"/bases/{self.base.slug}/editer/",
            {"nom": "<script>alert(1)</script>Sans balise"},
        )

        self.base.refresh_from_db()
        self.assertNotIn("<script>", self.base.nom)

    # -------------------------------------------------------------------
    # La visibilite
    # / Visibility
    # -------------------------------------------------------------------

    def test_le_proprietaire_ouvre_sa_base_au_public(self):
        self.client.force_login(self.proprietaire)

        reponse = self.client.post(
            f"/bases/{self.base.slug}/editer/", {"visibilite": "public"},
        )

        self.assertEqual(reponse.status_code, 200)
        self.base.refresh_from_db()
        self.assertEqual(self.base.visibilite, VisibiliteDossier.PUBLIC)

    def test_une_visibilite_inventee_est_refusee(self):
        self.client.force_login(self.proprietaire)

        reponse = self.client.post(
            f"/bases/{self.base.slug}/editer/", {"visibilite": "secret"},
        )

        self.assertEqual(reponse.status_code, 400)
        self.base.refresh_from_db()
        self.assertEqual(self.base.visibilite, VisibiliteDossier.PRIVE)

    # -------------------------------------------------------------------
    # Ce qu'une soumission partielle ne doit PAS faire
    # / What a partial submission must NOT do
    # -------------------------------------------------------------------

    def test_changer_la_visibilite_seule_n_efface_ni_le_nom_ni_la_description(self):
        """
        La vue n'ecrit que les cles REELLEMENT presentes dans la
        soumission. Sans cette regle, un formulaire partiel viderait les
        champs qu'il ne montre pas.
        / The view writes only the keys actually submitted; otherwise a
        partial form would blank the fields it does not display.
        """
        self.base.description = "Une description à conserver."
        self.base.save(update_fields=["description"])
        self.client.force_login(self.proprietaire)

        self.client.post(f"/bases/{self.base.slug}/editer/", {"visibilite": "public"})

        self.base.refresh_from_db()
        self.assertEqual(self.base.nom, "Nom de départ")
        self.assertEqual(self.base.description, "Une description à conserver.")

    # -------------------------------------------------------------------
    # Les permissions
    # / Permissions
    # -------------------------------------------------------------------

    def test_un_passant_ne_renomme_pas_la_base_d_un_autre(self):
        """Une base publique se lit ; elle ne se renomme pas pour autant."""
        self.base.visibilite = VisibiliteDossier.PUBLIC
        self.base.save(update_fields=["visibilite"])
        self.client.force_login(self.passant)

        reponse = self.client.post(
            f"/bases/{self.base.slug}/editer/", {"nom": "Détourné"},
        )

        self.assertIn(reponse.status_code, (403, 404))
        self.base.refresh_from_db()
        self.assertEqual(self.base.nom, "Nom de départ")

    # -------------------------------------------------------------------
    # Le formulaire a l'ecran
    # / The form on screen
    # -------------------------------------------------------------------

    def test_le_formulaire_montre_les_deux_nouveaux_champs(self):
        """
        Un endpoint sans champ a l'ecran est aussi inatteignable que le
        champ qu'il remplit. / An endpoint with no on-screen field is as
        unreachable as the field it fills.
        """
        self.client.force_login(self.proprietaire)

        contenu = self.client.get(f"/bases/{self.base.slug}/").content.decode()

        self.assertIn("corpus-base-editer-nom", contenu)
        self.assertIn("corpus-base-editer-visibilite", contenu)
        # Les trois niveaux sont proposes, pas seulement celui en cours.
        # / All three levels offered, not just the current one.
        for valeur in ("prive", "partage", "public"):
            self.assertIn(f"corpus-base-visibilite-choix-{valeur}", contenu)

    def test_le_champ_nom_est_pre_rempli(self):
        """
        On voit le nom actuel pendant qu'on tape le nouveau — un champ
        vide obligerait a le retaper de memoire.
        / A blank field would force retyping the name from memory.
        """
        self.client.force_login(self.proprietaire)

        contenu = self.client.get(f"/bases/{self.base.slug}/").content.decode()

        self.assertIn('value="Nom de départ"', contenu)

    def test_le_niveau_en_cours_est_coche(self):
        self.client.force_login(self.proprietaire)

        contenu = self.client.get(f"/bases/{self.base.slug}/").content.decode()

        bloc_du_niveau_prive = contenu.split('value="prive"')[1][:200]
        self.assertIn("checked", bloc_du_niveau_prive)


class CreationDUneBaseTest(TestCase):
    """
    La creation d'une base : le nom, et rien d'autre.
    / Creating a base: the name, and nothing else.

    LOCALISATION : front/tests/test_edition_d_une_base.py

    POURQUOI LA CREATION RESTE MINIMALE

    Elle vit dans une CELLULE DE LA GRILLE des bases, a cote des cartes :
    un televersement d'image et un bloc de trois choix y feraient eclater
    la maille. Et au moment ou l'on cree une base, on ne sait pas encore
    quoi ecrire dans sa description. Un carnet se cree de la meme facon.
    / Creation lives in a grid cell beside the cards; a description
    written before the base has content is a field everyone skips.
    """

    def setUp(self):
        self.utilisateur = User.objects.create_user(
            username="createur", password="motdepasse"
        )

    def test_creer_une_base_avec_un_nom(self):
        self.client.force_login(self.utilisateur)

        reponse = self.client.post("/bases/", {"nom": "Réseau des tiers-lieux"})

        self.assertEqual(reponse.status_code, 200)
        base_creee = BaseDeConnaissances.objects.get(nom="Réseau des tiers-lieux")
        self.assertEqual(base_creee.owner, self.utilisateur)
        self.assertEqual(base_creee.slug, "reseau-des-tiers-lieux")

    def test_un_nom_vide_ne_cree_rien(self):
        self.client.force_login(self.utilisateur)

        reponse = self.client.post("/bases/", {"nom": "   "})

        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(BaseDeConnaissances.objects.count(), 0)

    def test_les_balises_html_sont_retirees_du_nom_a_la_creation(self):
        """
        La creation passe par un serializer, comme le renommage : sans
        lui, le nom entrait en base tel quel.
        / Creation goes through a serializer, like the rename does.
        """
        self.client.force_login(self.utilisateur)

        self.client.post("/bases/", {"nom": "<b>Gras</b>"})

        base_creee = BaseDeConnaissances.objects.first()
        self.assertNotIn("<b>", base_creee.nom)

    def test_deux_bases_de_meme_nom_ont_des_slugs_distincts(self):
        self.client.force_login(self.utilisateur)

        self.client.post("/bases/", {"nom": "Doublon"})
        self.client.post("/bases/", {"nom": "Doublon"})

        slugs = sorted(BaseDeConnaissances.objects.values_list("slug", flat=True))
        self.assertEqual(slugs, ["doublon", "doublon-2"])

    def test_un_anonyme_ne_cree_pas_de_base(self):
        reponse = self.client.post("/bases/", {"nom": "Anonyme"})

        self.assertIn(reponse.status_code, (302, 403, 404))
        self.assertEqual(BaseDeConnaissances.objects.count(), 0)

    def test_la_base_creee_est_signalee_dans_la_grille(self):
        """
        La grille est rangee PAR NOM : une base creee atterrit a sa place
        alphabetique, pas sous les yeux de qui vient de cliquer
        « Creer ». Sur une dizaine de bases, il faut la chercher.
        / The grid is sorted by name, so a new base lands alphabetically
        rather than where the eye returns after clicking.
        """
        self.client.force_login(self.utilisateur)
        BaseDeConnaissances.objects.create(
            nom="Antérieure", slug="anterieure", owner=self.utilisateur,
        )

        contenu = self.client.post("/bases/", {"nom": "Zoulou"}).content.decode()

        self.assertIn('class="carte-base est-nouvelle"', contenu)
        # UNE seule carte marquee : la marque designe, elle ne decore pas.
        # / Exactly one card marked: it points, it does not decorate.
        self.assertEqual(contenu.count('class="carte-base est-nouvelle"'), 1)

    def test_une_simple_consultation_ne_marque_aucune_carte(self):
        """
        Sans cette garde, toute visite de `/bases/` rallumerait l'eclat
        et il cesserait de vouloir dire « celle-ci vient d'arriver ».
        / Otherwise every visit would re-fire the highlight.
        """
        self.client.force_login(self.utilisateur)
        BaseDeConnaissances.objects.create(
            nom="Deja la", slug="deja-la", owner=self.utilisateur,
        )

        contenu = self.client.get("/bases/").content.decode()

        self.assertNotIn('class="carte-base est-nouvelle"', contenu)

    def test_le_champ_de_creation_est_obligatoire_a_l_ecran(self):
        """
        La validation serveur refuse deja un nom vide ; `required`
        evite l'aller-retour et signale le champ AVANT la soumission.
        / Server-side validation already refuses a blank name; required
        avoids the round-trip and flags the field before submission.
        """
        self.client.force_login(self.utilisateur)

        contenu = self.client.get("/bases/").content.decode()

        bloc_du_champ = contenu.split("corpus-base-creer-nom")[0][-300:]
        self.assertIn("required", bloc_du_champ)


class SuppressionDUneBaseTest(TestCase):
    """
    Supprimer une base ne supprime pas ses carnets.
    / Deleting a base does not delete its notebooks.

    LOCALISATION : front/tests/test_edition_d_une_base.py

    CE QUE CES TESTS PROTEGENT

    Le niveau « base » est FACULTATIF dans le modele : un carnet vit tres
    bien sans base (core/models.py, BaseDeConnaissances). Supprimer une
    base ne doit donc defaire QUE l'appartenance — le carnet ressort au
    niveau plateforme, la ou `/carnets/` le montre. Un `on_delete` mal
    pose ferait disparaitre le travail de quelqu'un avec le contenant.

    Ses AXES DE CLASSEMENT, eux, partent avec elle : ils ne decrivent
    que cette base. Le libelle de confirmation annonce les deux, et un
    test verifie qu'il le fait — une confirmation qui n'enonce pas la
    perte ne protege de rien.
    / A notebook lives fine without a base, so deletion must only undo
    the membership. The base's own axes go with it, and the confirmation
    text must say both.
    """

    def setUp(self):
        self.proprietaire = User.objects.create_user(
            username="proprietaire", password="motdepasse"
        )
        self.passant = User.objects.create_user(
            username="passant", password="motdepasse"
        )
        self.base = BaseDeConnaissances.objects.create(
            nom="Base à supprimer",
            slug="base-a-supprimer",
            owner=self.proprietaire,
            visibilite=VisibiliteDossier.PUBLIC,
        )

    def _ranger_un_carnet_dans_la_base(self):
        from core.models import AppartenanceDossierBase, Dossier

        carnet = Dossier.objects.create(
            name="Carnet rangé dedans", owner=self.proprietaire,
            visibilite=VisibiliteDossier.PRIVE,
        )
        AppartenanceDossierBase.objects.create(base=self.base, dossier=carnet)
        return carnet

    # -------------------------------------------------------------------
    # Ce que la suppression fait, et ne fait pas
    # / What deletion does, and does not do
    # -------------------------------------------------------------------

    def test_le_proprietaire_supprime_sa_base(self):
        self.client.force_login(self.proprietaire)

        reponse = self.client.delete(f"/bases/{self.base.slug}/")

        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(
            BaseDeConnaissances.objects.filter(slug="base-a-supprimer").exists()
        )

    def test_les_carnets_survivent_a_la_suppression(self):
        """Le coeur de l'affaire : on detruit un contenant, pas du contenu."""
        from core.models import Dossier

        carnet = self._ranger_un_carnet_dans_la_base()
        self.client.force_login(self.proprietaire)

        self.client.delete(f"/bases/{self.base.slug}/")

        self.assertTrue(Dossier.objects.filter(pk=carnet.pk).exists())

    def test_le_carnet_ressort_au_niveau_plateforme(self):
        """
        Il ne suffit pas qu'il existe encore : il doit rester ATTEIGNABLE.
        / Existing is not enough — it must stay reachable.
        """
        carnet = self._ranger_un_carnet_dans_la_base()
        self.client.force_login(self.proprietaire)

        self.client.delete(f"/bases/{self.base.slug}/")
        contenu = self.client.get("/carnets/").content.decode()

        self.assertIn("Carnet rangé dedans", contenu)
        self.assertEqual(
            self.client.get(f"/carnets/{carnet.pk}/").status_code, 200,
        )

    def test_les_axes_de_la_base_partent_avec_elle(self):
        from core.models import ListeDeCategories

        ListeDeCategories.objects.create(base=self.base, nom="Un axe")
        self.client.force_login(self.proprietaire)

        self.client.delete(f"/bases/{self.base.slug}/")

        self.assertFalse(ListeDeCategories.objects.filter(nom="Un axe").exists())

    def test_la_suppression_annonce_ce_qu_elle_a_fait(self):
        """
        Sans retour, on ne distingue pas « supprimee » de « le clic n'a
        pas pris ». / Without feedback, deleted looks like nothing happened.
        """
        self.client.force_login(self.proprietaire)

        reponse = self.client.delete(f"/bases/{self.base.slug}/")

        # L'entete est du JSON : `json.dumps` y echappe les accents en
        # `\uXXXX`, donc on decode avant de chercher le nom.
        # / The header is JSON, which escapes accents: decode first.
        import json

        message = json.loads(reponse.headers["HX-Trigger"])["showToast"]["message"]
        self.assertIn("Base à supprimer", message)

    # -------------------------------------------------------------------
    # Les permissions
    # / Permissions
    # -------------------------------------------------------------------

    def test_un_passant_ne_supprime_pas_la_base_d_un_autre(self):
        """La base est PUBLIQUE : elle se lit, elle ne se detruit pas."""
        self.client.force_login(self.passant)

        reponse = self.client.delete(f"/bases/{self.base.slug}/")

        self.assertIn(reponse.status_code, (403, 404))
        self.assertTrue(
            BaseDeConnaissances.objects.filter(slug="base-a-supprimer").exists()
        )

    def test_un_anonyme_ne_supprime_pas(self):
        reponse = self.client.delete(f"/bases/{self.base.slug}/")

        self.assertIn(reponse.status_code, (302, 403, 404))
        self.assertTrue(
            BaseDeConnaissances.objects.filter(slug="base-a-supprimer").exists()
        )

    def test_supprimer_une_base_privee_d_autrui_est_introuvable(self):
        """Doctrine du 404 : un 403 confirmerait qu'elle existe."""
        base_privee = BaseDeConnaissances.objects.create(
            nom="Base privée", slug="base-privee-a-sonder",
            owner=self.proprietaire, visibilite=VisibiliteDossier.PRIVE,
        )
        self.client.force_login(self.passant)

        reponse = self.client.delete(f"/bases/{base_privee.slug}/")

        self.assertEqual(reponse.status_code, 404)

    # -------------------------------------------------------------------
    # Le geste a l'ecran
    # / The gesture on screen
    # -------------------------------------------------------------------

    def test_le_proprietaire_voit_le_bouton_de_suppression(self):
        self.client.force_login(self.proprietaire)

        contenu = self.client.get(f"/bases/{self.base.slug}/").content.decode()

        self.assertIn("corpus-base-supprimer", contenu)

    def test_un_passant_ne_voit_pas_le_bouton_de_suppression(self):
        self.client.force_login(self.passant)

        contenu = self.client.get(f"/bases/{self.base.slug}/").content.decode()

        self.assertNotIn("corpus-base-supprimer", contenu)

    def test_la_confirmation_dit_ce_qui_survit_et_ce_qui_part(self):
        """
        « Etes-vous sur ? » ne renseigne sur rien. La question doit
        enoncer le sort des carnets ET celui des axes, sinon la personne
        decouvre la perte apres coup.
        / A bare "are you sure?" informs nobody: the question must state
        what survives and what does not.
        """
        self.client.force_login(self.proprietaire)

        contenu = self.client.get(f"/bases/{self.base.slug}/").content.decode()

        debut = contenu.find("corpus-base-supprimer")
        bloc = contenu[max(0, debut - 700):debut]
        self.assertIn("hx-confirm", bloc)
        self.assertIn("carnets ne sont pas supprimés", bloc)
        self.assertIn("axes de classement", bloc)

    def test_le_bouton_de_suppression_est_hors_du_formulaire(self):
        """
        Dans le `<form>`, il se soumettrait au clavier comme n'importe
        quel bouton. Il doit en etre le frere, pas l'enfant.
        / Inside the form it would submit like any other button.
        """
        self.client.force_login(self.proprietaire)

        contenu = self.client.get(f"/bases/{self.base.slug}/").content.decode()

        entre_les_deux = contenu[
            contenu.find("corpus-base-editer-bouton"):
            contenu.find("corpus-base-supprimer")
        ]
        self.assertIn("</form>", entre_les_deux)


class RetourApresEnregistrementTest(TestCase):
    """
    Enregistrer sans retour est muet : la reponse re-rend la page et le
    panneau se replie, si bien qu'a l'oeil rien ne distingue « c'est
    enregistre » de « le clic n'a pas pris ».
    / A silent save is indistinguishable from a click that never landed.

    LOCALISATION : front/tests/test_edition_d_une_base.py
    """

    def setUp(self):
        self.proprietaire = User.objects.create_user(
            username="proprietaire", password="motdepasse"
        )
        self.base = BaseDeConnaissances.objects.create(
            nom="Base", slug="base-retour", owner=self.proprietaire,
            visibilite=VisibiliteDossier.PRIVE,
        )
        self.client.force_login(self.proprietaire)

    def test_enregistrer_declenche_un_toast(self):
        reponse = self.client.post(
            f"/bases/{self.base.slug}/editer/", {"description": "Neuve."},
        )

        self.assertIn("showToast", reponse.headers.get("HX-Trigger", ""))

    def test_une_soumission_qui_ne_change_rien_reste_silencieuse(self):
        """
        Un toast sans changement annoncerait un enregistrement qui n'a
        pas eu lieu. / A toast with no change would announce a save that
        never happened.
        """
        reponse = self.client.post(f"/bases/{self.base.slug}/editer/", {})

        self.assertNotIn("showToast", reponse.headers.get("HX-Trigger", ""))
