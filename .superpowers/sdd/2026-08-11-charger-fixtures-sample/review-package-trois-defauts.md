### DIFF — les trois defauts graves de la revue de cloture

diff --git a/core/views.py b/core/views.py
index 600a7d6..08a48ac 100644
--- a/core/views.py
+++ b/core/views.py
@@ -1,28 +1,29 @@
 import logging
 from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
 
 from django.db.models import Q
 from django.shortcuts import render
+from django.utils import timezone
 from django.utils.decorators import method_decorator
 from django.views.decorators.csrf import csrf_exempt
 from rest_framework import permissions, status, viewsets
 from rest_framework.authentication import SessionAuthentication, TokenAuthentication
 from rest_framework.decorators import action
 from rest_framework.response import Response
 
-from .models import Dossier, DossierPartage, Page, RoleSpecialDossier
+from .models import Dossier, DossierPartage, EtatIngestion, Page, RoleSpecialDossier
 from .services.corpus import (
     deplacer_une_note_vers_un_carnet,
     ranger_une_note_dans_un_carnet,
 )
 from .serializers import ClasserDepuisExtensionSerializer, PageCreateSerializer, PageListSerializer
 
 logger = logging.getLogger("core")
 
 # Parametres de tracking a retirer lors de la normalisation d'URL
 # / Tracking parameters to strip during URL normalization
 PARAMETRES_TRACKING = {
     "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
     "fbclid", "gclid", "ref", "mc_cid", "mc_eid",
 }
 
@@ -253,33 +254,47 @@ class PageViewSet(viewsets.ViewSet):
         # moteur ELEMENT — meme patron que l'import fichier (BR-B). Le
         # pipeline synchrone ci-dessus a rempli html_readability :
         # l'affichage reste ANCIEN (double ecriture) jusqu'a ce que les
         # elements existent. La page devient ELEMENT quand la tache
         # aboutit ; un echec laisse une page ANCIEN lisible. Broker en
         # panne : la creation reste un succes, sans fausse promesse.
         # / Web capture also feeds the ELEMENT engine, same pattern as
         # file import; a dead broker must not turn a successful capture
         # into a 500.
         if (page_creee.html_original or "").strip():
             from hypostasis_extractor.tasks_element import (
                 ingerer_une_capture_web_avec_docling,
             )
             try:
                 ingerer_une_capture_web_avec_docling.delay(page_creee.pk)
+                # Meme patron que l'import fichier et la relance
+                # (front/views.py:2103 et 5657) : constante EtatIngestion
+                # (pas de chaine brute) + horodatage pose. Sans
+                # ingestion_maj_le, la detection du fantome (U2) ne peut
+                # jamais se declencher pour une capture web, et le tri
+                # "-ingestion_maj_le" du dropdown la classerait en tete
+                # (NULL en premier sous PostgreSQL).
+                # / Same pattern as file import and relaunch: use the
+                # enum, not a raw string, and stamp ingestion_maj_le —
+                # otherwise ghost detection can never fire for a web
+                # capture, and the dropdown's ordering misplaces it.
                 Page.objects.filter(
                     pk=page_creee.pk, ingestion_etat="",
-                ).update(ingestion_etat="en_attente")
+                ).update(
+                    ingestion_etat=EtatIngestion.EN_ATTENTE,
+                    ingestion_maj_le=timezone.now(),
+                )
             except Exception as erreur_de_broker:
                 logger.error(
                     "PageViewSet.create: ingestion web NON lancee pour la "
                     "page %d (broker indisponible ? %s) — la page reste "
                     "sur l'ancien moteur",
                     page_creee.pk, erreur_de_broker,
                 )
 
         return Response(
             PageListSerializer(page_creee).data,
             status=status.HTTP_201_CREATED,
         )
 
     @action(detail=False, methods=["GET"], url_path="me")
     def me(self, request):
