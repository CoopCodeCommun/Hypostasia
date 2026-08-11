### DIFF DE LA TACHE 8 (ingestions dans le bouton et le dropdown)

diff --git a/core/models.py b/core/models.py
index eeb9689..d7eec54 100644
--- a/core/models.py
+++ b/core/models.py
@@ -224,24 +224,30 @@ class Page(models.Model):
         help_text="Message FALC montre a l'utilisateur quand le "
                   "decoupage a echoue. / Plain-words failure message.",
     )
     ingestion_maj_le = models.DateTimeField(
         null=True, blank=True,
         help_text="Quand ingestion_etat a change pour la derniere fois "
                   "(U2). Sert a detecter un etat actif FANTOME : un "
                   "worker tue laisse 'en_cours' pour toujours ; au-dela "
                   "d'un delai la relance est de nouveau permise. / When "
                   "the state last changed; used to break a stale active "
                   "state left by a dead worker.",
     )
+    ingestion_notification_lue = models.BooleanField(
+        default=False,
+        help_text="La fin du decoupage en elements a-t-elle ete vue ? "
+                  "Symetrique du notification_lue des jobs d'analyse et "
+                  "de transcription (addendum du 11 aout 2026).",
+    )
     type_de_note = models.CharField(
         max_length=10,
         choices=TypeDeNote.choices,
         default=TypeDeNote.NOTE,
         db_index=True,
         help_text="Ce que cette note est. Une synthese ou un wiki n'est "
                   "JAMAIS source d'une autre synthese — voir "
                   "core/services/synthese.py. / A synthesis is never a "
                   "source for another synthesis.",
     )
     # Proprietaire de la page (null = legacy/donnees existantes)
     # / Page owner (null = legacy/existing data)
diff --git a/front/views.py b/front/views.py
index 59482c9..8bad3e5 100644
--- a/front/views.py
+++ b/front/views.py
@@ -1108,33 +1108,46 @@ class LectureViewSet(viewsets.ViewSet):
             ).only("pk").first()
             if page.type_de_note == TypeDeNote.WIKI and enregistrement_de_wiki:
                 return redirect(f"/wikis/{enregistrement_de_wiki.pk}/")
             if page.type_de_note == TypeDeNote.SYNTHESE:
                 return redirect(f"/syntheses/{page.pk}/")
 
         # Marquage 'notification lue' si parametres presents (refonte A.6)
         # Le lien dropdown passe ?marquer_lue=X&type=analyse|synthese|transcription
         # ("analyse" et "synthese" pointent tous deux sur ExtractionJob)
         # / Mark notification as read if query params present (A.6 refactor)
         # / Dropdown link passes ?marquer_lue=X&type=analyse|synthese|transcription
         # / ("analyse" and "synthese" both point to ExtractionJob)
+        # Second chemin de marquage "lu", independant de TachesViewSet.marquer_lue :
+        # le lien du dropdown pointe ici, pas vers /taches/<pk>/marquer-lue/
+        # (complement du brief du 11 aout, piege 2). "ingestion" n'a pas de
+        # job : marquer_lue EST directement l'id de la Page.
+        # / Second, independent read-marking path — the dropdown link lands
+        # here, not on TachesViewSet.marquer_lue. "ingestion" has no job:
+        # marquer_lue IS the page id directly.
         marquer_lue = request.query_params.get("marquer_lue")
         type_tache = request.query_params.get("type")
-        if marquer_lue and type_tache in ("analyse", "synthese", "extraction", "transcription"):
+        if marquer_lue and type_tache in (
+            "analyse", "synthese", "extraction", "transcription", "ingestion",
+        ):
             try:
                 if type_tache == "transcription":
                     from core.models import TranscriptionJob
                     TranscriptionJob.objects.filter(
                         pk=marquer_lue, page__owner=request.user,
                     ).update(notification_lue=True)
+                elif type_tache == "ingestion":
+                    Page.objects.filter(
+                        pk=marquer_lue, owner=request.user,
+                    ).update(ingestion_notification_lue=True)
                 else:
                     ExtractionJob.objects.filter(
                         pk=marquer_lue, page__owner=request.user,
                     ).update(notification_lue=True)
             except (ValueError, TypeError):
                 # marquer_lue n'est pas un entier valide, ignorer silencieusement
                 # / marquer_lue is not a valid integer, ignore silently
                 pass
 
         analyseurs_actifs = _analyseurs_extraction_utilisables()
 
         # Verifier si un job est en cours pour cette page
