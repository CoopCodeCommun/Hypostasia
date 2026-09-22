"""
Quel prompt a écrit ce paragraphe ?
/ Which prompt wrote this paragraph?

LOCALISATION : hypostasis_extractor/tests/test_la_provenance_d_une_production.py

CE QUE CES TESTS PROTEGENT. Avant ce chantier, `prompt_description`
portait ONZE formes differentes selon l'appelant (mesure du 1er septembre
2026 sur 154 jobs) : tantot une etiquette de trente-huit caracteres,
tantot le preambule systeme entier, jamais le prompt REELLEMENT envoye —
sur un job de synthese mesure, 75 928 caracteres assembles contre 1 239
enregistres.

La provenance repond a deux questions, et a elles seules :
- quel prompt a produit ce texte ?
- ce prompt a-t-il change entre deux tours ?

ELLE NE PASSE PAS PAR `ExtractionJob`, et un test l'epingle. Trois
raisons : `/api/extraction-jobs/` rend `prompt_description` ET
`raw_result` a qui accede a la note ; le menu des taches charge trente
jobs COMPLETS sans `.only()` ni `.defer()` ; et un assemblage pese 25 000
a 80 000 caracteres de corpus.
/ Provenance never rides on ExtractionJob: the API exposes it, the task
menu loads whole rows, and an assembly weighs tens of thousands of chars.

CE QU'ELLE NE GARDE PAS : le texte du prompt. Seulement son EMPREINTE et
sa longueur. Le texte integral est un autre chantier
(`PLAN/TODO/2026-08-23-garder-le-texte-integral-d-un-prompt.md`).
/ It keeps a fingerprint and a length, never the text itself.
"""

import hashlib
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from core.models import (
    MotifDeTourDeWiki, Page, TourDeWiki, TypeDeNote, Wiki,
)
from core.services.corpus import ranger_une_note_dans_un_carnet
from front.tests.test_synthese_phase_c import creer_fixtures_phase_c
from hypostasis_extractor.models import (
    CheminDeProduction, ExtractionJob, ProvenanceDeProduction,
)


class BaseD_uneProduction(TestCase):
    """Un carnet, une note analysee, un wiki. / A notebook and a wiki."""

    def setUp(self):
        self.fixtures = creer_fixtures_phase_c()
        self.page_du_wiki = Page.objects.create(
            title="Wiki — Le seuil", text_readability="",
            html_readability="", html_original="",
            content_hash="hash-provenance-wiki", type_de_note=TypeDeNote.WIKI,
            owner=self.fixtures["demandeur"],
        )
        ranger_une_note_dans_un_carnet(
            self.page_du_wiki, self.fixtures["carnet"],
            self.fixtures["demandeur"],
        )
        self.wiki = Wiki.objects.create(
            page=self.page_du_wiki, dossier=self.fixtures["carnet"],
            sujet="Le seuil de passage en assemblée",
        )

    def _reponse_d_article(self):
        return (
            f"## Le seuil\n\nLe seuil est acté."
            f"[[ext:{self.fixtures['extraction_seuil'].pk}]]\n\n"
            f"CITATIONS_USED: ext:{self.fixtures['extraction_seuil'].pk}"
        )

    def _produire_le_wiki(self):
        job = ExtractionJob.objects.create(
            page=self.page_du_wiki, ai_model=self.fixtures["modele_ia"],
            name="Production de wiki", prompt_description="t",
            status="pending",
            raw_result={"est_wiki": True, "wiki_id": self.wiki.pk},
        )
        from front.tasks import produire_un_wiki_task

        with patch(
            "core.llm_providers.appeler_llm",
            return_value=self._reponse_d_article(),
        ), patch("front.tasks.enchainer_la_verification"):
            produire_un_wiki_task(job.pk)
        return job


