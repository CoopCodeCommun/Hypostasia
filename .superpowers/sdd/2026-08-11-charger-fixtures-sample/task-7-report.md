# Rapport — Tâche 7 : notifier depuis les trois tâches d'ingestion

## Ce qui a été fait

Suivi TDD strict : tests écrits en premier (Étape 1, copiés verbatim du
brief dans `hypostasis_extractor/tests/test_notifications_ingestion.py`),
lancés et vérifiés en échec (Étape 2), implémentation (Étapes 3-5), puis
tests relancés jusqu'au vert (Étape 6). Aucun écart entre le test et le
code final — le brief était juste, aucune correction de test nécessaire.

### 1. Nouvelle fonction `_prevenir_de_l_ingestion(page, statut)`

Ajoutée dans `hypostasis_extractor/tasks_element.py`, juste après
`_noter_l_etat_d_ingestion` (avant `ingerer_un_fichier_avec_docling`).
Code repris verbatim du brief : boucle sur
`front.tasks._destinataires_de_notification(page)`, ignore les `None`,
appelle `front.tasks.notifier_tache_terminee(user_pk=..., tache_id=page.pk,
tache_type="ingestion", status=statut)`, capture toute exception dans un
`try/except` avec `logger.warning` — une notification en échec ne fait
jamais échouer l'ingestion.

`tache_id=page.pk` (pas de job pour une ingestion, cf. brief).

### 2. Dix points d'appel ajoutés dans les trois tâches d'ingestion

Fichier `hypostasis_extractor/tasks_element.py`. Pour chaque tâche, un
appel `"completed"` après le `_noter_l_etat_d_ingestion(..., REUSSIE)`,
et un appel `"error"` après **chaque** `_noter_l_etat_d_ingestion(...,
ECHOUEE, ...)`. Le retour anticipé « page déjà ingérée »
(`{"erreur": "page deja ingeree"}`) ne notifie **pas** — conforme au
brief.

| Fonction | Ligne | Chemin | Statut |
|---|---|---|---|
| `ingerer_un_fichier_avec_docling` | 371 | page sans fichier source | error |
| `ingerer_un_fichier_avec_docling` | 386 | stockage sans chemin local | error |
| `ingerer_un_fichier_avec_docling` | 403 | exception de conversion Docling | error |
| `ingerer_un_fichier_avec_docling` | 407 | succès | completed |
| `ingerer_une_capture_web_avec_docling` | 461 | capture sans HTML (`ValueError`) | error |
| `ingerer_une_capture_web_avec_docling` | 472 | exception de conversion Docling | error |
| `ingerer_une_capture_web_avec_docling` | 476 | succès | completed |
| `ingerer_une_transcription_diarisee_en_elements` | 548 | exception du service (garde-fou double-worker) | error |
| `ingerer_une_transcription_diarisee_en_elements` | 560 | transcription vide/illisible (`"erreur" in resultat`) | error |
| `ingerer_une_transcription_diarisee_en_elements` | 564 | succès | completed |

(Numéros de ligne = état final du fichier après édition.)

### 3. Second défaut corrigé : destinataires de `_prevenir_l_utilisateur`

`hypostasis_extractor/tasks_element.py`, fonction `_prevenir_l_utilisateur`
(analyse) : remplacé la lecture de `job_extraction.page.owner` seul par
une boucle sur `front.tasks._destinataires_de_notification(job_extraction.page)`,
même tolérance aux erreurs (`try/except` + `logger.warning` par
destinataire) — même patron que `_prevenir_de_l_ingestion`.

### 4. Second défaut corrigé : destinataires de `transcrire_audio_task`

`front/tasks.py`, deux appels dans `transcrire_audio_task` :
- ligne ~704 (succès) : remplacé
  `user_pk=page_associee.owner.pk if page_associee.owner else None` par
  une boucle `for pk_destinataire in
  _destinataires_de_notification(page_associee): notifier_tache_terminee(...)`.
- ligne ~735 (erreur) : même transformation.

