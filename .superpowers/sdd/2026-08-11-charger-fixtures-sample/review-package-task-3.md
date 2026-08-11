### DIFF DE LA TACHE 3 (par rapport a l'etat apres tache 2)

=== charger_fixtures_sample.py ===
--- .superpowers/sdd/2026-08-11-charger-fixtures-sample/snapshots/task2-commande.py	2026-08-11 15:38:22.339065962 +0200
+++ front/management/commands/charger_fixtures_sample.py	2026-08-11 15:43:37.830642406 +0200
@@ -48,6 +48,8 @@
 
 FICHIER_DE_LA_CAPTURE = "capture-web-badgeons-la-normandie.html"
 FICHIER_DU_MARKDOWN = "PRESENTATION-V3.md"
+FICHIER_DE_LA_TRANSCRIPTION = "fake_debat_ia_transcription.json"
+FICHIER_DU_MP3 = "audio-FR-2locuteur-palaiscesar-14s.mp3"
 
 # L'article d'origine. Sans url, l'idempotence de la capture porterait
 # sur un champ vide et deux captures se confondraient.
@@ -234,6 +236,8 @@
         """
         self._charger_la_capture_web(proprietaire, carnet_des_etalons)
         self._charger_le_markdown(proprietaire, carnet_des_etalons)
+        self._charger_la_transcription_json(proprietaire, carnet_des_etalons)
+        self._charger_le_mp3(proprietaire, carnet_des_etalons)
 
     def _charger_la_capture_web(self, proprietaire, carnet_des_etalons):
         """
@@ -391,3 +395,179 @@
             f"Markdown            : {self._elements_du_resultat(resultat)} élément(s)",
         )
         return page_du_markdown
