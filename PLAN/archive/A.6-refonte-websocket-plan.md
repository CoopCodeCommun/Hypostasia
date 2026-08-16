# Plan A.6 — Refonte WebSocket + bouton "tâches en cours"

> **Pour les workers agentiques :** ce plan suit la skill `superpowers:writing-plans`. Les étapes utilisent la syntaxe checkbox `- [ ]` pour le suivi. Voir [PLAN/A.6-refonte-websocket-spec.md](A.6-refonte-websocket-spec.md) pour le design validé du brainstorming.

**Goal :** simplifier radicalement la couche WebSocket en supprimant la progression streaming (drawer cartes au fil de l'eau, OOB swaps en cascade, 10+ templates "en cours") au profit d'un seul bouton "tâches en cours" dans la toolbar avec dropdown au clic. Notification de fin de tâche via WS minimal + toast HX-Trigger au lancement.

**Architecture :**
- Conserver Channels + Daphne + channels-redis. Réduire à 1 seul `NotificationConsumer` minimal (~30 lignes).
- Ajouter `notification_lue: BooleanField` sur `ExtractionJob` (`hypostasis_extractor/models.py`) et `TranscriptionJob` (`core/models.py`).
- Nouveau ViewSet `TachesViewSet` avec 3 endpoints : `bouton`, `dropdown`, `marquer_lue`.
- Bouton dans la toolbar `base.html` avec 4 états CSS (`neutre|en_cours|succes|erreur`). JS minimal pour le WS handler + toggle dropdown.
- Tâches Celery (analyse, synthèse, transcription audio) : supprimer les ~8 appels intermédiaires "progression", remplacer les 3 appels finaux par `notifier_tache_terminee(...)`.
- Suppression de 10 templates "en cours", `notifications_progression.js`, `views_ws.py`, `ProgressionTacheConsumer`, `htmx-ext-ws`.

**Tech stack :** Django 6 + DRF + HTMX + Channels + Celery + PostgreSQL. Stack-ccc / skill djc.

**Ordre bottom-up** : on construit le neuf d'abord (modèles + helper + consumer + ViewSet + bouton + WS handler), puis on bascule les tâches Celery sur le nouveau helper, **puis** on retire l'ancien (templates, JS, views_ws, ext htmx-ws, tests obsolètes).

**Hors périmètre :**
- Reformulation IA + Restitution IA → retirées en **A.7**. Leurs templates `reformulation_en_cours.html` et `restitution_ia_en_cours.html` **restent** en place après A.6 (utilisés par leurs vues respectives qui ne sont pas modifiées en A.6).
- Le calcul de coût d'analyse (`cout_reel_euros`, `tokens_reels`) reste intact.
- L'extension navigateur Hypostasia n'est pas concernée.

**Préférences user :**
- Aucune commande git automatique
- Pas de `Co-Authored-By` dans les messages de commit
- Tests Django dans Docker via `docker exec hypostasia_web uv run python manage.py test --noinput`

---

## Cartographie des changements

### Fichiers supprimés (5)

| Fichier | Rôle |
|---|---|
| `front/views_ws.py` | ViewSet de test WS (~99 lignes) |
| `front/static/front/js/notifications_progression.js` | JS de progression (~109 lignes) |
| `front/static/front/vendor/htmx-ext-ws-2.0.4.js` | Extension HTMX WebSocket |
| **8 templates "en cours"** : `bandeau_notification.html`, `drawer_cartes_partielles.html`, `panneau_analyse_en_cours.html`, `synthese_en_cours_drawer.html`, `transcription_en_cours.html`, `ws_analyse_progression.html`, `ws_progression_tache.html`, `ws_synthese_terminee.html`, `ws_test_feedback.html`, `ws_toast.html` | ~800 lignes |

### Fichiers créés (5)

| Fichier | Rôle |
|---|---|
| `hypostasis_extractor/migrations/0027_extractionjob_notification_lue.py` | `AddField` auto-générée |
| `core/migrations/0031_transcriptionjob_notification_lue.py` | `AddField` auto-générée |
| `core/migrations/0032_marquer_notifications_existantes_lues.py` | Data migration manuelle |
| `front/views_taches.py` | Nouveau ViewSet `TachesViewSet` (~100 lignes) |
| `front/templates/front/includes/taches_bouton.html` | Bouton avec 4 états CSS (~30 lignes) |
| `front/templates/front/includes/taches_dropdown.html` | Liste 10 dernières tâches (~80 lignes) |

### Fichiers modifiés (8)

| Fichier | Changement |
|---|---|
| `core/models.py` | Ajouter `notification_lue` sur `TranscriptionJob` (l. 984+) |
| `hypostasis_extractor/models.py` | Ajouter `notification_lue` sur `ExtractionJob` |
| `front/consumers.py` | Refonte complète : retrait `ProgressionTacheConsumer` (~200 lignes retirées) + simplification `NotificationConsumer` (~30 lignes finales) |
| `front/routing.py` | Retrait route `ws/tache/<str:tache_id>/`, garder seulement `ws/notifications/` |
| `front/urls.py` | Ajouter `router.register(r"taches", TachesViewSet, basename="tache")` |
| `front/tasks.py` | Retrait helper `envoyer_progression_websocket()` + 8 appels intermédiaires "progression". Ajout helper `notifier_tache_terminee()` + 3 appels finaux dans `analyser_page_task`, `synthetiser_page_task`, `transcrire_audio_task` |
| `front/views.py` | Modifier `LectureViewSet.analyser` et `LectureViewSet.synthetiser` pour retourner toast HX-Trigger au lieu du drawer "en cours" + traiter query param `?marquer_lue=X&type=Y` dans `LectureViewSet.retrieve` |
| `front/templates/front/base.html` | Ajouter bouton `#btn-taches` dans toolbar + wrapper dropdown caché. Retirer ref `htmx-ext-ws`. Retirer ref `notifications_progression.js`. Retirer includes conditionnels (`bandeau_notification`, etc.) si présents |
| `front/static/front/js/hypostasia.js` | Ajouter ~30 lignes : connexion WS notifications + handler `tache_terminee` + toggle dropdown au clic |
| `front/tests/test_phases.py` | Retrait classes obsolètes (Phase14, Phase29 WS, Phase16BandeauNotificationTest, etc.) + ajout 3 classes `Phase26iTachesViewSetTest`, `Phase26iHelperNotifierTacheTermineeTest`, `Phase26iNotificationConsumerTest` |
| `front/tests/test_phase28_light.py` | Retrait sections WS de progression (~7 refs) |
| `front/tests/test_phase29_synthese_drawer.py` | Retrait tests OOB swap drawer (~4 refs) + retrait du fichier entier si tout devient obsolète |
| `front/tests/test_analyse_drawer_unifie.py` | Retrait du fichier entier (tout teste le pattern OOB+WS) |

### Cas particuliers

**`reformulation_en_cours.html` et `restitution_ia_en_cours.html`** : conservés en A.6 (retirés en A.7). Les vues correspondantes ne sont pas modifiées en A.6.

**`ws_test_feedback.html`** : utilisé par `hypostasis_extractor/views.py` (ligne 1707) pour le test live d'un analyseur. **À conserver** : c'est un usage hors périmètre A.6 (test extraction d'analyseur). Le grep le confirme.

**Numérotation des migrations** : à confirmer en exécution. Si entre temps de nouvelles migrations ont été créées, ajuster les numéros.

**Ordre de bascule des tâches Celery** : Tasks 8 (analyse/synthèse) avant Task 9 (suppression ancien helper) pour éviter `NameError`.

---

## Tâches

### Task 1 : Modèles `notification_lue` + migrations

**Files:**
- Modify: `core/models.py` (ajouter champ sur `TranscriptionJob`, l. 984+)
- Modify: `hypostasis_extractor/models.py` (ajouter champ sur `ExtractionJob`)
- Create: `core/migrations/0031_transcriptionjob_notification_lue.py` (auto)
- Create: `hypostasis_extractor/migrations/0027_extractionjob_notification_lue.py` (auto)

- [ ] **Step 1.1 — Lire les modèles `TranscriptionJob` et `ExtractionJob`**

```bash
Read /home/jonas/Gits/Hypostasia/core/models.py offset=984 limit=20
rg -n "^class ExtractionJob" /home/jonas/Gits/Hypostasia/hypostasis_extractor/models.py
```

Identifier le bon endroit pour ajouter le champ (après les champs status/created_at, avant les méthodes).

- [ ] **Step 1.2 — Ajouter le champ sur `TranscriptionJob`**

Dans `core/models.py`, ajouter :
```python
    notification_lue = models.BooleanField(
        default=False,
        help_text="Notification de fin lue par le proprietaire / "
                  "End-of-task notification read by the owner",
    )
```

- [ ] **Step 1.3 — Ajouter le champ sur `ExtractionJob`**

Dans `hypostasis_extractor/models.py`, ajouter le même champ avec le même `help_text`.

- [ ] **Step 1.4 — Auto-générer les migrations dans Docker**

```bash
docker exec hypostasia_web uv run python manage.py makemigrations 2>&1 | tail -10
```

Attendu :
```
Migrations for 'core':
  core/migrations/00XX_transcriptionjob_notification_lue.py
    - Add field notification_lue to transcriptionjob
Migrations for 'hypostasis_extractor':
  hypostasis_extractor/migrations/00XX_extractionjob_notification_lue.py
    - Add field notification_lue to extractionjob
```

Renommer pour lisibilité si besoin :
```bash
mv /home/jonas/Gits/Hypostasia/core/migrations/00XX_*.py /home/jonas/Gits/Hypostasia/core/migrations/0031_transcriptionjob_notification_lue.py
mv /home/jonas/Gits/Hypostasia/hypostasis_extractor/migrations/00XX_*.py /home/jonas/Gits/Hypostasia/hypostasis_extractor/migrations/0027_extractionjob_notification_lue.py
```

- [ ] **Step 1.5 — Appliquer les migrations dans Docker**

```bash
docker exec hypostasia_web uv run python manage.py migrate 2>&1 | tail -5
```

Attendu : `Applying core.0031... OK` et `Applying hypostasis_extractor.0027... OK`.

- [ ] **Step 1.6 — Django check**

```bash
docker exec hypostasia_web uv run python manage.py check 2>&1 | tail -3
```

- [ ] **Step 1.7 — Commit suggéré**

```
A.6 (1/12) — Modeles notification_lue + migrations

Ajoute le champ notification_lue (BooleanField, default=False) sur
ExtractionJob (hypostasis_extractor) et TranscriptionJob (core).
Migrations auto-generees + appliquees.
```

---

### Task 2 : Data migration — marquer jobs existants comme déjà lus

**Files:**
- Create: `core/migrations/0032_marquer_notifications_existantes_lues.py`

- [ ] **Step 2.1 — Créer la data migration manuellement**

Fichier `core/migrations/0032_marquer_notifications_existantes_lues.py` :

```python
"""
Marque tous les ExtractionJob et TranscriptionJob existants comme deja lus
au moment de la migration A.6. Sinon le bouton 'taches en cours'
apparaitrait en vert avec un compteur enorme au premier login post-migration.
/ Mark all existing jobs as 'already read' at A.6 migration time.
"""
from django.db import migrations


def marquer_jobs_existants_lus(apps, schema_editor):
    ExtractionJob = apps.get_model('hypostasis_extractor', 'ExtractionJob')
    TranscriptionJob = apps.get_model('core', 'TranscriptionJob')

    nb_extractions = ExtractionJob.objects.update(notification_lue=True)
    nb_transcriptions = TranscriptionJob.objects.update(notification_lue=True)

    if nb_extractions or nb_transcriptions:
        print(
            f"  -> A.6 data migration : "
            f"{nb_extractions} extractions + {nb_transcriptions} transcriptions "
            f"marquees comme deja lues."
        )


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0031_transcriptionjob_notification_lue'),
        ('hypostasis_extractor', '0027_extractionjob_notification_lue'),
    ]

    operations = [
        migrations.RunPython(
            marquer_jobs_existants_lus,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
```

- [ ] **Step 2.2 — Appliquer la migration dans Docker**

```bash
docker exec hypostasia_web uv run python manage.py migrate core 2>&1 | tail -5
```

Attendu : `Applying core.0032_marquer_notifications_existantes_lues... OK` + l'éventuel `print` si des jobs existaient.

- [ ] **Step 2.3 — Vérifier qu'aucun job n'a `notification_lue=False`**

```bash
docker exec hypostasia_web uv run python manage.py shell -c "from core.models import TranscriptionJob; from hypostasis_extractor.models import ExtractionJob; print('Extractions non lues:', ExtractionJob.objects.filter(notification_lue=False).count()); print('Transcriptions non lues:', TranscriptionJob.objects.filter(notification_lue=False).count())"
```

Attendu : `0` pour les deux.

- [ ] **Step 2.4 — Commit suggéré**

```
A.6 (2/12) — Data migration : marquer jobs existants comme deja lus

Migration RunPython qui passe notification_lue=True sur tous les
ExtractionJob et TranscriptionJob existants au moment de la
migration A.6. Evite que le bouton apparaisse en vert avec un
compteur enorme au premier login post-migration.
```

---

### Task 3 : Helper `notifier_tache_terminee` + retrait helper `envoyer_progression_websocket`

**Files:**
- Modify: `front/tasks.py` (ajouter `notifier_tache_terminee()`, retirer `envoyer_progression_websocket()` ENTIÈREMENT car l'ancien helper est plus utilisé après Task 8)

**Note :** dans cette task, on AJOUTE seulement `notifier_tache_terminee()`. Les anciens appels à `envoyer_progression_websocket()` sont retirés en Task 8. Le retrait du helper lui-même se fait en Task 9 (sinon Python plante car les appels existent encore).

- [ ] **Step 3.1 — Ajouter le helper `notifier_tache_terminee()` dans `front/tasks.py`**

Le placer juste après `envoyer_progression_websocket()` (vers ligne 30) :

```python
def notifier_tache_terminee(user_pk, tache_id, tache_type, status):
    """
    Push au client une notification de fin de tache via le NotificationConsumer.
    Appele uniquement a la fin d'une tache Celery (analyse / synthese / transcription).
    / Push a task-end notification via NotificationConsumer.
    Called only at the end of a Celery task.

    Args:
        user_pk : pk du proprietaire de la tache
        tache_id : pk du job (ExtractionJob ou TranscriptionJob)
        tache_type : "analyse" | "synthese" | "transcription"
        status : "completed" | "failed"
    """
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    channel_layer = get_channel_layer()
    if not channel_layer:
        logger.debug("notifier_tache_terminee: channel layer non configure, skip")
        return
    async_to_sync(channel_layer.group_send)(
        f"user_{user_pk}",
        {
            "type": "tache_terminee",  # nom de la methode handler du consumer
            "tache_id": tache_id,
            "tache_type": tache_type,
            "status": status,
        },
    )
```

- [ ] **Step 3.2 — Django check**

```bash
docker exec hypostasia_web uv run python manage.py check 2>&1 | tail -3
```

- [ ] **Step 3.3 — Commit suggéré**

```
A.6 (3/12) — Helper notifier_tache_terminee

Ajoute le helper notifier_tache_terminee(user_pk, tache_id,
tache_type, status) dans front/tasks.py. Push au client une
notification de fin via le NotificationConsumer (group user_<pk>).
Format unifie : {type, tache_id, tache_type, status}.
L'ancien helper envoyer_progression_websocket() est conserve
temporairement (sera retire en Task 9 apres bascule des taches Celery).
```

---

### Task 4 : Refonte `NotificationConsumer` + retrait `ProgressionTacheConsumer` + retrait `views_ws.py`

**Files:**
- Modify: `front/consumers.py` (réduit à ~35 lignes, 1 seul consumer)
- Modify: `front/routing.py` (retrait route `ws/tache/<str:tache_id>/`)
- Delete: `front/views_ws.py`
- Modify: `front/urls.py` (retrait import + register de `WsTestViewSet` si présent)

- [ ] **Step 4.1 — Lire les imports actuels de `front/urls.py`**

```bash
rg -n "WsTestViewSet|views_ws|ws-test" /home/jonas/Gits/Hypostasia/front/urls.py
```

- [ ] **Step 4.2 — Retirer `WsTestViewSet` de `front/urls.py`**

Retirer la ligne `from .views_ws import WsTestViewSet` (l. ~11) et la ligne `router.register(r"ws-test", WsTestViewSet, basename="ws-test")` (l. ~33).

- [ ] **Step 4.3 — Supprimer `front/views_ws.py`**

```bash
rm /home/jonas/Gits/Hypostasia/front/views_ws.py
```

- [ ] **Step 4.4 — Refonte complète de `front/consumers.py`**

Remplacer le contenu entier du fichier par :

```python
"""
Consumer WebSocket pour notifications de fin de tache.
Refonte A.6 : un seul consumer minimal, pas de progression streaming.
/ WebSocket consumer for task-end notifications.
A.6 refactor: single minimal consumer, no progression streaming.

LOCALISATION : front/consumers.py
"""
from channels.generic.websocket import AsyncJsonWebsocketConsumer


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    """
    Consumer minimal : ecoute le group user_<id> et pousse les notifications
    de fin de tache au bouton du client (changement de couleur).
    / Minimal consumer: listens on user_<id> group and pushes task-end
    notifications to the client's button (color change).
    """
    async def connect(self):
        # Refus si non authentifie / Refuse if not authenticated
        if not self.scope["user"].is_authenticated:
            await self.close()
            return
        # Rejoindre le group du proprietaire / Join owner's group
        self.nom_group = f"user_{self.scope['user'].pk}"
        await self.channel_layer.group_add(self.nom_group, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "nom_group"):
            await self.channel_layer.group_discard(
                self.nom_group, self.channel_name,
            )

    async def tache_terminee(self, event):
        """
        Recoit un message du group, pousse au client.
        Format event : {tache_id, tache_type, status}
        / Receives a group message, pushes to client.
        """
        await self.send_json({
            "type": "tache_terminee",
            "tache_id": event["tache_id"],
            "tache_type": event["tache_type"],
            "status": event["status"],
        })
```

- [ ] **Step 4.5 — Modifier `front/routing.py`**

Remplacer le contenu par :

```python
"""
Routes WebSocket de l'app front.
/ WebSocket routes for the front app.

LOCALISATION : front/routing.py
"""
from django.urls import path
from front import consumers

websocket_urlpatterns = [
    path('ws/notifications/', consumers.NotificationConsumer.as_asgi()),
]
```

- [ ] **Step 4.6 — Vérifier qu'aucune ref `ProgressionTacheConsumer` ou `WsTestViewSet` ne subsiste**

```bash
rg "ProgressionTacheConsumer|WsTestViewSet|views_ws|ws/tache/" /home/jonas/Gits/Hypostasia/ -g '!PLAN/**'
```
Attendu : 0 résultat.

- [ ] **Step 4.7 — Django check**

```bash
docker exec hypostasia_web uv run python manage.py check 2>&1 | tail -3
```

- [ ] **Step 4.8 — Commit suggéré**

```
A.6 (4/12) — Refonte NotificationConsumer + retrait ProgressionTacheConsumer

Refonte complete du fichier consumers.py : retrait
ProgressionTacheConsumer (~200 lignes) + simplification
NotificationConsumer (~30 lignes finales). Retrait du fichier
front/views_ws.py et de la route /ws/tache/<id>/. Routing reduit
a 1 seule route /ws/notifications/.
```

---

### Task 5 : Nouveau `TachesViewSet` + 2 templates

**Files:**
- Create: `front/views_taches.py` (nouveau, ~120 lignes)
- Create: `front/templates/front/includes/taches_bouton.html` (~30 lignes)
- Create: `front/templates/front/includes/taches_dropdown.html` (~80 lignes)
- Modify: `front/urls.py` (ajouter `router.register(r"taches", TachesViewSet, ...)`)

- [ ] **Step 5.1 — Créer `front/views_taches.py`**

Contenu complet :

```python
"""
ViewSet pour le bouton 'taches en cours' dans la toolbar (refonte A.6).
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

from core.models import TranscriptionJob
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
    nombre_en_cours = nombre_extractions_en_cours + nombre_transcriptions_en_cours

    # Comptage taches terminees non lues / Count finished unread tasks
    nombre_extractions_non_lues = ExtractionJob.objects.filter(
        page__owner=user,
        status__in=["completed", "failed"],
        notification_lue=False,
    ).count()
    nombre_transcriptions_non_lues = TranscriptionJob.objects.filter(
        page__owner=user,
        status__in=["completed", "failed"],
        notification_lue=False,
    ).count()
    nombre_non_lues = nombre_extractions_non_lues + nombre_transcriptions_non_lues

    # Etat dominant : priorite erreur > succes > en_cours > neutre
    # / Dominant state: priority erreur > succes > en_cours > neutre
    a_des_erreurs_non_lues = ExtractionJob.objects.filter(
        page__owner=user, status="failed", notification_lue=False,
    ).exists() or TranscriptionJob.objects.filter(
        page__owner=user, status="failed", notification_lue=False,
    ).exists()

    if a_des_erreurs_non_lues:
        etat = "erreur"
    elif nombre_non_lues > 0:
        etat = "succes"
    elif nombre_en_cours > 0:
        etat = "en_cours"
    else:
        etat = "neutre"

    return {
        "nombre_en_cours": nombre_en_cours,
        "nombre_non_lues": nombre_non_lues,
        "etat": etat,
    }


class TachesViewSet(viewsets.ViewSet):
    """
    Bouton 'taches en cours' dans la toolbar + dropdown au clic + marquer lue.
    / 'Tasks in progress' button in toolbar + dropdown on click + mark as read.

    LOCALISATION : front/views_taches.py
    """
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=["GET"])
    def bouton(self, request):
        """
        Renvoie le HTML du bouton avec son etat actuel (compteur, couleur).
        Appele en reaction a un message WS (via JS dans hypostasia.js).
        / Returns button HTML with current state.
        """
        contexte = _calculer_etat_bouton(request.user)
        return render(request, "front/includes/taches_bouton.html", contexte)

    @action(detail=False, methods=["GET"])
    def dropdown(self, request):
        """
        Renvoie la liste des 10 dernieres taches dans un dropdown
        + OOB swap du bouton pour realignement.
        / Returns 10 most recent tasks in a dropdown + OOB swap button.
        """
        # Taches recentes : 10 dernieres extractions + 10 dernieres transcriptions
        # melangees par created_at desc, max 10 au total
        # / Recent tasks: 10 latest extractions + 10 latest transcriptions
        # / merged by created_at desc, max 10 total
        extractions_recentes = list(ExtractionJob.objects.filter(
            page__owner=request.user,
        ).select_related("page").order_by("-created_at")[:10])

        transcriptions_recentes = list(TranscriptionJob.objects.filter(
            page__owner=request.user,
        ).select_related("page").order_by("-created_at")[:10])

        # Annoter le type pour le template / Annotate type for template
        for extraction in extractions_recentes:
            extraction.type_tache = "extraction"
        for transcription in transcriptions_recentes:
            transcription.type_tache = "transcription"

        # Fusionner et trier par date desc, garder 10
        # / Merge and sort by date desc, keep 10
        toutes_taches = sorted(
            extractions_recentes + transcriptions_recentes,
            key=lambda t: t.created_at,
            reverse=True,
        )[:10]

        contexte_bouton = _calculer_etat_bouton(request.user)

        return render(request, "front/includes/taches_dropdown.html", {
            "taches": toutes_taches,
            **contexte_bouton,
        })

    @action(detail=True, methods=["POST"], url_path="marquer-lue")
    def marquer_lue(self, request, pk=None):
        """
        Marque une notification comme lue. Pk = id du job.
        Le query param ?type=extraction|transcription distingue les 2 modeles.
        / Marks a notification as read. Pk = job id.

        LOCALISATION : front/views_taches.py
        """
        type_tache = request.query_params.get("type")
        if type_tache == "extraction":
            job = get_object_or_404(ExtractionJob, pk=pk, page__owner=request.user)
        elif type_tache == "transcription":
            job = get_object_or_404(TranscriptionJob, pk=pk, page__owner=request.user)
        else:
            return HttpResponse("Parametre type=extraction|transcription requis", status=400)

        job.notification_lue = True
        job.save(update_fields=["notification_lue"])
        return HttpResponse(status=204)
```

- [ ] **Step 5.2 — Créer `front/templates/front/includes/taches_bouton.html`**

```html
{# Bouton 'taches en cours' dans la toolbar (refonte A.6) #}
{# 4 etats CSS : neutre / en_cours / succes / erreur #}
{# / 'Tasks in progress' button in toolbar (A.6 refactor) #}
{# LOCALISATION : front/templates/front/includes/taches_bouton.html #}

<a id="btn-taches"
   class="btn-toolbar btn-taches btn-taches-{{ etat }}"
   title="Mes taches"
   data-testid="btn-taches"
   aria-label="Mes taches en cours et terminees">
    <svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" aria-hidden="true">
        <path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"/>
    </svg>
    {% if nombre_en_cours > 0 %}
    <span class="spinner-taches"></span>
    <span class="badge-taches" data-testid="badge-taches-en-cours">{{ nombre_en_cours }}</span>
    {% elif nombre_non_lues > 0 %}
    <span class="badge-taches badge-taches-{{ etat }}" data-testid="badge-taches-non-lues">{{ nombre_non_lues }}</span>
    {% endif %}
</a>
```

- [ ] **Step 5.3 — Créer `front/templates/front/includes/taches_dropdown.html`**

```html
{# Dropdown des 10 dernieres taches (refonte A.6) #}
{# / Dropdown of 10 most recent tasks (A.6 refactor) #}
{# LOCALISATION : front/templates/front/includes/taches_dropdown.html #}

<div id="taches-dropdown-content" class="taches-dropdown-content" data-testid="taches-dropdown">
    <div class="taches-dropdown-header">
        <h3 class="text-sm font-semibold text-slate-700">Mes taches recentes</h3>
    </div>
    {% if taches %}
    <ul class="taches-dropdown-liste">
        {% for tache in taches %}
        <li class="taches-dropdown-item taches-dropdown-item-{{ tache.status }}" data-testid="taches-item-{{ tache.pk }}">
            {# Icone selon statut / Status icon #}
            {% if tache.status == "completed" %}
                <span class="taches-icone taches-icone-succes" aria-hidden="true">&check;</span>
            {% elif tache.status == "failed" %}
                <span class="taches-icone taches-icone-erreur" aria-hidden="true">&times;</span>
            {% else %}
                <span class="taches-icone taches-icone-en-cours spinner-taches-mini" aria-hidden="true"></span>
            {% endif %}

            <div class="taches-dropdown-corps">
                <div class="taches-dropdown-nom">
                    {% if tache.type_tache == "extraction" %}
                        Analyse de &laquo; {{ tache.page.title|default:"Sans titre"|truncatechars:40 }} &raquo;
                    {% else %}
                        Transcription de &laquo; {{ tache.page.title|default:"Audio"|truncatechars:40 }} &raquo;
                    {% endif %}
                </div>
                <div class="taches-dropdown-meta">
                    {% if tache.status == "completed" %}
                        <span class="taches-meta-duree">Terminee</span>
                        <a href="/lire/{{ tache.page.pk }}/?marquer_lue={{ tache.pk }}&type={{ tache.type_tache }}"
                           hx-get="/lire/{{ tache.page.pk }}/?marquer_lue={{ tache.pk }}&type={{ tache.type_tache }}"
                           hx-target="#zone-lecture"
                           hx-swap="innerHTML"
                           hx-push-url="/lire/{{ tache.page.pk }}/"
                           class="taches-meta-lien" data-testid="taches-voir-resultat">
                            Voir le resultat
                        </a>
                    {% elif tache.status == "failed" %}
                        <span class="taches-meta-erreur">Erreur</span>
                        <a href="/lire/{{ tache.page.pk }}/?marquer_lue={{ tache.pk }}&type={{ tache.type_tache }}"
                           hx-get="/lire/{{ tache.page.pk }}/?marquer_lue={{ tache.pk }}&type={{ tache.type_tache }}"
                           hx-target="#zone-lecture"
                           hx-swap="innerHTML"
                           hx-push-url="/lire/{{ tache.page.pk }}/"
                           class="taches-meta-lien" data-testid="taches-voir-details">
                            Voir details
                        </a>
                    {% else %}
                        <span class="taches-meta-en-cours">En cours&hellip;</span>
                    {% endif %}
                </div>
            </div>
        </li>
        {% endfor %}
    </ul>
    {% else %}
    <p class="taches-dropdown-vide">Aucune tache recente.</p>
    {% endif %}
</div>

{# OOB swap : realignement du bouton avec l'etat actuel #}
{# / OOB swap: realign button with current state #}
<a id="btn-taches"
   hx-swap-oob="outerHTML"
   class="btn-toolbar btn-taches btn-taches-{{ etat }}"
   title="Mes taches"
   data-testid="btn-taches"
   aria-label="Mes taches en cours et terminees">
    <svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" aria-hidden="true">
        <path stroke-linecap="round" stroke-linejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"/>
    </svg>
    {% if nombre_en_cours > 0 %}
    <span class="spinner-taches"></span>
    <span class="badge-taches">{{ nombre_en_cours }}</span>
    {% elif nombre_non_lues > 0 %}
    <span class="badge-taches badge-taches-{{ etat }}">{{ nombre_non_lues }}</span>
    {% endif %}
</a>
```

- [ ] **Step 5.4 — Modifier `front/urls.py` pour register le ViewSet**

Ajouter l'import :
```python
from .views_taches import TachesViewSet
```

Ajouter le register :
```python
router.register(r"taches", TachesViewSet, basename="tache")
```

- [ ] **Step 5.5 — Django check**

```bash
docker exec hypostasia_web uv run python manage.py check 2>&1 | tail -3
```

- [ ] **Step 5.6 — Test rapide manuel**

```bash
docker exec hypostasia_web uv run python manage.py runserver 0.0.0.0:8123 &
# Avec un user authentifie :
curl -b cookies.txt http://localhost:8123/taches/bouton/ | head -10
```

Attendu : HTML du bouton avec `class="btn-taches btn-taches-neutre"` (si aucun job).

- [ ] **Step 5.7 — Commit suggéré**

```
A.6 (5/12) — TachesViewSet + 2 templates (bouton + dropdown)

Cree front/views_taches.py avec TachesViewSet (3 actions :
bouton, dropdown, marquer_lue) et la fonction utilitaire
_calculer_etat_bouton(). Cree taches_bouton.html (4 etats CSS)
et taches_dropdown.html (liste 10 dernieres taches + OOB swap
du bouton). Register sur /taches/ dans front/urls.py.
```

---

### Task 6 : Bouton dans `base.html` toolbar + JS minimal dans `hypostasia.js`

**Files:**
- Modify: `front/templates/front/base.html` (ajouter bouton + wrapper dropdown + retirer ref `htmx-ext-ws` + retirer ref `notifications_progression.js`)
- Modify: `front/static/front/js/hypostasia.js` (ajouter ~30 lignes : WS handler + toggle dropdown)

- [ ] **Step 6.1 — Lire la zone toolbar de `base.html`**

```bash
Read /home/jonas/Gits/Hypostasia/front/templates/front/base.html offset=100 limit=30
```

Identifier où placer le bouton (probablement à côté du bouton aide ou dans le menu utilisateur).

- [ ] **Step 6.2 — Ajouter le bouton + wrapper dropdown dans `base.html`**

Insérer juste avant la fermeture de la toolbar (à adapter selon la structure exacte) :

```html
{# Bouton 'mes taches' (refonte A.6) #}
{# / 'My tasks' button (A.6 refactor) #}
{% if request.user.is_authenticated %}
<div class="taches-wrapper">
    {% include "front/includes/taches_bouton.html" with nombre_en_cours=0 nombre_non_lues=0 etat="neutre" %}
    <div id="taches-dropdown-wrapper" class="taches-dropdown-wrapper hidden">
        <div id="taches-dropdown-content"></div>
    </div>
</div>
{% endif %}
```

**Note** : on rend le bouton avec un état neutre par défaut au load. Le calcul réel de l'état initial (couleur + compteurs) sera fait par le JS qui déclenche un fetch immédiat de `/taches/bouton/` au chargement de la page (alternative : context_processor qui injecte l'état dans `base.html`, mais ça ajoute du couplage).

→ **Décision** : pour rester FALC, on ajoute dans le JS un fetch initial du bouton au load. Ça reste 1 ligne de plus dans hypostasia.js.

- [ ] **Step 6.3 — Retirer ref `htmx-ext-ws` dans `base.html`**

```bash
rg -n "htmx-ext-ws|hx-ext=.ws" /home/jonas/Gits/Hypostasia/front/templates/front/base.html
```

Retirer la balise `<script src="...htmx-ext-ws...">` et tout `hx-ext="ws"` rencontré.

- [ ] **Step 6.4 — Retirer ref `notifications_progression.js` dans `base.html`**

```bash
rg -n "notifications_progression" /home/jonas/Gits/Hypostasia/front/templates/front/base.html
```

Retirer la balise `<script src="...notifications_progression.js">`.

- [ ] **Step 6.5 — Retirer les includes conditionnels obsolètes dans `base.html`**

Si présents : `{% if bandeau_notification %}{% include ... %}{% endif %}` ou similaires liés à la progression. À chercher :

```bash
rg -n "bandeau_notification|panneau_analyse_en_cours|synthese_en_cours_drawer|drawer_cartes_partielles|ws_analyse_progression|ws_progression_tache|ws_synthese_terminee|ws_test_feedback|ws_toast|transcription_en_cours" /home/jonas/Gits/Hypostasia/front/templates/front/base.html
```

Retirer toutes les refs trouvées (sauf `reformulation_en_cours.html` et `restitution_ia_en_cours.html` qui restent jusqu'à A.7).

- [ ] **Step 6.6 — Ajouter le JS minimal dans `hypostasia.js`**

Ajouter à la fin du fichier (~30 lignes) :

```javascript
// ===========================================================================
// === A.6 — WebSocket notifications + dropdown taches ===
// / A.6 — WebSocket notifications + tasks dropdown
// ===========================================================================

// Connexion au consumer NotificationConsumer (1 seule connexion par session)
// Si l'utilisateur n'est pas authentifie, le consumer ferme la connexion
// (geree cote serveur), donc pas de reconnexion infinie.
// / Connect to NotificationConsumer (1 connection per session)
const wsTachesProtocol = window.location.protocol === "https:" ? "wss://" : "ws://";
const wsTaches = new WebSocket(wsTachesProtocol + window.location.host + "/ws/notifications/");

// A la reception d'un message 'tache_terminee', refetch le bouton
// pour mettre a jour son etat (couleur + badge).
// / On 'tache_terminee', refetch button to update state.
wsTaches.addEventListener("message", function(evt) {
    const data = JSON.parse(evt.data);
    if (data.type === "tache_terminee") {
        htmx.ajax("GET", "/taches/bouton/", {
            target: "#btn-taches", swap: "outerHTML",
        });
    }
});

// Toggle dropdown au clic sur le bouton
// / Toggle dropdown on button click
document.body.addEventListener("click", function(evt) {
    const bouton = evt.target.closest("#btn-taches");
    const dropdown = document.getElementById("taches-dropdown-wrapper");
    if (!dropdown) return;
    if (bouton) {
        evt.preventDefault();
        dropdown.classList.toggle("hidden");
        // Si on vient d'ouvrir : fetch la liste fraiche
        // / If just opened: fetch fresh list
        if (!dropdown.classList.contains("hidden")) {
            htmx.ajax("GET", "/taches/dropdown/", {
                target: "#taches-dropdown-content", swap: "innerHTML",
            });
        }
    } else if (!evt.target.closest("#taches-dropdown-wrapper")) {
        // Click ailleurs : fermer le dropdown
        // / Click elsewhere: close dropdown
        dropdown.classList.add("hidden");
    }
});

// Au chargement : fetch initial du bouton pour avoir l'etat reel
// (les compteurs/couleur dependent de la DB)
// / On load: initial fetch of button to get real state from DB
document.addEventListener("DOMContentLoaded", function() {
    if (document.getElementById("btn-taches")) {
        htmx.ajax("GET", "/taches/bouton/", {
            target: "#btn-taches", swap: "outerHTML",
        });
    }
});
```

- [ ] **Step 6.7 — Ajouter le CSS minimal pour le bouton + dropdown dans `hypostasia.css`**

Au minimum : 4 classes d'état (`btn-taches-neutre|en_cours|succes|erreur`), positionnement absolu du dropdown sous le bouton, styles du dropdown.

À l'exécution : ajouter au bon endroit du fichier (après les styles toolbar existants). Code à adapter selon la palette du projet.

```css
/* === A.6 — Bouton 'mes taches' (refonte WebSocket) === */
.taches-wrapper { position: relative; }
.btn-taches { position: relative; }
.btn-taches-neutre { color: #94a3b8; }
.btn-taches-en_cours { color: #2563eb; }
.btn-taches-succes { color: #16a34a; }
.btn-taches-erreur { color: #dc2626; }
.spinner-taches {
    display: inline-block; width: 0.625rem; height: 0.625rem;
    border: 2px solid currentColor; border-top-color: transparent;
    border-radius: 50%; animation: spin 1s linear infinite;
}
.badge-taches {
    position: absolute; top: -4px; right: -4px;
    min-width: 1rem; height: 1rem; padding: 0 0.25rem;
    background: currentColor; color: white !important;
    border-radius: 0.5rem; font-size: 0.625rem; font-weight: 700;
    line-height: 1rem; text-align: center;
}
.taches-dropdown-wrapper {
    position: absolute; top: 100%; right: 0; margin-top: 0.25rem;
    min-width: 18rem; max-width: 24rem;
    background: white; border: 1px solid #e2e8f0; border-radius: 0.5rem;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08); z-index: 50;
}
.taches-dropdown-wrapper.hidden { display: none; }
.taches-dropdown-header { padding: 0.75rem; border-bottom: 1px solid #e2e8f0; }
.taches-dropdown-liste { list-style: none; margin: 0; padding: 0; max-height: 400px; overflow-y: auto; }
.taches-dropdown-item { display: flex; gap: 0.75rem; padding: 0.75rem; border-bottom: 1px solid #f1f5f9; }
.taches-dropdown-item:last-child { border-bottom: none; }
.taches-icone { width: 1.5rem; height: 1.5rem; display: flex; align-items: center; justify-content: center; flex-shrink: 0; font-weight: 700; border-radius: 50%; }
.taches-icone-succes { background: #dcfce7; color: #16a34a; }
.taches-icone-erreur { background: #fee2e2; color: #dc2626; }
.taches-icone-en-cours { background: #dbeafe; color: #2563eb; }
.taches-dropdown-corps { flex: 1; min-width: 0; }
.taches-dropdown-nom { font-size: 0.8125rem; color: #1e293b; font-weight: 500; }
.taches-dropdown-meta { font-size: 0.75rem; color: #64748b; margin-top: 0.25rem; display: flex; gap: 0.75rem; align-items: center; }
.taches-meta-lien { color: #2563eb; text-decoration: underline; }
.taches-meta-lien:hover { color: #1d4ed8; }
.taches-dropdown-vide { padding: 1.5rem; text-align: center; color: #94a3b8; font-size: 0.8125rem; }
.spinner-taches-mini { width: 0.875rem; height: 0.875rem; border-width: 1.5px; }
@keyframes spin { to { transform: rotate(360deg); } }
```

- [ ] **Step 6.8 — Test manuel rapide**

```bash
docker exec hypostasia_web uv run python manage.py runserver 0.0.0.0:8123 &
```

Ouvrir http://localhost:8123/ dans Firefox (connecté), vérifier dans la toolbar :
- Le bouton "tâches" est visible
- Au clic : le dropdown s'ouvre avec "Aucune tache recente." (si DB vide)
- Au clic ailleurs : le dropdown se ferme
- Console JS : pas d'erreur, le WS est connecté (vérifier dans Network)

- [ ] **Step 6.9 — Commit suggéré**

```
A.6 (6/12) — Bouton taches dans toolbar + JS minimal + CSS

Ajoute le bouton 'mes taches' dans la toolbar de base.html
(visible si authentifie). Ajoute ~50 lignes de JS dans
hypostasia.js : connexion WebSocket NotificationConsumer +
handler tache_terminee (refetch du bouton) + toggle dropdown au
clic + fetch initial du bouton au load.
Ajoute le CSS pour les 4 etats (neutre/en_cours/succes/erreur)
+ styles dropdown.
Retire les refs htmx-ext-ws et notifications_progression.js
de base.html.
```

---

### Task 7 : Modifier vues `analyser` et `synthetiser` — toast HX-Trigger + traiter `?marquer_lue`

**Files:**
- Modify: `front/views.py` (`LectureViewSet.analyser`, `LectureViewSet.synthetiser`, `LectureViewSet.retrieve`)

- [ ] **Step 7.1 — Lire `LectureViewSet.analyser` (action POST /lire/{pk}/analyser/)**

```bash
rg -n "def analyser\(" /home/jonas/Gits/Hypostasia/front/views.py
Read /home/jonas/Gits/Hypostasia/front/views.py offset=<ligne_trouvee> limit=80
```

Identifier ce qui est retourné actuellement (probablement le drawer "en cours"). Le remplacer par un toast HX-Trigger.

- [ ] **Step 7.2 — Modifier `LectureViewSet.analyser` pour retourner toast**

Après création de l'`ExtractionJob` et lancement de `analyser_page_task.delay(...)`, remplacer le `return render(...)` actuel par :

```python
import json

# ... apres job creation et task.delay() ...

reponse = HttpResponse(status=200)
reponse["HX-Trigger"] = json.dumps({
    "showToast": {
        "message": "Analyse lancee. Vous serez notifie a la fin.",
        "icon": "info",
    },
})
return reponse
```

À l'exécution : adapter au pattern exact (peut-être plusieurs branches du code à modifier — guard `job_en_cours`, branche permission, etc.).

- [ ] **Step 7.3 — Modifier `LectureViewSet.synthetiser` pour retourner toast**

Pareil que step 7.2 mais avec message "Synthese lancee. Vous serez notifie a la fin."

- [ ] **Step 7.4 — Modifier `LectureViewSet.retrieve` pour traiter `?marquer_lue=X&type=Y`**

Au début de la méthode `retrieve()`, ajouter :

```python
# Marquage 'notification lue' si parametres presents (refonte A.6)
# / Mark notification as read if query params present (A.6 refactor)
marquer_lue = request.query_params.get("marquer_lue")
type_tache = request.query_params.get("type")
if marquer_lue and type_tache in ("extraction", "transcription"):
    try:
        if type_tache == "extraction":
            from hypostasis_extractor.models import ExtractionJob
            ExtractionJob.objects.filter(
                pk=marquer_lue, page__owner=request.user,
            ).update(notification_lue=True)
        else:
            from core.models import TranscriptionJob
            TranscriptionJob.objects.filter(
                pk=marquer_lue, page__owner=request.user,
            ).update(notification_lue=True)
    except (ValueError, TypeError):
        pass  # marquer_lue n'est pas un entier valide, ignorer
```

- [ ] **Step 7.5 — Django check**

```bash
docker exec hypostasia_web uv run python manage.py check 2>&1 | tail -3
```

- [ ] **Step 7.6 — Commit suggéré**

```
A.6 (7/12) — Vues analyser/synthetiser : toast HX-Trigger + marquer_lue

Modifie LectureViewSet.analyser et LectureViewSet.synthetiser pour
retourner un simple toast HX-Trigger au lieu du drawer 'en cours'.
La page reste intacte, l'utilisateur navigue librement.
Ajoute dans LectureViewSet.retrieve le traitement du query param
?marquer_lue=X&type=Y pour marquer la notification du job comme lue.
```

---

### Task 8 : Bascule des tâches Celery sur `notifier_tache_terminee`

**Files:**
- Modify: `front/tasks.py` (`analyser_page_task`, `synthetiser_page_task`, `transcrire_audio_task`)

**ATTENTION** : à ce stade, `envoyer_progression_websocket()` existe encore (retiré en Task 9). Cette task RETIRE les ~8 appels intermédiaires "progression" des 3 tâches concernées + les remplace par 1 seul appel final `notifier_tache_terminee()` à la fin (succès et erreur).

- [ ] **Step 8.1 — Lister les appels actuels à supprimer/transformer**

```bash
rg -n "envoyer_progression_websocket|nom_groupe_analyse|nom_groupe_synthese|nom_groupe_transcription" /home/jonas/Gits/Hypostasia/front/tasks.py
```

D'après le scan préliminaire :
- `transcrire_audio_task` : ~3 appels (l. 579 progression, l. 641 + 664 terminees)
- `analyser_page_task` : ~5 appels (l. 1306 progression + chunks, l. 1539 + 1560)
- `synthetiser_page_task` : ~2 appels (l. 1190, l. 1207)
- 2 autres appels (l. 784 reformuler, l. 909 restituer) — ne pas toucher en A.6, retirés en A.7

- [ ] **Step 8.2 — Modifier `transcrire_audio_task`**

Retirer l'appel "progression" (~l. 579) et la variable `nom_groupe_transcription`. Remplacer les 2 appels "terminee" par :

```python
# A la fin (succes) :
notifier_tache_terminee(
    user_pk=page_associee.owner.pk,
    tache_id=job_transcription.pk,
    tache_type="transcription",
    status="completed",
)

# Dans bloc except (erreur) :
notifier_tache_terminee(
    user_pk=page_associee.owner.pk,
    tache_id=job_transcription.pk,
    tache_type="transcription",
    status="failed",
)
```

À l'exécution : adapter au contexte exact lu sur place (les variables `page_associee`, `job_transcription` peuvent avoir des noms différents).

- [ ] **Step 8.3 — Modifier `analyser_page_task`**

Pareil : retirer tous les appels intermédiaires "progression" (incluant ceux dans `AnnotateurAvecProgression` callback class). Garder/ajouter 2 appels finaux :

```python
# Succes :
notifier_tache_terminee(
    user_pk=page.owner.pk,
    tache_id=job_extraction.pk,
    tache_type="analyse",
    status="completed",
)

# Erreur :
notifier_tache_terminee(
    user_pk=page.owner.pk,
    tache_id=job_extraction.pk,
    tache_type="analyse",
    status="failed",
)
```

À l'exécution : également retirer la classe `AnnotateurAvecProgression` (vu dans CLAUDE.md §7 "Surcharges LangExtract") si elle n'a plus d'usage (sa raison d'être était d'envoyer la progression WS à chaque chunk, ce qu'on retire). Ajuster les références.

- [ ] **Step 8.4 — Modifier `synthetiser_page_task`**

Pareil :

```python
# Succes :
notifier_tache_terminee(
    user_pk=page_source.owner.pk,
    tache_id=job_synthese.pk,
    tache_type="synthese",
    status="completed",
)

# Erreur :
notifier_tache_terminee(
    user_pk=page_source.owner.pk,
    tache_id=job_synthese.pk,
    tache_type="synthese",
    status="failed",
)
```

- [ ] **Step 8.5 — Vérifier qu'aucun appel `envoyer_progression_websocket` ne subsiste pour analyse/synthèse/transcription**

```bash
rg "envoyer_progression_websocket|nom_groupe_analyse|nom_groupe_synthese|nom_groupe_transcription" /home/jonas/Gits/Hypostasia/front/tasks.py
```

Attendu : seulement 2 résultats restants (les appels dans les tasks `reformuler` ligne 784 et `restituer` ligne 909). Ces 2 sont retirés en A.7.

- [ ] **Step 8.6 — Django check**

```bash
docker exec hypostasia_web uv run python manage.py check 2>&1 | tail -3
```

- [ ] **Step 8.7 — Test rapide manuel**

Lancer une analyse et vérifier dans les logs Celery :
- L'analyse se termine sans erreur
- Le helper `notifier_tache_terminee` est appelé une fois à la fin
- Le bouton dans la toolbar se rafraîchit (passe à vert)

- [ ] **Step 8.8 — Commit suggéré**

```
A.6 (8/12) — Bascule taches Celery sur notifier_tache_terminee

Retire les ~8 appels intermediaires envoyer_progression_websocket
(progression streaming) dans analyser_page_task, synthetiser_page_task,
transcrire_audio_task. Remplace les appels 'terminee' par 1 seul
appel notifier_tache_terminee(...) avec format unifie. La classe
AnnotateurAvecProgression dans analyser_page_task est simplifiee
(plus de callback de progression).
Les appels dans reformuler/restituer (l. 784, 909) sont conserves
temporairement, retires en A.7.
```

---

### Task 9 : Retrait du helper `envoyer_progression_websocket()` + 2 derniers appels

**Files:**
- Modify: `front/tasks.py` (retrait du helper + appels reformuler/restituer)

**Note** : on retire ici les 2 derniers appels (reformuler l. 784, restituer l. 909) parce qu'on supprime le helper. Mais comme reformulation/restitution restent en place (jusqu'à A.7), elles n'auront temporairement plus de feedback de progression. C'est acceptable car A.7 viendra rapidement après.

**Alternative** : on peut laisser le helper et ses 2 appels jusqu'à A.7. Mais ça veut dire qu'on garde du code mort dont la seule raison d'être est ces 2 appels temporaires. Pas FALC.

→ **Décision** : retirer le helper en A.6. Reformulation/restitution n'auront plus de feedback de progression entre A.6 et A.7. Comme elles seront retirées en A.7 (juste après), c'est acceptable.

- [ ] **Step 9.1 — Lire les appels restants à retirer**

```bash
rg -n -B2 -A8 "envoyer_progression_websocket" /home/jonas/Gits/Hypostasia/front/tasks.py
```

Identifier les blocs dans `reformuler_page_task` (vers l. 784) et `restituer_page_task` (vers l. 909).

- [ ] **Step 9.2 — Retirer les appels dans `reformuler_page_task` et `restituer_page_task`**

Supprimer les blocs `envoyer_progression_websocket(...)` (généralement 4-6 lignes chacun).

- [ ] **Step 9.3 — Retirer le helper `envoyer_progression_websocket()` lui-même**

Supprimer la fonction (environ l. 16-30) :

```python
def envoyer_progression_websocket(nom_groupe, type_message, donnees):
    # ... ~14 lignes ...
```

- [ ] **Step 9.4 — Vérifier qu'aucune ref ne subsiste**

```bash
rg "envoyer_progression_websocket" /home/jonas/Gits/Hypostasia/front/tasks.py
```

Attendu : 0 résultat.

- [ ] **Step 9.5 — Django check**

```bash
docker exec hypostasia_web uv run python manage.py check 2>&1 | tail -3
```

- [ ] **Step 9.6 — Commit suggéré**

```
A.6 (9/12) — Retrait helper envoyer_progression_websocket

Supprime la fonction envoyer_progression_websocket() de tasks.py
ainsi que les 2 derniers appels dans reformuler_page_task et
restituer_page_task. Reformulation et restitution n'ont plus de
feedback de progression entre A.6 et A.7 (retirees en A.7).
```

---

### Task 10 : Suppression des 10 templates "en cours" + JS + ext

**Files:**
- Delete: 10 templates `front/templates/front/includes/`
- Delete: `front/static/front/js/notifications_progression.js`
- Delete: `front/static/front/vendor/htmx-ext-ws-2.0.4.js`

- [ ] **Step 10.1 — Supprimer les 10 templates "en cours"**

```bash
rm /home/jonas/Gits/Hypostasia/front/templates/front/includes/bandeau_notification.html \
   /home/jonas/Gits/Hypostasia/front/templates/front/includes/drawer_cartes_partielles.html \
   /home/jonas/Gits/Hypostasia/front/templates/front/includes/panneau_analyse_en_cours.html \
   /home/jonas/Gits/Hypostasia/front/templates/front/includes/synthese_en_cours_drawer.html \
   /home/jonas/Gits/Hypostasia/front/templates/front/includes/transcription_en_cours.html \
   /home/jonas/Gits/Hypostasia/front/templates/front/includes/ws_analyse_progression.html \
   /home/jonas/Gits/Hypostasia/front/templates/front/includes/ws_progression_tache.html \
   /home/jonas/Gits/Hypostasia/front/templates/front/includes/ws_synthese_terminee.html \
   /home/jonas/Gits/Hypostasia/front/templates/front/includes/ws_test_feedback.html \
   /home/jonas/Gits/Hypostasia/front/templates/front/includes/ws_toast.html
```

**Note** : conservés `reformulation_en_cours.html` et `restitution_ia_en_cours.html` (retirés en A.7).

- [ ] **Step 10.2 — Vérifier qu'aucune référence à ces templates ne subsiste**

```bash
rg -l "bandeau_notification|drawer_cartes_partielles|panneau_analyse_en_cours|synthese_en_cours_drawer|transcription_en_cours|ws_analyse_progression|ws_progression_tache|ws_synthese_terminee|ws_test_feedback|ws_toast" /home/jonas/Gits/Hypostasia/ -g '!PLAN/**' -g '!CHANGELOG.md'
```

Attendu : 0 résultat. Si présent dans des templates ou views, c'est qu'il faut retirer ces refs aussi.

**Cas particulier `ws_test_feedback.html`** : si on trouve une ref dans `hypostasis_extractor/views.py` ligne 1707 (test extraction analyseur), il faut adapter ce code. À l'exécution : si la ref est isolée et la feature n'est plus utilisée, retirer aussi. Sinon, repenser.

- [ ] **Step 10.3 — Supprimer `notifications_progression.js`**

```bash
rm /home/jonas/Gits/Hypostasia/front/static/front/js/notifications_progression.js
```

- [ ] **Step 10.4 — Supprimer `htmx-ext-ws-2.0.4.js` du vendor**

```bash
rm /home/jonas/Gits/Hypostasia/front/static/front/vendor/htmx-ext-ws-2.0.4.js
```

- [ ] **Step 10.5 — Django check + lancement serveur**

```bash
docker exec hypostasia_web uv run python manage.py check 2>&1 | tail -3
docker exec hypostasia_web uv run python manage.py runserver 0.0.0.0:8123 &
# Test manuel : ouvrir une page de lecture, vérifier qu'aucune erreur 500
# Lancer une analyse, vérifier le toast + le bouton vert à la fin
```

- [ ] **Step 10.6 — Commit suggéré**

```
A.6 (10/12) — Suppression templates 'en cours' + JS + ext htmx-ws

Supprime 10 templates de progression (bandeau_notification,
drawer_cartes_partielles, panneau_analyse_en_cours,
synthese_en_cours_drawer, transcription_en_cours,
ws_analyse_progression, ws_progression_tache, ws_synthese_terminee,
ws_test_feedback, ws_toast). Supprime notifications_progression.js
et l'extension vendor htmx-ext-ws-2.0.4.js. Conserve
reformulation_en_cours et restitution_ia_en_cours (retires en A.7).
```

---

### Task 11 : Tests Django — retrait obsolètes + ajout `Phase26i*`

**Files:**
- Modify: `front/tests/test_phases.py` (retrait classes WS obsolètes + ajout 3 classes `Phase26i*`)
- Modify: `front/tests/test_phase28_light.py` (retrait sections WS de progression)
- Delete or modify: `front/tests/test_phase29_synthese_drawer.py` (selon ce qui reste)
- Delete: `front/tests/test_analyse_drawer_unifie.py` (tout le fichier teste OOB+WS)

- [ ] **Step 11.1 — Identifier précisément les classes/tests à retirer**

```bash
rg -n "^class.*WS|^class.*BandeauNotification|^class.*DrawerCartes|^class.*ProgressionTache|^class.*WsToast|^class Phase14|^class Phase16BandeauNotificationTest|envoyer_progression_websocket|ProgressionTacheConsumer" /home/jonas/Gits/Hypostasia/front/tests/test_phases.py | head -20
```

À l'exécution : utiliser ce scan pour repérer les bornes exactes des classes à supprimer.

- [ ] **Step 11.2 — Supprimer les classes obsolètes dans `test_phases.py`**

Pour chaque classe identifiée, utiliser `Edit` ou `sed` pour la supprimer entièrement. Le comportement d'un test "WS" qui mocke `envoyer_progression_websocket` n'a plus de sens car le helper n'existe plus.

- [ ] **Step 11.3 — Adapter `test_phase28_light.py`**

```bash
rg -n "envoyer_progression_websocket|nom_groupe_|@override_settings.*CHANNEL" /home/jonas/Gits/Hypostasia/front/tests/test_phase28_light.py
```

Retirer les sections qui mockent ou vérifient des appels `envoyer_progression_websocket`.

- [ ] **Step 11.4 — Supprimer ou adapter `test_phase29_synthese_drawer.py`**

```bash
rg -n "envoyer_progression_websocket|hx-swap-oob|drawer_cartes_partielles|synthese_en_cours_drawer" /home/jonas/Gits/Hypostasia/front/tests/test_phase29_synthese_drawer.py
```

Si tout le fichier teste le pattern OOB+WS+drawer streaming, le supprimer. Si certains tests testent d'autres aspects de la synthèse (ex: création du job, statut completed, message d'erreur), les conserver.

