"""
Les frictions F4 à F10 de la recette connectée du 10 août 2026.
/ Recette frictions F4 to F10.

LOCALISATION : front/tests/test_frictions_recette_f4_f10.py

Sept défauts d'expérience relevés en exerçant le produit pour de vrai
(PLAN/recette-connectee-2026-08-10.md). Ce qu'ils avaient en commun :
l'écran en savait plus qu'il n'en disait.

- F4  lire un article ne changeait pas l'URL : F5 ramenait à la liste,
      et le lien n'était pas partageable depuis l'endroit où on lit ;
- F5  le diff parlait en langage machine (`append_to_section`,
      `[[ext:35284]]`) au moment précis où l'on demande d'accepter ;
- F6  le verdict d'un paragraphe se lisait comme un trait de
      séparation, et rien ne nommait l'état ;
- F7  la légende annonçait « non sourcé » avant même la première
      vérification : elle promettait des couleurs absentes du texte ;
- F8  produire, mettre à jour et vérifier donnaient trois lignes
      IDENTIQUES dans « Mes tâches » ;
- F9  le titre de l'onglet disait « Bibliothèque » partout ;
- F10 aucun choix de moteur, et surtout aucune mention de celui qui
      allait rédiger.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (
    Configuration,
    Dossier,
    Page,
    SourceLink,
    TypeDeNote,
    TypeLien,
    VisibiliteDossier,
    Wiki,
)
from core.services.corpus import ranger_une_note_dans_un_carnet
from front.templatetags.lisibilite_diff import (
    est_sans_redaction,
    marqueurs_en_renvois,
    nom_d_operation,
)

Utilisateur = get_user_model()


class LisibiliteDuDiffTest(TestCase):
    """F5 — le diff ne parle plus en langage machine."""

    def test_le_type_d_operation_est_traduit(self):
        self.assertEqual(
            nom_d_operation("append_to_section"),
            "Ajouter à la fin de la section",
        )
        self.assertEqual(
            nom_d_operation("replace_section"),
            "Remplacer le contenu de la section",
        )

    def test_un_type_inconnu_est_montre_tel_quel(self):
        """Mieux un mot technique qu'un silence sur ce qui sera appliqué."""
        self.assertEqual(nom_d_operation("un_type_futur"), "un_type_futur")

    def test_les_marqueurs_deviennent_lisibles(self):
        rendu = marqueurs_en_renvois("Un passage [[ext:35284]] sourcé.")
        self.assertNotIn("[[ext:", rendu)
        self.assertIn("source 35284", rendu)

    def test_le_contenu_du_modele_est_echappe(self):
        """Le texte vient d'un modèle de langage : il n'est pas de confiance."""
        rendu = marqueurs_en_renvois('<script>alert("xss")</script>')
        self.assertNotIn("<script>", rendu)
        self.assertIn("&lt;script&gt;", rendu)

    def test_une_operation_sans_phrase_est_reconnue(self):
        """Le défaut B2 : un contenu réduit à des marqueurs.

        Le back a été corrigé, mais l'écran doit rester capable de le
        DIRE si cela se reproduit.
        """
        self.assertTrue(est_sans_redaction("[[ext:35284]]"))
        self.assertTrue(est_sans_redaction("  [[ext:1]] [[ext:2]]  "))
        self.assertTrue(est_sans_redaction(""))
        self.assertFalse(est_sans_redaction("Une phrase [[ext:1]] sourcée."))


class VerdictsEtLegendeTest(TestCase):
    """F6 et F7 — le verdict se nomme, la légende ne promet rien."""

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            "proprio_verdicts", "pv@exemple.test", "motdepasse123",
        )
        self.carnet = Dossier.objects.create(
            name="Carnet des verdicts", owner=self.proprietaire,
            visibilite=VisibiliteDossier.PRIVE,
        )
        self.article = Page.objects.create(
            title="Wiki — verdicts", type_de_note=TypeDeNote.WIKI,
            owner=self.proprietaire, content_hash="hash-verdicts",
            html_readability="<p>Une affirmation.</p>",
            text_readability="Une affirmation.", html_original="",
        )
        ranger_une_note_dans_un_carnet(
            self.article, self.carnet, utilisateur=self.proprietaire,
        )
        Wiki.objects.create(
            page=self.article, dossier=self.carnet, sujet="verdicts",
        )
        self.client.force_login(self.proprietaire)

    def test_le_paragraphe_porte_un_title_qui_NOMME_son_etat(self):
        """Une couleur ne se lit pas toute seule."""
        from front.views_synthese import _html_avec_renvois

        html = _html_avec_renvois(self.article)
        self.assertIn('class="affirmation"', html)
        self.assertIn("title=", html)
        # Sans citation, l'article est « non sourcé » : le mot doit y etre.
        self.assertIn("Non sourcé", html)

    def test_la_legende_n_annonce_que_les_etats_presents(self):
        """Elle promettait « non sourcé » avant toute vérification."""
        reponse = self.client.get(
            f"/wikis/{self.article.wiki.pk}/", HTTP_HX_REQUEST="true",
        )
        contenu = reponse.content.decode()
        self.assertIn("synthese-legende", contenu)
        # Cet article n'a aucune citation : « non sourcé » est legitime,
        # mais « vérifié » ne doit PAS etre annonce.
        self.assertIn("non sourcé", contenu)
        self.assertNotIn("vérifié (verbatim + implication)", contenu)

    def test_le_verdict_se_porte_a_gauche_et_non_en_soulignement(self):
        """Un filet bas se lit comme une separation, pas comme un etat."""
        from pathlib import Path

        from django.conf import settings

        design = (
            Path(settings.BASE_DIR) / "front" / "templates" / "front"
            / "corpus" / "_style_maquette.html"
        ).read_text(encoding="utf-8")
        self.assertIn(
            '.zone-corpus .affirmation[data-verification="verifie"]'
            "     { border-left-color:var(--verifie); }",
            design,
        )


