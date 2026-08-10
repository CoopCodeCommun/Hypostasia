"""
Tests du rendu de lecture par elements — SPEC v2 phase I.
/ Tests for the element-based reading render — SPEC v2 phase I.

LOCALISATION : front/tests/test_rendu_elements.py

Lancer avec :
    docker exec hypostasia_dev_web uv run python manage.py test \\
        front.tests.test_rendu_elements
"""

from django.test import TestCase

from core.models import ElementDocument, Page, empreinte_du_texte
from front.services.rendu_elements import (
    MAXIMUM_DE_MARQUES_PAR_ELEMENT,
    MAXIMUM_D_IDEES_SUPERPOSEES,
    construire_les_blocs_de_lecture,
    construire_les_segments,
    rendre_le_texte_d_un_element,
)
from hypostasis_extractor.models import (
    AncrageExtraction,
    EtatAncrage,
    ExtractedEntity,
    ExtractionJob,
    ExtractionJobStatus,
)


class BaseRenduTestCase(TestCase):
    """Socle commun. / Common ground."""

    def setUp(self):
        self.page_de_test = Page.objects.create(
            url="http://exemple.local/page-rendu",
            html_original="x", html_readability="x", text_readability="x",
            content_hash="empreinte_rendu",
        )
        self.job = ExtractionJob.objects.create(
            page=self.page_de_test, name="Job de rendu",
            prompt_description="Extraire",
            status=ExtractionJobStatus.COMPLETED,
        )
        self.prochain_ordre = 0

    def _ajouter_un_element(self, texte, label="text", masque=False):
        element = ElementDocument.objects.create(
            page=self.page_de_test, ordre=self.prochain_ordre, label=label,
            texte=texte, empreinte_contenu=empreinte_du_texte(texte),
            masque=masque,
        )
        self.prochain_ordre += 1
        return element

    def _ancrer(self, element, debut, fin, statut="nouveau", ordre=0,
                etat=EtatAncrage.ANCREE, masquee=False):
        extraction = ExtractedEntity.objects.create(
            job=self.job, extraction_text=element.texte[debut:fin],
            start_char=debut, end_char=fin, statut_debat=statut,
            masquee=masquee,
        )
        return AncrageExtraction.objects.create(
            extraction=extraction, element=element,
            ordre_dans_extraction=ordre,
            debut_dans_element=debut, fin_dans_element=fin,
            etat_ancrage=etat,
        )


