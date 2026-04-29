"""
Tests pour la PHASE-29 : synthese deliberative dans le drawer
+ bool est_par_defaut sur les analyseurs.
/ Tests for PHASE-29: deliberative synthesis in drawer
+ est_par_defaut bool on analyzers.
"""
import json

from django.contrib.auth.models import User
from django.test import TestCase

from hypostasis_extractor.models import AnalyseurSyntaxique


class EstParDefautModeleTests(TestCase):
    """Tests sur le bool est_par_defaut et sa logique de save()."""

    def setUp(self):
        # Trois analyseurs du meme type / Three analyzers of the same type
        self.analyseur_a = AnalyseurSyntaxique.objects.create(
            name="Synthese A", type_analyseur="synthetiser",
            inclure_texte_original=True,
        )
        self.analyseur_b = AnalyseurSyntaxique.objects.create(
            name="Synthese B", type_analyseur="synthetiser",
            inclure_texte_original=True,
        )
        # Un analyseur d'un autre type / One analyzer of another type
        self.analyseur_autre_type = AnalyseurSyntaxique.objects.create(
            name="Hypostasia",
            type_analyseur="analyser",
            est_par_defaut=True,
        )

    def test_cocher_un_analyseur_comme_default(self):
        # Cocher A comme default → A doit avoir est_par_defaut=True
        # / Mark A as default → A must have est_par_defaut=True
        self.analyseur_a.est_par_defaut = True
        self.analyseur_a.save()
        self.analyseur_a.refresh_from_db()
        self.assertTrue(self.analyseur_a.est_par_defaut)

    def test_cocher_un_default_decoche_les_autres_du_meme_type(self):
        # B etait deja default → cocher A doit decocher B
        # / B was already default → marking A must uncheck B
        self.analyseur_b.est_par_defaut = True
        self.analyseur_b.save()
        self.analyseur_b.refresh_from_db()
        self.assertTrue(self.analyseur_b.est_par_defaut)

        self.analyseur_a.est_par_defaut = True
        self.analyseur_a.save()
        self.analyseur_b.refresh_from_db()
        self.assertFalse(self.analyseur_b.est_par_defaut)
        self.analyseur_a.refresh_from_db()
        self.assertTrue(self.analyseur_a.est_par_defaut)

    def test_cocher_un_default_ne_touche_pas_les_autres_types(self):
        # Cocher un analyseur synthetiser ne doit pas toucher l'analyseur "analyser"
        # / Marking a synthetiser analyzer must not affect the "analyser" type
        self.analyseur_a.est_par_defaut = True
        self.analyseur_a.save()
        self.analyseur_autre_type.refresh_from_db()
        self.assertTrue(self.analyseur_autre_type.est_par_defaut)


class PartialUpdateEstParDefautToastTests(TestCase):
    """Tests sur le toast info quand on coche est_par_defaut sur un analyseur."""

    def setUp(self):
        self.user_admin = User.objects.create_superuser(
            "admin_test", "admin@test.local", "test1234",
        )
        self.client.force_login(self.user_admin)
        self.analyseur_a = AnalyseurSyntaxique.objects.create(
            name="Synthese A", type_analyseur="synthetiser",
            inclure_texte_original=True,
        )
        self.analyseur_b = AnalyseurSyntaxique.objects.create(
            name="Synthese B", type_analyseur="synthetiser",
            inclure_texte_original=True,
            est_par_defaut=True,
        )

    def test_patch_est_par_defaut_true_renvoie_toast_si_un_autre_etait_default(self):
        # PATCH A.est_par_defaut=True → B doit etre decoche + toast info renvoye
        # / PATCH A.est_par_defaut=True → B must be unchecked + info toast returned
        reponse = self.client.patch(
            f"/api/analyseurs/{self.analyseur_a.pk}/",
            data=json.dumps({"est_par_defaut": True}),
            content_type="application/json",
        )
        self.assertEqual(reponse.status_code, 200)
        # Verifier que le HX-Trigger contient le toast info
        # / Check that HX-Trigger contains the info toast
        trigger = reponse.headers.get("HX-Trigger", "")
        self.assertTrue(trigger, "HX-Trigger absent")
        donnees_trigger = json.loads(trigger)
        self.assertIn("showToast", donnees_trigger)
        self.assertEqual(donnees_trigger["showToast"]["icon"], "info")
        self.assertIn("Synthese B", donnees_trigger["showToast"]["message"])

    def test_patch_est_par_defaut_true_sans_autre_default_ne_declenche_pas_toast(self):
        # On retire le default de B / Remove default from B
        AnalyseurSyntaxique.objects.filter(pk=self.analyseur_b.pk).update(
            est_par_defaut=False,
        )

        reponse = self.client.patch(
            f"/api/analyseurs/{self.analyseur_a.pk}/",
            data=json.dumps({"est_par_defaut": True}),
            content_type="application/json",
        )
        self.assertEqual(reponse.status_code, 200)
        trigger = reponse.headers.get("HX-Trigger", "")
        # Pas de toast attendu / No toast expected
        self.assertFalse(trigger, f"HX-Trigger inattendu : {trigger}")

    def test_patch_autre_champ_ne_declenche_pas_toast(self):
        # PATCH name uniquement → pas de toast
        # / PATCH name only → no toast
        reponse = self.client.patch(
            f"/api/analyseurs/{self.analyseur_a.pk}/",
            data=json.dumps({"name": "Nouveau nom"}),
            content_type="application/json",
        )
        self.assertEqual(reponse.status_code, 200)
        trigger = reponse.headers.get("HX-Trigger", "")
        self.assertFalse(trigger, f"HX-Trigger inattendu : {trigger}")


