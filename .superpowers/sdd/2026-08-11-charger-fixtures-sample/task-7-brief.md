## Tâche 7 : notifier depuis les trois tâches d'ingestion

**Fichiers :**
- Modifier : `hypostasis_extractor/tasks_element.py`
- Modifier : `front/tasks.py` (destinataires de la transcription)
- Test : `hypostasis_extractor/tests/test_notifications_ingestion.py` (créer)

**Interfaces :**
- Consomme : `front.tasks.notifier_tache_terminee`,
  `front.tasks._destinataires_de_notification`.
- Produit : `_prevenir_de_l_ingestion(page, statut)` dans `tasks_element.py`,
  appelée par les trois tâches d'ingestion. `tache_type="ingestion"`,
  `tache_id` = **la clé primaire de la Page** (une ingestion n'a pas de job).

- [ ] **Étape 1 : écrire les tests qui échouent**

```python
"""
Les taches d'ingestion previennent-elles l'utilisateur ?
/ Do ingestion tasks notify the user?

LOCALISATION : hypostasis_extractor/tests/test_notifications_ingestion.py
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import Dossier, Page
from core.services.corpus import ranger_une_note_dans_un_carnet

User = get_user_model()


class NotificationDeLIngestionTest(TestCase):
    """Une ingestion qui se termine doit se faire connaitre."""

    def setUp(self):
        self.proprietaire = User.objects.create_user(username="proprio")
        self.page = Page.objects.create(
            title="Une note", source_type="web",
            html_original="<p>du texte</p>", html_readability="<p>du texte</p>",
            text_readability="du texte", content_hash="x",
            owner=self.proprietaire,
        )

    def test_une_capture_ingeree_previent_son_proprietaire(self):
        from hypostasis_extractor.tasks_element import (
            ingerer_une_capture_web_avec_docling,
        )

        with patch(
            "hypostasis_extractor.services.ingestion_docling."
            "ingerer_une_capture_web", return_value=[1, 2, 3],
        ), patch("front.tasks.notifier_tache_terminee") as notification:
            ingerer_une_capture_web_avec_docling.apply(args=[self.page.pk])

        notification.assert_called_once_with(
            user_pk=self.proprietaire.pk,
            tache_id=self.page.pk,
            tache_type="ingestion",
            status="completed",
        )

    def test_une_ingestion_en_echec_previent_aussi(self):
        # Un echec silencieux est pire qu'un echec : l'utilisateur
        # attendrait indefiniment. / A silent failure is worse.
        from hypostasis_extractor.tasks_element import (
            ingerer_une_capture_web_avec_docling,
        )

        with patch(
            "hypostasis_extractor.services.ingestion_docling."
            "ingerer_une_capture_web", side_effect=ValueError("conversion HS"),
        ), patch("front.tasks.notifier_tache_terminee") as notification:
            ingerer_une_capture_web_avec_docling.apply(args=[self.page.pk])

        self.assertEqual(
            notification.call_args.kwargs["status"], "error",
        )

    def test_le_proprietaire_d_un_carnet_est_prevenu_aussi(self):
        # C'est la correction de la phase D, restee a moitie faite :
        # une note rangee dans le carnet d'un collegue doit le prevenir.
        # / The phase D fix, left half-done.
        from hypostasis_extractor.tasks_element import (
            ingerer_une_capture_web_avec_docling,
        )

        collegue = User.objects.create_user(username="collegue")
        carnet_du_collegue = Dossier.objects.create(
            name="Le carnet du collègue", owner=collegue,
        )
        ranger_une_note_dans_un_carnet(
            self.page, carnet_du_collegue, self.proprietaire,
        )

        with patch(
            "hypostasis_extractor.services.ingestion_docling."
            "ingerer_une_capture_web", return_value=[1],
        ), patch("front.tasks.notifier_tache_terminee") as notification:
            ingerer_une_capture_web_avec_docling.apply(args=[self.page.pk])

        pks_prevenus = {
            appel.kwargs["user_pk"] for appel in notification.call_args_list
        }
        self.assertEqual(pks_prevenus, {self.proprietaire.pk, collegue.pk})

    def test_une_notification_qui_echoue_ne_casse_pas_l_ingestion(self):
        # Une ingestion reussie ne doit pas devenir un echec parce que
        # le canal de notification est tombe.
        # / A dead channel must not fail a successful ingestion.
        from hypostasis_extractor.tasks_element import (
            ingerer_une_capture_web_avec_docling,
        )

        with patch(
            "hypostasis_extractor.services.ingestion_docling."
            "ingerer_une_capture_web", return_value=[1],
        ), patch(
            "front.tasks.notifier_tache_terminee",
            side_effect=RuntimeError("channel layer HS"),
        ):
            resultat = ingerer_une_capture_web_avec_docling.apply(
                args=[self.page.pk],
            )

        self.assertEqual(resultat.result, {"elements": 1})


class DestinatairesDeLAnalyseEtDeLaTranscriptionTest(TestCase):
    """
    La correction de la phase D, appliquee aux deux chemins oublies.
    / The phase D fix, applied to the two forgotten paths.
    """

    def test_l_analyse_previent_les_proprietaires_de_carnets(self):
        from hypostasis_extractor.models import ExtractionJob
        from hypostasis_extractor.tasks_element import _prevenir_l_utilisateur

        proprietaire = User.objects.create_user(username="proprio2")
        collegue = User.objects.create_user(username="collegue2")
        page = Page.objects.create(
            title="Note analysée", source_type="web", html_original="",
            html_readability="", text_readability="", content_hash="y",
            owner=proprietaire,
        )
        carnet = Dossier.objects.create(name="Carnet", owner=collegue)
        ranger_une_note_dans_un_carnet(page, carnet, proprietaire)

        job = ExtractionJob.objects.create(
            page=page, name="j", prompt_description="p", status="completed",
        )

        with patch("front.tasks.notifier_tache_terminee") as notification:
            _prevenir_l_utilisateur(job, "completed")

        pks_prevenus = {
            appel.kwargs["user_pk"] for appel in notification.call_args_list
        }
        self.assertEqual(pks_prevenus, {proprietaire.pk, collegue.pk})
```

- [ ] **Étape 2 : lancer les tests, vérifier qu'ils échouent**

```bash
docker exec -w /app hypostasia_web uv run python manage.py test \
    hypostasis_extractor.tests.test_notifications_ingestion --noinput \
    --settings=hypostasia.settings_test_opus
```

Attendu : `AssertionError: Expected 'notifier_tache_terminee' to be called
once. Called 0 times.` C'est le bon échec — la notification n'existe pas.

- [ ] **Étape 3 : écrire la fonction de notification**

Dans `hypostasis_extractor/tasks_element.py`, à côté de
`_prevenir_l_utilisateur` :

```python
def _prevenir_de_l_ingestion(page, statut):
    """
    Previent les interesses qu'un decoupage en elements s'est termine.
    / Tells the concerned parties an element ingestion has finished.

    LOCALISATION : hypostasis_extractor/tasks_element.py

    POURQUOI CETTE FONCTION

    Une ingestion de PDF prend 80 a 164 s (mesure du 11 aout 2026). Sans
    notification, l'utilisateur qui vient d'importer un document n'a
    aucun moyen de savoir quand son document est pret : il rafraichit au
    jugé. Les trois taches d'ingestion etaient les seules du projet a ne
    rien dire.
    / An ingestion takes up to 164 s; without this, nobody knows when.

    UNE INGESTION N'A PAS DE JOB

    Les analyses ont un ExtractionJob, les transcriptions un
    TranscriptionJob. Une ingestion n'a que sa Page, dont
    `ingestion_etat` porte l'etat. On passe donc la cle primaire de la
    PAGE comme `tache_id` — la vue des taches le sait et cherche au bon
    endroit. / An ingestion has no job: the page's pk is the task id.

    :param page: la Page ingeree
    :param statut: "completed" ou "error"
    """
    from front.tasks import (
        _destinataires_de_notification, notifier_tache_terminee,
    )

    for pk_destinataire in _destinataires_de_notification(page):
        if pk_destinataire is None:
            continue
        try:
            notifier_tache_terminee(
                user_pk=pk_destinataire,
                tache_id=page.pk,
                tache_type="ingestion",
                status=statut,
            )
        except Exception as erreur:
            # Une notification qui echoue ne doit pas faire echouer une
            # ingestion qui, elle, a reussi. Meme principe que partout
            # ailleurs dans ce fichier.
            # / A failed notification must not fail a successful ingestion.
            logger.warning(
                "Page %s : notification d'ingestion non transmise (%s).",
                page.pk, erreur,
            )
```

- [ ] **Étape 4 : appeler la fonction depuis les trois tâches**

Dans chacune des trois — `ingerer_un_fichier_avec_docling`,
`ingerer_une_capture_web_avec_docling`,
`ingerer_une_transcription_diarisee_en_elements` — appeler
`_prevenir_de_l_ingestion(page, "completed")` juste après
`_noter_l_etat_d_ingestion(page.pk, EtatIngestion.REUSSIE)`, et
`_prevenir_de_l_ingestion(page, "error")` juste après **chaque**
`_noter_l_etat_d_ingestion(..., EtatIngestion.ECHOUEE, ...)`.

Attention : il y a **plusieurs** chemins d'échec par tâche (page sans
fichier source, stockage sans chemin local, exception de conversion). Ils
doivent tous prévenir — un échec silencieux laisse l'utilisateur attendre
indéfiniment. **Ne pas prévenir** sur le retour anticipé « page déjà
ingérée » : rien ne s'est passé, il n'y a rien à annoncer.