class DecoupageEnSegmentsTest(TestCase):
    """
    L'algorithme de decoupage, teste seul.
    / The cutting algorithm, tested alone.
    """

    class FausseP:
        """Une portion minimale, sans base de donnees."""
        compteur = 0

        def __init__(self, debut, fin):
            self.debut_dans_element = debut
            self.fin_dans_element = fin
            DecoupageEnSegmentsTest.FausseP.compteur += 1
            self.pk = DecoupageEnSegmentsTest.FausseP.compteur

    def test_un_texte_sans_portion_donne_un_seul_segment(self):
        segments = construire_les_segments(30, [])

        self.assertEqual(segments, [(0, 30, [])])

    def test_une_portion_donne_trois_segments(self):
        portion = self.FausseP(10, 20)

        segments = construire_les_segments(30, [portion])

        self.assertEqual([(d, f) for d, f, _ in segments],
                         [(0, 10), (10, 20), (20, 30)])
        self.assertEqual(segments[0][2], [])
        self.assertEqual(segments[1][2], [portion])
        self.assertEqual(segments[2][2], [])

    def test_deux_portions_qui_se_croisent(self):
        """
        Le cas qu'aucune imbrication ne peut representer : A finit apres
        que B ait commence. Trois segments, dont un partage.
        / The case no nesting can express.
        """
        a = self.FausseP(0, 20)
        b = self.FausseP(10, 30)

        segments = construire_les_segments(30, [a, b])

        self.assertEqual([(d, f) for d, f, _ in segments],
                         [(0, 10), (10, 20), (20, 30)])
        self.assertEqual(segments[0][2], [a])
        self.assertEqual(set(segments[1][2]), {a, b})
        self.assertEqual(segments[2][2], [b])

    def test_la_plus_large_vient_en_premier(self):
        """
        L'ordre d'imbrication doit etre le meme d'un rendu a l'autre :
        la balise englobante s'ouvre en premier.
        / Deterministic nesting: the widest opens first.
        """
        large = self.FausseP(0, 30)
        etroite = self.FausseP(10, 20)

        segments = construire_les_segments(30, [large, etroite])

        segment_partage = [s for s in segments if len(s[2]) == 2][0]
        self.assertEqual(segment_partage[2][0], large)
        self.assertEqual(segment_partage[2][1], etroite)

    def test_les_bornes_hors_texte_sont_rognees(self):
        """
        Une portion qui deborde — edition non reconciliee, bug ailleurs —
        ne doit pas faire echouer l'affichage de toute la page.
        / An out-of-range portion must not break the whole page.
        """
        portion = self.FausseP(5, 9999)

        segments = construire_les_segments(20, [portion])

        self.assertEqual(segments[-1][1], 20)
        self.assertTrue(all(fin <= 20 for _d, fin, _p in segments))

    def test_une_portion_vide_est_ignoree(self):
        portion = self.FausseP(10, 10)

        segments = construire_les_segments(30, [portion])

        self.assertEqual(segments, [(0, 30, [])])

    def test_un_texte_vide_ne_donne_aucun_segment(self):
        self.assertEqual(construire_les_segments(0, []), [])

    def test_les_segments_recouvrent_exactement_le_texte(self):
        """
        L'INVARIANT CENTRAL : mis bout a bout, les segments redonnent le
        texte d'origine, sans trou ni doublon. Si cet invariant tombe, le
        document affiche n'est plus le document.
        / The central invariant: segments reconstitute the exact text.
        """
        texte = "".join(str(numero % 10) for numero in range(60))
        jeux_de_portions = [
            [],
            [self.FausseP(0, 60)],
            [self.FausseP(10, 20), self.FausseP(10, 20)],      # identiques
            [self.FausseP(0, 30), self.FausseP(10, 20)],       # imbriquees
            [self.FausseP(0, 20), self.FausseP(10, 30)],       # croisees
            [self.FausseP(50, 10)],                            # inversee
            [self.FausseP(-5, 15)],                            # negative
            [self.FausseP(40, 999)],                           # hors bornes
            [self.FausseP(30, 40), self.FausseP(0, 10)],       # non triees
        ]

        for portions in jeux_de_portions:
            segments = construire_les_segments(len(texte), portions)
            reconstitue = "".join(texte[debut:fin] for debut, fin, _p in segments)
            self.assertEqual(
                reconstitue, texte,
                f"reconstitution fausse pour {len(portions)} portion(s)",
            )

    def test_deux_portions_aux_bornes_identiques(self):
        """
        1 387 cas reels en base : deux extractions au meme endroit exact.
        Elles doivent donner UN segment portant les DEUX portions.
        / 1 387 real cases: two extractions at the exact same place.
        """
        premiere = self.FausseP(10, 20)
        seconde = self.FausseP(10, 20)

        segments = construire_les_segments(30, [premiere, seconde])

        segment_du_milieu = segments[1]
        self.assertEqual((segment_du_milieu[0], segment_du_milieu[1]), (10, 20))
        self.assertEqual(len(segment_du_milieu[2]), 2)

    def test_une_portion_rognee_couvre_bien_ce_qui_reste(self):
        """
        Rogner, ce n'est pas jeter : la partie qui tient dans le texte
        doit rester surlignee.
        / Clamping is not discarding: what fits must stay highlighted.
        """
        portion = self.FausseP(5, 9999)

        segments = construire_les_segments(20, [portion])

        segment_couvert = [s for s in segments if s[2]][0]
        self.assertEqual((segment_couvert[0], segment_couvert[1]), (5, 20))
        self.assertEqual(segment_couvert[2], [portion])

    def test_un_texte_d_un_seul_caractere(self):
        portion = self.FausseP(0, 1)

        segments = construire_les_segments(1, [portion])

        self.assertEqual(segments, [(0, 1, [portion])])


