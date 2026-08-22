"""
La passe de nuit : le moteur met les wikis a jour tout seul.
/ The nightly pass: the engine updates the wikis on its own.

LOCALISATION : front/tests/test_la_passe_de_nuit_des_wikis.py

SPEC-synthese, addendum du 21 aout 2026. La nuit applique SANS humain —
ce qui contredit le § 6.1 et n'est acceptable qu'a quatre conditions,
toutes exercees ici :

- elle n'applique QUE ce que l'applieur accepte (§ 6.2/6.3 intacts) ;
- un lot entierement rejete laisse l'article IDENTIQUE ;
- elle ne regenere JAMAIS l'article — elle ajoute, remplace, insere ;
- ce qu'elle ecarte est COMPTE, jamais passe sous silence.
/ The night applies without a human, under four exercised conditions.
"""

import json
from datetime import timedelta
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from core.models import (
    MotifDeTourDeWiki, Page, PasseDeNuit, TourDeWiki, TypeDeNote, Wiki,
)
from core.services.corpus import ranger_une_note_dans_un_carnet
from front.tests.test_synthese_phase_c import creer_fixtures_phase_c


class BaseDeLaPasseDeNuit(TestCase):
    """Un wiki qui cite une extraction sur deux. / A partial wiki."""

    def setUp(self):
        self.fixtures = creer_fixtures_phase_c()
        self.page_du_wiki = Page.objects.create(
            title="Wiki de la nuit",
            text_readability=(
                "## Le seuil\n\nLe seuil est acté."
                f"[[ext:{self.fixtures['extraction_seuil'].pk}]]\n"
            ),
            html_readability="<p>w</p>", html_original="<p>w</p>",
            content_hash="hash-nuit", type_de_note=TypeDeNote.WIKI,
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
        self._vieillir_le_dernier_tour(self.wiki)

    def _vieillir_le_dernier_tour(self, wiki):
        """
        Recule la derniere mise a jour d'un jour.
        / Ages the wiki's last update by a day.

        Sans ce recul, les fixtures naitraient toutes a la meme
        seconde et le wiki serait cree APRES ses extractions : rien
        n'aurait « paru depuis le dernier tour », et la passe n'aurait
        aucune raison de le reprendre. Le cas reel est l'inverse — un
        article produit hier, des extractions arrivees aujourd'hui.
        / Otherwise the wiki is born after its own extractions and
        nothing has appeared since its last round.
        """
        Wiki.objects.filter(pk=wiki.pk).update(
            derniere_mise_a_jour=timezone.now() - timedelta(days=1),
        )
        wiki.refresh_from_db()

    def _operations_valides(self):
        return json.dumps([{
            "type": "append_to_section",
            "section": "Le seuil",
            "contenu": (
                "L'ajournement coûte."
                f"[[ext:{self.fixtures['extraction_cout'].pk}]]"
            ),
        }])

    def _passer_la_nuit(self, reponse_llm, **options):
        with patch(
            "core.llm_providers.appeler_llm", return_value=reponse_llm,
        ), patch("front.tasks.enchainer_la_verification"):
            call_command("mettre_a_jour_les_wikis", verbosity=0, **options)


class UnTourDeNuitTest(BaseDeLaPasseDeNuit):
    """Ce que la nuit ecrit. / What the night writes."""

    def test_le_tour_est_signe_par_le_moteur_et_non_par_un_humain(self):
        self._passer_la_nuit(self._operations_valides())

        tour = TourDeWiki.objects.get(wiki=self.wiki)
        self.assertEqual(tour.motif, MotifDeTourDeWiki.MAJ_NOCTURNE)
        self.assertIsNone(tour.fait_par)
        self.assertTrue(tour.est_fait_par_le_moteur)

    def test_l_ajout_entre_dans_l_article(self):
        self._passer_la_nuit(self._operations_valides())

        self.page_du_wiki.refresh_from_db()
        self.assertIn("L'ajournement coûte.", self.page_du_wiki.text_readability)
        # L'article n'a pas ete regenere : ce qu'il disait est reste.
        # / Not regenerated: what it said is still there.
        self.assertIn("Le seuil est acté.", self.page_du_wiki.text_readability)

    def test_le_compteur_de_tours_monte(self):
        tours_avant = self.wiki.tours_de_mise_a_jour

        self._passer_la_nuit(self._operations_valides())

        self.wiki.refresh_from_db()
        self.assertEqual(self.wiki.tours_de_mise_a_jour, tours_avant + 1)

    def test_l_operation_est_ecrite_avec_sa_section_et_son_ajout(self):
        self._passer_la_nuit(self._operations_valides())

        operation = TourDeWiki.objects.get(wiki=self.wiki).operations.get()
        self.assertTrue(operation.appliquee)
        self.assertEqual(operation.section, "Le seuil")
        self.assertIn("L'ajournement coûte.", operation.contenu)
        self.assertEqual(
            list(operation.extractions_citees.values_list("pk", flat=True)),
            [self.fixtures["extraction_cout"].pk],
        )


class UnLotEntierementRejeteTest(BaseDeLaPasseDeNuit):
    """
    La nuit n'a AUCUN passe-droit : ce que l'applieur refuse, elle ne
    l'ecrit pas — et l'article ne bouge pas d'un caractere.
    / The night gets no free pass over the applier's rules.
    """

    def test_une_section_fantome_laisse_l_article_identique(self):
        texte_avant = self.page_du_wiki.text_readability
        operations_hallucinees = json.dumps([{
            "type": "append_to_section",
            "section": "Une section que le modèle a inventée",
            "contenu": (
                "Du contenu."
                f"[[ext:{self.fixtures['extraction_cout'].pk}]]"
            ),
        }])

        self._passer_la_nuit(operations_hallucinees)

        self.page_du_wiki.refresh_from_db()
        self.assertEqual(self.page_du_wiki.text_readability, texte_avant)

    def test_le_rejet_est_ecrit_avec_son_motif(self):
        operations_hallucinees = json.dumps([{
            "type": "append_to_section",
            "section": "Une section que le modèle a inventée",
            "contenu": (
                "Du contenu."
                f"[[ext:{self.fixtures['extraction_cout'].pk}]]"
            ),
        }])

        self._passer_la_nuit(operations_hallucinees)

        tour = TourDeWiki.objects.get(wiki=self.wiki)
        operation = tour.operations.get()
        self.assertFalse(operation.appliquee)
        self.assertNotEqual(operation.motif_de_rejet, "")
        self.assertFalse(tour.a_change_l_article)

    def test_un_lot_sans_source_est_refuse(self):
        # § 6.3 : une affirmation sans preuve n'entre pas dans un
        # article source. / No evidence, no entry.
        sans_source = json.dumps([{
            "type": "append_to_section",
            "section": "Le seuil",
            "contenu": "Une affirmation sans la moindre preuve.",
        }])

        self._passer_la_nuit(sans_source)

        self.page_du_wiki.refresh_from_db()
        self.assertNotIn(
            "sans la moindre preuve", self.page_du_wiki.text_readability,
        )


class CeQuiEstExamineTest(BaseDeLaPasseDeNuit):
    """
    Le cout est borne par ce qu'on examine : un wiki sans extraction
    ecartee n'appelle aucun modele.
    / Cost is bounded by what gets examined.
    """

    def test_un_wiki_a_jour_n_appelle_aucun_modele(self):
        # L'article cite deja les deux extractions : rien a reprendre.
        # On passe par le chemin d'ecriture normal — ce sont les
        # SourceLink indexes qui disent ce qui est repris, pas le texte.
        # / The indexed links, not the raw text, say what was taken up.
        from core.services.synthese import extractions_du_perimetre
        from front.tasks import _ecrire_le_corps_d_un_article

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
        TourDeWiki.objects.all().delete()

        with patch("core.llm_providers.appeler_llm") as appel, patch(
            "front.tasks.enchainer_la_verification",
        ):
            call_command("mettre_a_jour_les_wikis", verbosity=0)

        appel.assert_not_called()
        self.assertFalse(TourDeWiki.objects.exists())

    def test_un_echec_ecrit_un_tour_et_ne_se_retente_pas_chaque_nuit(self):
        # SANS TOUR, RIEN N'AVANCE : le meme wiki rappellerait le
        # redacteur la nuit suivante, et celle d'apres, sans backoff ni
        # plafond — un modele durablement injoignable couterait tous
        # les soirs, invisiblement.
        # / Without a round nothing advances and the writer is summoned
        # every night, invisibly.
        from front.tasks import _le_wiki_a_une_raison_d_etre_repris

        texte_avant = self.page_du_wiki.text_readability

        with patch(
            "core.llm_providers.appeler_llm",
            side_effect=RuntimeError("le modèle est injoignable"),
        ), patch("front.tasks.enchainer_la_verification"):
            call_command("mettre_a_jour_les_wikis", verbosity=0)

        tour = TourDeWiki.objects.get(wiki=self.wiki)
        self.assertEqual(tour.motif, MotifDeTourDeWiki.ECHEC)
        self.assertIn("injoignable", tour.message_d_echec)
        self.assertFalse(tour.a_change_l_article)

        # L'article n'a pas bouge, et le wiki n'a plus de raison d'etre
        # repris tant que rien de neuf n'arrive.
        # / The article is untouched, and there is no reason to re-run.
        self.page_du_wiki.refresh_from_db()
        self.wiki.refresh_from_db()
        self.assertEqual(self.page_du_wiki.text_readability, texte_avant)
        self.assertFalse(_le_wiki_a_une_raison_d_etre_repris(self.wiki))

    def test_un_echec_n_est_pas_annonce_comme_une_modification(self):
        # Un tour d'echec ne change pas l'article : le recapitulatif
        # l'exclut deja, comme tout tour sans changement.
        # / A failed round changes nothing: the recap excludes it.
        with patch(
            "core.llm_providers.appeler_llm",
            side_effect=RuntimeError("le modèle est injoignable"),
        ), patch("front.tasks.enchainer_la_verification"):
            call_command("mettre_a_jour_les_wikis", verbosity=0)

        tour = TourDeWiki.objects.get(wiki=self.wiki)
        self.assertFalse(tour.a_change_l_article)

    def test_un_wiki_sans_nouveaute_n_est_pas_repris_chaque_nuit(self):
        # LE PIEGE QUE CE TEST EXISTE POUR EMPECHER. Un wiki garde des
        # extractions ecartees EN PERMANENCE — un article ne reprend
        # jamais tout son perimetre. Reprendre sur ce seul critere le
        # ferait rejuger chaque nuit sur la meme matiere : le modele
        # reproposerait les memes extractions, l'historique se
        # remplirait de tours sans cause, et le recapitulatif
        # annoncerait des modifications que rien n'a appelees.
        # / A wiki always has left-out extractions; that criterion alone
        # would re-run it every night on the same material.
        from front.tasks import _le_wiki_a_une_raison_d_etre_repris

        # Il RESTE une extraction ecartee (l'article n'en cite qu'une
        # sur deux), mais RIEN n'est apparu depuis la derniere mise a
        # jour. / Something left out, but nothing new.
        from core.services.synthese import extractions_ecartees

        self.wiki.derniere_mise_a_jour = timezone.now()
        self.wiki.save(update_fields=["derniere_mise_a_jour"])

        self.assertTrue(extractions_ecartees(self.page_du_wiki).exists())
        self.assertFalse(_le_wiki_a_une_raison_d_etre_repris(self.wiki))

        with patch("core.llm_providers.appeler_llm") as appel, patch(
            "front.tasks.enchainer_la_verification",
        ):
            call_command("mettre_a_jour_les_wikis", verbosity=0)

        appel.assert_not_called()
        self.assertFalse(TourDeWiki.objects.exists())

    def test_une_extraction_neuve_donne_une_raison_de_reprendre(self):
        from hypostasis_extractor.models import ExtractedEntity
        from front.tasks import _le_wiki_a_une_raison_d_etre_repris

        self.wiki.derniere_mise_a_jour = timezone.now()
        self.wiki.save(update_fields=["derniere_mise_a_jour"])
        self.assertFalse(_le_wiki_a_une_raison_d_etre_repris(self.wiki))

        ExtractedEntity.objects.create(
            job=self.fixtures["job_analyse"], extraction_class="donnee",
            extraction_text="Un fait arrivé cette nuit.",
            start_char=60, end_char=86,
        )

        self.assertTrue(_le_wiki_a_une_raison_d_etre_repris(self.wiki))

    def test_un_wiki_a_jour_n_a_aucune_raison_meme_avec_du_neuf(self):
        # L'autre condition reste necessaire : sans ecartee, la
        # proposition echouerait sur « rien a mettre a jour ».
        # / Without a left-out extraction the proposal would fail.
        from core.services.synthese import extractions_du_perimetre
        from front.tasks import (
            _ecrire_le_corps_d_un_article, _le_wiki_a_une_raison_d_etre_repris,
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

        self.assertFalse(_le_wiki_a_une_raison_d_etre_repris(self.wiki))

    def test_un_lot_rejete_ne_fait_pas_revenir_le_wiki_chaque_nuit(self):
        # LE PIEGE LE PLUS FIN DU CHANTIER. `derniere_mise_a_jour`
        # n'avance QUE si une operation est appliquee. Un lot
        # entierement rejete la laisse donc en arriere, la nouveaute
        # qui avait declenche ce tour compte encore le lendemain, et le
        # redacteur est rappele chaque nuit sur la meme matiere, pour
        # le meme rejet. C'est `TourDeWiki.fait_le` — ecrit meme pour un
        # lot rejete — qui dit « on a deja regarde ».
        # / A fully rejected batch leaves the date behind; without the
        # attempt date the writer is summoned nightly on the same
        # material.
        from front.tasks import _le_wiki_a_une_raison_d_etre_repris

        self.assertTrue(_le_wiki_a_une_raison_d_etre_repris(self.wiki))

        operations_hallucinees = json.dumps([{
            "type": "append_to_section",
            "section": "Une section que le modèle a inventée",
            "contenu": (
                "Du contenu."
                f"[[ext:{self.fixtures['extraction_cout'].pk}]]"
            ),
        }])
        self._passer_la_nuit(operations_hallucinees)

        # Le tour existe, l'article n'a pas bouge, et le compteur du
        # wiki n'a pas monte. / The round exists; nothing else moved.
        tour = TourDeWiki.objects.get(wiki=self.wiki)
        self.assertFalse(tour.a_change_l_article)

        self.wiki.refresh_from_db()
        self.assertFalse(_le_wiki_a_une_raison_d_etre_repris(self.wiki))

    def test_un_lot_de_no_change_ne_reecrit_pas_l_article(self):
        # L'applieur ACCEPTE `no_change` — c'est une operation
        # legitime. Mais accepter n'est pas changer : le chemin
        # d'ecriture complet (reindexation, juge d'API facture,
        # compteur de tours) ne doit pas s'ouvrir pour un texte
        # identique. / Accepted is not changed.
        texte_avant = self.page_du_wiki.text_readability
        tours_avant = self.wiki.tours_de_mise_a_jour

        self._passer_la_nuit(json.dumps([{"type": "no_change"}]))

        self.page_du_wiki.refresh_from_db()
        self.wiki.refresh_from_db()
        self.assertEqual(self.page_du_wiki.text_readability, texte_avant)
        self.assertEqual(self.wiki.tours_de_mise_a_jour, tours_avant)
        self.assertFalse(TourDeWiki.objects.get(wiki=self.wiki).a_change_l_article)

    def test_le_maximum_borne_et_compte_ce_qu_il_ecarte(self):
        # Une troncature muette se lirait comme une couverture
        # complete. / A silent truncation would read as full coverage.
        second_article = Page.objects.create(
            title="Second wiki",
            text_readability=(
                "## Le seuil\n\nActé."
                f"[[ext:{self.fixtures['extraction_seuil'].pk}]]\n"
            ),
            html_readability="<p>w</p>", html_original="<p>w</p>",
            content_hash="hash-nuit-2", type_de_note=TypeDeNote.WIKI,
            owner=self.fixtures["demandeur"],
        )
        ranger_une_note_dans_un_carnet(
            second_article, self.fixtures["carnet"],
            self.fixtures["demandeur"],
        )
        self._vieillir_le_dernier_tour(Wiki.objects.create(
            page=second_article, dossier=self.fixtures["carnet"],
            sujet="Le seuil, encore",
        ))

        self._passer_la_nuit(self._operations_valides(), maximum=1)

        passe = PasseDeNuit.objects.get()
        self.assertEqual(passe.wikis_examines, 1)
        self.assertEqual(passe.wikis_ecartes_par_le_maximum, 1)

    def test_a_blanc_n_ecrit_rien(self):
        with patch("core.llm_providers.appeler_llm") as appel, patch(
            "front.tasks.enchainer_la_verification",
        ):
            call_command("mettre_a_jour_les_wikis", verbosity=0, a_blanc=True)

        appel.assert_not_called()
        self.assertFalse(TourDeWiki.objects.exists())
        self.assertFalse(PasseDeNuit.objects.exists())


class LaPasseSeDeclareTest(BaseDeLaPasseDeNuit):
    """
    La passe dit quand elle commence et quand elle finit : c'est ce que
    le recapitulatif du matin interroge avant de partir.
    / The pass declares its start and end: the recap waits on it.
    """

    def test_la_passe_est_ouverte_puis_fermee(self):
        self._passer_la_nuit(self._operations_valides())

        passe = PasseDeNuit.objects.get()
        self.assertIsNotNone(passe.terminee_le)
        self.assertFalse(passe.tourne_encore)
        self.assertEqual(passe.wikis_examines, 1)
        self.assertEqual(passe.wikis_modifies, 1)

    def test_un_wiki_en_erreur_n_arrete_pas_les_autres(self):
        second_article = Page.objects.create(
            title="Wiki qui échoue",
            text_readability=(
                "## Le seuil\n\nActé."
                f"[[ext:{self.fixtures['extraction_seuil'].pk}]]\n"
            ),
            html_readability="<p>w</p>", html_original="<p>w</p>",
            content_hash="hash-nuit-3", type_de_note=TypeDeNote.WIKI,
            owner=self.fixtures["demandeur"],
        )
        ranger_une_note_dans_un_carnet(
            second_article, self.fixtures["carnet"],
            self.fixtures["demandeur"],
        )
        self._vieillir_le_dernier_tour(Wiki.objects.create(
            page=second_article, dossier=self.fixtures["carnet"],
            sujet="Le seuil, encore",
        ))

        # Le premier appel echoue, le second rend des operations
        # valides. / First call fails, second one succeeds.
        reponses = [
            RuntimeError("le modèle est injoignable"),
            self._operations_valides(),
        ]

        def _repondre(*arguments, **options):
            reponse = reponses.pop(0)
            if isinstance(reponse, Exception):
                raise reponse
            return reponse

        with patch(
            "core.llm_providers.appeler_llm", side_effect=_repondre,
        ), patch("front.tasks.enchainer_la_verification"):
            call_command("mettre_a_jour_les_wikis", verbosity=0)

        passe = PasseDeNuit.objects.get()
        self.assertEqual(passe.wikis_examines, 2)
        self.assertEqual(passe.wikis_en_erreur, 1)
        self.assertEqual(passe.wikis_modifies, 1)


class LaRaisonDuTourDeNuitTest(BaseDeLaPasseDeNuit):
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
            html_original="<p>n</p>", content_hash="hash-nuit-neuve",
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

        self._passer_la_nuit(self._operations_valides())

        tour = TourDeWiki.objects.get(wiki=self.wiki)
        self.assertEqual(tour.extractions_nouvelles, 1)
        self.assertIn(
            note_neuve.pk,
            tour.notes_declenchantes.values_list("pk", flat=True),
        )


class DeuxPassesNeTournentJamaisEnsembleTest(BaseDeLaPasseDeNuit):
    """
    Une nuit plus longue que prevu et un cron qui repart : deux passes
    appelleraient le redacteur sur les MEMES wikis.
    / Two passes would call the writer on the same wikis.
    """

    def test_une_passe_en_cours_empeche_la_suivante(self):
        PasseDeNuit.objects.create()  # terminee_le reste NULL

        with patch("core.llm_providers.appeler_llm") as appel, patch(
            "front.tasks.enchainer_la_verification",
        ):
            with self.assertRaises(CommandError):
                call_command("mettre_a_jour_les_wikis", verbosity=0)

        appel.assert_not_called()
        self.assertFalse(TourDeWiki.objects.exists())

    def test_une_passe_abandonnee_ne_bloque_pas_la_nuit_suivante(self):
        # Un conteneur tue laisse `terminee_le` a NULL pour toujours :
        # sans peremption, plus aucune nuit ne repartirait.
        # / A killed container would otherwise block every later night.
        passe_morte = PasseDeNuit.objects.create()
        PasseDeNuit.objects.filter(pk=passe_morte.pk).update(
            lancee_le=timezone.now() - timedelta(days=2),
        )

        self._passer_la_nuit(self._operations_valides())

        self.assertEqual(TourDeWiki.objects.count(), 1)
        passe_morte.refresh_from_db()
        self.assertIsNotNone(passe_morte.terminee_le)

    def test_a_blanc_ne_regarde_pas_les_passes(self):
        # Dire ce qui partirait ne coute rien et n'ecrit rien : aucune
        # raison de le refuser. / A dry run costs nothing.
        PasseDeNuit.objects.create()

        with patch("core.llm_providers.appeler_llm") as appel:
            call_command("mettre_a_jour_les_wikis", verbosity=0, a_blanc=True)

        appel.assert_not_called()

class LaPasseEstUnFanOutDeTachesTest(BaseDeLaPasseDeNuit):
    """
    Un wiki, une tache. C'est ce qui la garde sous le plafond de
    30 minutes et fait avancer les appels en parallele.
    / One wiki, one task: parallel, and far below the 30-minute limit.
    """

    def setUp(self):
        super().setUp()
        # Un second wiki, pour voir DEUX taches partir.
        # / A second wiki, to see two tasks fire.
        second_article = Page.objects.create(
            title="Second wiki de la nuit",
            text_readability=(
                "## Le seuil\n\nActé."
                f"[[ext:{self.fixtures['extraction_seuil'].pk}]]\n"
            ),
            html_readability="<p>w</p>", html_original="<p>w</p>",
            content_hash="hash-fanout", type_de_note=TypeDeNote.WIKI,
            owner=self.fixtures["demandeur"],
        )
        ranger_une_note_dans_un_carnet(
            second_article, self.fixtures["carnet"],
            self.fixtures["demandeur"],
        )
        self.second_wiki = Wiki.objects.create(
            page=second_article, dossier=self.fixtures["carnet"],
            sujet="Le seuil, encore",
        )
        self._vieillir_le_dernier_tour(self.second_wiki)

    def test_une_tache_est_mise_en_file_par_wiki(self):
        from front.tasks import lancer_la_passe_de_nuit_task

        with patch(
            "front.tasks.mettre_a_jour_un_wiki_la_nuit_task.delay",
        ) as mise_en_file:
            lancer_la_passe_de_nuit_task()

        wikis_mis_en_file = {
            appel.args[1] for appel in mise_en_file.call_args_list
        }
        self.assertEqual(
            wikis_mis_en_file, {self.wiki.pk, self.second_wiki.pk},
        )

    def test_la_passe_reste_ouverte_tant_qu_une_tache_n_a_pas_fini(self):
        # C'est ce que le recapitulatif du matin interroge : tant que le
        # compte n'est pas atteint, le mail attend.
        # / The morning recap waits on exactly this.
        from front.tasks import lancer_la_passe_de_nuit_task

        with patch("front.tasks.mettre_a_jour_un_wiki_la_nuit_task.delay"):
            lancer_la_passe_de_nuit_task()

        passe = PasseDeNuit.objects.get()
        self.assertTrue(passe.tourne_encore)
        self.assertEqual(passe.wikis_examines, 2)
        self.assertEqual(passe.wikis_termines, 0)

    def test_la_derniere_tache_ferme_la_passe(self):
        self._passer_la_nuit(self._operations_valides())

        passe = PasseDeNuit.objects.get()
        self.assertIsNotNone(passe.terminee_le)
        self.assertEqual(passe.wikis_termines, 2)
        self.assertEqual(passe.wikis_modifies, 2)

    def test_un_wiki_en_erreur_rend_quand_meme_la_main(self):
        # SINON LA PASSE RESTE OUVERTE POUR TOUJOURS, et le
        # recapitulatif du matin n'arrive jamais.
        # / Otherwise the pass never closes and the mail never comes.
        with patch(
            "core.llm_providers.appeler_llm",
            side_effect=RuntimeError("le modèle est injoignable"),
        ), patch("front.tasks.enchainer_la_verification"):
            call_command("mettre_a_jour_les_wikis", verbosity=0)

        passe = PasseDeNuit.objects.get()
        self.assertIsNotNone(passe.terminee_le)
        self.assertEqual(passe.wikis_en_erreur, 2)
        self.assertEqual(passe.wikis_modifies, 0)

    def test_une_nuit_sans_rien_a_faire_ferme_la_passe_tout_de_suite(self):
        # Une passe ouverte sans tache pour la fermer bloquerait le
        # recapitulatif jusqu'a sa peremption.
        # / An empty pass with nobody to close it would block the mail.
        from front.tasks import lancer_la_passe_de_nuit_task

        Wiki.objects.all().delete()

        lancer_la_passe_de_nuit_task()

        passe = PasseDeNuit.objects.get()
        self.assertIsNotNone(passe.terminee_le)
        self.assertEqual(passe.wikis_examines, 0)