diff --git a/front/tests/test_capture_web_docling.py b/front/tests/test_capture_web_docling.py
index e2f16a0..444e522 100644
--- a/front/tests/test_capture_web_docling.py
+++ b/front/tests/test_capture_web_docling.py
@@ -57,30 +57,40 @@ class CaptureWebRouteVersDoclingTest(TestCase):
     @mock.patch(
         "hypostasis_extractor.tasks_element"
         ".ingerer_une_capture_web_avec_docling.delay"
     )
     def test_une_capture_lance_l_ingestion_et_pose_l_etat(self, delay_mock):
         reponse = self._capturer()
         self.assertEqual(reponse.status_code, 201,
         )
         page = Page.objects.get(url="https://exemple.test/article")
         # Double ecriture : l'affichage reste ANCIEN a la creation.
         # / Double write: display stays OLD at creation time.
         self.assertFalse(page.elements.exists())
         delay_mock.assert_called_once_with(page.pk,
         )
         self.assertEqual(page.ingestion_etat, EtatIngestion.EN_ATTENTE)
+        # Defaut 3 (revue de cloture du 11 aout) : les deux autres
+        # endroits qui posent l'etat en_attente ecrivent aussi
+        # ingestion_maj_le (front/views.py:2103 et 5657). Sans cet
+        # horodatage, la detection du fantome (defaut 2) ne peut jamais
+        # se declencher pour une capture web, et order_by("-ingestion_maj_le")
+        # la classe en tete (NULL en premier sous PostgreSQL).
+        # / The other two call sites that set en_attente also stamp
+        # ingestion_maj_le; without it, ghost detection can never fire
+        # for a web capture, and the dropdown's ordering misplaces it.
+        self.assertIsNotNone(page.ingestion_maj_le)
 
     @mock.patch(
         "hypostasis_extractor.tasks_element"
         ".ingerer_une_capture_web_avec_docling.delay"
     )
     def test_un_broker_en_panne_ne_promet_rien(self, delay_mock):
         delay_mock.side_effect = Exception("broker indisponible",
         )
         reponse = self._capturer()
         self.assertEqual(reponse.status_code, 201,
         )
         page = Page.objects.get(url="https://exemple.test/article")
         self.assertEqual(page.ingestion_etat, "",
         )
         self.assertFalse(page.elements.exists())
