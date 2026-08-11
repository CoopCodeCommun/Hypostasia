"""
Tests de la phase H synthese : endpoints § 10 et taches carnet-niveau.
/ Phase H tests: § 10 endpoints and notebook-level tasks.

LOCALISATION : front/tests/test_synthese_phase_h.py

Le carnet gagne ses onglets reels : wikis (vivants, § 3.1) et syntheses
dirigees (actes dates, § 3.2), produits par des taches qui appliquent
le contrat de la phase C (marqueurs [[ext:N]], ligne CITATIONS_USED,
perimetre OBLIGATOIRE) et l'applieur de la phase F.
/ Real tabs: living wikis and dated syntheses, built on the phase C
contract and the phase F applier.
"""

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import (
    CategorieDossier, Dossier, ListeDeCategories, Page, SourceLink,
    SyntheseDirigee, TypeDeNote, TypeLien, Wiki,
)
from core.services.corpus import ranger_une_note_dans_un_carnet
from front.tests.test_synthese_phase_c import creer_fixtures_phase_c
from hypostasis_extractor.models import ExtractedEntity, ExtractionJob

User = get_user_model()


class TacheWikiTest(TestCase):
    """produire_un_wiki_task : l'article vivant. / The living article."""

    def setUp(self):
        self.fixtures = creer_fixtures_phase_c()
        self.page_du_wiki = Page.objects.create(
            title="Wiki — Le seuil", text_readability="",
            html_readability="", html_original="",
            content_hash="hash-h-wiki", type_de_note=TypeDeNote.WIKI,
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

    def _lancer(self, reponse_llm):
        job = ExtractionJob.objects.create(
            page=self.page_du_wiki, ai_model=self.fixtures["modele_ia"],
            name="Production de wiki", prompt_description="t",
            status="pending",
            raw_result={
                "est_wiki": True, "wiki_id": self.wiki.pk,
                "demandeur_id": self.fixtures["demandeur"].pk,
            },
        )
        with patch(
            "core.llm_providers.appeler_llm", return_value=reponse_llm,
        ):
            from front.tasks import produire_un_wiki_task
            produire_un_wiki_task(job.pk)
        job.refresh_from_db()
        return job

    def test_l_article_est_produit_avec_ses_citations(self):
        pk_seuil = self.fixtures["extraction_seuil"].pk
        reponse = (
            "## Le seuil\n\n"
            f"Le seuil déclenche l'assemblée.[[ext:{pk_seuil}]]\n\n"
            f"CITATIONS_USED: {pk_seuil}\n"
        )

        job = self._lancer(reponse)

        self.assertEqual(job.status, "completed")
        self.page_du_wiki.refresh_from_db()
        self.assertIn(f"[[ext:{pk_seuil}]]", self.page_du_wiki.text_readability)
        self.assertNotIn("CITATIONS_USED", self.page_du_wiki.text_readability)
        self.assertEqual(
            SourceLink.objects.filter(
                page_cible=self.page_du_wiki, type_lien=TypeLien.CITE,
            ).count(),
            1,
        )

    def test_un_article_sans_aucune_citation_est_refuse(self):
        # Un perimetre non vide et ZERO marqueur : le modele a redige
        # sans citer — un article sans preuve n'est pas un succes dans
        # un systeme de synthese SOURCEE. Echec bruyant.
        # / A citation-less article over a non-empty scope fails loudly.
        reponse_sans_citation = (
            "## La gouvernance\n\n"
            "Un long developpement fluide sans aucune preuve.\n\n"
            "CITATIONS_USED: aucune\n"
        )

        job = self._lancer(reponse_sans_citation)

        self.assertEqual(job.status, "error")
        self.assertIn("citation", job.error_message.lower())
        self.page_du_wiki.refresh_from_db()
        self.assertEqual(self.page_du_wiki.text_readability, "")

    def test_un_marqueur_hors_perimetre_du_wiki_est_retire(self):
        # Le perimetre d'un wiki = les notes sources de SON carnet.
        # / A wiki's scope = its notebook's source notes.
        autre_note = Page.objects.create(
            title="Hors carnet", text_readability="x",
            html_readability="<p>x</p>", html_original="<p>x</p>",
            content_hash="hash-h-hors",
        )
        job_hors = ExtractionJob.objects.create(
            page=autre_note, name="Analyse hors", status="completed",
            ai_model=None,
        )
        extraction_hors = ExtractedEntity.objects.create(
            job=job_hors, extraction_class="donnee",
            extraction_text="fait etranger", start_char=0, end_char=13,
        )
        pk_seuil = self.fixtures["extraction_seuil"].pk
        reponse = (
            f"Un fait.[[ext:{pk_seuil}]] "
            f"Un autre.[[ext:{extraction_hors.pk}]]\n\n"
            f"CITATIONS_USED: {pk_seuil}, {extraction_hors.pk}\n"
        )

        job = self._lancer(reponse)

        self.assertEqual(job.status, "completed")
        self.assertEqual(job.raw_result["marqueurs_retires"], [extraction_hors.pk])


class TacheSyntheseDeCarnetTest(TestCase):
    """La synthese dirigee AU NIVEAU CARNET. / Notebook-level synthesis."""

    def setUp(self):
        self.fixtures = creer_fixtures_phase_c()
        # Une seconde note analysee dans le carnet, et une synthese qui
        # ne doit JAMAIS entrer dans le perimetre (§ 3.3).
        # / A second analyzed note, and a synthesis that must stay out.
        self.seconde_note = Page.objects.create(
            title="Deuxième séance", text_readability="Le budget est voté.",
            html_readability="<p>b</p>", html_original="<p>b</p>",
            content_hash="hash-h-note2", owner=self.fixtures["demandeur"],
        )
        ranger_une_note_dans_un_carnet(
            self.seconde_note, self.fixtures["carnet"],
            self.fixtures["demandeur"],
        )
        job_2 = ExtractionJob.objects.create(
            page=self.seconde_note, name="Analyse 2", status="completed",
            ai_model=None,
        )
        self.extraction_budget = ExtractedEntity.objects.create(
            job=job_2, extraction_class="donnee",
            extraction_text="Le budget est voté.",
            start_char=0, end_char=19,
        )
        vieille_synthese = Page.objects.create(
            title="Vieille synthèse", text_readability="s",
            html_readability="<p>s</p>", html_original="<p>s</p>",
            content_hash="hash-h-vieille", type_de_note=TypeDeNote.SYNTHESE,
        )
        ranger_une_note_dans_un_carnet(
            vieille_synthese, self.fixtures["carnet"],
            self.fixtures["demandeur"],
        )

    def _lancer(self, reponse_llm, **raw_en_plus):
        # Comme la vue le fera : la Page de l'article et l'acte date
        # (perimetre fige AU MOMENT DU GESTE) existent AVANT la tache ;
        # la tache remplit. / As the view does: the article page and the
        # frozen act exist BEFORE the task; the task fills them.
        from core.services.synthese import notes_sources_du_carnet

        notes_figees = list(
            notes_sources_du_carnet(self.fixtures["carnet"])
            .values_list("pk", flat=True)
        )
        page_de_synthese = Page.objects.create(
            title="Synthèse du conseil", text_readability="",
            html_readability="", html_original="",
            content_hash="hash-h-sc", type_de_note=TypeDeNote.SYNTHESE,
            owner=self.fixtures["demandeur"],
        )
        ranger_une_note_dans_un_carnet(
            page_de_synthese, self.fixtures["carnet"],
            self.fixtures["demandeur"],
        )
        dirigee = SyntheseDirigee.objects.create(
            page=page_de_synthese, dossier=self.fixtures["carnet"],
            produite_par=self.fixtures["demandeur"],
            perimetre_d_extractions_fige=True,
        )
        dirigee.notes_du_perimetre.set(notes_figees)

        contenu = {
            "est_synthese_carnet": True,
            "demandeur_id": self.fixtures["demandeur"].pk,
            "notes_du_perimetre": notes_figees,
        }
        contenu.update(raw_en_plus)
        job = ExtractionJob.objects.create(
            page=page_de_synthese, ai_model=self.fixtures["modele_ia"],
            name="Synthèse de carnet", prompt_description="t",
            status="pending", raw_result=contenu,
        )
        with patch(
            "core.llm_providers.appeler_llm", return_value=reponse_llm,
        ):
            from front.tasks import produire_une_synthese_de_carnet_task
            produire_une_synthese_de_carnet_task(job.pk)
        job.refresh_from_db()
        return job

    def test_le_perimetre_multi_notes_est_fige_sans_les_syntheses(self):
        pk_seuil = self.fixtures["extraction_seuil"].pk
        pk_budget = self.extraction_budget.pk
        reponse = (
            "## Décisions\n\n"
            f"Le seuil est acté.[[ext:{pk_seuil}]] "
            f"Le budget est voté.[[ext:{pk_budget}]]\n\n"
            f"CITATIONS_USED: {pk_seuil}, {pk_budget}\n"
        )

        job = self._lancer(reponse)

        self.assertEqual(job.status, "completed")
        page_synthese = Page.objects.get(pk=job.raw_result["page_synthese_id"])
        self.assertEqual(page_synthese.type_de_note, TypeDeNote.SYNTHESE)
        dirigee = page_synthese.synthese_dirigee
        # Les DEUX notes, JAMAIS la vieille synthese (§ 3.3).
        self.assertEqual(
            sorted(p.pk for p in dirigee.notes_du_perimetre.all()),
            sorted([self.fixtures["note_source"].pk, self.seconde_note.pk]),
        )
        self.assertTrue(dirigee.perimetre_d_extractions_fige)
        # Les citations des deux notes sont indexees.
        self.assertEqual(
            SourceLink.objects.filter(
                page_cible=page_synthese, type_lien=TypeLien.CITE,
            ).count(),
            2,
        )
        # Rangee dans le carnet, titre de la demande.
        self.assertEqual(
            [a.dossier_id for a in page_synthese.appartenances_dossiers.all()],
            [self.fixtures["carnet"].pk],
        )
        self.assertEqual(dirigee.dossier_id, self.fixtures["carnet"].pk)


class TacheMajWikiTest(TestCase):
    """proposer_une_maj_de_wiki_task : les operations. / The proposal."""

    def setUp(self):
        self.fixtures = creer_fixtures_phase_c()
        self.page_du_wiki = Page.objects.create(
            title="Wiki seuil",
            text_readability=(
                "## Le seuil\n\nLe seuil est acté."
                f"[[ext:{self.fixtures['extraction_seuil'].pk}]]\n"
            ),
            html_readability="<p>w</p>", html_original="<p>w</p>",
            content_hash="hash-h-maj", type_de_note=TypeDeNote.WIKI,
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

    def _lancer(self, reponse_llm):
        job = ExtractionJob.objects.create(
            page=self.page_du_wiki, ai_model=self.fixtures["modele_ia"],
            name="Proposition de mise à jour", prompt_description="t",
            status="pending",
            raw_result={"est_maj_wiki": True, "wiki_id": self.wiki.pk},
        )
        with patch(
            "core.llm_providers.appeler_llm", return_value=reponse_llm,
        ):
            from front.tasks import proposer_une_maj_de_wiki_task
            proposer_une_maj_de_wiki_task(job.pk)
        job.refresh_from_db()
        return job

    def test_les_operations_sont_stockees_avec_la_fraicheur(self):
        pk_cout = self.fixtures["extraction_cout"].pk
        operations = [{
            "type": "append_to_section", "section": "Le seuil",
            "contenu": f"L'ajournement coûte.[[ext:{pk_cout}]]",
        }]

        job = self._lancer(json.dumps(operations))

        self.assertEqual(job.status, "completed")
        self.assertEqual(
            job.raw_result["operations"][0]["section"], "Le seuil",
        )
        # La proposition porte l'updated_at de l'article (addendum n°1).
        self.assertEqual(
            job.raw_result["updated_at_de_l_article"],
            self.page_du_wiki.updated_at.isoformat(),
        )

    def test_une_reponse_non_json_echoue_bruyamment(self):
        job = self._lancer("Voici quelques idées de modifications...")

        self.assertEqual(job.status, "error")
        self.assertIsNone(job.raw_result.get("operations"))


class EndpointsWikiTest(TestCase):
    """WikiViewSet § 10. / The § 10 wiki endpoints."""

    def setUp(self):
        self.fixtures = creer_fixtures_phase_c()
        self.client.login(username="demandeur_synthese", password="test1234")

    def _creer_un_wiki(self, texte="## Le seuil\n\nActé.\n"):
        page = Page.objects.create(
            title="Wiki seuil", text_readability=texte,
            html_readability="<p>w</p>", html_original="<p>w</p>",
            content_hash="hash-h-ew", type_de_note=TypeDeNote.WIKI,
            owner=self.fixtures["demandeur"],
        )
        ranger_une_note_dans_un_carnet(
            page, self.fixtures["carnet"], self.fixtures["demandeur"],
        )
        return Wiki.objects.create(
            page=page, dossier=self.fixtures["carnet"], sujet="Le seuil",
        )

    @patch("front.tasks.produire_un_wiki_task.delay")
    def test_creer_un_wiki_lance_la_tache(self, mock_delay):
        reponse = self.client.post(
            f"/carnets/{self.fixtures['carnet'].pk}/wikis/",
            {"sujet": "Le seuil de passage en assemblée"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(reponse.status_code, 200)
        wiki = Wiki.objects.get(dossier=self.fixtures["carnet"])
        self.assertEqual(wiki.sujet, "Le seuil de passage en assemblée")
        self.assertEqual(wiki.page.type_de_note, TypeDeNote.WIKI)
        self.assertTrue(mock_delay.called)

    def test_creer_un_wiki_exige_l_ecriture(self):
        autre = User.objects.create_user(
            username="tiers_h", password="test1234",
        )
        carnet_d_autrui = Dossier.objects.create(
            name="Carnet d'autrui H", owner=autre,
        )

        reponse = self.client.post(
            f"/carnets/{carnet_d_autrui.pk}/wikis/",
            {"sujet": "Intrusion"}, HTTP_HX_REQUEST="true",
        )

        self.assertIn(reponse.status_code, (403, 404))
        self.assertFalse(Wiki.objects.exists())

    def test_la_liste_des_wikis_du_carnet(self):
        self._creer_un_wiki()

        reponse = self.client.get(
            f"/carnets/{self.fixtures['carnet'].pk}/wikis/",
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertIn("Le seuil", reponse.content.decode())

    def test_l_article_d_un_wiki_se_lit(self):
        wiki = self._creer_un_wiki()

        reponse = self.client.get(
            f"/wikis/{wiki.pk}/", HTTP_HX_REQUEST="true",
        )

        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode()
        self.assertIn("Le seuil", contenu)

    @patch("front.tasks.proposer_une_maj_de_wiki_task.delay")
    def test_previsualiser_maj_lance_la_proposition(self, mock_delay):
        wiki = self._creer_un_wiki()

        reponse = self.client.post(
            f"/wikis/{wiki.pk}/mise_a_jour/", {},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(mock_delay.called)

    def test_appliquer_une_proposition_perimee_est_refuse(self):
        wiki = self._creer_un_wiki()
        job = ExtractionJob.objects.create(
            page=wiki.page, name="Proposition", status="completed",
            ai_model=None,
            raw_result={
                "est_maj_wiki": True, "wiki_id": wiki.pk,
                "operations": [{"type": "no_change", "section": "Le seuil"}],
                "updated_at_de_l_article": "2020-01-01T00:00:00+00:00",
            },
        )

        reponse = self.client.post(
            f"/wikis/{wiki.pk}/appliquer/",
            {"job_id": job.pk, "indices": "0"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(reponse.status_code, 409)

    def test_appliquer_des_operations_retenues(self):
        pk_seuil = self.fixtures["extraction_seuil"].pk
        wiki = self._creer_un_wiki(
            f"## Le seuil\n\nActé.[[ext:{pk_seuil}]]\n"
        )
        wiki.page.refresh_from_db()
        job = ExtractionJob.objects.create(
            page=wiki.page, name="Proposition", status="completed",
            ai_model=None,
            raw_result={
                "est_maj_wiki": True, "wiki_id": wiki.pk,
                "operations": [
                    {"type": "append_to_section", "section": "Le seuil",
                     "contenu": f"Complément.[[ext:{pk_seuil}]]"},
                    {"type": "append_to_section", "section": "Fantôme",
                     "contenu": f"Perdu.[[ext:{pk_seuil}]]"},
                ],
                "updated_at_de_l_article":
                    wiki.page.updated_at.isoformat(),
            },
        )

        reponse = self.client.post(
            f"/wikis/{wiki.pk}/appliquer/",
            {"job_id": job.pk, "indices": "0"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(reponse.status_code, 200)
        wiki.refresh_from_db()
        wiki.page.refresh_from_db()
        self.assertIn("Complément.", wiki.page.text_readability)
        self.assertNotIn("Perdu.", wiki.page.text_readability)
        # Le tour est incremente (etalon:1188-1194 via § 3.1).
        self.assertEqual(wiki.tours_de_mise_a_jour, 2)
        # Les citations sont reindexees.
        self.assertEqual(
            SourceLink.objects.filter(
                page_cible=wiki.page, type_lien=TypeLien.CITE,
            ).count(),
            2,
        )


class EndpointsSyntheseCarnetTest(TestCase):
    """Les endpoints § 10 des syntheses dirigees. / Synthesis endpoints."""

    def setUp(self):
        self.fixtures = creer_fixtures_phase_c()
        self.client.login(username="demandeur_synthese", password="test1234")

    @patch("front.tasks.produire_une_synthese_de_carnet_task.delay")
    def test_creer_fige_les_notes_avant_la_tache(self, mock_delay):
        vieille_synthese = Page.objects.create(
            title="Vieille", text_readability="s",
            html_readability="<p>s</p>", html_original="<p>s</p>",
            content_hash="hash-h-esc", type_de_note=TypeDeNote.SYNTHESE,
        )
        ranger_une_note_dans_un_carnet(
            vieille_synthese, self.fixtures["carnet"],
            self.fixtures["demandeur"],
        )

        reponse = self.client.post(
            f"/carnets/{self.fixtures['carnet'].pk}/syntheses/",
            {"titre": "Synthèse du conseil du 12 mars"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(reponse.status_code, 200)
        job = ExtractionJob.objects.filter(
            raw_result__est_synthese_carnet=True,
        ).latest("created_at")
        # Le perimetre est fige A LA DEMANDE (§ 3.2), sans la synthese.
        self.assertEqual(
            job.raw_result["notes_du_perimetre"],
            [self.fixtures["note_source"].pk],
        )
        self.assertTrue(mock_delay.called)

    def test_ecartees_et_couverture_repondent(self):
        # Une dirigee produite par la tache phase C (figee).
        from front.tests.test_synthese_phase_c import (
            creer_le_job_de_synthese, reponse_llm_correcte,
        )
        job = creer_le_job_de_synthese(self.fixtures)
        with patch(
            "core.llm_providers.appeler_llm",
            return_value=reponse_llm_correcte(self.fixtures),
        ):
            from front.tasks import synthetiser_page_task
            synthetiser_page_task(job.pk)
        job.refresh_from_db()
        page_synthese = Page.objects.get(pk=job.raw_result["page_synthese_id"])

        reponse_ecartees = self.client.get(
            f"/syntheses/{page_synthese.pk}/ecartees/", HTTP_HX_REQUEST="true",
        )
        reponse_couverture = self.client.get(
            f"/syntheses/{page_synthese.pk}/couverture/",
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(reponse_ecartees.status_code, 200)
        self.assertEqual(reponse_couverture.status_code, 200)

    @patch("front.tasks.verifier_les_citations_task.delay")
    def test_verifier_est_un_geste_explicite(self, mock_delay):
        page_synthese = Page.objects.create(
            title="Synthèse à vérifier", text_readability="s",
            html_readability="<p>s</p>", html_original="<p>s</p>",
            content_hash="hash-h-verif", type_de_note=TypeDeNote.SYNTHESE,
            owner=self.fixtures["demandeur"],
        )
        ranger_une_note_dans_un_carnet(
            page_synthese, self.fixtures["carnet"],
            self.fixtures["demandeur"],
        )
        SyntheseDirigee.objects.create(
            page=page_synthese, dossier=self.fixtures["carnet"],
        )

        reponse = self.client.post(
            f"/syntheses/{page_synthese.pk}/verifier/", {},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(mock_delay.called)


class TroncatureDesEcarteesTest(TestCase):
    """
    La troncature du volet des ecartees est ANNONCEE (recette connectee
    du 10 aout, defaut B3) : le resume disait « 458 » quand le volet en
    montrait 200, sans un mot — deux chiffres contradictoires.
    / The 200-row truncation of the discarded-extractions panel is now
    announced instead of silently contradicting the summary.
    """

    def setUp(self):
        self.fixtures = creer_fixtures_phase_c()
        self.client.login(username="demandeur_synthese", password="test1234")

    def test_la_troncature_des_ecartees_est_annoncee(self):
        from core.models import SyntheseDirigee
        from core.services.synthese import extractions_ecartees
        from front.tests.test_synthese_phase_c import (
            creer_le_job_de_synthese, reponse_llm_correcte,
        )
        from hypostasis_extractor.models import ExtractedEntity, ExtractionJob

        job = creer_le_job_de_synthese(self.fixtures)
        with patch(
            "core.llm_providers.appeler_llm",
            return_value=reponse_llm_correcte(self.fixtures),
        ):
            from front.tasks import synthetiser_page_task
            synthetiser_page_task(job.pk)
        job.refresh_from_db()
        page_synthese = Page.objects.get(pk=job.raw_result["page_synthese_id"])

        # Gonfler le perimetre FIGE au-dela de la fenetre de 200.
        # / Inflate the frozen scope beyond the 200-row window.
        dirigee = SyntheseDirigee.objects.get(page=page_synthese)
        job_source = ExtractionJob.objects.create(
            page=self.fixtures["note_source"], status="completed",
        )
        nouvelles = ExtractedEntity.objects.bulk_create([
            ExtractedEntity(
                job=job_source, extraction_class="principe",
                extraction_text=f"extraction de masse {indice}",
                start_char=0, end_char=10,
            )
            for indice in range(215)
        ])
        dirigee.extractions_du_perimetre.add(*nouvelles)

        nombre_total = extractions_ecartees(page_synthese).count()
        self.assertGreater(nombre_total, 200)

        reponse = self.client.get(
            f"/syntheses/{page_synthese.pk}/ecartees/", HTTP_HX_REQUEST="true",
        )
        contenu = reponse.content.decode()

        # Le TOTAL est affiche, la fenetre est annoncee, et le nombre
        # de lignes correspond a la fenetre. / The total is shown, the
        # window announced, the row count matches the window.
        self.assertIn(str(nombre_total), contenu)
        self.assertIn("200 premières", contenu)
        self.assertEqual(
            contenu.count('data-testid="synthese-ecartee"'), 200,
        )