diff --git a/front/views_taches.py b/front/views_taches.py
index 27a2334..0fb213f 100644
--- a/front/views_taches.py
+++ b/front/views_taches.py
@@ -3,71 +3,96 @@ ViewSet pour le bouton 'taches en cours' dans la toolbar (refonte A.6).
 - bouton() : renvoie l'etat actuel du bouton (compteurs + couleur)
 - dropdown() : renvoie la liste des 10 dernieres taches + OOB swap du bouton
 - marquer_lue() : passe notification_lue=True sur un job
 / ViewSet for the 'tasks in progress' button in the toolbar (A.6 refactor).
 
 LOCALISATION : front/views_taches.py
 """
 from django.http import HttpResponse
 from django.shortcuts import get_object_or_404, render
 from rest_framework import permissions, viewsets
 from rest_framework.decorators import action
 
-from core.models import TranscriptionJob
+from core.models import EtatIngestion, Page, TranscriptionJob
 from hypostasis_extractor.models import ExtractionJob
 
 
 def _calculer_etat_bouton(user):
     """
     Calcule l'etat du bouton + les compteurs pour un utilisateur.
     Priorite : erreur > succes > en_cours > neutre.
     / Compute button state + counters for a user.
     Priority: erreur > succes > en_cours > neutre.
 
     LOCALISATION : front/views_taches.py
     """
     # Comptage taches en cours / Count tasks in progress
     nombre_extractions_en_cours = ExtractionJob.objects.filter(
         page__owner=user, status__in=["pending", "processing"],
     ).count()
     nombre_transcriptions_en_cours = TranscriptionJob.objects.filter(
         page__owner=user, status__in=["pending", "processing"],
     ).count()
-    nombre_en_cours = nombre_extractions_en_cours + nombre_transcriptions_en_cours
+    # Les ingestions n'ont pas de job : leur etat vit sur la Page.
+    # `ingestion_etat` vide = aucune ingestion demandee (un .txt, une page
+    # nee avant le moteur ELEMENT) : ce n'est pas une tache.
+    # / Ingestions have no job; an empty state means no task at all.
+    nombre_ingestions_en_cours = Page.objects.filter(
+        owner=user,
+        ingestion_etat__in=[EtatIngestion.EN_ATTENTE, EtatIngestion.EN_COURS],
+    ).count()
+    nombre_en_cours = (
+        nombre_extractions_en_cours
+        + nombre_transcriptions_en_cours
+        + nombre_ingestions_en_cours
+    )
 
     # Comptage taches terminees non lues / Count finished unread tasks
     nombre_extractions_non_lues = ExtractionJob.objects.filter(
         page__owner=user,
         status__in=["completed", "error"],
         notification_lue=False,
     ).count()
     nombre_transcriptions_non_lues = TranscriptionJob.objects.filter(
         page__owner=user,
         status__in=["completed", "error"],
         notification_lue=False,
     ).count()
-    nombre_non_lues = nombre_extractions_non_lues + nombre_transcriptions_non_lues
+    nombre_ingestions_non_lues = Page.objects.filter(
+        owner=user,
+        ingestion_etat__in=[EtatIngestion.REUSSIE, EtatIngestion.ECHOUEE],
+        ingestion_notification_lue=False,
+    ).count()
+    nombre_non_lues = (
+        nombre_extractions_non_lues
+        + nombre_transcriptions_non_lues
+        + nombre_ingestions_non_lues
+    )
 
     # Etat dominant : priorite erreur > en_cours > succes > neutre
     # On veut voir 'en_cours' pendant qu'une tache tourne, meme s'il y a
     # des anciennes notifications non lues (ne pas les masquer mais les
     # reporter a la fin de la tache courante).
     # / Dominant state: priority erreur > en_cours > succes > neutre
     # / We want to see 'en_cours' while a task is running, even if there
     # / are unread old notifications (don't mask them but defer to end of
     # / current task).
     a_des_erreurs_non_lues = ExtractionJob.objects.filter(
         page__owner=user, status="error", notification_lue=False,
     ).exists() or TranscriptionJob.objects.filter(
         page__owner=user, status="error", notification_lue=False,
+    ).exists() or Page.objects.filter(
+        owner=user,
+        ingestion_etat=EtatIngestion.ECHOUEE,
+        ingestion_notification_lue=False,
     ).exists()
 
     if a_des_erreurs_non_lues:
         etat = "erreur"
     elif nombre_en_cours > 0:
         etat = "en_cours"
     elif nombre_non_lues > 0:
         etat = "succes"
     else:
         etat = "neutre"
 
     return {
@@ -146,76 +171,142 @@ class TachesViewSet(viewsets.ViewSet):
                     extraction.libelle_de_tache = "Mise à jour"
                 elif raw.get("est_wiki"):
                     extraction.libelle_de_tache = "Wiki"
                 elif raw.get("est_synthese_carnet"):
                     extraction.libelle_de_tache = "Synthèse dirigée"
                 else:
                     extraction.libelle_de_tache = "Analyse"
         for transcription in transcriptions_recentes:
             transcription.type_tache = "transcription"
             transcription.page_resultat_id = transcription.page.pk
             transcription.libelle_de_tache = "Transcription"
 
-        # Fusionner et trier par date desc, garder 30
-        # / Merge and sort by date desc, keep 30
+        # Les ingestions recentes de l'utilisateur. On annote les memes
+        # attributs que les jobs pour que le template ne connaisse qu'une
+        # seule forme. `status` est traduit depuis ingestion_etat : le
+        # `status` propre de la Page parle d'autre chose. `page = soi-meme`
+        # reproduit la FK `.page` qu'ont ExtractionJob et TranscriptionJob :
+        # le gabarit lit `tache.page.title` et (branche erreur)
+        # `tache.page.pk` sans savoir que la tache EST la page (complement
+        # du brief, piege 1).
+        # / Same annotations as jobs, so the template knows one shape only.
+        # `page = self` mirrors the `.page` FK of the other two models,
+        # since the template reads `tache.page.title`/`tache.page.pk`
+        # without knowing an ingestion tache IS the page.
+        ingestions_recentes = list(Page.objects.filter(
+            owner=request.user,
+        ).exclude(ingestion_etat="").order_by("-ingestion_maj_le")[:30])
+
+        for page_ingeree in ingestions_recentes:
+            page_ingeree.type_tache = "ingestion"
+            page_ingeree.page_resultat_id = page_ingeree.pk
+            page_ingeree.libelle_de_tache = "Découpage"
+            page_ingeree.page = page_ingeree
+            if page_ingeree.ingestion_etat == EtatIngestion.ECHOUEE:
+                page_ingeree.status = "error"
+            elif page_ingeree.ingestion_etat == EtatIngestion.REUSSIE:
+                page_ingeree.status = "completed"
+            else:
+                page_ingeree.status = "processing"
+
+        # Fusionner et trier par date desc, garder 30. Cle de tri commune
+        # explicite (`date_tri`) plutot que `created_at` brut : pour un
+        # job, created_at EST la date de la tache, mais pour une
+        # ingestion, created_at est la date de creation de la NOTE — qui
+        # peut preceder de loin le decoupage. Utiliser ingestion_maj_le
+        # pour les ingestions evite de trier deux sens du temps
+        # differents dans le meme sorted().
+        # / Common sort key rather than raw created_at: a job's
+        # created_at IS its date, but a page's created_at is when the
+        # NOTE was made, not when it was ingested.
+        for extraction in extractions_recentes:
+            extraction.date_tri = extraction.created_at
+        for transcription in transcriptions_recentes:
+            transcription.date_tri = transcription.created_at
+        for page_ingeree in ingestions_recentes:
+            page_ingeree.date_tri = page_ingeree.ingestion_maj_le or page_ingeree.created_at
+
         toutes_taches = sorted(
-            extractions_recentes + transcriptions_recentes,
-            key=lambda t: t.created_at,
+            extractions_recentes + transcriptions_recentes + ingestions_recentes,
+            key=lambda t: t.date_tri,
             reverse=True,
         )[:30]
 
         contexte_bouton = _calculer_etat_bouton(request.user)
 
         return render(request, "front/includes/taches_dropdown.html", {
             "taches": toutes_taches,
             **contexte_bouton,
         })
 
     @action(detail=True, methods=["POST"], url_path="marquer-lue")
     def marquer_lue(self, request, pk=None):
         """
