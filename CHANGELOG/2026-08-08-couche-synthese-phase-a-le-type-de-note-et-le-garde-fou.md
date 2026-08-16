# Couche synthese, phase A : le type de note et le garde-fou

**Date :** 2026-08-08
**Migration :** Oui

**Quoi / What :** `TypeDeNote` (note/wiki/synthese) sur Page (un champ,
pas une propriete : la regle doit etre une clause filter),
`core/services/synthese.py:notes_sources_du_carnet()` — le garde-fou
« une synthese n'est JAMAIS source d'une autre synthese », exerce par
test (N notes + M syntheses → N). Migration 0047 : 292 syntheses
existantes typees (reperage par versionnage ; 0 par raw_result — les
jobs anciens n'ont pas le marqueur). Le filtre corpus passe du
versionnage au TYPE (dependance C.6, = estUneSource de l'etalon).

**Design relu avant d'ecrire** (consigne du proprietaire) : la note
d'architecture de la memoire Atomic + l'etalon corpus.html § 8 (articles
= sections → paragraphes → sources, numerotation a l'affichage).
**4 trous de spec releves et consignes en addendum de
SPEC-synthese-carnet.md** : controle optimiste de concurrence sur les
propositions (updated_at), ligne de controle anti-troncature
(CITATIONS_USED), niveaux de titre exposes (## seulement), et la
justification du rejet PAR OPERATION (pas de point de reprise chez nous,
contrairement a Atomic).

### Migration
- **Migration necessaire / Migration required :** Oui — core.0046 (champ)
  et 0047 (donnees, reversible), appliquees sur dev.