class LaProvenanceD_unWikiTest(BaseD_uneProduction):
    """Ce qu'une production d'article laisse derriere elle."""

    def test_une_production_ecrit_sa_provenance(self):
        job = self._produire_le_wiki()

        provenance = ProvenanceDeProduction.objects.get(job=job)
        self.assertEqual(provenance.chemin, CheminDeProduction.WIKI)
        self.assertEqual(provenance.modele, self.fixtures["modele_ia"])

    def test_l_empreinte_est_celle_du_prompt_reellement_assemble(self):
        from front.tasks import assembler_le_prompt_de_wiki

        prompt_attendu, _ids = assembler_le_prompt_de_wiki(self.wiki)
        job = self._produire_le_wiki()

        provenance = ProvenanceDeProduction.objects.get(job=job)
        self.assertEqual(
            provenance.empreinte,
            hashlib.sha256(prompt_attendu.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(provenance.longueur, len(prompt_attendu))

    def test_les_extractions_montrees_sont_gardees_triees(self):
        # Un `set` s'itere dans un ordre que rien ne garantit : versee
        # telle quelle, la liste changerait d'une production a l'autre
        # sans qu'aucune extraction n'ait bouge.
        # / A set iterates in no guaranteed order.
        job = self._produire_le_wiki()

        provenance = ProvenanceDeProduction.objects.get(job=job)
        self.assertEqual(
            provenance.extractions_montrees,
            sorted(provenance.extractions_montrees),
        )
        self.assertIn(
            self.fixtures["extraction_seuil"].pk,
            provenance.extractions_montrees,
        )

    def test_changer_une_piece_de_prompt_change_l_empreinte(self):
        # LA PIECE DU REDACTEUR, pas celle du synthetiseur de note.
        # Depuis le typage des analyseurs, un article prend son preambule
        # dans un analyseur `rediger_un_article` : editer celui de la
        # synthese d'une note ne change plus rien a l'empreinte d'un
        # wiki, et c'est justement ce que la separation voulait obtenir.
        # / The writer's piece, not the note-synthesizer's: since typing,
        # an article takes its preamble from a `rediger_un_article`.
        from hypostasis_extractor.models import PromptPiece

        premier_job = self._produire_le_wiki()
        empreinte_avant = ProvenanceDeProduction.objects.get(
            job=premier_job,
        ).empreinte

        piece = PromptPiece.objects.filter(
            analyseur=self.fixtures["analyseur_de_redaction"],
        ).first()
        piece.content = piece.content + "\nSois bref."
        piece.save(update_fields=["content"])
        second_job = self._produire_le_wiki()

        empreinte_apres = ProvenanceDeProduction.objects.get(
            job=second_job,
        ).empreinte
        self.assertNotEqual(empreinte_avant, empreinte_apres)

    def test_deux_productions_a_base_inchangee_gardent_la_meme_empreinte(self):
        # C'est la question a laquelle la provenance existe pour
        # repondre : « le prompt a-t-il change entre deux tours ? »
        # / The very question provenance exists to answer.
        premier_job = self._produire_le_wiki()
        second_job = self._produire_le_wiki()

        self.assertEqual(
            ProvenanceDeProduction.objects.get(job=premier_job).empreinte,
            ProvenanceDeProduction.objects.get(job=second_job).empreinte,
        )


class LaProvenanceNePassePasParLeJobTest(BaseD_uneProduction):
    """
    La decision epinglee : l'assemblage n'entre JAMAIS dans
    `ExtractionJob`. / The pinned decision.

    Sans ce test, la prochaine main qui cherchera « ou est le prompt ? »
    le remettra dans `prompt_description`, ou il est deja passe sous
    huit conventions differentes — et il repartira dans l'API.
    / Without it, the next hand puts the prompt back where it leaked.
    """

    def test_le_job_ne_porte_pas_l_assemblage(self):
        from front.tasks import assembler_le_prompt_de_wiki

        prompt_assemble, _ids = assembler_le_prompt_de_wiki(self.wiki)
        job = self._produire_le_wiki()

        job.refresh_from_db()
        self.assertNotEqual(job.prompt_description, prompt_assemble)
        self.assertNotIn(
            "=== EXTRACTIONS DU PÉRIMÈTRE ===", job.prompt_description,
        )

    def test_l_api_d_un_job_ne_rend_aucune_provenance(self):
        from hypostasis_extractor.serializers import (
            ExtractionJobDetailSerializer,
        )

        job = self._produire_le_wiki()

        champs_rendus = set(ExtractionJobDetailSerializer(job).data.keys())
        self.assertNotIn("provenances", champs_rendus)
        self.assertNotIn("empreinte", champs_rendus)


class LaProvenanceD_unTourDeNuitTest(TestCase):
    """
    La nuit aussi laisse sa provenance, et on remonte au modele depuis
    le tour. / The night leaves provenance too.
    """

    def setUp(self):
        self.fixtures = creer_fixtures_phase_c()
        self.page_du_wiki = Page.objects.create(
            title="Wiki de la nuit",
            text_readability=(
                "## Le seuil\n\nLe seuil est acté."
                f"[[ext:{self.fixtures['extraction_seuil'].pk}]]\n"
            ),
            html_readability="<p>w</p>", html_original="<p>w</p>",
            content_hash="hash-provenance-nuit", type_de_note=TypeDeNote.WIKI,
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
        # Les fixtures naissent toutes a la meme seconde, donc le wiki
        # nait APRES ses extractions : rien n'aurait « paru depuis le
        # dernier tour », et la passe n'aurait aucune raison de le
        # reprendre. Le cas reel est l'inverse — un article produit
        # hier, des extractions arrivees aujourd'hui.
        # / Otherwise the wiki is born after its own extractions.
        Wiki.objects.filter(pk=self.wiki.pk).update(
            derniere_mise_a_jour=timezone.now() - timedelta(days=1),
        )
        self.wiki.refresh_from_db()

    def _passer_la_nuit(self):
        from django.core.management import call_command

        operations = (
            '[{"type": "append_to_section", "section": "Le seuil", '
            '"contenu": "L\'ajournement coûte.'
            f'[[ext:{self.fixtures["extraction_cout"].pk}]]"}}]'
        )
        with patch(
            "core.llm_providers.appeler_llm", return_value=operations,
        ), patch("front.tasks.enchainer_la_verification"):
            call_command("mettre_a_jour_les_wikis", verbosity=0)

    def test_le_tour_de_nuit_ecrit_sa_provenance(self):
        self._passer_la_nuit()

        tour = TourDeWiki.objects.get(
            wiki=self.wiki, motif=MotifDeTourDeWiki.MAJ_NOCTURNE,
        )
        provenance = ProvenanceDeProduction.objects.get(tour_de_wiki=tour)
        self.assertEqual(provenance.chemin, CheminDeProduction.MAJ_WIKI)

    def test_on_remonte_au_modele_depuis_le_tour(self):
        # LA question de la note : « quel modele a ecrit un article de
        # nuit ? » / The note's question.
        self._passer_la_nuit()

        tour = TourDeWiki.objects.get(
            wiki=self.wiki, motif=MotifDeTourDeWiki.MAJ_NOCTURNE,
        )
        self.assertEqual(
            tour.provenances.get().modele, self.fixtures["modele_ia"],
        )

    def test_la_provenance_de_nuit_porte_aussi_son_job(self):
        self._passer_la_nuit()

        tour = TourDeWiki.objects.get(
            wiki=self.wiki, motif=MotifDeTourDeWiki.MAJ_NOCTURNE,
        )
        provenance = ProvenanceDeProduction.objects.get(tour_de_wiki=tour)
        self.assertEqual(provenance.job, tour.job)


class LaProvenanceD_uneAnalyseTest(TestCase):
    """
    Une analyse trace CE QUE NOUS COMPOSONS, et le dit.
    / An analysis traces what WE compose, and says so.
    """

    def setUp(self):
        self.fixtures = creer_fixtures_phase_c()

    def test_une_analyse_ecrit_une_provenance_par_envoi_pas_par_chunk(self):
        # Une par CHUNK repeterait la meme empreinte des dizaines de
        # fois : le preambule est le meme pour toute la page. Une par
        # ENVOI, en revanche, est juste — une relance renvoie vraiment
        # le prompt.
        # / One per chunk would repeat the same fingerprint; one per
        # send is right, because a re-run really re-sends.
        from hypostasis_extractor.services.analyse_par_element import (
            analyser_une_page_par_element,
        )

        job = ExtractionJob.objects.create(
            page=self.fixtures["note_source"],
            ai_model=self.fixtures["modele_ia"],
            name="Analyse", prompt_description="Extrais les hypostases.",
            status="pending",
            raw_result={"analyseur_id": self.fixtures["analyseur"].pk},
        )

        analyser_une_page_par_element(
            self.fixtures["note_source"], job,
            appeler_le_llm=lambda texte, job_en_cours: [],
        )

        provenance = ProvenanceDeProduction.objects.get(job=job)
        self.assertEqual(provenance.chemin, CheminDeProduction.ANALYSE)
        self.assertEqual(provenance.analyseur, self.fixtures["analyseur"])
        self.assertEqual(provenance.modele, self.fixtures["modele_ia"])

    def test_une_relance_laisse_une_seconde_trace(self):
        # Un job relance — retry Celery, ou relance manuelle d'un job en
        # erreur — RENVOIE le prompt. Deux envois, deux traces : c'est
        # pourquoi les provenances ne sont pas purgees avec les
        # extractions au debut d'une reprise.
        # / A re-run really re-sends: two sends, two traces.
        from hypostasis_extractor.services.analyse_par_element import (
            analyser_une_page_par_element,
        )

        job = ExtractionJob.objects.create(
            page=self.fixtures["note_source"],
            ai_model=self.fixtures["modele_ia"],
            name="Analyse", prompt_description="Extrais les hypostases.",
            status="pending",
            raw_result={"analyseur_id": self.fixtures["analyseur"].pk},
        )

        analyser_une_page_par_element(
            self.fixtures["note_source"], job,
            appeler_le_llm=lambda texte, job_en_cours: [],
        )
        analyser_une_page_par_element(
            self.fixtures["note_source"], job,
            appeler_le_llm=lambda texte, job_en_cours: [],
        )

        self.assertEqual(
            ProvenanceDeProduction.objects.filter(job=job).count(), 2,
        )

    def test_l_empreinte_suit_les_extractions_d_un_exemple(self):
        # CE QUI PART, c'est le texte de l'exemple ET ses extractions
        # attendues avec leurs attributs — jamais son NOM. Une empreinte
        # calculee sur le nom repondrait « rien n'a change » apres
        # l'edition d'une extraction d'exemple, qui change pourtant ce
        # que le modele recoit.
        # / What is sent: the example text and its expected extractions,
        # never its name.
        from hypostasis_extractor.models import (
            AnalyseurExample, ExampleExtraction,
        )
        from hypostasis_extractor.services.analyse_par_element import (
            analyser_une_page_par_element,
        )

        exemple = AnalyseurExample.objects.filter(
            analyseur=self.fixtures["analyseur"],
        ).first()
        if exemple is None:
            exemple = AnalyseurExample.objects.create(
                analyseur=self.fixtures["analyseur"],
                name="Exemple", example_text="Le seuil est acté.", order=0,
            )
        extraction_d_exemple = ExampleExtraction.objects.create(
            example=exemple, extraction_class="donnee",
            extraction_text="Le seuil est acté.", order=0,
        )

        def analyser():
            job = ExtractionJob.objects.create(
                page=self.fixtures["note_source"],
                ai_model=self.fixtures["modele_ia"],
                name="Analyse", prompt_description="Extrais.",
                status="pending",
                raw_result={"analyseur_id": self.fixtures["analyseur"].pk},
            )
            analyser_une_page_par_element(
                self.fixtures["note_source"], job,
                appeler_le_llm=lambda texte, job_en_cours: [],
            )
            return ProvenanceDeProduction.objects.get(job=job).empreinte

        empreinte_avant = analyser()

        extraction_d_exemple.extraction_text = "Le quorum est acté."
        extraction_d_exemple.save(update_fields=["extraction_text"])

        self.assertNotEqual(empreinte_avant, analyser())


class LaProvenanceD_uneSyntheseDeNoteTest(TestCase):
    """`synthetiser_page_task` trace son envoi. / The note synthesis."""

    def setUp(self):
        self.fixtures = creer_fixtures_phase_c()

    def test_une_synthese_de_note_ecrit_sa_provenance(self):
        from front.tasks import synthetiser_page_task

        job = ExtractionJob.objects.create(
            page=self.fixtures["note_source"],
            ai_model=self.fixtures["modele_ia"],
            name="Synthèse", prompt_description="t", status="pending",
            raw_result={
                "est_synthese": True,
                "analyseur_id": self.fixtures["analyseur"].pk,
            },
        )
        reponse = (
            f"Le seuil est acté.[[ext:{self.fixtures['extraction_seuil'].pk}]]"
            f"\n\nCITATIONS_USED: ext:"
            f"{self.fixtures['extraction_seuil'].pk}"
        )

        with patch(
            "core.llm_providers.appeler_llm", return_value=reponse,
        ), patch("front.tasks.enchainer_la_verification"):
            synthetiser_page_task(job.pk)

        provenance = ProvenanceDeProduction.objects.get(job=job)
        self.assertEqual(provenance.chemin, CheminDeProduction.SYNTHESE_NOTE)
        self.assertEqual(provenance.analyseur, self.fixtures["analyseur"])
        self.assertGreater(provenance.longueur, 0)
