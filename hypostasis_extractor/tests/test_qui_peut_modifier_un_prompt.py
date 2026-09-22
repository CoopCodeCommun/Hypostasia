"""
Qui peut toucher à quel prompt.
/ Who may touch which prompt.

LOCALISATION : hypostasis_extractor/tests/test_qui_peut_modifier_un_prompt.py

TROIS RÈGLES, ET CHACUNE PROTÈGE D'UNE CHOSE DIFFÉRENTE :

- **le panneau se lit** par tout utilisateur connecté — un prompt qu'on
  ne peut pas lire ne se discute pas ;
- **les prompts d'origine** ne se modifient que par un superutilisateur :
  ce sont ceux sur lesquels TOUT LE SITE retombe, et une modification
  malheureuse s'y propage à toutes les productions, sans qu'aucun écran
  ne l'annonce ;
- **les trois champs à portée globale** — `est_par_defaut`,
  `type_analyseur`, `is_active` — restent au superutilisateur MÊME sur
  un analyseur ordinaire. Un seul suffirait à détourner la production de
  tout le monde, et chaque production est facturée.
/ Three rules: read for all, original prompts for superusers, and the
three global-reach fields for superusers even on an ordinary analyzer.

CE QU'UN UTILISATEUR ORDINAIRE FAIT À LA PLACE : il pose une PRÉFÉRENCE,
qui préremplit son sélecteur et n'engage que lui.
/ What an ordinary user does instead: sets a preference, binding only them.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from hypostasis_extractor.models import (
    AnalyseurSyntaxique, PreferenceD_analyseur, PromptPiece,
)


class BaseDesPermissions(TestCase):
    """Trois comptes, deux analyseurs. / Three accounts, two analyzers."""

    def setUp(self):
        Utilisateur = get_user_model()
        self.ordinaire = Utilisateur.objects.create_user(
            username="lectrice", password="test1234",
        )
        self.superutilisateur = Utilisateur.objects.create_superuser(
            username="patronne", password="test1234",
        )
        self.prompt_d_origine = AnalyseurSyntaxique.objects.create(
            name="Rédacteur d'article", type_analyseur="rediger_un_article",
            is_active=True, est_par_defaut=True, est_d_origine=True,
        )
        PromptPiece.objects.create(
            analyseur=self.prompt_d_origine, role="instruction",
            content="Rédige.", order=0,
        )
        self.prompt_ordinaire = AnalyseurSyntaxique.objects.create(
            name="Mon rédacteur", type_analyseur="rediger_un_article",
            is_active=True, est_d_origine=False,
        )


class LePanneauSeLitParToutLeMondeTest(BaseDesPermissions):
    """Lire n'est pas modifier. / Reading is not editing."""

    def test_un_utilisateur_ordinaire_voit_la_liste(self):
        self.client.force_login(self.ordinaire)

        reponse = self.client.get("/api/analyseurs/", HTTP_HX_REQUEST="true")

        self.assertEqual(reponse.status_code, 200)
        # Le gabarit echappe l'apostrophe : on cherche le nom tel qu'il
        # est RENDU. / The template escapes the apostrophe.
        self.assertIn("Rédacteur d&#x27;article", reponse.content.decode())

    def test_un_utilisateur_ordinaire_ouvre_l_editeur(self):
        self.client.force_login(self.ordinaire)

        reponse = self.client.get(
            f"/api/analyseurs/{self.prompt_d_origine.pk}/",
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(reponse.status_code, 200)


class LesPromptsD_origineSontFermesTest(BaseDesPermissions):
    """Ce sur quoi tout le site retombe. / What the whole site falls back on."""

    def test_un_ordinaire_ne_modifie_pas_un_prompt_d_origine(self):
        self.client.force_login(self.ordinaire)

        reponse = self.client.patch(
            f"/api/analyseurs/{self.prompt_d_origine.pk}/",
            "description=modifiée",
            content_type="application/x-www-form-urlencoded",
        )

        self.assertEqual(reponse.status_code, 403)
        self.prompt_d_origine.refresh_from_db()
        self.assertNotEqual(self.prompt_d_origine.description, "modifiée")

    def test_un_ordinaire_ne_touche_pas_aux_pieces_d_un_prompt_d_origine(self):
        self.client.force_login(self.ordinaire)
        piece = self.prompt_d_origine.pieces.get()

        reponse = self.client.patch(
            f"/api/analyseurs/{self.prompt_d_origine.pk}/update_piece/",
            f"piece_id={piece.pk}&content=détourné",
            content_type="application/x-www-form-urlencoded",
        )

        self.assertEqual(reponse.status_code, 403)
        piece.refresh_from_db()
        self.assertEqual(piece.content, "Rédige.")

    def test_un_superutilisateur_le_modifie(self):
        self.client.force_login(self.superutilisateur)

        reponse = self.client.patch(
            f"/api/analyseurs/{self.prompt_d_origine.pk}/",
            "description=corrigée",
            content_type="application/x-www-form-urlencoded",
        )

        self.assertEqual(reponse.status_code, 200)
        self.prompt_d_origine.refresh_from_db()
        self.assertEqual(self.prompt_d_origine.description, "corrigée")


class UnUtilisateurOrdinaireACeQuiEstASoiTest(BaseDesPermissions):
    """Créer et modifier les siens. / Creating and editing one's own."""

    def test_il_cree_un_analyseur(self):
        self.client.force_login(self.ordinaire)

        reponse = self.client.post("/api/analyseurs/", {
            "name": "Le mien", "type_analyseur": "rediger_un_article",
        })

        self.assertEqual(reponse.status_code, 201)
        cree = AnalyseurSyntaxique.objects.get(name="Le mien")
        # Ce qu'il crée n'est PAS d'origine : il pourra le remodifier.
        # / What he creates is not original: he may edit it again.
        self.assertFalse(cree.est_d_origine)

    def test_il_modifie_un_analyseur_ordinaire(self):
        self.client.force_login(self.ordinaire)

        reponse = self.client.patch(
            f"/api/analyseurs/{self.prompt_ordinaire.pk}/",
            "description=la mienne",
            content_type="application/x-www-form-urlencoded",
        )

        self.assertEqual(reponse.status_code, 200)
        self.prompt_ordinaire.refresh_from_db()
        self.assertEqual(self.prompt_ordinaire.description, "la mienne")

    def test_il_ajoute_une_piece_a_un_analyseur_ordinaire(self):
        self.client.force_login(self.ordinaire)

        reponse = self.client.post(
            f"/api/analyseurs/{self.prompt_ordinaire.pk}/add_piece/",
            {"role": "instruction", "content": "Ma consigne.", "order": 0},
        )

        self.assertEqual(reponse.status_code, 201)
        self.assertEqual(self.prompt_ordinaire.pieces.count(), 1)


class LesTroisChampsGlobauxRestentFermesTest(BaseDesPermissions):
    """
    Un seul d'entre eux détourne la production de tout le monde.
    / A single one redirects everyone's productions.
    """

    def test_un_ordinaire_ne_coche_pas_le_defaut_du_site(self):
        # Cocher `est_par_defaut` ferait passer TOUS les gestes, tous
        # FACTURÉS, par son analyseur.
        # / It would route every billed gesture through it.
        self.client.force_login(self.ordinaire)

        reponse = self.client.patch(
            f"/api/analyseurs/{self.prompt_ordinaire.pk}/",
            "est_par_defaut=true",
            content_type="application/x-www-form-urlencoded",
        )

        self.assertEqual(reponse.status_code, 403)
        self.prompt_ordinaire.refresh_from_db()
        self.assertFalse(self.prompt_ordinaire.est_par_defaut)

    def test_un_ordinaire_ne_change_pas_le_type(self):
        # Changer le type laisse le type de DÉPART sans défaut : la
        # résolution retombe alors sur l'ordre alphabétique, qu'il
        # suffit de gagner en se nommant « AAA ».
        # / It leaves the departure type with no default at all.
        self.client.force_login(self.ordinaire)

        reponse = self.client.patch(
            f"/api/analyseurs/{self.prompt_ordinaire.pk}/",
            "type_analyseur=synthetiser",
            content_type="application/x-www-form-urlencoded",
        )

        self.assertEqual(reponse.status_code, 403)

    def test_un_superutilisateur_coche_le_defaut(self):
        self.client.force_login(self.superutilisateur)

        reponse = self.client.patch(
            f"/api/analyseurs/{self.prompt_ordinaire.pk}/",
            "est_par_defaut=true",
            content_type="application/x-www-form-urlencoded",
        )

        self.assertEqual(reponse.status_code, 200)
        self.prompt_ordinaire.refresh_from_db()
        self.assertTrue(self.prompt_ordinaire.est_par_defaut)


class LaPreferenceNeEngageQueSonAuteurTest(BaseDesPermissions):
    """Le geste qui remplace « cocher le défaut ». / The replacement gesture."""

    def test_un_ordinaire_pose_sa_preference(self):
        self.client.force_login(self.ordinaire)

        reponse = self.client.post(
            f"/api/analyseurs/{self.prompt_ordinaire.pk}/preferer/",
        )

        self.assertEqual(reponse.status_code, 200)
        preference = PreferenceD_analyseur.objects.get(
            utilisateur=self.ordinaire,
        )
        self.assertEqual(preference.analyseur, self.prompt_ordinaire)
        self.assertEqual(preference.type_analyseur, "rediger_un_article")

    def test_elle_ne_touche_pas_au_defaut_du_site(self):
        self.client.force_login(self.ordinaire)

        self.client.post(
            f"/api/analyseurs/{self.prompt_ordinaire.pk}/preferer/",
        )

        self.prompt_ordinaire.refresh_from_db()
        self.prompt_d_origine.refresh_from_db()
        self.assertFalse(self.prompt_ordinaire.est_par_defaut)
        self.assertTrue(self.prompt_d_origine.est_par_defaut)

    def test_une_seule_preference_par_type(self):
        self.client.force_login(self.ordinaire)

        self.client.post(f"/api/analyseurs/{self.prompt_ordinaire.pk}/preferer/")
        self.client.post(f"/api/analyseurs/{self.prompt_d_origine.pk}/preferer/")

        self.assertEqual(
            PreferenceD_analyseur.objects.filter(
                utilisateur=self.ordinaire,
            ).count(),
            1,
        )

    def test_ma_preference_preremplit_MON_selecteur(self):
        from core.models import Dossier
        from front.views_synthese import _redacteur_prefere_de

        PreferenceD_analyseur.objects.create(
            utilisateur=self.ordinaire,
            type_analyseur="rediger_un_article",
            analyseur=self.prompt_ordinaire,
        )

        # La mienne pour moi ; rien pour l'autre, qui garde le défaut.
        # / Mine for me; nothing for the other, who keeps the default.
        self.assertEqual(
            _redacteur_prefere_de(self.ordinaire), self.prompt_ordinaire,
        )
        self.assertIsNone(_redacteur_prefere_de(self.superutilisateur))

    def test_une_preference_vers_un_analyseur_retire_vaut_comme_absente(self):
        from front.views_synthese import _redacteur_prefere_de

        PreferenceD_analyseur.objects.create(
            utilisateur=self.ordinaire,
            type_analyseur="rediger_un_article",
            analyseur=self.prompt_ordinaire,
        )
        self.prompt_ordinaire.is_active = False
        self.prompt_ordinaire.save(update_fields=["is_active"])

        self.assertIsNone(_redacteur_prefere_de(self.ordinaire))
