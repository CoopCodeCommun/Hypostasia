"""
Un tour de wiki : le redacteur propose, l'applieur trie, l'humain signe.
/ One wiki round: the writer proposes, the applier sorts, a human signs.

LOCALISATION : front/tests/test_appliquer_un_tour_de_wiki.py

SPEC-synthese § 6.2/6.3, addendum du 21 septembre 2026. Le seul chemin
vers une mise a jour est le geste « Mettre a jour » d'un article, qui
enchaine `construire_la_proposition_d_operations` puis
`appliquer_un_tour_de_wiki`. Ces tests exercent ces deux etapes dans
l'ordre, comme la vue, le modele etant simule.

Ce que l'applieur garantit, et qui ne depend pas de qui l'appelle :

- il n'applique QUE ce qui respecte le § 6.2/6.3 ;
- un lot entierement rejete laisse l'article IDENTIQUE ;
- il ajoute, remplace ou insere — il ne regenere jamais l'article ;
- chaque tour s'ecrit dans l'historique, rejets compris.
/ What the applier guarantees, whoever calls it.
"""

import json
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from core.models import MotifDeTourDeWiki, Page, TourDeWiki, TypeDeNote, Wiki
from core.services.corpus import ranger_une_note_dans_un_carnet
from front.tests.test_synthese_phase_c import creer_fixtures_phase_c