- [ ] **Étape 5 : corriger les destinataires des deux chemins oubliés**

Dans `hypostasis_extractor/tasks_element.py`, `_prevenir_l_utilisateur`
prend aujourd'hui `page.owner` seul. Le faire passer par
`_destinataires_de_notification(job_extraction.page)`, en gardant la même
tolérance aux erreurs.

Dans `front/tasks.py`, `transcrire_audio_task` notifie
`page_associee.owner.pk` à deux endroits (succès ~704, erreur ~735). Les
faire passer par `_destinataires_de_notification(page_associee)` — la
fonction est définie dans le même fichier, ligne 50.

- [ ] **Étape 6 : lancer les tests, vérifier qu'ils passent**

```bash
docker exec -w /app hypostasia_web uv run python manage.py test \
    hypostasis_extractor.tests.test_notifications_ingestion --noinput \
    --settings=hypostasia.settings_test_opus
```

Puis, **séparément**, les suites qui touchent aux notifications, pour
vérifier qu'on n'a rien cassé :

```bash
docker exec -w /app hypostasia_web uv run python manage.py test \
    front.tests.test_corpus_phase_d hypostasis_extractor.tests \
    --noinput --settings=hypostasia.settings_test_opus
```

- [ ] **Étape 7 : point d'arrêt**

