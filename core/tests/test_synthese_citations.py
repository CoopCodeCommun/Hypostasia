"""
Tests du lien de citation (phase B synthese).
/ Citation link tests (synthesis phase B).

LOCALISATION : core/tests/test_synthese_citations.py

SPEC-synthese § 4 : le markdown est la verite, les SourceLink en sont
l'index, reconstruits a chaque enregistrement. Le numero [N] n'est jamais
stocke — le marqueur [[ext:<id>]] l'est.
/ Markdown is the truth; links are its index; [N] is never stored.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import Dossier, Page, SourceLink, TypeDeNote, TypeLien
from core.services.corpus import ranger_une_note_dans_un_carnet
from core.services.synthese import (
    MOTIF_DE_MARQUEUR,
    SuppressionRefuseeSourceCitee,
    indexer_les_citations,
)
from hypostasis_extractor.models import ExtractedEntity, ExtractionJob

Utilisateur = get_user_model()


def creer_une_page(url_unique, **champs):
    """Cree une page minimale. / Minimal page."""
    return Page.objects.create(
        url=url_unique,
        html_original="<p>o</p>",
        html_readability="<p>l</p>",
        text_readability="texte",
        content_hash=f"hash-{url_unique}",
        title=f"Note {url_unique[-10:]}",
        **champs,
    )


def creer_une_extraction(page, texte="le seuil de dix mille euros"):
    """Cree une extraction sur une page. / An extraction on a page."""
    job = ExtractionJob.objects.create(
        page=page, name="Job test citations", status="completed", ai_model=None,
    )
    return ExtractedEntity.objects.create(
        job=job, extraction_class="argument", extraction_text=texte,
        start_char=0, end_char=len(texte),
    )


class ParseurDeMarqueursTest(TestCase):
    """indexer_les_citations : le markdown est la verite. / The parser."""

    def setUp(self):
        self.note_source = creer_une_page("http://exemple.local/sb-source")
        self.extraction_a = creer_une_extraction(self.note_source, "premier passage")
        self.extraction_b = creer_une_extraction(self.note_source, "second passage")
        self.article = creer_une_page(
            "http://exemple.local/sb-article", type_de_note=TypeDeNote.SYNTHESE,
        )

    def test_un_lien_par_couple_paragraphe_extraction(self):
        markdown = (
            "## Le seuil\n\n"
            f"Le seuil déclenche le passage en assemblée.[[ext:{self.extraction_a.pk}]]"
            f"[[ext:{self.extraction_b.pk}]]\n\n"
            f"L'ajournement est un coût.[[ext:{self.extraction_a.pk}]]\n"
        )

        bilan = indexer_les_citations(self.article, markdown, None)

        liens = SourceLink.objects.filter(
            page_cible=self.article, type_lien=TypeLien.CITE,
        ).order_by("start_char_cible", "ordre_dans_la_section")
        self.assertEqual(liens.count(), 3)

        premier = liens.first()
        self.assertEqual(premier.extraction_source, self.extraction_a)
        self.assertEqual(premier.section, "Le seuil")
        # Les bornes cibles sont celles du PARAGRAPHE citant.
        # / Target bounds are the citing paragraph's.
        self.assertEqual(
            markdown[premier.start_char_cible:premier.end_char_cible].split("[[")[0],
            "Le seuil déclenche le passage en assemblée.",
        )
        self.assertEqual(bilan["marqueurs_retires"], [])

    def test_reindexer_reconstruit_l_index(self):
        # On reconstruit a chaque enregistrement — deux verites divergent
        # toujours. / Rebuild the index; never maintain two truths.
        markdown_v1 = f"Phrase.[[ext:{self.extraction_a.pk}]]\n"
        indexer_les_citations(self.article, markdown_v1, None)
        markdown_v2 = f"Autre phrase.[[ext:{self.extraction_b.pk}]]\n"
        indexer_les_citations(self.article, markdown_v2, None)

        liens = SourceLink.objects.filter(
            page_cible=self.article, type_lien=TypeLien.CITE,
        )
        self.assertEqual(liens.count(), 1)
        self.assertEqual(liens.first().extraction_source, self.extraction_b)

    def test_un_marqueur_hors_perimetre_est_retire_et_signale(self):
        # Une citation hors perimetre est une hallucination : pas de lien,
        # marqueur retire du texte, fait signale — jamais en silence.
        # / An out-of-scope citation is a hallucination: no link, marker
        # stripped, loudly reported.
        markdown = f"Affirmation.[[ext:{self.extraction_b.pk}]]\n"

        bilan = indexer_les_citations(
            self.article, markdown,
            identifiants_du_perimetre={self.extraction_a.pk},
        )

        self.assertEqual(SourceLink.objects.filter(page_cible=self.article).count(), 0)
        self.assertNotIn("[[ext:", bilan["texte_nettoye"])
        self.assertEqual(bilan["marqueurs_retires"], [self.extraction_b.pk])

    def test_un_marqueur_vers_une_extraction_inexistante_est_retire(self):
        markdown = "Affirmation.[[ext:999999]]\n"
        bilan = indexer_les_citations(self.article, markdown, None)
        self.assertEqual(SourceLink.objects.filter(page_cible=self.article).count(), 0)
        self.assertEqual(bilan["marqueurs_retires"], [999999])


class ArbitrageDeLaSuppressionTest(TestCase):
    """§ 4.2 : une extraction citee ne disparait pas en silence. / § 4.2."""

    def setUp(self):
        self.note_source = creer_une_page("http://exemple.local/sb-arb-source")
        self.extraction = creer_une_extraction(self.note_source)

    def _citer_depuis(self, type_de_note, url):
        article = creer_une_page(url, type_de_note=type_de_note)
        indexer_les_citations(
            article, f"Affirmation.[[ext:{self.extraction.pk}]]\n", None
        )
        return article

    def test_citee_par_une_dirigee_la_suppression_est_refusee(self):
        from django.db import transaction

        self._citer_depuis(TypeDeNote.SYNTHESE, "http://exemple.local/sb-dirigee")

        # Savepoint : l'exception sort du bloc atomique du delete() —
        # sans lui, les requetes suivantes du test seraient refusees.
        # / Savepoint so the test can keep querying after the raise.
        with self.assertRaises(SuppressionRefuseeSourceCitee):
            with transaction.atomic():
                self.extraction.delete()
        self.assertTrue(
            ExtractedEntity.objects.filter(pk=self.extraction.pk).exists()
        )

    def test_citee_par_un_wiki_seul_la_citation_bascule_supprimee(self):
        article = self._citer_depuis(TypeDeNote.WIKI, "http://exemple.local/sb-wiki")

        self.extraction.delete()

        lien = SourceLink.objects.get(page_cible=article)
        self.assertEqual(lien.etat_de_la_source, "supprimee")
        self.assertIsNone(lien.extraction_source)

    def test_non_citee_la_suppression_est_libre(self):
        self.extraction.delete()
        self.assertFalse(
            ExtractedEntity.objects.filter(pk=self.extraction.pk).exists()
        )


class PropagationDetacheeTest(TestCase):
    """§ 4.2 fin : une ancre detachee detache la citation. / Drift state."""

    def test_la_reconciliation_detache_la_citation(self):
        from core.models import ElementDocument, empreinte_du_texte
        from hypostasis_extractor.models import AncrageExtraction
        from hypostasis_extractor.services.reconciliation import (
            reconcilier_les_portions_de_l_element,
        )

        note = creer_une_page("http://exemple.local/sb-drift")
        element = ElementDocument.objects.create(
            page=note, ordre=0, label="text",
            texte="le passage source exact",
            empreinte_contenu=empreinte_du_texte("le passage source exact"),
        )
        extraction = creer_une_extraction(note, "passage source")
        ancrage = AncrageExtraction.objects.create(
            extraction=extraction, element=element,
            ordre_dans_extraction=0,
            debut_dans_element=3, fin_dans_element=17,
        )
        article = creer_une_page(
            "http://exemple.local/sb-drift-article",
            type_de_note=TypeDeNote.WIKI,
        )
        indexer_les_citations(article, f"Phrase.[[ext:{extraction.pk}]]\n", None)

        # Le texte change tellement que la portion ne se retrouve plus.
        # / The text changes so much the portion cannot be relocated.
        reconcilier_les_portions_de_l_element(
            element, "un contenu entierement different"
        )

        lien = SourceLink.objects.get(page_cible=article)
        self.assertEqual(lien.etat_de_la_source, "detachee")


class RobustesseDuParseurTest(TestCase):
    """Les cas de markdown reel releves par la relecture B. / Real-world md."""

    def setUp(self):
        self.note_source = creer_une_page("http://exemple.local/sb-rob-source")
        self.extraction = creer_une_extraction(self.note_source)
        self.article = creer_une_page(
            "http://exemple.local/sb-rob-article",
            type_de_note=TypeDeNote.WIKI,
        )

    def test_le_crlf_est_normalise(self):
        # Un textarea navigateur envoie du \r\n : titres et bornes doivent
        # tenir. / Browser textareas send CRLF.
        markdown = (
            f"## Titre\r\n\r\nPhrase.[[ext:{self.extraction.pk}]]\r\n"
        )
        indexer_les_citations(self.article, markdown, None)

        lien = SourceLink.objects.get(page_cible=self.article)
        self.assertEqual(lien.section, "Titre")

    def test_un_titre_sans_ligne_vide_apres_est_reconnu(self):
        # Les LLM produisent couramment « ## Titre\nParagraphe ».
        # / LLMs commonly emit a heading glued to its paragraph.
        markdown = (
            f"## Le seuil\nPhrase collée.[[ext:{self.extraction.pk}]]\n"
        )
        indexer_les_citations(self.article, markdown, None)

        lien = SourceLink.objects.get(page_cible=self.article)
        self.assertEqual(lien.section, "Le seuil")

    def test_deux_marqueurs_identiques_ne_font_qu_un_lien(self):
        # « Un lien par couple (paragraphe, identifiant) » (§ 4.4).
        # / One link per (paragraph, id) pair.
        markdown = (
            f"Phrase.[[ext:{self.extraction.pk}]][[ext:{self.extraction.pk}]]\n"
        )
        indexer_les_citations(self.article, markdown, None)

        self.assertEqual(
            SourceLink.objects.filter(page_cible=self.article).count(), 1
        )

    def test_un_marqueur_dans_un_titre_est_retire_et_signale(self):
        # Un titre n'affirme rien : un marqueur y est une hallucination de
        # placement — retire ET signale, jamais avale.
        # / A marker inside a heading is stripped AND reported.
        markdown = f"## Titre[[ext:{self.extraction.pk}]]\n\nPhrase sans source.\n"
        bilan = indexer_les_citations(self.article, markdown, None)

        self.assertEqual(SourceLink.objects.filter(page_cible=self.article).count(), 0)
        self.assertIn(self.extraction.pk, bilan["marqueurs_retires"])
        self.assertNotIn("[[ext:", bilan["texte_nettoye"])
        # Le nom de section reste propre. / Section name stays clean.
        self.assertIn("## Titre\n", bilan["texte_nettoye"])

    def test_une_ancre_deja_detachee_cree_un_lien_detache(self):
        # La reindexation ne blanchit pas une derive existante (relecture
        # B, N5). / Reindexing must not launder an existing drift.
        from core.models import ElementDocument, empreinte_du_texte
        from hypostasis_extractor.models import AncrageExtraction, EtatAncrage

        element = ElementDocument.objects.create(
            page=self.note_source, ordre=0, label="text", texte="texte",
            empreinte_contenu=empreinte_du_texte("texte"),
        )
        AncrageExtraction.objects.create(
            extraction=self.extraction, element=element,
            ordre_dans_extraction=0, debut_dans_element=0,
            fin_dans_element=5, etat_ancrage=EtatAncrage.DETACHEE,
        )
        indexer_les_citations(
            self.article, f"Phrase.[[ext:{self.extraction.pk}]]\n", None
        )
        lien = SourceLink.objects.get(page_cible=self.article)
        self.assertEqual(lien.etat_de_la_source, "detachee")

    def test_le_masquage_detache_aussi_les_citations(self):
        # Trou N6 : la propagation couvre masquage ET reingestion, pas
        # seulement la reconciliation. / Masking also detaches citations.
        from core.models import ElementDocument, empreinte_du_texte
        from hypostasis_extractor.models import AncrageExtraction
        from hypostasis_extractor.services.masquage import masquer_un_element

        element = ElementDocument.objects.create(
            page=self.note_source, ordre=0, label="text",
            texte="le passage masquable",
            empreinte_contenu=empreinte_du_texte("le passage masquable"),
        )
        AncrageExtraction.objects.create(
            extraction=self.extraction, element=element,
            ordre_dans_extraction=0, debut_dans_element=0, fin_dans_element=10,
        )
        indexer_les_citations(
            self.article, f"Phrase.[[ext:{self.extraction.pk}]]\n", None
        )

        masquer_un_element(element, "bruit de transcription", None)

        lien = SourceLink.objects.get(page_cible=self.article)
        self.assertEqual(lien.etat_de_la_source, "detachee")


class GardeAvantPurgeTest(TestCase):
    """
    Relecture B, B2/B3 : les flux qui purgent des extractions refusent
    PROPREMENT quand une dirigee cite — jamais un 500.
    / Purge flows refuse CLEANLY when a frozen synthesis cites.
    """

    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            username="purgeur_test", password="motdepasse", is_superuser=True,
        )
        self.note_source = creer_une_page(
            "http://exemple.local/sb-purge-source", owner=self.utilisateur,
        )
        self.extraction = creer_une_extraction(self.note_source)
        self.dirigee = creer_une_page(
            "http://exemple.local/sb-purge-dirigee",
            type_de_note=TypeDeNote.SYNTHESE,
        )
        indexer_les_citations(
            self.dirigee, f"Affirmation.[[ext:{self.extraction.pk}]]\n", None
        )

    def test_la_garde_refuse_avant_la_purge(self):
        from core.services.synthese import (
            verifier_qu_aucune_dirigee_ne_cite_les_extractions,
        )

        with self.assertRaises(SuppressionRefuseeSourceCitee):
            verifier_qu_aucune_dirigee_ne_cite_les_extractions(
                ExtractedEntity.objects.filter(pk=self.extraction.pk)
            )

    def test_supprimer_la_page_source_citee_repond_un_message_pas_un_500(self):
        """
        LE CODE ATTENDU A CHANGE LE 13 AOUT : 200 -> 409.

        Ce test attendait 200 parce que la reponse etait l'arbre lateral,
        toujours du HTML. L'arbre retire, la reponse est devenue la liste
        des notes du carnet d'ou part le geste — absente ici, la requete
        ne nommant aucun carnet. Le refus repondait alors 204, que tout
        client lit comme UN SUCCES SANS CORPS.

        409 aligne ce refus sur son JUMEAU
        (`test_supprimer_l_extraction_citee_repond_409_avec_message`,
        plus bas) : meme cause, meme code. Les deux invariants que ce
        test nomme sont inchanges — un message, pas un 500 ; et la page
        est toujours la.
        / The expected code changed from 200 to 409: the old response was
        the (now removed) side tree. 409 matches the twin refusal below.
        """
        self.client.force_login(self.utilisateur)
        reponse = self.client.post(f"/pages/{self.note_source.pk}/supprimer/")

        import json as json_stdlib

        self.assertEqual(reponse.status_code, 409)
        declencheur = json_stdlib.loads(reponse.headers.get("HX-Trigger", "{}"))
        self.assertIn(
            "citée par une synthèse",
            declencheur.get("showToast", {}).get("message", ""),
        )
        self.assertTrue(Page.objects.filter(pk=self.note_source.pk).exists())

    def test_supprimer_l_extraction_citee_repond_409_avec_message(self):
        self.client.force_login(self.utilisateur)
        reponse = self.client.post(
            "/extractions/supprimer_entite/",
            {"entity_id": self.extraction.pk,
             "page_id": self.note_source.pk},
        )
        self.assertEqual(reponse.status_code, 409)
        self.assertTrue(
            ExtractedEntity.objects.filter(pk=self.extraction.pk).exists()
        )


class TitreDeSectionVerbeuxTest(TestCase):
    """
    Relecture C, I5 : un titre de section plus long que le champ
    SourceLink.section (200) est tronque — il ne detruit pas la synthese.
    / A heading longer than the section field is truncated, never fatal.
    """

    def test_un_titre_de_section_tres_long_est_tronque(self):
        note_source = creer_une_page("http://exemple.local/sc-i5-source")
        extraction = creer_une_extraction(note_source, "un passage")
        article = creer_une_page(
            "http://exemple.local/sc-i5-article",
            type_de_note=TypeDeNote.SYNTHESE,
        )
        titre_verbeux = "Très long titre " * 20  # 320 caracteres

        markdown = (
            f"## {titre_verbeux}\n\n"
            f"Une affirmation.[[ext:{extraction.pk}]]\n"
        )
        bilan = indexer_les_citations(article, markdown, None)

        self.assertEqual(bilan["liens_crees"], 1)
        lien = SourceLink.objects.get(page_cible=article)
        self.assertEqual(len(lien.section), 200)
        self.assertTrue(titre_verbeux.startswith(lien.section))


# =============================================================================
# PHASE D — les calculs purs : ecartees (§ 8) et couverture (§ 9)
# / PHASE D — pure computations: left-out extractions and coverage.
# =============================================================================


class ExtractionsEcarteesTest(TestCase):
    """
    § 8 : « ce qui n'a pas ete repris » est une DIFFERENCE D'ENSEMBLES
    (perimetre − citees), jamais une liste stockee. Trois configurations.
    / § 8: a set difference, never a stored list. Three setups.
    """

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="ecartees_test", password="motdepasse",
        )
        self.carnet = Dossier.objects.create(
            name="Carnet ecartees D", owner=self.proprietaire,
        )
        self.note_source = creer_une_page(
            "http://exemple.local/sd-source", owner=self.proprietaire,
        )
        ranger_une_note_dans_un_carnet(
            self.note_source, self.carnet, self.proprietaire,
        )
        # Trois extractions citables sur le MEME job d'analyse.
        # / Three citable extractions on the same analysis job.
        self.job_analyse = ExtractionJob.objects.create(
            page=self.note_source, name="Analyse ecartees",
            status="completed", ai_model=None,
        )
        self.extraction_a = ExtractedEntity.objects.create(
            job=self.job_analyse, extraction_class="donnee",
            extraction_text="premier fait", start_char=0, end_char=12,
        )
        self.extraction_b = ExtractedEntity.objects.create(
            job=self.job_analyse, extraction_class="donnee",
            extraction_text="second fait", start_char=13, end_char=24,
        )
        self.extraction_c = ExtractedEntity.objects.create(
            job=self.job_analyse, extraction_class="donnee",
            extraction_text="troisieme fait", start_char=25, end_char=39,
        )

    def _creer_une_dirigee_qui_cite(self, extractions_citees):
        # Comme en production (phase C) : le perimetre d'extractions est
        # fige a la creation. / As in production: frozen at creation.
        from core.models import SyntheseDirigee
        from core.services.synthese import extractions_citables_de_la_note

        article = creer_une_page(
            "http://exemple.local/sd-dirigee",
            type_de_note=TypeDeNote.SYNTHESE,
        )
        dirigee = SyntheseDirigee.objects.create(
            page=article, dossier=self.carnet,
            produite_par=self.proprietaire,
            perimetre_d_extractions_fige=True,
        )
        dirigee.notes_du_perimetre.add(self.note_source)
        dirigee.extractions_du_perimetre.set(
            extractions_citables_de_la_note(self.note_source),
        )
        markdown = "\n\n".join(
            f"Affirmation.[[ext:{extraction.pk}]]"
            for extraction in extractions_citees
        ) + "\n"
        indexer_les_citations(article, markdown, None)
        return article

    def test_ecartees_est_une_difference_d_ensembles(self):
        from core.services.synthese import extractions_ecartees

        # Configuration 1 : une citee sur trois -> deux ecartees.
        # / Setup 1: one cited out of three -> two left out.
        article = self._creer_une_dirigee_qui_cite([self.extraction_a])

        ecartees = extractions_ecartees(article)

        self.assertEqual(
            sorted(extraction.pk for extraction in ecartees),
            sorted([self.extraction_b.pk, self.extraction_c.pk]),
        )

    def test_tout_citer_ne_laisse_rien(self):
        # Configuration 2 : tout est cite -> aucune ecartee.
        # / Setup 2: everything cited -> nothing left out.
        from core.services.synthese import extractions_ecartees

        article = self._creer_une_dirigee_qui_cite(
            [self.extraction_a, self.extraction_b, self.extraction_c],
        )

        self.assertEqual(extractions_ecartees(article).count(), 0)

    def test_le_perimetre_ignore_les_extractions_non_citables(self):
        # Configuration 3 : une masquee et une non pertinente ne sont ni
        # citables ni « ecartees » — elles n'ont jamais ete proposees au
        # modele. / Hidden or dismissed extractions never enter the scope.
        from core.services.synthese import extractions_ecartees

        # masquee=True est le SEUL etat non citable : l'ancienne valeur
        # non_pertinent a fusionne dedans (migration extractor 0029).
        # / masquee=True is the only non-citable state since 0029.
        ExtractedEntity.objects.filter(
            pk__in=[self.extraction_b.pk, self.extraction_c.pk],
        ).update(masquee=True)
        article = self._creer_une_dirigee_qui_cite([self.extraction_a])

        self.assertEqual(extractions_ecartees(article).count(), 0)

    def test_le_perimetre_d_un_wiki_suit_le_carnet(self):
        # Un wiki recalcule : une note ajoutee au carnet APRES la
        # production entre dans le perimetre — ses extractions non
        # citees deviennent des ecartees. / A wiki's scope follows the
        # notebook at computation time.
        from core.models import Wiki
        from core.services.synthese import extractions_ecartees

        article = creer_une_page(
            "http://exemple.local/sd-wiki", type_de_note=TypeDeNote.WIKI,
        )
        Wiki.objects.create(
            page=article, dossier=self.carnet, sujet="Les faits",
        )
        markdown = f"Affirmation.[[ext:{self.extraction_a.pk}]]\n"
        indexer_les_citations(article, markdown, None)

        self.assertEqual(extractions_ecartees(article).count(), 2)

        note_arrivee_apres = creer_une_page(
            "http://exemple.local/sd-apres", owner=self.proprietaire,
        )
        ranger_une_note_dans_un_carnet(
            note_arrivee_apres, self.carnet, self.proprietaire,
        )
        job_apres = ExtractionJob.objects.create(
            page=note_arrivee_apres, name="Analyse apres",
            status="completed", ai_model=None,
        )
        ExtractedEntity.objects.create(
            job=job_apres, extraction_class="donnee",
            extraction_text="fait nouveau", start_char=0, end_char=12,
        )

        self.assertEqual(extractions_ecartees(article).count(), 3)

    def test_une_page_sans_genre_est_refusee(self):
        # Une note ordinaire n'a ni perimetre ni ecartees : erreur
        # explicite, pas un resultat vide trompeur. / A plain note has
        # no scope: explicit error, not a misleading empty result.
        from core.services.synthese import extractions_ecartees

        note_ordinaire = creer_une_page("http://exemple.local/sd-plain")

        with self.assertRaises(ValueError):
            extractions_ecartees(note_ordinaire)


class CouvertureDeLaNoteTest(TestCase):
    """
    § 9 : la couverture est une JOINTURE — quels elements portent au
    moins une extraction. Compares a un LEFT JOIN manuel.
    / § 9: coverage is a join, compared to a manual LEFT JOIN.
    """

    def test_couverture_est_une_jointure(self):
        from core.models import ElementDocument, empreinte_du_texte
        from core.services.synthese import couverture_de_la_note
        from hypostasis_extractor.models import AncrageExtraction

        page = creer_une_page("http://exemple.local/sd-couverture")
        elements = []
        for numero, texte in enumerate(
            ["premier element", "deuxieme element", "troisieme element"],
        ):
            elements.append(ElementDocument.objects.create(
                page=page, ordre=numero, label="text", texte=texte,
                empreinte_contenu=empreinte_du_texte(texte),
            ))
        extraction = creer_une_extraction(page, "premier")
        seconde_extraction = creer_une_extraction(page, "deuxieme")
        # L'element 0 porte DEUX portions : il ne compte qu'une fois.
        # / Element 0 carries TWO portions: counted once.
        AncrageExtraction.objects.create(
            extraction=extraction, element=elements[0],
            ordre_dans_extraction=0, debut_dans_element=0,
            fin_dans_element=7,
        )
        AncrageExtraction.objects.create(
            extraction=seconde_extraction, element=elements[0],
            ordre_dans_extraction=0, debut_dans_element=0,
            fin_dans_element=7,
        )
        AncrageExtraction.objects.create(
            extraction=seconde_extraction, element=elements[1],
            ordre_dans_extraction=1, debut_dans_element=0,
            fin_dans_element=8,
        )

        couverture = couverture_de_la_note(page)

        # Le LEFT JOIN manuel : parcours Python element par element.
        # / The manual LEFT JOIN: plain Python walk.
        couverts_a_la_main = sum(
            1 for element in page.elements.all()
            if element.portions_d_extractions.exists()
        )
        self.assertEqual(
            couverture,
            {"total": 3, "couverts": couverts_a_la_main},
        )
        self.assertEqual(couverture["couverts"], 2)

    def test_une_page_sans_element_a_une_couverture_vide(self):
        from core.services.synthese import couverture_de_la_note

        page = creer_une_page("http://exemple.local/sd-sans-element")

        self.assertEqual(
            couverture_de_la_note(page), {"total": 0, "couverts": 0},
        )


class CorrectifsRelectureDTest(TestCase):
    """
    Correctifs de la relecture adverse de la phase D (9 aout).
    / Fixes from the phase D adversarial review.
    """

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="relecture_d_test", password="motdepasse",
        )
        self.carnet = Dossier.objects.create(
            name="Carnet relecture D", owner=self.proprietaire,
        )
        self.note_source = creer_une_page(
            "http://exemple.local/rd-source", owner=self.proprietaire,
        )
        ranger_une_note_dans_un_carnet(
            self.note_source, self.carnet, self.proprietaire,
        )
        self.job_analyse = ExtractionJob.objects.create(
            page=self.note_source, name="Analyse", status="completed",
            ai_model=None,
        )
        self.extraction_a = ExtractedEntity.objects.create(
            job=self.job_analyse, extraction_class="donnee",
            extraction_text="premier fait", start_char=0, end_char=12,
        )
        self.extraction_b = ExtractedEntity.objects.create(
            job=self.job_analyse, extraction_class="donnee",
            extraction_text="second fait", start_char=13, end_char=24,
        )

    def _creer_une_dirigee_qui_cite(self, extractions_citees, **champs):
        # Reflete la production phase C : le perimetre d'extractions est
        # FIGE a la creation (relecture E, I2 : une dirigee sans flag
        # est un historique, ses ecartees sont refusees).
        # / Mirrors production: the extraction scope is frozen.
        from core.models import SyntheseDirigee
        from core.services.synthese import extractions_citables_de_la_note

        champs.setdefault("perimetre_d_extractions_fige", True)
        article = creer_une_page(
            "http://exemple.local/rd-dirigee",
            type_de_note=TypeDeNote.SYNTHESE,
        )
        dirigee = SyntheseDirigee.objects.create(
            page=article, dossier=self.carnet,
            produite_par=self.proprietaire, **champs,
        )
        dirigee.notes_du_perimetre.add(self.note_source)
        if dirigee.perimetre_d_extractions_fige:
            dirigee.extractions_du_perimetre.set(
                extractions_citables_de_la_note(self.note_source),
            )
        markdown = "\n\n".join(
            f"Affirmation.[[ext:{extraction.pk}]]"
            for extraction in extractions_citees
        ) + "\n"
        indexer_les_citations(article, markdown, None)
        return article, dirigee

    # ----- B1 : un job manuel n'evince pas le perimetre -----

    def test_une_extraction_manuelle_n_evince_pas_le_perimetre(self):
        # Un job « Extractions manuelles » posterieur a l'analyse ne
        # doit pas devenir « LE dernier job » et vider le perimetre :
        # toutes les extractions visibles de la note comptent.
        # / A later manual-extraction job must not empty the scope.
        from core.services.synthese import extractions_ecartees

        job_manuel = ExtractionJob.objects.create(
            page=self.note_source, name="Extractions manuelles",
            status="completed", ai_model=None,
        )
        extraction_manuelle = ExtractedEntity.objects.create(
            job=job_manuel, extraction_class="donnee",
            extraction_text="fait manuel", start_char=0, end_char=11,
        )
        article, _dirigee = self._creer_une_dirigee_qui_cite(
            [self.extraction_a],
        )

        ecartees = extractions_ecartees(article)

        self.assertEqual(
            sorted(extraction.pk for extraction in ecartees),
            sorted([self.extraction_b.pk, extraction_manuelle.pk]),
        )

    # ----- B2 : le perimetre d'extractions d'une dirigee est FIGE -----

    def test_le_perimetre_d_extractions_d_une_dirigee_est_fige(self):
        # Une re-analyse APRES production ne change pas les ecartees de
        # l'acte date : l'ensemble fige a la production fait foi.
        # / A re-analysis never rewrites a frozen synthesis's left-outs.
        from core.services.synthese import extractions_ecartees

        article, dirigee = self._creer_une_dirigee_qui_cite(
            [self.extraction_a],
        )

        job_de_re_analyse = ExtractionJob.objects.create(
            page=self.note_source, name="Re-analyse", status="completed",
            ai_model=None,
        )
        ExtractedEntity.objects.create(
            job=job_de_re_analyse, extraction_class="donnee",
            extraction_text="fait posterieur", start_char=0, end_char=15,
        )

        ecartees = extractions_ecartees(article)

        self.assertEqual(
            [extraction.pk for extraction in ecartees],
            [self.extraction_b.pk],
        )

    def test_un_perimetre_fige_vide_ne_declare_rien_ecarte(self):
        # Analyseur sans extractions : rien n'a ete propose au modele,
        # rien ne peut avoir ete « ecarte ». / Nothing proposed, nothing
        # left out.
        from core.services.synthese import extractions_ecartees

        article, dirigee = self._creer_une_dirigee_qui_cite([])
        dirigee.extractions_du_perimetre.clear()

        self.assertEqual(extractions_ecartees(article).count(), 0)

    # ----- I4 : le garde-fou § 3.3 est mecanique cote dirigee -----

    def test_une_synthese_dans_le_perimetre_fige_est_ignoree(self):
        from core.services.synthese import extractions_du_perimetre

        autre_synthese = creer_une_page(
            "http://exemple.local/rd-intruse",
            type_de_note=TypeDeNote.SYNTHESE,
        )
        job_de_l_intruse = ExtractionJob.objects.create(
            page=autre_synthese, name="Analyse intruse",
            status="completed", ai_model=None,
        )
        ExtractedEntity.objects.create(
            job=job_de_l_intruse, extraction_class="donnee",
            extraction_text="fait d'une synthese", start_char=0,
            end_char=19,
        )
        article, dirigee = self._creer_une_dirigee_qui_cite(
            [], perimetre_d_extractions_fige=False,
        )
        dirigee.notes_du_perimetre.add(autre_synthese)

        perimetre = extractions_du_perimetre(article)

        self.assertEqual(
            sorted(extraction.pk for extraction in perimetre),
            sorted([self.extraction_a.pk, self.extraction_b.pk]),
        )

    # ----- I9 : liens non CITE et sources supprimees -----

    def test_les_liens_non_cite_ne_comptent_pas_comme_citations(self):
        from core.services.synthese import extractions_ecartees

        article, _dirigee = self._creer_une_dirigee_qui_cite(
            [self.extraction_a],
        )
        SourceLink.objects.create(
            page_cible=article, start_char_cible=0, end_char_cible=5,
            extraction_source=self.extraction_b,
            type_lien=TypeLien.IDENTIQUE,
        )

        # b n'est PAS citee (le lien de versionnage ne compte pas).
        # / b is NOT cited; the legacy link does not count.
        self.assertEqual(
            [extraction.pk for extraction in extractions_ecartees(article)],
            [self.extraction_b.pk],
        )

    def test_une_citation_a_la_source_supprimee_ne_casse_rien(self):
        from core.services.synthese import extractions_ecartees

        article, _dirigee = self._creer_une_dirigee_qui_cite(
            [self.extraction_a],
        )
        SourceLink.objects.create(
            page_cible=article, start_char_cible=0, end_char_cible=5,
            extraction_source=None, type_lien=TypeLien.CITE,
        )

        self.assertEqual(
            [extraction.pk for extraction in extractions_ecartees(article)],
            [self.extraction_b.pk],
        )

    # ----- I9d : le wiki filtre par ses categories -----

    def test_le_perimetre_d_extractions_d_un_wiki_suit_ses_categories(self):
        from core.models import (
            CategorieDossier, ListeDeCategories, Wiki,
        )
        from core.services.synthese import extractions_du_perimetre

        axe = ListeDeCategories.objects.create(
            nom="Type", dossier=self.carnet,
        )
        categorie_retenue = CategorieDossier.objects.create(
            liste=axe, nom="Compte rendu",
        )
        appartenance = self.note_source.appartenances_dossiers.get(
            dossier=self.carnet,
        )
        appartenance.categories.add(categorie_retenue)

        note_hors_perimetre = creer_une_page(
            "http://exemple.local/rd-hors", owner=self.proprietaire,
        )
        ranger_une_note_dans_un_carnet(
            note_hors_perimetre, self.carnet, self.proprietaire,
        )
        job_hors = ExtractionJob.objects.create(
            page=note_hors_perimetre, name="Analyse hors",
            status="completed", ai_model=None,
        )
        ExtractedEntity.objects.create(
            job=job_hors, extraction_class="donnee",
            extraction_text="fait hors perimetre", start_char=0,
            end_char=19,
        )

        article = creer_une_page(
            "http://exemple.local/rd-wiki", type_de_note=TypeDeNote.WIKI,
        )
        wiki = Wiki.objects.create(
            page=article, dossier=self.carnet, sujet="Les comptes rendus",
        )
        wiki.categories_du_perimetre.add(categorie_retenue)

        perimetre = extractions_du_perimetre(article)

        self.assertEqual(
            sorted(extraction.pk for extraction in perimetre),
            sorted([self.extraction_a.pk, self.extraction_b.pk]),
        )


class CouvertureFiltreeTest(TestCase):
    """
    Relecture D, I6 : la couverture ne compte ni les extractions
    masquees, ni les ancres detachees, ni les jobs inacheves.
    / Coverage counts neither hidden extractions, detached anchors nor
    unfinished jobs.
    """

    def test_la_couverture_ignore_les_masquees_et_les_detachees(self):
        from core.models import ElementDocument, empreinte_du_texte
        from core.services.synthese import couverture_de_la_note
        from hypostasis_extractor.models import AncrageExtraction, EtatAncrage

        page = creer_une_page("http://exemple.local/rd-couverture")
        elements = []
        for numero in range(3):
            texte = f"element numero {numero}"
            elements.append(ElementDocument.objects.create(
                page=page, ordre=numero, label="text", texte=texte,
                empreinte_contenu=empreinte_du_texte(texte),
            ))

        extraction_visible = creer_une_extraction(page, "visible")
        extraction_masquee = creer_une_extraction(page, "masquee")
        ExtractedEntity.objects.filter(pk=extraction_masquee.pk).update(
            masquee=True,
        )
        extraction_detachee = creer_une_extraction(page, "detachee")

        AncrageExtraction.objects.create(
            extraction=extraction_visible, element=elements[0],
            ordre_dans_extraction=0, debut_dans_element=0,
            fin_dans_element=7,
        )
        AncrageExtraction.objects.create(
            extraction=extraction_masquee, element=elements[1],
            ordre_dans_extraction=0, debut_dans_element=0,
            fin_dans_element=7,
        )
        AncrageExtraction.objects.create(
            extraction=extraction_detachee, element=elements[2],
            ordre_dans_extraction=0, debut_dans_element=0,
            fin_dans_element=7, etat_ancrage=EtatAncrage.DETACHEE,
        )

        # Seul l'element 0 est couvert : la masquee et la detachee ne
        # prouvent aucune lecture fiable. / Only element 0 counts.
        self.assertEqual(
            couverture_de_la_note(page), {"total": 3, "couverts": 1},
        )


class CorrectifsRelectureETest(TestCase):
    """
    Correctifs de la relecture adverse des lots D+E (9 aout soir).
    / Fixes from the D+E adversarial review.
    """

    def setUp(self):
        self.proprietaire = Utilisateur.objects.create_user(
            username="relecture_e_test", password="motdepasse",
        )
        self.carnet = Dossier.objects.create(
            name="Carnet relecture E", owner=self.proprietaire,
        )
        self.note_source = creer_une_page(
            "http://exemple.local/re-source", owner=self.proprietaire,
        )
        self.extraction = creer_une_extraction(self.note_source, "un fait")
        self.dirigee_page = creer_une_page(
            "http://exemple.local/re-dirigee",
            type_de_note=TypeDeNote.SYNTHESE,
        )
        indexer_les_citations(
            self.dirigee_page,
            f"Affirmation.[[ext:{self.extraction.pk}]]\n", None,
        )

    # ----- I2 : les ecartees d'une dirigee historique sont refusees -----

    def test_les_ecartees_d_une_dirigee_historique_sont_refusees(self):
        # Une dirigee sans perimetre fige (migration 0050) n'a AUCUN
        # SourceLink : la difference d'ensembles dirait « 100 %
        # ecarte », un faux positif a charge contre l'acte. On refuse
        # de repondre plutot que de mentir.
        # / A historical synthesis would show "100% left out": refuse
        # to answer rather than lie.
        from core.models import SyntheseDirigee
        from core.services.synthese import (
            PerimetreDExtractionsInconnu, extractions_ecartees,
        )

        page_historique = creer_une_page(
            "http://exemple.local/re-historique",
            type_de_note=TypeDeNote.SYNTHESE,
        )
        SyntheseDirigee.objects.create(
            page=page_historique, dossier=self.carnet,
            perimetre_d_extractions_fige=False,
        )

        with self.assertRaises(PerimetreDExtractionsInconnu):
            extractions_ecartees(page_historique)

    # ----- B1 : la garde § 4.2 refuse AVANT l'appel LLM -----

    def test_l_analyse_par_element_refuse_avant_l_appel_llm(self):
        # Ce test portait sur `run_langextract_job`, supprimee le 17 aout
        # 2026 avec l'etage de l'ancien moteur. L'INVARIANT, lui, reste
        # entier et vaut pour le seul chemin d'analyse vivant : le refus
        # § 4.2 doit tomber AVANT qu'on paie le modele, et avant la purge
        # des extractions de la passe precedente.
        # / Re-pointed to the only live analysis path; the invariant holds.
        from unittest.mock import patch

        from hypostasis_extractor.services.analyse_par_element import (
            analyser_une_page_par_element,
        )

        job_a_relancer = self.extraction.job
        job_a_relancer.prompt_description = "prompt"
        job_a_relancer.save(update_fields=["prompt_description"])

        appels_au_modele = []

        def _juge_espion(texte_du_chunk, job_extraction):
            appels_au_modele.append(texte_du_chunk)
            return []

        with patch("core.llm_providers.appeler_llm") as mock_llm:
            try:
                analyser_une_page_par_element(
                    self.extraction.job.page, job_a_relancer,
                    appeler_le_llm=_juge_espion,
                )
            except Exception:
                pass

        # Le refus arrive AVANT de payer l'appel LLM, et l'extraction
        # citee est TOUJOURS la. / Refusal BEFORE the paid call.
        self.assertEqual(appels_au_modele, [])
        self.assertFalse(mock_llm.called)
        self.assertTrue(
            ExtractedEntity.objects.filter(pk=self.extraction.pk).exists()
        )


class DoublonsDeMarqueursTest(TestCase):
    """
    Les doublons d'un meme marqueur dans un meme paragraphe sont
    retires DU TEXTE aussi (recette connectee du 10 aout, defaut B1).
    / Duplicate markers within a paragraph leave the TEXT too.

    L'indexation absorbait deja les doublons (un lien par couple
    paragraphe x extraction, § 4.4) mais le texte gardait toutes les
    occurrences : l'en-tete annoncait 23 renvois quand le corps en
    montrait 25 — trois compteurs contradictoires sur le meme ecran.
    / The index deduped but the text kept every occurrence: three
    contradicting counters on one screen.
    """

    def setUp(self):
        self.note_source = creer_une_page("http://exemple.local/b1-source")
        self.extraction_a = creer_une_extraction(self.note_source, "premier passage")
        self.extraction_b = creer_une_extraction(self.note_source, "second passage")
        self.article = creer_une_page(
            "http://exemple.local/b1-article", type_de_note=TypeDeNote.SYNTHESE,
        )

    def test_le_doublon_du_meme_paragraphe_sort_du_texte(self):
        markdown = (
            f"Une premiere phrase.[[ext:{self.extraction_a.pk}]] Une "
            f"seconde phrase du meme paragraphe.[[ext:{self.extraction_a.pk}]]"
            f"[[ext:{self.extraction_b.pk}]]\n"
        )

        bilan = indexer_les_citations(self.article, markdown, None)

        # Deux liens (deux extractions, un paragraphe)... et DEUX
        # marqueurs dans le texte nettoye : autant que de liens.
        # / Two links, and exactly two markers left in the text.
        liens = SourceLink.objects.filter(
            page_cible=self.article, type_lien=TypeLien.CITE,
        )
        self.assertEqual(liens.count(), 2)
        self.assertEqual(
            len(MOTIF_DE_MARQUEUR.findall(bilan["texte_nettoye"])), 2,
        )
        self.assertEqual(bilan["doublons_absorbes"], 1)

    def test_le_meme_marqueur_dans_deux_paragraphes_reste_partout(self):
        # Deux paragraphes distincts : deux couples, deux liens, deux
        # marqueurs — rien n'est retire. / Two paragraphs: nothing
        # removed.
        markdown = (
            f"Premier paragraphe.[[ext:{self.extraction_a.pk}]]\n\n"
            f"Second paragraphe.[[ext:{self.extraction_a.pk}]]\n"
        )

        bilan = indexer_les_citations(self.article, markdown, None)

        self.assertEqual(
            SourceLink.objects.filter(
                page_cible=self.article, type_lien=TypeLien.CITE,
            ).count(), 2,
        )
        self.assertEqual(
            len(MOTIF_DE_MARQUEUR.findall(bilan["texte_nettoye"])), 2,
        )
        self.assertEqual(bilan["doublons_absorbes"], 0)

    def test_les_bornes_des_liens_se_rapportent_au_texte_sans_doublons(self):
        # Les start_char_cible doivent decouper le texte FINAL (celui
        # qui sera stocke), pas une version intermediaire.
        # / Link bounds must slice the FINAL stored text.
        markdown = (
            f"Phrase citee deux fois.[[ext:{self.extraction_a.pk}]]"
            f"[[ext:{self.extraction_a.pk}]]\n\n"
            f"Autre paragraphe.[[ext:{self.extraction_b.pk}]]\n"
        )

        bilan = indexer_les_citations(self.article, markdown, None)

        texte = bilan["texte_nettoye"]
        lien_b = SourceLink.objects.get(
            page_cible=self.article, extraction_source=self.extraction_b,
        )
        self.assertIn(
            "Autre paragraphe.",
            texte[lien_b.start_char_cible:lien_b.end_char_cible],
        )
