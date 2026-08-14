"""
Tests des textes de presentation poses par `charger_fixtures_sample`.
/ Tests for the presentation texts set by `charger_fixtures_sample`.

LOCALISATION : front/tests/test_textes_des_fixtures.py

POURQUOI CES TESTS EXISTENT

Le carnet et la base etalons etaient crees SANS description ni guide de
redaction. Les ecrans qui les affichent — la liste des carnets, le detail
d'un carnet, la future liste des bases en cartes — avaient donc raison de
paraitre vides : il n'y avait rien a montrer. On ne peut pas mettre au
point une carte de presentation sur un objet sans texte de presentation.

Ces tests verrouillent deux choses que le mainteneur a demandees le
12 aout : que les textes soient POSES, et qu'ils ne soient JAMAIS
ecrases une fois qu'une personne les a ecrits elle-meme.
/ The reference notebook and base had no description: the screens showing
them were right to look empty. Texts must be set, and never overwritten.
"""

from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from core.models import (
    AppartenancePageDossier,
    BaseDeConnaissances,
    CategorieDossier,
    Dossier,
    ListeDeCategories,
    Page,
)
from front.management.commands.charger_fixtures_sample import (
    AXES_DE_CLASSEMENT_DU_CARNET,
    FICHIER_DE_LA_CAPTURE,
    DESCRIPTION_DE_LA_BASE_DE_DEMONSTRATION,
    DESCRIPTION_DU_CARNET,
    GUIDE_DE_REDACTION_DU_CARNET,
    NOM_DE_LA_BASE_DE_DEMONSTRATION,
    NOM_DU_CARNET,
)

# La commande charge six documents dont deux PDF passes a Docling : 3 min,
# plusieurs Gio, et un appel Voxtral facture. Ces tests ne parlent que des
# textes de presentation — on neutralise l'ingestion.
# / The command runs Docling and a paid Voxtral call; these tests are only
# about presentation texts, so ingestion is neutralised.
CHARGEMENT_DES_DOCUMENTS = (
    "front.management.commands.charger_fixtures_sample."
    "Command._charger_les_documents"
)


