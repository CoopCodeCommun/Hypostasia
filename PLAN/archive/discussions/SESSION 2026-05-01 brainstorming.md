# Session brainstorming Hypostasia — 2026-05-01

> **Doc de continuité de session.** À lire en premier si tu es Claude Code et que tu
> reprends cette conversation sur une autre machine. Tout ce qui a été décidé,
> tout ce qui a bougé dans le repo, tout ce qui reste à faire.

## Contexte de la session

- **Quand** : 2026-05-01, après-midi
- **Où** : machine de Jonas (jonas@…/mnt/tank/Gits/Hypostasia)
- **Pourquoi** : challenger les features prévues et déjà implémentées avec la grille
  « besoin documenté vs idée non validée ». Brief utilisateur littéral : *« on veut
  coder sur des besoins, pas des idées »*.
- **Méthode** : skill `superpowers:brainstorming`, mode mix pragmatique avec
  6 questions ciblées (option C de la skill).
- **Outils** : MCP Atomic (`semantic_search`, `read_atom`) pour relire les
  conférences Bull/LowCal/plaidoyer avant la session.

## Ce qui s'est passé en amont (matinée du 2026-05-01)

Avant le brainstorming, 4 décisions YAGNI prises sur retours d'usage :

1. **Heat map du débat** (PHASE-19) → OUT
2. **Mode focus / mode lecture** (PHASE-17 partiel) → délégué Firefox Reader View
3. **Bibliothèque d'analyseurs vue dédiée** (PHASE-26b) → fusionnée menu config
4. **Explorer / page de découverte** (PHASE-25d / 25d-v2) → OUT (pas réseau social)

