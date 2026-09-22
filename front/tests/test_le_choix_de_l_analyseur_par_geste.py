"""
Chaque geste de production choisit son analyseur.
/ Every production gesture picks its analyzer.

LOCALISATION : front/tests/test_le_choix_de_l_analyseur_par_geste.py

CE QUI MANQUAIT. La création d'un wiki et la synthèse dirigée n'avaient
AUCUN paramètre d'analyseur : elles prenaient le défaut du type, sans
qu'on puisse en désigner un autre ni même savoir lequel avait servi. Seul
le geste de synthèse d'une note laissait choisir.
/ Two of the three gestures took the type's default with no way to pick.

LE CHOIX SE FIGE SUR LE JOB, jamais relu à l'exécution. Entre la demande
et son tour dans la file, l'analyseur par défaut peut changer : relire le
défaut au moment de produire ferait mentir la provenance de l'article.
C'est la règle que le job applique déjà au modèle.
/ Frozen on the job: the default can change while the job waits.

LE PRÉFÉRÉ EST EN TÊTE, donc présélectionné — et c'est EXACTEMENT celui
qui aurait servi sans choix, parce que la liste emploie le tri du
résolveur (`-est_par_defaut, name`).
/ The preferred one comes first, and it IS the default that would serve.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import Dossier
from front.tests.test_synthese_phase_c import creer_fixtures_phase_c
from hypostasis_extractor.models import AnalyseurSyntaxique, ExtractionJob


class BaseDuChoix(TestCase):
    """Un carnet, deux rédacteurs. / A notebook and two writers."""

    def setUp(self):
        self.fixtures = creer_fixtures_phase_c()
        self.carnet = self.fixtures["carnet"]
        self.demandeur = self.fixtures["demandeur"]
        self.client.force_login(self.demandeur)

        self.redacteur_prefere = self.fixtures["analyseur_de_redaction"]
        self.autre_redacteur = AnalyseurSyntaxique.objects.create(
            name="Autre rédacteur", type_analyseur="rediger_un_article",
            is_active=True, est_par_defaut=False,
        )
        self.redacteur_inactif = AnalyseurSyntaxique.objects.create(
            name="Rédacteur retiré", type_analyseur="rediger_un_article",
            is_active=False,
        )


class LeChoixALaCreationD_unWikiTest(BaseDuChoix):
    """Le formulaire propose, et le job retient. / Offered, then kept."""

    def test_le_formulaire_propose_les_redacteurs_le_prefere_en_tete(self):
        # L'onglet est un PARTIAL : un acces direct redirige vers
        # l'ecran du carnet, ou il serait rendu nu.
        # / The tab is a partial: a direct hit redirects.
        reponse = self.client.get(
            f"/carnets/{self.carnet.pk}/wikis/", HTTP_HX_REQUEST="true",
        )

        contenu = reponse.content.decode()
        self.assertIn('data-testid="select-analyseur-wiki"', contenu)
        self.assertIn(self.redacteur_prefere.name, contenu)
        self.assertIn(self.autre_redacteur.name, contenu)
        # Un analyseur retiré ne se propose pas.
        # / A deactivated analyzer is not offered.
        self.assertNotIn(self.redacteur_inactif.name, contenu)
        # Le préféré vient AVANT l'autre : c'est lui que le navigateur
        # sélectionne. / The preferred one comes first.
        self.assertLess(
            contenu.index(self.redacteur_prefere.name),
            contenu.index(self.autre_redacteur.name),
        )

    def test_le_job_retient_l_analyseur_choisi(self):
        from unittest.mock import patch

        with patch("front.tasks.produire_un_wiki_task.delay"):
            self.client.post(f"/carnets/{self.carnet.pk}/wikis/", {
                "sujet": "Le seuil",
                "analyseur_id": self.autre_redacteur.pk,
            })

        job = ExtractionJob.objects.filter(
            raw_result__contains={"est_wiki": True},
        ).latest("created_at")
        self.assertEqual(
            job.raw_result["analyseur_id"], self.autre_redacteur.pk,
        )

    def test_sans_choix_le_job_retient_le_prefere(self):
        from unittest.mock import patch

        with patch("front.tasks.produire_un_wiki_task.delay"):
            self.client.post(f"/carnets/{self.carnet.pk}/wikis/", {
                "sujet": "Le seuil",
            })

        job = ExtractionJob.objects.filter(
            raw_result__contains={"est_wiki": True},
        ).latest("created_at")
        self.assertEqual(
            job.raw_result["analyseur_id"], self.redacteur_prefere.pk,
        )

    def test_un_choix_inatteignable_retombe_sur_le_prefere(self):
        # Le paramètre vient du client : rien n'empêche d'y poser l'id
        # d'un analyseur retiré, ou d'un autre type. On ne l'honore pas.
        # / The parameter comes from the client: an unofferable id is
        # ignored, never honoured.
        from unittest.mock import patch

        with patch("front.tasks.produire_un_wiki_task.delay"):
            self.client.post(f"/carnets/{self.carnet.pk}/wikis/", {
                "sujet": "Le seuil",
                "analyseur_id": self.redacteur_inactif.pk,
            })

        job = ExtractionJob.objects.filter(
            raw_result__contains={"est_wiki": True},
        ).latest("created_at")
        self.assertEqual(
            job.raw_result["analyseur_id"], self.redacteur_prefere.pk,
        )


class LeChoixALaCreationD_uneSyntheseDirigeeTest(BaseDuChoix):
    """Le même choix, sur l'autre geste de carnet."""

    def test_le_formulaire_propose_les_redacteurs(self):
        reponse = self.client.get(
            f"/carnets/{self.carnet.pk}/syntheses/", HTTP_HX_REQUEST="true",
        )

        contenu = reponse.content.decode()
        self.assertIn(
            'data-testid="select-analyseur-synthese-dirigee"', contenu,
        )
        self.assertIn(self.redacteur_prefere.name, contenu)
        self.assertNotIn(self.redacteur_inactif.name, contenu)

    def test_le_job_retient_l_analyseur_choisi(self):
        from unittest.mock import patch

        with patch("front.tasks.produire_une_synthese_de_carnet_task.delay"):
            self.client.post(f"/carnets/{self.carnet.pk}/syntheses/", {
                "titre": "Synthèse du conseil",
                "analyseur_id": self.autre_redacteur.pk,
            })

        job = ExtractionJob.objects.filter(
            raw_result__contains={"est_synthese_carnet": True},
        ).latest("created_at")
        self.assertEqual(
            job.raw_result["analyseur_id"], self.autre_redacteur.pk,
        )