class LibellesDesTachesTest(TestCase):
    """F8 — trois actions distinctes ne peuvent pas se lire pareil."""

    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            "proprio_taches", "pt@exemple.test", "motdepasse123",
        )
        self.page = Page.objects.create(
            title="Wiki — libellés", type_de_note=TypeDeNote.WIKI,
            owner=self.utilisateur, content_hash="hash-libelles",
            html_readability="<p>x</p>", text_readability="x",
            html_original="",
        )
        self.client.force_login(self.utilisateur)

    def _job(self, marqueur):
        from hypostasis_extractor.models import ExtractionJob

        return ExtractionJob.objects.create(
            page=self.page, name="peu importe", status="completed",
            raw_result={marqueur: True},
        )

    def test_les_trois_actions_d_un_article_se_distinguent(self):
        self._job("est_wiki")
        self._job("est_maj_wiki")
        self._job("est_verification")
        reponse = self.client.get("/taches/dropdown/", HTTP_HX_REQUEST="true")
        contenu = reponse.content.decode()
        for libelle in ("Wiki", "Mise à jour", "Vérification"):
            self.assertIn(libelle, contenu, f"« {libelle} » ne s'affiche pas")

    def test_le_panneau_des_taches_porte_ses_accents(self):
        """Seul endroit de l'interface qui n'en avait pas."""
        self._job("est_wiki")
        contenu = self.client.get(
            "/taches/dropdown/", HTTP_HX_REQUEST="true",
        ).content.decode()
        self.assertIn("Mes tâches récentes", contenu)
        self.assertNotIn("Mes taches recentes", contenu)


class TitreDeLOngletTest(TestCase):
    """F9 — le titre disait « Bibliothèque » partout."""

    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            "proprio_titre", "ptit@exemple.test", "motdepasse123",
        )
        self.carnet = Dossier.objects.create(
            name="Carnet nommé", owner=self.utilisateur,
            visibilite=VisibiliteDossier.PRIVE,
        )
        self.client.force_login(self.utilisateur)

    def test_le_carnet_donne_son_nom_a_l_onglet(self):
        reponse = self.client.get(f"/carnets/{self.carnet.pk}/")
        self.assertIn(
            "<title>Carnet nommé — Hypostasia</title>",
            reponse.content.decode(),
        )

    def test_la_liste_des_carnets_se_nomme(self):
        reponse = self.client.get("/carnets/")
        self.assertIn("<title>Carnets — Hypostasia</title>",
                      reponse.content.decode())


class MoteurAnnonceTest(TestCase):
    """F10 — à défaut de choisir le moteur, l'écran le nomme."""

    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            "proprio_moteur", "pm@exemple.test", "motdepasse123",
        )
        self.carnet = Dossier.objects.create(
            name="Carnet du moteur", owner=self.utilisateur,
            visibilite=VisibiliteDossier.PRIVE,
        )
        self.client.force_login(self.utilisateur)

    def test_l_ecran_de_creation_nomme_le_modele(self):
        configuration = Configuration.get_solo()
        if configuration.ai_model is None:
            self.skipTest("aucun modele configure dans cet environnement")
        reponse = self.client.get(
            f"/carnets/{self.carnet.pk}/wikis/", HTTP_HX_REQUEST="true",
        )
        contenu = reponse.content.decode()
        self.assertIn("synthese-moteur-annonce", contenu)
        self.assertIn(configuration.ai_model.name, contenu)


class UrlDesArticlesTest(TestCase):
    """F4 — lire un article doit changer l'URL."""

    def test_les_listes_poussent_l_url_de_l_article(self):
        from pathlib import Path

        from django.conf import settings

        dossier = (
            Path(settings.BASE_DIR) / "front" / "templates" / "front" / "corpus"
        )
        for nom, attendu in (
            ("liste_wikis.html", 'hx-push-url="/wikis/{{ wiki.pk }}/"'),
            ("liste_syntheses.html",
             'hx-push-url="/syntheses/{{ synthese.page_id }}/"'),
        ):
            contenu = (dossier / nom).read_text(encoding="utf-8")
            self.assertIn(attendu, contenu,
                          f"{nom} ne pousse pas l'URL de l'article")
