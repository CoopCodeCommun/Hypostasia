# Revue YAGNI / sur-ingénierie des features Hypostasia — Design

**Date** : 2026-05-01
**Auteur** : Jonas Turbeaux (Code Commun) + brainstorming Claude Code
**Méthode** : skill `superpowers:brainstorming` — mix pragmatique, 6 questions ciblées
**Objectif** : passer chaque feature livrée et planifiée au tamis « besoin documenté
vs idée non validée », puis trancher YAGNI / sur-ingénierie / besoin / trou.

## Contexte

Le projet Hypostasia est en alpha. Le PLAN.md cumule 28+ phases livrées (~865 tests),
plus une refonte v4 (« inspiration Atomic ») qui ajouterait 12+ phases supplémentaires
(chunking, RAG pgvector, chat agentique, sociales × RAG). Sans tri, la roadmap dérive
vers le « plan d'un produit à 50 personnes sur 3 ans » que le plaidoyer Bull lui-même
identifie comme un risque de dispersion.

**Le brief utilisateur :** « on veut coder sur des besoins, pas des idées ».

## Sources mobilisées (atomes Atomic)

- `51fabee2` — Plaidoyer Institut Bull × Code Commun × Hypostasia
- `0dcf9922` — Conférence Sallantin Bull, 28/04/2026
- `4ee95ce2` — CR LowCal × Hypostasia, 22/04/2026
- `8b24e41e` — Arguments synthèse délibérative produits par Hypostasia (verbatim Bull)
- `3e892efd` — Chat Zoom Bull
- `ab6c43e6` — PHASE-29 synthèse drawer (état d'alpha 0.3.1)
- `2d2af937` — Les 30 hypostases classées par famille épistémique

## Grille d'évaluation

Une feature est **un besoin** si elle est explicitement demandée dans :
- Une conférence (Bull, LowCal)
- Le plaidoyer Code Commun × Bull
- Un retour utilisateur terrain (Ephicentria — preuve de concept)

Une feature est **une idée** si elle est issue de :
- Critique UX d'un designer (Yves) sans validation utilisateur
- Inspiration Atomic (« puisque Atomic le fait »)
- Pure spéculation produit

Décisions YAGNI prises *avant* le brainstorming (matin du 2026-05-01) déjà documentées
dans `PLAN/discussions/YAGNI 2026-05-01.md` :

1. Heat map du débat (PHASE-19) → OUT
2. Mode focus / mode lecture (PHASE-17 partiel) → délégué à Firefox Reader View
3. Bibliothèque d'analyseurs vue dédiée (PHASE-26b) → fusionnée menu config
4. Explorer (PHASE-25d / 25d-v2) → OUT (pas réseau social)

## Décisions du brainstorming (afternoon 2026-05-01)

### Q1 — Modèle de déploiement

**Décision : SaaS + self-hosted en parallèle (déjà codé, on garde le multi-tenant).**

Conséquence : l'auth Django, les visibilités 3 niveaux, les groupes et les invitations
email **restent**. Mais le self-hosted reste un livrable cible (cf. Q6 et T2 de la
section trous).

### Q2 — Stripe / crédits prépayés (PHASE-26h)

**Décision : retiré entièrement. OpenRouter direct, l'utilisateur met sa clé.**

Raison : la couche commerciale Stripe contredit le positionnement « commun numérique
gouverné collectivement » du plaidoyer §6. Le SaaS Code Commun se finance autrement
(cotisation SCIC, dons, contrat de soutien) — pas par micro-paiement à l'analyse.

**Code à supprimer** :
- `front/services_stripe.py`
- `front/views_credits.py`
- `front/views_stripe_webhook.py`
- Modèles `Credit`, `CreditPurchase`, `StripeWebhookEvent` + migrations
- Templates `front/includes/credits_*.html`
- Gate avant analyse (PHASE-26h)
- Tests `test_phase26h*.py`
- Variables d'env Stripe dans `.env.example`
- Routes URL `/credits/`, `/stripe/webhook/`

**Code à garder** : aucun héritage côté `Analyseur` ne dépend de Stripe.

### Q3 — Wizard de synthèse 5 étapes (PHASE-28 prévue)

**Décision : retiré. Le flow drawer livré (PHASE-28-light + PHASE-29) est l'unique chemin.**

Raison : aucun verbatim Bull/LowCal ne demande un wizard. Jean dit le contraire
(principe 3) : « il ne faut pas leur demander de vérifier par obligation ». Le flow
drawer compact a déjà passé le test sur 2 conférences (Bull, LowCal) et Ephicentria.

Si une review post-synthèse devient un vrai besoin remonté, on ré-évalue.

### Q4 — Bloc RAG / Atomic-style (PHASES 30-38)

**Décision : périmètre resserré.**

| Phase | Sort | Justification |
|---|---|---|
| **30 — Sourçage `[N]` auto** | ✅ Garde | Plaidoyer §6.1 : auditabilité de la grammaire |
| **31 — Chunking markdown-aware** | ✅ Garde | Réduit pastilles ~30 → 5-10/page (UX) |
| **32 — OpenRouter + instructor** | ✅ Garde | Validé en Q2 |
| **38 — Refonte pipeline 1 chunk = 1 extraction** | ✅ Garde | Suppression LangExtract (dette technique) |
| **33 — RAG socle pgvector** | ✅ Garde | Recherche sémantique = vraie valeur produit |
| **34 — RAG features (recherche, doublons, alignement sémantique)** | ✅ Garde | Vraie valeur produit (cross-documents) |
| **MCP server Hypostasia** *(nouveau)* | ✅ Garde | Remplace 35, expose la KB à tout LLM externe |
| **35 — Chat agentique interne** | ❌ OUT | Remplacé par MCP (interopérabilité > chat-bot interne) |
| **36 — Update incrémental section_ops** | ⏸️ Reporté | Optimisation tokens, pas blocant |
| **37a — Notifications « ce qui te concerne »** | ⏸️ Reporté | YAGNI tant que volume contributeurs faible |
| **37b — Cartographie sémantique contributeurs** | ❌ OUT | Idée non validée |
| **37c — Détection contradiction cross-doc** | ❌ OUT | Idée délicate (faux positifs) |
| **37d — Heat map sémantique** | ❌ OUT | PHASE-19 retirée ce matin |
| **37e — Géométrie 7e facette sémantique** | ⏸️ Reporté | Dépend formalisation Jean (Q5) |
| **37f — Suggestion analyseur à l'import** | ❌ OUT | Trivial via MCP si besoin |

**Conséquence implicite** : `PHASE-29-normalize` devient obsolète après PHASE-38
(Pydantic + JSON Schema valident à la source). À supprimer à ce moment-là.

### Q5 — Géométrie navigable du débat (« le dodécaèdre »)

**Décision : on ne code rien.**

Raison : la géométrie est **la science** du produit (plaidoyer §6.2). Elle relève de
Jean Sallantin, Dominique Luzeaux et Antsa Avo. Coder une vue radar 6 axes ou une
matrice 30 hypostases sans formalisation mathématique préalable serait inventer notre
propre objet — exactement ce que le plaidoyer reproche à un éditeur commercial.

**Action** : poser la question explicitement à Jean en CR de session.

### Q6 — Self-hosted Docker (livrable Bull)

**Décision : reporté post-refonte RAG.**

Raison : on stabilise d'abord la stack PostgreSQL + pgvector + Redis + Celery + Channels,
puis on package proprement (modèle Atomic-self-hosted : dépôt dédié, docker-compose,
Traefik, .env.example). Faire l'inverse multiplierait les retours-arrière.

**Calendrier indicatif** : ~3-4 mois (refonte RAG) puis 3-5 jours (extraction self-hosted).

## Trou unique retenu (les autres long terme)

**T2 — Migration LLM européens.**

Conséquence directe du plaidoyer §6.6 (« passer en production sur un modèle hébergé
hors d'Europe est incompatible avec la définition même d'un commun numérique »).

OpenRouter rend la migration triviale techniquement (changer `model=` dans l'appel).
Le travail réel est qualitatif :

- Tester chaque modèle sur le pipeline d'extraction (qualité hypostases) :
  Mistral Large, Lumo (Proton Suisse), Linagora LUCIE / OpenLLM-France,
  modèles hébergés LIRMM Montpellier
- Construire une matrice qualité × coût × souveraineté
- Valider avec Jean / Antsa la grammaire des hypostases sur chaque modèle

**Effort estimé** : 3-5 jours, à mener en parallèle de la refonte RAG (PHASE-32 OpenRouter
est le prérequis technique).

**Trous reportés long terme (mention pour mémoire)** :
- T1 — Anonymisation systématique des contributions
- T3 — Livraison « demain matin » (Celery scheduling + email)
- T4 — Référentiel hypostases publiquement révisable
- T5 — Pilote commission parlementaire / procès assises

## Périmètre confirmé (déjà livré, on n'y touche pas)

- Modèles métier (Page, ExtractedEntity, Commentaire, Dossier, AIModel,
  Analyseur, ExtractionJob, PageEdit, SourceLink…)
- Auth Django + visibilité 3 niveaux + groupes + invitations email (multi-tenant)
- Drawer de synthèse + extraction (PHASE-26g, 28-light, 29)
- Alignement V1/V2 par hypostase (PHASE-27b)
- Dashboard de consensus (PHASE-14)
- Layout marginalia + bottom sheet mobile (PHASE-21)
- Charte visuelle (Wong, 4 polices, 8 familles d'hypostases)
- Édition extraction + permissions (PHASE-26f)
- Filtre contributeur (PHASE-26a-bis + ux)
- Statuts de débat 6 (PHASE-26c)
- Traçabilité PageEdit + diff side-by-side (PHASE-27a + 27b)
- Notifications WebSocket
- Onboarding + tooltips hypostases (PHASE-16) — *retirer onglet « Explorer »*
- Raccourcis clavier (PHASE-17, **sans** le `L`)
- Tests existants (~865), à adapter à ~70%

## Ordre des sessions de cleanup et de refonte

### Phase A — Cleanup (sessions courtes, 1-3 jours chacune)

1. **Session A.1 — Retrait Explorer** (PHASE-25d-v2, le plus volumineux : ~10 fichiers
   templates + view + URLs + sérializer + onboarding)
2. **Session A.2 — Retrait Heat map** (~5 fichiers : `utils.py` calcul score,
   `views.py` flag, `marginalia.js` toggle, CSS, raccourci `H`, tests)
3. **Session A.3 — Retrait Mode focus** (~3 fichiers : `keyboard.js` raccourci `L`,
   CSS `.mode-focus`, bouton toolbar) — vérifier Firefox Reader View en parallèle
4. **Session A.4 — Retrait Stripe / crédits** (le plus impactant : views_credits,
   services_stripe, webhook, modèles, migrations, templates, gate analyse, tests)
5. **Session A.5 — Fusion Bibliothèque analyseurs dans menu config** (refactoring
   plus que retrait, à scoper)

### Phase B — Refonte RAG resserrée (~3-4 mois, ordre suggéré)

1. **PHASE-32** — OpenRouter + instructor (socle)
2. **PHASE-31** — Chunking markdown-aware (prérequis)
3. **PHASE-38** — Refonte pipeline 1 chunk = 1 extraction (pivot, supprime LangExtract)
4. **T2** — Migration LLM européens (en parallèle, dès que 32 est posée)
5. **PHASE-30** — Sourçage `[N]` automatique (rend triviale PHASE-27c)
6. **PHASE-33** — RAG socle pgvector
7. **PHASE-34** — RAG features (recherche sémantique, doublons, alignement)
8. **Nouvelle phase MCP server Hypostasia** (`semantic_search`, `read_page`,
   `read_extraction`, `list_dossiers`, `synthese_status` à minima)

Suppression `PHASE-29-normalize` après PHASE-38.

### Phase C — Self-hosted (post-Phase B)

- Création dépôt `hypostasia-self-hosted` (modèle Atomic-self-hosted)
- Docker-compose, Traefik, bind-mount data, .env.example, README

## Questions à remonter à Jean / équipe scientifique

1. **Géométrie navigable** : quel objet mathématique exact ? Radar à N axes,
   dodécaèdre 12 faces, espace projectif, autre ? Quelles dimensions vous semblent
   indispensables à mesurer ?
2. **Migration LLM européens** : préférences entre Mistral, Lumo, Linagora LUCIE,
   LIRMM ? Critères de validation ?
3. **Self-hosted Bull** : calendrier acceptable côté Jean / souscripteurs Bull pour
   le livrable Docker (~3-4 mois post brainstorming) ?

## Métriques de succès

Cette revue est réussie si, dans un mois :

- Les 5 sessions de cleanup (A.1 à A.5) sont effectuées, le code est plus simple,
  les tests passent encore (~70% de réutilisation)
- La PHASE-32 (OpenRouter + instructor) est livrée
- Une matrice qualité Mistral / Lumo / LUCIE / LIRMM est commencée (T2)
- Une question écrite est partie à Jean / Dominique / Antsa sur la géométrie

## Notes finales

Ce document est volontairement **opinioné**. Les décisions reflètent l'état des
besoins documentés au 2026-05-01. Si un retour Bull / Ephicentria / LowCal contredit
une décision (ex : « on a vraiment besoin du chat agentique interne »), on ré-évalue.
La règle YAGNI ne dit pas « jamais », elle dit « pas tant qu'on n'a pas besoin ».