diff --git a/front/views.py b/front/views.py
index 59482c9..6a74d77 100644
--- a/front/views.py
+++ b/front/views.py
@@ -383,30 +383,59 @@ def _est_proprietaire_page(utilisateur, page):
     / Rule: note owner OR owner of a containing notebook. The current
     holder keeps their rights, the author gains theirs.
     """
     if not utilisateur or not utilisateur.is_authenticated:
         return False
 
     if page.owner_id == utilisateur.pk:
         return True
 
     return Dossier.objects.filter(
         appartenances_pages__page=page,
         owner=utilisateur,
     ).exists()
 
 
+def _filtre_proprietaire_page(prefixe, utilisateur):
+    """
+    Filtre Q reproduisant EXACTEMENT _est_proprietaire_page, pour les
+    requetes en LISTE (compteurs du badge, dropdown des taches) ou un
+    appel par-objet couterait un N+1 (revue de cloture du 11 aout,
+    defaut 1). `prefixe` est le chemin ORM jusqu'a Page : "" si le
+    queryset porte deja sur Page, "page__" s'il porte sur un job
+    (ExtractionJob/TranscriptionJob) lie a une Page par FK.
+    / Q filter mirroring _est_proprietaire_page for list/count queries,
+    to avoid a per-row N+1. `prefixe` is the ORM path down to Page.
+
+    NE PAS FAIRE DIVERGER de _est_proprietaire_page : proprietaire de
+    la note OU proprietaire d'un carnet qui la contient. Les deux
+    doivent rester la MEME notion d'acces (spec § 11, phase D) — c'est
+    elle que _destinataires_de_notification (front/tasks.py) notifie.
+    / Must stay in sync with _est_proprietaire_page — the one notion of
+    access that _destinataires_de_notification notifies.
+
+    Produit des lignes dupliquees si la note est dans plusieurs carnets
+    du meme proprietaire : l'appelant doit chainer .distinct().
+    / Yields duplicate rows when a note sits in several notebooks of
+    the same owner: callers must chain .distinct().
+    """
+    return (
+        Q(**{f"{prefixe}owner": utilisateur}) |
+        Q(**{f"{prefixe}appartenances_dossiers__dossier__owner": utilisateur})
+    )
+
+
 def _peut_supprimer_extraction(utilisateur, entite):
     """
     Verifie si un utilisateur peut supprimer une extraction.
     Conditions : authentifie, statut nouveau (pas commente), aucun commentaire,
     et (owner du dossier OU contributeur qui a cree l'extraction).
     Logique consolidee suite au retrait de _peut_editer_extraction (A.8 Phase 4-bis).
     / Checks if a user can delete an extraction.
     / Conditions: authenticated, status nouveau (not commente), no comments,
     / and (folder owner OR contributor who created the extraction).
     / Logic consolidated after _peut_editer_extraction removal (A.8 Phase 4-bis).
 
     LOCALISATION : front/views.py
     """
     if not utilisateur or not utilisateur.is_authenticated:
         return False
@@ -799,30 +828,41 @@ def _diff_paragraphes(texte_ancien, texte_nouveau):
 
 # Delai maximum d'inactivite d'un job avant de le considerer comme bloque.
 # Si updated_at n'a pas bouge depuis ce delai, le job est marque en erreur.
 # / Maximum inactivity delay for a job before considering it stalled.
 # / If updated_at hasn't changed for this delay, the job is marked as error.
 DELAI_MAX_INACTIVITE_JOB = timedelta(minutes=5)
 # Un job PENDING attend son tour en file : avec un seul worker et une
 # analyse devant lui, 10 minutes d'attente sont NORMALES. Le tuer a 5
 # minutes annulait un job parfaitement sain (relecture BR-C, defaut
 # n°1). 90 minutes = le plafond de la garde d'edition
 # (garde_edition.DELAI_AVANT_DE_CONSIDERER_UN_JOB_MORT).
 # / A PENDING job is queueing; killing it at 5 min cancelled healthy
 # jobs. 90 min aligns with the edit guard's ceiling.
 DELAI_MAX_ATTENTE_EN_FILE = timedelta(minutes=90)
 
+# Un etat d'ingestion actif (en_attente/en_cours) sans mise a jour depuis
+# ce delai est un FANTOME : le worker Docling qui le portait est mort
+# (relecture U2, defaut H2). relancer_ingestion l'utilise pour autoriser
+# la relance ; le comptage du badge (front/views_taches.py) DOIT
+# utiliser la meme constante, sinon les deux se contredisent au premier
+# changement (defaut 2, revue de cloture du 11 aout).
+# / An active ingestion state with no update past this delay is a
+# GHOST: the worker that owned it died. Both the relaunch guard and the
+# badge counter must share this one constant.
+DELAI_INGESTION_FANTOME_MIN = 15
+
 
 def _verifier_et_nettoyer_job_bloque(job_en_cours):
     """
     Verifie si un job en cours est bloque, et le marque en erreur si oui.
     / Checks whether an in-progress job is stalled; marks it as error.
 
     LOCALISATION : front/views.py
 
     Deux delais, pas un :
     - PROCESSING : les DEUX moteurs battent le coeur a chaque chunk
       (front/tasks.py pour l'ANCIEN, analyse_par_element.py pour
       ELEMENT). 5 minutes sans battement = vraiment mort.
     - PENDING : le job attend en file, personne ne touche updated_at.
       On ne le declare mort qu'au plafond de la garde d'edition (90 min).
     / Two delays: PROCESSING heartbeats each chunk (5 min = dead);
@@ -1105,42 +1145,70 @@ class LectureViewSet(viewsets.ViewSet):
             from core.models import Wiki as ModeleWiki
             enregistrement_de_wiki = ModeleWiki.objects.filter(
                 page=page,
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
+        # Perimetre ELARGI (defaut 1, revue de cloture du 11 aout) :
+        # _filtre_proprietaire_page reproduit _est_proprietaire_page —
+        # proprietaire de la note OU proprietaire d'un carnet qui la
+        # contient — pour matcher _destinataires_de_notification
+        # (front/tasks.py). Sans ca, le proprietaire d'un carnet de
+        # classe recevait la notification mais ne pouvait jamais la
+        # marquer lue par ce chemin.
+        # / Widened scope: mirrors _est_proprietaire_page so the
+        # notebook owner (not just the note owner) can mark it read.
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
-                        pk=marquer_lue, page__owner=request.user,
+                        pk=marquer_lue,
+                    ).filter(
+                        _filtre_proprietaire_page("page__", request.user),
                     ).update(notification_lue=True)
+                elif type_tache == "ingestion":
+                    Page.objects.filter(
+                        pk=marquer_lue,
+                    ).filter(
+                        _filtre_proprietaire_page("", request.user),
+                    ).update(ingestion_notification_lue=True)
                 else:
                     ExtractionJob.objects.filter(
-                        pk=marquer_lue, page__owner=request.user,
+                        pk=marquer_lue,
+                    ).filter(
+                        _filtre_proprietaire_page("page__", request.user),
                     ).update(notification_lue=True)
             except (ValueError, TypeError):
                 # marquer_lue n'est pas un entier valide, ignorer silencieusement
                 # / marquer_lue is not a valid integer, ignore silently
                 pass
 
         analyseurs_actifs = _analyseurs_extraction_utilisables()
 
         # Verifier si un job est en cours pour cette page
         # Si oui, renvoyer le panneau d'analyse en cours avec les entites deja trouvees
         # / Check if a job is currently running for this page
         # / If so, return the in-progress analysis panel with already found entities
         job_en_cours = ExtractionJob.objects.filter(
             page=page,
             status__in=["pending", "processing"],
@@ -2008,33 +2076,36 @@ class LectureViewSet(viewsets.ViewSet):
                 },
             })
             return reponse
 
         def _refus_falc(message):
             reponse_de_refus = HttpResponse(status=409)
             reponse_de_refus["HX-Trigger"] = json.dumps({
                 "showToast": {"message": message, "icon": "warning"},
             })
             return reponse_de_refus
 
         # Un etat actif FANTOME (relecture U2, defaut H2) : un worker
         # docling tue en pleine conversion (serveur 8 Go, concurrence 1)
         # laisse en_cours pour toujours. Au-dela de DELAI_INGESTION_
         # FANTOME_MIN sans mise a jour, on autorise la relance : le