class RenduDuTexteTest(BaseRenduTestCase):
    """Le HTML produit. / The produced HTML."""

    def test_un_element_sans_idee_rend_son_texte_nu(self):
        element = self._ajouter_un_element("Un paragraphe ordinaire.")

        html = rendre_le_texte_d_un_element(element, [])

        self.assertEqual(html, "Un paragraphe ordinaire.")
        self.assertNotIn("<mark", html)

    def test_une_idee_pose_une_balise(self):
        element = self._ajouter_un_element("Le jugement des personnes.")
        portion = self._ancrer(element, 3, 11)

        html = rendre_le_texte_d_un_element(element, [portion])

        self.assertIn('<mark class="portion hl-extraction"', html)
        self.assertIn(">jugement</mark>", html)
        self.assertIn('data-superposition="1"', html)

    def test_les_caracteres_dangereux_sont_echappes(self):
        """
        element.texte est du texte brut. Sans echappement, un document
        contenant du HTML l'executerait dans la page.
        / Without escaping, a document containing HTML would run it.
        """
        element = self._ajouter_un_element(
            "Le script <script>alert(1)</script> et l'esperluette & ici.",
        )

        html = rendre_le_texte_d_un_element(element, [])

        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("&amp;", html)

    def test_l_echappement_ne_decale_pas_les_positions(self):
        """
        Le piege : echapper le texte AVANT de le decouper decalerait tout,
        puisque & devient &amp;. On echappe donc chaque segment APRES
        l'avoir decoupe.
        / Escaping before cutting would shift every offset.
        """
        element = self._ajouter_un_element("A & B puis jugement final.")
        # « jugement » commence au caractere 11 du texte BRUT.
        self.assertEqual(element.texte[11:19], "jugement")
        portion = self._ancrer(element, 11, 19)

        html = rendre_le_texte_d_un_element(element, [portion])

        self.assertIn(">jugement</mark>", html)
        self.assertIn("&amp;", html)

    def test_deux_idees_qui_se_croisent_donnent_du_html_bien_forme(self):
        """
        Chaque balise s'ouvre et se ferme dans le meme segment : le HTML
        reste valide meme quand les intervalles se croisent.
        / Every tag opens and closes within one segment.
        """
        element = self._ajouter_un_element("AAAAAAAAAABBBBBBBBBBCCCCCCCCCC")
        premiere = self._ancrer(element, 0, 20)
        seconde = self._ancrer(element, 10, 30)

        html = rendre_le_texte_d_un_element(element, [premiere, seconde])

        self.assertEqual(html.count("<mark"), html.count("</mark>"))
        # Le segment partage porte deux balises.
        # / The shared segment carries two tags.
        self.assertIn('data-superposition="2"', html)

    def test_au_dela_du_plafond_on_cesse_d_empiler(self):
        """
        Une page migree porte un element de 2 469 portions. Empiler
        autant de balises rendrait le texte illisible et le DOM absurde.
        / Stacking thousands of tags would help no one.
        """
        element = self._ajouter_un_element("A" * 50)
        portions = [
            self._ancrer(element, 0, 50, ordre=numero)
            for numero in range(MAXIMUM_D_IDEES_SUPERPOSEES + 3)
        ]

        html = rendre_le_texte_d_un_element(element, portions)

        self.assertEqual(html.count("<mark"), MAXIMUM_D_IDEES_SUPERPOSEES)
        self.assertEqual(html.count("</mark>"), MAXIMUM_D_IDEES_SUPERPOSEES)

    def test_au_dela_du_volume_le_texte_est_rendu_nu(self):
        """
        Le plafond de profondeur ne borne pas le NOMBRE de segments.
        Mesure sur l'element pathologique issu de la bascule : 4 876
        segments, 8 158 marques, 1,4 Mo de HTML par affichage. Au-dela
        d'un certain volume, le surlignage n'aide plus personne.
        / The depth cap does not bound the NUMBER of segments.
        """
        element = self._ajouter_un_element("z" * 4000)
        portions = [
            self._ancrer(element, numero * 4, numero * 4 + 3, ordre=0)
            for numero in range(MAXIMUM_DE_MARQUES_PAR_ELEMENT + 50)
        ]

        html = rendre_le_texte_d_un_element(element, portions)

        self.assertNotIn("<mark", html)
        # Le texte, lui, est bien rendu — et echappe.
        # / The text itself is rendered, and escaped.
        self.assertEqual(html, "z" * 4000)

    def test_le_bloc_dit_combien_d_idees_ne_sont_pas_surlignees(self):
        """
        Rendre le texte nu SANS le dire laisse le lecteur devant une page
        ou rien n'est surligne, sans moyen de savoir que des centaines
        d'idees s'y rattachent. Constate au navigateur sur /lire/419/
        apres la reconversion : 623 ancres, zero marque, aucun message.
        Le code promettait pourtant de « le dire dans le bloc » — il n'en
        faisait qu'un logger.warning, invisible pour qui lit la page.
        / Rendering plain text silently leaves the reader with no clue.
        """
        element = self._ajouter_un_element("z" * 4000)
        for numero in range(MAXIMUM_DE_MARQUES_PAR_ELEMENT + 50):
            self._ancrer(element, numero * 4, numero * 4 + 3, ordre=0)

        blocs = construire_les_blocs_de_lecture(self.page_de_test)

        bloc = next(
            bloc for bloc in blocs if bloc["element"].pk == element.pk
        )
        self.assertEqual(
            bloc["idees_non_surlignees"],
            MAXIMUM_DE_MARQUES_PAR_ELEMENT + 50,
        )

    def test_un_bloc_normal_n_annonce_aucune_idee_non_surlignee(self):
        element = self._ajouter_un_element("z" * 400)
        self._ancrer(element, 0, 3, ordre=0)

        blocs = construire_les_blocs_de_lecture(self.page_de_test)

        bloc = next(
            bloc for bloc in blocs if bloc["element"].pk == element.pk
        )
        self.assertEqual(bloc["idees_non_surlignees"], 0)

    def test_sous_le_plafond_le_surlignage_reste(self):
        """Contre-epreuve : le plafond ne se declenche pas pour rien."""
        element = self._ajouter_un_element("z" * 400)
        portions = [
            self._ancrer(element, numero * 4, numero * 4 + 3, ordre=0)
            for numero in range(20)
        ]

        html = rendre_le_texte_d_un_element(element, portions)

        self.assertEqual(html.count("<mark"), 20)

    def test_la_superposition_annoncee_est_la_vraie(self):
        """
        Meme quand on ne balise que les 4 plus larges, l'attribut doit
        dire combien d'idees sont REELLEMENT la : l'affichage doit
        pouvoir annoncer « 7 idees ici ».
        / The attribute reports the real count, not the drawn one.
        """
        element = self._ajouter_un_element("A" * 40)
        portions = [
            self._ancrer(element, 0, 40 - numero, ordre=numero)
            for numero in range(MAXIMUM_D_IDEES_SUPERPOSEES + 3)
        ]

        html = rendre_le_texte_d_un_element(element, portions)

        self.assertIn(
            f'data-superposition="{MAXIMUM_D_IDEES_SUPERPOSEES + 3}"', html,
        )

    def test_le_cap_garde_les_plus_larges(self):
        """
        Quand on ecrete, on garde les idees les plus englobantes : ce sont
        celles qui portent le sens le plus large.
        / When capping, the widest ideas survive.
        """
        element = self._ajouter_un_element("B" * 40)
        la_plus_large = self._ancrer(element, 0, 40, ordre=0)
        portions = [la_plus_large] + [
            self._ancrer(element, 10, 10 + numero, ordre=numero + 1)
            for numero in range(1, MAXIMUM_D_IDEES_SUPERPOSEES + 3)
        ]

        html = rendre_le_texte_d_un_element(element, portions)

        self.assertIn(
            f'data-extraction-id="{la_plus_large.extraction_id}"', html,
        )

    def test_le_rendu_est_du_html_sur(self):
        """mark_safe doit s'appliquer, sinon le template echapperait tout."""
        from django.utils.safestring import SafeString

        element = self._ajouter_un_element("Un texte quelconque.")

        html = rendre_le_texte_d_un_element(element, [])

        self.assertIsInstance(html, SafeString)

    def test_un_statut_forge_ne_sort_pas_de_l_attribut(self):
        """
        statut_debat vient de la base. S'il portait un jour du texte
        libre, il ne doit pas pouvoir fermer l'attribut et injecter.
        / Even a forged status must not break out of the attribute.

        Le champ est limite a 20 caracteres, ce qui reduit deja la
        surface — mais la longueur n'est pas une protection : on echappe.
        / The 20-char limit is not a protection; escaping is.
        """
        element = self._ajouter_un_element("Un passage.")
        portion = self._ancrer(element, 0, 8)
        portion.extraction.statut_debat = '"><b onload=x>'
        portion.extraction.save(update_fields=["statut_debat"])
        portion.refresh_from_db()

        html = rendre_le_texte_d_un_element(element, [portion])

        # L'attribut n'est pas ferme : le guillemet est echappe.
        # / The attribute is not closed: the quote is escaped.
        self.assertNotIn('"><b', html)
        self.assertIn("&quot;&gt;&lt;b", html)

    def test_le_statut_de_l_idee_est_porte_par_la_balise(self):
        """C'est lui qui donne sa couleur au soulignement."""
        element = self._ajouter_un_element("Un passage debattu ici.")
        portion = self._ancrer(element, 3, 18, statut="commente")

        html = rendre_le_texte_d_un_element(element, [portion])

        self.assertIn('data-statut="commente"', html)