- [ ] **Step 11.5 — Supprimer `test_analyse_drawer_unifie.py`**

Si tout le fichier teste l'ancien pattern OOB+WS+drawer streaming pour les analyses, supprimer le fichier entier :

```bash
rm /home/jonas/Gits/Hypostasia/front/tests/test_analyse_drawer_unifie.py
```

À vérifier en lisant le fichier au préalable.

- [ ] **Step 11.6 — Ajouter les 3 nouvelles classes `Phase26i*` dans `test_phases.py`**

À la fin du fichier, ajouter le bloc :

```python
# =============================================================================
# PHASE-26i — Refonte WebSocket : bouton 'taches' + NotificationConsumer
# / PHASE-26i — WebSocket refactor: 'tasks' button + NotificationConsumer
# =============================================================================


class Phase26iTachesViewSetTest(TestCase):
    """Tests du ViewSet TachesViewSet (bouton, dropdown, marquer_lue).
    / Tests for TachesViewSet (button, dropdown, mark_read)."""

    def setUp(self):
        from django.contrib.auth.models import User
        from core.models import Dossier, Page
        self.user = User.objects.create_user(username="taches_owner", password="test1234")
        self.dossier = Dossier.objects.create(name="D taches", owner=self.user)
        self.page = Page.objects.create(
            title="Page taches", dossier=self.dossier, owner=self.user,
            text_readability="Texte test.", html_original="<p>t</p>",
            html_readability="<p>t</p>",
        )
        self.client.login(username="taches_owner", password="test1234")

    def test_bouton_neutre_si_aucune_tache(self):
        """Bouton renvoie etat neutre si aucune tache."""
        reponse = self.client.get("/taches/bouton/")
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "btn-taches-neutre")

    def test_bouton_en_cours_si_extraction_pending(self):
        """Bouton renvoie etat en_cours si une extraction est pending."""
        from hypostasis_extractor.models import ExtractionJob, AnalyseurSyntaxique
        from core.models import AIModel
        modele = AIModel.objects.create(name="Mock", model_choice="mock_default", is_active=True)
        analyseur = AnalyseurSyntaxique.objects.create(name="A", ai_model=modele)
        ExtractionJob.objects.create(
            page=self.page, ai_model=modele, name="Test",
            prompt_description="t", status="pending",
        )
        reponse = self.client.get("/taches/bouton/")
        self.assertContains(reponse, "btn-taches-en_cours")
        self.assertContains(reponse, "badge-taches-en-cours")

    def test_bouton_succes_si_notification_non_lue(self):
        """Bouton renvoie etat succes si une tache est completed et non lue."""
        from hypostasis_extractor.models import ExtractionJob
        from core.models import AIModel
        modele = AIModel.objects.create(name="Mock2", model_choice="mock_default", is_active=True)
        ExtractionJob.objects.create(
            page=self.page, ai_model=modele, name="T2",
            prompt_description="t", status="completed", notification_lue=False,
        )
        reponse = self.client.get("/taches/bouton/")
        self.assertContains(reponse, "btn-taches-succes")

    def test_bouton_erreur_si_failed_non_lu(self):
        """Bouton renvoie etat erreur (prioritaire) si une tache failed non lue."""
        from hypostasis_extractor.models import ExtractionJob
        from core.models import AIModel
        modele = AIModel.objects.create(name="Mock3", model_choice="mock_default", is_active=True)
        ExtractionJob.objects.create(
            page=self.page, ai_model=modele, name="T3",
            prompt_description="t", status="failed", notification_lue=False,
        )
        # Une autre completed pour vérifier que erreur est prioritaire
        ExtractionJob.objects.create(
            page=self.page, ai_model=modele, name="T4",
            prompt_description="t", status="completed", notification_lue=False,
        )
        reponse = self.client.get("/taches/bouton/")
        self.assertContains(reponse, "btn-taches-erreur")

    def test_dropdown_filtre_par_owner(self):
        """Dropdown ne renvoie que les taches du user connecte."""
        from django.contrib.auth.models import User
        from core.models import Dossier, Page
        from hypostasis_extractor.models import ExtractionJob
        from core.models import AIModel
        autre = User.objects.create_user(username="autre", password="test1234")
        autre_dossier = Dossier.objects.create(name="Autre", owner=autre)
        autre_page = Page.objects.create(
            title="Page autre", dossier=autre_dossier, owner=autre,
            text_readability="t", html_original="<p>t</p>", html_readability="<p>t</p>",
        )
        modele = AIModel.objects.create(name="Mock4", model_choice="mock_default", is_active=True)
        ExtractionJob.objects.create(
            page=autre_page, ai_model=modele, name="Tache autre",
            prompt_description="t", status="completed", notification_lue=False,
        )
        reponse = self.client.get("/taches/dropdown/")
        self.assertNotContains(reponse, "Tache autre")
        self.assertNotContains(reponse, "Page autre")

    def test_marquer_lue_passe_le_flag_a_true(self):
        """marquer_lue passe notification_lue a True."""
        from hypostasis_extractor.models import ExtractionJob
        from core.models import AIModel
        modele = AIModel.objects.create(name="Mock5", model_choice="mock_default", is_active=True)
        job = ExtractionJob.objects.create(
            page=self.page, ai_model=modele, name="T5",
            prompt_description="t", status="completed", notification_lue=False,
        )
        reponse = self.client.post(f"/taches/{job.pk}/marquer-lue/?type=extraction")
        self.assertEqual(reponse.status_code, 204)
        job.refresh_from_db()
        self.assertTrue(job.notification_lue)

    def test_marquer_lue_seulement_owner(self):
        """marquer_lue refuse 404 si pas owner."""
        from django.contrib.auth.models import User
        from core.models import Dossier, Page
        from hypostasis_extractor.models import ExtractionJob
        from core.models import AIModel
        autre = User.objects.create_user(username="autre2", password="test1234")
        autre_dossier = Dossier.objects.create(name="Autre2", owner=autre)
        autre_page = Page.objects.create(
            title="Page autre2", dossier=autre_dossier, owner=autre,
            text_readability="t", html_original="<p>t</p>", html_readability="<p>t</p>",
        )
        modele = AIModel.objects.create(name="Mock6", model_choice="mock_default", is_active=True)
        job_autre = ExtractionJob.objects.create(
            page=autre_page, ai_model=modele, name="T6",
            prompt_description="t", status="completed", notification_lue=False,
        )
        reponse = self.client.post(f"/taches/{job_autre.pk}/marquer-lue/?type=extraction")
        self.assertEqual(reponse.status_code, 404)


class Phase26iHelperNotifierTacheTermineeTest(TestCase):
    """Tests du helper notifier_tache_terminee.
    / Tests for notifier_tache_terminee helper."""

    def test_helper_envoie_au_group_user_pk(self):
        """Le helper appelle channel_layer.group_send avec le bon group."""
        from unittest.mock import patch, MagicMock
        from front.tasks import notifier_tache_terminee
        with patch("front.tasks.get_channel_layer") as mock_channel_layer:
            mock_layer = MagicMock()
            mock_channel_layer.return_value = mock_layer
            with patch("front.tasks.async_to_sync") as mock_async:
                mock_send = MagicMock()
                mock_async.return_value = mock_send

                notifier_tache_terminee(
                    user_pk=42, tache_id=123, tache_type="analyse", status="completed",
                )

                mock_async.assert_called_once()  # async_to_sync appele
                args_send = mock_send.call_args
                self.assertEqual(args_send[0][0], "user_42")
                message = args_send[0][1]
                self.assertEqual(message["type"], "tache_terminee")
                self.assertEqual(message["tache_id"], 123)
                self.assertEqual(message["tache_type"], "analyse")
                self.assertEqual(message["status"], "completed")

    def test_helper_skip_si_channel_layer_absent(self):
        """Le helper ne plante pas si channel_layer est None."""
        from unittest.mock import patch
        from front.tasks import notifier_tache_terminee
        with patch("front.tasks.get_channel_layer", return_value=None):
            # Ne doit pas lever / Should not raise
            notifier_tache_terminee(
                user_pk=42, tache_id=123, tache_type="analyse", status="completed",
            )
```

