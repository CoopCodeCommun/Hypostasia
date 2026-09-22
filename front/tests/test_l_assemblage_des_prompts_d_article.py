"""
L'assemblage d'un prompt d'article se fait SANS appeler de modele.
/ Assembling an article prompt calls no model.

LOCALISATION : front/tests/test_l_assemblage_des_prompts_d_article.py

POURQUOI CES TESTS EXISTENT. La provenance d'un article repose sur une
EMPREINTE du prompt qui l'a produit. Une empreinte n'a de sens qu'a deux
conditions, et aucune des deux ne va de soi :

- l'assemblage doit etre REJOUABLE sans appeler — donc sans facturer —
  le moindre modele ;
- il doit etre DETERMINISTE : deux assemblages de la meme base rendent
  le meme texte, au caractere pres. Sinon « le prompt a-t-il change
  entre deux tours ? » n'a pas de reponse.

Le piege est mecanique : `notes_du_perimetre_d_un_wiki` rend un queryset
`.distinct()` sans `order_by`, et `Page` n'a aucun `Meta.ordering`.
PostgreSQL est alors libre de rendre les notes dans l'ordre qu'il veut.
/ The scope queryset has no ordering and Page has no default one, so the
database may return the notes in any order.

ET LE TEST QUI COMPTE LE PLUS est le dernier de chaque classe : le texte
rendu par l'assembleur est EXACTEMENT celui qui part au modele. Sans
lui, l'assembleur deviendrait une seconde version du prompt — c'est
exactement ce qui est arrive a
`benchmarks/chaine_complete/comparer_la_chaine.py`, qui reassemble le
prompt a la main tout en annoncant « le prompt de production ».
/ The assembler must BE the production prompt, not a second copy of it.
"""

from unittest.mock import patch

from django.test import TestCase

from core.models import Page, SyntheseDirigee, TypeDeNote, Wiki
from core.services.corpus import ranger_une_note_dans_un_carnet
from front.tests.test_synthese_phase_c import creer_fixtures_phase_c
from hypostasis_extractor.models import ExtractionJob


