# Session A.7 : Retrait Reformulation IA + Restitution IA + Restitution manuelle

**Date :** 2026-05-02
**Migration :** Oui

**Quoi / What :** retrait integral des fonctionnalites Reformulation IA, Restitution IA
et Restitution manuelle (code mort en pratique : 0/134 extractions utilisaient ces
champs en DB, sections invisibles dans l'UI). Conservation totale de la Synthese
(seul mecanisme IA reellement utilise) et du versionning de pages (utilise par la
Synthese).

**Pourquoi / Why :** suite logique du brainstorming YAGNI 2026-05-01 (cf.
`PLAN/REVUE_YAGNI_2026-05-01.md`) et de la refonte WebSocket A.6. Audit DB +
Chrome a confirme l'absence d'usage : aucune entite avec `texte_reformule`,
aucune avec `texte_restitution_ia`, aucune `restitution_page` non-null sur les
134 extractions de l'instance live. Aucun bouton Reformuler/Restituer/Pre-remplir-IA
visible dans l'UI courante (sidebar droite cachee + sections conditionnees a des
champs DB vides). Le code mort cumule represente une dette technique non
justifiee qui complique la refonte RAG a venir.

### Changements principaux / Main changes

1. **2 taches Celery supprimees / 2 Celery tasks removed** : `reformuler_entite_task`
   (~110 lignes), `restituer_debat_task` (~115 lignes) dans `front/tasks.py`.
2. **9 actions ViewSet retirees / 9 ViewSet actions removed** : 3 actions
   reformulation IA (`choisir_reformulateur`, `previsualiser_reformulation`,
   `reformuler`), 4 actions restitution IA (`choisir_restituteur`,
   `previsualiser_restitution`, `generer_restitution`, `restitution_ia_status`),
   1 action restitution manuelle (`creer_restitution`), 1 action `fil_discussion`
   + helper `_re_rendre_fil_discussion`.
3. **3 serializers retires / 3 serializers removed** : `RunReformulationSerializer`,
   `RunRestitutionSerializer`, `RestitutionDebatSerializer`.
4. **7 templates supprimes / 7 templates deleted** : `reformulation_en_cours.html`,
   `choisir_reformulateur.html`, `confirmation_reformulation.html`,
   `restitution_ia_en_cours.html`, `choisir_restituteur.html`,
   `confirmation_restitution.html`, `fil_discussion.html`.
5. **13 champs DB retires / 13 DB fields removed** via migration consolidee :
   - `ExtractedEntity` : `texte_reformule`, `reformule_par`, `reformulation_en_cours`,
     `reformulation_lancee_a`, `reformulation_erreur`, `restitution_page`,
     `restitution_texte`, `restitution_date`, `restitution_ia_en_cours`,
     `restitution_ia_lancee_a`, `restitution_ia_erreur`, `texte_restitution_ia`
   - `ExtractionJob` : `est_reformulation`
6. **Enum `TypeAnalyseur` reduit de 4 a 2 valeurs** : suppression de `REFORMULER`
   et `RESTITUER`. Reste `ANALYSER` + `SYNTHETISER`.
7. **Modele vestige `core.Reformulation` supprime** : zero usage en code et zero
   ligne en DB. Heritage d'une architecture TextBlock-based abandonnee.
8. **Related_name renomme** : `Page.parent_page.related_name` passe de `restitutions`
   a `versions_enfants` pour coherence semantique (la Synthese aussi cree des
   versions enfants).
9. **Templates branches nettoyes** : sections `{% if reformulation_* %}` /
   `{% if restitution_* %}` retirees de `vue_commentaires.html` ; bouton hover
   `btn-commenter-extraction` (qui pointait vers `fil_discussion`) retire de
   `extraction_results.html` et `bottom_sheet_extraction.html` ; logique de timeout
   reset des reformulations bloquees (~50 lignes) retiree de l'action
   `vue_commentaires` ; contexte `analyseurs_reformuler_existent` /
   `analyseurs_restituer_existent` retire des actions ViewSet.