class CalculerConsensusHelperTests(TestCase):
    """Tests sur le helper _calculer_consensus."""

    def setUp(self):
        from core.models import Page, Dossier
        from hypostasis_extractor.models import ExtractionJob, ExtractedEntity
        self.user = User.objects.create_user("user_test", password="test1234")
        self.dossier = Dossier.objects.create(name="Test", owner=self.user)
        self.page = Page.objects.create(
            title="Test", dossier=self.dossier, owner=self.user,
            html_readability="<p>Test</p>", text_readability="Test text",
        )
        self.job = ExtractionJob.objects.create(
            page=self.page, status="completed", name="Test",
        )
        # 3 consensuel, 1 discute, 1 controverse, 1 non_pertinent
        # / 3 consensual, 1 discussed, 1 controversial, 1 non-relevant
        for _i in range(3):
            ExtractedEntity.objects.create(
                job=self.job, extraction_class="theorie",
                extraction_text="texte", statut_debat="consensuel",
                start_char=0, end_char=5,
            )
        ExtractedEntity.objects.create(
            job=self.job, extraction_class="theorie",
            extraction_text="texte", statut_debat="discute",
            start_char=0, end_char=5,
        )
        ExtractedEntity.objects.create(
            job=self.job, extraction_class="theorie",
            extraction_text="texte", statut_debat="controverse",
            start_char=0, end_char=5,
        )
        ExtractedEntity.objects.create(
            job=self.job, extraction_class="theorie",
            extraction_text="texte", statut_debat="non_pertinent",
            start_char=0, end_char=5,
        )

    def test_calculer_consensus_compteurs_corrects(self):
        # Le save() de ExtractedEntity synchronise masquee=True quand non_pertinent.
        # Le helper filtre sur masquee=False donc les non_pertinent ne sont pas comptes.
        # / ExtractedEntity.save() syncs masquee=True for non_pertinent.
        # / Helper filters masquee=False so non_pertinent are not counted.
        from front.views import _calculer_consensus
        consensus = _calculer_consensus(self.page)
        self.assertEqual(consensus["compteur_consensuel"], 3)
        self.assertEqual(consensus["compteur_discute"], 1)
        self.assertEqual(consensus["compteur_controverse"], 1)
        self.assertEqual(consensus["compteur_non_pertinent"], 0)
        # Total visibles : 3 + 1 + 1 = 5 (le non_pertinent est masque)
        # / Total visible: 3 + 1 + 1 = 5 (non_pertinent is hidden)
        self.assertEqual(consensus["total_entites_toutes"], 5)

    def test_calculer_consensus_pourcentage_et_seuil(self):
        from front.views import _calculer_consensus
        consensus = _calculer_consensus(self.page)
        # 3 consensuel sur 5 dans le cycle deliberatif (3+0+1+1)
        # / 3 consensual out of 5 in deliberative cycle
        self.assertEqual(consensus["pourcentage_consensus"], 60)
        self.assertFalse(consensus["seuil_atteint"])  # 60% < 80%
        self.assertEqual(consensus["seuil_consensus"], 80)
        # 2 extractions bloquantes (1 controverse + 1 discute)
        # / 2 blocking extractions (1 controverse + 1 discute)
        self.assertEqual(len(list(consensus["extractions_bloquantes"])), 2)


