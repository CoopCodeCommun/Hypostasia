"""
La liste des wikis d'un carnet dit lesquels ont du neuf.
/ The notebook's wiki list says which wikis have news.

LOCALISATION : front/tests/test_la_liste_des_wikis_signale_le_neuf.py

SPEC-synthese, addendum du 21 septembre 2026. Un wiki ne se met a jour
que par le geste « Mettre a jour » de son article. Ce geste n'a de sens
que si le perimetre a recu quelque chose depuis le dernier tour — et
c'est la liste du carnet qui doit le dire, sans ouvrir les wikis un par
un.

Le compte est LE MEME que celui de l'en-tete de l'article
(`nouveautes_du_perimetre` depuis `derniere_mise_a_jour`) : les deux
ecrans ne doivent jamais se contredire.
/ Same count as the article header: the two screens must agree.
"""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from core.models import Page, TypeDeNote, Wiki
from core.services.corpus import ranger_une_note_dans_un_carnet
from front.tests.test_synthese_phase_c import creer_fixtures_phase_c
from hypostasis_extractor.models import ExtractedEntity


class LaListeDesWikisSignaleLeNeufTest(TestCase):
    """Un wiki, et ce qui arrive (ou non) dans son perimetre."""

    def setUp(self):
        self.fixtures = creer_fixtures_phase_c()
        self.client.login(username="demandeur_synthese", password="test1234")

        page_du_wiki = Page.objects.create(
            title="Wiki seuil", text_readability="## Le seuil\n\nActé.\n",
            html_readability="<p>w</p>", html_original="<p>w</p>",
            content_hash="hash-liste-neuf", type_de_note=TypeDeNote.WIKI,
            owner=self.fixtures["demandeur"],
        )
        ranger_une_note_dans_un_carnet(
            page_du_wiki, self.fixtures["carnet"], self.fixtures["demandeur"],
        )
        self.wiki = Wiki.objects.create(
            page=page_du_wiki, dossier=self.fixtures["carnet"],
            sujet="Le seuil",
        )
        # Le dernier tour date d'une heure : tout ce que les fixtures ont
        # cree AVANT lui n'est pas du neuf. `derniere_mise_a_jour` est un
        # auto_now, on passe donc par update() pour le poser.
        # / The last round is one hour old; auto_now forces update().
        self.date_du_dernier_tour = timezone.now() - timedelta(hours=1)
        Wiki.objects.filter(pk=self.wiki.pk).update(
            derniere_mise_a_jour=self.date_du_dernier_tour,
        )
        ExtractedEntity.objects.filter(
            job__page=self.fixtures["note_source"],
        ).update(created_at=self.date_du_dernier_tour - timedelta(hours=1))

    def _lire_la_liste(self):
        reponse = self.client.get(
            f"/carnets/{self.fixtures['carnet'].pk}/wikis/",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 200)
        return reponse.content.decode()

    def _une_extraction_arrivee_apres_le_tour(self, masquee=False):
        extraction_de_reference = self.fixtures["extraction_seuil"]
        return ExtractedEntity.objects.create(
            job=extraction_de_reference.job, extraction_class="donnee",
            extraction_text="Un fait arrivé après le tour.",
            start_char=0, end_char=10, masquee=masquee,
        )

    def test_une_extraction_neuve_est_annoncee_avec_sa_date(self):
        self._une_extraction_arrivee_apres_le_tour()

        contenu = self._lire_la_liste()

        self.assertIn('data-testid="synthese-wiki-nouveautes"', contenu)
        self.assertIn('data-neuf="oui"', contenu)
        # La chaine ENTIERE : la meme date apparait deja dans « mis a jour
        # le … » de la ligne, elle ne prouverait rien seule.
        # / The full string: the date alone already appears on the line.
        date_du_tour = timezone.localtime(
            self.date_du_dernier_tour,
        ).strftime("%d/%m/%Y")
        self.assertIn(f"1 nouveauté depuis le {date_du_tour}", contenu)

    def test_sans_rien_de_neuf_la_ligne_le_dit(self):
        contenu = self._lire_la_liste()

        self.assertIn('data-testid="synthese-wiki-nouveautes"', contenu)
        self.assertIn('data-neuf="non"', contenu)
        self.assertIn("rien de neuf", contenu)

    def test_une_extraction_masquee_n_est_pas_du_neuf(self):
        # Une extraction masquee a ete ecartee par un humain : la
        # compter proposerait de relancer une production sur ce qu'il a
        # retire. / Curated-out extractions are not news.
        self._une_extraction_arrivee_apres_le_tour(masquee=True)

        contenu = self._lire_la_liste()

        self.assertIn('data-neuf="non"', contenu)
        self.assertIn("rien de neuf", contenu)

    def test_la_liste_et_l_article_donnent_le_meme_compte(self):
        self._une_extraction_arrivee_apres_le_tour()
        self._une_extraction_arrivee_apres_le_tour()

        liste = self._lire_la_liste()
        article = self.client.get(
            f"/wikis/{self.wiki.pk}/", HTTP_HX_REQUEST="true",
        ).content.decode()

        self.assertIn("2 nouveautés depuis le", liste)
        self.assertIn("2 nouveautés dans le périmètre", article)
