### DIFF DU FIX (round 1, tache 4)

--- .superpowers/sdd/2026-08-11-charger-fixtures-sample/snapshots/task4-commande.py	2026-08-11 16:00:47.916863067 +0200
+++ front/management/commands/charger_fixtures_sample.py	2026-08-11 16:05:17.002403604 +0200
@@ -52,10 +52,11 @@
 FICHIER_DU_MP3 = "audio-FR-2locuteur-palaiscesar-14s.mp3"
 
 # Les formats que cette commande ne convertit jamais elle-meme : Docling
-# les mesure a 2 a 3,4 Gio et 80 a 164 s selon la taille. Ils ont leur
+# les mesure a 2 a 3,4 Gio et 80 a 164 s selon la taille (mesure du
+# 11 aout 2026, voir tmp/benchmark-docling-2026-08-11.md). Ils ont leur
 # propre chemin, une conversion a la fois. / Formats this command never
-# converts itself: measured at 2-3.4 GiB and 80-164s. They have their own
-# path, one conversion at a time.
+# converts itself: measured at 2-3.4 GiB and 80-164s, see the benchmark
+# file above. They have their own path, one conversion at a time.
 EXTENSIONS_REFUSEES = {".pdf", ".docx"}
 
 # Les quatre documents etalons, par nom de fichier, dans l'ordre de
@@ -164,11 +165,15 @@
                 raise CommandError(
                     f"« {nom_du_fichier} » est un {extension} : cette "
                     f"commande ne lance jamais Docling sur ce format. Une "
-                    f"conversion de PDF coûte 2 031 Mio et 98 s (mesure du "
-                    f"11 août 2026) ; une commande de fixtures qui en "
-                    f"enchaîne a fait tomber le serveur le 10 août. Passer "
-                    f"par `charger_fixtures_pdf`, qui rejoue des fixtures "
-                    f"déjà converties, sans Docling.",
+                    f"conversion de PDF coûte de 2 à 3,4 Gio et de 80 à "
+                    f"164 s selon la taille (mesure du 11 août 2026, voir "
+                    f"tmp/benchmark-docling-2026-08-11.md) ; une commande "
+                    f"de fixtures qui en enchaîne a fait tomber le serveur "
+                    f"le 10 août. Le PDF et le docx ont un chemin "
+                    f"d'ingestion dédié, mesuré, une conversion à la "
+                    f"fois — la commande qui rejouera ces fixtures déjà "
+                    f"converties sans Docling est prévue mais n'existe "
+                    f"pas encore dans ce dépôt.",
                 )
 
             if nom_du_fichier not in DOCUMENTS_ETALONS:

--- .superpowers/sdd/2026-08-11-charger-fixtures-sample/snapshots/task4-tests.py	2026-08-11 16:00:47.918725869 +0200
+++ front/tests/test_charger_fixtures_sample.py	2026-08-11 16:05:32.963268119 +0200
@@ -457,3 +457,36 @@
             )
 
         self.assertIn("n-existe-pas.md", str(contexte.exception))
+
+    def test_fichier_est_repetable_et_charge_les_deux(self):
+        # LE POINT : `--fichier` repete deux fois doit charger les DEUX
+        # documents demandes, et rien d'autre — pas seulement le dernier
+        # de la liste. / --fichier repeated twice must load BOTH requested
+        # documents, and nothing else — not just the last one.
+        cible_capture = (
+            "hypostasis_extractor.tasks_element."
+            "ingerer_une_capture_web_avec_docling.apply"
+        )
+        cible_fichier = (
+            "hypostasis_extractor.tasks_element."
+            "ingerer_un_fichier_avec_docling.apply"
+        )
+        with patch(cible_capture), patch(cible_fichier):
+            call_command(
+                "charger_fixtures_sample",
+                "--fichier", "capture-web-badgeons-la-normandie.html",
+                "--fichier", "PRESENTATION-V3.md",
+                stdout=StringIO(),
+            )
+
+        noms_de_fichiers_charges = set(
+            Page.objects.values_list("original_filename", flat=True),
+        )
+        self.assertEqual(
+            noms_de_fichiers_charges,
+            {
+                "capture-web-badgeons-la-normandie.html",
+                "PRESENTATION-V3.md",
+            },
+        )
+        self.assertEqual(Page.objects.count(), 2)
