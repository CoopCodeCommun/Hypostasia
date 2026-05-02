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
    """A.8 : tests adaptes au helper _calculer_consensus simplifie.
    Le helper retourne {total, commentees, non_commentees, pourcentage}.
    / A.8: tests adapted to simplified _calculer_consensus helper.
    Returns {total, commentees, non_commentees, pourcentage}."""

    def setUp(self):
        from core.models import Page, Dossier
        from hypostasis_extractor.models import (
            CommentaireExtraction, ExtractionJob, ExtractedEntity,
        )
        self.user = User.objects.create_user("user_test", password="test1234")
        self.dossier = Dossier.objects.create(name="Test", owner=self.user)
        self.page = Page.objects.create(
            title="Test", dossier=self.dossier, owner=self.user,
            html_readability="<p>Test</p>", text_readability="Test text",
        )
        self.job = ExtractionJob.objects.create(
            page=self.page, status="completed", name="Test",
        )
        # 2 entites visibles avec commentaire (-> "commente" via signal)
        # 3 entites visibles sans commentaire (-> "nouveau")
        # 1 entite masquee (exclue par le helper)
        # / 2 visible with comment (signal sets "commente")
        # / 3 visible without comment ("nouveau")
        # / 1 hidden (excluded by helper)
        for _i in range(2):
            entite_commentee = ExtractedEntity.objects.create(
                job=self.job, extraction_class="theorie",
                extraction_text="texte", statut_debat="nouveau",
                start_char=0, end_char=5,
            )
            CommentaireExtraction.objects.create(
                entity=entite_commentee, user=self.user, commentaire="OK",
            )
        for _i in range(3):
            ExtractedEntity.objects.create(
                job=self.job, extraction_class="theorie",
                extraction_text="texte", statut_debat="nouveau",
                start_char=0, end_char=5,
            )
        ExtractedEntity.objects.create(
            job=self.job, extraction_class="theorie",
            extraction_text="texte", statut_debat="nouveau",
            start_char=0, end_char=5,
            masquee=True,
        )

    def test_calculer_consensus_compteurs_corrects(self):
        """Le helper retourne total visibles (5), commentees (2), non_commentees (3)."""
        from front.views import _calculer_consensus
        consensus = _calculer_consensus(self.page)
        self.assertEqual(consensus["total"], 5)
        self.assertEqual(consensus["commentees"], 2)
        self.assertEqual(consensus["non_commentees"], 3)

    def test_calculer_consensus_pourcentage(self):
        """Le pourcentage est 100 * commentees / total = 40%."""
        from front.views import _calculer_consensus
        consensus = _calculer_consensus(self.page)
        self.assertEqual(consensus["pourcentage"], 40)


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