class PrevisualiserSyntheseTests(TestCase):
    """Tests sur l'endpoint /lire/{pk}/previsualiser_synthese/."""

    def setUp(self):
        from core.models import Page, Dossier, Configuration, AIModel
        self.user = User.objects.create_user("user_test", password="test1234")
        self.client.force_login(self.user)
        self.dossier = Dossier.objects.create(name="Test", owner=self.user)
        self.page = Page.objects.create(
            title="Test", dossier=self.dossier, owner=self.user,
            html_readability="<p>Test</p>", text_readability="Test text",
        )
        self.modele_ia = AIModel.objects.create(
            model_choice="mock", is_active=True,
        )
        config = Configuration.get_solo()
        config.ai_active = True
        config.ai_model = self.modele_ia
        config.save()
        self.analyseur_synthese = AnalyseurSyntaxique.objects.create(
            name="Synthese delib", type_analyseur="synthetiser",
            inclure_extractions=True, inclure_texte_original=True,
            est_par_defaut=True,
        )

    def test_previsualiser_synthese_renvoie_partial(self):
        # Mock _construire_prompt_synthese si pas de job d'analyse pour eviter les erreurs
        # / Mock _construire_prompt_synthese if no analysis job to avoid errors
        from hypostasis_extractor.models import ExtractionJob, ExtractedEntity
        # Creer un job d'analyse complet avec quelques extractions
        # / Create a complete analysis job with some extractions
        job = ExtractionJob.objects.create(
            page=self.page, ai_model=self.modele_ia, status="completed", name="Test",
        )
        ExtractedEntity.objects.create(
            job=job, extraction_class="theorie", extraction_text="texte",
            statut_debat="consensuel", start_char=0, end_char=5,
        )
        reponse = self.client.get(
            f"/lire/{self.page.pk}/previsualiser_synthese/",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode("utf-8")
        self.assertIn("confirmation-synthese", contenu)
        self.assertIn("Synthese delib", contenu)

    def test_previsualiser_sans_analyseur_synthese_renvoie_400(self):
        AnalyseurSyntaxique.objects.filter(type_analyseur="synthetiser").delete()
        reponse = self.client.get(
            f"/lire/{self.page.pk}/previsualiser_synthese/",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 400)
        trigger = reponse.headers.get("HX-Trigger", "")
        self.assertIn("showToast", trigger)
        self.assertIn("error", trigger)

    def test_previsualiser_sans_modele_ia_renvoie_400(self):
        from core.models import Configuration
        config = Configuration.get_solo()
        config.ai_model = None
        config.save()
        reponse = self.client.get(
            f"/lire/{self.page.pk}/previsualiser_synthese/",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 400)

    def test_previsualiser_avec_inclure_extractions_mais_zero_extractions(self):
        # inclure_extractions=True mais pas de job d'analyse → bouton desactive
        # / inclure_extractions=True but no analysis job → button disabled
        reponse = self.client.get(
            f"/lire/{self.page.pk}/previsualiser_synthese/",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode("utf-8")
        # Apostrophe HTML-encodee dans le template, on cherche le mot-cle
        # / Apostrophe HTML-encoded in template, search keyword
        self.assertIn("Lancez", contenu)
        self.assertIn("abord une analyse", contenu)
        # Et le bouton doit etre disabled / And button must be disabled
        self.assertIn("alerte-blocage-synthese", contenu)
        self.assertIn("disabled", contenu)

    def test_previsualiser_avec_les_deux_bool_a_false(self):
        # Les deux bool a False → bouton desactive avec message "configurez"
        # / Both bools False → button disabled with "configure" message
        AnalyseurSyntaxique.objects.filter(pk=self.analyseur_synthese.pk).update(
            inclure_extractions=False,
            inclure_texte_original=False,
        )
        reponse = self.client.get(
            f"/lire/{self.page.pk}/previsualiser_synthese/",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode("utf-8")
        # Apostrophe HTML-encodee dans le template
        # / Apostrophe HTML-encoded in template
        self.assertIn("Configurez", contenu)
        self.assertIn("analyseur pour inclure", contenu)
        self.assertIn("alerte-blocage-synthese", contenu)
        self.assertIn("disabled", contenu)

    def test_previsualiser_select_analyseur_param(self):
        # Si plusieurs analyseurs, ?analyseur_id=N permet de basculer
        # / If multiple analyzers, ?analyseur_id=N switches
        autre_analyseur = AnalyseurSyntaxique.objects.create(
            name="Autre Synthese", type_analyseur="synthetiser",
            inclure_texte_original=True,
        )
        reponse = self.client.get(
            f"/lire/{self.page.pk}/previsualiser_synthese/?analyseur_id={autre_analyseur.pk}",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode("utf-8")
        self.assertIn("Autre Synthese", contenu)


class SyntheseStatusTests(TestCase):
    """Tests sur l'endpoint /lire/{pk}/synthese_status/ (PHASE-29)."""

    def setUp(self):
        from core.models import Page, Dossier, AIModel
        self.user = User.objects.create_user("user_test", password="test1234")
        self.client.force_login(self.user)
        self.dossier = Dossier.objects.create(name="Test", owner=self.user)
        self.page = Page.objects.create(
            title="Test", dossier=self.dossier, owner=self.user,
            html_readability="<p>Test</p>", text_readability="Test text",
        )
        self.modele_ia = AIModel.objects.create(
            model_choice="mock", is_active=True,
        )

    def test_synthese_status_processing_renvoie_polling(self):
        from hypostasis_extractor.models import ExtractionJob
        ExtractionJob.objects.create(
            page=self.page, ai_model=self.modele_ia,
            status="processing", raw_result={"est_synthese": True},
        )
        reponse = self.client.get(
            f"/lire/{self.page.pk}/synthese_status/",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode("utf-8")
        # Le partial polling drawer / Polling drawer partial
        self.assertIn("synthese_status", contenu)
        self.assertIn("Synthèse en cours", contenu)

    def test_synthese_status_completed_renvoie_hx_location_et_fermer_drawer(self):
        # PHASE-29 simplifie : completed renvoie un HX-Location vers /lire/V/
        # (HTMX swap natif de zone-lecture) au lieu d'un OOB complexe.
        # / Simplified: completed returns HX-Location to /lire/V/ instead of OOB.
        from hypostasis_extractor.models import ExtractionJob
        from core.models import Page
        page_v2 = Page.objects.create(
            title="V2", dossier=self.dossier, owner=self.user,
            parent_page=self.page, version_number=2,
            html_readability="<p>V2</p>", text_readability="V2 text",
        )
        ExtractionJob.objects.create(
            page=self.page, ai_model=self.modele_ia,
            status="completed",
            raw_result={
                "est_synthese": True,
                "page_synthese_id": page_v2.pk,
                "version_number": 2,
            },
        )
        reponse = self.client.get(
            f"/lire/{self.page.pk}/synthese_status/",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 200)
        # HX-Location pointe vers la V2 / HX-Location points to V2
        location = reponse.headers.get("HX-Location", "")
        self.assertIn(f"/lire/{page_v2.pk}/", location)
        self.assertIn("zone-lecture", location)
        # HX-Trigger fermerDrawer / HX-Trigger fermerDrawer
        trigger = reponse.headers.get("HX-Trigger", "")
        self.assertIn("fermerDrawer", trigger)

    def test_synthese_status_error_reste_dans_drawer(self):
        from hypostasis_extractor.models import ExtractionJob
        ExtractionJob.objects.create(
            page=self.page, ai_model=self.modele_ia,
            status="error",
            error_message="Erreur LLM test",
            raw_result={"est_synthese": True},
        )
        reponse = self.client.get(
            f"/lire/{self.page.pk}/synthese_status/",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(reponse.status_code, 200)
        contenu = reponse.content.decode("utf-8")
        self.assertIn("Erreur LLM test", contenu)
        self.assertIn("btn-retry-synthese", contenu)


class SyntheseTermineeWebSocketTests(TestCase):
    """Tests sur le handler synthese_terminee du NotificationConsumer (PHASE-29).
    / Tests on the synthese_terminee handler of NotificationConsumer (PHASE-29)."""

    def test_synthese_terminee_envoie_toast_avec_lien_v2(self):
        # Le handler doit emettre un fragment HTML qui contient :
        # - un toast OOB sur #ws-toasts
        # - un lien hx-get vers la page V2
        # - le numero de version
        # / Handler must emit an HTML fragment containing:
        # / - a toast OOB on #ws-toasts
        # / - an hx-get link to the V2 page
        # / - the version number
        import asyncio
        from front.consumers import NotificationConsumer

        consumer = NotificationConsumer()
        fragments_envoyes = []

        async def mock_send(text_data):
            fragments_envoyes.append(text_data)

        consumer.send = mock_send
        asyncio.run(consumer.synthese_terminee({
            "page_synthese_id": 42,
            "version_number": 3,
            "titre_page": "Page Test",
        }))

        self.assertEqual(len(fragments_envoyes), 1)
        fragment_html = fragments_envoyes[0]
        # OOB explicite vers #ws-toasts (la forme courte avec id porteur ne marche
        # pas avec htmx-ext-ws-2.0.4)
        # / Explicit OOB to #ws-toasts (short form with id-bearer doesn't work
        # / with htmx-ext-ws-2.0.4)
        self.assertIn('hx-swap-oob="beforeend:#ws-toasts"', fragment_html)
        # Toast de niveau "succes" / Success-level toast
        self.assertIn("ws-toast--succes", fragment_html)
        # Lien vers la V2 / Link to V2
        self.assertIn("/lire/42/", fragment_html)
        self.assertIn("V3", fragment_html)
        # Titre de la page transmis / Page title relayed
        self.assertIn("Page Test", fragment_html)

    def test_synthese_terminee_sans_page_synthese_id_ne_fait_rien(self):
        # Si le payload est invalide (pas de page_synthese_id), aucun fragment envoye
        # / If payload is invalid (no page_synthese_id), no fragment sent
        import asyncio
        from front.consumers import NotificationConsumer

        consumer = NotificationConsumer()
        fragments_envoyes = []

        async def mock_send(text_data):
            fragments_envoyes.append(text_data)

        consumer.send = mock_send
        asyncio.run(consumer.synthese_terminee({}))
        self.assertEqual(len(fragments_envoyes), 0)


class SynthetiserPageTaskNotificationTests(TestCase):
    """Tests que la tache Celery envoie bien le signal au groupe utilisateur.
    / Tests that the Celery task sends the signal to the user's group."""

    def test_tache_envoie_signal_synthese_terminee_au_groupe_utilisateur(self):
        # On mock l'appel LLM et envoyer_progression_websocket pour intercepter
        # les appels et verifier que le signal est bien envoye au bon groupe.
        # / Mock LLM call and envoyer_progression_websocket to capture calls
        # / and verify the signal is sent to the right group.
        from unittest.mock import patch
        from core.models import Page, Dossier, Configuration, AIModel
        from hypostasis_extractor.models import (
            AnalyseurSyntaxique, ExtractionJob, ExtractedEntity, PromptPiece,
        )

        user = User.objects.create_user("owner_synth", password="test1234")
        dossier = Dossier.objects.create(name="D", owner=user)
        page_source = Page.objects.create(
            title="Page source", dossier=dossier, owner=user,
            html_readability="<p>texte</p>", text_readability="texte source",
        )
        modele = AIModel.objects.create(model_choice="mock", is_active=True)
        config = Configuration.get_solo()
        config.ai_model = modele
        config.ai_active = True
        config.save()

        analyseur = AnalyseurSyntaxique.objects.create(
            name="Synth test", type_analyseur="synthetiser", is_active=True,
            inclure_texte_original=True,
        )
        PromptPiece.objects.create(
            analyseur=analyseur, name="Test", role="instruction",
            content="Synthetise.", order=0,
        )
        # Job d'analyse precedent (necessaire pour que la tache trouve un job source)
        # / Previous analysis job (required so the task finds a source job)
        job_analyse = ExtractionJob.objects.create(
            page=page_source, ai_model=modele, status="completed", name="A",
        )
        ExtractedEntity.objects.create(
            job=job_analyse, extraction_class="theorie",
            extraction_text="texte", statut_debat="consensuel",
            start_char=0, end_char=5,
        )
        # Job de synthese qu'on va executer
        # / Synthesis job to execute
        job_synthese = ExtractionJob.objects.create(
            page=page_source, ai_model=modele, name="Synthese",
            prompt_description="test", status="pending",
            raw_result={"analyseur_id": analyseur.pk, "est_synthese": True},
        )

        # Mock LLM + appel WS / Mock LLM + WS call
        # / appeler_llm est importe a l'interieur de la fonction Celery,
        # / on le mock donc dans son module d'origine.
        with patch("core.llm_providers.appeler_llm", return_value="Texte synthetise."), \
             patch("front.tasks.envoyer_progression_websocket") as mock_ws:
            from front.tasks import synthetiser_page_task
            synthetiser_page_task(job_synthese.pk)

        # Verifier qu'un appel a ete fait au groupe utilisateur avec synthese_terminee
        # / Check a call was made to the user's group with synthese_terminee
        appels_au_user_group = [
            appel for appel in mock_ws.call_args_list
            if appel[0][0] == f"notifications_user_{user.pk}"
        ]
        self.assertEqual(len(appels_au_user_group), 1, "Signal user_group manquant")
        appel = appels_au_user_group[0]
        self.assertEqual(appel[0][1], "synthese_terminee")
        donnees = appel[0][2]
        self.assertIn("page_synthese_id", donnees)
        self.assertIn("version_number", donnees)
        self.assertIn("titre_page", donnees)
        self.assertEqual(donnees["titre_page"], "Page source")