Ces décisions sont documentées dans `PLAN/discussions/YAGNI 2026-05-01.md`.
Annotations DEPRECATED ajoutées dans :
- `PLAN/PHASES/INDEX.md` (section YAGNI en tête + statuts mis à jour)
- `PLAN/PLAN.md` (Étapes 1.11, 1.15, 4.1, 4.1b, section Page d'engagement)
- `PLAN/INSPIRATION_ATOMIC.md` (section 8.4 + ligne 37d)
- En-têtes des squelettes `PHASE-17.md`, `PHASE-19.md`, `PHASE-25d.md`,
  `PHASE-25d-v2.md`, `PHASE-26b.md`

## Atomes Atomic mobilisés (lus en intégralité)

- `51fabee2` — Plaidoyer Institut Bull × Code Commun × Hypostasia (v0.2)
- `0dcf9922` — Conférence Sallantin Bull, 28/04/2026 (verbatim)
- `4ee95ce2` — CR LowCal × Hypostasia, 22/04/2026
- `8b24e41e` — Arguments synthèse délibérative produits par Hypostasia (Bull)
- `3e892efd` — Chat Zoom Bull
- `ab6c43e6` — PHASE-29 Hypostasia synthèse drawer (état alpha 0.3.1)
- `2d2af937` — Les 30 hypostases classées par famille épistémique

## Brainstorming — les 6 questions Q1-Q6

### Q1 — Modèle de déploiement

**Réponse Jonas : C** (SaaS + self-hosted en parallèle, déjà codé).

→ Multi-tenant gardé : auth Django, visibilités 3 niveaux, groupes, invitations email.

### Q2 — Stripe / crédits prépayés (PHASE-26h)

**Réponse Jonas : C** (retiré entièrement, OpenRouter direct).

→ Suppression à venir : `services_stripe`, `views_credits`, webhook, modèles Credit,
migrations, gate analyse, templates `credits_*.html`, tests `test_phase26h*.py`.

### Q3 — Wizard de synthèse 5 étapes (PHASE-28 prévue)

**Réponse Jonas : A** (retiré).

→ Le flow drawer livré (PHASE-28-light + PHASE-29) reste l'unique chemin.

### Q4 — Bloc RAG / Atomic-style (PHASES 30-38)

**Réponse Jonas : B+ avec ajout MCP** (la recherche sémantique donne énormément de
valeur ; rajout d'un MCP server pour remplacer souplement le chat agentique interne).

→ Garde : 30, 31, 32, 38, 33, 34 + nouvelle phase MCP server Hypostasia.
→ OUT : 35 (chat agentique), 37b, 37c, 37f.
→ Reporté : 36, 37a, 37e (dépend Jean).
→ 37d était déjà OUT (matin).

### Q5 — Géométrie navigable du débat (« le dodécaèdre »)

**Réponse Jonas : A** (on ne code rien tant que Jean+Dominique+Antsa n'ont pas formalisé).

### Q6 — Self-hosted Docker (livrable Bull)

**Réponse Jonas : C** (reporté post-refonte RAG, on stabilise la stack d'abord).

## Trous identifiés et tri

Présentés en section 4 du brainstorming. Décision Jonas : **on ne garde que T2**.

| # | Trou | Statut |
|---|---|---|
| **T1** — Anonymisation systématique | Long terme |
| **T2** — Migration LLM européens (Mistral, Lumo, Linagora, LIRMM) | ✅ Actif, en parallèle de la refonte RAG |
| **T3** — Restitution « demain matin » (Celery scheduling + email) | Long terme |
| **T4** — Référentiel hypostases publiquement révisable | Long terme |
| **T5** — Pilote commission parlementaire / procès assises | Long terme |

## Spec produite

**Fichier** : `/mnt/tank/Gits/Hypostasia/PLAN/REVUE_YAGNI_2026-05-01.md`

Contient :
- Contexte, sources, grille d'évaluation
- Les 6 décisions Q1-Q6 avec justifications
- Le trou unique retenu T2
- Le périmètre confirmé (déjà livré, intouché)
- L'ordre suggéré des sessions de cleanup et de refonte
- Les questions à remonter à Jean

Auto-revue effectuée : aucun placeholder, cohérence interne OK, scope adapté
(c'est une revue de cadrage, pas un plan d'implémentation).

## Plan d'action concret pour la prochaine session

### Phase A — Cleanup (sessions courtes)

1. **A.1 — Retrait Explorer** *(le plus volumineux)*
   - `front/views_explorer.py` (suppression complète)
   - 6 templates `front/includes/explorer_*.html`
   - Routes `/explorer/`
   - `ExplorerFiltresSerializer`
   - Onboarding : retirer onglet « Explorer les dossiers »
   - Liens HTMX explorer dans toolbar/sidebar
   - `Phase25dExplorerRechercheTest` et tests E2E associés

2. **A.2 — Retrait Heat map**
   - `front/utils.py` calcul score
   - `front/views.py` flag heatmap
   - `marginalia.js` toggle
   - CSS variables `--heatmap-*`, classe `.heatmap-active`
   - Raccourci `H` dans `keyboard.js`
   - Tests

3. **A.3 — Retrait Mode focus** (vérifier Firefox Reader View en parallèle)
   - Raccourci `L` dans `keyboard.js`
   - CSS `.mode-focus`, `.mode-focus-active`
   - Bouton focus toolbar
   - Tests E2E focus

4. **A.4 — Retrait Stripe / crédits** *(le plus impactant)*
   - `services_stripe.py`, `views_credits.py`, `views_stripe_webhook.py`
   - Modèles + migrations
   - Templates `credits_*.html`
   - Gate analyse PHASE-26h
   - Tests
   - Variables d'env Stripe
   - Routes `/credits/`, `/stripe/webhook/`

5. **A.5 — Fusion Bibliothèque analyseurs dans menu config**
   - À scoper avec Jonas (refactoring plus que retrait)

### Phase B — Refonte RAG resserrée (~3-4 mois)

Ordre suggéré :

1. PHASE-32 — OpenRouter + instructor (socle)
2. PHASE-31 — Chunking markdown-aware (prérequis)
3. PHASE-38 — Refonte pipeline 1 chunk = 1 extraction (pivot)
4. T2 — Migration LLM européens (parallèle)
5. PHASE-30 — Sourçage `[N]` automatique
6. PHASE-33 — RAG socle pgvector
7. PHASE-34 — RAG features (recherche sémantique cross-documents)
8. **Nouvelle phase MCP server Hypostasia**
   - À minima : `semantic_search`, `read_page`, `read_extraction`,
     `list_dossiers`, `synthese_status`
   - Conséquence : plus besoin de coder un chat agentique interne (PHASE-35
     restée OUT). Tout LLM externe (Claude Desktop, Claude Code, etc.) peut
     consommer Hypostasia via MCP.

Suppression `PHASE-29-normalize` après PHASE-38.

### Phase C — Self-hosted (post-Phase B)

- Création dépôt `hypostasia-self-hosted` sur le modèle `Nasjoe/atomic-self-hosted`
- Docker-compose, Traefik, bind-mount data, .env.example, README

## Questions à remonter à Jean / Dominique / Antsa

1. **Géométrie navigable** : quel objet mathématique exact ? Radar à N axes,
   dodécaèdre 12 faces, espace projectif, autre ? Quelles dimensions vous semblent
   indispensables à mesurer ? (= Q5 du brainstorming)

2. **Migration LLM européens** : préférences entre Mistral, Lumo (Proton/Suisse),
   Linagora LUCIE / OpenLLM-France, modèles hébergés LIRMM Montpellier ? Critères
   de validation (qualité d'extraction des hypostases, coût, vitesse, souveraineté
   d'hébergement) ?

3. **Self-hosted Bull** : calendrier acceptable côté Jean / souscripteurs Bull pour
   le livrable Docker (~3-4 mois post brainstorming) ?

## Checklist de reprise (pour la prochaine session Claude Code)

Si tu reprends cette conversation sur une autre machine :

1. **Lire ce document en premier** (tu y es).
2. **Lire la spec validée** : `PLAN/REVUE_YAGNI_2026-05-01.md`.
3. **Lire la note YAGNI matinale** : `PLAN/discussions/YAGNI 2026-05-01.md`.
4. **Vérifier l'état git** :
   ```bash
   git -C /mnt/tank/Gits/Hypostasia status
   git -C /mnt/tank/Gits/Hypostasia log --oneline -10
   ```
   Pour savoir ce qui a été commité depuis (le user gère git manuellement,
   ne pas commiter pour lui).
5. **Demander au user** où il en est et par quelle session il veut commencer
   (plutôt A.1 Explorer si la spec est encore fraîche).
6. **Si le user veut directement écrire un plan d'implémentation**, invoquer
   `superpowers:writing-plans` (la skill brainstorming l'a explicitement listée
   comme la transition naturelle après spec validée).

## Préférences utilisateur (à respecter)

- **Pas de `Co-Authored-By` dans les commits** (mémoire user)
- **Pas de commandes git automatiques** — Jonas gère son git manuellement
- **Stack opinionée à respecter** : Django 6 + DRF (ViewSet explicite, jamais
  ModelViewSet) + HTMX + Tailwind + PostgreSQL + Redis + Celery + Channels.
  Conventions FALC, FR/EN bilingue dans les commentaires.
- **Refactoring profond préféré au from scratch** (décision validée 2026-04-26)

## Fin

C'est tout. Le brainstorming a duré ~1h, on a tranché 6 décisions structurantes,
on a allégé la roadmap d'au moins 5 phases (35, 37b, 37c, 37f + Stripe + wizard
synthèse) et on a un cap clair pour les 3-4 prochains mois : cleanup → refonte
RAG resserrée → self-hosted Docker.

L'objectif initial du user — *« coder sur des besoins, pas des idées »* — est
matérialisé.
