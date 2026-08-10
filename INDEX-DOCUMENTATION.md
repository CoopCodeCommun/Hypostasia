# Index de la documentation — Hypostasia V3

> **But de ce fichier** : point d'entrée unique pour toute session (humaine
> ou IA). Il range tous les documents par RÔLE, donne leur STATUT, et
> signale les pièges de fraîcheur. Tenu à jour le **10 août 2026**.
>
> **Ordre de lecture conseillé pour démarrer froid** :
> 1. la MÉMOIRE PERSISTANTE (voir tout en bas) — l'état vivant, le plus frais ;
> 2. ce fichier ;
> 3. `PRESENTATION-V3.md` (vue d'ensemble) **avec l'avertissement ci-dessous** ;
> 4. la spec du domaine sur lequel on travaille ;
> 5. `CHANGELOG.md` (les entrées récentes = l'état réel du code).

## ⚠️ Pièges de fraîcheur à connaître AVANT de faire confiance à un document

- **`PRESENTATION-V3.md` (9 août) SOUS-ESTIME l'avancement.** Il dit que le
  moteur ELEMENT « n'est pas branché » : c'est FAUX depuis les addenda BR-A→E
  (9-10 août) de `SPEC-ancrage-par-element-v2.md`. Pour l'état RÉEL du code,
  faire foi du CHANGELOG + des addenda datés des specs, pas de PRESENTATION-V3.
- **`PLAN/INSPIRATION_ATOMIC.md` (26 avril) IGNORE le moteur ELEMENT.** Il est
  antérieur, orienté vers le dépôt PROD `/mnt/tank/Gits/Hypostasia`. Ses idées
  (RAG, sourçage `[N]`, section_ops) restent valides mais sont **à réconcilier**
  avec l'architecture ELEMENT (ancrage par portions) avant d'être codées.
- **Décision de gouvernance du 10 août** (voir mémoire
  `decision-element-seul-moteur`) : le moteur ELEMENT devient le SEUL moteur,
  l'ANCIEN meurt (offsets, marge, pastilles). Toute spec qui décrit le double
  moteur (§ 9 de SPEC-ancrage) est à relire sous cet angle.
- **Vocabulaire « phase » AMBIGU** : SPEC-ancrage numérote A-K + addenda BR-A→E
  + U1-U5 ; SPEC-synthese numérote A-I ; SPEC-corpus numérote A-I ;
  `PLAN/PHASES/` numérote 1-29. « phase H » ne désigne PAS la même chose selon
  le document. Toujours préciser de quelle spec on parle.
- **`SPEC-ancrage § 2.2`** décrit `EtatAncrage` à 3 valeurs (EXACTE/RETROUVEE/
  DETACHEE) mais le CODE n'en a que 2 (ANCREE/DETACHEE) — la correction est
  dans l'encart de tête de la spec, pas au § 2.2.

---

## 1. Fondateurs (vue d'ensemble)

| Document | Rôle | Statut |
|---|---|---|
| `PRESENTATION-V3.md` | Présentation générale du produit, de l'architecture et de l'état | ⚠️ 9 août — sous-estime le branchement (voir pièges) |
| `GUIDELINES.md` | Conventions de code et de conduite du projet | ✅ référence |
| `README.md` (racine) | Démarrage du dépôt | ✅ |

## 2. Specs canoniques — l'état CIBLE par domaine (📌 = ce qu'on veut construire)

| Document | Domaine | Statut |
|---|---|---|
| `SPEC-ancrage-par-element-v2.md` | Le MOTEUR d'ancrage par élément (portions, scission/fusion, masquage, PDF §8.2, audio §8.3) + addenda datés BR-A→E, U1-U5, mesure D3 | 📌 IMPLÉMENTÉE A-G + branchée BR-A→F ; addenda en tête font foi ; §8.2/§8.3 (PDF/audio UI) = specs INSUFFISANTES pour coder (voir §5 ci-dessous) |
| `SPEC-corpus-base-carnet-note.md` | Carnets, bases, notes, catégories par relation, axes, permissions | ✅ IMPLÉMENTÉE A-I |
| `SPEC-synthese-carnet.md` | Wikis vivants & synthèses dirigées, sourçage `[N]`, vérification NLI, **§6 mise à jour par section_ops (diff)**, écartées/couverture | ✅ IMPLÉMENTÉE A-I ; §6 = la « mise à jour partielle façon Atomic », faite |
| `SPEC-selection-des-preuves.md` | Regroupement d'extractions par similarité (embeddings intra-carnet, PAS du RAG), oppositions, tri par le débat | 📌 SPÉCIFIÉE, écran NON codé (phases A-G) |

## 3. Spec de refonte transverse « Atomic » (⚠️ à réconcilier avec ELEMENT)

| Document | Rôle | Statut |
|---|---|---|
| `PLAN/INSPIRATION_ATOMIC.md` | Refonte inspirée d'Atomic. Contient : §4 pipeline (chunking markdown-aware, extraction Pydantic+instructor), §5 sourçage `[N]`, **§6 RAG complet via pgvector**, **§7 update incrémental section_ops**. Roadmap PHASE-30 à 36. | ⚠️ 26 avril, ignore ELEMENT, orienté PROD. §5/§7 = FAITS (dans la couche synthèse d'août). **§6 RAG = SPÉCIFIÉ mais NON implémenté** (pgvector absent) |

> **Le RAG N'EST PAS un trou total** : il est spécifié ici (§6). Mais c'est une
> spec séparée des 4 canoniques, non implémentée, et à réconcilier avec ELEMENT.
> Ce qui existe côté embeddings (`SPEC-selection-des-preuves`) sert le
> regroupement intra-carnet, PAS le retrieval — les deux ne doivent pas être
> confondus. `front/templates/.../recherche_semantique.html` est mort, à supprimer.

## 4. Étalon visuel — l'AUTORITÉ de comportement du front

| Fichier | Écran | Notes |
|---|---|---|
| `tmp/maquettes/maquette.html` | Lecture : gouttière + barre d'état, surlignage inline `mark.portion.hl-extraction`, panneau/drawer d'extractions, modes inspection/lecture, source pdf/audio | Autorité front. **Lecteur audio & viewer PDF y sont des MOCKS** (toast/placeholder), pas des références codables |
| `tmp/maquettes/corpus.html` | Carnet : facettes, axes, catégories, fil d'Ariane à bascule | Autorité front |
| `tmp/maquettes/selection-preuves.html` | Sélection des preuves (écran non codé) | Autorité front |
| `tmp/maquettes/donnees.js` | Modèle de données de référence ; son en-tête liste ce qui est MOCKÉ | Source unique de la maquette |
| `tmp/maquettes/index.html` | Sommaire des maquettes | — |
| `scripts/verifier_les_maquettes.py` | Contrôles Playwright | ⚠️ compare la maquette À ELLE-MÊME, PAS au rendu Django réel |

## 5. Cahiers des charges & plans de chantier

| Document | Chantier | Statut |
|---|---|---|
| `PLAN/branchement-moteur-ancrage-cahier-des-charges.md` | Branchement du moteur ELEMENT (BR-A→G, décisions D1-D5) | ✅ BR-A→F faits ; BR-G (PDF/audio UI) à cadrer |
| `PLAN/bascule-css-cahier-des-charges.md` + `bascule-css-etat-2026-08-09.md` | Portage du design maquette (lots T1-T10) | ✅ TERMINÉ |
| `PLAN/corpus-phase-f-cahier-des-charges.md` | Écran carnet | ✅ fait |
| `PLAN/audit-ux-ui-2026-08-08.md` | Backlog UX (D1-D16) | ⏳ P0 faits, **backlog P1 à solder** |
| `PLAN/A.6-refonte-websocket-{plan,spec}.md` | Refonte WebSocket | 🕰️ historique |
| `PLAN/A.8-statuts-binaires-fusion-templates-{plan,spec}.md` | Statuts binaires nouveau/commenté | 🕰️ historique (livré) |
| `PLAN/A.1`→`A.7-retrait-*.md` | Retraits de fonctionnalités (explorer, heatmap, mode focus, stripe, biblio analyseurs, reformulation) | 🕰️ historique (faits) |
| `PLAN/LANGEXTRACT_OVERRIDES.md` + `LangExtractReadMe.md` | Fork LangExtract | ✅ référence technique |

## 6. Mesures, recettes, confrontations (constats datés)

| Document | Contenu | Statut |
|---|---|---|
| `PLAN/mesure-D3-frontiere-audio-2026-08-10.md` | Mesure chiffrée du chunking audio (tour de parole = élément) | ✅ tranche l'INGESTION audio (pas le lecteur) |
| `PLAN/recette-connectee-2026-08-10.md` | Parcours réel LLM du carnet 1 (frictions B1-B4, F1-F10) | ✅ frictions soldées |
| `PLAN/confrontation-maquette-synthese-2026-08-09.md` | Confrontation écran synthèse ↔ maquette | ✅ P0 intégrés |
| `PLAN/REVUE_YAGNI_2026-05-01.md` | Revue de simplification | 🕰️ historique |

## 7. Fiches « A TESTER et DOCUMENTER/ » (livré par phase + comment tester)

Une fiche par phase livrée : quoi, comment tester, vérifications en base.
- Ancrage : `ancrage-par-element-phase-a.md`, `ancrage-par-element-phases-b-a-g.md`,
  `branchement-moteur-phases-br-a-b.md`, **`usage-moteur-element-u1-u3.md`** (U1-U4 + sécurité).
- Corpus : `corpus-phase-a`→`corpus-phase-g` (7 fiches).
- Synthèse : `synthese-phase-c`→`synthese-phase-g`, `synthese-phases-h-i-ecrans.md`.

## 8. Historique & brainstorming

| Document | Rôle |
|---|---|
| `CHANGELOG.md` | **Journal par phase — l'état RÉEL du code, source la plus fiable de « ce qui est fait »** |
| `PLAN/PHASES/PHASE-01`→`29` + `PHASES/INDEX.md` | Historique des phases 1-29 (avant le chantier ancrage/corpus/synthèse) |
| `PLAN/PLAN.md`, `PLAN/README.md` | Vue d'ensemble du dossier PLAN + roadmap (PHASE-30→36 : Atomic/RAG) |
| `PLAN/discussions/*.md` | Brainstorming, notes de design, retours de presse (8 fichiers) 🕰️ |

## 9. Ce qui reste à SPÉCIFIER avant de coder (trous confirmés par l'audit du 10 août)

- **Lecteur AUDIO** : `SPEC-ancrage §8.3` insuffisant (6 lignes, renvoie à une v1
  ABSENTE du dépôt) ; l'étalon marque « aucun lecteur audio n'existe ». À écrire :
  timeline diarisée réelle, bouton « suivre la lecture », `trouverLeBlocAlInstant`.
- **Lecteur PDF avec surlignage** : `SPEC-ancrage §8.2` = bon delta (3 corrections)
  mais SANS le socle (composant PDF.js, pagination, zoom, calque) ; étalon = stub toast.
- **RAG** : spécifié dans `INSPIRATION_ATOMIC §6` mais à réconcilier avec ELEMENT
  et non implémenté (pgvector absent).
- **Scission/fusion (UI)** : moteur + endpoint faits (BR-E), mais AUCUN geste dans
  la maquette — « l'opération n°1 » sur une diarisation n'a pas de référence visuelle.
- **Sélection des preuves** : écran entier absent (0 template/route/vue).

## 10. La mémoire persistante (l'état vivant, hors dépôt)

`~/.claude/projects/-mnt-tank-Gits-Hypostasia-dev/memory/` — index dans `MEMORY.md`.
À lire EN PREMIER à chaque session : elle porte l'état le plus frais, les décisions
(ex. `decision-element-seul-moteur`), et les pièges (`lecons-front-et-verification` :
Tailwind figé, cache templates, Docling OOM, sécurité AllowAny, ancres inline).