+
+    def _charger_la_transcription_json(self, proprietaire, carnet_des_etalons):
+        """
+        Cree la note issue de la transcription deja faite, et l'ingere.
+        / Creates the note from the ready-made transcript, and ingests it.
+
+        LOCALISATION : front/management/commands/charger_fixtures_sample.py
+
+        DOCLING N'INTERVIENT PAS : une transcription diarisee est deja
+        structuree. `ingerer_une_transcription_diarisee` la decoupe en
+        tours de parole sans charger le moindre modele.
+        / Docling plays no part: a diarised transcript is already structured.
+
+        ATTENTION — la vue d'import, elle, N'APPELLE PAS cette ingestion
+        (front/views.py:5326) : une note importee par cette porte reste
+        sans element, donc sans gouttiere et sans ancrage possible. C'est
+        un trou de l'application, releve le 11 aout 2026. La commande
+        appelle l'ingestion explicitement.
+        / The import view never triggers this ingestion; we do it here.
+        """
+        import json
+
+        if self._note_deja_presente(
+            carnet_des_etalons, FICHIER_DE_LA_TRANSCRIPTION,
+        ):
+            self.stdout.write("Transcription JSON  : déjà présente — sautée")
+            return None
+
+        if self.a_blanc:
+            self.stdout.write("Transcription JSON  : serait chargée")
+            return None
+
+        from front.services.transcription_audio import construire_html_diarise
+
+        chemin_du_json = REPERTOIRE_SAMPLE / FICHIER_DE_LA_TRANSCRIPTION
+        contenu_brut = chemin_du_json.read_text(encoding="utf-8")
+        donnees_de_la_transcription = json.loads(contenu_brut)
+
+        html_diarise, texte_brut = construire_html_diarise(
+            donnees_de_la_transcription,
+        )
+
+        page_du_json = Page.objects.create(
+            source_type="audio",
+            original_filename=FICHIER_DE_LA_TRANSCRIPTION,
+            url=None,
+            title="Débat IA — transcription",
+            html_original="",
+            html_readability=html_diarise,
+            text_readability=texte_brut,
+            content_hash=hashlib.sha256(
+                texte_brut.encode("utf-8"),
+            ).hexdigest(),
+            transcription_raw=donnees_de_la_transcription,
+            status="completed",
+            owner=proprietaire,
+            dossier=carnet_des_etalons,
+            source_file=ContentFile(
+                contenu_brut.encode("utf-8"),
+                name=FICHIER_DE_LA_TRANSCRIPTION,
+            ),
+        )
+        ranger_une_note_dans_un_carnet(
+            page_du_json, carnet_des_etalons, proprietaire,
+        )
+
+        from hypostasis_extractor.tasks_element import (
+            ingerer_une_transcription_diarisee_en_elements,
+        )
+
+        resultat = ingerer_une_transcription_diarisee_en_elements.apply(
+            args=[page_du_json.pk],
+        )
+        self.stdout.write(
+            f"Transcription JSON  : {self._elements_du_resultat(resultat)} "
+            f"tour(s) de parole",
+        )
+        return page_du_json
+
+    def _charger_le_mp3(self, proprietaire, carnet_des_etalons):
+        """
+        Cree la note audio et lance la vraie transcription Voxtral.
+        / Creates the audio note and runs the real Voxtral transcription.
+
+        LOCALISATION : front/management/commands/charger_fixtures_sample.py
+
+        C'est la seule fixture qui eprouve la chaine COMPLETE : mp3 ->
+        Voxtral -> tours de parole -> elements. Un appel reseau reel, donc
+        aussi un test de bout en bout a chaque chargement.
+        / The only fixture exercising the full chain, network call included.
+
+        La tache enchaine elle-meme l'ingestion en elements, mais par
+        `.delay()` : sans worker, elle partirait dans le broker et ne se
+        ferait jamais. On la rejoue donc ici, en synchrone, si la page
+        n'a pas d'element. / The task chains via .delay(); we redo it sync.
+        """
+        if self.sans_mp3:
+            self.stdout.write("Audio mp3           : sauté (--sans-mp3)")
+            return None
+
+        if not os.environ.get("MISTRAL_API_KEY"):
+            self.stdout.write(self.style.WARNING(
+                "Audio mp3           : sauté — pas de MISTRAL_API_KEY. "
+                "La transcription serait mockée, pas réelle.",
+            ))
+            return None
+
+        if self._note_deja_presente(carnet_des_etalons, FICHIER_DU_MP3):
+            self.stdout.write("Audio mp3           : déjà présent — sauté")
+            return None
+
+        if self.a_blanc:
+            self.stdout.write("Audio mp3           : serait transcrit (Voxtral)")
+            return None
+
+        from core.models import TranscriptionConfig, TranscriptionJob
+
+        chemin_du_mp3 = REPERTOIRE_SAMPLE / FICHIER_DU_MP3
+        octets_du_mp3 = chemin_du_mp3.read_bytes()
+
+        page_du_mp3 = Page.objects.create(
+            source_type="audio",
+            original_filename=FICHIER_DU_MP3,
+            url=None,
+            title="Palais César — deux locuteurs",
+            html_original="",
+            html_readability="",
+            text_readability="",
+            content_hash="",
+            status="processing",
+            owner=proprietaire,
+            dossier=carnet_des_etalons,
+            source_file=ContentFile(octets_du_mp3, name=FICHIER_DU_MP3),
+        )
+        ranger_une_note_dans_un_carnet(
+            page_du_mp3, carnet_des_etalons, proprietaire,
+        )
+
+        config_active = TranscriptionConfig.objects.filter(
+            is_active=True,
+        ).first()
+        job_de_transcription = TranscriptionJob.objects.create(
+            page=page_du_mp3,
+            transcription_config=config_active,
+            audio_filename=FICHIER_DU_MP3,
+            status="pending",
+        )
+
+        from front.tasks import transcrire_audio_task
+
+        transcrire_audio_task.apply(args=[
+            job_de_transcription.pk,
+            page_du_mp3.source_file.path,
+            config_active.max_speakers if config_active else 5,
+            config_active.language if config_active else "fr",
+        ])
+
+        page_du_mp3.refresh_from_db()
+
+        # La tache enchaine l'ingestion par `.delay()`. Sans worker, elle
+        # n'a pas eu lieu : on la rejoue ici, en synchrone.
+        # / The task chained via .delay(); without a worker, redo it here.
+        if not page_du_mp3.elements.exists() and page_du_mp3.transcription_raw:
+            from hypostasis_extractor.tasks_element import (
+                ingerer_une_transcription_diarisee_en_elements,
+            )
+
+            ingerer_une_transcription_diarisee_en_elements.apply(
+                args=[page_du_mp3.pk],
+            )
+
+        self.stdout.write(
+            f"Audio mp3 (Voxtral) : {page_du_mp3.elements.count()} "
+            f"tour(s) de parole",
+        )
+        return page_du_mp3

=== test_charger_fixtures_sample.py ===
--- .superpowers/sdd/2026-08-11-charger-fixtures-sample/snapshots/task2-tests.py	2026-08-11 15:38:22.341705506 +0200
+++ front/tests/test_charger_fixtures_sample.py	2026-08-11 15:45:04.519838007 +0200
@@ -189,11 +189,15 @@
             )
 
         carnet = Dossier.objects.get(name="Documents étalons")
+        # 3, pas 2 : --sans-mp3 ne saute que le mp3. La transcription JSON
+        # (tache 3) se charge toujours, meme ici ou son ingestion n'est
+        # pas mockee. / --sans-mp3 only skips the mp3; the JSON transcript
+        # (task 3) still loads, even with its ingestion unmocked here.
         self.assertEqual(
             Page.objects.filter(
                 appartenances_dossiers__dossier=carnet,
             ).distinct().count(),
-            2,
+            3,
         )
 
     def test_relancer_ne_double_rien_et_ne_reconvertit_pas(self):
@@ -221,7 +225,11 @@
             self.assertEqual(capture_mockee.call_count, 1)
             self.assertEqual(fichier_mocke.call_count, 1)
 
