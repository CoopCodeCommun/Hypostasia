# Tests — où lancer, où écrire

## Lancer : par le Makefile, jamais autrement

**Les commandes ne sont pas recopiées ici.** Elles vivent dans le `Makefile`, à
la racine, et à un seul endroit — une seconde copie finirait par mentir. Ce
document a lui-même annoncé « ~800 tests en ~20 s » longtemps après que la
suite en comptait plus du double.

```bash
make test          # l'aide : toutes les cibles et leur coût
```

Ce qu'il faut savoir avant de taper quoi que ce soit :

- **`make test-rapide` est le geste quotidien.** Tout sauf e2e, Docling et LLM.
- **Les tests coûteux sont opt-in par deux mécanismes à la fois** : une variable
  d'environnement (`TESTS_DOCLING`, `TESTS_LLM_REELS`) **et** un tag Django. Les
  e2e, eux, sont tagués `e2e` par leur classe de base (`front/tests/e2e/base.py`)
  — c'est ce qui permet à `test-rapide` de les exclure.
- **`make test-llm` appelle de vrais modèles et c'est facturé.** La cible
  demande confirmation.
- **Une suite à la fois, jamais `--parallel`.** La base de test est partagée :
  deux exécutions simultanées se la détruisent mutuellement en plein vol. C'est
  déjà arrivé — 755 erreurs fantômes, sans rapport avec le code.

## Où écrire un test

| Ce qu'on teste | Où |
|---|---|
| du **Python** — modèle, serializer, vue, service, validation serveur | `front/tests/test_*.py`, `core/tests/`, `hypostasis_extractor/tests/` |
| du **navigateur** — rendu, swap HTMX, WebSocket, CSS, JS | `front/tests/e2e/test_NN_*.py` (Playwright) |
| **les deux** | un test serveur *et* un test e2e — ils ne voient pas la même chose |

Un test unitaire **ne peut pas** exécuter de JavaScript : il n'a pas de
navigateur. Un test e2e **ne peut pas** compter sur un ROLLBACK de base entre
deux tests : il tourne contre un serveur vivant.

### Deux pièges Playwright qui coûtent une demi-heure

- **`PLAYWRIGHT_BROWSERS_PATH=/home/hypostasia/.cache/ms-playwright`** doit être
  dans l'environnement. Sans elle, tous les e2e échouent en `setUpClass`, et le
  message ne dit pas pourquoi.
- **L'API sync de Playwright tourne dans une boucle asyncio** : toute requête
  ORM lancée depuis un test e2e lève `SynchronousOnlyOperation`. Faire ses
  requêtes **avant** d'ouvrir le navigateur.

## Ce qu'il y a, aujourd'hui

*Compté le 16 août 2026 — un nombre de fichiers, pas un nombre de tests.*

| | Unitaires | E2E |
|---|---|---|
| `front` | 58 fichiers | 30 fichiers |
| `core` | 14 fichiers | — |
| `hypostasis_extractor` | 18 fichiers | — |

`front/tests/test_phases.py` est un monolithe de 7 408 lignes qui couvre les
phases 01 à 26h. Les tests écrits depuis vivent dans des fichiers nommés par
leur sujet (`test_lecture_elements.py`, `test_taches_ingestion.py`), pas par
leur numéro de phase — c'est la convention à suivre.

## Des garde-fous à ne pas casser

- **`front/tests/test_aucun_geste_orphelin.py`** vérifie que chaque geste porté
  par l'arbre latéral supprimé a gardé un point d'entrée quelque part. Il existe
  parce que deux fois dans la même journée, un retrait « propre » a failli
  supprimer une fonction entière sans que personne ne le voie.
- **`hypostasis_extractor/tests/test_files_celery_ingestion.py`** verrouille les
  deux files Celery et la concurrence 1 sur l'ingestion Docling.
- **`front/tests/test_script_d_installation.py`** tient l'invariant
  `DEBUG` ↔ `NGINX_CONF` : les désaccorder donne un 502 sur tout le site.

## Pour aller plus loin

- **`PLAN_TEST.md`** (à côté) — philosophie, infrastructure Playwright,
  conventions de nommage. ⚠️ Ses blocs de commandes et ses inventaires chiffrés
  datent de mars 2026 : s'y fier pour la méthode, pas pour les nombres.
- **`CHANGELOG/`** — ce que chaque chantier a livré et comment le vérifier à la
  main. C'est là que vit la couverture par phase, qui figurait autrefois ici.
