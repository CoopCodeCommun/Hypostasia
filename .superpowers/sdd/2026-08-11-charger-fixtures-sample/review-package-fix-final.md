### DIFF DE LA VAGUE DE CORRECTION FINALE

--- .superpowers/sdd/2026-08-11-charger-fixtures-sample/snapshots/task5fix-commande.py	2026-08-11 17:09:47.798724564 +0200
+++ front/management/commands/charger_fixtures_sample.py	2026-08-11 17:28:54.386266707 +0200
@@ -30,6 +30,7 @@
 
 import hashlib
 import os
+import uuid
 from pathlib import Path
 
 from django.conf import settings
@@ -37,7 +38,13 @@
 from django.core.files.base import ContentFile
 from django.core.management.base import BaseCommand
 
-from core.models import Dossier, Page, TranscriptionConfig, VisibiliteDossier
+from core.models import (
+    Dossier,
+    Page,
+    TranscriptionConfig,
+    TranscriptionProvider,
+    VisibiliteDossier,
+)
 from core.services.corpus import ranger_une_note_dans_un_carnet
 
 User = get_user_model()
@@ -130,13 +137,23 @@
                 "MODE A BLANC — rien ne sera ecrit.",
             ))
 
+        # Le compteur du bilan final (§ 4 de la spec). Il ne compte que
+        # les notes sautees PARCE QU'ELLES SONT DEJA LA — pas celles que
+        # --sans-mp3 ou --fichier ont exclues, qui n'ont jamais ete
+        # candidates. / Counts only notes skipped as already present.
+        self.nombre_de_notes_sautees = 0
+
         proprietaire = self._proprietaire()
 
         if options["reset"]:
             self._reinitialiser(proprietaire)
 
         carnet_des_etalons = self._creer_le_carnet(proprietaire)
-        self._creer_la_config_de_transcription()
+        # La valeur de retour n'est PAS jetable : c'est la seule config
+        # dont on sait qu'elle est bien Voxtral. Voir
+        # `_config_voxtral_utilisable`. / Not throwaway: it is the only
+        # config known to be Voxtral.
+        self.config_de_transcription = self._creer_la_config_de_transcription()
 
         self._charger_les_documents(proprietaire, carnet_des_etalons)
 
@@ -242,10 +259,34 @@
         / Returns the reference notebook, creating it if needed.
 
         LOCALISATION : front/management/commands/charger_fixtures_sample.py
+
+        LE MODE A BLANC CHERCHE, MAIS NE CREE PAS.
+
+        Rendre `None` sans chercher ferait mentir tout le reste du bilan :
+        `_note_deja_presente` rendrait toujours False faute de carnet ou
+        regarder, et --a-blanc annoncerait « serait chargee » pour les
+        quatre notes alors qu'une vraie execution les sauterait toutes.
+        L'option existe pour montrer ce qui se passerait — elle doit dire
+        vrai. / A dry run looks the notebook up but never creates it:
+        returning None blindly made every downstream line lie.
         """
         if self.a_blanc:
-            self.stdout.write(f"Carnet              : {NOM_DU_CARNET} (serait créé)")
-            return None
+            carnet_existant = None
+            if proprietaire is not None:
+                carnet_existant = Dossier.objects.filter(
+                    name=NOM_DU_CARNET, owner=proprietaire,
+                ).first()
+
+            if carnet_existant is not None:
+                self.stdout.write(
+                    f"Carnet              : {NOM_DU_CARNET} — "
+                    f"pk={carnet_existant.pk} (réutilisé)",
+                )
+            else:
+                self.stdout.write(
+                    f"Carnet              : {NOM_DU_CARNET} (serait créé)",
+                )
+            return carnet_existant
 
         carnet, a_ete_cree = Dossier.objects.get_or_create(
             name=NOM_DU_CARNET, owner=proprietaire,
@@ -398,13 +439,74 @@
         elements — mais il arrive APRES la conversion Docling. S'y fier
         ferait payer 98 s pour un PDF de 3 pages, et rien produire.
         / The service's guard comes after conversion; this one comes before.
+
+        UNE NOTE SANS ELEMENT N'EST PAS UNE NOTE PRESENTE.
+
+        Si l'ingestion echoue, la Page reste en base sans le moindre
+        element : elle n'a ni gouttiere, ni ancrage possible, elle ne sert
+        a rien. Tester la seule existence de la Page faisait sauter cette
+        coquille a chaque relance, et l'etat a moitie ingere ne se reparait
+        jamais sans --reset. On la supprime donc pour la recharger — la
+        supprimer est obligatoire, sinon la contrainte globale
+        `unique_url_si_presente` refuse la capture web, et les trois
+        autres notes se dedoublent.
+        / A note with no element is a shell: delete it so it can reload.
+        Deleting first is mandatory — the global url constraint would
+        otherwise reject the web capture, and the others would duplicate.
         """
