"""
Tests du branchement des roles : chaque producteur demande le modele de
SON usage. / Role wiring tests: each producer asks for its own model.

LOCALISATION : front/tests/test_les_roles_sont_branches.py

Le role se resout A LA CREATION DU JOB, jamais a l'appel : c'est
`ExtractionJob.ai_model` qui porte la provenance de ce qui a ete produit.
Un job qui estampille un modele et une tache qui en utilise un autre,
c'est une provenance mensongere.

CE QUE CES TESTS VERROUILLENT :
- les trois producteurs d'articles (wiki, mise a jour, synthese de
  carnet) demandent le REDACTEUR ;
- les deux endpoints de verification demandent le JUGE ;
- la tache de synthese par note utilise le modele DU JOB, pas celui que
  la Configuration porte au moment ou elle s'execute ;
- SANS aucune affectation, tout estampille `Configuration.ai_model` —
  c'est ce qui garantit qu'aucun comportement ne change le jour du
  deploiement.
/ Roles resolve at job creation; the three writers ask for the writer,
the two verification endpoints ask for the judge, and with no assignment
at all everything still stamps Configuration.ai_model.
"""

from unittest.mock import patch

from django.test import TestCase

from core.models import (
    AIModel, Configuration, ModeleParRole, Page, RoleDeModele, SyntheseDirigee,
    TypeDeNote, Wiki,
)
from core.services.corpus import ranger_une_note_dans_un_carnet
from front.tests.test_synthese_phase_c import (
    creer_fixtures_phase_c, creer_le_job_de_synthese, reponse_llm_correcte,
)
from hypostasis_extractor.models import ExtractionJob

MOT_DE_PASSE_DU_DEMANDEUR = "test1234"
NOM_DU_DEMANDEUR = "demandeur_synthese"


def _reponse_d_article(extraction):
    """
    Une reponse de modele conforme au contrat de la phase C : un
    marqueur, et la ligne CITATIONS_USED qui detecte les troncatures.
    / A contract-compliant model answer.
    """
    return (
        "## Le seuil\n\n"
        f"Le seuil declenche l'assemblee.[[ext:{extraction.pk}]]\n\n"
        f"CITATIONS_USED: {extraction.pk}\n"
    )


