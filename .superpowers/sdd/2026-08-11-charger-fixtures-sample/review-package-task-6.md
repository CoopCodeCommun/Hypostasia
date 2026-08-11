### DIFF DE LA TACHE 6 (lecture seule, git diff sans modification)

diff --git a/hypostasis_extractor/tests/test_fixtures_representatives.py b/hypostasis_extractor/tests/test_fixtures_representatives.py
index 6b09984..1c97b93 100644
--- a/hypostasis_extractor/tests/test_fixtures_representatives.py
+++ b/hypostasis_extractor/tests/test_fixtures_representatives.py
@@ -193,10 +193,99 @@ class ConversionReelleDUnDocxAvecTableauTest(BaseFixturesTestCase):
         )
 
         element_tableau = next(
             e for e in elements if e.label == "table"
         )
         # Le contenu des cellules est dans le texte de l'element : les
         # extractions pourront s'y ancrer. / Cell content is anchorable.
         self.assertIn("6 500 euros", element_tableau.texte,
         )
         self.assertIn("Formations", element_tableau.texte)
+
+
+@tag("docling")
+@unittest.skipUnless(DOCLING_DEMANDE, RAISON_DU_SKIP)
+class CaptureWebEtalonTest(TestCase):
+    """
+    Le contrôle de non-régression de l'extraction HTML.
+    / The HTML extraction's non-regression control.
+
+    LOCALISATION : hypostasis_extractor/tests/test_fixtures_representatives.py
+
+    Ce compte VERROUILLE les deux correctifs du 11 août 2026 :
+
+    - une image n'est pas un tableau : sans légende elle ne produit
+      aucun bloc, au lieu du message « Image not available… » destiné au
+      développeur ;
+    - un gras ne coupe pas une phrase : les fragments d'un même groupe
+      inline se recollent, au lieu de produire deux blocs là où l'auteur
+      a écrit une phrase.
+
+    54 éléments dont un `picture` = retour à la version d'avant les
+    correctifs. Une cinquantaine de blocs tous en `text` = retour du
+    découpage maison par paragraphes.
+    / This count locks in the two 11 August fixes.
+    """
+
+    def test_la_capture_web_rend_vingt_huit_elements(self):
+        from io import StringIO
+
+        from django.core.management import call_command
+
+        from core.models import ElementDocument, Page
+
+        # Ne charge QUE la capture web : les trois autres documents
+        # etalons (markdown, transcription, mp3) ne nous concernent pas
+        # ici et gonfleraient le temps du test. / Only the web capture.
+        call_command(
+            "charger_fixtures_sample",
+            "--fichier", "capture-web-badgeons-la-normandie.html",
+            stdout=StringIO(),
+        )
+
+        page_de_la_capture = Page.objects.get(source_type="web")
+        elements = ElementDocument.objects.filter(page=page_de_la_capture)
+
+        self.assertEqual(elements.count(), 28)
+
+        # Ventilation par label : le compte total seul ne suffirait pas
+        # a distinguer un retour du bug d'une coincidence numerique.
+        # / Per-label breakdown: the total alone could hide a regression.
+        comptes_par_label = {}
+        for element in elements:
+            comptes_par_label[element.label] = (
+                comptes_par_label.get(element.label, 0) + 1
+            )
+
+        self.assertEqual(
+            comptes_par_label,
+            {"section_header": 4, "list_item": 5, "text": 19},
+        )
+
+    def test_la_page_ingeree_porte_l_etat_reussie(self):
+        """
+        L'état d'ingestion ne peut se tester qu'ici.
+        / The ingestion state can only be tested here.
+
+        Avec Docling mocké, la tâche ne tourne pas, donc n'écrit pas
+        `ingestion_etat` : un test rapide qui l'affirmerait ne
+        vérifierait que son propre mock. C'est justement l'écart que
+        `charger_fixtures_llm_reel` a laissé passer — ses pages
+        gardent un état vide alors que l'écran de lecture l'affiche.
+        / A mocked task writes no state; asserting it would test the mock.
+        """
+        from io import StringIO
+
+        from django.core.management import call_command
+
+        from core.models import EtatIngestion, Page
+
+        call_command(
+            "charger_fixtures_sample",
+            "--fichier", "capture-web-badgeons-la-normandie.html",
+            stdout=StringIO(),
+        )
+
+        page_de_la_capture = Page.objects.get(source_type="web")
+        self.assertEqual(
+            page_de_la_capture.ingestion_etat, EtatIngestion.REUSSIE,
+        )
