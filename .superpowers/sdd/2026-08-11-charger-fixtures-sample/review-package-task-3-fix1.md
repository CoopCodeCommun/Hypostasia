### DIFF DU FIX (round 1, tache 3)

=== charger_fixtures_sample.py ===
--- .superpowers/sdd/2026-08-11-charger-fixtures-sample/snapshots/task3-commande.py	2026-08-11 15:47:35.039455522 +0200
+++ front/management/commands/charger_fixtures_sample.py	2026-08-11 15:54:52.315599309 +0200
@@ -510,7 +510,12 @@
             self.stdout.write("Audio mp3           : serait transcrit (Voxtral)")
             return None
 
-        from core.models import TranscriptionConfig, TranscriptionJob
+        from core.models import (
+            PageStatus,
+            TranscriptionConfig,
+            TranscriptionJob,
+            TranscriptionJobStatus,
+        )
 
         chemin_du_mp3 = REPERTOIRE_SAMPLE / FICHIER_DU_MP3
         octets_du_mp3 = chemin_du_mp3.read_bytes()
@@ -553,6 +558,30 @@
         ])
 
         page_du_mp3.refresh_from_db()
+        job_de_transcription.refresh_from_db()
+
+        # `transcrire_audio_task` attrape ses propres exceptions et pose
+        # page.status/job.status = ERROR en silence (front/tasks.py
+        # ~711-726), sans jamais relever d'exception ici. Sans ce
+        # controle, le bilan afficherait "0 tour(s) de parole" —
+        # indiscernable d'une transcription reussie qui n'aurait rien
+        # trouve a dire. / The task silently marks page/job as ERROR on
+        # failure; without this check the report would lie by omission.
+        transcription_en_echec = (
+            page_du_mp3.status == PageStatus.ERROR
+            or job_de_transcription.status == TranscriptionJobStatus.ERROR
+        )
+        if transcription_en_echec:
+            message_d_erreur = (
+                job_de_transcription.error_message
+                or page_du_mp3.error_message
+                or "raison inconnue"
+            )
+            self.stdout.write(self.style.WARNING(
+                f"Audio mp3 (Voxtral) : ÉCHEC de la transcription — "
+                f"{message_d_erreur}",
+            ))
+            return page_du_mp3
 
         # La tache enchaine l'ingestion par `.delay()`. Sans worker, elle
         # n'a pas eu lieu : on la rejoue ici, en synchrone.

=== test_charger_fixtures_sample.py ===
--- .superpowers/sdd/2026-08-11-charger-fixtures-sample/snapshots/task3-tests.py	2026-08-11 15:47:35.041419843 +0200
+++ front/tests/test_charger_fixtures_sample.py	2026-08-11 15:54:25.514777367 +0200
@@ -349,3 +349,43 @@
         job = TranscriptionJob.objects.get(page=page_du_mp3)
         self.assertEqual(job.transcription_config.provider, "voxtral")
         voxtral.assert_called_once()
+
+    def test_echec_voxtral_est_signale_dans_le_bilan(self):
+        # LE POINT : `transcrire_audio_task` attrape ses propres
+        # exceptions et pose page.status/job.status = ERROR en silence
+        # (front/tasks.py ~711-726). Sans controle explicite, le bilan
+        # affiche "0 tour(s) de parole" — indiscernable d'un succes sans
+        # contenu. On simule cet echec en posant les statuts d'erreur
+        # nous-memes, comme le ferait la tache reelle en cas de panne
+        # reseau. / The task swallows its own exceptions and silently
+        # marks page/job as ERROR; the report must say so explicitly.
+        import os
+
+        from core.models import PageStatus, TranscriptionJob, TranscriptionJobStatus
+
+        capture_mockee, fichier_mocke = self._mocks_docling()
+
+        def simuler_echec_reseau_voxtral(args=None, **kwargs):
+            job_de_test = TranscriptionJob.objects.get(pk=args[0])
+            job_de_test.status = TranscriptionJobStatus.ERROR
+            job_de_test.error_message = "Erreur réseau Voxtral (simulée)"
+            job_de_test.save(update_fields=["status", "error_message"])
+
+            page_de_test = job_de_test.page
+            page_de_test.status = PageStatus.ERROR
+            page_de_test.error_message = "Erreur réseau Voxtral (simulée)"
+            page_de_test.save(update_fields=["status", "error_message"])
+
+        sortie = StringIO()
+        with patch.dict(os.environ, {"MISTRAL_API_KEY": "une-cle-de-test"}):
+            with capture_mockee, fichier_mocke, patch(
+                "hypostasis_extractor.tasks_element."
+                "ingerer_une_transcription_diarisee_en_elements.apply",
+            ), patch(
+                "front.tasks.transcrire_audio_task.apply",
+                side_effect=simuler_echec_reseau_voxtral,
+            ):
+                call_command("charger_fixtures_sample", stdout=sortie)
+
+        self.assertIn("ÉCHEC", sortie.getvalue())
+        self.assertIn("Erreur réseau Voxtral (simulée)", sortie.getvalue())
