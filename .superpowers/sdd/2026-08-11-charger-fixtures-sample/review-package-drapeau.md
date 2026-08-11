### DIFF — drapeau de lecture par destinataire + rattrapage NULL
diff --git a/core/models.py b/core/models.py
index 174ad0b..0cfac58 100644
--- a/core/models.py
+++ b/core/models.py
@@ -228,25 +228,29 @@ class Page(models.Model):
         null=True, blank=True,
         help_text="Quand ingestion_etat a change pour la derniere fois "
                   "(U2). Sert a detecter un etat actif FANTOME : un "
                   "worker tue laisse 'en_cours' pour toujours ; au-dela "
                   "d'un delai la relance est de nouveau permise. / When "
                   "the state last changed; used to break a stale active "
                   "state left by a dead worker.",
     )
     ingestion_notification_lue = models.BooleanField(
         default=False,
         help_text="La fin du decoupage en elements a-t-elle ete vue ? "
                   "Symetrique du notification_lue des jobs d'analyse et "
-                  "de transcription (addendum du 11 aout 2026).",
+                  "de transcription (addendum du 11 aout 2026). MORT "
+                  "pour la decision depuis la correction 1 (11 aout, "
+                  "meme jour) : voir NotificationTacheLue, qui porte le "
+                  "drapeau PAR DESTINATAIRE. Champ laisse en base "
+                  "(pas de suppression de colonne) mais plus ecrit ni lu.",
     )
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
@@ -1227,25 +1231,29 @@ class TranscriptionJob(models.Model):
         max_length=500,
         blank=True,
         help_text="Nom du fichier audio original",
     )
     processing_time_seconds = models.FloatField(
         null=True,
         blank=True,
         help_text="Duree de traitement en secondes",
     )
     notification_lue = models.BooleanField(
         default=False,
         help_text="Notification de fin lue par le proprietaire / "
-                  "End-of-task notification read by the owner",
+                  "End-of-task notification read by the owner. MORT "
+                  "pour la decision depuis la correction 1 (11 aout "
+                  "2026) : voir NotificationTacheLue, qui porte le "
+                  "drapeau PAR DESTINATAIRE. Champ laisse en base mais "
+                  "plus ecrit ni lu.",
     )
     created_at = models.DateTimeField(auto_now_add=True)
     updated_at = models.DateTimeField(auto_now=True)
 
     def __str__(self):
         return f"TranscriptionJob #{self.pk} — {self.get_status_display()} ({self.page})"
 
     class Meta:
         ordering = ["-created_at"]
         verbose_name = "Job de transcription"
         verbose_name_plural = "Jobs de transcription"
 
diff --git a/front/views_taches.py b/front/views_taches.py
index 07a5098..28cce3d 100644
--- a/front/views_taches.py
+++ b/front/views_taches.py
@@ -68,31 +68,26 @@ def _calculer_etat_bouton(user):
     ).distinct().count()
     nombre_transcriptions_en_cours = TranscriptionJob.objects.filter(
         _filtre_proprietaire_page("page__", user),
         status__in=["pending", "processing"],
     ).distinct().count()
     # Les ingestions n'ont pas de job : leur etat vit sur la Page.
     # `ingestion_etat` vide = aucune ingestion demandee (un .txt, une page
     # nee avant le moteur ELEMENT) : ce n'est pas une tache.
     # / Ingestions have no job; an empty state means no task at all.
     # Defaut 2 (revue de cloture du 11 aout) : un etat actif sans mise
     # a jour depuis DELAI_INGESTION_FANTOME_MIN est un FANTOME (worker
     # mort) — meme regle que relancer_ingestion (front/views.py), sinon
