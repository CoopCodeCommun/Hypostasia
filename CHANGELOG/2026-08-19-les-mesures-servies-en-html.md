# Les mesures servies en HTML / Benchmark notes served as HTML

**Date :** 2026-08-19
**Migration :** Non.

## Résumé / Summary

**Quoi / What :** `/benchmarks/` liste les comptes rendus de mesure du dossier
`benchmarks/`, et `/benchmarks/voir/<chemin>.md` en rend un en HTML.
Authentification exigée.
*/ Two routes list and render the `benchmarks/` measurement notes.*

**Pourquoi / Why :** ces comptes rendus sont mis à jour souvent. Un HTML
engendré serait une **seconde copie** à régénérer à la main — et le jour où on
oublie, la page ment sans que rien ne le dise. Le markdown est donc rendu **à la
lecture** : il n'y a jamais qu'une source.
*/ Rendered on read; a generated copy would silently go stale.*

### Fichiers / Files

| Fichier | Changement |
|---|---|
| `front/views_benchmarks.py` | **nouveau** — `BenchmarksViewSet` |
| `front/templates/front/benchmarks/` | **nouveau** — index, mesure, style |
| `front/urls.py` | routeur + un `re_path` explicite |
| `front/tests/test_route_des_benchmarks.py` | **nouveau** — 5 tests |

## Deux décisions

### Un `re_path` explicite, exception assumée

Le chemin d'une mesure porte des barres obliques
(`redaction/2026-08-19_….md`), qu'un `DefaultRouter` ne sait pas exprimer. La
vue reste un **ViewSet DRF** ; seul le routage est manuel — même motif que les
trois `path()` déjà présents dans `front/urls.py`.

### La vérification d'appartenance se fait APRÈS résolution

La vue prend un chemin dans l'URL. `resolve()` seul ne protège de rien : c'est
la **comparaison** avec la racine qui protège. Sans elle, `../../.env` serait
servi — et avec lui toutes les clés d'API. Un test le verrouille, sur cinq
formes d'échappement.

Le rendu passe par `bleach` avec une liste blanche qui **inclut les tableaux** :
c'est la forme même de ces mesures.

---

## Comment tester (à la main) / Manual test

1. Se connecter, ouvrir `/benchmarks/` → la liste, la plus récente en tête.
2. Cliquer une mesure → le markdown rendu, tableaux compris.
3. Un tableau large **défile dans son conteneur**, la page ne défile pas
   horizontalement.
4. `/benchmarks/voir/../.env` → **jamais** de 200, jamais de clé affichée.
5. En navigation privée (non connecté) → pas de 200.

**Reste à faire** : la vérification au navigateur, en clair **et** en sombre.
Les tokens employés (`--papier`, `--encre`, `--filet`, `--papier-creux`)
existent dans les deux thèmes, mais le rendu n'a pas été vu.
