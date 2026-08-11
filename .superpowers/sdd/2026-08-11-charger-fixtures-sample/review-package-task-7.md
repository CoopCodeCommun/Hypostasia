### DIFF DE LA TACHE 7 (notifications d'ingestion)

diff --git a/front/tasks.py b/front/tasks.py
index adf85e3..6654d61 100644
--- a/front/tasks.py
+++ b/front/tasks.py
@@ -692,30 +692,31 @@ def transcrire_audio_task(self, job_id, chemin_fichier_audio, max_locuteurs=5, l
         job_transcription.processing_time_seconds = round(duree_traitement, 2)
         job_transcription.save(update_fields=[
             "raw_result", "status", "processing_time_seconds",
         ])
 
         logger.info(
             "transcrire_audio_task: termine job=%s page=%s segments=%d duree=%.1fs",
             job_id, page_associee.pk, len(segments_transcrits), duree_traitement,
         )
 
         # Notifier le navigateur que la tache est terminee (succes)
         # / Notify the browser that the task is complete (success)
-        notifier_tache_terminee(
-            user_pk=page_associee.owner.pk if page_associee.owner else None,
-            tache_id=job_transcription.pk,
-            tache_type="transcription",
-            status="completed",
-        )
+        for pk_destinataire in _destinataires_de_notification(page_associee):
+            notifier_tache_terminee(
+                user_pk=pk_destinataire,
+                tache_id=job_transcription.pk,
+                tache_type="transcription",
+                status="completed",
+            )
 
     except Exception as erreur_transcription:
         # En cas d'erreur, marquer le job et la page en erreur
         # / On error, mark both job and page as error
         duree_traitement = time.time() - debut_traitement
         message_erreur = str(erreur_transcription)
 
         logger.error(
             "transcrire_audio_task: erreur job=%s — %s",
             job_id, message_erreur, exc_info=True,
         )
 
@@ -723,30 +724,31 @@ def transcrire_audio_task(self, job_id, chemin_fichier_audio, max_locuteurs=5, l
         page_associee.error_message = message_erreur[:1000]
         page_associee.save(update_fields=["status", "error_message"])
 
         job_transcription.status = TranscriptionJobStatus.ERROR
         job_transcription.error_message = message_erreur
         job_transcription.processing_time_seconds = round(duree_traitement, 2)
         job_transcription.save(update_fields=[
             "status", "error_message", "processing_time_seconds",
         ])
 
         # Notifier le navigateur que la tache est terminee (erreur)
         # / Notify the browser that the task is complete (error)
-        notifier_tache_terminee(
-            user_pk=page_associee.owner.pk if page_associee.owner else None,
-            tache_id=job_transcription.pk,
-            tache_type="transcription",
-            status="error",
-        )
+        for pk_destinataire in _destinataires_de_notification(page_associee):
+            notifier_tache_terminee(
+                user_pk=pk_destinataire,
+                tache_id=job_transcription.pk,
+                tache_type="transcription",
+                status="error",
+            )
 
     finally:
         # Supprimer le fichier audio temporaire (qu'il y ait eu erreur ou non)
         # / Delete the temporary audio file (whether there was an error or not)
         if os.path.exists(chemin_fichier_audio):
             try:
                 os.unlink(chemin_fichier_audio)
                 logger.debug("transcrire_audio_task: fichier temp supprime %s", chemin_fichier_audio)
             except OSError as erreur_suppression:
                 logger.warning(
                     "transcrire_audio_task: impossible de supprimer %s — %s",
                     chemin_fichier_audio, erreur_suppression,
diff --git a/hypostasis_extractor/tasks_element.py b/hypostasis_extractor/tasks_element.py
index 02ce929..a1f3596 100644
--- a/hypostasis_extractor/tasks_element.py
+++ b/hypostasis_extractor/tasks_element.py
@@ -194,45 +194,44 @@ def analyser_une_page_avec_le_moteur_element(self, identifiant_du_job):
 
 def _prevenir_l_utilisateur(job_extraction, statut):
     """
     Envoie la notification de fin de tache au proprietaire de la page.
     / Sends the end-of-task notification to the page owner.
 
     LOCALISATION : hypostasis_extractor/tasks_element.py
 
     On reutilise le meme canal que le moteur ANCIEN : l'interface ecoute
     deja ces evenements, il n'y a aucune raison d'en inventer un autre.
     / Same channel as the old engine; the UI already listens to it.
     """
-    from front.tasks import notifier_tache_terminee
+    from front.tasks import _destinataires_de_notification, notifier_tache_terminee
 
-    proprietaire = getattr(job_extraction.page, "owner", None)
-    if proprietaire is None:
-        return
-
-    try:
-        notifier_tache_terminee(
-            user_pk=proprietaire.pk,
-            tache_id=job_extraction.pk,
-            tache_type="analyse",
-            status=statut,
-        )
-    except Exception as erreur:
-        # Une notification qui echoue ne doit pas faire echouer une
-        # analyse qui, elle, a reussi.
-        # / A failed notification must not fail a successful analysis.
-        logger.warning(
-            "Job %s : notification non envoyee (%s).",
-            job_extraction.pk, erreur,
-        )
+    for pk_destinataire in _destinataires_de_notification(job_extraction.page):
+        if pk_destinataire is None:
+            continue
+        try:
+            notifier_tache_terminee(
+                user_pk=pk_destinataire,
+                tache_id=job_extraction.pk,
+                tache_type="analyse",
+                status=statut,
+            )
+        except Exception as erreur:
+            # Une notification qui echoue ne doit pas faire echouer une
+            # analyse qui, elle, a reussi.
+            # / A failed notification must not fail a successful analysis.
+            logger.warning(
+                "Job %s : notification non envoyee (%s).",
+                job_extraction.pk, erreur,
+            )
 
 
 def _noter_l_etat_d_ingestion(identifiant_de_la_page, etat, detail=""):
     """
     Ecrit l'etat d'ingestion sur la page, en une requete UPDATE (U2).
     / Writes the ingestion state on the page in one UPDATE query.
 
     LOCALISATION : hypostasis_extractor/tasks_element.py
 
     Un update() cible, jamais un save() de l'objet entier : la page
     peut etre modifiee ailleurs pendant la conversion (titre, carnets),
     on ne doit ecraser que ces trois champs. L'horodatage permet a la
@@ -243,24 +242,76 @@ def _noter_l_etat_d_ingestion(identifiant_de_la_page, etat, detail=""):
     the view's write is conditional.
     """
     from django.utils import timezone
 
     from core.models import Page
 
     Page.objects.filter(pk=identifiant_de_la_page).update(
         ingestion_etat=etat, ingestion_detail=detail,
         ingestion_maj_le=timezone.now(),
     )
 
 
+def _prevenir_de_l_ingestion(page, statut):
+    """
+    Previent les interesses qu'un decoupage en elements s'est termine.
+    / Tells the concerned parties an element ingestion has finished.
+
+    LOCALISATION : hypostasis_extractor/tasks_element.py
+
+    POURQUOI CETTE FONCTION
+
+    Une ingestion de PDF prend 80 a 164 s (mesure du 11 aout 2026). Sans
+    notification, l'utilisateur qui vient d'importer un document n'a
+    aucun moyen de savoir quand son document est pret : il rafraichit au
+    jugé. Les trois taches d'ingestion etaient les seules du projet a ne
+    rien dire.
+    / An ingestion takes up to 164 s; without this, nobody knows when.
+
+    UNE INGESTION N'A PAS DE JOB
+
+    Les analyses ont un ExtractionJob, les transcriptions un
+    TranscriptionJob. Une ingestion n'a que sa Page, dont
+    `ingestion_etat` porte l'etat. On passe donc la cle primaire de la
+    PAGE comme `tache_id` — la vue des taches le sait et cherche au bon
+    endroit. / An ingestion has no job: the page's pk is the task id.
+
+    :param page: la Page ingeree
+    :param statut: "completed" ou "error"
+    """
+    from front.tasks import (
+        _destinataires_de_notification, notifier_tache_terminee,
+    )
+
+    for pk_destinataire in _destinataires_de_notification(page):
+        if pk_destinataire is None:
+            continue
+        try:
+            notifier_tache_terminee(
+                user_pk=pk_destinataire,
+                tache_id=page.pk,
+                tache_type="ingestion",
+                status=statut,
+            )
+        except Exception as erreur:
+            # Une notification qui echoue ne doit pas faire echouer une
+            # ingestion qui, elle, a reussi. Meme principe que partout
+            # ailleurs dans ce fichier.
+            # / A failed notification must not fail a successful ingestion.
+            logger.warning(
+                "Page %s : notification d'ingestion non transmise (%s).",
+                page.pk, erreur,
+            )
+
+
 @shared_task(bind=True)
 def ingerer_un_fichier_avec_docling(self, identifiant_de_la_page, chemin_du_fichier=None):
     """
     Convertit un fichier en elements, via Docling.
     / Converts a file into elements, via Docling.
 
     LOCALISATION : hypostasis_extractor/tasks_element.py
 
     :param identifiant_de_la_page: la cle primaire de la Page a peupler
     :param chemin_du_fichier: le fichier source a convertir. Si None
         (cas normal depuis la vue d'import, BR-B), la tache le resout
         elle-meme depuis page.source_file — la vue n'a pas a connaitre
@@ -308,57 +359,61 @@ def ingerer_un_fichier_avec_docling(self, identifiant_de_la_page, chemin_du_fich
     if chemin_du_fichier is None:
         if not page.source_file:
             logger.error(
                 "Page %s : pas de fichier source, ingestion impossible.",
                 page.pk,
             )
             _noter_l_etat_d_ingestion(
                 page.pk, EtatIngestion.ECHOUEE,
                 "Le fichier d'origine n'est plus disponible : le "
                 "découpage en éléments est impossible. La note reste "
                 "lisible.",
             )
+            _prevenir_de_l_ingestion(page, "error")
             return {"erreur": "page sans fichier source"}
         try:
             chemin_du_fichier = page.source_file.path
         except Exception as erreur_de_stockage:
             logger.error(
                 "Page %s : le stockage ne donne pas de chemin local (%s).",
                 page.pk, erreur_de_stockage,
             )
             _noter_l_etat_d_ingestion(
                 page.pk, EtatIngestion.ECHOUEE,
                 "Le fichier d'origine n'est pas accessible sur ce "
                 "serveur : le découpage en éléments est impossible. La "
                 "note reste lisible.",
             )
+            _prevenir_de_l_ingestion(page, "error")
             return {"erreur": "fichier source sans chemin local"}
 
     try:
         elements = ingestion_docling.ingerer_un_fichier(page, chemin_du_fichier)
     except Exception as erreur:
         logger.exception(
             "Page %s : l'ingestion Docling a echoue.", page.pk,
         )
         # Le detail technique va au journal ; l'ecran parle simplement
         # et rappelle que rien n'est perdu (U2, FALC).
         # / Technical detail in the log; the screen speaks plainly.
         _noter_l_etat_d_ingestion(
             page.pk, EtatIngestion.ECHOUEE,
             "La conversion du fichier a échoué. La note reste lisible "
             "telle quelle. Vous pouvez relancer le découpage.",
         )
+        _prevenir_de_l_ingestion(page, "error")
         return {"erreur": str(erreur)}
 
     _noter_l_etat_d_ingestion(page.pk, EtatIngestion.REUSSIE)
+    _prevenir_de_l_ingestion(page, "completed")
     logger.info(
         "Page %s : %s element(s) ingere(s) depuis %s.",
         page.pk, len(elements), chemin_du_fichier,
     )
     return {"elements": len(elements)}
 
 
 @shared_task(bind=True)
 def ingerer_une_capture_web_avec_docling(self, identifiant_de_la_page):
     """
     Convertit le HTML d'une capture web en elements, via Docling (U4).
     / Converts a web capture's HTML into elements, via Docling.
@@ -394,37 +449,40 @@ def ingerer_une_capture_web_avec_docling(self, identifiant_de_la_page):
 
     try:
         elements = ingestion_docling.ingerer_une_capture_web(page)
     except ValueError as erreur:
         # Pas de HTML a decouper : dit simplement, page lisible.
         # / No HTML to split; said plainly, page still readable.
         logger.warning("Page %s : capture sans HTML (%s).", page.pk, erreur)
         _noter_l_etat_d_ingestion(
             page.pk, EtatIngestion.ECHOUEE,
             "Cette page capturée n'a pas de contenu à découper en "
             "éléments. Elle reste lisible telle quelle.",
         )
+        _prevenir_de_l_ingestion(page, "error")
         return {"erreur": "capture sans html"}
     except Exception as erreur:
         logger.exception(
             "Page %s : l'ingestion Docling du HTML a echoue.", page.pk,
         )
         _noter_l_etat_d_ingestion(
             page.pk, EtatIngestion.ECHOUEE,
             "La conversion de la page capturée a échoué. La note reste "
             "lisible telle quelle. Vous pouvez relancer le découpage.",
         )
+        _prevenir_de_l_ingestion(page, "error")
         return {"erreur": str(erreur)}
 
     _noter_l_etat_d_ingestion(page.pk, EtatIngestion.REUSSIE)
+    _prevenir_de_l_ingestion(page, "completed")
     logger.info(
         "Page %s : %s element(s) ingere(s) depuis le HTML capture.",
         page.pk, len(elements),
     )
     return {"elements": len(elements)}
 
 
 @shared_task(bind=True)
 def ingerer_une_transcription_diarisee_en_elements(self, identifiant_de_la_page):
     """
     Convertit la transcription d'un audio en elements (D2, ordre 3).
     / Converts an audio transcript into elements.
@@ -478,31 +536,34 @@ def ingerer_une_transcription_diarisee_en_elements(self, identifiant_de_la_page)
     # / Without this, a crash freezes the state on EN_COURS forever.
     try:
         resultat = ingerer_une_transcription_diarisee(page)
     except Exception as erreur:  # noqa: BLE001 — on veut TOUT rattraper
         logger.exception(
             "Page %s : l'ingestion de la transcription a echoue.", page.pk,
         )
         _noter_l_etat_d_ingestion(
             page.pk, EtatIngestion.ECHOUEE,
             "Le découpage de cette transcription en tours de parole a "
             "échoué. L'enregistrement reste lisible tel quel.",
         )
+        _prevenir_de_l_ingestion(page, "error")
         return {"erreur": str(erreur)}
 
     if "erreur" in resultat:
         # Une transcription vide ou illisible n'est pas un plantage :
         # la page reste lisible par son HTML diarise, et l'etat le dit.
         # / An empty transcript is not a crash; the page stays readable.
         _noter_l_etat_d_ingestion(
             page.pk, EtatIngestion.ECHOUEE,
             "Cet enregistrement n'a pas de transcription exploitable à "
             "découper en tours de parole. Il reste lisible tel quel.",
         )
+        _prevenir_de_l_ingestion(page, "error")
         return resultat
 
     _noter_l_etat_d_ingestion(page.pk, EtatIngestion.REUSSIE)
+    _prevenir_de_l_ingestion(page, "completed")
     logger.info(
         "Page %s : %s element(s) crees depuis la transcription.",
         page.pk, resultat["elements_crees"],
     )
     return {"elements": resultat["elements_crees"]}

## NOUVEAU : hypostasis_extractor/tests/test_notifications_ingestion.py
     1	"""
     2	Les taches d'ingestion previennent-elles l'utilisateur ?
     3	/ Do ingestion tasks notify the user?
     4	
     5	LOCALISATION : hypostasis_extractor/tests/test_notifications_ingestion.py
     6	"""
     7	
     8	from unittest.mock import patch
     9	
    10	from django.contrib.auth import get_user_model
    11	from django.test import TestCase
    12	
    13	from core.models import Dossier, Page
    14	from core.services.corpus import ranger_une_note_dans_un_carnet
    15	
    16	User = get_user_model()
    17	
    18	
    19	class NotificationDeLIngestionTest(TestCase):
    20	    """Une ingestion qui se termine doit se faire connaitre."""
    21	
    22	    def setUp(self):
    23	        self.proprietaire = User.objects.create_user(username="proprio")
    24	        self.page = Page.objects.create(
    25	            title="Une note", source_type="web",
    26	            html_original="<p>du texte</p>", html_readability="<p>du texte</p>",
    27	            text_readability="du texte", content_hash="x",
    28	            owner=self.proprietaire,
    29	        )
    30	
    31	    def test_une_capture_ingeree_previent_son_proprietaire(self):
    32	        from hypostasis_extractor.tasks_element import (
    33	            ingerer_une_capture_web_avec_docling,
    34	        )
    35	
    36	        with patch(
    37	            "hypostasis_extractor.services.ingestion_docling."
    38	            "ingerer_une_capture_web", return_value=[1, 2, 3],
    39	        ), patch("front.tasks.notifier_tache_terminee") as notification:
    40	            ingerer_une_capture_web_avec_docling.apply(args=[self.page.pk])
    41	
    42	        notification.assert_called_once_with(
    43	            user_pk=self.proprietaire.pk,
    44	            tache_id=self.page.pk,
    45	            tache_type="ingestion",
    46	            status="completed",
    47	        )
    48	
    49	    def test_une_ingestion_en_echec_previent_aussi(self):
    50	        # Un echec silencieux est pire qu'un echec : l'utilisateur
    51	        # attendrait indefiniment. / A silent failure is worse.
    52	        from hypostasis_extractor.tasks_element import (
    53	            ingerer_une_capture_web_avec_docling,
    54	        )
    55	
    56	        with patch(
    57	            "hypostasis_extractor.services.ingestion_docling."
    58	            "ingerer_une_capture_web", side_effect=ValueError("conversion HS"),
    59	        ), patch("front.tasks.notifier_tache_terminee") as notification:
    60	            ingerer_une_capture_web_avec_docling.apply(args=[self.page.pk])
    61	
    62	        self.assertEqual(
    63	            notification.call_args.kwargs["status"], "error",
    64	        )
    65	
    66	    def test_le_proprietaire_d_un_carnet_est_prevenu_aussi(self):
    67	        # C'est la correction de la phase D, restee a moitie faite :
    68	        # une note rangee dans le carnet d'un collegue doit le prevenir.
    69	        # / The phase D fix, left half-done.
    70	        from hypostasis_extractor.tasks_element import (
    71	            ingerer_une_capture_web_avec_docling,
    72	        )
    73	
    74	        collegue = User.objects.create_user(username="collegue")
    75	        carnet_du_collegue = Dossier.objects.create(
    76	            name="Le carnet du collègue", owner=collegue,
    77	        )
    78	        ranger_une_note_dans_un_carnet(
    79	            self.page, carnet_du_collegue, self.proprietaire,
    80	        )
    81	
    82	        with patch(
    83	            "hypostasis_extractor.services.ingestion_docling."
    84	            "ingerer_une_capture_web", return_value=[1],
    85	        ), patch("front.tasks.notifier_tache_terminee") as notification:
    86	            ingerer_une_capture_web_avec_docling.apply(args=[self.page.pk])
    87	
    88	        pks_prevenus = {
    89	            appel.kwargs["user_pk"] for appel in notification.call_args_list
    90	        }
    91	        self.assertEqual(pks_prevenus, {self.proprietaire.pk, collegue.pk})
    92	
    93	    def test_une_notification_qui_echoue_ne_casse_pas_l_ingestion(self):
    94	        # Une ingestion reussie ne doit pas devenir un echec parce que
    95	        # le canal de notification est tombe.
    96	        # / A dead channel must not fail a successful ingestion.
    97	        from hypostasis_extractor.tasks_element import (
    98	            ingerer_une_capture_web_avec_docling,
    99	        )
   100	
   101	        with patch(
   102	            "hypostasis_extractor.services.ingestion_docling."
   103	            "ingerer_une_capture_web", return_value=[1],
   104	        ), patch(
   105	            "front.tasks.notifier_tache_terminee",
   106	            side_effect=RuntimeError("channel layer HS"),
   107	        ):
   108	            resultat = ingerer_une_capture_web_avec_docling.apply(
   109	                args=[self.page.pk],
   110	            )
   111	
   112	        self.assertEqual(resultat.result, {"elements": 1})
   113	
   114	
   115	class DestinatairesDeLAnalyseEtDeLaTranscriptionTest(TestCase):
   116	    """
   117	    La correction de la phase D, appliquee aux deux chemins oublies.
   118	    / The phase D fix, applied to the two forgotten paths.
   119	    """
   120	
   121	    def test_l_analyse_previent_les_proprietaires_de_carnets(self):
   122	        from hypostasis_extractor.models import ExtractionJob
   123	        from hypostasis_extractor.tasks_element import _prevenir_l_utilisateur
   124	
   125	        proprietaire = User.objects.create_user(username="proprio2")
   126	        collegue = User.objects.create_user(username="collegue2")
   127	        page = Page.objects.create(
   128	            title="Note analysée", source_type="web", html_original="",
   129	            html_readability="", text_readability="", content_hash="y",
   130	            owner=proprietaire,
   131	        )
   132	        carnet = Dossier.objects.create(name="Carnet", owner=collegue)
   133	        ranger_une_note_dans_un_carnet(page, carnet, proprietaire)
   134	
   135	        job = ExtractionJob.objects.create(
   136	            page=page, name="j", prompt_description="p", status="completed",
   137	        )
   138	
   139	        with patch("front.tasks.notifier_tache_terminee") as notification:
   140	            _prevenir_l_utilisateur(job, "completed")
   141	
   142	        pks_prevenus = {
   143	            appel.kwargs["user_pk"] for appel in notification.call_args_list
   144	        }
   145	        self.assertEqual(pks_prevenus, {proprietaire.pk, collegue.pk})
