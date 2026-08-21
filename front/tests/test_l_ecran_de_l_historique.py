"""
L'ecran qui donne l'histoire d'un wiki a lire.
/ The screen that makes a wiki's history readable.

LOCALISATION : front/tests/test_l_ecran_de_l_historique.py

SPEC-synthese, addendum du 21 aout 2026. Ce qui doit se lire sans
cliquer ailleurs : qui a fait le tour (un humain, ou le moteur), ce
qui a ete ajoute, ce qui a DISPARU pour un remplacement (§ 6.4), et ce
qui a ete refuse — avec son motif.
/ Who, what was added, what vanished, and what was refused.
"""

from unittest.mock import patch

from django.test import TestCase

from core.models import (
    MotifDeTourDeWiki, OperationDeWiki, Page, TourDeWiki, TypeDeNote, Wiki,
)
from core.services.corpus import ranger_une_note_dans_un_carnet
from front.tests.test_synthese_phase_c import creer_fixtures_phase_c


class EcranDeLHistoriqueTest(TestCase):
    """GET /wikis/{id}/historique/ — le partial. / The partial."""

    def setUp(self):
        self.fixtures = creer_fixtures_phase_c()
        self.page_du_wiki = Page.objects.create(
            title="Wiki à historique",
            text_readability="## Le seuil\n\nActé.\n",
            html_readability="<p>w</p>", html_original="<p>w</p>",
            content_hash="hash-ecran-histo", type_de_note=TypeDeNote.WIKI,
            owner=self.fixtures["demandeur"],
        )
        ranger_une_note_dans_un_carnet(
            self.page_du_wiki, self.fixtures["carnet"],
            self.fixtures["demandeur"],
        )
        self.wiki = Wiki.objects.create(
            page=self.page_du_wiki, dossier=self.fixtures["carnet"],
            sujet="Le seuil",
        )
        self.client.login(
            username="demandeur_synthese", password="test1234",
        )

    def _un_tour(self, fait_par=None, motif=MotifDeTourDeWiki.MAJ_NOCTURNE):
        return TourDeWiki.objects.create(
            wiki=self.wiki, numero_de_tour=2, fait_par=fait_par,
            motif=motif,
            texte_avant="## Le seuil\n\nAvant.\n",
            texte_apres="## Le seuil\n\nAvant. Et après.\n",
            extractions_nouvelles=3, commentaires_nouveaux=1,
        )

    def test_un_tour_du_moteur_est_annonce_comme_tel(self):
        self._un_tour(fait_par=None)

        reponse = self.client.get(f"/wikis/{self.wiki.pk}/historique/")

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, 'data-par-le-moteur="oui"')
        self.assertContains(reponse, "le moteur, automatiquement")

    def test_un_tour_humain_nomme_son_auteur(self):
        self._un_tour(
            fait_par=self.fixtures["demandeur"],
            motif=MotifDeTourDeWiki.MAJ_MANUELLE,
        )

        reponse = self.client.get(f"/wikis/{self.wiki.pk}/historique/")

        self.assertContains(reponse, 'data-par-le-moteur="non"')
        self.assertContains(reponse, "demandeur_synthese")

    def test_la_raison_chiffree_est_lisible(self):
        tour = self._un_tour()
        from django.utils import timezone
        tour.depuis = timezone.now()
        tour.save(update_fields=["depuis"])

        reponse = self.client.get(f"/wikis/{self.wiki.pk}/historique/")

        self.assertContains(reponse, "3 nouvelles extractions,")
        self.assertContains(reponse, "1 nouveau commentaire")

    def test_un_remplacement_montre_ce_qui_a_disparu(self):
        # § 6.4 : sans l'avant, l'ecran ferait approuver une reecriture
        # sans montrer ce qu'elle efface.
        # / Without the before, a rewrite hides what it erased.
        tour = self._un_tour()
        OperationDeWiki.objects.create(
            tour=tour, indice=0, type_d_operation="replace_section",
            section="Le seuil", appliquee=True,
            contenu="Le texte neuf.",
            ancien_contenu="Le texte que le tour a effacé.",
        )

        reponse = self.client.get(f"/wikis/{self.wiki.pk}/historique/")

        self.assertContains(reponse, "Le texte neuf.")
        self.assertContains(reponse, "Le texte que le tour a effacé.")

    def test_les_marqueurs_ne_sont_pas_montres_au_lecteur(self):
        # Les marqueurs [[ext:N]] sont la VERITE du sourcage et restent
        # stockes ; a l'ecran, ils ne disent rien a personne — le compte
        # de preuves le dit mieux.
        # / Markers stay stored, but say nothing on screen.
        tour = self._un_tour()
        OperationDeWiki.objects.create(
            tour=tour, indice=0, type_d_operation="append_to_section",
            section="Le seuil", appliquee=True,
            contenu="Un fait sourcé.[[ext:4242]]",
        )

        reponse = self.client.get(f"/wikis/{self.wiki.pk}/historique/")

        self.assertContains(reponse, "Un fait sourcé.")
        self.assertNotContains(reponse, "[[ext:")

    def test_un_rejet_est_montre_avec_son_motif(self):
        tour = self._un_tour()
        OperationDeWiki.objects.create(
            tour=tour, indice=0, type_d_operation="append_to_section",
            section="Une section inventée", appliquee=False,
            contenu="Le contenu que personne n'a voulu.",
            motif_de_rejet="Cette section n'existe pas dans l'article.",
        )

        reponse = self.client.get(f"/wikis/{self.wiki.pk}/historique/")

        self.assertContains(reponse, "Refusé")
        self.assertContains(
            reponse, "Cette section n&#x27;existe pas dans l&#x27;article.",
        )
        # Le contenu refuse est CONSERVE et montre (§ 6.2).
        # / Rejected content is kept and shown.
        self.assertContains(reponse, "Le contenu que personne n")

    def test_un_wiki_sans_histoire_le_dit(self):
        reponse = self.client.get(f"/wikis/{self.wiki.pk}/historique/")

        self.assertContains(reponse, "pas encore d'histoire")

    def test_l_ecran_d_article_porte_le_depliant(self):
        with patch("front.views_synthese.contexte_d_une_preuve"):
            reponse = self.client.get(
                f"/wikis/{self.wiki.pk}/", HTTP_HX_REQUEST="true",
            )

        self.assertContains(reponse, 'data-testid="synthese-historique-bloc"')
        self.assertContains(reponse, f"/wikis/{self.wiki.pk}/historique/")

    def test_un_inconnu_ne_lit_pas_l_historique(self):
        # Le meme refus que le reste de l'ecran article
        # (`_acces_article_ou_refus`) : l'histoire d'un article n'est
        # pas plus publique que l'article.
        # / The same gate as the article screen itself.
        self.client.logout()

        reponse = self.client.get(f"/wikis/{self.wiki.pk}/historique/")

        self.assertEqual(reponse.status_code, 403)
