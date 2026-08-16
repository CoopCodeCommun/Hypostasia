# Couche synthese, phase B : le lien de citation ecrit

**Date :** 2026-08-09
**Migration :** Oui

**Quoi / What :** le prealable a tout le sourcing (SPEC-synthese § 4) :
- `SourceLink` gagne `section`, `ordre_dans_la_section`,
  `etat_de_verification` (par PAIRE affirmation-source),
  `etat_de_la_source` (presente/supprimee/detachee), et
  `TypeLien.CITE` (migration core.0048). `page_cible` EST l'article
  citant ; `ancrage_source` = la premiere portion (§ 4.5).
- `indexer_les_citations()` : le parseur `[[ext:<id>]]`. Le markdown est
  la verite, les liens son index, reconstruits a chaque enregistrement.
  Un marqueur inexistant ou hors perimetre est RETIRE du texte et
  SIGNALE — jamais garde en silence. Sections aux titres `##` seulement
  (addendum n°3). Bornes cibles = le paragraphe citant.
- Signal `pre_delete` sur ExtractedEntity : citee par une DIRIGEE ->
  suppression refusee (`SuppressionRefuseeSourceCitee`) ; citee par des
  wikis seulement -> autorisee, citations basculees SUPPRIMEE. Jamais
  d'orphelinage silencieux.
- Propagation de derive : une ancre passee DETACHEE par la
  reconciliation detache la citation qui la pointait (§ 4.2 fin).

8 tests (`core/tests/test_synthese_citations.py`). L'ecriture DANS la
tache part en phase C avec la reecriture complete de
`synthetiser_page_task` (note typee + marqueurs + ligne CITATIONS_USED).

### Relecture / Review
Relecture adverse passee (9 aout), correctifs appliques avec leurs tests
(17 au total) :
- **Garde § 4.2 avant les purges** (le bloquant) : les 3 sites de purge
  (analyse_par_element, front/tasks re-extraction, run_langextract_job)
  appellent `verifier_qu_aucune_dirigee_ne_cite_les_extractions()` AVANT
  de supprimer — refus propre en amont, plus d'exception au milieu d'une
  purge. Les vues de suppression (extraction, page entiere) repondent un
  message FALC (« citee par une synthese adoptee... ») au lieu d'un 500.
- **Parseur robuste** : CRLF normalise, titre colle a son paragraphe
  reconnu (« ## Titre\\nPhrase », courant chez les LLM), un lien par
  couple (paragraphe, extraction) meme si le marqueur est duplique,
  marqueur dans un titre retire ET signale (nom de section propre).
- **La reindexation ne blanchit pas une derive** : une ancre deja
  DETACHEE donne un lien DETACHEE.
- **Propagation complete** : le masquage et la reingestion detachent
  aussi les citations (helper partage), plus seulement la reconciliation.
- Spec § 4.2 corrigee (views.py:904 = ExampleExtraction, pas une
  extraction de corpus).
- Decision documentee : « l'ecriture dans la tache » part en phase C avec
  la reecriture complete de synthetiser_page_task — la phase B livre la
  bibliotheque et TOUTES ses gardes, branchees aux flux existants.

### Migration
- **Migration necessaire / Migration required :** Oui — core.0048,
  appliquee sur dev.