class BaseDUnTourDeWiki(TestCase):
    """Un wiki qui cite une extraction sur deux. / A partial wiki."""

    def setUp(self):
        self.fixtures = creer_fixtures_phase_c()
        self.page_du_wiki = Page.objects.create(
            title="Wiki du seuil",
            text_readability=(
                "## Le seuil\n\nLe seuil est acté."
                f"[[ext:{self.fixtures['extraction_seuil'].pk}]]\n"
            ),
            html_readability="<p>w</p>", html_original="<p>w</p>",
            content_hash="hash-tour", type_de_note=TypeDeNote.WIKI,
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

    def _operations_valides(self):
        return json.dumps([{
            "type": "append_to_section",
            "section": "Le seuil",
            "contenu": (
                "L'ajournement coûte."
                f"[[ext:{self.fixtures['extraction_cout'].pk}]]"
            ),
        }])

    def _proposer_puis_appliquer(self, reponse_llm):
        """
        Les deux etapes du geste humain, dans l'ordre de la vue.
        / The two steps of the human gesture, in the view's order.
        """
        from front.tasks import (
            appliquer_un_tour_de_wiki,
            construire_la_proposition_d_operations,
        )

        with patch(
            "core.llm_providers.appeler_llm", return_value=reponse_llm,
        ), patch("front.tasks.enchainer_la_verification"):
            operations, _jeton = construire_la_proposition_d_operations(
                self.wiki, self.fixtures["modele_ia"],
            )
            appliquer_un_tour_de_wiki(
                self.wiki, operations,
                motif=MotifDeTourDeWiki.MAJ_MANUELLE,
                fait_par=self.fixtures["demandeur"],
            )


class UnTourAccepteTest(BaseDUnTourDeWiki):
    """Ce qu'un tour accepte ecrit. / What an accepted round writes."""

    def test_le_tour_est_signe_par_l_humain_qui_accepte(self):
        self._proposer_puis_appliquer(self._operations_valides())

        tour = TourDeWiki.objects.get(wiki=self.wiki)
        self.assertEqual(tour.motif, MotifDeTourDeWiki.MAJ_MANUELLE)
        self.assertEqual(tour.fait_par, self.fixtures["demandeur"])
        self.assertFalse(tour.est_fait_par_le_moteur)

    def test_l_ajout_entre_dans_l_article(self):
        self._proposer_puis_appliquer(self._operations_valides())

        self.page_du_wiki.refresh_from_db()
        self.assertIn("L'ajournement coûte.", self.page_du_wiki.text_readability)
        # L'article n'a pas ete regenere : ce qu'il disait est reste.
        # / Not regenerated: what it said is still there.
        self.assertIn("Le seuil est acté.", self.page_du_wiki.text_readability)

    def test_le_compteur_de_tours_monte(self):
        tours_avant = self.wiki.tours_de_mise_a_jour

        self._proposer_puis_appliquer(self._operations_valides())

        self.wiki.refresh_from_db()
        self.assertEqual(self.wiki.tours_de_mise_a_jour, tours_avant + 1)

    def test_l_operation_est_ecrite_avec_sa_section_et_son_ajout(self):
        self._proposer_puis_appliquer(self._operations_valides())

        operation = TourDeWiki.objects.get(wiki=self.wiki).operations.get()
        self.assertTrue(operation.appliquee)
        self.assertEqual(operation.section, "Le seuil")
        self.assertIn("L'ajournement coûte.", operation.contenu)
        self.assertEqual(
            list(operation.extractions_citees.values_list("pk", flat=True)),
            [self.fixtures["extraction_cout"].pk],
        )


class UnLotEntierementRejeteTest(BaseDUnTourDeWiki):
    """
    Ce que l'applieur refuse n'entre pas — et l'article ne bouge pas
    d'un caractere. / What the applier refuses stays out.
    """

    def _operations_sur_une_section_fantome(self):
        return json.dumps([{
            "type": "append_to_section",
            "section": "Une section que le modèle a inventée",
            "contenu": (
                "Du contenu."
                f"[[ext:{self.fixtures['extraction_cout'].pk}]]"
            ),
        }])

    def test_une_section_fantome_laisse_l_article_identique(self):
        texte_avant = self.page_du_wiki.text_readability

        self._proposer_puis_appliquer(
            self._operations_sur_une_section_fantome(),
        )

        self.page_du_wiki.refresh_from_db()
        self.assertEqual(self.page_du_wiki.text_readability, texte_avant)

    def test_le_rejet_est_ecrit_avec_son_motif(self):
        self._proposer_puis_appliquer(
            self._operations_sur_une_section_fantome(),
        )

        tour = TourDeWiki.objects.get(wiki=self.wiki)
        operation = tour.operations.get()
        self.assertFalse(operation.appliquee)
        self.assertNotEqual(operation.motif_de_rejet, "")
        self.assertFalse(tour.a_change_l_article)

    def test_un_lot_de_no_change_ne_reecrit_pas_l_article(self):
        # L'applieur ACCEPTE `no_change` — c'est une operation
        # legitime. Mais accepter n'est pas changer : le chemin
        # d'ecriture complet (reindexation, juge d'API facture,
        # compteur de tours) ne doit pas s'ouvrir pour un texte
        # identique. / Accepted is not changed.
        texte_avant = self.page_du_wiki.text_readability
        tours_avant = self.wiki.tours_de_mise_a_jour

        self._proposer_puis_appliquer(json.dumps([{"type": "no_change"}]))

        self.page_du_wiki.refresh_from_db()
        self.wiki.refresh_from_db()
        self.assertEqual(self.page_du_wiki.text_readability, texte_avant)
        self.assertEqual(self.wiki.tours_de_mise_a_jour, tours_avant)
        self.assertFalse(
            TourDeWiki.objects.get(wiki=self.wiki).a_change_l_article,
        )

    def test_un_lot_sans_source_est_refuse(self):
        # § 6.3 : une affirmation sans preuve n'entre pas dans un
        # article source. / No evidence, no entry.
        sans_source = json.dumps([{
            "type": "append_to_section",
            "section": "Le seuil",
            "contenu": "Une affirmation sans la moindre preuve.",
        }])

        self._proposer_puis_appliquer(sans_source)

        self.page_du_wiki.refresh_from_db()
        self.assertNotIn(
            "sans la moindre preuve", self.page_du_wiki.text_readability,
        )


class RienAReprendreTest(BaseDUnTourDeWiki):
    """
    Un article qui reprend tout son perimetre n'appelle aucun modele :
    la proposition refuse AVANT l'appel facture.
    / A fully covering article calls no model.
    """

    def test_un_wiki_a_jour_n_appelle_aucun_modele(self):
        # L'article cite deja les deux extractions. On passe par le
        # chemin d'ecriture normal — ce sont les SourceLink indexes qui
        # disent ce qui est repris, pas le texte brut.
        # / The indexed links, not the raw text, say what was taken up.
        from core.services.synthese import extractions_du_perimetre
        from front.tasks import (
            _ecrire_le_corps_d_un_article,
            construire_la_proposition_d_operations,
        )

        with patch("front.tasks.enchainer_la_verification"):
            _ecrire_le_corps_d_un_article(
                self.page_du_wiki,
                f"## Le seuil\n\nActé."
                f"[[ext:{self.fixtures['extraction_seuil'].pk}]] "
                f"Et coûteux."
                f"[[ext:{self.fixtures['extraction_cout'].pk}]]\n",
                set(
                    extractions_du_perimetre(self.page_du_wiki)
                    .values_list("pk", flat=True)
                ),
                motif_du_tour=MotifDeTourDeWiki.MAJ_MANUELLE,
                wiki_du_tour=self.wiki,
            )

        with patch("core.llm_providers.appeler_llm") as appel, \
                self.assertRaises(ValueError):
            construire_la_proposition_d_operations(
                self.wiki, self.fixtures["modele_ia"],
            )

        appel.assert_not_called()


class LaRaisonDuTourTest(BaseDUnTourDeWiki):
    """
    Le tour dit POURQUOI il a eu lieu : ce qui est apparu depuis le
    precedent. / The round says why it happened.
    """

    def test_le_tour_compte_les_nouveautes_du_perimetre(self):
        # Une note de plus dans le carnet, avec une extraction : c'est
        # exactement ce que le lecteur veut lire dans l'historique.
        # / One more note with an extraction: the reason to read.
        from hypostasis_extractor.models import ExtractedEntity, ExtractionJob

        borne = timezone.now()
        self.wiki.derniere_mise_a_jour = borne
        self.wiki.save(update_fields=["derniere_mise_a_jour"])

        note_neuve = Page.objects.create(
            title="Note arrivée après",
            text_readability="Un fait neuf.", html_readability="<p>n</p>",
            html_original="<p>n</p>", content_hash="hash-tour-neuve",
            owner=self.fixtures["demandeur"],
        )
        ranger_une_note_dans_un_carnet(
            note_neuve, self.fixtures["carnet"], self.fixtures["demandeur"],
        )
        job = ExtractionJob.objects.create(
            page=note_neuve, name="Analyse neuve", status="completed",
            ai_model=self.fixtures["modele_ia"],
        )
        ExtractedEntity.objects.create(
            job=job, extraction_class="donnee",
            extraction_text="Un fait neuf.", start_char=0, end_char=13,
        )

        self._proposer_puis_appliquer(self._operations_valides())

        tour = TourDeWiki.objects.get(wiki=self.wiki)
        self.assertEqual(tour.extractions_nouvelles, 1)
        self.assertIn(
            note_neuve.pk,
            tour.notes_declenchantes.values_list("pk", flat=True),
        )
