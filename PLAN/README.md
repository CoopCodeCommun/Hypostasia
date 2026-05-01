# PLAN/ — Index général de la documentation Hypostasia

> Toute la documentation de conception du projet. Spec produit, phases
> d'implémentation, notes de design, décisions architecturales. Lisible par un
> humain qui découvre et par un agent IA (Claude Code) qui implémente.

---

## En 30 secondes

**Hypostasia** est une plateforme de **lecture délibérative collective**.
Un groupe lit un texte, l'IA en extrait des passages clés (hypostases — 30 catégories
en 8 familles), commentaires et débats par passage avec statuts évolutifs
(consensuel / discutable / discuté / controversé / non pertinent / nouveau). Quand le
seuil 80% de consensus est atteint, l'IA peut générer une nouvelle version (V2)
chaînée à l'originale.

**Stack** : Django 6 + DRF + HTMX + Tailwind + PostgreSQL 17 + Redis + Celery.

**État** : alpha, sans utilisateurs réels. Refonte planifiée (PHASES 30-38) inspirée
d'[Atomic](https://github.com/kenforthewin/atomic) pour adopter les patterns RAG +
sourçage `[N]` + chunking markdown-aware + section_ops.

---

## Comment utiliser cette documentation

### Si tu es un humain qui découvre

Lecture conseillée dans l'ordre :

1. **`/README.md`** (à la racine du projet) — overview + install
2. **`/CLAUDE.md`** — règles d'architecture strictes (priorité haute)
3. **`/GUIDELINES.md`** — patterns d'implémentation détaillés
4. **`PLAN/INSPIRATION_ATOMIC.md`** — la spec de refonte v4 (où va le projet)
5. **`PLAN/PHASES/INDEX.md`** — où on en est (suivi des phases)
6. **`PLAN/PLAN.md`** — la spec originale historique (~3200 lignes, optionnel pour
   la profondeur)

### Si tu es un agent IA (Claude Code) qui implémente une phase

1. Lire **`/CLAUDE.md`** + **`/GUIDELINES.md`** d'abord (conventions strictes)
2. Lire **`PLAN/INSPIRATION_ATOMIC.md`** en entier (décisions architecturales)
3. Lire **`PLAN/PHASES/INDEX.md`** pour identifier les dépendances de la phase à faire
4. Lire le fichier **`PLAN/PHASES/PHASE-XX.md`** correspondant
5. Implémenter en respectant le skill `stack-ccc` et les conventions Django/HTMX

---

## Carte de la documentation

```
/                                           ← racine du projet
├── README.md                               Overview public + install
├── CLAUDE.md                               Règles strictes pour agents IA
├── GUIDELINES.md                           Patterns d'architecture
├── AGENTS.md                               (alias de CLAUDE.md)
└── PLAN/                                   ← TOUTE la doc de conception est ici
    │
    ├── README.md                           ← TU ES ICI (index général)
    │
    ├── INSPIRATION_ATOMIC.md ⭐            Spec de refonte v4 (2107 lignes)
    │                                       Décisions tranchées + 9 squelettes de
    │                                       phases (PHASE-30 à 38). À lire en
    │                                       priorité pour comprendre où va le projet.
    │
    ├── PLAN.md                             Spec originale historique (3219 lignes)
    │                                       Référence vivante du projet, état actuel
    │                                       de chaque composant, problèmes identifiés.
    │                                       Plus ancien que INSPIRATION_ATOMIC.md.
    │
    ├── LANGEXTRACT_OVERRIDES.md            ⚠️ DÉPRÉCIÉ — sera supprimé en PHASE-38
    │                                       (suppression de LangExtract)
    │
    ├── PHASES/                             Plan d'implémentation phase par phase
    │   ├── INDEX.md                        Sommaire + suivi d'avancement
    │   ├── PHASE-01.md                     Phases livrées (01 à 29-normalize)
    │   ├── PHASE-02.md
    │   ├── ...
    │   ├── PHASE-29-normalize.md
    │   └── (PHASE-30 à 38 à créer — squelettes dans INSPIRATION_ATOMIC.md Annexe A)
    │
    ├── discussions/                        Brainstorming et notes de design historiques
    │   ├── idea.md                         Idées éparses (très court)
    │   ├── design dodecaedre.md            Concept "géométrie du débat"
    │   ├── notes design.md                 Critique designer UX
    │   ├── notes design suite.md           Critique UX exhaustive avec mockups ASCII
    │   ├── remarques générales.md          Critique CTO + CEO
    │   └── design discussion 3             Discussion design supplémentaire
    │
    └── References/                         Documents externes de référence
        └── exemple alignement.pdf          Exemple de tableau d'alignement par hypostase
                                            (cas d'usage différenciateur du produit)
```

---

## État du projet

### Phases livrées (alpha en cours, ~25 phases sur 28)

Voir `PLAN/PHASES/INDEX.md` pour le détail. En résumé :