class L_analyseurFigeSurLeJobSertALaProductionTest(BaseDuChoix):
    """
    Le prompt part avec l'analyseur du GESTE, pas celui du moment.
    / The prompt uses the gesture's analyzer, not the current default.
    """

    def test_le_prompt_emploie_l_analyseur_fige_meme_si_le_defaut_a_change(self):
        from unittest.mock import patch

        from core.models import Page, TypeDeNote, Wiki
        from core.services.corpus import ranger_une_note_dans_un_carnet
        from hypostasis_extractor.models import PromptPiece

        PromptPiece.objects.create(
            analyseur=self.autre_redacteur, role="instruction",
            content="LE PRÉAMBULE DE L'AUTRE RÉDACTEUR.", order=0,
        )
        page_du_wiki = Page.objects.create(
            title="Wiki — Le seuil", text_readability="",
            html_readability="", html_original="",
            content_hash="hash-choix-wiki", type_de_note=TypeDeNote.WIKI,
            owner=self.demandeur,
        )
        ranger_une_note_dans_un_carnet(
            page_du_wiki, self.carnet, self.demandeur,
        )
        wiki = Wiki.objects.create(
            page=page_du_wiki, dossier=self.carnet, sujet="Le seuil",
        )
        job = ExtractionJob.objects.create(
            page=page_du_wiki, ai_model=self.fixtures["modele_ia"],
            name="Wiki", prompt_description="t", status="pending",
            raw_result={
                "est_wiki": True, "wiki_id": wiki.pk,
                "analyseur_id": self.autre_redacteur.pk,
            },
        )

        # Le défaut bascule APRÈS la demande, pendant que le job attend.
        # / The default flips after the request, while the job waits.
        self.redacteur_prefere.est_par_defaut = False
        self.redacteur_prefere.save(update_fields=["est_par_defaut"])

        reponse = (
            f"## Le seuil\n\nActé."
            f"[[ext:{self.fixtures['extraction_seuil'].pk}]]\n\n"
            f"CITATIONS_USED: ext:{self.fixtures['extraction_seuil'].pk}"
        )
        from front.tasks import produire_un_wiki_task

        with patch(
            "core.llm_providers.appeler_llm", return_value=reponse,
        ) as appel, patch("front.tasks.enchainer_la_verification"):
            produire_un_wiki_task(job.pk)

        prompt_parti = appel.call_args_list[0].args[1]
        self.assertIn("LE PRÉAMBULE DE L'AUTRE RÉDACTEUR.", prompt_parti)

    def test_la_provenance_nomme_l_analyseur_fige(self):
        from unittest.mock import patch

        from core.models import Page, TypeDeNote, Wiki
        from core.services.corpus import ranger_une_note_dans_un_carnet
        from hypostasis_extractor.models import (
            ProvenanceDeProduction, PromptPiece,
        )

        PromptPiece.objects.create(
            analyseur=self.autre_redacteur, role="instruction",
            content="Rédige autrement.", order=0,
        )
        page_du_wiki = Page.objects.create(
            title="Wiki — Le quorum", text_readability="",
            html_readability="", html_original="",
            content_hash="hash-choix-provenance", type_de_note=TypeDeNote.WIKI,
            owner=self.demandeur,
        )
        ranger_une_note_dans_un_carnet(
            page_du_wiki, self.carnet, self.demandeur,
        )
        wiki = Wiki.objects.create(
            page=page_du_wiki, dossier=self.carnet, sujet="Le quorum",
        )
        job = ExtractionJob.objects.create(
            page=page_du_wiki, ai_model=self.fixtures["modele_ia"],
            name="Wiki", prompt_description="t", status="pending",
            raw_result={
                "est_wiki": True, "wiki_id": wiki.pk,
                "analyseur_id": self.autre_redacteur.pk,
            },
        )
        reponse = (
            f"## Le quorum\n\nActé."
            f"[[ext:{self.fixtures['extraction_seuil'].pk}]]\n\n"
            f"CITATIONS_USED: ext:{self.fixtures['extraction_seuil'].pk}"
        )
        from front.tasks import produire_un_wiki_task

        with patch(
            "core.llm_providers.appeler_llm", return_value=reponse,
        ), patch("front.tasks.enchainer_la_verification"):
            produire_un_wiki_task(job.pk)

        provenance = ProvenanceDeProduction.objects.get(job=job)
        self.assertEqual(provenance.analyseur, self.autre_redacteur)