-        self.assertEqual(Page.objects.count(), 2)
+        # 3, pas 2 : la transcription JSON (tache 3) se charge aussi, et
+        # son idempotence propre (_note_deja_presente) evite qu'elle soit
+        # doublee au second appel. / The JSON transcript (task 3) also
+        # loads, and its own idempotency check prevents duplication.
+        self.assertEqual(Page.objects.count(), 3)
 
     def test_les_taches_sont_appelees_en_synchrone_avec_la_cle_primaire(self):
         cible_capture = (
@@ -240,3 +248,104 @@
         capture_mockee.assert_called_once_with(
             args=[page_de_la_capture.pk],
         )
+
+
+class EntreesAudioTest(TestCase):
+    """La transcription déjà faite, et la chaîne mp3 complète."""
+
+    def _mocks_docling(self):
+        """Les deux tâches Docling, neutralisées ensemble."""
+        return (
+            patch(
+                "hypostasis_extractor.tasks_element."
+                "ingerer_une_capture_web_avec_docling.apply",
+            ),
+            patch(
+                "hypostasis_extractor.tasks_element."
+                "ingerer_un_fichier_avec_docling.apply",
+            ),
+        )
+
+    def test_le_json_devient_une_page_audio_avec_ses_elements(self):
+        capture_mockee, fichier_mocke = self._mocks_docling()
+        cible_ingestion = (
+            "hypostasis_extractor.tasks_element."
+            "ingerer_une_transcription_diarisee_en_elements.apply"
+        )
+        with capture_mockee, fichier_mocke, patch(cible_ingestion) as ingestion:
+            call_command(
+                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
+            )
+
+        page_du_json = Page.objects.get(
+            original_filename="fake_debat_ia_transcription.json",
+        )
+        self.assertEqual(page_du_json.source_type, "audio")
+        # 12 segments, 3 locuteurs — mesure du fichier versionne.
+        # / 12 segments, 3 speakers, measured from the versioned file.
+        self.assertEqual(len(page_du_json.transcription_raw["segments"]), 12)
+        # LE POINT : la vue d'import, elle, N'appelle PAS cette ingestion
+        # (front/views.py:5326). Une note importee par cette porte reste
+        # sans element. La commande, elle, doit l'appeler.
+        # / The import view never calls this; the command must.
+        ingestion.assert_called_once_with(args=[page_du_json.pk])
+
+    def test_sans_mp3_la_transcription_voxtral_n_est_pas_lancee(self):
+        capture_mockee, fichier_mocke = self._mocks_docling()
+        cible_voxtral = "front.tasks.transcrire_audio_task.apply"
+        with capture_mockee, fichier_mocke, patch(
+            "hypostasis_extractor.tasks_element."
+            "ingerer_une_transcription_diarisee_en_elements.apply",
+        ), patch(cible_voxtral) as voxtral_mocke:
+            call_command(
+                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
+            )
+
+        voxtral_mocke.assert_not_called()
+        self.assertFalse(
+            Page.objects.filter(
+                original_filename="audio-FR-2locuteur-palaiscesar-14s.mp3",
+            ).exists(),
+        )
+
+    def test_sans_cle_mistral_le_mp3_est_saute_et_le_reste_charge(self):
+        import os
+
+        capture_mockee, fichier_mocke = self._mocks_docling()
+        sortie = StringIO()
+        cle_sauvegardee = os.environ.pop("MISTRAL_API_KEY", None)
+        try:
+            with capture_mockee, fichier_mocke, patch(
+                "hypostasis_extractor.tasks_element."
+                "ingerer_une_transcription_diarisee_en_elements.apply",
+            ), patch("front.tasks.transcrire_audio_task.apply") as voxtral:
+                call_command("charger_fixtures_sample", stdout=sortie)
+        finally:
+            if cle_sauvegardee is not None:
+                os.environ["MISTRAL_API_KEY"] = cle_sauvegardee
+
+        voxtral.assert_not_called()
+        self.assertIn("MISTRAL_API_KEY", sortie.getvalue())
+        # Les trois autres notes sont chargees malgre tout.
+        # / The other three notes are loaded regardless.
+        self.assertEqual(Page.objects.count(), 3)
+
+    def test_avec_la_cle_le_mp3_cree_une_page_et_un_job(self):
+        import os
+
+        capture_mockee, fichier_mocke = self._mocks_docling()
+        with patch.dict(os.environ, {"MISTRAL_API_KEY": "une-cle-de-test"}):
+            with capture_mockee, fichier_mocke, patch(
+                "hypostasis_extractor.tasks_element."
+                "ingerer_une_transcription_diarisee_en_elements.apply",
+            ), patch("front.tasks.transcrire_audio_task.apply") as voxtral:
+                call_command("charger_fixtures_sample", stdout=StringIO())
+
+        from core.models import TranscriptionJob
+
+        page_du_mp3 = Page.objects.get(
+            original_filename="audio-FR-2locuteur-palaiscesar-14s.mp3",
+        )
+        job = TranscriptionJob.objects.get(page=page_du_mp3)
+        self.assertEqual(job.transcription_config.provider, "voxtral")
+        voxtral.assert_called_once()