-        # message « attendez » deviendrait un mensonge. / A dead worker
-        # leaves an active state forever; past a delay, allow relaunch.
-        DELAI_INGESTION_FANTOME_MIN = 15
+        # message « attendez » deviendrait un mensonge. DELAI_INGESTION_
+        # FANTOME_MIN est une constante MODULE (pas locale) : le badge
+        # (front/views_taches.py) la reutilise pour ne pas se
+        # contredire (defaut 2, revue de cloture du 11 aout).
+        # / A dead worker leaves an active state forever; past a delay,
+        # allow relaunch. Module-level constant, reused by the badge.
         ingestion_active = page.ingestion_etat in (
             EtatIngestion.EN_ATTENTE, EtatIngestion.EN_COURS,
         )
         if ingestion_active:
             derniere_maj = page.ingestion_maj_le
             fantome = (
                 derniere_maj is not None
                 and (timezone.now() - derniere_maj)
                 > timedelta(minutes=DELAI_INGESTION_FANTOME_MIN)
             )
             if not fantome:
                 return _refus_falc(
                     "Un découpage est déjà en cours pour cette note. "
                     "Attendez qu'il se termine.",
                 )
diff --git a/front/views_taches.py b/front/views_taches.py
index 27a2334..1a6dbfd 100644
--- a/front/views_taches.py
+++ b/front/views_taches.py
@@ -1,76 +1,131 @@
 """
 ViewSet pour le bouton 'taches en cours' dans la toolbar (refonte A.6).
 - bouton() : renvoie l'etat actuel du bouton (compteurs + couleur)
 - dropdown() : renvoie la liste des 10 dernieres taches + OOB swap du bouton
 - marquer_lue() : passe notification_lue=True sur un job
 / ViewSet for the 'tasks in progress' button in the toolbar (A.6 refactor).
 
 LOCALISATION : front/views_taches.py
 """