| Domaine | Statut |
|---|---|
| Socle technique (Phase 1 historique) | ✅ Livré (PHASE-01 à 23) |
| Providers IA + analyseurs (Phase 3-4 historique) | ✅ Livré (PHASE-24, 26b, 26g, 26h) |
| Users + partage + visibilité 3 niveaux + invitations (Phase 2 historique) | ✅ Livré (PHASE-25, 25b, 25c, 25d, 25d-v2) |
| Filtres contributeur + statuts + accessibilité Wong | ✅ Livré (PHASE-26a, 26a-bis, 26c, 26d, 26e, 26f) |
| Traçabilité (modèles + diff + synthèse light) | ✅ Livré (PHASE-27a, 27b, 28-light) |
| Normalisation des attributs LLM | ✅ Livré (PHASE-29-normalize) |
| Traçabilité enrichie (SourceLinks manuels, fil de réflexion) | ⏳ Reportée (PHASE-27c, 27d, 27e à faire — partiellement remplacée par sourçage `[N]` PHASE-30) |
| Wizard synthèse complet | ⏳ À reconsidérer (PHASE-28-full reportée) |

### Phases attendues — refonte v4 (planifiée)

Spec complète : `PLAN/INSPIRATION_ATOMIC.md`. Squelettes prêts à dérouler dans
**Annexe A** du même document.

| # | Titre | Effort | Dépendances |
|---|---|---|---|
| **PHASE-31** | Chunking markdown-aware (méthode rasoir style Atomic) | M | aucune |
| **PHASE-32** | OpenRouter + instructor (provider LLM unifié, structured outputs) | S | PHASE-24 |
| **PHASE-38** | Refonte pipeline extraction Atomic-style (1 chunk = 1 extraction, suppression LangExtract) | L | PHASE-31, 32 |
| **PHASE-30** | Sourçage `[N]` automatique des synthèses délibératives | M | PHASE-28-light, 32 |
| **PHASE-33** | RAG socle (pgvector + pipeline d'embedding) | L | PHASE-31, 32 |
| **PHASE-34** | RAG features (recherche sémantique, doublons, alignement sémantique) | L | PHASE-33 |
| **PHASE-36** | Update incrémental section_ops (synthèses) | L | PHASE-30 |
| **PHASE-35** | Chat agentique avec la base | L | PHASE-34 |
| **PHASE-37+** | Sociales × RAG (6 sous-phases indépendantes) | S à M | PHASE-34 |

**Calendrier estimé** : 2-3 mois pour la refonte complète + 1-2 mois pour les sociales.

---

## Workflow type — démarrer une nouvelle session

### Pour implémenter une phase existante

```
1. Lire /CLAUDE.md + /GUIDELINES.md
2. Lire PLAN/PHASES/INDEX.md (état des phases)
3. Lire PLAN/PHASES/PHASE-XX.md (la phase visée)
4. Si refonte v4, lire aussi la section correspondante de PLAN/INSPIRATION_ATOMIC.md
5. Brainstormer les ambiguïtés avec l'utilisateur
6. Implémenter en respectant skill stack-ccc
7. Mettre à jour PLAN/PHASES/INDEX.md (cocher la phase, ajouter date + commit hash)
```

### Pour créer une nouvelle phase de la refonte v4

```
1. Lire PLAN/INSPIRATION_ATOMIC.md (en particulier l'Annexe A pour le squelette)
2. Copier le squelette de la phase concernée dans un nouveau fichier PLAN/PHASES/PHASE-XX.md
3. Étoffer avec contexte, fichiers concernés, critères de validation, vérification navigateur
4. Soumettre à l'utilisateur pour validation
5. Implémenter
6. Documenter dans INDEX.md
```

### Pour reprendre un projet froid (nouvelle session)

```
1. Lire ce README.md (PLAN/README.md)
2. Lire /CLAUDE.md + /GUIDELINES.md
3. Lire PLAN/INSPIRATION_ATOMIC.md sections 0-3 (décisions + nouveau modèle)
4. Lire PLAN/PHASES/INDEX.md pour l'état d'avancement
5. Demander à l'utilisateur : "Sur quelle phase on travaille ?"
```

---

## Préférences utilisateur (importantes)

- **Pas de `Co-Authored-By`** dans les commits (l'utilisateur veut l'attribution sole)
- **Pas de commandes git automatiques** (cf. `/CLAUDE.md` section 8)
- **Stack opinionée à respecter** (cf. `/GUIDELINES.md` sections 1-5) — ViewSet
  explicite, Serializers DRF, HTMX, noms verbeux, commentaires bilingues FR/EN
- **FALC autant UX que code** — pas sur-ingéniérer
- **Refactoring profond > from scratch** (décision validée le 2026-04-26)
- **Alpha sans utilisateurs réels** — on peut casser librement

---

## Liens externes

- **Atomic** (référence d'inspiration) : https://github.com/kenforthewin/atomic
  - Cloné en local lecture seule à `/mnt/tank/Gits/atomic/`
  - Fork de l'utilisateur : https://github.com/Nasjoe/atomic
- **Hypostasia** (ce projet) : `/mnt/tank/Gits/Hypostasia/`

---

## Méta : qui maintient ce README ?

Ce fichier doit être mis à jour quand :
- Une nouvelle catégorie de document est créée dans `PLAN/`
- Une phase majeure est livrée (mettre à jour le tableau "État du projet")
- Une décision architecturale change (référencer le doc qui la documente)
- Un document devient obsolète/déprécié (le marquer ici)

**Dernière mise à jour** : 2026-04-26 (création + structure post-décision refonte v4).