class LeRedacteurEstBrancheTest(TestCase):
    """
    Les trois producteurs d'articles demandent le redacteur.
    / The three article producers ask for the writer.
    """

    def setUp(self):
        self.fixtures = creer_fixtures_phase_c()
        self.redacteur = AIModel.objects.create(
            name="Rédacteur du rôle", model_choice="mock", is_active=True,
        )
        ModeleParRole.objects.create(
            role=RoleDeModele.REDACTEUR_D_ARTICLE, modele=self.redacteur,
        )
        self.client.login(
            username=NOM_DU_DEMANDEUR, password=MOT_DE_PASSE_DU_DEMANDEUR,
        )

    def test_la_creation_d_un_wiki_demande_le_redacteur(self):
        """Le job du wiki estampille le rédacteur, et c'est lui qu'on appelle."""
        with patch(
            "core.llm_providers.appeler_llm",
            return_value=_reponse_d_article(self.fixtures["extraction_seuil"]),
        ) as appel_du_modele:
            reponse = self.client.post(
                f"/carnets/{self.fixtures['carnet'].pk}/wikis/",
                {"sujet": "Le seuil de passage en assemblée"},
                HTTP_HX_REQUEST="true",
            )

        self.assertEqual(reponse.status_code, 200)
        job = ExtractionJob.objects.get(raw_result__est_wiki=True)
        self.assertEqual(job.ai_model, self.redacteur)
        # LE PREMIER APPEL, pas le dernier. Depuis que la verification
        # s'enchaine a l'ecriture d'un article, un SECOND appel suit
        # celui du redacteur — celui du juge — et `call_args` ne rend
        # que le dernier. Ce test dit « c'est le REDACTEUR qui ecrit » :
        # c'est donc le premier appel qu'il doit lire.
        # / The first call, not the last: verification now chains after
        # the writing, and call_args only returns the latest one.
        self.assertEqual(
            appel_du_modele.call_args_list[0][0][0], self.redacteur,
        )

    def test_la_proposition_de_mise_a_jour_demande_le_redacteur(self):
        """Le job de mise à jour estampille le rédacteur."""
        page_du_wiki = Page.objects.create(
            title="Wiki — Le seuil", text_readability="## Le seuil\n\nTexte.",
            html_readability="", html_original="", content_hash="hash-maj",
            type_de_note=TypeDeNote.WIKI, owner=self.fixtures["demandeur"],
        )
        ranger_une_note_dans_un_carnet(
            page_du_wiki, self.fixtures["carnet"], self.fixtures["demandeur"],
        )
        wiki = Wiki.objects.create(
            page=page_du_wiki, dossier=self.fixtures["carnet"],
            sujet="Le seuil",
        )

        with patch("core.llm_providers.appeler_llm", return_value="[]"):
            reponse = self.client.post(
                f"/wikis/{wiki.pk}/mise_a_jour/", {}, HTTP_HX_REQUEST="true",
            )

        self.assertEqual(reponse.status_code, 200)
        job = ExtractionJob.objects.get(raw_result__est_maj_wiki=True)
        self.assertEqual(job.ai_model, self.redacteur)

    def test_la_creation_d_une_synthese_de_carnet_demande_le_redacteur(self):
        """Le job de la synthèse dirigée estampille le rédacteur."""
        with patch(
            "core.llm_providers.appeler_llm",
            return_value=_reponse_d_article(self.fixtures["extraction_seuil"]),
        ) as appel_du_modele:
            reponse = self.client.post(
                f"/carnets/{self.fixtures['carnet'].pk}/syntheses/",
                {"titre": "État des lieux du seuil"},
                HTTP_HX_REQUEST="true",
            )

        self.assertEqual(reponse.status_code, 200)
        job = ExtractionJob.objects.get(raw_result__est_synthese_carnet=True)
        self.assertEqual(job.ai_model, self.redacteur)
        # LE PREMIER APPEL, pas le dernier. Depuis que la verification
        # s'enchaine a l'ecriture d'un article, un SECOND appel suit
        # celui du redacteur — celui du juge — et `call_args` ne rend
        # que le dernier. Ce test dit « c'est le REDACTEUR qui ecrit » :
        # c'est donc le premier appel qu'il doit lire.
        # / The first call, not the last: verification now chains after
        # the writing, and call_args only returns the latest one.
        self.assertEqual(
            appel_du_modele.call_args_list[0][0][0], self.redacteur,
        )