class TextesDesFixturesTest(TestCase):
    """
    LOCALISATION : front/tests/test_textes_des_fixtures.py
    """

    def charger_les_fixtures(self):
        """Lance la commande sans son ingestion. / Run it without ingestion."""
        sortie = StringIO()
        with patch(CHARGEMENT_DES_DOCUMENTS):
            call_command("charger_fixtures_sample", stdout=sortie)
        return sortie.getvalue()

    # -------------------------------------------------------------------
    # Les textes sont poses
    # / The texts are set
    # -------------------------------------------------------------------

    def test_le_carnet_porte_une_description(self):
        """Sans elle, la liste des carnets n'a qu'un nom a afficher."""
        self.charger_les_fixtures()

        carnet = Dossier.objects.get(name=NOM_DU_CARNET)

        self.assertTrue(carnet.description.strip())
        self.assertEqual(carnet.description, DESCRIPTION_DU_CARNET)

    def test_la_description_du_carnet_tient_dans_le_champ(self):
        """
        `Dossier.description` est un CharField(max_length=200). Un texte
        plus long serait tronque par la base — sur PostgreSQL, il leve.
        / The field caps at 200 characters; PostgreSQL raises beyond.
        """
        self.assertLessEqual(len(DESCRIPTION_DU_CARNET), 200)

    def test_le_carnet_porte_un_guide_de_redaction(self):
        """
        L'etalon (corpus.html) montre ce guide EN TETE du carnet, encadre :
        il s'adresse au contributeur au moment ou il contribue.
        / The mockup shows this guide at the top of the notebook.
        """
        self.charger_les_fixtures()

        carnet = Dossier.objects.get(name=NOM_DU_CARNET)

        self.assertTrue(carnet.guide_de_redaction.strip())
        self.assertEqual(carnet.guide_de_redaction, GUIDE_DE_REDACTION_DU_CARNET)

    def test_la_base_porte_une_description(self):
        """La carte d'une base sans description n'a que son nom."""
        self.charger_les_fixtures()

        base = BaseDeConnaissances.objects.get(
            nom=NOM_DE_LA_BASE_DE_DEMONSTRATION
        )

        self.assertTrue(base.description.strip())
        self.assertEqual(base.description, DESCRIPTION_DE_LA_BASE_DE_DEMONSTRATION)

    # -------------------------------------------------------------------
    # Les axes de classement
    # / The classification axes
    # -------------------------------------------------------------------

    def test_le_carnet_porte_ses_axes_de_classement(self):
        """
        L'etalon (corpus.html) montre les axes en facettes cliquables au
        haut du carnet : « TYPE (4) · THEME (3) · ECHEANCE (2) ». Sans
        axe en base, cette rangee reste vide et l'ecran ne peut pas etre
        compare a l'etalon — ni meme mis au point.
        / The mockup shows classification axes as clickable facets; with
        none in the database that row stays empty.
        """
        self.charger_les_fixtures()

        carnet = Dossier.objects.get(name=NOM_DU_CARNET)
        axes = ListeDeCategories.objects.filter(dossier=carnet)

        self.assertEqual(axes.count(), len(AXES_DE_CLASSEMENT_DU_CARNET))
        for nom_de_l_axe, categories_attendues in AXES_DE_CLASSEMENT_DU_CARNET.items():
            axe = axes.get(nom=nom_de_l_axe)
            noms_des_categories = set(
                axe.categories_de_dossier.values_list("nom", flat=True)
            )
            self.assertEqual(noms_des_categories, set(categories_attendues))

    def test_chaque_categorie_porte_une_couleur(self):
        """
        L'etalon teinte ses pastilles. Une categorie sans couleur retombe
        au filet gris et la facette perd sa lisibilite d'un coup d'oeil.
        / A colourless category falls back to grey and the facet loses
        its at-a-glance readability.
        """
        self.charger_les_fixtures()

        carnet = Dossier.objects.get(name=NOM_DU_CARNET)
        for axe in ListeDeCategories.objects.filter(dossier=carnet):
            for categorie in axe.categories_de_dossier.all():
                self.assertRegex(
                    categorie.couleur,
                    r"^#[0-9a-fA-F]{6}$",
                    f"« {categorie.nom} » n'a pas de couleur valide.",
                )

    def test_une_note_etalon_est_reellement_classee(self):
        """
        Des axes sans note classee dessous donnent des facettes qui ne
        filtrent rien : « 0 sur 6 » quel que soit le clic. Une facette
        qui ne filtre pas ne montre pas le mecanisme, elle montre un bug.

        Le decor neutralise le chargement des six documents (Docling :
        3 min et plusieurs Gio). On pose donc soi-meme une note portant
        le nom de fichier d'un etalon, et on relance : c'est exactement
        le chemin qu'emprunte une installation ou les documents sont
        deja la.
        / Ingestion is neutralised here, so we file one note ourselves
        and re-run — the same path as an install where documents exist.
        """
        self.charger_les_fixtures()
        carnet = Dossier.objects.get(name=NOM_DU_CARNET)

        note_de_la_capture = Page.objects.create(
            title="Badgeons la Normandie",
            url="https://exemple.test/badgeons",
            original_filename=FICHIER_DE_LA_CAPTURE,
        )
        appartenance = AppartenancePageDossier.objects.create(
            page=note_de_la_capture, dossier=carnet,
        )

        self.charger_les_fixtures()

        appartenance.refresh_from_db()
        noms_des_categories = set(
            appartenance.categories.values_list("nom", flat=True)
        )
        self.assertEqual(noms_des_categories, {"Web", "Structure"})

    def test_un_classement_pose_a_la_main_n_est_pas_refait(self):
        """
        Meme regle que pour les textes : la commande se relance a chaque
        installation et ne doit pas defaire un rangement humain.
        / The command re-runs on every install and must not undo a
        hand-made filing.
        """
        self.charger_les_fixtures()
        carnet = Dossier.objects.get(name=NOM_DU_CARNET)
        note = Page.objects.create(
            title="Note rangée à la main",
            url="https://exemple.test/rangee-main",
            original_filename=FICHIER_DE_LA_CAPTURE,
        )
        appartenance = AppartenancePageDossier.objects.create(
            page=note, dossier=carnet,
        )
        categorie_choisie = CategorieDossier.objects.get(
            liste__dossier=carnet, nom="Audio",
        )
        appartenance.categories.set([categorie_choisie])

        self.charger_les_fixtures()

        appartenance.refresh_from_db()
        self.assertEqual(
            set(appartenance.categories.values_list("nom", flat=True)),
            {"Audio"},
        )

    def test_relancer_la_commande_ne_duplique_pas_les_axes(self):
        """La commande se relance a chaque installation."""
        self.charger_les_fixtures()
        self.charger_les_fixtures()

        carnet = Dossier.objects.get(name=NOM_DU_CARNET)

        self.assertEqual(
            ListeDeCategories.objects.filter(dossier=carnet).count(),
            len(AXES_DE_CLASSEMENT_DU_CARNET),
        )

    # -------------------------------------------------------------------
    # Ce qu'une personne a ecrit lui appartient
    # / What a person wrote belongs to them
    # -------------------------------------------------------------------

    def test_une_description_ecrite_a_la_main_n_est_pas_ecrasee(self):
        """
        La commande est IDEMPOTENTE et se relance a chaque installation.
        Si elle reimposait ses textes, elle effacerait a chaque fois ce
        que le mainteneur aurait ecrit. Elle ne remplit que le vide.
        / The command re-runs on every install: it fills blanks, never
        overwrites what someone wrote.
        """
        self.charger_les_fixtures()
        carnet = Dossier.objects.get(name=NOM_DU_CARNET)
        carnet.description = "Ma propre description."
        carnet.guide_de_redaction = "Mes propres consignes."
        carnet.save(update_fields=["description", "guide_de_redaction"])

        self.charger_les_fixtures()

        carnet.refresh_from_db()
        self.assertEqual(carnet.description, "Ma propre description.")
        self.assertEqual(carnet.guide_de_redaction, "Mes propres consignes.")

    def test_une_description_de_base_ecrite_a_la_main_n_est_pas_ecrasee(self):
        """Meme regle pour la base. / Same rule for the base."""
        self.charger_les_fixtures()
        base = BaseDeConnaissances.objects.get(
            nom=NOM_DE_LA_BASE_DE_DEMONSTRATION
        )
        base.description = "Ma propre présentation."
        base.save(update_fields=["description"])

        self.charger_les_fixtures()

        base.refresh_from_db()
        self.assertEqual(base.description, "Ma propre présentation.")

    def test_un_carnet_deja_present_mais_vide_est_complete(self):
        """
        Le cas de la base de dev : le carnet existe depuis des semaines,
        sans description. `get_or_create(defaults=...)` ne remplit que
        les objets qu'il CREE — l'existant serait reste vide pour
        toujours. / get_or_create's defaults never touch existing rows.
        """
        self.charger_les_fixtures()
        carnet = Dossier.objects.get(name=NOM_DU_CARNET)
        carnet.description = ""
        carnet.guide_de_redaction = ""
        carnet.save(update_fields=["description", "guide_de_redaction"])

        self.charger_les_fixtures()

        carnet.refresh_from_db()
        self.assertEqual(carnet.description, DESCRIPTION_DU_CARNET)
        self.assertEqual(carnet.guide_de_redaction, GUIDE_DE_REDACTION_DU_CARNET)