class BlocsDeLectureTest(BaseRenduTestCase):
    """La liste de blocs rendue au template. / The block list for the template."""

    def test_les_blocs_suivent_l_ordre_du_document(self):
        self._ajouter_un_element("Premier")
        self._ajouter_un_element("Deuxieme")

        blocs = construire_les_blocs_de_lecture(self.page_de_test)

        self.assertEqual(
            [bloc["element"].texte for bloc in blocs], ["Premier", "Deuxieme"],
        )

    def test_chaque_label_a_sa_balise(self):
        self._ajouter_un_element("Un titre", label="title")
        self._ajouter_un_element("Un sous-titre", label="section_header")
        self._ajouter_un_element("Du texte", label="text")
        self._ajouter_un_element("Un label inconnu", label="chose_inconnue")

        blocs = construire_les_blocs_de_lecture(self.page_de_test)

        self.assertEqual(
            [bloc["balise"] for bloc in blocs], ["h2", "h3", "p", "p"],
        )

    def test_les_puces_consecutives_sont_regroupees(self):
        """
        Un <li> hors d'un <ul> n'est pas du HTML valide.
        / A <li> outside a <ul> is invalid HTML.
        """
        self._ajouter_un_element("Une intro", label="text")
        self._ajouter_un_element("Premiere puce", label="list_item")
        self._ajouter_un_element("Deuxieme puce", label="list_item")
        self._ajouter_un_element("Un paragraphe apres", label="text")

        blocs = construire_les_blocs_de_lecture(self.page_de_test)

        self.assertEqual(len(blocs), 3)
        self.assertFalse(blocs[0]["est_une_liste"])
        self.assertTrue(blocs[1]["est_une_liste"])
        self.assertEqual(len(blocs[1]["puces"]), 2)
        self.assertFalse(blocs[2]["est_une_liste"])

    def test_deux_listes_separees_ne_fusionnent_pas(self):
        self._ajouter_un_element("Puce A", label="list_item")
        self._ajouter_un_element("Un paragraphe entre les deux", label="text")
        self._ajouter_un_element("Puce B", label="list_item")

        blocs = construire_les_blocs_de_lecture(self.page_de_test)

        listes = [bloc for bloc in blocs if bloc.get("est_une_liste")]
        self.assertEqual(len(listes), 2)

    def test_le_compteur_compte_les_idees_pas_les_portions(self):
        """
        Une idee coupee en deux morceaux dans le meme element reste UNE
        idee. / One idea split in two is still one idea.
        """
        element = self._ajouter_un_element("AAAA BBBB CCCC DDDD")
        extraction = ExtractedEntity.objects.create(
            job=self.job, extraction_text="deux morceaux",
            start_char=0, end_char=4,
        )
        for numero, (debut, fin) in enumerate([(0, 4), (10, 14)]):
            AncrageExtraction.objects.create(
                extraction=extraction, element=element,
                ordre_dans_extraction=numero,
                debut_dans_element=debut, fin_dans_element=fin,
            )

        blocs = construire_les_blocs_de_lecture(self.page_de_test)

        self.assertEqual(blocs[0]["nombre_d_idees"], 1)

    def test_une_portion_detachee_n_est_pas_rendue(self):
        """
        Ses offsets ne designent plus rien de sur. La poser quand meme
        surlignerait un passage au hasard.
        / Its offsets are meaningless; drawing it would highlight at random.
        """
        element = self._ajouter_un_element("Le jugement des personnes.")
        self._ancrer(element, 3, 11, etat=EtatAncrage.DETACHEE)

        blocs = construire_les_blocs_de_lecture(self.page_de_test)

        self.assertNotIn("<mark", blocs[0]["html_du_texte"])
        self.assertEqual(blocs[0]["nombre_d_idees"], 0)

    def test_une_idee_masquee_n_est_pas_rendue(self):
        """Masquee par la curation : elle ne se voit plus."""
        element = self._ajouter_un_element("Le jugement des personnes.")
        self._ancrer(element, 3, 11, masquee=True)

        blocs = construire_les_blocs_de_lecture(self.page_de_test)

        self.assertNotIn("<mark", blocs[0]["html_du_texte"])

    def test_un_element_masque_est_signale(self):
        """Le template le rendra barre et grise, mais il reste affiche."""
        self._ajouter_un_element("Du bruit invente.", masque=True)

        blocs = construire_les_blocs_de_lecture(self.page_de_test)

        self.assertTrue(blocs[0]["est_masque"])

    def test_une_page_sans_element_ne_rend_aucun_bloc(self):
        self.assertEqual(construire_les_blocs_de_lecture(self.page_de_test), [])

    def test_le_rendu_ne_fait_que_deux_requetes(self):
        """
        Une page peut porter 650 elements. Lire ses portions element par
        element ferait 650 requetes.
        / Reading portions per element would mean 650 queries.
        """
        for numero in range(12):
            element = self._ajouter_un_element(f"Paragraphe numero {numero}.")
            self._ancrer(element, 0, 9)

        with self.assertNumQueries(2):
            construire_les_blocs_de_lecture(self.page_de_test)