-    # le badge reste allume pour toujours. exclude(...__lt=seuil) garde
-    # les ingestion_maj_le NULL (NULL < seuil est inconnu en SQL, jamais
-    # vrai) : sans date, pas fantome, meme convention que relancer_ingestion.
-    # / An active state stalled past the ghost delay is excluded from
-    # the count; NULL dates are kept (not a ghost), same convention as
-    # relancer_ingestion.
-    # Correction 2 (revue de cloture du 11 aout) : filter(__gte=seuil)
+    # le badge reste allume pour toujours.
+    # Correction 2 (revue de cloture du 11 aout, meme jour) : filter(__gte=seuil)
     # au lieu de exclude(__lt=seuil) — une comparaison NULL est TOUJOURS
     # inconnue en SQL, donc exclue d'un filter(). Un etat actif SANS
     # ingestion_maj_le (le bug corrige de core/views.py, plus jamais
     # produit desormais) est ainsi traite comme un fantome : sans date,
     # rien ne prouve qu'il est recent.
     # / filter(__gte=) instead of exclude(__lt=): a NULL comparison is
     # always unknown in SQL, so filter() drops it — an active state
     # with no timestamp is now treated as a ghost.
     seuil_fantome = timezone.now() - timedelta(minutes=DELAI_INGESTION_FANTOME_MIN)
     nombre_ingestions_en_cours = Page.objects.filter(
         _filtre_proprietaire_page("", user),
         ingestion_etat__in=[EtatIngestion.EN_ATTENTE, EtatIngestion.EN_COURS],
## MIGRATIONS NOUVELLES
--- core/migrations/0059_creer_notification_tache_lue.py ---
     1	# Generated by Django 6.0.2 on 2026-08-11 20:36
     2	
     3	import django.db.models.deletion
     4	from django.conf import settings
     5	from django.db import migrations, models
     6	
     7	
     8	class Migration(migrations.Migration):
     9	
    10	    dependencies = [
    11	        ('core', '0058_estampiller_les_ingestions_deja_vues'),
    12	        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    13	    ]
    14	
    15	    operations = [
    16	        migrations.CreateModel(
    17	            name='NotificationTacheLue',
    18	            fields=[
    19	                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
    20	                ('type_tache', models.CharField(choices=[('extraction', 'Extraction'), ('transcription', 'Transcription'), ('ingestion', 'Ingestion')], max_length=14)),
    21	                ('tache_id', models.PositiveIntegerField(help_text="Pk de l'ExtractionJob, du TranscriptionJob ou de la Page (ingestion) concerne, selon type_tache.")),
    22	                ('utilisateur', models.ForeignKey(help_text='Le destinataire qui a lu cette tache.', on_delete=django.db.models.deletion.CASCADE, related_name='notifications_taches_lues', to=settings.AUTH_USER_MODEL)),
    23	            ],
    24	            options={
    25	                'constraints': [models.UniqueConstraint(fields=('utilisateur', 'type_tache', 'tache_id'), name='unicite_notification_tache_lue_par_destinataire')],
    26	            },
    27	        ),
    28	    ]
--- core/migrations/0060_migrer_les_notifications_lues_par_destinataire.py ---
     1	"""
     2	Migration de donnees : reprend les trois booleens partages
     3	(ExtractionJob.notification_lue, TranscriptionJob.notification_lue,
     4	Page.ingestion_notification_lue) deja a True et cree la ligne
     5	NotificationTacheLue equivalente pour le PROPRIETAIRE DE LA NOTE.
     6	/ Data migration: backfills the three legacy shared booleans already
     7	True into the new per-recipient NotificationTacheLue rows, attributed
     8	to the note's owner.
     9	
    10	LOCALISATION : core/migrations/0060_migrer_les_notifications_lues_par_destinataire.py
    11	
    12	Correction 1 (revue de cloture du 11 aout 2026, tache "drapeau par
    13	destinataire"). Ces booleens portaient une information reelle : SANS
    14	cette migration, toute tache deja lue redeviendrait non lue au premier
    15	chargement du bouton — un badge qui se rallume en masse sur du travail
    16	deja vu.
    17	
    18	Attribution au PROPRIETAIRE DE LA NOTE (job.page.owner /
    19	page.owner), pas au proprietaire d'un carnet contenant : avant
    20	l'elargissement du perimetre de lecture (revue de cloture du 11 aout,
    21	meme journee), seul le proprietaire de la note pouvait marquer une
    22	tache lue (front/views_taches.py utilisait `page__owner=user`,
    23	jamais un carnet). Un booleen a True ne peut donc temoigner que de
    24	CE lecteur-la. Les pages sans owner (legacy, owner_id NULL) sont
    25	ignorees : personne a qui attribuer la lecture.
    26	
    27	Patron des migrations 0042, 0047, 0050, 0058 : bilan chiffre imprime,
    28	reversible (le rollback supprime les lignes creees).
    29	/ Follows the 0042/0047/0050/0058 pattern: printed counts, reversible.
    30	"""
    31	
    32	from django.db import migrations
    33	
    34	
    35	def migrer_les_notifications_lues(apps, schema_editor):
    36	    """
    37	    Pour chaque job/page deja marque lu (booleen partage a True) et
    38	    porteur d'un owner, cree la ligne NotificationTacheLue
    39	    correspondante pour cet owner. get_or_create par securite
    40	    (idempotence si la migration est relancee).
    41	    / For each already-read job/page with an owner, create the
    42	    matching NotificationTacheLue row for that owner.
    43	    """
    44	    ExtractionJob = apps.get_model("hypostasis_extractor", "ExtractionJob")
    45	    TranscriptionJob = apps.get_model("core", "TranscriptionJob")
    46	    Page = apps.get_model("core", "Page")
    47	    NotificationTacheLue = apps.get_model("core", "NotificationTacheLue")
    48	
    49	    nombre_extractions_migrees = 0
    50	    nombre_extractions_sans_owner = 0
    51	    for job in ExtractionJob.objects.filter(
    52	        notification_lue=True, page__owner__isnull=False,
    53	    ).values("pk", "page__owner_id"):
    54	        _ligne, cree = NotificationTacheLue.objects.get_or_create(
    55	            utilisateur_id=job["page__owner_id"],
    56	            type_tache="extraction",
    57	            tache_id=job["pk"],
    58	        )
    59	        if cree:
    60	            nombre_extractions_migrees += 1
    61	    nombre_extractions_sans_owner = ExtractionJob.objects.filter(
    62	        notification_lue=True, page__owner__isnull=True,
    63	    ).count()
    64	
    65	    nombre_transcriptions_migrees = 0
    66	    for job in TranscriptionJob.objects.filter(
    67	        notification_lue=True, page__owner__isnull=False,
    68	    ).values("pk", "page__owner_id"):
    69	        _ligne, cree = NotificationTacheLue.objects.get_or_create(
    70	            utilisateur_id=job["page__owner_id"],
    71	            type_tache="transcription",
    72	            tache_id=job["pk"],
    73	        )
    74	        if cree:
    75	            nombre_transcriptions_migrees += 1
    76	    nombre_transcriptions_sans_owner = TranscriptionJob.objects.filter(
    77	        notification_lue=True, page__owner__isnull=True,
    78	    ).count()
    79	
    80	    nombre_ingestions_migrees = 0
    81	    for page in Page.objects.filter(
    82	        ingestion_notification_lue=True, owner__isnull=False,
    83	    ).values("pk", "owner_id"):
    84	        _ligne, cree = NotificationTacheLue.objects.get_or_create(
    85	            utilisateur_id=page["owner_id"],
    86	            type_tache="ingestion",
    87	            tache_id=page["pk"],
    88	        )
    89	        if cree:
    90	            nombre_ingestions_migrees += 1
    91	    nombre_ingestions_sans_owner = Page.objects.filter(
    92	        ingestion_notification_lue=True, owner__isnull=True,
    93	    ).count()
    94	
    95	    print(
    96	        f"\n[migration 0060] notifications lues migrees par destinataire :\n"
    97	        f"  extraction    : {nombre_extractions_migrees} migree(s), "
    98	        f"{nombre_extractions_sans_owner} ignoree(s) (sans owner)\n"
    99	        f"  transcription : {nombre_transcriptions_migrees} migree(s), "
   100	        f"{nombre_transcriptions_sans_owner} ignoree(s) (sans owner)\n"
   101	        f"  ingestion     : {nombre_ingestions_migrees} migree(s), "
   102	        f"{nombre_ingestions_sans_owner} ignoree(s) (sans owner)"
   103	    )
   104	
   105	
   106	def retirer_les_notifications_migrees(apps, schema_editor):
   107	    """
   108	    Rollback : supprime uniquement les lignes NotificationTacheLue —
   109	    les trois booleens legacy n'ont jamais ete touches par cette
   110	    migration, rien a leur remettre.
   111	    / Rollback: only deletes the created rows; the legacy booleans
   112	    were never written by this migration.
   113	    """
   114	    NotificationTacheLue = apps.get_model("core", "NotificationTacheLue")
   115	    nombre, _detail = NotificationTacheLue.objects.all().delete()
   116	    print(f"\n[migration 0060 rollback] {nombre} ligne(s) supprimee(s)")
   117	
   118	
   119	class Migration(migrations.Migration):
   120	
   121	    dependencies = [
   122	        ("core", "0059_creer_notification_tache_lue"),
   123	        ("hypostasis_extractor", "0033_simplification_element_parent_et_etats"),
   124	    ]
   125	
   126	    operations = [
   127	        migrations.RunPython(
   128	            migrer_les_notifications_lues,
   129	            reverse_code=retirer_les_notifications_migrees,
   130	        ),
   131	    ]
--- core/migrations/0061_documenter_les_champs_de_notification_lue_morts.py ---
     1	# Generated by Django 6.0.2 on 2026-08-11 20:49
     2	
     3	from django.db import migrations, models
     4	
     5	
     6	class Migration(migrations.Migration):
     7	
     8	    dependencies = [
     9	        ('core', '0060_migrer_les_notifications_lues_par_destinataire'),
    10	    ]
    11	
    12	    operations = [
    13	        migrations.AlterField(
    14	            model_name='page',
    15	            name='ingestion_notification_lue',
    16	            field=models.BooleanField(default=False, help_text="La fin du decoupage en elements a-t-elle ete vue ? Symetrique du notification_lue des jobs d'analyse et de transcription (addendum du 11 aout 2026). MORT pour la decision depuis la correction 1 (11 aout, meme jour) : voir NotificationTacheLue, qui porte le drapeau PAR DESTINATAIRE. Champ laisse en base (pas de suppression de colonne) mais plus ecrit ni lu."),
    17	        ),
    18	        migrations.AlterField(
    19	            model_name='transcriptionjob',
    20	            name='notification_lue',
    21	            field=models.BooleanField(default=False, help_text='Notification de fin lue par le proprietaire / End-of-task notification read by the owner. MORT pour la decision depuis la correction 1 (11 aout 2026) : voir NotificationTacheLue, qui porte le drapeau PAR DESTINATAIRE. Champ laisse en base mais plus ecrit ni lu.'),
    22	        ),
    23	    ]
--- hypostasis_extractor/migrations/0034_documenter_les_champs_de_notification_lue_morts.py ---
     1	# Generated by Django 6.0.2 on 2026-08-11 20:49
     2	
     3	from django.db import migrations, models
     4	
     5	
     6	class Migration(migrations.Migration):
     7	
     8	    dependencies = [
     9	        ('hypostasis_extractor', '0033_simplification_element_parent_et_etats'),
    10	    ]
    11	
    12	    operations = [
    13	        migrations.AlterField(
    14	            model_name='extractionjob',
    15	            name='notification_lue',
    16	            field=models.BooleanField(default=False, help_text='Notification de fin lue par le proprietaire / End-of-task notification read by the owner. MORT pour la decision depuis la correction 1 (11 aout 2026) : voir core.models.NotificationTacheLue, qui porte le drapeau PAR DESTINATAIRE. Champ laisse en base mais plus ecrit ni lu.'),
    17	        ),
    18	    ]
