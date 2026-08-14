"""
Tests de la base de connaissances (phase H).
/ Knowledge base tests (phase H).

LOCALISATION : front/tests/test_corpus_phase_h.py

SPEC-corpus § 9 : GET /bases/, GET /bases/{slug}/, POST carnets/ et
categories/. Le niveau base est FACULTATIF (§ 3.1) — rien n'oblige un
carnet a en avoir une.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (
    AppartenanceDossierBase,
    BaseDeConnaissances,
    CategorieBase,
    Dossier,
    ListeDeCategories,
    VisibiliteDossier,
)

Utilisateur = get_user_model()


class BaseListeEtDetailTest(TestCase):
    """GET /bases/ et /bases/{slug}/. / List and detail."""

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="proprio_h_test", password="motdepasse"
        )
        self.base_publique = BaseDeConnaissances.objects.create(
            nom="Réseau tiers-lieux", slug="reseau-tiers-lieux",
            owner=self.proprietaire, visibilite=VisibiliteDossier.PUBLIC,
        )
        self.base_privee = BaseDeConnaissances.objects.create(
            nom="Base privée H", slug="base-privee-h",
            owner=self.proprietaire, visibilite=VisibiliteDossier.PRIVE,
        )
        self.carnet = Dossier.objects.create(
            name="Veille H", owner=self.proprietaire,
            visibilite=VisibiliteDossier.PUBLIC,
        )
        AppartenanceDossierBase.objects.create(
            dossier=self.carnet, base=self.base_publique,
        )

    def test_anonyme_liste_les_bases_publiques_seulement(self):
        reponse = self.client.get("/bases/", HTTP_HX_REQUEST="true")
        contenu = reponse.content.decode("utf-8")

        self.assertEqual(reponse.status_code, 200)
        self.assertIn("Réseau tiers-lieux", contenu)
        self.assertNotIn("Base privée H", contenu)

    def test_anonyme_lit_une_base_publique_et_ses_carnets(self):
        reponse = self.client.get(
            f"/bases/{self.base_publique.slug}/", HTTP_HX_REQUEST="true",
        )
        contenu = reponse.content.decode("utf-8")

        self.assertEqual(reponse.status_code, 200)
        self.assertIn("Veille H", contenu)

    def test_anonyme_recoit_404_sur_une_base_privee(self):
        # 404, pas 403 : le slug EST le nom — un 403 confirmerait
        # l'existence (relecture H, oracle). / 404, not 403: no oracle.
        reponse = self.client.get(f"/bases/{self.base_privee.slug}/")
        self.assertEqual(reponse.status_code, 404)

    def test_le_compteur_de_la_liste_ne_compte_pas_les_carnets_invisibles(self):
        # Relecture H, B1 : meme doctrine que « dans N carnets ».
        # / Same no-leak doctrine as "in N notebooks".
        carnet_prive = Dossier.objects.create(
            name="Carnet invisible H", owner=self.proprietaire,
            visibilite=VisibiliteDossier.PRIVE,
        )
        AppartenanceDossierBase.objects.create(
            dossier=carnet_prive, base=self.base_publique,
        )
        reponse = self.client.get("/bases/", HTTP_HX_REQUEST="true")
        contenu = reponse.content.decode("utf-8")
        self.assertIn("1 carnet", contenu)
        self.assertNotIn("2 carnets", contenu)

    def test_une_base_orpheline_privee_est_fermee(self):
        # Relecture H, B2 : owner=None sur un modele NEUF = compte
        # supprime — la base se FERME, elle ne s'ouvre pas.
        # / An orphaned private base closes, never opens.
        base_orpheline = BaseDeConnaissances.objects.create(
            nom="Base orpheline H", slug="base-orpheline-h",
            owner=None, visibilite=VisibiliteDossier.PRIVE,
        )
        visiteur = Utilisateur.objects.create_user(
            username="visiteur_orphelin_h", password="motdepasse"
        )
        self.client.force_login(visiteur)
        reponse = self.client.get(f"/bases/{base_orpheline.slug}/")
        self.assertEqual(reponse.status_code, 404)

    def test_creer_une_base(self):
        createur = Utilisateur.objects.create_user(
            username="createur_h", password="motdepasse"
        )
        self.client.force_login(createur)
        reponse = self.client.post("/bases/", {"nom": "Ma nouvelle base"})
        self.assertEqual(reponse.status_code, 200)
        base_creee = BaseDeConnaissances.objects.get(nom="Ma nouvelle base")
        self.assertEqual(base_creee.owner, createur)
        self.assertEqual(base_creee.slug, "ma-nouvelle-base")

    def test_le_proprietaire_du_carnet_retire_son_carnet_de_la_base(self):
        # Doctrine du 8 aout : on peut toujours sortir SON contenu d'un
        # contenant d'autrui. / One can always pull one's content out.
        proprietaire_du_carnet = Utilisateur.objects.create_user(
            username="proprio_carnet_h", password="motdepasse"
        )
        son_carnet = Dossier.objects.create(
            name="Son carnet H", owner=proprietaire_du_carnet,
            visibilite=VisibiliteDossier.PUBLIC,
        )
        AppartenanceDossierBase.objects.create(
            dossier=son_carnet, base=self.base_publique,
        )
        self.client.force_login(proprietaire_du_carnet)
        reponse = self.client.post(
            f"/bases/{self.base_publique.slug}/carnets/{son_carnet.pk}/retirer/"
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertFalse(
            AppartenanceDossierBase.objects.filter(
                dossier=son_carnet, base=self.base_publique,
            ).exists()
        )
        self.assertTrue(Dossier.objects.filter(pk=son_carnet.pk).exists())

    def test_acces_direct_rend_la_page_du_site(self):
        reponse = self.client.get(f"/bases/{self.base_publique.slug}/")
        contenu = reponse.content.decode("utf-8")
        self.assertIn("htmx", contenu)

    def test_un_carnet_prive_d_une_base_publique_n_est_pas_nomme(self):
        # Meme doctrine que le bloc de la note : on ne nomme jamais un
        # contenant que le demandeur ne peut pas lire.
        # / Same doctrine: never name an unreadable container.
        carnet_prive = Dossier.objects.create(
            name="Carnet secret H", owner=self.proprietaire,
            visibilite=VisibiliteDossier.PRIVE,
        )
        AppartenanceDossierBase.objects.create(
            dossier=carnet_prive, base=self.base_publique,
        )
        reponse = self.client.get(
            f"/bases/{self.base_publique.slug}/", HTTP_HX_REQUEST="true",
        )
        self.assertNotIn(
            "Carnet secret H", reponse.content.decode("utf-8")
        )

    def test_le_sommaire_d_une_carte_ne_nomme_aucun_carnet_interdit(self):
        # La liste des bases (refonte en cartes du 12 aout) NOMME
        # desormais les carnets d'une base, pour remplacer une
        # description absente. Elle herite donc de la meme doctrine que
        # le detail : jamais un carnet que le demandeur ne peut lire.
        # / The card grid now NAMES a base's notebooks; same no-leak
        # doctrine as the detail view applies.
        carnet_prive = Dossier.objects.create(
            name="Carnet invisible du sommaire", owner=self.proprietaire,
            visibilite=VisibiliteDossier.PRIVE,
        )
        AppartenanceDossierBase.objects.create(
            dossier=carnet_prive, base=self.base_publique,
        )
        reponse = self.client.get("/bases/", HTTP_HX_REQUEST="true")
        self.assertNotIn(
            "Carnet invisible du sommaire", reponse.content.decode("utf-8")
        )

    def test_la_liste_des_bases_coute_le_meme_nombre_de_requetes(self):
        # VERROU N+1. La carte d'une base montre son sommaire, donc les
        # NOMS de ses carnets : sans `Prefetch`, chaque base ajouterait
        # sa requete, et chaque carnet la sienne. On mesure le cout a
        # une base, puis a quatre bases de deux carnets chacune : le
        # nombre de requetes doit etre le MEME : deux, mesurees le 12 aout
        # (la liste annotee, puis le prefetch des appartenances).
        # / N+1 lock: cards name their notebooks, so without a Prefetch
        # every base would add a query. The cost must not grow.
        with self.assertNumQueries(2):
            self.client.get("/bases/", HTTP_HX_REQUEST="true")

        for numero in range(4):
            base_ajoutee = BaseDeConnaissances.objects.create(
                nom=f"Base de charge {numero}",
                slug=f"base-de-charge-{numero}",
                owner=self.proprietaire,
                visibilite=VisibiliteDossier.PUBLIC,
            )
            for rang in range(2):
                carnet_ajoute = Dossier.objects.create(
                    name=f"Carnet {numero}-{rang}", owner=self.proprietaire,
                    visibilite=VisibiliteDossier.PUBLIC,
                )
                AppartenanceDossierBase.objects.create(
                    dossier=carnet_ajoute, base=base_ajoutee,
                )

        with self.assertNumQueries(2):
            self.client.get("/bases/", HTTP_HX_REQUEST="true")


class AjouterUnCarnetALaBaseTest(TestCase):
    """POST /bases/{slug}/carnets/. / Adding a notebook to a base."""

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="rangeur_h_test", password="motdepasse"
        )
        self.autre = Utilisateur.objects.create_user(
            username="autre_h_test", password="motdepasse"
        )
        self.base = BaseDeConnaissances.objects.create(
            nom="Base H", slug="base-h", owner=self.proprietaire,
        )
        self.carnet = Dossier.objects.create(
            name="Carnet à ranger H", owner=self.proprietaire,
        )

    def test_le_proprietaire_ajoute_un_carnet(self):
        self.client.force_login(self.proprietaire)
        reponse = self.client.post(
            f"/bases/{self.base.slug}/carnets/",
            {"carnet_id": self.carnet.pk},
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(
            AppartenanceDossierBase.objects.filter(
                dossier=self.carnet, base=self.base,
            ).exists()
        )

    def test_ajouter_est_idempotent(self):
        self.client.force_login(self.proprietaire)
        self.client.post(
            f"/bases/{self.base.slug}/carnets/", {"carnet_id": self.carnet.pk},
        )
        reponse = self.client.post(
            f"/bases/{self.base.slug}/carnets/", {"carnet_id": self.carnet.pk},
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(
            AppartenanceDossierBase.objects.filter(
                dossier=self.carnet, base=self.base,
            ).count(),
            1,
        )

    def test_un_tiers_n_ajoute_pas(self):
        self.client.force_login(self.autre)
        reponse = self.client.post(
            f"/bases/{self.base.slug}/carnets/",
            {"carnet_id": self.carnet.pk},
        )
        self.assertEqual(reponse.status_code, 403)

    def test_on_n_ajoute_pas_un_carnet_qu_on_ne_peut_pas_lire(self):
        carnet_d_autrui = Dossier.objects.create(
            name="Privé d'autrui H", owner=self.autre,
            visibilite=VisibiliteDossier.PRIVE,
        )
        self.client.force_login(self.proprietaire)
        reponse = self.client.post(
            f"/bases/{self.base.slug}/carnets/",
            {"carnet_id": carnet_d_autrui.pk},
        )
        self.assertEqual(reponse.status_code, 403)


class CategoriesDeLaBaseTest(TestCase):
    """GET/POST /bases/{slug}/categories/ et la relation categorisee."""

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="categoriseur_h_test", password="motdepasse"
        )
        self.base = BaseDeConnaissances.objects.create(
            nom="Base catégories H", slug="base-categories-h",
            owner=self.proprietaire,
        )

    def test_creer_un_axe_et_une_categorie_de_base(self):
        self.client.force_login(self.proprietaire)
        self.client.post(
            f"/bases/{self.base.slug}/categories/",
            {"action": "creer_liste", "nom": "Territoire"},
        )
        liste = ListeDeCategories.objects.get(base=self.base, nom="Territoire")
        reponse = self.client.post(
            f"/bases/{self.base.slug}/categories/",
            {"action": "creer_categorie", "liste_id": liste.pk, "nom": "Régional"},
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(
            CategorieBase.objects.filter(liste=liste, nom="Régional").exists()
        )

    def test_creer_exige_l_ecriture(self):
        intrus = Utilisateur.objects.create_user(
            username="intrus_h_test", password="motdepasse"
        )
        self.client.force_login(intrus)
        reponse = self.client.post(
            f"/bases/{self.base.slug}/categories/",
            {"action": "creer_liste", "nom": "Intrusion"},
        )
        self.assertEqual(reponse.status_code, 403)


class RelationCarnetBaseTest(TestCase):
    """
    Les trous de spec § 9 bouches (decision du 8 aout) : categoriser et
    epingler la relation carnet-base — le meme patron que la note, un
    cran au-dessus, ENFIN complet. / The § 9 spec holes plugged.
    """

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="relation_h_test", password="motdepasse"
        )
        self.base = BaseDeConnaissances.objects.create(
            nom="Base relation H", slug="base-relation-h",
            owner=self.proprietaire,
        )
        self.autre_base = BaseDeConnaissances.objects.create(
            nom="Autre base H", slug="autre-base-h",
            owner=self.proprietaire,
        )
        self.carnet = Dossier.objects.create(
            name="Carnet relation H", owner=self.proprietaire,
        )
        self.appartenance = AppartenanceDossierBase.objects.create(
            dossier=self.carnet, base=self.base,
        )
        self.liste = ListeDeCategories.objects.create(
            nom="Territoire", base=self.base,
        )
        self.categorie = CategorieBase.objects.create(
            liste=self.liste, nom="Régional",
        )
        liste_de_l_autre = ListeDeCategories.objects.create(
            nom="Territoire", base=self.autre_base,
        )
        self.categorie_etrangere = CategorieBase.objects.create(
            liste=liste_de_l_autre, nom="National",
        )
        self.client.force_login(self.proprietaire)

    def test_categoriser_la_relation_carnet_base(self):
        reponse = self.client.post(
            f"/bases/{self.base.slug}/carnets/{self.carnet.pk}/categories/",
            {"categorie_ids": [self.categorie.pk]},
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(
            list(self.appartenance.categories.values_list("nom", flat=True)),
            ["Régional"],
        )

    def test_categorie_d_une_autre_base_refusee(self):
        reponse = self.client.post(
            f"/bases/{self.base.slug}/carnets/{self.carnet.pk}/categories/",
            {"categorie_ids": [self.categorie_etrangere.pk]},
        )
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(self.appartenance.categories.count(), 0)

    def test_epingler_la_relation_bascule(self):
        self.client.post(
            f"/bases/{self.base.slug}/carnets/{self.carnet.pk}/epingler/"
        )
        self.appartenance.refresh_from_db()
        self.assertTrue(self.appartenance.epingle)

        self.client.post(
            f"/bases/{self.base.slug}/carnets/{self.carnet.pk}/epingler/"
        )
        self.appartenance.refresh_from_db()
        self.assertFalse(self.appartenance.epingle)

    def test_un_tiers_ne_categorise_pas(self):
        intrus = Utilisateur.objects.create_user(
            username="intrus_relation_h", password="motdepasse"
        )
        self.client.force_login(intrus)
        reponse = self.client.post(
            f"/bases/{self.base.slug}/carnets/{self.carnet.pk}/categories/",
            {"categorie_ids": [self.categorie.pk]},
        )
        self.assertEqual(reponse.status_code, 403)