`_destinataires_de_notification` renvoie `[None]` quand il n'y a aucun
destinataire (owner et carnets tous `None`), ce qui reproduit
exactement le comportement précédent dans ce cas (un seul appel avec
`user_pk=None`). Pas de `try/except` ajouté autour de la boucle : ce
n'est pas le patron existant à cet endroit du fichier (le patron
synthèse, lignes ~1387-1393, ne l'a pas non plus — `notifier_tache_terminee`
lui-même absorbe déjà l'absence de channel layer, cf. son
`if couche_channels is None: return`).

## Sortie exacte des tests

### Étape 2 — avant implémentation (échec attendu)

```
Ran 5 tests in 0.144s
FAILED (failures=3, errors=1)
```

- `test_une_capture_ingeree_previent_son_proprietaire` :
  `AssertionError: Expected 'notifier_tache_terminee' to be called once.
  Called 0 times.` — exactement l'échec annoncé par le brief.
- `test_une_ingestion_en_echec_previent_aussi` :
  `AttributeError: 'NoneType' object has no attribute 'kwargs'` (aucun
  appel du tout).
- `test_le_proprietaire_d_un_carnet_est_prevenu_aussi` : ensemble de pks
  prévenus incomplet.
- `test_l_analyse_previent_les_proprietaires_de_carnets` : le collègue
  n'était pas prévenu.
- `test_une_notification_qui_echoue_ne_casse_pas_l_ingestion` : passait
  déjà (rien à casser, la tâche n'appelait rien).

### Étape 6 — après implémentation

```
docker exec -w /app hypostasia_web uv run python manage.py test \
    hypostasis_extractor.tests.test_notifications_ingestion --noinput \
    --settings=hypostasia.settings_test_opus

Ran 5 tests in 0.186s
OK
```

```
docker exec -w /app hypostasia_web uv run python manage.py test \
    front.tests.test_corpus_phase_d hypostasis_extractor.tests \
    --noinput --settings=hypostasia.settings_test_opus

Ran 313 tests in 91.648s
OK (skipped=9)
```

Aucun test préexistant n'a changé de comportement (313/313 verts, 9
skips identiques à la base — pas de régression).

## Écarts par rapport au brief

Aucun. Le code de `_prevenir_de_l_ingestion` et les tests ont été repris
verbatim. Les dix points d'appel suivent la règle du brief (« tous les
chemins d'échec préviennent, le retour anticipé ne prévient pas »).

## Notes

- Fichiers modifiés :
  `hypostasis_extractor/tasks_element.py`,
  `front/tasks.py`,
  `hypostasis_extractor/tests/test_notifications_ingestion.py` (nouveau).
- Rien commité, aucune opération git lancée.

---

## Correction post-revue (revue adverse)

La revue a trouvé deux défauts introduits en touchant `front/tasks.py`
et une erreur de compte dans ce rapport (§ 2 disait « neuf », le
tableau en listait dix — corrigé ci-dessus en « dix », qui est le bon
compte).

### 1. CRITIQUE — `try/except` manquant autour des deux boucles de `transcrire_audio_task`

Les boucles de notification (succès ~704, erreur ~736) sont **à
l'intérieur du `try` principal** de la tâche (ouvert ligne 631).
`notifier_tache_terminee` (`front/tasks.py:17`) n'absorbe que le cas
« channel layer non configuré » (retour silencieux si
`couche_channels is None`) — pas une exception levée par `group_send`
(ligne 39, ex. broker Redis tombé). Sans `try/except` local, cette
exception remonte au `except Exception` de la ligne 712, qui
**écrase le statut `COMPLETED` déjà sauvegardé en base par `ERROR`** :
une transcription réussie, texte déjà persisté, se retrouvait marquée
en échec, puis une seconde notification « error » était tentée (même
canal mort → même échec, absorbé cette fois par le `except` externe
qui l'encadre déjà pour la mise à jour de statut, mais le mal était
fait).