class BaseD_unArticle(TestCase):
    """Un carnet, deux notes analysees, un wiki. / A notebook and a wiki."""

    def setUp(self):
        self.fixtures = creer_fixtures_phase_c()
        # UNE SECONDE NOTE SOURCE : avec une seule, tout ordre de notes
        # se vaut et le test de determinisme ne prouverait rien.
        # / A second source note: with one, any order looks stable.
        self.seconde_note = Page.objects.create(
            title="Conseil du 19 mars",
            text_readability="Le quorum se discute.",
            html_readability="<p>q</p>", html_original="<p>q</p>",
            content_hash="hash-assemblage-seconde",
            source_type="web", owner=self.fixtures["demandeur"],
        )
        ranger_une_note_dans_un_carnet(
            self.seconde_note, self.fixtures["carnet"],
            self.fixtures["demandeur"],
        )
        job_de_la_seconde = ExtractionJob.objects.create(
            page=self.seconde_note, ai_model=self.fixtures["modele_ia"],
            name="Analyse", prompt_description="p", status="completed",
        )
        from hypostasis_extractor.models import ExtractedEntity

        self.extraction_du_quorum = ExtractedEntity.objects.create(
            job=job_de_la_seconde, extraction_class="donnee",
            extraction_text="Le quorum se discute.",
            start_char=0, end_char=21, statut_debat="nouveau",
        )

        self.page_du_wiki = Page.objects.create(
            title="Wiki — Le seuil", text_readability="",
            html_readability="", html_original="",
            content_hash="hash-assemblage-wiki", type_de_note=TypeDeNote.WIKI,
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


class L_assemblageDuPromptDeWikiTest(BaseD_unArticle):
    """`assembler_le_prompt_de_wiki`. / The wiki prompt assembler."""

    def test_deux_assemblages_successifs_rendent_le_meme_texte(self):
        from front.tasks import assembler_le_prompt_de_wiki

        premier, _ids = assembler_le_prompt_de_wiki(self.wiki)
        second, _ids = assembler_le_prompt_de_wiki(self.wiki)

        self.assertEqual(premier, second)

    def test_l_assemblage_n_appelle_aucun_modele(self):
        # Une empreinte qu'on ne peut pas recalculer sans payer n'est
        # pas une empreinte. / A fingerprint you must pay to recompute
        # is not one.
        from front.tasks import assembler_le_prompt_de_wiki

        with patch("core.llm_providers.appeler_llm") as appel:
            assembler_le_prompt_de_wiki(self.wiki)

        self.assertFalse(appel.called)

    def test_les_notes_sont_montrees_par_ordre_de_cle(self):
        # L'ordre du queryset du perimetre n'est garanti par rien : il
        # est fixe ICI, sinon l'empreinte bougerait sans que la base
        # change. / The scope queryset guarantees no order.
        from front.tasks import assembler_le_prompt_de_wiki

        prompt, _ids = assembler_le_prompt_de_wiki(self.wiki)

        position_de_la_premiere = prompt.find(
            self.fixtures["note_source"].title
        )
        position_de_la_seconde = prompt.find(self.seconde_note.title)
        self.assertNotEqual(position_de_la_premiere, -1)
        self.assertNotEqual(position_de_la_seconde, -1)
        self.assertLess(position_de_la_premiere, position_de_la_seconde)

    def test_l_assemblage_rend_les_identifiants_montres_au_modele(self):
        from front.tasks import assembler_le_prompt_de_wiki

        prompt, identifiants = assembler_le_prompt_de_wiki(self.wiki)

        self.assertIn(self.extraction_du_quorum.pk, identifiants)
        self.assertIn(
            f"ext:{self.extraction_du_quorum.pk}", prompt,
        )

    def test_le_texte_assemble_est_celui_qui_part_au_modele(self):
        from front.tasks import assembler_le_prompt_de_wiki, produire_un_wiki_task

        attendu, _ids = assembler_le_prompt_de_wiki(self.wiki)
        job = ExtractionJob.objects.create(
            page=self.page_du_wiki, ai_model=self.fixtures["modele_ia"],
            name="Production de wiki", prompt_description="t",
            status="pending",
            raw_result={"est_wiki": True, "wiki_id": self.wiki.pk},
        )
        reponse = (
            f"## Le seuil\n\nLe seuil est acté."
            f"[[ext:{self.fixtures['extraction_seuil'].pk}]]\n\n"
            f"CITATIONS_USED: ext:{self.fixtures['extraction_seuil'].pk}"
        )

        with patch(
            "core.llm_providers.appeler_llm", return_value=reponse,
        ) as appel, patch("front.tasks.enchainer_la_verification"):
            produire_un_wiki_task(job.pk)

        # LE PREMIER appel, jamais `call_args` : celui-la rend le
        # DERNIER, et une production enchaine la verification des
        # citations — donc un second appel, au juge.
        # / The FIRST call: a production chains citation verification.
        self.assertEqual(appel.call_args_list[0].args[1], attendu)


class L_assemblageDuPromptDeSyntheseDirigeeTest(BaseD_unArticle):
    """`assembler_le_prompt_de_synthese_dirigee`. / The directed one."""

    def setUp(self):
        super().setUp()
        self.page_de_synthese = Page.objects.create(
            title="Synthèse du conseil", text_readability="",
            html_readability="", html_original="",
            content_hash="hash-assemblage-synthese",
            type_de_note=TypeDeNote.SYNTHESE,
            owner=self.fixtures["demandeur"],
        )
        ranger_une_note_dans_un_carnet(
            self.page_de_synthese, self.fixtures["carnet"],
            self.fixtures["demandeur"],
        )
        self.synthese = SyntheseDirigee.objects.create(
            page=self.page_de_synthese, dossier=self.fixtures["carnet"],
        )
        self.synthese.notes_du_perimetre.set(
            [self.fixtures["note_source"], self.seconde_note]
        )

    def test_deux_assemblages_successifs_rendent_le_meme_texte(self):
        from front.tasks import assembler_le_prompt_de_synthese_dirigee

        premier, _ids = assembler_le_prompt_de_synthese_dirigee(
            self.page_de_synthese
        )
        second, _ids = assembler_le_prompt_de_synthese_dirigee(
            self.page_de_synthese
        )

        self.assertEqual(premier, second)

    def test_les_notes_sont_montrees_par_ordre_de_cle(self):
        # Une M2M non triee rend ses lignes dans l'ordre que la base
        # veut. / An unordered M2M returns rows in any order.
        from front.tasks import assembler_le_prompt_de_synthese_dirigee

        prompt, _ids = assembler_le_prompt_de_synthese_dirigee(
            self.page_de_synthese
        )

        self.assertLess(
            prompt.find(self.fixtures["note_source"].title),
            prompt.find(self.seconde_note.title),
        )

    def test_le_texte_assemble_est_celui_qui_part_au_modele(self):
        from front.tasks import (
            assembler_le_prompt_de_synthese_dirigee,
            produire_une_synthese_de_carnet_task,
        )

        attendu, _ids = assembler_le_prompt_de_synthese_dirigee(
            self.page_de_synthese
        )
        job = ExtractionJob.objects.create(
            page=self.page_de_synthese, ai_model=self.fixtures["modele_ia"],
            name="Synthèse dirigée", prompt_description="t",
            status="pending",
            raw_result={"est_synthese_carnet": True},
        )
        reponse = (
            f"## Le seuil\n\nLe seuil est acté."
            f"[[ext:{self.fixtures['extraction_seuil'].pk}]]\n\n"
            f"CITATIONS_USED: ext:{self.fixtures['extraction_seuil'].pk}"
        )

        with patch(
            "core.llm_providers.appeler_llm", return_value=reponse,
        ) as appel, patch("front.tasks.enchainer_la_verification"):
            produire_une_synthese_de_carnet_task(job.pk)

        self.assertEqual(appel.call_args_list[0].args[1], attendu)


class L_assemblageDuPromptDeMiseAJourTest(BaseD_unArticle):
    """`assembler_le_prompt_de_mise_a_jour`. / The update assembler."""

    def setUp(self):
        super().setUp()
        # L'article cite DEJA une extraction : la mise a jour porte sur
        # ce qu'il a laisse de cote. On passe par le VRAI chemin
        # d'ecriture : « ecartee » est une difference d'ensembles entre
        # le perimetre et les `SourceLink` INDEXES, jamais une lecture
        # du texte. Poser `text_readability` a la main laisserait zero
        # citation indexee, donc tout le perimetre ecarte.
        # / The real write path: "left out" is a set difference against
        # indexed SourceLinks, not a reading of the text.
        from core.models import MotifDeTourDeWiki
        from front.tasks import _ecrire_le_corps_d_un_article

        with patch("front.tasks.enchainer_la_verification"):
            _ecrire_le_corps_d_un_article(
                self.page_du_wiki,
                "## Le seuil\n\nLe seuil est acté."
                f"[[ext:{self.fixtures['extraction_seuil'].pk}]]\n",
                {self.fixtures["extraction_seuil"].pk},
                motif_du_tour=MotifDeTourDeWiki.CREATION,
                wiki_du_tour=self.wiki,
            )
        self.page_du_wiki.refresh_from_db()

    def test_deux_assemblages_successifs_rendent_le_meme_texte(self):
        from front.tasks import assembler_le_prompt_de_mise_a_jour

        premier, _ids = assembler_le_prompt_de_mise_a_jour(self.wiki)
        second, _ids = assembler_le_prompt_de_mise_a_jour(self.wiki)

        self.assertEqual(premier, second)

    def test_l_assemblage_n_appelle_aucun_modele(self):
        from front.tasks import assembler_le_prompt_de_mise_a_jour

        with patch("core.llm_providers.appeler_llm") as appel:
            assembler_le_prompt_de_mise_a_jour(self.wiki)

        self.assertFalse(appel.called)

    def test_l_assemblage_rend_les_extractions_ecartees(self):
        from front.tasks import assembler_le_prompt_de_mise_a_jour

        prompt, identifiants = assembler_le_prompt_de_mise_a_jour(self.wiki)

        # Celle que l'article cite deja n'est PAS proposee ; les autres,
        # si. / What the article already cites is not offered again.
        self.assertNotIn(self.fixtures["extraction_seuil"].pk, identifiants)
        self.assertIn(self.fixtures["extraction_cout"].pk, identifiants)
        self.assertIn(self.extraction_du_quorum.pk, identifiants)
        self.assertIn(f"ext:{self.extraction_du_quorum.pk}", prompt)

    def test_le_texte_assemble_est_celui_qui_part_au_modele(self):
        from front.tasks import (
            assembler_le_prompt_de_mise_a_jour,
            construire_la_proposition_d_operations,
        )

        attendu, _ids = assembler_le_prompt_de_mise_a_jour(self.wiki)

        with patch(
            "core.llm_providers.appeler_llm", return_value="[]",
        ) as appel:
            construire_la_proposition_d_operations(
                self.wiki, self.fixtures["modele_ia"],
            )

        self.assertEqual(appel.call_args.args[1], attendu)
