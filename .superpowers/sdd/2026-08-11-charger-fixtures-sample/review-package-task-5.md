### DIFF DE LA TACHE 5

--- .superpowers/sdd/2026-08-11-charger-fixtures-sample/snapshots/task4fix-commande.py	2026-08-11 16:55:41.411808395 +0200
+++ front/management/commands/charger_fixtures_sample.py	2026-08-11 17:02:11.778819371 +0200
@@ -107,6 +107,13 @@
                 "Repetable."
             ),
         )
+        analyseur_d_arguments.add_argument(
+            "--reset", action="store_true",
+            help=(
+                "Supprime le carnet etalon et ses notes propres avant de "
+                "recharger. Refuse si une note porte des ancres."
+            ),
+        )
 
     def handle(self, *args, **options):
         self.a_blanc = options["a_blanc"]
@@ -124,6 +131,10 @@
             ))
 
         proprietaire = self._proprietaire()
+
+        if options["reset"]:
+            self._reinitialiser(proprietaire)
+
         carnet_des_etalons = self._creer_le_carnet(proprietaire)
         self._creer_la_config_de_transcription()
 
@@ -290,6 +301,91 @@
         )
         return config
 
+    def _reinitialiser(self, proprietaire):
+        """
+        Supprime le carnet etalon et les notes qui n'appartiennent qu'a lui.
+        / Deletes the reference notebook and the notes filed only in it.
+
+        LOCALISATION : front/management/commands/charger_fixtures_sample.py
+
+        POURQUOI CETTE OPTION EXISTE
+
+        L'idempotence saute ce qui est deja la — y compris l'appel Voxtral,
+        qu'on veut precisement pouvoir rejouer a chaque chargement. `--reset`
+        est la seule facon de tout refaire.
+        / Idempotency skips the Voxtral call we want to replay.
+
+        LE GARDE-FOU N'EST PAS FACULTATIF
+
+        `AncrageExtraction.element` est en PROTECT : supprimer une page qui
+        porte des ancres leve ProtectedError. On ne se contente pas de
+        laisser l'exception sortir — on VERIFIE D'ABORD, et on refuse tout
+        en bloc. Une suppression partielle laisserait le carnet a moitie
+        vide, dans un etat que personne n'a voulu.
+        / Check first and refuse wholesale: a partial delete is worse.
+        """
+        from django.core.management.base import CommandError
+
+        from hypostasis_extractor.models import AncrageExtraction
+
+        carnet_existant = Dossier.objects.filter(
+            name=NOM_DU_CARNET, owner=proprietaire,
+        ).first()
+        if carnet_existant is None:
+            self.stdout.write("Réinitialisation    : aucun carnet à supprimer")
+            return None
+
+        # Les notes rangees UNIQUEMENT dans ce carnet sont a nous. Une note
+        # rangee ailleurs aussi appartient a ce quelqu'un d'autre.
+        # / Only notes filed solely here are ours to remove.
+        notes_a_supprimer = []
+        for page in Page.objects.filter(
+            appartenances_dossiers__dossier=carnet_existant,
+        ).distinct():
+            rangee_ailleurs = page.appartenances_dossiers.exclude(
+                dossier=carnet_existant,
+            ).exists()
+            if not rangee_ailleurs:
+                notes_a_supprimer.append(page)
+
+        # VERIFIER AVANT DE SUPPRIMER.
+        notes_avec_ancres = []
+        for page in notes_a_supprimer:
+            nombre_d_ancres = AncrageExtraction.objects.filter(
+                element__page=page,
+            ).count()
+            if nombre_d_ancres:
+                notes_avec_ancres.append((page, nombre_d_ancres))
+
+        if notes_avec_ancres:
+            detail = " ; ".join(
+                f"« {page.title} » ({nombre} ancre(s))"
+                for page, nombre in notes_avec_ancres
+            )
+            raise CommandError(
+                f"--reset refusé : {detail}. Ces notes portent des "
+                f"extractions ancrées, et une ancre est une preuve. Rien "
+                f"n'a été supprimé. Retirer les portions d'abord, ou "
+                f"recharger dans une base neuve.",
+            )
+
+        if self.a_blanc:
+            self.stdout.write(
+                f"Réinitialisation    : {len(notes_a_supprimer)} note(s) "
+                f"seraient supprimées",
+            )
+            return None
+
+        for page in notes_a_supprimer:
+            page.delete()
+        carnet_existant.delete()
+
+        self.stdout.write(
+            f"Réinitialisation    : {len(notes_a_supprimer)} note(s) "
+            f"supprimée(s), carnet supprimé",
+        )
+        return None
+
     def _note_deja_presente(self, carnet_des_etalons, nom_du_fichier):
         """
         Dit si une note issue de ce fichier est deja dans le carnet.
@@ -347,6 +443,24 @@
             self.stdout.write("Capture web         : serait chargée")
             return None
 
+        # `url` est unique en base (contrainte unique_url_si_presente,
+        # non scopee par carnet). --reset peut avoir garde cette page
+        # ailleurs (rangee aussi dans un autre carnet, donc pas a nous
+        # de la supprimer) : on la range ici plutot que d'en tenter un
+        # doublon que la contrainte refuserait. / `url` is globally
+        # unique. --reset may have kept this page elsewhere (also filed
+        # in another notebook, so not ours to delete): file it here
+        # instead of attempting a duplicate the DB constraint rejects.
+        page_deja_ailleurs = Page.objects.filter(url=URL_DE_LA_CAPTURE).first()
+        if page_deja_ailleurs is not None:
+            ranger_une_note_dans_un_carnet(
+                page_deja_ailleurs, carnet_des_etalons, proprietaire,
+            )
+            self.stdout.write(
+                "Capture web         : déjà présente ailleurs — rangée ici",
+            )
+            return page_deja_ailleurs
+
         html_capture = (REPERTOIRE_SAMPLE / FICHIER_DE_LA_CAPTURE).read_text(
             encoding="utf-8",
         )

--- .superpowers/sdd/2026-08-11-charger-fixtures-sample/snapshots/task4fix-tests.py	2026-08-11 16:55:41.413697621 +0200
+++ front/tests/test_charger_fixtures_sample.py	2026-08-11 16:59:08.868306109 +0200
@@ -490,3 +490,129 @@
             },
         )
         self.assertEqual(Page.objects.count(), 2)
+
+
+class ReinitialisationTest(TestCase):
+    """--reset rejoue tout, sauf s'il y a des preuves à perdre."""
+
+    def _charger_une_fois(self):
+        cible_capture = (
+            "hypostasis_extractor.tasks_element."
+            "ingerer_une_capture_web_avec_docling.apply"
+        )
+        cible_fichier = (
+            "hypostasis_extractor.tasks_element."
+            "ingerer_un_fichier_avec_docling.apply"
+        )
+        cible_audio = (
+            "hypostasis_extractor.tasks_element."
+            "ingerer_une_transcription_diarisee_en_elements.apply"
+        )
+        with patch(cible_capture), patch(cible_fichier), patch(cible_audio):
+            call_command(
+                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
+            )
+
+    def test_reset_supprime_les_notes_et_les_recharge(self):
+        self._charger_une_fois()
+        pks_de_depart = set(Page.objects.values_list("pk", flat=True))
+        self.assertEqual(len(pks_de_depart), 3)
+
+        cible_capture = (
+            "hypostasis_extractor.tasks_element."
+            "ingerer_une_capture_web_avec_docling.apply"
+        )
+        with patch(cible_capture) as capture_mockee, patch(
+            "hypostasis_extractor.tasks_element."
+            "ingerer_un_fichier_avec_docling.apply",
+        ), patch(
+            "hypostasis_extractor.tasks_element."
+            "ingerer_une_transcription_diarisee_en_elements.apply",
+        ):
+            call_command(
+                "charger_fixtures_sample", "--reset", "--sans-mp3",
+                stdout=StringIO(),
+            )
+            # Le point du reset : on RECONVERTIT, la ou l'idempotence
+            # aurait saute. / The point of --reset: convert again.
+            self.assertEqual(capture_mockee.call_count, 1)
+
+        self.assertEqual(Page.objects.count(), 3)
+        self.assertFalse(
+            set(Page.objects.values_list("pk", flat=True)) & pks_de_depart,
+        )
+
+    def test_reset_refuse_si_une_note_porte_une_ancre(self):
+        from django.core.management.base import CommandError
+
+        # Ces trois modeles vivent dans hypostasis_extractor, PAS dans
+        # core.models. / These three live in hypostasis_extractor.
+        from hypostasis_extractor.models import (
+            AncrageExtraction, ExtractedEntity, ExtractionJob,
+        )
+
+        self._charger_une_fois()
+        page_avec_ancre = Page.objects.filter(source_type="web").first()
+        element = page_avec_ancre.elements.create(
+            ordre=0, label="text", texte="un passage", empreinte_contenu="x",
+        )
+        job = ExtractionJob.objects.create(
+            page=page_avec_ancre, name="job de test",
+            prompt_description="peu importe", status="completed",
+        )
+        entite = ExtractedEntity.objects.create(
+            job=job, extraction_class="PHENOMENE", extraction_text="une idée",
+            start_char=0, end_char=10,
+        )
+        # Les champs sont debut_dans_element / fin_dans_element — des
+        # positions DANS l'element, jamais dans le texte global de la
+        # page. / Positions within the element, never page-global.
+        AncrageExtraction.objects.create(
+            extraction=entite, element=element,
+            ordre_dans_extraction=0,
+            debut_dans_element=0, fin_dans_element=10,
+        )
+
+        nombre_de_pages_avant = Page.objects.count()
+        with self.assertRaises(CommandError) as contexte:
+            call_command(
+                "charger_fixtures_sample", "--reset", "--sans-mp3",
+                stdout=StringIO(),
+            )
+
+        # RIEN ne doit avoir ete supprime — pas de suppression partielle
+        # qui laisserait le carnet a moitie vide.
+        # / Nothing deleted: no half-emptied notebook.
+        self.assertEqual(Page.objects.count(), nombre_de_pages_avant)
+        self.assertIn(page_avec_ancre.title, str(contexte.exception))
+
+    def test_reset_ne_touche_pas_une_note_rangee_ailleurs(self):
+        from core.models import Dossier as CarnetModele
+        from core.services.corpus import ranger_une_note_dans_un_carnet
+
+        self._charger_une_fois()
+        page_partagee = Page.objects.filter(source_type="web").first()
+        proprietaire = page_partagee.owner
+        autre_carnet = CarnetModele.objects.create(
+            name="Un autre carnet", owner=proprietaire,
+        )
+        ranger_une_note_dans_un_carnet(page_partagee, autre_carnet, proprietaire)
+
+        with patch(
+            "hypostasis_extractor.tasks_element."
+            "ingerer_une_capture_web_avec_docling.apply",
+        ), patch(
+            "hypostasis_extractor.tasks_element."
+            "ingerer_un_fichier_avec_docling.apply",
+        ), patch(
+            "hypostasis_extractor.tasks_element."
+            "ingerer_une_transcription_diarisee_en_elements.apply",
+        ):
+            call_command(
+                "charger_fixtures_sample", "--reset", "--sans-mp3",
+                stdout=StringIO(),
+            )
+
+        # Elle vit ailleurs : on ne l'emporte pas.
+        # / It lives elsewhere: not ours to delete.
+        self.assertTrue(Page.objects.filter(pk=page_partagee.pk).exists())