10. **JS nettoye / JS cleaned** : handler clic `.restitution-ancre` retire de
    `hypostasia.js` (pastille violette inline orpheline) ; options select
    `<option value="reformuler">` et `<option value="restituer">` retirees du
    SwAlert d'edition d'analyseur.
11. **Templates de l'editeur d'analyseur mis a jour** : `analyseur_editor.html`
    (2 options `<option>` retirees), `analyseur_item.html` (couleur badge
    `bg-amber-400` pour reformuler retiree), `modale_prompt_readonly.html` (2
    branches `{% elif %}` retirees + ajout d'une branche `synthetiser` manquante).
12. **Vestige template** : `core/templates/core/includes/sidebar_items_partial.html`
    referencait `block.reformulations.all` (related_name du modele supprime). Aurait
    plante au prochain rendu de la sidebar — VIEW 3 (`reformulations`), VIEW 7
    (`edit_reformulations`) et bouton toolbar « Re-ecriture » retires (~75 lignes).
13. **3 fichiers fixtures JSON nettoyes** des 13 champs DB retires :
    `exemple_deliberation.json`, `demo_alignement_versions.json`, `demo_completes.json`.
14. **Fixture analyseur "FALC" (type reformuler) retiree** de `charger_fixtures_demo.py`.
15. **Tests morts retires** : 1 classe `Phase24IntegrationReformulationMockTest` +
    4 methodes individuelles dans test_phases.py + adaptation de 3 methodes de tests
    survivants (`Phase04ModifierCommentaireTest`, `Phase04SupprimerCommentaireTest`,
    `Phase24ResolveModelParamsAnthropicTest`) qui referençaient des chaines obsoletes.

### Migrations DB / DB migrations

- `hypostasis_extractor/migrations/0028_a7_retrait_reformulation_restitution_fields.py` :
  13 RemoveField + 1 AlterField (TypeAnalyseur).
- `core/migrations/0033_a7_retrait_modele_reformulation.py` : 1 DeleteModel.
- `core/migrations/0034_a7_renommer_related_name_versions_enfants.py` : 1 AlterField
  (related_name).

### Solde net / Net balance

- 28 fichiers modifies, 7 templates supprimes, 3 nouvelles migrations
- **+304 / −4794 = −4490 lignes nettes**
- Cumul cleanup A.1 → A.7 : ~12900 lignes net retirees en 7 sessions

### Verification anti-regression / Anti-regression check

- Snapshot tests pre-A.7 : 748 tests, 728 OK, 0 fail, 20 errors (preexistantes E2E
  playwright + script orphelin)
- Snapshot tests post-A.7 : **743 tests, 723 OK, 0 fail, 20 errors** (memes 20
  preexistantes — zero regression introduite)
- `manage.py check` : System check identified no issues (0 silenced)
- Test UI Chrome : page `/lire/4/` se charge proprement (33 cartes inline + 59
  pastilles + onglets V1/V2/V3/V4 + Synthese deliberative). Endpoint
  `/extractions/vue_commentaires/?page_id=4` rend 77 KB sans aucune ref obsolete.
  Aucun lien hx-get/hx-post avec URL obsolete dans le DOM.

### Hors perimetre / Out of scope (conserve intact)

- Tache Celery `synthetiser_page_task` et helper `_construire_prompt_synthese`
- Type analyseur `SYNTHETISER` + 3 analyseurs synthetiseurs en fixture
  (Charte, Mathemagique, Synthese deliberative)
- Versionning Page (`parent_page`, `version_number`, `version_label`)
- Carte inline `carte_inline.html` + bouton "Commenter" inline (pure JS local)
- Systeme de commentaires (`CommentaireExtraction`) + statuts de debat +
  action `changer_statut`
- Helper `core/llm_providers.py:appeler_llm` (utilise par la Synthese)

### References / References

- Plan d'execution : `PLAN/A.7-retrait-reformulation-restitution.md`
- Spec maitre : `PLAN/REVUE_YAGNI_2026-05-01.md`
- Sessions precedentes A.1-A.6 : retrait Explorer / Heatmap / Mode focus /
  Stripe / Bibliotheque analyseurs / refonte WebSocket