+        from hypostasis_extractor.models import AncrageExtraction
+
         if carnet_des_etalons is None:
             return False
-        return Page.objects.filter(
+
+        note_existante = Page.objects.filter(
             appartenances_dossiers__dossier=carnet_des_etalons,
             original_filename=nom_du_fichier,
+        ).first()
+        if note_existante is None:
+            return False
+
+        if note_existante.elements.exists():
+            return True
+
+        # A blanc, on constate sans supprimer : la note EST rechargeable,
+        # c'est ce que le bilan doit annoncer.
+        # / Dry run states the fact without deleting anything.
+        if self.a_blanc:
+            return False
+
+        # Une ancre est une preuve. Elle est censee etre impossible sans
+        # element (AncrageExtraction.element pointe un ElementDocument),
+        # mais on verifie plutot que de supposer : une suppression qui
+        # emporte une preuve ne se rattrape pas.
+        # / An anchor is evidence: verify rather than assume.
+        nombre_d_ancres = AncrageExtraction.objects.filter(
+            element__page=note_existante,
+        ).count()
+        if nombre_d_ancres:
+            self.stdout.write(self.style.WARNING(
+                f"    « {note_existante.title} » est sans élément mais "
+                f"porte {nombre_d_ancres} ancre(s) — non supprimée, non "
+                f"rechargée.",
+            ))
+            return True
+
+        # Rangee AUSSI ailleurs, elle appartient a ce quelqu'un d'autre.
+        # Meme regle que --reset : on ne l'emporte pas.
+        # / Also filed elsewhere: not ours to delete, same rule as --reset.
+        rangee_ailleurs = note_existante.appartenances_dossiers.exclude(
+            dossier=carnet_des_etalons,
         ).exists()
+        if rangee_ailleurs:
+            self.stdout.write(self.style.WARNING(
+                f"    « {note_existante.title} » est sans élément mais "
+                f"rangée aussi dans un autre carnet — non supprimée, non "
+                f"rechargée.",
+            ))
+            return True
+
+        note_existante.delete()
+        return False
 
     def _charger_les_documents(self, proprietaire, carnet_des_etalons):
         """
@@ -418,6 +520,48 @@
         self._charger_la_transcription_json(proprietaire, carnet_des_etalons)
         self._charger_le_mp3(proprietaire, carnet_des_etalons)
 
+        self.stdout.write(
+            f"Notes sautées       : {self.nombre_de_notes_sautees} "
+            f"(déjà présentes)",
+        )
+
+    def _detail_par_label(self, page_ingeree):
+        """
+        Rend le decompte par label des elements d'une page, en une ligne.
+        / Returns the per-label element breakdown of a page, on one line.
+
+        LOCALISATION : front/management/commands/charger_fixtures_sample.py
+
+        CE DETAIL EST LE TEMOIN DE NON-REGRESSION (§ 5 de la spec).
+
+        La capture web doit rendre `section_header 4 · list_item 5 ·
+        text 19`. Un total seul ne dirait rien : 54 elements dont un
+        `picture` signalerait un retour d'avant les correctifs du 11 aout
+        (legende d'image, recollage des groupes `inline`), et une
+        cinquantaine de blocs TOUS en `text` signalerait le retour du
+        decoupage maison par paragraphes. Les deux passeraient inapercus
+        derriere un simple compte.
+        / A bare total would hide both known regressions; the per-label
+        breakdown is what catches them.
+
+        Le detail n'est imprime QUE pour la capture web : les autres
+        fixtures ne portent pas ce controle.
+        / Printed for the web capture only.
+        """
+        nombre_par_label = {}
+        for element in page_ingeree.elements.order_by("ordre"):
+            nombre_par_label[element.label] = (
+                nombre_par_label.get(element.label, 0) + 1
+            )
+
+        if not nombre_par_label:
+            return ""
+
+        morceaux_du_detail = []
+        for label, nombre in nombre_par_label.items():
+            morceaux_du_detail.append(f"{label} {nombre}")
+        return " — " + " · ".join(morceaux_du_detail)
+
     def _charger_la_capture_web(self, proprietaire, carnet_des_etalons):
         """
         Cree la note issue de la capture web, et l'ingere.
@@ -461,6 +605,7 @@
 
         if self._note_deja_presente(carnet_des_etalons, FICHIER_DE_LA_CAPTURE):
             self.stdout.write("Capture web         : déjà présente — sautée")
+            self.nombre_de_notes_sautees += 1
             return None
 
         if self.a_blanc:
@@ -535,7 +680,8 @@
 
         nombre_d_elements = self._ingerer_la_capture(page_de_la_capture)
         self.stdout.write(
-            f"Capture web         : {nombre_d_elements} élément(s)",
+            f"Capture web         : {nombre_d_elements} élément(s)"
+            f"{self._detail_par_label(page_de_la_capture)}",
         )
         return page_de_la_capture
 
@@ -605,6 +751,7 @@
 
         if self._note_deja_presente(carnet_des_etalons, FICHIER_DU_MARKDOWN):
             self.stdout.write("Markdown            : déjà présent — sauté")
+            self.nombre_de_notes_sautees += 1
             return None
 
         if self.a_blanc:
@@ -682,6 +829,7 @@
             carnet_des_etalons, FICHIER_DE_LA_TRANSCRIPTION,
         ):
             self.stdout.write("Transcription JSON  : déjà présente — sautée")
+            self.nombre_de_notes_sautees += 1
             return None
 
         if self.a_blanc:
@@ -735,6 +883,69 @@
         )
         return page_du_json
 
