### DIFF DU FIX (tache 8, round 1) — reamorcage du drapeau

diff --git a/hypostasis_extractor/tasks_element.py b/hypostasis_extractor/tasks_element.py
index 02ce929..f0601c3 100644
--- a/hypostasis_extractor/tasks_element.py
+++ b/hypostasis_extractor/tasks_element.py
@@ -191,78 +191,144 @@ def analyser_une_page_avec_le_moteur_element(self, identifiant_du_job):
     )
     return bilan
 
 
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
     relance de detecter un etat actif FANTOME (worker tue, relecture
     U2 defaut H2). La tache FAIT FOI : elle ecrit sans condition —
     c'est la VUE qui pose son etat sous condition (defaut H1).
     / Targeted update with a timestamp; the task's write always wins,
     the view's write is conditional.
+
+    Un cycle qui REDEMARRE (en_attente/en_cours) reармer aussi
+    ingestion_notification_lue a False : sinon une relance qui succede
+    a une notification deja lue ne rallume jamais le badge — le
+    drapeau restait a True pour toujours (revue adverse, tache 8,
+    addendum du 11 aout 2026). On le fait ICI, au seul endroit qui
+    ecrit l'etat pour toutes les taches d'ingestion, plutot que de
+    l'eparpiller chez chaque appelant.
+    / A cycle restarting also rearms the read flag here — the single
+    place writing ingestion state for every ingestion task — rather
+    than scattering the reset across callers.
     """
     from django.utils import timezone
 
-    from core.models import Page
+    from core.models import EtatIngestion, Page
+
+    valeurs_a_ecrire = {
+        "ingestion_etat": etat, "ingestion_detail": detail,
+        "ingestion_maj_le": timezone.now(),
+    }
+    if etat in (EtatIngestion.EN_ATTENTE, EtatIngestion.EN_COURS):
+        valeurs_a_ecrire["ingestion_notification_lue"] = False
+
+    Page.objects.filter(pk=identifiant_de_la_page).update(**valeurs_a_ecrire)
+
 
-    Page.objects.filter(pk=identifiant_de_la_page).update(
-        ingestion_etat=etat, ingestion_detail=detail,
-        ingestion_maj_le=timezone.now(),
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
     )
 
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
         le stockage. / If None, resolved from page.source_file.
     :return: {"elements": int} ou un dict d'erreur
@@ -305,63 +371,67 @@ def ingerer_un_fichier_avec_docling(self, identifiant_de_la_page, chemin_du_fich
     # `.path` peut lever avec un stockage non-fichier : on le dit
     # proprement au lieu de faire planter le worker.
     # / Resolve the path from the page; say it cleanly if impossible.
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
 
     LOCALISATION : hypostasis_extractor/tasks_element.py
 
@@ -391,43 +461,46 @@ def ingerer_une_capture_web_avec_docling(self, identifiant_de_la_page):
         return {"erreur": "page deja ingeree"}
 
     _noter_l_etat_d_ingestion(page.pk, EtatIngestion.EN_COURS)
 
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
 
     LOCALISATION : hypostasis_extractor/tasks_element.py
 
@@ -475,34 +548,37 @@ def ingerer_une_transcription_diarisee_en_elements(self, identifiant_de_la_page)
     # l'etat reste EN_COURS pour toujours — la puce d'ingestion tourne
     # dans le vide et « Relancer » refuse d'agir. Les trois autres
     # taches d'ingestion ont ce filet ; celle-ci l'avait oublie.
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
## migration 0058 complete
     1	"""
     2	Migration de donnees : les pages dont le decoupage est TERMINE (reussi ou
     3	echoue) recoivent ingestion_notification_lue=True.
     4	/ Data migration: pages whose ingestion has FINISHED (succeeded or
     5	failed) get ingestion_notification_lue=True.
     6	
     7	LOCALISATION : core/migrations/0058_estampiller_les_ingestions_deja_vues.py
     8	
     9	Le champ ajoute en 0057 vaut False par defaut. Sans cette migration,
    10	TOUTES les pages deja ingerees (donc deja vues par leur proprietaire,
    11	bien avant l'existence de ce marqueur) apparaitraient d'un coup comme
    12	des notifications non lues dans le dropdown des taches — un badge
    13	alarmant sur un travail termine depuis longtemps. On estampille donc
    14	l'existant comme deja lu ; seules les ingestions a venir demarreront
    15	non lues. Reversible : le rollback remet tout a False. Bilan chiffre
    16	obligatoire (patron des migrations 0042, 0047, 0050).
    17	/ The field defaults to False; without this migration every already-
    18	ingested page would surface as an unread notification. Stamp the
    19	existing pages as read; only future ingestions start unread.
    20	
    21	Restreint a reussie/echouee (revue adverse, tache 8) : en_attente et
    22	en_cours ne sont PAS « deja vues », ce sont des ingestions a mi-parcours
    23	au moment du deploiement — les estampiller aurait eteint leur badge
    24	avant meme que l'utilisateur ait pu voir la fin du cycle. Les valeurs
    25	sont ecrites en dur (reussie/echouee), comme le fait deja la migration
    26	0042 pour ses roles : apps.get_model() ne donne pas acces a
    27	EtatIngestion, et un import direct depuis core.models coupleraient
    28	cette migration figee au code vivant.
    29	/ Restricted to reussie/echouee: en_attente/en_cours are in-flight
    30	ingestions at deploy time, not "already seen" ones.
    31	"""
    32	
    33	from django.db import migrations
    34	
    35	ETATS_TERMINES = ("reussie", "echouee")
    36	
    37	
    38	def estampiller_les_ingestions_deja_vues(apps, schema_editor):
    39	    """
    40	    Pose ingestion_notification_lue=True sur toutes les pages dont
    41	    l'ingestion est terminee (reussie ou echouee) — pas celles encore
    42	    en_attente/en_cours.
    43	    / Stamps ingestion_notification_lue=True on every page whose
    44	    ingestion has finished — not the still in-flight ones.
    45	    """
    46	    Page = apps.get_model("core", "Page")
    47	
    48	    nombre_estampille = Page.objects.filter(
    49	        ingestion_etat__in=ETATS_TERMINES,
    50	    ).update(ingestion_notification_lue=True)
    51	
    52	    print(
    53	        f"\n[migration 0058] ingestions deja vues estampillees : "
    54	        f"{nombre_estampille} page(s)"
    55	    )
    56	
    57	
    58	def desestampiller_les_ingestions(apps, schema_editor):
    59	    """
    60	    Rollback : remet ingestion_notification_lue a False partout.
    61	    / Rollback: resets ingestion_notification_lue to False everywhere.
    62	    """
    63	    Page = apps.get_model("core", "Page")
    64	    nombre = Page.objects.filter(
    65	        ingestion_etat__in=ETATS_TERMINES,
    66	    ).update(ingestion_notification_lue=False)
    67	    print(f"\n[migration 0058 rollback] {nombre} estampille(s) retiree(s)")
    68	
    69	
    70	class Migration(migrations.Migration):
    71	
    72	    dependencies = [
    73	        ("core", "0057_page_ingestion_notification_lue"),
    74	    ]
    75	
    76	    operations = [
    77	        migrations.RunPython(
    78	            estampiller_les_ingestions_deja_vues,
    79	            reverse_code=desestampiller_les_ingestions,
    80	        ),
    81	    ]
