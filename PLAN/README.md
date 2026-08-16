# PLAN/ — la conception, vivante et archivée

> **La carte du dépôt n'est pas ici : c'est `AGENTS.md`, à la racine**, chargé
> à chaque session. Ce README-ci ne décrit que le dossier `PLAN/`.
>
> Revu le 16 août 2026.

## Ce qui est vivant

| Fichier | Ce qu'il porte | État |
|---|---|---|
| `PASSATION.md` | Le document de reprise de session : environnement, état de la base, chantiers restants, pièges | ✅ **à lire en premier pour travailler** |
| `INSPIRATION_ATOMIC.md` | La refonte inspirée d'[Atomic](https://github.com/kenforthewin/atomic). § 5 (sourçage `[N]`) et § 7 (`section_ops`) sont **faits**, dans la couche synthèse d'août. **§ 6 — le RAG via pgvector — est spécifié et NON implémenté.** | ⚠️ 26 avril : antérieur au moteur ELEMENT, à réconcilier avec lui avant de coder |
| `LANGEXTRACT_OVERRIDES.md` | Les surcharges du fork LangExtract et la procédure de vérification à chaque montée de version | ✅ référence technique |
| `specs/` | **Les quatre specs canoniques** — ancrage, corpus, synthèse, sélection des preuves. Leur statut est dans `specs/README.md` |
| `PLAN.md` | La spec produit d'origine, 3 356 lignes (mesurées le 16 août 2026) | 🕰️ mai 2026 — référence de fond, pas l'état du code |

Deux dossiers de pièces jointes : `References/` (documents externes cités par
les specs) et `Documents exterieurs/`.

## Ce qui est archivé

`archive/` ne contient que du **fait, du livré ou du daté**. On y va pour
comprendre pourquoi une chose est comme elle est, jamais pour savoir quoi faire.

| Chemin | Contenu |
|---|---|
| `archive/A.1` → `A.8` | Les retraits de fonctionnalités (explorer, heat map, mode focus, Stripe, bibliothèque d'analyseurs, reformulation) et la refonte WebSocket. **Tous livrés.** |
| `archive/PHASES/` | Les phases 01 à 29-normalize, plus leur `INDEX.md`. L'historique d'avant le chantier ancrage/corpus/synthèse. |
| `archive/discussions/` | Brainstorming, notes de design, retours de presse, arbitrages YAGNI. |
| `archive/cahiers-des-charges/` | Bascule CSS, écran carnet, branchement du moteur d'ancrage. **Chantiers terminés.** |
| `archive/mesures-et-recettes/` | Constats datés : mesure D3 sur la frontière audio, recette connectée, audit UX/UI, confrontation à la maquette. |
| `archive/REVUE_YAGNI_2026-05-01.md` | La revue de simplification du 1er mai. |

**Ces documents ne sont pas mis à jour.** Un chiffre qu'on y lit vaut pour le
jour où il a été écrit — leur nom porte souvent la date pour cette raison.

## Où va le reste

| Ce qu'on cherche | Où |
|---|---|
| Ce qui a changé, et comment le vérifier à la main | `CHANGELOG/` |
| L'état cible d'un domaine | `PLAN/specs/` |
| Le comportement de référence d'un écran | `front/static/front/maquettes/` |
| Les conventions de code | `AGENTS.md` (= `CLAUDE.md`) et le skill `djc` |
| Les défauts connus non traités | `CHANGELOG/DEFAUTS-DIFFERES.md` |

## Préférences du mainteneur

- **Jamais de `Co-Authored-By`** dans un commit.
- **Jamais de commande git** lancée par un agent — ni `commit`, ni `add`, ni
  `checkout --`, ni `stash`, ni `reset`, ni `clean`. Le mainteneur commite
  lui-même.
- **Stack opinionée** : `ViewSet` explicites, serializers DRF, HTMX, noms
  verbeux, commentaires bilingues FR/EN. Voir le skill `djc`.
- **FALC autant dans l'UX que dans le code** — ne pas sur-ingénierer.
- **Alpha sans utilisateurs réels** : on peut casser, à condition de le dire.