+    def _config_voxtral_utilisable(self):
+        """
+        Rend la configuration Voxtral a passer au job, ou None.
+        / Returns the Voxtral configuration for the job, or None.
+
+        LOCALISATION : front/management/commands/charger_fixtures_sample.py
+
+        POURQUOI PAS `filter(is_active=True).first()`.
+
+        Ce `.first()` prenait N'IMPORTE QUELLE config active.
+        `TranscriptionConfig` n'a aucun `Meta.ordering` : l'ordre est
+        arbitraire cote SGBD. Et son `provider` vaut MOCK par defaut
+        (core/models.py:993) — toute config creee depuis l'admin sans
+        choisir de modele est une config mock. Qu'une seule traine en base
+        et front/tasks.py:634 retombe sur `transcrire_audio_mock`, pendant
+        que le bilan annonce « Audio mp3 (Voxtral) : N tour(s) de parole ».
+        C'est le faux verbatim que le § 3.2 de la spec existe pour
+        interdire. / That `.first()` could pick a MOCK config: the task
+        would silently mock while the report still claimed Voxtral.
+
+        On prend donc la config que `_creer_la_config_de_transcription` a
+        rendue — la seule dont on sait qu'elle est bien Voxtral. Le repli
+        n'accepte qu'un `provider` voxtral, jamais autre chose : mieux
+        vaut sauter le mp3 en le disant que produire un faux verbatim.
+        / Fall back only to a genuinely voxtral provider — skipping loudly
+        beats faking a transcript.
+        """
+        if (
+            self.config_de_transcription is not None
+            and self.config_de_transcription.provider
+            == TranscriptionProvider.VOXTRAL
+        ):
+            return self.config_de_transcription
+
+        return TranscriptionConfig.objects.filter(
+            is_active=True, provider=TranscriptionProvider.VOXTRAL,
+        ).order_by("pk").first()
+
+    def _copier_l_audio_en_temporaire(self, octets_de_l_audio):
+        """
+        Copie l'audio dans AUDIO_TEMP_DIR et rend le chemin de la copie.
+        / Copies the audio into AUDIO_TEMP_DIR and returns the copy's path.
+
+        LOCALISATION : front/management/commands/charger_fixtures_sample.py
+
+        LA TACHE DETRUIT LE FICHIER QU'ON LUI PASSE.
+
+        `transcrire_audio_task` fait `os.unlink(chemin_fichier_audio)` dans
+        un `finally` (front/tasks.py:742-747) : succes ou echec, le fichier
+        recu disparait. Son contrat est de recevoir un fichier TEMPORAIRE
+        — la vue d'import lui passe une copie dans `AUDIO_TEMP_DIR`
+        (front/views.py:5422-5428), jamais le media de la page. Lui passer
+        `page.source_file.path` laissait la note avec un `source_file` qui
+        ne pointait plus sur rien.
+        / The task unlinks whatever path it receives; give it a copy, never
+        the page's own media.
+        """
+        nom_temporaire = f"{uuid.uuid4().hex}.mp3"
+        chemin_temporaire = str(settings.AUDIO_TEMP_DIR / nom_temporaire)
+        with open(chemin_temporaire, "wb") as destination:
+            destination.write(octets_de_l_audio)
+        return chemin_temporaire
+
     def _charger_le_mp3(self, proprietaire, carnet_des_etalons):
         """
         Cree la note audio et lance la vraie transcription Voxtral.
@@ -770,19 +981,32 @@
 
         if self._note_deja_presente(carnet_des_etalons, FICHIER_DU_MP3):
             self.stdout.write("Audio mp3           : déjà présent — sauté")
+            self.nombre_de_notes_sautees += 1
             return None
 
+        # LA GARDE A BLANC EST ICI, AVANT TOUT LE RESTE : le mp3 est le
+        # seul document dont le traitement appelle un service facture.
+        # / The dry-run guard comes first: this is the only paid path.
         if self.a_blanc:
             self.stdout.write("Audio mp3           : serait transcrit (Voxtral)")
             return None
 
         from core.models import (
             PageStatus,
-            TranscriptionConfig,
             TranscriptionJob,
             TranscriptionJobStatus,
         )
 
+        config_voxtral = self._config_voxtral_utilisable()
+        if config_voxtral is None:
+            self.stdout.write(self.style.WARNING(
+                "Audio mp3           : sauté — aucune configuration "
+                "Voxtral active. La transcription serait mockée en "
+                "silence, et le bilan annoncerait quand même des tours "
+                "de parole Voxtral.",
+            ))
+            return None
+
         chemin_du_mp3 = REPERTOIRE_SAMPLE / FICHIER_DU_MP3
         octets_du_mp3 = chemin_du_mp3.read_bytes()
 
@@ -804,23 +1028,23 @@
             page_du_mp3, carnet_des_etalons, proprietaire,
         )
 
-        config_active = TranscriptionConfig.objects.filter(
-            is_active=True,
-        ).first()
         job_de_transcription = TranscriptionJob.objects.create(
             page=page_du_mp3,
-            transcription_config=config_active,
+            transcription_config=config_voxtral,
             audio_filename=FICHIER_DU_MP3,
             status="pending",
         )
 
         from front.tasks import transcrire_audio_task
 
+        chemin_temporaire_de_l_audio = self._copier_l_audio_en_temporaire(
+            octets_du_mp3,
+        )
         transcrire_audio_task.apply(args=[
             job_de_transcription.pk,
-            page_du_mp3.source_file.path,
-            config_active.max_speakers if config_active else 5,
-            config_active.language if config_active else "fr",
+            chemin_temporaire_de_l_audio,
+            config_voxtral.max_speakers,
+            config_voxtral.language,
         ])
 
         page_du_mp3.refresh_from_db()

--- .superpowers/sdd/2026-08-11-charger-fixtures-sample/snapshots/task5fix-tests.py	2026-08-11 17:09:47.800842383 +0200
+++ front/tests/test_charger_fixtures_sample.py	2026-08-11 17:29:37.285893494 +0200
@@ -6,6 +6,7 @@
 """
 
 from io import StringIO
