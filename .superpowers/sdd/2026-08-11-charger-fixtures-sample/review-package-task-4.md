### DIFF DE LA TACHE 4 (par rapport a l'etat apres le fix de la tache 3)

=== charger_fixtures_sample.py ===
--- .superpowers/sdd/2026-08-11-charger-fixtures-sample/snapshots/task3fix-commande.py	2026-08-11 15:55:58.067902920 +0200
+++ front/management/commands/charger_fixtures_sample.py	2026-08-11 15:59:35.012306590 +0200
@@ -51,6 +51,23 @@
 FICHIER_DE_LA_TRANSCRIPTION = "fake_debat_ia_transcription.json"
 FICHIER_DU_MP3 = "audio-FR-2locuteur-palaiscesar-14s.mp3"
 
+# Les formats que cette commande ne convertit jamais elle-meme : Docling
+# les mesure a 2 a 3,4 Gio et 80 a 164 s selon la taille. Ils ont leur
+# propre chemin, une conversion a la fois. / Formats this command never
+# converts itself: measured at 2-3.4 GiB and 80-164s. They have their own
+# path, one conversion at a time.
+EXTENSIONS_REFUSEES = {".pdf", ".docx"}
+
+# Les quatre documents etalons, par nom de fichier, dans l'ordre de
+# chargement. `--fichier` restreint a un sous-ensemble de cette table.
+# / The four reference documents, in loading order.
+DOCUMENTS_ETALONS = [
+    FICHIER_DE_LA_CAPTURE,
+    FICHIER_DU_MARKDOWN,
+    FICHIER_DE_LA_TRANSCRIPTION,
+    FICHIER_DU_MP3,
+]
+
 # L'article d'origine. Sans url, l'idempotence de la capture porterait
 # sur un champ vide et deux captures se confondraient.
 # / Without a url, the capture's idempotency key would be empty.
@@ -82,10 +99,23 @@
             "--sans-mp3", action="store_true",
             help="Saute la transcription Voxtral du fichier audio.",
         )
+        analyseur_d_arguments.add_argument(
+            "--fichier", action="append", default=None, dest="fichiers",
+            help=(
+                "Ne charger que ce fichier de sample/, au lieu des quatre. "
+                "Repetable."
+            ),
+        )
 
     def handle(self, *args, **options):
         self.a_blanc = options["a_blanc"]
         self.sans_mp3 = options["sans_mp3"]
+        # Resolu AVANT toute ecriture et toute conversion : un --fichier
+        # pointant un PDF doit rendre la main immediatement, pas apres
+        # avoir lance Docling. / Resolved before any write or conversion.
+        self.fichiers_demandes = self._resoudre_les_fichiers_demandes(
+            options["fichiers"],
+        )
 
         if self.a_blanc:
             self.stdout.write(self.style.WARNING(
@@ -103,6 +133,54 @@
                 "\nRien n'a ete ecrit : relancer sans --a-blanc pour agir.",
             ))
 
+    def _resoudre_les_fichiers_demandes(self, fichiers_de_l_option):
+        """
+        Rend la liste des fichiers a charger, en refusant les formats lourds.
+        / Returns the files to load, refusing the heavy formats.
+
+        LOCALISATION : front/management/commands/charger_fixtures_sample.py
+
+        POURQUOI REFUSER PLUTOT QU'IGNORER
+
+        Le PDF et le docx n'ont pas ete eprouves par Docling sur cette
+        machine. Une commande de fixtures qui convertit des PDF en masse a
+        fait tomber le serveur le 10 aout 2026 : 2 031 Mio et 98 s pour
+        trois pages. Les laisser passer en silence rejouerait l'incident ;
+        les refuser en le disant oriente vers le chemin prevu pour eux.
+        / Refusing loudly beats ignoring silently: mass PDF conversion
+        took the server down.
+        """
+        from django.core.management.base import CommandError
+
+        if not fichiers_de_l_option:
+            return list(DOCUMENTS_ETALONS)
+
+        fichiers_retenus = []
+        for chemin_demande in fichiers_de_l_option:
+            nom_du_fichier = os.path.basename(chemin_demande)
+            extension = os.path.splitext(nom_du_fichier)[1].lower()
+
+            if extension in EXTENSIONS_REFUSEES:
+                raise CommandError(
+                    f"« {nom_du_fichier} » est un {extension} : cette "
+                    f"commande ne lance jamais Docling sur ce format. Une "
+                    f"conversion de PDF coûte 2 031 Mio et 98 s (mesure du "
+                    f"11 août 2026) ; une commande de fixtures qui en "
+                    f"enchaîne a fait tomber le serveur le 10 août. Passer "
+                    f"par `charger_fixtures_pdf`, qui rejoue des fixtures "
+                    f"déjà converties, sans Docling.",
+                )
+
+            if nom_du_fichier not in DOCUMENTS_ETALONS:
+                raise CommandError(
+                    f"« {nom_du_fichier} » n'est pas un document étalon. "
+                    f"Attendus : {', '.join(DOCUMENTS_ETALONS)}.",
+                )
+
+            fichiers_retenus.append(nom_du_fichier)
+
+        return fichiers_retenus
+
     def _proprietaire(self):
         """
         Rend le proprietaire des notes etalons, en le creant s'il le faut.
@@ -251,6 +329,11 @@
         de charger_fixtures_demo n'ont que des <p> et sortent toutes en
         `text`. / The only fixture exercising real HTML structure labels.
         """