-        Marque une notification comme lue. Pk = id du job.
-        Le query param ?type=extraction|transcription distingue les 2 modeles.
-        / Marks a notification as read. Pk = job id.
+        Marque une notification comme lue. Pk = id du job (ou, pour une
+        ingestion qui n'a pas de job, id de la Page elle-meme).
+        Le query param ?type=extraction|transcription|ingestion distingue
+        les modeles concernes.
+        / Marks a notification as read. Pk = job id, or (ingestion has no
+        job) the Page id itself.
 
         LOCALISATION : front/views_taches.py
         """
         type_tache = request.query_params.get("type")
         # "analyse" et "synthese" pointent tous deux sur ExtractionJob (distinction via raw_result.est_synthese)
         # / "analyse" and "synthese" both point to ExtractionJob (distinguished via raw_result.est_synthese)
         if type_tache in ("analyse", "synthese", "extraction"):
             job = get_object_or_404(ExtractionJob, pk=pk, page__owner=request.user)
+            job.notification_lue = True
+            job.save(update_fields=["notification_lue"])
         elif type_tache == "transcription":
             job = get_object_or_404(TranscriptionJob, pk=pk, page__owner=request.user)
+            job.notification_lue = True
+            job.save(update_fields=["notification_lue"])
+        elif type_tache == "ingestion":
+            # Pas de job : pk est directement l'id de la Page. Le filtre
+            # owner=request.user donne un 404 (jamais un 403) pour la
+            # page d'autrui — doctrine du projet.
+            # / No job: pk IS the page id. owner filter yields 404, never
+            # 403, for another user's page — project doctrine.
+            page = get_object_or_404(Page, pk=pk, owner=request.user)
+            page.ingestion_notification_lue = True
+            page.save(update_fields=["ingestion_notification_lue"])
         else:
-            return HttpResponse("Parametre type=analyse|synthese|transcription requis", status=400)
+            return HttpResponse(
+                "Parametre type=analyse|synthese|transcription|ingestion requis",
+                status=400,
+            )
 
-        job.notification_lue = True
-        job.save(update_fields=["notification_lue"])
         return HttpResponse(status=204)
 
     @action(detail=False, methods=["POST"], url_path="marquer-toutes-lues")
     def marquer_toutes_lues(self, request):
         """
         Marque TOUTES les notifications terminees du user comme lues.
         Refetch ensuite le dropdown frais + OOB swap du bouton (etat neutre).
         / Mark ALL user's finished notifications as read.
         Then refetch fresh dropdown + OOB swap of button (neutre state).
 
         LOCALISATION : front/views_taches.py
         """
         nombre_extractions = ExtractionJob.objects.filter(
             page__owner=request.user,
             status__in=["completed", "error"],
             notification_lue=False,
         ).update(notification_lue=True)
 
         nombre_transcriptions = TranscriptionJob.objects.filter(
             page__owner=request.user,
             status__in=["completed", "error"],
             notification_lue=False,
         ).update(notification_lue=True)
 
+        nombre_ingestions = Page.objects.filter(
+            owner=request.user,
+            ingestion_etat__in=[EtatIngestion.REUSSIE, EtatIngestion.ECHOUEE],
+            ingestion_notification_lue=False,
+        ).update(ingestion_notification_lue=True)
+
         # Renvoie le dropdown rafraichi (avec OOB swap du bouton inclus)
         # / Returns refreshed dropdown (with OOB button swap included)
         # Reutilise la logique de dropdown() / Reuses dropdown() logic
         return self.dropdown(request)

## MIGRATIONS
     1	# Generated by Django 6.0.2 on 2026-08-11 17:28
     2	
     3	from django.db import migrations, models
     4	
     5	
     6	class Migration(migrations.Migration):
     7	
     8	    dependencies = [
     9	        ('core', '0056_suppression_du_flag_moteur'),
    10	    ]
    11	
    12	    operations = [
    13	        migrations.AddField(
    14	            model_name='page',
    15	            name='ingestion_notification_lue',
    16	            field=models.BooleanField(default=False, help_text="La fin du decoupage en elements a-t-elle ete vue ? Symetrique du notification_lue des jobs d'analyse et de transcription (addendum du 11 aout 2026)."),
    17	        ),
    18	    ]

     1	"""
     2	Migration de donnees : les pages deja ingerees (ingestion_etat non vide)
     3	recoivent ingestion_notification_lue=True.
     4	/ Data migration: pages already ingested get ingestion_notification_lue=True.
     5	
     6	LOCALISATION : core/migrations/0058_estampiller_les_ingestions_deja_vues.py
     7	
     8	Le champ ajoute en 0057 vaut False par defaut. Sans cette migration,
     9	TOUTES les pages deja ingerees (donc deja vues par leur proprietaire,
    10	bien avant l'existence de ce marqueur) apparaitraient d'un coup comme
    11	des notifications non lues dans le dropdown des taches — un badge
    12	alarmant sur un travail termine depuis longtemps. On estampille donc
    13	l'existant comme deja lu ; seules les ingestions a venir demarreront
    14	non lues. Reversible : le rollback remet tout a False. Bilan chiffre
    15	obligatoire (patron des migrations 0042, 0047, 0050).
    16	/ The field defaults to False; without this migration every already-
    17	ingested page would surface as an unread notification. Stamp the
    18	existing pages as read; only future ingestions start unread.
    19	"""
    20	
    21	from django.db import migrations
    22	
    23	
    24	def estampiller_les_ingestions_deja_vues(apps, schema_editor):
    25	    """
    26	    Pose ingestion_notification_lue=True sur toutes les pages dont
    27	    l'ingestion a deja ete demandee (ingestion_etat non vide).
    28	    / Stamps ingestion_notification_lue=True on every page whose
    29	    ingestion was already requested.
    30	    """
    31	    Page = apps.get_model("core", "Page")
    32	
    33	    nombre_estampille = Page.objects.exclude(ingestion_etat="").update(
    34	        ingestion_notification_lue=True,
    35	    )
    36	
    37	    print(
    38	        f"\n[migration 0058] ingestions deja vues estampillees : "
    39	        f"{nombre_estampille} page(s)"
    40	    )
    41	
    42	
    43	def desestampiller_les_ingestions(apps, schema_editor):
    44	    """
    45	    Rollback : remet ingestion_notification_lue a False partout.
    46	    / Rollback: resets ingestion_notification_lue to False everywhere.
    47	    """
    48	    Page = apps.get_model("core", "Page")
    49	    nombre = Page.objects.exclude(ingestion_etat="").update(
    50	        ingestion_notification_lue=False,
    51	    )
    52	    print(f"\n[migration 0058 rollback] {nombre} estampille(s) retiree(s)")
    53	
    54	
    55	class Migration(migrations.Migration):
    56	
    57	    dependencies = [
    58	        ("core", "0057_page_ingestion_notification_lue"),
    59	    ]
    60	
    61	    operations = [
    62	        migrations.RunPython(
    63	            estampiller_les_ingestions_deja_vues,
    64	            reverse_code=desestampiller_les_ingestions,
    65	        ),
    66	    ]

## TESTS
     1	"""
     2	Les ingestions apparaissent-elles dans le bouton et le dropdown ?
     3	/ Do ingestions show up in the tasks button and dropdown?
     4	
     5	LOCALISATION : front/tests/test_taches_ingestion.py
     6	"""
     7	
     8	from django.contrib.auth import get_user_model
     9	from django.test import TestCase
    10	
    11	from core.models import EtatIngestion, Page
    12	
    13	User = get_user_model()
    14	
    15	
    16	class IngestionDansLesTachesTest(TestCase):
    17	
    18	    def setUp(self):
    19	        self.proprietaire = User.objects.create_user(
    20	            username="proprio", password="motdepasse",
    21	        )
    22	        self.client.force_login(self.proprietaire)
    23	
    24	    def _creer_page(self, etat, lue=False):
    25	        return Page.objects.create(
    26	            title="Un document", source_type="file",
    27	            original_filename="doc.pdf",
    28	            html_original="", html_readability="", text_readability="",
    29	            content_hash="", owner=self.proprietaire,
    30	            ingestion_etat=etat, ingestion_notification_lue=lue,
    31	        )
    32	
    33	    def test_une_ingestion_en_cours_compte_dans_le_bouton(self):
    34	        self._creer_page(EtatIngestion.EN_COURS)
    35	
    36	        reponse = self.client.get("/taches/bouton/")
    37	
    38	        self.assertContains(reponse, "1")
    39	        self.assertEqual(reponse.context["nombre_en_cours"], 1)
    40	
    41	    def test_une_ingestion_reussie_non_lue_compte_comme_non_lue(self):
    42	        self._creer_page(EtatIngestion.REUSSIE, lue=False)
    43	
    44	        reponse = self.client.get("/taches/bouton/")
    45	
    46	        self.assertEqual(reponse.context["nombre_non_lues"], 1)
    47	
    48	    def test_une_ingestion_deja_lue_ne_compte_plus(self):
    49	        self._creer_page(EtatIngestion.REUSSIE, lue=True)
    50	
    51	        reponse = self.client.get("/taches/bouton/")
    52	
    53	        self.assertEqual(reponse.context["nombre_non_lues"], 0)
    54	
    55	    def test_une_page_sans_ingestion_ne_compte_jamais(self):
    56	        # Une page nee avant le moteur ELEMENT, ou un .txt : son
    57	        # ingestion_etat est vide, elle n'est pas une tache.
    58	        # / A page that never requested an ingestion is not a task.
    59	        self._creer_page("")
    60	
    61	        reponse = self.client.get("/taches/bouton/")
    62	
    63	        self.assertEqual(reponse.context["nombre_non_lues"], 0)
    64	        self.assertEqual(reponse.context["nombre_en_cours"], 0)
    65	
    66	    def test_l_ingestion_apparait_dans_le_dropdown(self):
    67	        page = self._creer_page(EtatIngestion.REUSSIE)
    68	
    69	        reponse = self.client.get("/taches/dropdown/")
    70	
    71	        libelles = [t.libelle_de_tache for t in reponse.context["taches"]]
    72	        self.assertIn("Découpage", libelles)
    73	        self.assertEqual(reponse.context["taches"][0].page_resultat_id, page.pk)
    74	
    75	    def test_marquer_lue_une_ingestion(self):
    76	        page = self._creer_page(EtatIngestion.REUSSIE, lue=False)
    77	
    78	        self.client.post(f"/taches/{page.pk}/marquer-lue/?type=ingestion")
    79	
    80	        page.refresh_from_db()
    81	        self.assertTrue(page.ingestion_notification_lue)
    82	
    83	    def test_on_ne_marque_pas_lue_la_page_d_un_autre(self):
    84	        # Doctrine du projet : 404, jamais 403.
    85	        # / Project doctrine: 404, never 403.
    86	        autre = User.objects.create_user(username="autre")
    87	        page_d_autrui = Page.objects.create(
    88	            title="Pas la mienne", source_type="file",
    89	            html_original="", html_readability="", text_readability="",
    90	            content_hash="", owner=autre,
    91	            ingestion_etat=EtatIngestion.REUSSIE,
    92	        )
    93	
    94	        reponse = self.client.post(
    95	            f"/taches/{page_d_autrui.pk}/marquer-lue/?type=ingestion",
    96	        )
    97	
    98	        self.assertEqual(reponse.status_code, 404)
    99	        page_d_autrui.refresh_from_db()
   100	        self.assertFalse(page_d_autrui.ingestion_notification_lue)
   101	
   102	    def test_marquer_lue_via_le_lien_lecture(self):
   103	        # Deuxieme chemin de marquage : le lien du dropdown pointe vers
   104	        # /lire/<id>/?marquer_lue=<pk>&type=ingestion, traite par
   105	        # front/views.py (LectureViewSet.retrieve), pas par le ViewSet
   106	        # Taches. Les deux chemins sont independants (complement du brief,
   107	        # piege 2).
   108	        # / Second read-marking path: the dropdown link, handled by
   109	        # LectureViewSet.retrieve, independent from TachesViewSet.
   110	        page = self._creer_page(EtatIngestion.REUSSIE, lue=False)
   111	
   112	        self.client.get(
   113	            f"/lire/{page.pk}/?marquer_lue={page.pk}&type=ingestion",
   114	        )
   115	
   116	        page.refresh_from_db()
   117	        self.assertTrue(page.ingestion_notification_lue)