Ne rien commiter. Rapporter le nombre de tests et tout test préexistant
qui aurait changé de comportement.

---

## Tâche 8 : afficher les ingestions dans le bouton et le dropdown
# Addendum du 11 août 2026 — brancher l'ingestion aux notifications

> Demande du propriétaire du dépôt, en cours de session. Ne fait pas partie
> de la spec `2026-08-11-fixtures-sample-design.md` : ces deux tâches
> touchent l'application, pas les fixtures.

## Le constat

Le moteur de notification existe et fonctionne :

```
tâche Celery → notifier_tache_terminee(user_pk, tache_id, tache_type, status)
             → group_send "user_<pk>" → NotificationConsumer.tache_terminee
             → JS : refetch /taches/bouton/
```

**Trois tâches n'y sont pas branchées**, toutes dans
`hypostasis_extractor/tasks_element.py` :

| Tâche | Ligne | Notifie ? |
|---|---|---|
| `ingerer_un_fichier_avec_docling` | 256 | non |
| `ingerer_une_capture_web_avec_docling` | 361 | non |
| `ingerer_une_transcription_diarisee_en_elements` | 427 | non |

Conséquence : importer un PDF déclenche 80 à 164 s de travail (mesure du
11 août) sans que rien ne prévienne l'utilisateur à la fin.

**Second défaut, découvert au même endroit.**
`_destinataires_de_notification(page)` (`front/tasks.py:50`) rend « l'owner
plus les propriétaires des carnets contenant la note ». Son commentaire dit
qu'elle existe parce qu'« avant la phase D, le second carnet d'une note
n'apprenait jamais qu'une synthèse avait tourné ». Or seules la **synthèse**
(`front/tasks.py:1383`, `1414`) et l'**article** (`1615`) l'utilisent :
l'**analyse** (`tasks_element.py:213`) et la **transcription**
(`front/tasks.py:704`, `735`) notifient encore `page.owner` seul. La
correction de la phase D n'a été appliquée qu'à moitié.

## Décision

Pas de nouveau modèle. `Page.ingestion_etat` porte déjà l'état
(`en_attente` / `en_cours` / `reussie` / `echouee`) et fait foi ; un modèle
`JobIngestion` parallèle dupliquerait la vérité et finirait par en diverger.
Il manque seulement un marqueur « lu », symétrique du `notification_lue`
que portent `ExtractionJob` et `TranscriptionJob`.

Le JS n'inspecte pas `tache_type` — il refetch le bouton à chaque message.
Aucun fichier statique à toucher : **ni `collectstatic`, ni bump de `?v=`**.

---

## Tâche 7 : notifier depuis les trois tâches d'ingestion