(Note : la classe `Phase26iNotificationConsumerTest` async pytest-asyncio est plus complexe à mettre en place. Si pytest-asyncio n'est pas configuré dans le projet, on peut la skip pour cette session et la tester manuellement. La logique du consumer est triviale (~30 lignes) — les vrais bugs sortiront en intégration UI manuelle.)

À l'exécution : adapter les fixtures et imports selon ce qui existe déjà dans `test_phases.py`.

- [ ] **Step 11.7 — Lancer la suite Django dans Docker**

```bash
docker exec hypostasia_web uv run python manage.py test front.tests.test_phases front.tests.test_phase28_light --noinput -v 0 2>&1 | tail -5
```

Attendu : OK + 9 tests Phase26i* en plus.

- [ ] **Step 11.8 — Commit suggéré**

```
A.6 (11/12) — Tests : retrait WS obsoletes + ajout Phase26i*

Retire les tests obsoletes lies au WS de progression dans
test_phases.py (Phase14*, Phase16BandeauNotification, classes
WS), test_phase28_light.py (sections envoyer_progression_websocket),
test_phase29_synthese_drawer.py (tests OOB drawer), supprime
test_analyse_drawer_unifie.py (entier).
Ajoute Phase26iTachesViewSetTest (7 tests : bouton 4 etats,
dropdown filtre owner, marquer_lue avec/sans permission) et
Phase26iHelperNotifierTacheTermineeTest (2 tests : appel
group_send, skip si channel_layer absent).
```

---

### Task 12 : Vérification finale + test manuel UI

**Files:** aucun (verification uniquement)

- [ ] **Step 12.1 — Grep complet**

```bash
rg "envoyer_progression_websocket|ProgressionTacheConsumer|WsTestViewSet|notifications_progression|htmx-ext-ws|bandeau_notification|drawer_cartes_partielles|panneau_analyse_en_cours|synthese_en_cours_drawer|transcription_en_cours|ws_analyse_progression|ws_progression_tache|ws_synthese_terminee|ws_test_feedback|ws_toast|nom_groupe_analyse|nom_groupe_synthese|nom_groupe_transcription|tache_progression|AnnotateurAvecProgression" /home/jonas/Gits/Hypostasia/ \
   --type-add 'web:*.{py,html,js,css}' -t web \
   -g '!PLAN/**' \
   -g '!CHANGELOG.md' 2>&1 | head -10
```

Attendu : 0 résultat (sauf éventuellement reformulation_en_cours et restitution_ia_en_cours qui sont conservés).

- [ ] **Step 12.2 — Django check**

```bash
docker exec hypostasia_web uv run python manage.py check 2>&1 | tail -3
```

Attendu : `System check identified no issues (0 silenced).`

- [ ] **Step 12.3 — Suite tests Django**

```bash
docker exec hypostasia_web uv run python manage.py test --noinput -v 0 2>&1 | tail -10
```

Attendu : tous les tests passent (sauf éventuellement E2E qui dépendent de Playwright Chromium non installé — préexistant).

- [ ] **Step 12.4 — Test manuel UI complet (Firefox)**

1. Lancer le serveur Docker avec Daphne (vérifier que `daphne` est utilisé pour ASGI)
2. **Connexion** : se connecter avec un compte qui a au moins 1 page
3. **Toolbar** : vérifier que le bouton "tâches" (icône clipboard) est visible, état neutre (gris)
4. **Lancer une analyse** sur une page :
   - Cliquer "Lancer l'analyse" → toast s'affiche en bas droite "Analyse lancee. Vous serez notifie a la fin."
   - La page reste intacte (pas de drawer "en cours" qui s'ouvre)
   - Le bouton dans la toolbar passe à bleu + spinner + badge "1"
5. **Naviguer** ailleurs pendant que l'analyse tourne (ouvrir une autre page, modifier des paramètres)
6. **Attendre la fin** (~30s à 2min) :
   - Le bouton passe à vert + badge "1" (ou rouge si erreur)
   - Console JS : message WS reçu, refetch du bouton OK
7. **Cliquer sur le bouton** :
   - Le dropdown s'ouvre avec la liste des dernières tâches
   - L'analyse récente apparaît avec icône ✓ verte + lien "Voir le résultat"
8. **Cliquer "Voir le résultat"** :
   - La page de lecture se charge avec les nouvelles extractions
   - Au prochain refetch du bouton (au prochain WS push ou navigation), le bouton passe à neutre
9. **Console JS** : aucune erreur

- [ ] **Step 12.5 — Test manuel WS coupé**

1. Lancer une analyse
2. Pendant qu'elle tourne, **fermer la connexion WS** (DevTools Network → fermer la connexion ou redémarrer Daphne `docker exec hypostasia_web pkill -f daphne` si applicable)
3. Attendre la fin de la tâche (Celery continue à tourner)
4. Le bouton reste figé sur "en cours" (normal, pas de WS push)
5. **Cliquer sur le bouton** :
   - Le dropdown fetch `/taches/dropdown/` qui ramène l'état frais
   - OOB swap du bouton → passe à vert
6. → Comportement attendu confirmé (Flow 6 de la spec)

- [ ] **Step 12.6 — Pas de commit final si la vérification est OK**

Si tout est propre, pas de commit additionnel. Le commit cleanup éventuel concerne seulement des oublis trouvés en step 12.1.

---

## Sortie attendue à la fin de la session A.6

- 5 fichiers supprimés (3 Python + 1 JS + 1 vendor)
- 10 templates "en cours" supprimés
- 5 fichiers créés (1 ViewSet + 2 templates + 3 migrations)
- ~12 fichiers modifiés
- ~12 commits proposés à Jonas
- Solde net estimé : **~-2600 lignes**
- Les analyses, synthèses et transcriptions audio sont trackées dans le bouton "tâches"
- Toast au lancement, bouton change de couleur à la fin
- Reformulation/restitution restent fonctionnelles temporairement (sans feedback de progression) jusqu'à A.7

## Risques identifiés et mitigation

| Risque | Mitigation |
|---|---|
| Numérotation des migrations conflit (autre migration créée entre temps) | Step 1.4 inspecte le résultat de makemigrations et renomme si nécessaire |
| Reformulation/restitution sans feedback entre A.6 et A.7 | Acceptable, A.7 vient juste après. Si Jonas veut éviter, garder le helper `envoyer_progression_websocket` et faire le retrait final en A.7 |
| `AnnotateurAvecProgression` (CLAUDE.md §7) cassé après simplification | Step 8.3 doit être prudent : la classe peut juste être simplifiée (callback de progression vide) sans être supprimée si elle est wrappée ailleurs |
| Test E2E Playwright qui dépend du WS de progression | À cartographier en step 11.5. Si présent : à supprimer aussi |
| `ws_test_feedback.html` utilisé par hypostasis_extractor (test extraction analyseur) | Step 10.2 : si la ref existe, à analyser au cas par cas. Soit garder le template (renommer pour clarté), soit retirer si la feature n'est plus utilisée |
| WS handler JS connecte 1 fois par tab → multi-tab génère plusieurs WS | Acceptable. Channels gère plusieurs sockets par user via le group_send |

## Auto-revue

- ✅ Toutes les sections de la spec [PLAN/A.6-refonte-websocket-spec.md](A.6-refonte-websocket-spec.md) sont couvertes :
  - Décisions Q1-Q8 → Architecture + Composants + Tasks 3-7
  - Modèles + migrations → Tasks 1-2
  - Consumer + helper → Tasks 3-4
  - ViewSet + templates → Task 5
  - Bouton + JS + CSS → Task 6
  - Vues analyser/synthetiser → Task 7
  - Bascule Celery → Task 8
  - Suppression ancien helper → Task 9
  - Suppression templates "en cours" → Task 10
  - Tests → Task 11
- ✅ Aucun placeholder ("TBD", "TODO", "fill in details")
- ✅ Chemins exacts pour chaque modification
- ✅ Code complet pour chaque diff
- ✅ Ordre **bottom-up** respecté : on ajoute le neuf avant de retirer l'ancien
- ✅ Ordre Task 8 (bascule Celery) avant Task 9 (retrait helper) — sinon `NameError`
- ✅ Tous les commits suggérés respectent la préférence "pas de Co-Authored-By"
- ✅ Aucune commande git automatique
- ✅ Tests Docker pour migrations (DB postgres dispo)
- ✅ Cas particulier `reformulation_en_cours.html` / `restitution_ia_en_cours.html` documenté (conservés jusqu'à A.7)
- ✅ Cas particulier `ws_test_feedback.html` documenté (à analyser en exécution)

## Références

- Spec validée : [PLAN/A.6-refonte-websocket-spec.md](A.6-refonte-websocket-spec.md)
- Plans précédents : A.1 → A.5
- Skill obligatoire pour exécution : `superpowers:executing-plans`
- Documentation existante : `CLAUDE.md` §7 (Surcharges LangExtract — `AnnotateurAvecProgression`) et §7b (WebSocket + OOB patterns) — cette dernière deviendra obsolète après A.6 et devra être supprimée