+from types import SimpleNamespace
 from unittest.mock import patch
 
 from django.contrib.auth import get_user_model
@@ -16,6 +17,56 @@
 
 User = get_user_model()
 
+# Les trois taches d'ingestion, par leur chemin d'import. Les tests les
+# mockent presque toujours : une conversion Docling reelle coute 98 s.
+# / The three ingestion tasks, by import path; almost always mocked.
+CIBLE_INGESTION_CAPTURE = (
+    "hypostasis_extractor.tasks_element."
+    "ingerer_une_capture_web_avec_docling.apply"
+)
+CIBLE_INGESTION_FICHIER = (
+    "hypostasis_extractor.tasks_element."
+    "ingerer_un_fichier_avec_docling.apply"
+)
+CIBLE_INGESTION_TRANSCRIPTION = (
+    "hypostasis_extractor.tasks_element."
+    "ingerer_une_transcription_diarisee_en_elements.apply"
+)
+
+
+def ingestion_simulee(*labels_des_elements):
+    """
+    Rend un side_effect de mock qui simule une ingestion REUSSIE.
+    / Returns a mock side_effect simulating a SUCCESSFUL ingestion.
+
+    LOCALISATION : front/tests/test_charger_fixtures_sample.py
+
+    POURQUOI CE HELPER EXISTE
+
+    Un `patch()` nu rend un Mock et ne cree AUCUN element : la page reste
+    a moitie ingeree. Or l'idempotence de la commande porte desormais sur
+    la presence d'elements, pas sur celle de la Page — une page sans
+    element doit pouvoir etre rechargee. Un test qui veut eprouver le saut
+    d'une note deja chargee doit donc simuler une ingestion qui produit
+    vraiment quelque chose.
+    / A bare patch() creates no element, so the page stays half-ingested;
+    idempotency now keys on elements, so tests must simulate real output.
+    """
+    labels_retenus = labels_des_elements or ("text",)
+
+    def executer_l_ingestion(args=None, **kwargs):
+        page_ingeree = Page.objects.get(pk=args[0])
+        for position, label in enumerate(labels_retenus):
+            page_ingeree.elements.create(
+                ordre=position,
+                label=label,
+                texte=f"élément simulé {position}",
+                empreinte_contenu=f"empreinte-{page_ingeree.pk}-{position}",
+            )
+        return SimpleNamespace(result={"elements": len(labels_retenus)})
+
+    return executer_l_ingestion
+
 
 class ProprietaireEtCarnetTest(TestCase):
     """Le socle : qui possède les notes étalons, et où elles sont rangées."""
