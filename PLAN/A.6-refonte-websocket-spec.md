# Spec A.6 — Refonte WebSocket + bouton "tâches en cours"

**Date** : 2026-05-01 (session brainstorming après A.5)
**Auteur** : Jonas Turbeaux + brainstorming Claude Code via skill `superpowers:brainstorming`
**Statut** : design validé, prêt pour `writing-plans`

> **Note** : ce document est une **spec** (design produit). Le **plan d'implémentation détaillé** sera écrit ensuite dans `PLAN/A.6-refonte-websocket-plan.md` via la skill `superpowers:writing-plans`.

---

## Contexte

L'infrastructure WebSocket actuelle (Channels + Daphne + Redis + 2 consumers + 11 appels `envoyer_progression_websocket()` + 10 templates "en cours" + JS dédié + extension `htmx-ext-ws` + patterns OOB en cascade dans 6+ templates) est devenue trop complexe pour la valeur qu'elle apporte. La doc `CLAUDE.md` §7b documente déjà 3 catégories de pièges (MutationObserver vs OOB, deux zones OOB qui se battent, template différent pendant/après).

L'objectif est une **refonte radicale FALC** :
- Supprimer toute la couche "progression streaming" (drawer cartes au fil de l'eau, barre de progression chunks, OOB swaps en cascade)
- Conserver uniquement un système de **notification de fin de tâche** ultra-simple
- Remplacer par un **bouton "tâches en cours"** dans la toolbar avec dropdown au clic

### Brief utilisateur

> *« Je souhaite simplifier à fond toute la gestion des websocket, des notifications lors du lancement des analyses et des synthèses. Je trouve que les process avec HTMX OOB et compagnie ne donnent pas le résultat espéré. Je te propose qqch : on débranche le websocket partout sauf pour les notifications. On réalise un petit bouton dans le menu qui indique les tâches en cours. Le bouton change de couleur quand une extraction ou une synthèse est terminée. Le but : simplifier énormément le code pour qu'on soit le plus FALC possible et respecter le skill /djc. »*

---

## Décisions du brainstorming (Q1-Q8)

| # | Question | Décision | Conséquence |
|---|---|---|---|
| **Q1** | Périmètre WebSocket | **B** — Channels gardé, 1 seul `NotificationConsumer` minimal | On conserve l'infra ASGI/Daphne/channels-redis. On retire `ProgressionTacheConsumer`, `views_ws.py`, `htmx-ext-ws`, `notifications_progression.js` |
| **Q2** | Affichage de la durée | **C** — pas de durée temps réel, durée affichée seulement à la fin | Pas de polling pour la durée, pas de timer JS local. Juste un spinner pendant que ça tourne |
| **Q3** | Visibilité du bouton | **A** — toujours visible, 3 états | États : neutre (gris), en_cours (bleu + spinner + compteur), succes (vert + badge), erreur (rouge + badge). 4 classes CSS au total |
| **Q4** | Comportement au clic | **A** — dropdown léger | Liste des 10 dernières tâches avec icône statut + nom + durée finale (terminées) + lien "Voir résultat" |
| **Q5** | Tâches trackées | **C** — analyse + synthèse + transcription audio | Reformulation et restitution IA seront retirées entièrement en session A.7 |
| **Q6** | Marqueur "lue" | **B** — champ `notification_lue` directement sur les modèles `ExtractionJob` et `TranscriptionJob` | 2 migrations triviales (`AddField`) + 1 data migration pour marquer les jobs existants comme déjà lus |
| **Q7** | Réaction au lancement | **A** — toast HX-Trigger + navigation libre | Le clic "Lancer l'analyse" renvoie juste un toast et la page reste intacte. L'utilisateur peut naviguer librement |
| **Q8** | Rafraîchissement bouton | **D** — pure WS + fetch fresh au clic du bouton | Pas de polling périodique. Le WS push pour la réactivité, le clic ramène la fraîcheur via OOB swap dans la réponse du dropdown |

---

## Architecture

### Ce qu'on garde

| Élément | Rôle |
|---|---|
| `channels`, `daphne`, `channels-redis` (pyproject) | Infra ASGI |
| `daphne` dans INSTALLED_APPS, `RedisChannelLayer` dans CHANNEL_LAYERS (settings) | Inchangé |
| `hypostasia/asgi.py` | Inchangé (1 seul WS path) |
| `front/routing.py` | Réduit à 1 seule route : `path('ws/notifications/', NotificationConsumer.as_asgi())` |
| `NotificationConsumer` dans `front/consumers.py` | Refonte complète, ~30 lignes au lieu de ~200 |
| Modèles métier (`ExtractionJob`, `TranscriptionJob`, `Page`, etc.) | Inchangés (sauf ajout 1 champ chacun) |
| Tâches Celery (logique métier) | Inchangées (juste les appels WS internes simplifiés) |

### Ce qu'on retire

| Élément | Volume estimé |
|---|---|
| `ProgressionTacheConsumer` (`front/consumers.py`) | ~200 lignes |
| `front/views_ws.py` (ViewSet de test) | ~50 lignes |
| `front/static/front/js/notifications_progression.js` (entièrement) | ~300 lignes |
| Extension `htmx-ext-ws` (`vendor/htmx-ext-ws-2.0.4.js`) | 1 fichier vendor |
| **10 templates "en cours"** : `panneau_analyse_en_cours`, `synthese_en_cours_drawer`, `transcription_en_cours`, `reformulation_en_cours`, `restitution_ia_en_cours`, `drawer_cartes_partielles`, `ws_analyse_progression`, `ws_progression_tache`, `ws_toast`, `bandeau_notification` | ~800 lignes |
| 8 appels intermédiaires `envoyer_progression_websocket(..., "progression", ...)` dans `tasks.py` | Code dispersé |
| Tous les patterns OOB swap dans templates de progression | 5+ templates touchés |
| Helper `envoyer_progression_websocket()` (l'ancien) | Remplacé par `notifier_tache_terminee()` plus simple |
| Sections de tests dépendant du WS de progression dans 4 fichiers | ~400 lignes |

### Ce qu'on ajoute

| Élément | Volume estimé |
|---|---|
| `notification_lue = BooleanField(default=False)` sur `ExtractionJob` | 1 ligne + migration |
| `notification_lue = BooleanField(default=False)` sur `TranscriptionJob` | 1 ligne + migration |
| Data migration : marquer tous les jobs existants `notification_lue=True` | ~15 lignes |
| Helper `notifier_tache_terminee(user_pk, tache_id, tache_type, status)` dans `tasks.py` | ~15 lignes |
| Refonte `NotificationConsumer` simplifié | ~30 lignes |
| Nouveau ViewSet `TachesViewSet` (`front/views_taches.py`) avec 3 actions : `bouton`, `dropdown`, `marquer_lue` | ~100 lignes |
| Template `taches_bouton.html` (4 états CSS) | ~30 lignes |
| Template `taches_dropdown.html` (liste 10 entrées) | ~80 lignes |
| Bouton dans `base.html` toolbar | ~10 lignes |
| JS minimal dans `hypostasia.js` : connexion WS + handler `tache_terminee` + toggle dropdown | ~30 lignes |
| Tests classe `Phase26iTachesViewSetTest` (~8 tests) | ~150 lignes |
| Tests classe `Phase26iHelperNotifierTacheTermineeTest` (~2 tests) | ~30 lignes |
| Tests classe `Phase26iNotificationConsumerTest` (async, ~3 tests) | ~80 lignes |

### Solde net estimé

- **Lignes retirées** : ~3000
- **Lignes ajoutées** : ~400
- **Net** : **~-2600 lignes**

---

## Composants détaillés

### 1. Modèles (2 migrations)

```python
# core/models.py — addition sur TranscriptionJob
class TranscriptionJob(models.Model):
    # ... champs existants ...
    notification_lue = models.BooleanField(
        default=False,
        help_text="Notification de fin lue par le proprietaire / "
                  "End-of-task notification read by the owner",
    )

# hypostasis_extractor/models.py — addition sur ExtractionJob
class ExtractionJob(models.Model):
    # ... champs existants ...
    notification_lue = models.BooleanField(
        default=False,
        help_text="Notification de fin lue par le proprietaire / "
                  "End-of-task notification read by the owner",
    )
```

Migrations associées :
- `core/migrations/00XX_transcriptionjob_notification_lue.py` (auto-générée, `AddField`)
- `hypostasis_extractor/migrations/00XX_extractionjob_notification_lue.py` (auto-générée, `AddField`)
- `core/migrations/00XX_marquer_notifications_existantes_lues.py` (data migration manuelle, `RunPython`)

### 2. Consumer simplifié

```python
# front/consumers.py — fichier complet après refonte (~35 lignes)
"""
Consumer WebSocket pour notifications de fin de tache.
Refonte A.6 : un seul consumer minimal, pas de progression streaming.
/ WebSocket consumer for task-end notifications.
A.6 refactor: single minimal consumer, no progression streaming.
"""
from channels.generic.websocket import AsyncJsonWebsocketConsumer


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    """
    Consumer minimal : ecoute le group user_<id> et pousse les
    notifications de fin de tache au client.
    / Minimal consumer: listens on user_<id> group and pushes task-end
    notifications to the client.

    LOCALISATION : front/consumers.py
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

### 3. Helper Celery simplifié

```python
# front/tasks.py — nouveau helper (~15 lignes)
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

### 4. ViewSet `TachesViewSet`

Voir spec détaillée dans la section 2 du brainstorming. Résumé :

- `GET /taches/bouton/` → renvoie le partial HTML du bouton avec son état (calcul des compteurs depuis la DB, choix de l'état parmi `neutre|en_cours|succes|erreur`)
- `GET /taches/dropdown/` → renvoie le partial HTML du dropdown (liste des 10 dernières tâches avec icône statut + nom + durée + lien) **+ OOB swap** du bouton lui-même pour réalignement
- `POST /taches/<pk>/marquer-lue/?type=extraction|transcription` → flag `notification_lue=True`, retourne 204 No Content

L'état est calculé selon priorité : `erreur` > `succes` > `en_cours` > `neutre`.

### 5. Templates

**`taches_bouton.html`** (~30 lignes) : un `<a id="btn-taches">` avec classes CSS d'état, badge compteur conditionnel, spinner conditionnel.

**`taches_dropdown.html`** (~80 lignes) : 
- Header avec titre "Mes tâches récentes"
- Liste de `{% for tache in taches %}` avec :
  - Icône statut (✓ vert / ⟳ bleu / ✗ rouge)
  - Nom de la tâche (`{{ tache.nom_court }}`)
  - Durée finale pour terminées (`{{ tache.duree_finale|duree_humaine }}`) ou "en cours…"
  - Bouton "Voir résultat" qui pointe vers la page concernée + query param de marquage lue
- OOB swap du bouton à la fin du template (`<a id="btn-taches" hx-swap-oob="outerHTML">…</a>`)

### 6. JS minimal dans `hypostasia.js` (~30 lignes ajoutées)

```javascript
// === A.6 — WebSocket notifications + dropdown taches ===

// Connexion au consumer NotificationConsumer (1 seule connexion par session)
// / Connect to NotificationConsumer (1 connection per session)
const wsTaches = new WebSocket(
    (window.location.protocol === "https:" ? "wss://" : "ws://")
    + window.location.host + "/ws/notifications/"
);

// A la reception d'un message 'tache_terminee', refetch le bouton
// pour mettre a jour son etat (couleur + badge).
// / On 'tache_terminee', refetch button to update state.
wsTaches.addEventListener("message", function(evt) {
    const data = JSON.parse(evt.data);
    if (data.type === "tache_terminee") {
        // Trigger HTMX fetch sur le bouton
        // / Trigger HTMX fetch on the button
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
    if (bouton) {
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
```

---

## Data flow utilisateur

### Flow 1 — Lancement d'une analyse

1. Utilisateur sur `/lire/123/`, clique "Lancer l'analyse"
2. HTMX `POST /lire/123/analyser/`
3. Server : crée `ExtractionJob(status="pending")`, lance `analyser_page_task.delay()`
4. Server répond : 200, body vide, `HX-Trigger: {"showToast": {"message": "Analyse lancée. Vous serez notifié à la fin.", "icon": "info"}}`
5. Client : toast s'affiche en bas, page reste intacte
6. Utilisateur peut naviguer librement

### Flow 2 — Notification de fin

1. Tâche Celery termine `analyser_page_task` (avec succès ou erreur)
2. `tasks.py` appelle `notifier_tache_terminee(user_pk=42, tache_id=789, tache_type="analyse", status="completed")`
3. `NotificationConsumer` pousse au group `user_42` → message JSON au navigateur
4. JS dans `hypostasia.js` reçoit le message, déclenche `htmx.ajax("GET", "/taches/bouton/", ...)` qui rafraîchit le bouton
5. Bouton passe à état `succes` (vert + badge 1)

### Flow 3 — Consultation du dropdown

1. Utilisateur clique sur le bouton vert
2. JS toggle l'affichage du wrapper `#taches-dropdown-wrapper`
3. JS fetch `/taches/dropdown/` (HTMX inject dans `#taches-dropdown-content`)
4. Server répond le partial HTML du dropdown + OOB swap du bouton (réalignement)

### Flow 4 — Clic "Voir résultat"

1. Utilisateur clique sur "Voir résultat" pour une analyse terminée
2. Lien : `<a hx-get="/lire/123/?marquer_lue=789&type=extraction" hx-target="#zone-lecture" hx-swap="innerHTML" hx-push-url="/lire/123/">`
3. Server : `LectureViewSet.retrieve()` détecte le query param, marque le job comme lu (`ExtractionJob(789).notification_lue = True`), puis renvoie le HTML normal de la page
4. Au prochain refetch du bouton (suite à un autre WS push ou clic ultérieur), le bouton passe à `neutre`

### Flow 5 — Page rechargée pendant qu'une tâche tourne

1. Utilisateur a lancé une analyse, ferme l'onglet, rouvre la page
2. Au chargement, le bouton est rendu côté serveur (état initial frais depuis DB)
3. Le WebSocket se reconnecte automatiquement à la connexion (1 seule connexion par page)
4. Pas de polling : si la tâche se termine pendant l'absence, le badge sera "non lu" en DB → bouton vert au reload
5. Si tâche encore en cours : bouton bleu, spinner

### Flow 6 — Erreur de connexion WebSocket

1. WebSocket déconnecté (réseau perdu, Daphne redémarré, etc.)
2. Pas de notification "tâche terminée" en push
3. **MAIS** : dès que l'utilisateur clique sur le bouton, le dropdown fetch `/taches/dropdown/` qui ramène l'état frais depuis DB + OOB swap du bouton
4. Si l'utilisateur ne clique jamais : bouton figé sur l'ancien état (acceptable, c'est sa responsabilité)
5. Au prochain reload de la page : tout re-synchronisé

### Flow 7 — Erreur de tâche

1. `analyser_page_task` lève une exception
2. Bloc `except` : `ExtractionJob.status = "failed"`, `error_message = ...`
3. Appel `notifier_tache_terminee(user_pk, tache_id, "analyse", "failed")`
4. Bouton passe à état `erreur` (rouge, prioritaire sur `succes`)
5. Dropdown : ligne avec icône ✗ rouge + message court + bouton "Voir détails"

---

## Tests

### Tests à retirer (cartographie au moment de l'implémentation)

- **`front/tests/test_phases.py`** : classes `Phase14*`, `Phase29SyntheseDrawerWS*`, `Phase16BandeauNotificationTest`, et autres tests qui mockent `envoyer_progression_websocket` (~7 refs)
- **`front/tests/test_phase28_light.py`** : sections de tests qui vérifient les calls WS de progression (~7 refs)
- **`front/tests/test_phase29_synthese_drawer.py`** : tests du pattern OOB swap drawer (~4 refs)
- **`front/tests/test_analyse_drawer_unifie.py`** : tout le fichier teste le pattern OOB+WS+drawer
- **Tests qui chargent les 10 templates "en cours"** (chargement template existe + structure)

### Tests à ajouter

**Classe `Phase26iTachesViewSetTest`** (8 tests) :
- `test_bouton_neutre_si_aucune_tache`
- `test_bouton_en_cours_si_extraction_pending`
- `test_bouton_succes_si_notification_non_lue`
- `test_bouton_erreur_si_failed_non_lu` (priorité sur succes)
- `test_dropdown_liste_10_dernieres_taches` (sort created_at desc)
- `test_dropdown_filtre_par_owner` (sécurité)
- `test_marquer_lue_passe_le_flag_a_true`
- `test_marquer_lue_seulement_owner` (refus 404 si pas owner)

**Classe `Phase26iHelperNotifierTacheTermineeTest`** (2 tests) :
- `test_helper_envoie_au_group_user_pk` (mock `channel_layer.group_send`)
- `test_helper_format_message_attendu` (vérifie les clés)

**Classe `Phase26iNotificationConsumerTest`** (3 tests, async pytest-asyncio) :
- `test_consumer_refuse_anonyme`
- `test_consumer_join_group_user_pk`
- `test_consumer_recoit_message_tache_terminee`

---

## Migration de l'existant en DB

### Migrations

- `hypostasis_extractor/migrations/00XX_extractionjob_notification_lue.py` (`AddField` auto)
- `core/migrations/00XX_transcriptionjob_notification_lue.py` (`AddField` auto)
- `core/migrations/00XX_marquer_notifications_existantes_lues.py` (data migration `RunPython`)

### Data migration : marquer tous les jobs existants comme déjà lus

```python
"""
Marque tous les ExtractionJob et TranscriptionJob existants au moment de
la migration A.6 comme deja lus. Sinon le bouton apparaitrait en vert
avec un compteur enorme au premier login post-migration.
/ Mark all existing jobs as 'already read' at A.6 migration time.
Otherwise the button would show a huge unread counter on first post-migration login.
"""
from django.db import migrations


def marquer_jobs_existants_lus(apps, schema_editor):
    ExtractionJob = apps.get_model('hypostasis_extractor', 'ExtractionJob')
    TranscriptionJob = apps.get_model('core', 'TranscriptionJob')
    nb_extractions = ExtractionJob.objects.update(notification_lue=True)
    nb_transcriptions = TranscriptionJob.objects.update(notification_lue=True)
    print(f"  -> A.6 data migration : "
          f"{nb_extractions} extractions + {nb_transcriptions} transcriptions "
          f"marquees comme deja lues.")


class Migration(migrations.Migration):
    dependencies = [
        # ('hypostasis_extractor', '00XX_extractionjob_notification_lue'),
        # ('core', '00XX_transcriptionjob_notification_lue'),
    ]
    operations = [
        migrations.RunPython(
            marquer_jobs_existants_lus,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
```

---

## Hors périmètre A.6

### Reformulation IA + Restitution IA → A.7

Décision prise pendant le brainstorming : ces 2 tâches Celery sont entièrement retirées en **session A.7** (planifiée juste après A.6). Templates `reformulation_en_cours.html` et `restitution_ia_en_cours.html` ne sont pas dans le périmètre A.6 ; ils seront retirés en A.7 avec leur logique métier.

**Pourquoi pas A.6 ?** Parce que retirer des templates "en cours" est un effet de bord, mais retirer la fonctionnalité Reformulation IA / Restitution IA elle-même nécessite une décision YAGNI distincte (ce que A.7 traitera).

### Le calcul de coût d'analyse

Conservé sur les modèles `Analyseur` / `ExtractionJob` (`cout_reel_euros`, `tokens_input_reels`, `tokens_output_reels`). Utile pour informer l'utilisateur indépendamment de la facturation (qu'on a retirée en A.4).

### L'extension navigateur Hypostasia

La sidebar de l'extension communique aussi avec le serveur. Pas concernée par cette refonte (utilise des appels HTTP DRF JSON, pas le WS de progression).

---

## Décisions futures liées

- **A.7** — Retrait Reformulation IA + Restitution IA (suite logique de cette refonte)
- **PHASE B (refonte RAG)** — Ne dépend pas directement de A.6 mais bénéficie de la simplification (les futures phases auront moins de dette technique sur le WS à gérer)

---

## Métriques de succès

Cette refonte est réussie si :

- ✅ Le code WebSocket passe de ~3000 lignes à ~400 lignes (gain net ~2600 lignes)
- ✅ Plus aucun pattern OOB swap en cascade dans les templates
- ✅ La doc CLAUDE.md §7b "WebSocket + OOB : patterns et pieges" devient obsolète (à supprimer après A.6)
- ✅ Le bouton "tâches en cours" affiche correctement les 4 états (neutre/en_cours/succes/erreur)
- ✅ Le toast s'affiche au lancement (HX-Trigger + showToast déjà câblé)
- ✅ La notification WS push correctement et le bouton se rafraîchit en réaction
- ✅ Le dropdown s'ouvre au clic et liste correctement les 10 dernières tâches
- ✅ Le marquage "lue" persiste en DB et survit aux reloads de page
- ✅ Tous les tests Django passent dans Docker
- ✅ Test manuel UI Firefox : 4 scénarios (lancement analyse, notification, consultation dropdown, voir résultat)

---

## Auto-revue de la spec

- ✅ **Pas de placeholders** : "TBD", "TODO", sections vagues — aucun
- ✅ **Cohérence interne** : les décisions Q1-Q8 sont reportées fidèlement dans Architecture/Composants/Data flow. Pas de contradiction.
- ✅ **Scope** : single subsystem (refonte WS + bouton), 1 plan d'implémentation suffit. Pas de décomposition nécessaire.
- ✅ **Ambiguïté** :
  - Le pattern HTMX d'ouverture du dropdown a été clarifié (toggle JS + fetch HTMX au moment du clic, pas `hx-get-onclick` qui n'existe pas)
  - Le marquage "lue" passe par query param dans la requête `/lire/{pk}/?marquer_lue=789&type=extraction` (1 seule requête, pas 2)
  - L'OOB swap du bouton dans la réponse du dropdown est explicitement documenté pour le réalignement post-clic
- ✅ **Tests** : périmètre clair (tests à retirer + tests à ajouter Phase26i*)
- ✅ **Migration** : 2 `AddField` + 1 data migration pour éviter le compteur énorme post-migration

---

## Références

- Spec maître : [PLAN/REVUE_YAGNI_2026-05-01.md](REVUE_YAGNI_2026-05-01.md)
- Plans précédents : A.1 → A.5
- Skill suivante (à invoquer pour le plan d'implémentation) : `superpowers:writing-plans`
