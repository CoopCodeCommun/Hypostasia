# Les mesures servies en HTML / Benchmark notes served as HTML

**Date :** 2026-08-19
**Migration :** Non.

## Résumé / Summary

**Quoi / What :** `/benchmarks/` liste les comptes rendus de mesure du dossier
`benchmarks/`, et `/benchmarks/voir/<chemin>.md` en rend un en HTML.
**Publiques** — pas d'authentification.
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
| `front/templates/front/includes/onboarding_vide.html` | deux liens sur la page d'accueil |
| `front/tests/test_route_des_benchmarks.py` | **nouveau** — 7 tests |

## Les deux adresses, sur la page d'accueil

`Mesures` → `/benchmarks/` et `Maquettes` →
`/static/front/maquettes/maquette.html`, en bas du guide « Découvrir ». On les
cherchait à la main dans le dépôt.

**ET NON DANS LA BARRE D'OUTILS**, où ils avaient d'abord été posés : son
conteneur gauche est en `overflow-hidden`, et deux liens de plus y étaient
**rognés sans qu'aucune erreur ne le dise**.

**Sans `hx-get`, délibérément** : ce sont des pages **autonomes**, pas des
partials. Un swap dans `#zone-lecture` les afficherait sans leur style ni leur
navigation.

**Un seul lien vers les maquettes**, celui de `maquette.html` : son en-tête est
l'autorité et renvoie lui-même vers `corpus.html` et `selection-preuves.html`.
Trois liens ici en feraient trois copies à tenir à jour.

**Visibles par tous, et la route l'est aussi.** Les deux vont ensemble : un lien
montré à un visiteur anonyme qui le mènerait à un mur de connexion serait une
promesse cassée.

**Ce que ça rend public** : les tarifs des modèles, les choix techniques, et
surtout les **défauts mesurés du produit** — 85 % de verbatim à l'extraction,
14 à 23 % de citations introuvables, un juge qui sous-note. Pour un outil dont
l'objet est la traçabilité, les cacher serait contradictoire. **Aucune clé,
aucune donnée d'utilisateur** : seuls les `.md` sous `benchmarks/` sont servis,
et la garde de chemin reste en place — un test vérifie qu'un anonyme ne peut
pas plus atteindre `../.env` qu'un connecté.

**Aucune classe Tailwind neuve** : celles employées sont exactement celles du
lien « Carnets » voisin — le build est figé, une classe absente du bundle est
inerte et ne lève aucune erreur.

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