-from django.http import HttpResponse
+from datetime import timedelta
+
+from django.http import Http404, HttpResponse
 from django.shortcuts import get_object_or_404, render
+from django.utils import timezone
 from rest_framework import permissions, viewsets
 from rest_framework.decorators import action
 
-from core.models import TranscriptionJob
+from core.models import EtatIngestion, Page, TranscriptionJob
 from hypostasis_extractor.models import ExtractionJob
 
+from .views import DELAI_INGESTION_FANTOME_MIN, _est_proprietaire_page, _filtre_proprietaire_page
+
 
 def _calculer_etat_bouton(user):
     """
     Calcule l'etat du bouton + les compteurs pour un utilisateur.
     Priorite : erreur > succes > en_cours > neutre.
     / Compute button state + counters for a user.
     Priority: erreur > succes > en_cours > neutre.
 
     LOCALISATION : front/views_taches.py
+
+    Perimetre ELARGI (defaut 1, revue de cloture du 11 aout) :
+    _filtre_proprietaire_page (front/views.py) reproduit
+    _est_proprietaire_page — proprietaire de la note OU proprietaire
+    d'un carnet qui la contient — pour matcher exactement qui
+    _destinataires_de_notification (front/tasks.py) previent. Ecrit en
+    filtre de requete (pas en boucle par objet) pour eviter le N+1.
+    / Widened scope to match notification recipients; expressed as a
+    query filter, not a per-object loop, to avoid N+1.
     """
     # Comptage taches en cours / Count tasks in progress
     nombre_extractions_en_cours = ExtractionJob.objects.filter(
-        page__owner=user, status__in=["pending", "processing"],
-    ).count()
+        _filtre_proprietaire_page("page__", user),
+        status__in=["pending", "processing"],
+    ).distinct().count()
     nombre_transcriptions_en_cours = TranscriptionJob.objects.filter(
-        page__owner=user, status__in=["pending", "processing"],
-    ).count()
-    nombre_en_cours = nombre_extractions_en_cours + nombre_transcriptions_en_cours
+        _filtre_proprietaire_page("page__", user),
+        status__in=["pending", "processing"],
+    ).distinct().count()
+    # Les ingestions n'ont pas de job : leur etat vit sur la Page.
+    # `ingestion_etat` vide = aucune ingestion demandee (un .txt, une page
+    # nee avant le moteur ELEMENT) : ce n'est pas une tache.
+    # / Ingestions have no job; an empty state means no task at all.
+    # Defaut 2 (revue de cloture du 11 aout) : un etat actif sans mise
+    # a jour depuis DELAI_INGESTION_FANTOME_MIN est un FANTOME (worker
+    # mort) — meme regle que relancer_ingestion (front/views.py), sinon
+    # le badge reste allume pour toujours. exclude(...__lt=seuil) garde
+    # les ingestion_maj_le NULL (NULL < seuil est inconnu en SQL, jamais
+    # vrai) : sans date, pas fantome, meme convention que relancer_ingestion.
+    # / An active state stalled past the ghost delay is excluded from
+    # the count; NULL dates are kept (not a ghost), same convention as
+    # relancer_ingestion.
+    seuil_fantome = timezone.now() - timedelta(minutes=DELAI_INGESTION_FANTOME_MIN)
+    nombre_ingestions_en_cours = Page.objects.filter(
+        _filtre_proprietaire_page("", user),
+        ingestion_etat__in=[EtatIngestion.EN_ATTENTE, EtatIngestion.EN_COURS],
+    ).exclude(
+        ingestion_maj_le__lt=seuil_fantome,
+    ).distinct().count()
+    nombre_en_cours = (
+        nombre_extractions_en_cours
+        + nombre_transcriptions_en_cours
+        + nombre_ingestions_en_cours
+    )
 
     # Comptage taches terminees non lues / Count finished unread tasks
     nombre_extractions_non_lues = ExtractionJob.objects.filter(
-        page__owner=user,
+        _filtre_proprietaire_page("page__", user),
         status__in=["completed", "error"],
         notification_lue=False,
-    ).count()
+    ).distinct().count()
     nombre_transcriptions_non_lues = TranscriptionJob.objects.filter(
-        page__owner=user,
+        _filtre_proprietaire_page("page__", user),
         status__in=["completed", "error"],
         notification_lue=False,
-    ).count()
-    nombre_non_lues = nombre_extractions_non_lues + nombre_transcriptions_non_lues
+    ).distinct().count()
+    nombre_ingestions_non_lues = Page.objects.filter(
+        _filtre_proprietaire_page("", user),
+        ingestion_etat__in=[EtatIngestion.REUSSIE, EtatIngestion.ECHOUEE],
+        ingestion_notification_lue=False,
+    ).distinct().count()
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
-        page__owner=user, status="error", notification_lue=False,
+        _filtre_proprietaire_page("page__", user),
+        status="error", notification_lue=False,
     ).exists() or TranscriptionJob.objects.filter(
-        page__owner=user, status="error", notification_lue=False,
+        _filtre_proprietaire_page("page__", user),
+        status="error", notification_lue=False,
+    ).exists() or Page.objects.filter(
+        _filtre_proprietaire_page("", user),
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
         "nombre_en_cours": nombre_en_cours,
         "nombre_non_lues": nombre_non_lues,
         "etat": etat,
@@ -92,40 +147,44 @@ class TachesViewSet(viewsets.ViewSet):
         Renvoie le HTML du bouton avec son etat actuel (compteur, couleur).
         Appele en reaction a un message WS (via JS dans hypostasia.js).
         / Returns button HTML with current state.
         """
         contexte = _calculer_etat_bouton(request.user)
         return render(request, "front/includes/taches_bouton.html", contexte)
 
     @action(detail=False, methods=["GET"])
     def dropdown(self, request):
         """
         Renvoie la liste des 30 dernieres taches dans un dropdown
         + OOB swap du bouton pour realignement.
         / Returns 30 most recent tasks in a dropdown + OOB swap button.
         """
         # Taches recentes : 30 dernieres extractions + 30 dernieres transcriptions
-        # melangees par created_at desc, max 30 au total
+        # melangees par created_at desc, max 30 au total. Perimetre
+        # ELARGI (defaut 1, revue de cloture du 11 aout) : voir
+        # _filtre_proprietaire_page. .distinct() est necessaire — le
+        # join sur appartenances_dossiers duplique une ligne par carnet.
         # / Recent tasks: 30 latest extractions + 30 latest transcriptions
-        # / merged by created_at desc, max 30 total
+        # / merged by created_at desc, max 30 total. Widened scope; the
+        # / join can duplicate rows, hence distinct().
         extractions_recentes = list(ExtractionJob.objects.filter(
-            page__owner=request.user,
-        ).select_related("page").order_by("-created_at")[:30])
+            _filtre_proprietaire_page("page__", request.user),
+        ).select_related("page").order_by("-created_at").distinct()[:30])
 
         transcriptions_recentes = list(TranscriptionJob.objects.filter(
-            page__owner=request.user,
-        ).select_related("page").order_by("-created_at")[:30])
+            _filtre_proprietaire_page("page__", request.user),
+        ).select_related("page").order_by("-created_at").distinct()[:30])
 
         # Annoter le type pour le template / Annotate type for template
         # Une ExtractionJob peut etre soit une analyse, soit une synthese
         # (raw_result.est_synthese=True). On les distingue ici pour l'affichage.
         # / An ExtractionJob can be either an analysis or a synthesis
         # / (raw_result.est_synthese=True). We distinguish here for display.
         # `type_tache` porte la LOGIQUE (marquage lu, cible du lien) et
         # ne bouge pas ; `libelle_de_tache` porte l'AFFICHAGE. Sans lui,
         # produire un wiki, proposer une mise a jour et verifier des
         # citations donnaient trois lignes IDENTIQUES — « Analyse de
         # "Wiki — …" » — parce que tout ce qui n'est pas une synthese
         # tombait dans « analyse » (recette du 10 aout, F8).
         # / type_tache drives logic and stays; libelle_de_tache is new
         # and only drives display: three different actions used to read
         # exactly the same.
@@ -143,79 +202,166 @@ class TachesViewSet(viewsets.ViewSet):
                 if raw.get("est_verification"):
                     extraction.libelle_de_tache = "Vérification"
                 elif raw.get("est_maj_wiki"):
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
+            _filtre_proprietaire_page("", request.user),
+        ).exclude(ingestion_etat="").order_by("-ingestion_maj_le").distinct()[:30])
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
+
+        Perimetre ELARGI (defaut 1, revue de cloture du 11 aout) : on
+        recupere l'objet par pk SEUL, puis on verifie l'acces avec
+        _est_proprietaire_page — la MEME fonction que le reste du
+        depot, appelee ici sur un objet unique (pas de N+1 : c'est une
+        action detail=True, un seul objet). Acces refuse -> Http404,
+        JAMAIS 403 (doctrine du projet) : un tiers ne doit pas
+        distinguer une tache d'autrui d'une tache inexistante.
+        / Widened scope: fetch by pk alone, then check access with the
+        same _est_proprietaire_page used everywhere else. No access ->
+        Http404, never 403.
         """
         type_tache = request.query_params.get("type")
         # "analyse" et "synthese" pointent tous deux sur ExtractionJob (distinction via raw_result.est_synthese)
         # / "analyse" and "synthese" both point to ExtractionJob (distinguished via raw_result.est_synthese)
         if type_tache in ("analyse", "synthese", "extraction"):
-            job = get_object_or_404(ExtractionJob, pk=pk, page__owner=request.user)
+            job = get_object_or_404(ExtractionJob, pk=pk)
+            if not _est_proprietaire_page(request.user, job.page):
+                raise Http404("No ExtractionJob matches the given query.")
+            job.notification_lue = True
+            job.save(update_fields=["notification_lue"])
         elif type_tache == "transcription":
-            job = get_object_or_404(TranscriptionJob, pk=pk, page__owner=request.user)
+            job = get_object_or_404(TranscriptionJob, pk=pk)
+            if not _est_proprietaire_page(request.user, job.page):
+                raise Http404("No TranscriptionJob matches the given query.")
+            job.notification_lue = True
+            job.save(update_fields=["notification_lue"])
+        elif type_tache == "ingestion":
+            # Pas de job : pk est directement l'id de la Page.
+            # / No job: pk IS the page id.
+            page = get_object_or_404(Page, pk=pk)
+            if not _est_proprietaire_page(request.user, page):
+                raise Http404("No Page matches the given query.")
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
+
+        Perimetre ELARGI (defaut 1, revue de cloture du 11 aout) : voir
+        _filtre_proprietaire_page. .update() sur un queryset filtre par
+        jointure reste une SEULE requete SQL (Django la compile en
+        UPDATE ... WHERE pk IN (sous-requete)) : pas de N+1 ici.
+        / Widened scope; .update() on a joined queryset still compiles
+        to a single UPDATE with a WHERE-pk-IN subquery — no N+1.
         """
         nombre_extractions = ExtractionJob.objects.filter(
-            page__owner=request.user,
+            _filtre_proprietaire_page("page__", request.user),
             status__in=["completed", "error"],
             notification_lue=False,
         ).update(notification_lue=True)
 
         nombre_transcriptions = TranscriptionJob.objects.filter(
-            page__owner=request.user,
+            _filtre_proprietaire_page("page__", request.user),
             status__in=["completed", "error"],
             notification_lue=False,
         ).update(notification_lue=True)
 
+        nombre_ingestions = Page.objects.filter(
+            _filtre_proprietaire_page("", request.user),
+            ingestion_etat__in=[EtatIngestion.REUSSIE, EtatIngestion.ECHOUEE],
+            ingestion_notification_lue=False,
+        ).update(ingestion_notification_lue=True)
+
         # Renvoie le dropdown rafraichi (avec OOB swap du bouton inclus)
         # / Returns refreshed dropdown (with OOB button swap included)
         # Reutilise la logique de dropdown() / Reuses dropdown() logic
         return self.dropdown(request)