@@ -209,8 +260,20 @@
             "hypostasis_extractor.tasks_element."
             "ingerer_un_fichier_avec_docling.apply"
         )
-        with patch(cible_capture) as capture_mockee, \
-                patch(cible_fichier) as fichier_mocke:
+        # Les mocks SIMULENT UNE INGESTION REUSSIE (ils creent un element).
+        # Un `patch()` nu n'en creerait aucun : la page resterait a moitie
+        # ingeree, et l'idempotence — qui porte desormais sur la presence
+        # d'elements et non sur celle de la Page — la rechargerait a juste
+        # titre. Ce test-ci parle du cas nominal : une note bel et bien
+        # ingeree ne se reconvertit pas.
+        # / The mocks simulate a SUCCESSFUL ingestion: a bare patch() would
+        # leave the page element-less, which idempotency now (rightly)
+        # treats as reloadable. This test covers the nominal case.
+        with patch(
+            cible_capture, side_effect=ingestion_simulee("text"),
+        ) as capture_mockee, patch(
+            cible_fichier, side_effect=ingestion_simulee("text"),
+        ) as fichier_mocke:
             call_command(
                 "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
             )
@@ -635,3 +698,334 @@
         self.assertTrue(
             Dossier.objects.filter(pk=carnet_avant.pk).exists(),
         )