+        # Garde : --fichier peut avoir exclu ce document.
+        # / Guard: --fichier may have excluded this document.
+        if FICHIER_DE_LA_CAPTURE not in self.fichiers_demandes:
+            return None
+
         if self._note_deja_presente(carnet_des_etalons, FICHIER_DE_LA_CAPTURE):
             self.stdout.write("Capture web         : déjà présente — sautée")
             return None
@@ -347,6 +430,11 @@
         C'est pourquoi cette fixture-ci est sure, la ou le PDF ne l'est pas.
         / Markdown goes through Docling without OCR or layout models.
         """
+        # Garde : --fichier peut avoir exclu ce document.
+        # / Guard: --fichier may have excluded this document.
+        if FICHIER_DU_MARKDOWN not in self.fichiers_demandes:
+            return None
+
         if self._note_deja_presente(carnet_des_etalons, FICHIER_DU_MARKDOWN):
             self.stdout.write("Markdown            : déjà présent — sauté")
             return None
@@ -417,6 +505,11 @@
         """
         import json
 
+        # Garde : --fichier peut avoir exclu ce document.
+        # / Guard: --fichier may have excluded this document.
+        if FICHIER_DE_LA_TRANSCRIPTION not in self.fichiers_demandes:
+            return None
+
         if self._note_deja_presente(
             carnet_des_etalons, FICHIER_DE_LA_TRANSCRIPTION,
         ):
@@ -491,6 +584,11 @@
         ferait jamais. On la rejoue donc ici, en synchrone, si la page
         n'a pas d'element. / The task chains via .delay(); we redo it sync.
         """
+        # Garde : --fichier peut avoir exclu ce document.
+        # / Guard: --fichier may have excluded this document.
+        if FICHIER_DU_MP3 not in self.fichiers_demandes:
+            return None
+
         if self.sans_mp3:
             self.stdout.write("Audio mp3           : sauté (--sans-mp3)")
             return None

=== test_charger_fixtures_sample.py ===
--- .superpowers/sdd/2026-08-11-charger-fixtures-sample/snapshots/task3fix-tests.py	2026-08-11 15:55:58.070288281 +0200
+++ front/tests/test_charger_fixtures_sample.py	2026-08-11 15:58:27.141882713 +0200
@@ -389,3 +389,71 @@
 
         self.assertIn("ÉCHEC", sortie.getvalue())
         self.assertIn("Erreur réseau Voxtral (simulée)", sortie.getvalue())
+
+
+class RefusDesFormatsLourdsTest(TestCase):
+    """Le PDF et le docx ne passent pas par cette porte."""
+
+    def test_un_pdf_est_refuse_sans_conversion(self):
+        from django.core.management.base import CommandError
+
+        cible_fichier = (
+            "hypostasis_extractor.tasks_element."
+            "ingerer_un_fichier_avec_docling.apply"
+        )
+        with patch(cible_fichier) as fichier_mocke:
+            with self.assertRaises(CommandError) as contexte:
+                call_command(
+                    "charger_fixtures_sample",
+                    "--fichier", "sample/Etude_Epistemologique_IA.pdf",
+                    stdout=StringIO(),
+                )
+
+        # Le message doit ORIENTER, pas seulement refuser.
+        # / The message must point somewhere, not merely refuse.
+        self.assertIn(".pdf", str(contexte.exception))
+        fichier_mocke.assert_not_called()
+
+    def test_un_docx_est_refuse_aussi(self):
+        from django.core.management.base import CommandError
+
+        with self.assertRaises(CommandError):
+            call_command(
+                "charger_fixtures_sample",
+                "--fichier", "sample/quelque-chose.docx",
+                stdout=StringIO(),
+            )
+
+    def test_fichier_restreint_le_chargement_a_ce_seul_document(self):
+        cible_capture = (
+            "hypostasis_extractor.tasks_element."
+            "ingerer_une_capture_web_avec_docling.apply"
+        )
+        cible_fichier = (
+            "hypostasis_extractor.tasks_element."
+            "ingerer_un_fichier_avec_docling.apply"
+        )
+        with patch(cible_capture) as capture_mockee, patch(cible_fichier):
+            call_command(
+                "charger_fixtures_sample",
+                "--fichier", "PRESENTATION-V3.md",
+                stdout=StringIO(),
+            )
+
+        self.assertEqual(Page.objects.count(), 1)
+        self.assertEqual(
+            Page.objects.first().original_filename, "PRESENTATION-V3.md",
+        )
+        capture_mockee.assert_not_called()
+
+    def test_un_fichier_inconnu_est_refuse_clairement(self):
+        from django.core.management.base import CommandError
+
+        with self.assertRaises(CommandError) as contexte:
+            call_command(
+                "charger_fixtures_sample",
+                "--fichier", "n-existe-pas.md",
+                stdout=StringIO(),
+            )
+
+        self.assertIn("n-existe-pas.md", str(contexte.exception))
