"""
Un analyseur qui change laisse une version derrière lui.
/ An analyzer that changes leaves a version behind.

LOCALISATION : hypostasis_extractor/tests/test_le_versionnage_d_un_analyseur.py

POURQUOI CES TESTS EXISTENT. `ExtractionJob.analyseur_version` est une
cle etrangere posee depuis des mois, avec un `help_text` qui promet « la
version de l'analyseur au moment de l'extraction ». Mesure du 1er
septembre 2026 : **zero** `AnalyseurVersion` en base, et zero job sur 154
qui en porte une. Le champ ne pouvait pas etre rempli : rien ne creait de
version.

Trois trous, tous verifies dans le code :
- creer un analyseur ne creait AUCUNE v1 ;
- `partial_update` ne versionnait ni le type, ni `est_par_defaut` ;
- les fixtures posaient les pieces sans version.
/ Three holes: no v1 on create, no version on what decides which
gesture picks the analyzer, and fixtures filled pieces without a version.

CE QU'ON NE VERSIONNE PAS : un PATCH qui ne change rien. Le bouton
« Sauver » de l'editeur repost nom et description a chaque clic — une
version par clic ferait grossir l'historique de snapshots identiques
(mesure du 1er septembre : un snapshot d'analyseur d'extraction pese
23 873 octets).
/ Not versioned: a PATCH that changes nothing — the Save button reposts
name and description on every click, and a snapshot weighs ~24 KB.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from hypostasis_extractor.models import AnalyseurSyntaxique, AnalyseurVersion


class BaseDuVersionnage(TestCase):
    """
    Un superutilisateur. / A superuser.

    LES DEUX CHAMPS VERSIONNES LUI SONT RESERVES : `est_par_defaut` et
    `type_analyseur` ont une portee GLOBALE — ils decident de
    l'analyseur sur lequel tout le site retombe. Un compte ordinaire, ou
    meme staff, recoit un 403 et n'ecrit donc aucune version.
    / The two versioned fields are superuser-only: they have global reach.
    """

    def setUp(self):
        self.staff = get_user_model().objects.create_superuser(
            username="staff_versionnage", password="test1234",
        )
        self.client.force_login(self.staff)


class LaCreationD_unAnalyseurTest(BaseDuVersionnage):
    """Naitre, c'est deja une version. / Being born is a version."""

    def test_creer_un_analyseur_cree_sa_v1(self):
        reponse = self.client.post("/api/analyseurs/", {
            "name": "Rédacteur d'essai",
            "type_analyseur": "synthetiser",
        })

        self.assertEqual(reponse.status_code, 201)
        analyseur = AnalyseurSyntaxique.objects.get(name="Rédacteur d'essai")
        version = analyseur.versions.get()
        self.assertEqual(version.version_number, 1)
        self.assertEqual(version.modified_by, self.staff)

    def test_la_v1_porte_le_type_choisi_a_la_creation(self):
        self.client.post("/api/analyseurs/", {
            "name": "Rédacteur d'essai",
            "type_analyseur": "synthetiser",
        })

        analyseur = AnalyseurSyntaxique.objects.get(name="Rédacteur d'essai")
        self.assertEqual(
            analyseur.versions.get().snapshot["type_analyseur"],
            "synthetiser",
        )


class LaMiseAJourD_unAnalyseurTest(BaseDuVersionnage):
    """Ce qui change le CONTENU envoye doit laisser une trace."""

    def setUp(self):
        super().setUp()
        self.analyseur = AnalyseurSyntaxique.objects.create(
            name="Analyseur d'essai", type_analyseur="analyser",
        )

    def test_changer_le_defaut_cree_une_version(self):
        # `est_par_defaut` decide QUEL analyseur sera choisi par un
        # geste : le changer sans le versionner rend deux productions
        # incomparables sans qu'aucune trace ne le dise.
        # / It decides which analyzer a gesture picks.
        self.client.patch(
            f"/api/analyseurs/{self.analyseur.pk}/",
            "est_par_defaut=true",
            content_type="application/x-www-form-urlencoded",
        )

        self.assertEqual(self.analyseur.versions.count(), 1)

    def test_changer_le_type_cree_une_version(self):
        self.client.patch(
            f"/api/analyseurs/{self.analyseur.pk}/",
            "type_analyseur=synthetiser",
            content_type="application/x-www-form-urlencoded",
        )

        self.assertEqual(self.analyseur.versions.count(), 1)

    def test_un_patch_qui_ne_change_rien_ne_versionne_pas(self):
        # Le bouton « Sauver » repost nom et description a chaque clic.
        # / The Save button reposts name and description on every click.
        self.client.patch(
            f"/api/analyseurs/{self.analyseur.pk}/",
            "name=Analyseur d'essai",
            content_type="application/x-www-form-urlencoded",
        )

        self.assertEqual(self.analyseur.versions.count(), 0)

    def test_renommer_ne_versionne_pas(self):
        # Un nom ne change RIEN a ce qui part au modele. Le versionner
        # ferait grossir l'historique de snapshots identiques au
        # caractere pres, sauf un.
        # / A name changes nothing in what is sent.
        self.client.patch(
            f"/api/analyseurs/{self.analyseur.pk}/",
            "name=Autre nom",
            content_type="application/x-www-form-urlencoded",
        )

        self.assertEqual(self.analyseur.versions.count(), 0)


class LesFixturesLaissentUneV1Test(TestCase):
    """
    Les analyseurs de l'installation ont une version, eux aussi.
    / The installed analyzers get a version too.
    """

    def test_les_fixtures_creent_une_v1_par_analyseur(self):
        from front.services.fixtures_analyseurs import (
            creer_les_modeles_ia_et_les_analyseurs,
        )

        creer_les_modeles_ia_et_les_analyseurs()

        for analyseur in AnalyseurSyntaxique.objects.all():
            self.assertEqual(
                analyseur.versions.count(), 1,
                f"L'analyseur « {analyseur.name} » n'a pas sa v1.",
            )

    def test_un_second_passage_ne_cree_pas_de_seconde_version(self):
        # CETTE FONCTION TOURNE A CHAQUE DEMARRAGE DE CONTENEUR
        # (`bin/install.sh`). Sans garde, chaque redemarrage ajouterait
        # un snapshot de ~24 Ko par analyseur, pour rien.
        # / It runs at every container start: one snapshot per restart.
        from front.services.fixtures_analyseurs import (
            creer_les_modeles_ia_et_les_analyseurs,
        )

        creer_les_modeles_ia_et_les_analyseurs()
        nombre_de_versions = AnalyseurVersion.objects.count()

        creer_les_modeles_ia_et_les_analyseurs()

        self.assertEqual(AnalyseurVersion.objects.count(), nombre_de_versions)