+
+
+class ConfigDeTranscriptionDuMp3Test(TestCase):
+    """Quelle configuration le job de transcription reçoit, et pourquoi."""
+
+    def _charger_avec_la_cle(self, sortie, side_effect_voxtral=None):
+        """Lance la commande avec MISTRAL_API_KEY, Docling neutralisé."""
+        import os
+
+        with patch.dict(os.environ, {"MISTRAL_API_KEY": "une-cle-de-test"}):
+            with patch(CIBLE_INGESTION_CAPTURE), \
+                    patch(CIBLE_INGESTION_FICHIER), \
+                    patch(CIBLE_INGESTION_TRANSCRIPTION), \
+                    patch(
+                        "front.tasks.transcrire_audio_task.apply",
+                        side_effect=side_effect_voxtral,
+                    ) as voxtral_mocke:
+                call_command("charger_fixtures_sample", stdout=sortie)
+        return voxtral_mocke
+
+    def test_le_mp3_recoit_la_config_voxtral_pas_une_config_mock_active(self):
+        # LE POINT : `filter(is_active=True).first()` prend n'importe
+        # quelle config active. TranscriptionConfig n'a aucun
+        # Meta.ordering, et son provider vaut MOCK par defaut : une config
+        # creee depuis l'admin sans choisir de modele est une config mock.
+        # Si elle passe, front/tasks.py:634 retombe sur transcrire_audio_mock
+        # et le bilan annonce quand meme des tours de parole Voxtral — le
+        # faux verbatim que le § 3.2 de la spec existe pour interdire.
+        # / A MOCK config created first must not be picked over Voxtral:
+        # the task would silently mock and the report would still lie.
+        config_mock_active = TranscriptionConfig.objects.create(
+            name="Config d'un autre usage", model_choice="mock",
+            is_active=True,
+        )
+        self.assertEqual(config_mock_active.provider, "mock")
+
+        self._charger_avec_la_cle(StringIO())
+
+        from core.models import TranscriptionJob
+
+        job_du_mp3 = TranscriptionJob.objects.get()
+        self.assertEqual(job_du_mp3.transcription_config.provider, "voxtral")
+        self.assertEqual(job_du_mp3.transcription_config.name, "Voxtral Mini")
+
+    def test_sans_config_voxtral_le_mp3_est_saute_plutot_que_mocke(self):
+        # Le cas reel : une config nommee « Voxtral Mini » existe deja mais
+        # a ete posee en mock (get_or_create porte sur le seul `name`, il
+        # la rend telle quelle). Sans config voxtral utilisable, mieux vaut
+        # sauter le mp3 en le disant que produire un faux verbatim.
+        # / An existing MOCK config named "Voxtral Mini" is returned as-is
+        # by get_or_create: skip the mp3 loudly rather than fake a verbatim.
+        TranscriptionConfig.objects.create(
+            name="Voxtral Mini", model_choice="mock", is_active=True,
+        )
+
+        sortie = StringIO()
+        voxtral_mocke = self._charger_avec_la_cle(sortie)
+
+        voxtral_mocke.assert_not_called()
+        self.assertIn("Voxtral", sortie.getvalue())
+        self.assertFalse(
+            Page.objects.filter(
+                original_filename="audio-FR-2locuteur-palaiscesar-14s.mp3",
+            ).exists(),
+        )
+
+    def test_le_media_de_la_note_audio_survit_a_la_tache(self):
+        # LE POINT : `transcrire_audio_task` fait os.unlink() sur le chemin
+        # recu, dans un `finally`, succes ou echec (front/tasks.py:742-747).
+        # Son contrat est de recevoir un fichier TEMPORAIRE — la vue
+        # d'import lui passe une copie dans AUDIO_TEMP_DIR. Lui passer
+        # page.source_file.path detruit le media de la note elle-meme.
+        # / The task unlinks the path it receives, in a finally block:
+        # passing page.source_file.path destroys the note's own media.
+        import os
+
+        chemins_recus = []
+
+        def simuler_le_unlink_de_la_tache(args=None, **kwargs):
+            chemin_recu = args[1]
+            chemins_recus.append(chemin_recu)
+            if os.path.exists(chemin_recu):
+                os.unlink(chemin_recu)
+
+        self._charger_avec_la_cle(
+            StringIO(), side_effect_voxtral=simuler_le_unlink_de_la_tache,
+        )
+
+        page_du_mp3 = Page.objects.get(
+            original_filename="audio-FR-2locuteur-palaiscesar-14s.mp3",
+        )
+        self.assertEqual(len(chemins_recus), 1)
+        self.assertNotEqual(chemins_recus[0], page_du_mp3.source_file.path)
+        self.assertTrue(
+            os.path.exists(page_du_mp3.source_file.path),
+            "le média de la note a été supprimé par la tâche",
+        )
+
+
+class RattrapageDesNotesSansElementTest(TestCase):
+    """Une ingestion ratée ne doit pas être définitive."""
+
+    def test_une_note_sans_element_est_rechargee(self):
+        # LE POINT : si l'ingestion echoue, la note reste en base SANS
+        # element. `_note_deja_presente` ne testait que l'existence de la
+        # Page : toutes les relances la sautaient, et l'etat a moitie
+        # ingere ne se reparait jamais sans --reset.
+        # / A failed ingestion left a page with no element that every rerun
+        # skipped: the half-ingested state never repaired itself.
+        with patch(CIBLE_INGESTION_CAPTURE) as capture_ratee, \
+                patch(CIBLE_INGESTION_FICHIER), \
+                patch(CIBLE_INGESTION_TRANSCRIPTION):
+            call_command(
+                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
+            )
+            self.assertEqual(capture_ratee.call_count, 1)
+
+        with patch(
+            CIBLE_INGESTION_CAPTURE,
+            side_effect=ingestion_simulee("text"),
+        ) as capture_rejouee, patch(CIBLE_INGESTION_FICHIER), \
+                patch(CIBLE_INGESTION_TRANSCRIPTION):
+            call_command(
+                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
+            )
+            self.assertEqual(capture_rejouee.call_count, 1)
+
+        # Rechargee, pas doublee : la contrainte unique_url_si_presente
+        # interdirait de toute facon un doublon de la capture web.
+        # / Reloaded, not duplicated.
+        self.assertEqual(
+            Page.objects.filter(source_type="web").count(), 1,
+        )
+
+    def test_une_note_avec_ses_elements_est_bien_sautee(self):
+        with patch(
+            CIBLE_INGESTION_CAPTURE, side_effect=ingestion_simulee("text"),
+        ), patch(
+            CIBLE_INGESTION_FICHIER, side_effect=ingestion_simulee("text"),
+        ), patch(
+            CIBLE_INGESTION_TRANSCRIPTION, side_effect=ingestion_simulee("text"),
+        ):
+            call_command(
+                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
+            )
+
+        with patch(CIBLE_INGESTION_CAPTURE) as capture_rejouee, \
+                patch(CIBLE_INGESTION_FICHIER) as fichier_rejoue, \
+                patch(CIBLE_INGESTION_TRANSCRIPTION) as transcription_rejouee:
+            call_command(
+                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
+            )
+
+        capture_rejouee.assert_not_called()
+        fichier_rejoue.assert_not_called()
+        transcription_rejouee.assert_not_called()
+        self.assertEqual(Page.objects.count(), 3)
+
+    def test_une_note_sans_element_rangee_ailleurs_n_est_pas_supprimee(self):
+        # Une note rangee AUSSI dans un autre carnet appartient a ce
+        # quelqu'un d'autre : on ne la supprime pas pour se rattraper.
+        # Meme regle que --reset. / A note also filed elsewhere is not ours.
+        from core.services.corpus import ranger_une_note_dans_un_carnet
+
+        with patch(CIBLE_INGESTION_CAPTURE), patch(CIBLE_INGESTION_FICHIER), \
+                patch(CIBLE_INGESTION_TRANSCRIPTION):
+            call_command(
+                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
+            )
+
+        page_partagee = Page.objects.get(source_type="web")
+        autre_carnet = Dossier.objects.create(
+            name="Un autre carnet", owner=page_partagee.owner,
+        )
+        ranger_une_note_dans_un_carnet(
+            page_partagee, autre_carnet, page_partagee.owner,
+        )
+
+        with patch(CIBLE_INGESTION_CAPTURE), patch(CIBLE_INGESTION_FICHIER), \
+                patch(CIBLE_INGESTION_TRANSCRIPTION):
+            call_command(
+                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
+            )
+
+        self.assertTrue(Page.objects.filter(pk=page_partagee.pk).exists())
+
+
+class ModeABlancTest(TestCase):
+    """Le mode à blanc doit dire vrai, pas seulement ne rien écrire."""
+
+    def _charger_une_fois_pour_de_vrai(self):
+        with patch(
+            CIBLE_INGESTION_CAPTURE, side_effect=ingestion_simulee("text"),
+        ), patch(
+            CIBLE_INGESTION_FICHIER, side_effect=ingestion_simulee("text"),
+        ), patch(
+            CIBLE_INGESTION_TRANSCRIPTION, side_effect=ingestion_simulee("text"),
+        ):
+            call_command(
+                "charger_fixtures_sample", "--sans-mp3", stdout=StringIO(),
+            )
+
+    def test_a_blanc_dit_vrai_sur_une_base_deja_chargee(self):
+        # LE POINT : `_creer_le_carnet` rendait None en mode a blanc sans
+        # chercher le carnet existant. `_note_deja_presente` rendait donc
+        # toujours False, et le mode a blanc annoncait « serait chargee »
+        # pour les quatre notes alors qu'une vraie execution les sautait
+        # toutes. L'option existe pour montrer ce qui se passerait.
+        # / Dry run must reflect what a real run would do.
+        self._charger_une_fois_pour_de_vrai()
+
+        sortie = StringIO()
+        call_command(
+            "charger_fixtures_sample", "--a-blanc", "--sans-mp3",
+            stdout=sortie,
+        )
+
+        texte_du_bilan = sortie.getvalue()
+        self.assertIn("Capture web         : déjà présente — sautée", texte_du_bilan)
+        self.assertIn("Markdown            : déjà présent — sauté", texte_du_bilan)
+        self.assertNotIn("serait chargée", texte_du_bilan)
+
+    def test_a_blanc_ne_cree_toujours_aucun_carnet(self):
+        # Chercher le carnet existant ne doit pas devenir le creer.
+        # / Looking the notebook up must not become creating it.
+        User.objects.create_superuser(
+            username="deja_la", email="deja@example.org", password="x",
+        )
+
+        call_command(
+            "charger_fixtures_sample", "--a-blanc", "--sans-mp3",
+            stdout=StringIO(),
+        )
+
+        self.assertEqual(Dossier.objects.count(), 0)
+
+    def test_a_blanc_n_appelle_pas_voxtral_meme_avec_la_cle(self):
+        # LE SEUL CHEMIN OU UNE GARDE MAL PLACEE COUTE UN APPEL RESEAU
+        # PAYANT. Le mp3 est le seul document dont le traitement appelle
+        # un service facture ; --a-blanc doit rendre la main avant.
+        # / The only path where a misplaced guard costs a paid network call.
+        import os
+
+        sortie = StringIO()
+        with patch.dict(os.environ, {"MISTRAL_API_KEY": "une-cle-de-test"}):
+            with patch(CIBLE_INGESTION_CAPTURE), \
+                    patch(CIBLE_INGESTION_FICHIER), \
+                    patch(CIBLE_INGESTION_TRANSCRIPTION), \
+                    patch(
+                        "front.tasks.transcrire_audio_task.apply",
+                    ) as voxtral_mocke, patch(
+                        "front.services.transcription_audio."
+                        "transcrire_audio_via_voxtral",
+                    ) as voxtral_direct:
+                call_command(
+                    "charger_fixtures_sample", "--a-blanc", stdout=sortie,
+                )
+
+        voxtral_mocke.assert_not_called()
+        voxtral_direct.assert_not_called()
+        self.assertEqual(Page.objects.count(), 0)
+        self.assertEqual(TranscriptionConfig.objects.count(), 0)
+        from core.models import TranscriptionJob
+
+        self.assertEqual(TranscriptionJob.objects.count(), 0)
+        self.assertIn("serait transcrit", sortie.getvalue())
+
+
+class BilanDeSortieTest(TestCase):
+    """Le bilan du § 4 de la spec, ligne par ligne."""
+
+    def test_le_bilan_detaille_les_labels_de_la_capture_web(self):
+        # Le detail par label n'est imprime que pour la capture web : c'est
+        # elle qui porte le controle de non-regression du § 5 (28 elements
+        # — section_header 4 · list_item 5 · text 19). Sans ce detail,
+        # un retour au decoupage maison (tout en `text`) passerait inapercu.
+        # / Only the web capture prints the per-label breakdown: it carries
+        # the § 5 non-regression check.
+        sortie = StringIO()
+        with patch(
+            CIBLE_INGESTION_CAPTURE,
+            side_effect=ingestion_simulee(
+                "section_header", "list_item", "text", "text",
+            ),
+        ), patch(
+            CIBLE_INGESTION_FICHIER, side_effect=ingestion_simulee("text"),
+        ), patch(
+            CIBLE_INGESTION_TRANSCRIPTION, side_effect=ingestion_simulee("text"),
+        ):
+            call_command(
+                "charger_fixtures_sample", "--sans-mp3", stdout=sortie,
+            )
+
+        texte_du_bilan = sortie.getvalue()
+        self.assertIn(
+            "Capture web         : 4 élément(s) — "
+            "section_header 1 · list_item 1 · text 2",
+            texte_du_bilan,
+        )
+        # Le markdown, lui, n'a pas de detail par label.
+        # / The markdown line carries no per-label detail.
+        self.assertIn("Markdown            : 1 élément(s)", texte_du_bilan)
+        self.assertNotIn("Markdown            : 1 élément(s) —", texte_du_bilan)
+
+    def test_le_bilan_compte_les_notes_sautees(self):
+        with patch(
+            CIBLE_INGESTION_CAPTURE, side_effect=ingestion_simulee("text"),
+        ), patch(
+            CIBLE_INGESTION_FICHIER, side_effect=ingestion_simulee("text"),
+        ), patch(
+            CIBLE_INGESTION_TRANSCRIPTION, side_effect=ingestion_simulee("text"),
+        ):
+            sortie_du_premier_chargement = StringIO()
+            call_command(
+                "charger_fixtures_sample", "--sans-mp3",
+                stdout=sortie_du_premier_chargement,
+            )
+            sortie_du_second_chargement = StringIO()
+            call_command(
+                "charger_fixtures_sample", "--sans-mp3",
+                stdout=sortie_du_second_chargement,
+            )
+
+        self.assertIn(
+            "Notes sautées       : 0 (déjà présentes)",
+            sortie_du_premier_chargement.getvalue(),
+        )
+        self.assertIn(
+            "Notes sautées       : 3 (déjà présentes)",
+            sortie_du_second_chargement.getvalue(),
+        )
