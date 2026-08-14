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