Mon hypothèse initiale rapportée (« le patron synthèse ne le fait pas
non plus, donc pas nécessaire ici ») était fausse : le patron synthèse
(lignes ~1387-1393) n'est *pas* dans un `try` dont le `except`
réécrit un statut déjà réussi de la même façon — la comparaison ne
tenait pas. Corrigé.

**Correctif** : les deux boucles (succès et erreur) sont maintenant
enveloppées d'un `try/except Exception` par appel, avec
`logger.warning`, même patron que `_prevenir_de_l_ingestion` et
`_prevenir_l_utilisateur`.

**Preuve TDD** : nouveau fichier
`front/tests/test_notification_transcription.py`, test
`test_une_notification_qui_echoue_ne_marque_pas_la_page_en_erreur`.
Il fait tourner `transcrire_audio_task.apply()` avec
`transcrire_audio_mock` mocké (retour rapide, sans le `time.sleep(3)`
réel) et `notifier_tache_terminee` qui lève `RuntimeError`, puis
vérifie que `page.status == PageStatus.COMPLETED` et
`job_transcription.status == "completed"`.

Vérifié en échec sur le code non corrigé (rollback temporaire de la
boucle succès, sans opération git — édition manuelle puis restauration
immédiate) :

```
AssertionError: 'error' != PageStatus.COMPLETED
Ran 1 test in 0.085s
FAILED (failures=1)
```

Puis vert après restauration du correctif :

```
Ran 1 test in 0.064s
OK
```

### 2. IMPORTANT — `None` non filtré dans les deux boucles de `front/tasks.py`

`_destinataires_de_notification` rend `[None]` quand il n'y a aucun
destinataire (docstring, `front/tasks.py:65-68`). Les boucles de
`tasks_element.py` filtraient déjà `if pk_destinataire is None: continue`
(lignes 209 et 286 à l'époque) ; celles de `front/tasks.py`
(transcription, succès et erreur) ne le faisaient pas — un
`user_pk=None` aurait poussé sur le groupe `user_None`, notification
perdue en silence. Ajouté aux deux endroits, même garde que partout
ailleurs.

### Sortie exacte des tests, dans l'ordre demandé

**1. `hypostasis_extractor.tests.test_notifications_ingestion`, seule :**

```
docker exec -w /app hypostasia_web uv run python manage.py test \
    hypostasis_extractor.tests.test_notifications_ingestion --noinput \
    --settings=hypostasia.settings_test_opus

Ran 5 tests in 0.143s
OK
```

**2. Les suites `front.tests` touchées par la transcription, séparément
(une seule invocation `manage.py test` avec plusieurs labels — un seul
processus, pas deux suites en parallèle) :**

```
docker exec -w /app hypostasia_web uv run python manage.py test \
    front.tests.test_notification_transcription \
    front.tests.test_import_docling \
    front.tests.test_permissions_famille \
    front.tests.test_phase27a \
    front.tests.test_charger_fixtures_sample \
    front.tests.test_rendu_elements \
    front.tests.test_phases \
    --noinput --settings=hypostasia.settings_test_opus

Ran 679 tests in 126.641s
OK
```

Cette commande a dépassé le délai de 120 s de l'outil bash au premier
essai et est passée en arrière-plan automatiquement ; son processus
Celery/Django a été laissé tourner seul jusqu'à la fin (vérifié par
`ps -eo etime,cmd | grep manage.py test` : aucun processus actif avant
lecture du résultat), sans relance concurrente.

### Fichiers modifiés (session de correction)

- `front/tasks.py` : `try/except` + filtrage `None` ajoutés aux deux
  boucles de `transcrire_audio_task` (succès ~704-725, erreur
  ~749-770 après les ajouts).
- `front/tests/test_notification_transcription.py` (nouveau) : preuve
  TDD du défaut critique.
- `.superpowers/sdd/2026-08-11-charger-fixtures-sample/task-7-report.md` :
  compte corrigé (neuf → dix) et présente section ajoutée.

Rien commité, aucune opération git lancée.
