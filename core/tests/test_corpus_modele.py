"""
Tests des modeles de la couche corpus (phases A et B).
/ Corpus layer model tests (phases A and B).

LOCALISATION : core/tests/test_corpus_modele.py

Ces tests couvrent la SPEC-corpus-base-carnet-note.md v1.1 § 3 :
les deux tables de liaison, les listes de categories, les contraintes
d'unicite, le champ Dossier.role_special (§ 6.3), et la validation
applicative des categories (§ 3.4 — serializer + signaux m2m_changed,
classes ValidationDesCategories*Test).
/ Includes § 3.4 category validation (serializer + m2m_changed signals).
"""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from core.models import (
    AppartenanceDossierBase,
    AppartenancePageDossier,
    BaseDeConnaissances,
    CategorieBase,
    CategorieDossier,
    Dossier,
    ListeDeCategories,
    Page,
    RoleSpecialDossier,
)

Utilisateur = get_user_model()


def creer_une_page(url_unique):
    """
    Cree une page minimale pour les tests.
    / Creates a minimal page for tests.
    """
    return Page.objects.create(
        url=url_unique,
        html_original="<p>original</p>",
        html_readability="<p>lisible</p>",
        text_readability="texte de la note",
        content_hash=f"hash-{url_unique}",
    )


