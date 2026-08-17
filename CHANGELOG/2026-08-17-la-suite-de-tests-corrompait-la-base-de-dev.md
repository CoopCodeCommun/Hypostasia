# La suite de tests corrompait la base de dev / The test suite corrupted the dev database

**Date :** 2026-08-17
**Migration :** Non

## Résumé / Summary

**Quoi / What :** `CELERY_TASK_ALWAYS_EAGER` n'était pas posé sous test. Tout test
traversant un `.delay()` publiait donc un **vrai message** dans le Redis partagé, portant
une clé primaire de la **base de test** — et le worker de dev l'exécutait contre la base de
**dev**, où cette clé désigne un tout autre objet.
*/ `CELERY_TASK_ALWAYS_EAGER` was not set under test, so any test crossing a `.delay()`
published a real message carrying test-database primary keys, which the dev worker then ran
against the dev database.*

**Pourquoi / Why :** c'est la même famille que « une suite de tests à la fois, jamais
`--parallel` », déjà documentée : deux exécutions qui partagent une ressource se détruisent
mutuellement. Ici la ressource n'est pas la base, c'est le **broker** — et personne ne
l'avait vu.
*/ Same family as the documented "one test suite at a time": the shared resource here is
the broker.*

### Comment il s'est montré

Une réinstallation complète (`docker compose down -v && make install`) a d'abord réussi :
5 notes ingérées, 8 jobs `completed`, aucune erreur. **Dix minutes plus tard**, sans
qu'aucune commande ne touche la base, quatre jobs étaient passés en `error` et le carnet
étalon était tombé de **101 à 41 extractions citables**.

Les messages d'erreur ont donné la piste — les jobs 3, 4 et 5 sont des jobs d'**analyse**,
et ils avaient échoué sur des exceptions de **wiki** et de **synthèse** :

```
job 4 | error | ext= 18 | Analyseur: Hypostasia | 'wiki_id'
job 5 | error | ext= 24 | Analyseur: Hypostasia | Page has no synthese_dirigee.
```

Et les journaux ont donné l'heure : **12:04-12:05**, précisément pendant que des suites de
tests tournaient. Les identifiants « introuvables » qui les accompagnaient (9, 10, 12 à 15)
étaient ceux de la base de test.

**Aucun test n'a échoué.** La corruption était entièrement silencieuse.

### Le dégât réel n'était pas l'exception

Il était dans le gestionnaire d'erreur. Une tâche d'article qui lève marque son job
`error` — et **un job d'analyse en `error` rend ses extractions NON CITABLES**
(`_filtrer_les_citables` ne retient que les jobs terminés). De la donnée parfaitement
valide devenue invisible : 42 extractions écartées du périmètre de toute synthèse, sans
message, sans trace à l'écran.

### Trois barrières

| # | Barrière | Où |
|---|---|---|
| 1 | **`CELERY_TASK_ALWAYS_EAGER` + `EAGER_PROPAGATES` sous test** — aucune tâche ne sort vers le broker ; elles s'exécutent en ligne, dans la transaction du test, et une exception fait échouer le test au lieu d'être ravalée | `hypostasia/settings.py` |
| 2 | **Une tâche refuse un job qui n'est pas le sien, AVANT d'y toucher** — les quatre tâches carnet-niveau vérifient leur marqueur (`est_wiki`, `est_synthese_carnet`, `est_maj_wiki`, `est_verification`) et s'arrêtent en avertissant, sans rien modifier | `front/tasks.py` — `_le_job_n_est_pas_le_mien` |
| 3 | Le défaut `MOCK` de `AIModel.provider`, qui protège du côté facturation | `core/models.py` (existant) |

> **Une quatrième barrière a été posée puis RETIRÉE**, et la raison est consignée dans
> `core/llm_providers.py` : un garde « pas d'appel réel sous test » levait dès qu'un test
> employait un provider non-`MOCK`. Or `Phase24LlmProviders*Test` éprouve légitimement ce
> dispatch, **SDK moqué**, sans qu'aucun appel ne sorte. Le critère ne pouvait pas
> distinguer un SDK patché d'un appel accidentel : 5 tests cassés pour zéro défaut réel
> attrapé. Retiré au profit des trois barrières ci-dessus, qui tiennent.

### Le nettoyage des fixtures héritées

**1 446 lignes supprimées** : `charger_fixtures_demo` (1 341) et `import_demo_debat` (105).
Elles n'étaient plus appelées par l'installation, mais la raison de fond est ailleurs :
elles écrivaient des extractions **sans aucune `AncrageExtraction`** et des `parent_page` /
`version_number` — le modèle « synthèse = version d'une page » abandonné le 9 août. Deux
nids de vestiges, vivants et appelables.

`reset_demo` est **gardé** après vérification : il enchaîne `charger_fixtures_sample` puis
`charger_extractions_demo`, les deux commandes qui ancrent.

### Une promesse rendue vraie

