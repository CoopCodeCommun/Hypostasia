# Recette connectee : les trois defauts BACK sont corriges (B1, B2, B3)

**Date :** 2026-08-10
**Migration :** Non

**Contexte / Context :** la recette connectee du carnet 1 (session
Opus, PLAN/recette-connectee-2026-08-10.md) a revele 4 defauts back
dans la couche synthese livree la veille. Trois sont corriges en TDD :

**B1 — les compteurs du wiki se contredisaient** (23 renvois annonces,
25 affiches) : l'indexation absorbait les doublons d'un marqueur dans
un meme paragraphe (un lien par couple, § 4.4) mais le TEXTE gardait
toutes les occurrences. Le doublon sort desormais du texte aussi
(`indexer_les_citations`, nouveau compteur `doublons_absorbes` dans le
bilan) : tous les compteurs de l'ecran coincident. Verification faite
au passage : le clic, lui, pointait deja le BON lien (mapping par
extraction + position, zero orphelin sur le wiki 3 reel) — le defaut
etait le comptage, pas l'attribution.

**B2 — les operations de mise a jour au contenu reduit a un marqueur
nu** (`"contenu": "[[ext:35284]]"` → paragraphes orphelins [4]) : une
operation dont le contenu, marqueurs retires, est vide est REJETEE
avec motif FALC (`section_ops._controler_les_sources`) — le modele
doit proposer un passage redige ET source.

**B3 — la troncature du volet des ecartees etait muette** (« 458 »
au resume, 200 lignes affichees) : le volet affiche desormais le TOTAL
et annonce « les 200 premieres sont affichees ».

**B4 consigne, pas code** : la pauvrete du sourçage (2 extractions
citees sur 465) est un probleme de PROMPT — B2 forcera deja le modele
a rediger ; les `marqueurs_retires` sont signales dans raw_result
depuis la phase C mais n'ont pas de surface UI. A retravailler avec
les consignes de production.

Tests : `core.tests.test_synthese_citations` (3 nouveaux, 38 verts),
`core.tests.test_section_ops` (3 nouveaux, 27 verts),
`front.tests.test_synthese_phase_h` (1 nouveau, 17 verts) +
non-regression synthese (52 + 25 verts).
Fichiers : `core/services/synthese.py`, `core/services/section_ops.py`,
`front/views_synthese.py`, `partials/ecartees.html`.