class LeJugeEstBrancheTest(TestCase):
    """
    Les deux endpoints de verification demandent le juge.
    / Both verification endpoints ask for the judge.
    """

    def setUp(self):
        self.fixtures = creer_fixtures_phase_c()
        self.juge = AIModel.objects.create(
            name="Petit juge du rôle", model_choice="mock", is_active=True,
        )
        ModeleParRole.objects.create(
            role=RoleDeModele.JUGE_DE_VERIFICATION, modele=self.juge,
        )
        self.client.login(
            username=NOM_DU_DEMANDEUR, password=MOT_DE_PASSE_DU_DEMANDEUR,
        )

    def _creer_un_article(self, type_de_note, empreinte):
        """Un article rangé dans le carnet des fixtures."""
        page_d_article = Page.objects.create(
            title="Article à vérifier", text_readability="Texte.",
            html_readability="", html_original="", content_hash=empreinte,
            type_de_note=type_de_note, owner=self.fixtures["demandeur"],
        )
        ranger_une_note_dans_un_carnet(
            page_d_article, self.fixtures["carnet"],
            self.fixtures["demandeur"],
        )
        return page_d_article

    def test_verifier_un_wiki_demande_le_juge(self):
        """Le job de vérification d'un wiki estampille le juge."""
        page_du_wiki = self._creer_un_article(TypeDeNote.WIKI, "hash-w-juge")
        wiki = Wiki.objects.create(
            page=page_du_wiki, dossier=self.fixtures["carnet"], sujet="Sujet",
        )

        reponse = self.client.post(
            f"/wikis/{wiki.pk}/verifier/", {}, HTTP_HX_REQUEST="true",
        )

        self.assertEqual(reponse.status_code, 200)
        job = ExtractionJob.objects.get(raw_result__est_verification=True)
        self.assertEqual(job.ai_model, self.juge)

    def test_verifier_une_synthese_demande_le_juge(self):
        """Le job de vérification d'une synthèse estampille le juge."""
        from django.utils import timezone

        page_de_synthese = self._creer_un_article(
            TypeDeNote.SYNTHESE, "hash-s-juge",
        )
        SyntheseDirigee.objects.create(
            page=page_de_synthese, dossier=self.fixtures["carnet"],
            produite_par=self.fixtures["demandeur"],
            produite_le=timezone.now(), perimetre_d_extractions_fige=True,
        )

        reponse = self.client.post(
            f"/syntheses/{page_de_synthese.pk}/verifier/", {},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(reponse.status_code, 200)
        job = ExtractionJob.objects.get(raw_result__est_verification=True)
        self.assertEqual(job.ai_model, self.juge)


class LaSyntheseParNoteSuitSonJobTest(TestCase):
    """
    La tache de synthese par note utilise le modele DU JOB.
    / The per-note synthesis task uses the JOB's model.
    """

    def test_la_tache_utilise_le_modele_estampille_sur_le_job(self):
        """
        Le job porte le modele, la tache l'utilise. Relire la
        Configuration au moment de l'execution ferait mentir la
        provenance des le premier changement de modele entre la demande
        et son tour dans la file.
        / Re-reading the Configuration at run time would make the job's
        stamp a lie as soon as the model changes while it waits.
        """
        fixtures = creer_fixtures_phase_c()
        modele_du_job = AIModel.objects.create(
            name="Rédacteur estampillé", model_choice="mock", is_active=True,
        )
        job = creer_le_job_de_synthese(fixtures)
        job.ai_model = modele_du_job
        job.save(update_fields=["ai_model"])

        with patch(
            "core.llm_providers.appeler_llm",
            return_value=reponse_llm_correcte(fixtures),
        ) as appel_du_modele:
            from front.tasks import synthetiser_page_task
            synthetiser_page_task(job.pk)

        # LE PREMIER APPEL, celui de la REDACTION. La verification
        # s'enchaine desormais a l'ecriture, et son appel — celui du
        # juge — vient apres : `call_args` ne rend que le dernier.
        # / The first call, the writing one: verification chains after.
        self.assertEqual(
            appel_du_modele.call_args_list[0][0][0], modele_du_job,
        )
        self.assertNotEqual(
            Configuration.get_solo().ai_model, modele_du_job,
        )


class SansAffectationRienNeChangeTest(TestCase):
    """
    Table de roles vide : le comportement est celui d'avant, a
    l'identique. / Empty role table: today's behaviour, unchanged.
    """

    def setUp(self):
        self.fixtures = creer_fixtures_phase_c()
        self.client.login(
            username=NOM_DU_DEMANDEUR, password=MOT_DE_PASSE_DU_DEMANDEUR,
        )

    def test_la_table_de_roles_est_bien_vide(self):
        """Le garde-fou du test : aucune affectation dans ce scénario."""
        self.assertEqual(ModeleParRole.objects.count(), 0)

    def test_le_wiki_estampille_le_modele_de_la_configuration(self):
        """Sans rôle affecté, le wiki reprend le modèle de la Configuration."""
        with patch(
            "core.llm_providers.appeler_llm",
            return_value=_reponse_d_article(self.fixtures["extraction_seuil"]),
        ):
            self.client.post(
                f"/carnets/{self.fixtures['carnet'].pk}/wikis/",
                {"sujet": "Le seuil"}, HTTP_HX_REQUEST="true",
            )

        job = ExtractionJob.objects.get(raw_result__est_wiki=True)
        self.assertEqual(job.ai_model, self.fixtures["modele_ia"])
        self.assertEqual(job.ai_model, Configuration.get_solo().ai_model)

    def test_la_verification_estampille_le_modele_de_la_configuration(self):
        """Sans rôle affecté, la vérification reprend celui de la Configuration."""
        page_du_wiki = Page.objects.create(
            title="Wiki sans rôle", text_readability="Texte.",
            html_readability="", html_original="", content_hash="hash-sans",
            type_de_note=TypeDeNote.WIKI, owner=self.fixtures["demandeur"],
        )
        ranger_une_note_dans_un_carnet(
            page_du_wiki, self.fixtures["carnet"], self.fixtures["demandeur"],
        )
        wiki = Wiki.objects.create(
            page=page_du_wiki, dossier=self.fixtures["carnet"], sujet="S",
        )

        self.client.post(
            f"/wikis/{wiki.pk}/verifier/", {}, HTTP_HX_REQUEST="true",
        )

        job = ExtractionJob.objects.get(raw_result__est_verification=True)
        self.assertEqual(job.ai_model, self.fixtures["modele_ia"])