Le commentaire de `bin/install.sh` annonçait que « le démarrage suivant complète ce qui
manque » — les analyses partant dans la file Celery, l'article ne cite au premier passage
qu'une partie du corpus. Mais le saut d'idempotence portait sur « l'article est non vide » :
il gelait donc l'article sur son périmètre partiel **pour toujours**.

Le saut compare désormais la **taille du périmètre** à la production, consignée dans le job.
Vérifié sur données réelles :

| | 1er passage | 2e passage |
|---|---|---|
| Wiki | 17 `SourceLink` | **58** |
| Synthèse | 63 `SourceLink` | **87** |
| Périmètre figé | 63 | **104** |

Un troisième passage saute, et rien n'est refacturé.

### Un garde-fou qui avait lui-même dérivé

`ReferentielPublieDansLeReadmeTest` vérifie que la matrice des 30 hypostases publiée aux
humains reste d'accord avec le code — la **cinquième copie** du référentiel. Or l'exposé a
quitté le `README.md` pour `PRESENTATION-V3.md` le 16 août, et le test a continué de lire le
README : il était **rouge** depuis, dans une suite que personne ne relançait entièrement.
Repointé.

### Fichiers modifiés / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `hypostasia/settings.py` | `CELERY_TASK_ALWAYS_EAGER` et `EAGER_PROPAGATES` sous test |
| `front/tasks.py` | **+** `_le_job_n_est_pas_le_mien`, appliquée aux quatre tâches carnet-niveau |
| `core/llm_providers.py` | la raison du garde retiré, consignée à sa place |
| `front/management/commands/charger_fixtures_demo.py`, `import_demo_debat.py` | **supprimés** (1 446 lignes) |
| `front/management/commands/produire_les_syntheses_etalons.py` | **+** `_faut_il_reproduire` : reprise quand le périmètre a grossi |
| `front/services/fixtures_analyseurs.py`, `charger_fixtures_sample.py` | commentaires qui citaient la commande supprimée au présent |
| `front/tests/test_fixtures_analyseurs.py` | import et classe de test de la commande supprimée |
| `hypostasis_extractor/tests/test_referentiel_des_hypostases.py` | lit `PRESENTATION-V3.md`, plus le README |
| `README.md` | table des fixtures alignée |
| **2 fichiers de tests neufs** | 7 tests |

---

## Comment tester (à la main) / Manual test

### Test 1 — le broker est isolé sous test

```bash
docker exec -w /app hypostasia_web python manage.py shell -c "
from django.conf import settings
print('hors test :', settings.CELERY_TASK_ALWAYS_EAGER)"        # doit afficher False
docker exec -w /app hypostasia_web python manage.py test \
  front.tests.test_une_tache_ne_touche_que_son_job --noinput     # sous test : True
```

Puis, worker à l'arrêt, lancer une suite qui traverse un `.delay()` et vérifier que la file
reste vide :

```bash
docker exec hypostasia_redis redis-cli LLEN celery     # doit rester 0
```

### Test 2 — une tâche ne dégrade pas un job étranger

```bash
docker exec -w /app hypostasia_web python manage.py test \
  front.tests.test_une_tache_ne_touche_que_son_job --noinput
```

Le test qui compte est `test_les_extractions_du_job_etranger_restent_citables` : c'est la
**citabilité** qui était perdue, pas le statut.

### Test 3 — l'installation donne des ancres propres

```bash
docker compose down -v && make install
```

Attendre la fin des tâches (`make logs S=celery_worker`), puis :

```bash
docker exec -w /app hypostasia_web python manage.py shell -c "
from core.models import ElementDocument, Page
from hypostasis_extractor.models import AncrageExtraction, ExtractedEntity
sans_ancre = [e for e in ExtractedEntity.objects.all()
              if not AncrageExtraction.objects.filter(extraction=e).exists()]
print('extractions :', ExtractedEntity.objects.count(), '| SANS ANCRE :', len(sans_ancre))
fausses = 0
for p in AncrageExtraction.objects.select_related('element', 'extraction'):
    t = (p.element.texte or '')[p.debut_dans_element:p.fin_dans_element]
    a = p.extraction.extraction_text or ''
    if not (t and (t in a or a in t)): fausses += 1
print('portions :', AncrageExtraction.objects.count(), '| FAUSSES :', fausses)"
```

Attendu : **0 sans ancre, 0 fausse**. Mesuré le 17 août 2026 sur une installation neuve :
104 extractions, 109 portions, zéro des deux.

### Test 4 — la reprise du périmètre

Une fois toutes les analyses terminées, relancer :

```bash
docker exec -w /app hypostasia_web python manage.py produire_les_syntheses_etalons
```

Elle doit **reproduire** (le périmètre a grossi depuis le premier passage), puis **sauter**
au passage suivant.

### Piège à connaître

**Une suite de tests à la fois** — et désormais on sait pourquoi c'est vrai même quand les
deux exécutions visent des bases différentes : le broker, lui, est partagé.