class AppartenancePageDossierTest(TestCase):
    """La table de liaison note <-> carnet. / The note <-> notebook link table."""

    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            username="jonas_test", password="motdepasse"
        )
        self.carnet_conseil = Dossier.objects.create(
            name="Conseil d'administration", owner=self.utilisateur
        )
        self.carnet_veille = Dossier.objects.create(
            name="Veille financement", owner=self.utilisateur
        )
        self.note = creer_une_page("http://exemple.local/cr-conseil-12-mars")

    def test_une_note_dans_deux_carnets(self):
        # Une meme note rattachee a deux carnets : deux lignes de liaison,
        # aucune duplication de Page.
        # / Same note in two notebooks: two link rows, no Page duplication.
        AppartenancePageDossier.objects.create(
            page=self.note, dossier=self.carnet_conseil,
            integree_par=self.utilisateur,
        )
        AppartenancePageDossier.objects.create(
            page=self.note, dossier=self.carnet_veille,
            integree_par=self.utilisateur,
        )

        self.assertEqual(Page.objects.count(), 1)
        self.assertEqual(self.note.appartenances_dossiers.count(), 2)
        self.assertEqual(self.carnet_conseil.appartenances_pages.count(), 1)
        self.assertEqual(self.carnet_veille.appartenances_pages.count(), 1)

    def test_unicite_page_dans_un_dossier(self):
        # La meme note ne peut pas etre rattachee deux fois au meme carnet.
        # / The same note cannot be linked twice to the same notebook.
        AppartenancePageDossier.objects.create(
            page=self.note, dossier=self.carnet_conseil,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AppartenancePageDossier.objects.create(
                    page=self.note, dossier=self.carnet_conseil,
                )

    def test_categories_differentes_selon_le_carnet(self):
        # La meme note porte [Budget] dans un carnet et [Subvention] dans
        # l'autre : la categorie appartient a la RELATION, pas a la note.
        # / The category belongs to the RELATION, not to the note.
        liste_conseil = ListeDeCategories.objects.create(
            nom="Type", dossier=self.carnet_conseil,
        )
        liste_veille = ListeDeCategories.objects.create(
            nom="Type", dossier=self.carnet_veille,
        )
        categorie_budget = CategorieDossier.objects.create(
            liste=liste_conseil, nom="Budget",
        )
        categorie_subvention = CategorieDossier.objects.create(
            liste=liste_veille, nom="Subvention",
        )

        appartenance_conseil = AppartenancePageDossier.objects.create(
            page=self.note, dossier=self.carnet_conseil,
        )
        appartenance_veille = AppartenancePageDossier.objects.create(
            page=self.note, dossier=self.carnet_veille,
        )
        appartenance_conseil.categories.add(categorie_budget)
        appartenance_veille.categories.add(categorie_subvention)

        noms_dans_le_conseil = list(
            appartenance_conseil.categories.values_list("nom", flat=True)
        )
        noms_dans_la_veille = list(
            appartenance_veille.categories.values_list("nom", flat=True)
        )
        self.assertEqual(noms_dans_le_conseil, ["Budget"])
        self.assertEqual(noms_dans_la_veille, ["Subvention"])

    def test_l_ordre_du_carnet_respecte_epinglage_puis_ordre_manuel(self):
        # Le tri par defaut : epinglees d'abord, puis ordre manuel,
        # puis plus recente integration.
        # / Default ordering: pinned first, then manual order, then newest.
        note_ancienne = creer_une_page("http://exemple.local/note-ancienne")
        note_epinglee = creer_une_page("http://exemple.local/note-epinglee")

        appartenance_ordinaire = AppartenancePageDossier.objects.create(
            page=note_ancienne, dossier=self.carnet_conseil,
        )
        appartenance_epinglee = AppartenancePageDossier.objects.create(
            page=note_epinglee, dossier=self.carnet_conseil, epinglee=True,
        )

        appartenances_triees = list(
            self.carnet_conseil.appartenances_pages.all()
        )
        self.assertEqual(
            appartenances_triees,
            [appartenance_epinglee, appartenance_ordinaire],
        )


class AppartenanceDossierBaseTest(TestCase):
    """La table de liaison carnet <-> base. / The notebook <-> base link table."""

    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            username="reseau_test", password="motdepasse"
        )
        self.base = BaseDeConnaissances.objects.create(
            nom="Réseau des tiers-lieux d'Occitanie",
            slug="reseau-tiers-lieux-occitanie",
            owner=self.utilisateur,
        )
        self.carnet = Dossier.objects.create(
            name="Veille financement", owner=self.utilisateur
        )

    def test_un_carnet_dans_deux_bases(self):
        autre_base = BaseDeConnaissances.objects.create(
            nom="Réseau national", slug="reseau-national",
        )
        AppartenanceDossierBase.objects.create(
            dossier=self.carnet, base=self.base,
        )
        AppartenanceDossierBase.objects.create(
            dossier=self.carnet, base=autre_base,
        )
        self.assertEqual(self.carnet.appartenances_bases.count(), 2)

    def test_unicite_dossier_dans_une_base(self):
        AppartenanceDossierBase.objects.create(
            dossier=self.carnet, base=self.base,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AppartenanceDossierBase.objects.create(
                    dossier=self.carnet, base=self.base,
                )

    def test_carnet_sans_base_est_valide(self):
        # Le niveau base est FACULTATIF : un carnet vit tres bien sans base.
        # / The base level is OPTIONAL.
        self.assertEqual(self.carnet.appartenances_bases.count(), 0)
        # Aucune contrainte ne force la creation d'une appartenance.
        self.carnet.full_clean()


class ListeDeCategoriesTest(TestCase):
    """Les axes de classement et leurs contraintes. / Classification axes."""

    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            username="classeur_test", password="motdepasse"
        )
        self.carnet = Dossier.objects.create(
            name="Veille", owner=self.utilisateur
        )
        self.base = BaseDeConnaissances.objects.create(
            nom="Base de test", slug="base-de-test",
        )

    def test_liste_appartient_a_un_seul_contenant_jamais_les_deux(self):
        # Une liste rattachee a la fois a un carnet ET a une base viole la
        # contrainte en base de donnees.
        # / A list attached to both a notebook AND a base violates the
        # database constraint.
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ListeDeCategories.objects.create(
                    nom="Type", dossier=self.carnet, base=self.base,
                )

    def test_liste_sans_aucun_contenant_est_refusee(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ListeDeCategories.objects.create(nom="Type")

    def test_deplacer_une_liste_est_refuse(self):
        # Le contenant d'une liste est fixe a la creation : le changer
        # rendrait incoherentes les categorisations deja posees.
        # / A list's container is fixed at creation.
        autre_carnet = Dossier.objects.create(
            name="Autre carnet", owner=self.utilisateur
        )
        liste = ListeDeCategories.objects.create(
            nom="Type", dossier=self.carnet,
        )

        liste.dossier = autre_carnet
        with self.assertRaises(ValidationError):
            liste.clean()

    def test_basculer_une_liste_de_carnet_vers_base_est_refuse(self):
        liste = ListeDeCategories.objects.create(
            nom="Type", dossier=self.carnet,
        )
        liste.dossier = None
        liste.base = self.base
        with self.assertRaises(ValidationError):
            liste.clean()

    def test_unicite_du_nom_de_categorie_dans_une_liste(self):
        liste = ListeDeCategories.objects.create(
            nom="Type", dossier=self.carnet,
        )
        CategorieDossier.objects.create(liste=liste, nom="Subvention")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CategorieDossier.objects.create(liste=liste, nom="Subvention")

    def test_le_carnet_d_une_categorie_se_lit_via_sa_liste(self):
        # Pas de champ dossier denormalise sur CategorieDossier : le carnet
        # se lit via la liste (spec § 3.3, correction n°4 de la v1.1).
        # / No denormalized dossier field: read the notebook via the list.
        liste = ListeDeCategories.objects.create(
            nom="Type", dossier=self.carnet,
        )
        categorie = CategorieDossier.objects.create(liste=liste, nom="Prix")
        self.assertEqual(categorie.dossier_id, self.carnet.pk)

    def test_la_base_d_une_categorie_de_base_se_lit_via_sa_liste(self):
        liste = ListeDeCategories.objects.create(
            nom="Territoire", base=self.base,
        )
        categorie = CategorieBase.objects.create(liste=liste, nom="Régional")
        self.assertEqual(categorie.base_id, self.base.pk)


class ValidationDesCategoriesTest(TestCase):
    """
    La validation qui n'a pas le droit de manquer (SPEC-corpus § 3.4) :
    une categorie appliquee doit venir du carnet de l'appartenance.
    / The validation that must not be missing: an applied category must
    come from the membership's notebook.
    """

    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            username="valideur_test", password="motdepasse"
        )
        self.carnet_a = Dossier.objects.create(
            name="Carnet A", owner=self.utilisateur
        )
        self.carnet_b = Dossier.objects.create(
            name="Carnet B", owner=self.utilisateur
        )
        self.liste_a = ListeDeCategories.objects.create(
            nom="Type", dossier=self.carnet_a,
        )
        self.liste_b = ListeDeCategories.objects.create(
            nom="Type", dossier=self.carnet_b,
        )
        self.categorie_du_carnet_a = CategorieDossier.objects.create(
            liste=self.liste_a, nom="Budget",
        )
        self.categorie_du_carnet_b = CategorieDossier.objects.create(
            liste=self.liste_b, nom="Subvention",
        )
        self.note = creer_une_page("http://exemple.local/note-validation")
        self.appartenance_au_carnet_a = AppartenancePageDossier.objects.create(
            page=self.note, dossier=self.carnet_a,
        )

    def test_categorie_du_bon_carnet_acceptee_par_le_signal(self):
        # Le cas nominal ne doit pas lever. / Nominal case must not raise.
        self.appartenance_au_carnet_a.categories.add(self.categorie_du_carnet_a)
        self.assertEqual(self.appartenance_au_carnet_a.categories.count(), 1)

    def test_categorie_etrangere_refusee_par_le_signal_sens_direct(self):
        # appartenance.categories.add(cat) : instance = l'appartenance,
        # pk_set = pks de categories (reverse=False).
        # / Direct sense: instance is the membership.
        # transaction.atomic : le signal leve DANS le bloc atomique du
        # .add(), ce qui marque la transaction du test « a annuler » —
        # le savepoint permet de continuer a requeter apres.
        # / The savepoint lets us keep querying after the raise.
        with self.assertRaises(ValidationError):
            with transaction.atomic():
                self.appartenance_au_carnet_a.categories.add(
                    self.categorie_du_carnet_b
                )
        self.assertEqual(self.appartenance_au_carnet_a.categories.count(), 0)

    def test_categorie_du_bon_carnet_acceptee_en_sens_inverse(self):
        # Le cas nominal en sens inverse (reverse=True) : sans lui, un bug
        # qui ferait refuser SYSTEMATIQUEMENT la branche reverse passerait
        # inapercu — les tests de refus resteraient verts (relecture B).
        # / Nominal reverse case: without it, a branch that always refuses
        # would still pass the refusal tests.
        self.categorie_du_carnet_a.appartenances.add(
            self.appartenance_au_carnet_a
        )
        self.assertEqual(self.appartenance_au_carnet_a.categories.count(), 1)

    def test_categorie_etrangere_refusee_par_le_signal_sens_inverse(self):
        # cat.appartenances.add(appartenance) : instance = la categorie,
        # pk_set = pks d'appartenances (reverse=True). Le cas que la v1.0
        # de la spec cassait en ignorant le kwarg reverse.
        # / Reverse sense: instance is the category. The case v1.0 broke.
        with self.assertRaises(ValidationError):
            with transaction.atomic():
                self.categorie_du_carnet_b.appartenances.add(
                    self.appartenance_au_carnet_a
                )
        self.assertEqual(self.appartenance_au_carnet_a.categories.count(), 0)

    def test_categorie_etrangere_refusee_par_set(self):
        # .set() passe aussi par pre_add : le filet couvre ce chemin.
        # / .set() also goes through pre_add.
        with self.assertRaises(ValidationError):
            with transaction.atomic():
                self.appartenance_au_carnet_a.categories.set(
                    [self.categorie_du_carnet_a, self.categorie_du_carnet_b]
                )
        self.assertEqual(self.appartenance_au_carnet_a.categories.count(), 0)

    def test_serializer_refuse_les_ids_introuvables(self):
        from core.serializers import CategoriserUneNoteSerializer

        serializer = CategoriserUneNoteSerializer(
            data={"categorie_ids": [999999]},
            context={"appartenance": self.appartenance_au_carnet_a},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("categorie_ids", serializer.errors)

    def test_serializer_accepte_la_liste_vide_pour_tout_decocher(self):
        from core.serializers import CategoriserUneNoteSerializer

        serializer = CategoriserUneNoteSerializer(
            data={"categorie_ids": []},
            context={"appartenance": self.appartenance_au_carnet_a},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["categories_a_appliquer"], []
        )

    def test_categorie_etrangere_refusee_par_le_serializer(self):
        # Le serializer refuse AVANT le signal : l'utilisateur recoit une
        # erreur de formulaire, pas une 500.
        # / The serializer refuses BEFORE the signal: form error, not a 500.
        from core.serializers import CategoriserUneNoteSerializer

        serializer = CategoriserUneNoteSerializer(
            data={"categorie_ids": [self.categorie_du_carnet_b.pk]},
            context={"appartenance": self.appartenance_au_carnet_a},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("categorie_ids", serializer.errors)

    def test_categorie_du_bon_carnet_acceptee_par_le_serializer(self):
        from core.serializers import CategoriserUneNoteSerializer

        serializer = CategoriserUneNoteSerializer(
            data={"categorie_ids": [self.categorie_du_carnet_a.pk]},
            context={"appartenance": self.appartenance_au_carnet_a},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            list(serializer.validated_data["categories_a_appliquer"]),
            [self.categorie_du_carnet_a],
        )


class ValidationDesCategoriesDeBaseTest(TestCase):
    """
    Le symetrique cote base, que la v1.0 de la spec avait oublie.
    / The base-side symmetric validation, forgotten by spec v1.0.
    """

    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            username="valideur_base_test", password="motdepasse"
        )
        self.base_a = BaseDeConnaissances.objects.create(
            nom="Base A", slug="base-a",
        )
        self.base_b = BaseDeConnaissances.objects.create(
            nom="Base B", slug="base-b",
        )
        self.liste_a = ListeDeCategories.objects.create(
            nom="Territoire", base=self.base_a,
        )
        self.liste_b = ListeDeCategories.objects.create(
            nom="Territoire", base=self.base_b,
        )
        self.categorie_de_la_base_a = CategorieBase.objects.create(
            liste=self.liste_a, nom="Régional",
        )
        self.categorie_de_la_base_b = CategorieBase.objects.create(
            liste=self.liste_b, nom="National",
        )
        self.carnet = Dossier.objects.create(
            name="Veille", owner=self.utilisateur
        )
        self.appartenance_a_la_base_a = AppartenanceDossierBase.objects.create(
            dossier=self.carnet, base=self.base_a,
        )

    def test_categorie_de_la_bonne_base_acceptee(self):
        self.appartenance_a_la_base_a.categories.add(self.categorie_de_la_base_a)
        self.assertEqual(self.appartenance_a_la_base_a.categories.count(), 1)

    def test_categorie_etrangere_refusee_cote_base_sens_direct(self):
        with self.assertRaises(ValidationError):
            with transaction.atomic():
                self.appartenance_a_la_base_a.categories.add(
                    self.categorie_de_la_base_b
                )
        self.assertEqual(self.appartenance_a_la_base_a.categories.count(), 0)

    def test_categorie_de_la_bonne_base_acceptee_en_sens_inverse(self):
        # Meme exigence que cote carnet : le nominal de la branche reverse.
        # / Same requirement as notebook side: nominal reverse branch.
        self.categorie_de_la_base_a.appartenances.add(
            self.appartenance_a_la_base_a
        )
        self.assertEqual(self.appartenance_a_la_base_a.categories.count(), 1)

    def test_categorie_etrangere_refusee_cote_base_par_set(self):
        with self.assertRaises(ValidationError):
            with transaction.atomic():
                self.appartenance_a_la_base_a.categories.set(
                    [self.categorie_de_la_base_a, self.categorie_de_la_base_b]
                )
        self.assertEqual(self.appartenance_a_la_base_a.categories.count(), 0)

    def test_categorie_etrangere_refusee_cote_base_sens_inverse(self):
        with self.assertRaises(ValidationError):
            with transaction.atomic():
                self.categorie_de_la_base_b.appartenances.add(
                    self.appartenance_a_la_base_a
                )
        self.assertEqual(self.appartenance_a_la_base_a.categories.count(), 0)


class RoleSpecialDossierTest(TestCase):
    """
    Les carnets « magiques » identifies par role_special, plus par leur nom.
    / "Magic" notebooks identified by role_special, no longer by name.
    """

    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            username="proprietaire_test", password="motdepasse"
        )

    def test_un_seul_a_ranger_par_proprietaire(self):
        Dossier.objects.create(
            name="A ranger", owner=self.utilisateur,
            role_special=RoleSpecialDossier.A_RANGER,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Dossier.objects.create(
                    name="A ranger (copie)", owner=self.utilisateur,
                    role_special=RoleSpecialDossier.A_RANGER,
                )

    def test_deux_proprietaires_ont_chacun_leur_a_ranger(self):
        autre_utilisateur = Utilisateur.objects.create_user(
            username="autre_test", password="motdepasse"
        )
        Dossier.objects.create(
            name="A ranger", owner=self.utilisateur,
            role_special=RoleSpecialDossier.A_RANGER,
        )
        # Ne doit pas lever : la contrainte est par (owner, role_special).
        # / Must not raise: the constraint is per (owner, role_special).
        Dossier.objects.create(
            name="A ranger", owner=autre_utilisateur,
            role_special=RoleSpecialDossier.A_RANGER,
        )
        nombre_de_fourre_tout = Dossier.objects.filter(
            role_special=RoleSpecialDossier.A_RANGER
        ).count()
        self.assertEqual(nombre_de_fourre_tout, 2)

    def test_les_dossiers_sans_proprietaire_sont_aussi_limites(self):
        # Retour de relecture (phase A) : en Postgres, les NULL sont
        # distincts par defaut dans un index unique — sans nulls_distinct,
        # un nombre illimite de fourre-tout SANS owner pourrait exister,
        # et un futur get_or_create(owner=None) leverait
        # MultipleObjectsReturned.
        # / Ownerless special notebooks must be limited too
        # (nulls_distinct=False).
        Dossier.objects.create(
            name="A ranger", owner=None,
            role_special=RoleSpecialDossier.A_RANGER,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Dossier.objects.create(
                    name="A ranger bis", owner=None,
                    role_special=RoleSpecialDossier.A_RANGER,
                )

    def test_les_dossiers_ordinaires_ne_sont_pas_limites(self):
        # role_special vide n'est jamais contraint : un proprietaire peut
        # avoir autant de carnets ordinaires qu'il veut.
        # / Empty role_special is never constrained.
        Dossier.objects.create(name="Carnet 1", owner=self.utilisateur)
        Dossier.objects.create(name="Carnet 2", owner=self.utilisateur)
        nombre_de_carnets_ordinaires = Dossier.objects.filter(
            owner=self.utilisateur, role_special="",
        ).count()
        self.assertEqual(nombre_de_carnets_ordinaires, 2)
