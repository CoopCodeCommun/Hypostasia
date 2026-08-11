### DIFF DE LA TACHE 9 (PDF + base de demonstration)

diff --git a/hypostasis_extractor/tests/test_fixtures_representatives.py b/hypostasis_extractor/tests/test_fixtures_representatives.py
index 6b09984..f3b3ed8 100644
--- a/hypostasis_extractor/tests/test_fixtures_representatives.py
+++ b/hypostasis_extractor/tests/test_fixtures_representatives.py
@@ -191,12 +191,169 @@ class ConversionReelleDUnDocxAvecTableauTest(BaseFixturesTestCase):
         self.assertIn("table", labels,
 
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
+
+
+@tag("docling")
+@unittest.skipUnless(DOCLING_DEMANDE, RAISON_DU_SKIP)
+class PdfEtalonTest(TestCase):
+    """
+    Le premier test qui prouve l'ancrage par coordonnées de bout en bout.
+    / The first test proving coordinate-based anchoring end to end.
+
+    LOCALISATION : hypostasis_extractor/tests/test_fixtures_representatives.py
+
+    Avant ce test, AUCUN PDF n'avait jamais été ingéré par le moteur
+    ELEMENT : la base ne portait pas une seule boîte de coordonnées, et
+    le visualiseur PDF ne pouvait pas être développé faute du moindre
+    `page_no`. Ce compte VERROUILLE ce que la conversion réelle du
+    11 août 2026 a mesuré (98 s, 2 031 Mio, voir
+    tmp/benchmark-docling-2026-08-11.md) : 11 éléments, dont 2 tableaux,
+    et 11 boîtes sur 11 éléments.
+    / Before this test, no PDF had ever been ingested by the ELEMENT
+    engine: the database carried no coordinate box at all. This count
+    locks in what the real 11 August conversion measured.
+    """
+
+    def test_le_pdf_rend_onze_elements_avec_leurs_boites(self):
+        from io import StringIO
+
+        from django.core.management import call_command
+
+        from core.models import ElementDocument, Page
+
+        # Ne charge QUE le PDF : les autres documents etalons ne nous
+        # concernent pas ici et gonfleraient le temps du test.
+        # / Only the PDF: the other reference documents are irrelevant.
+        call_command(
+            "charger_fixtures_sample",
+            "--fichier", "Etude_Epistemologique_IA.pdf",
+            stdout=StringIO(),
+        )
+
+        page_du_pdf = Page.objects.get(
+            original_filename="Etude_Epistemologique_IA.pdf",
+        )
+        elements = ElementDocument.objects.filter(page=page_du_pdf)
+
+        self.assertEqual(elements.count(), 11)
+
+        # Ventilation par label : le compte total seul ne dirait pas si
+        # les 2 tableaux ont bien ete reconnus comme tels.
+        # / Per-label breakdown: the total alone wouldn't show whether
+        # the 2 tables were recognised as such.
+        comptes_par_label = {}
+        for element in elements:
+            comptes_par_label[element.label] = (
+                comptes_par_label.get(element.label, 0) + 1
+            )
+        self.assertEqual(comptes_par_label.get("table"), 2)
+
+        # LE POINT DE CE TEST : chaque element porte sa provenance
+        # physique — page_no ET au moins une boite. Sans elle, le
+        # visualiseur PDF n'a rien a afficher. / The point of this test:
+        # every element carries page_no AND at least one box.
+        numeros_de_page_rencontres = set()
+        for element in elements:
+            self.assertIn("page_no", element.provenance)
+            self.assertTrue(element.provenance.get("boites"))
+            numeros_de_page_rencontres.add(element.provenance["page_no"])
+
+        self.assertEqual(numeros_de_page_rencontres, {1, 2, 3})
