# Session A.8 : Statuts binaires + drawer-only + FALC additionnel

**Date :** 2026-05-02
**Migration :** Oui

**Quoi / What :** simplification massive de la couche debat — `ExtractedEntity.statut_debat`
passe de 6 valeurs (nouveau, discutable, discute, consensuel, controverse, non_pertinent)
a **2 valeurs binaires** (`nouveau`, `commente`) auto-derivees par signal Django depuis
l'existence de commentaires. Refonte UX en **drawer-only** : suppression de la carte
inline (fusion vers `_card_body.html` unique). Retrait additionnel FALC : edition
d'extraction, edition/suppression de commentaire, onglet "Tous les commentaires",
bouton "Replier la carte", tri "Statut de debat".

**Pourquoi / Why :** suite logique du brainstorming YAGNI 2026-05-01 et de la session
A.7. Les 6 statuts manuels (consensuel/controverse/etc.) demandaient un effort cognitif
non valide par l'usage : sur l'instance live, la majorite des entites restaient en
"nouveau" et la curation manuelle etait quasi-inexistante. La logique de gating
"synthese bloquee si <80% consensus" empechait de lancer des syntheses dont l'utilisateur
voulait quand meme tester la qualite. La carte inline + drawer = 2 templates a maintenir
pour le meme objet ; la fusion supprime la divergence. Les autres retraits FALC (edition
d'extraction, edition/suppression de commentaire, onglet doublon, replier) ciblent des
features a usage faible/nul.

### Changements principaux / Main changes

1. **Signal Django auto-update** : nouveau `hypostasis_extractor/signals.py`. Le statut
   `statut_debat` est auto-derive de l'existence de commentaires (post_save +
   post_delete sur `CommentaireExtraction`). Plus de set manuel.
2. **Enum reduit** : `StatutDebat` passe de 6 valeurs a 2 (`NOUVEAU`, `COMMENTE`).
   Migration data + AlterField.
3. **Fusion `non_pertinent` -> `masquee`** : le statut `non_pertinent` disparait, ses
   instances en DB sont fusionnees dans `masquee=True`. Le champ `masquee` devient
   independant du statut.
4. **Action `changer_statut` retiree** : 4 boutons UI supprimes de la carte.
5. **Refonte drawer-only** : suppression de `carte_inline.html` + JS de creation
   dynamique de carte sous les paragraphes. Clic pastille -> ouvre drawer + scroll
   vers la carte concernee. **Le drawer est l'unique endroit pour voir et commenter
   une extraction.**
6. **`_card_body.html` unique** : retrait du parametre `mode`, partial unique pour
   le drawer (et le bottom_sheet mobile). Le formulaire commenter cible
   `closest .extraction-content` avec swap `outerHTML` -> les commentaires apparaissent
   immediatement sans toast ni rechargement.
7. **Pastille triangle orange** : le statut `commente` s'affiche en triangle orange
   (clip-path CSS) au lieu d'un cercle vert. Plus distinctif visuellement et coherent
   avec le code couleur "discussion en cours".
8. **Layout commentaires Facebook-like** : pseudo en haut (gras), commentaire en
   dessous. Plus lisible que l'ancien layout horizontal avec typo Srisakdi.
9. **Dashboard consensus simplifie** : graphique 6 segments remplace par barre binaire
   `commentees / total`. Le bouton "Lancer la synthese" reste present (sans gate).
10. **`_calculer_consensus`** simplifie de ~30 a ~10 lignes.
11. **Action `vue_commentaires`** retiree + template + onglet "Tous les commentaires"
    (redondant avec le drawer).
12. **Actions `modifier_commentaire` + `supprimer_commentaire`** retirees + serializers.
13. **YAGNI edition d'extraction** : actions `editer` + `modifier`, helper
    `_peut_editer_extraction`, bouton "Modifier" et modale d'edition retires entierement.
14. **Tri "Statut de debat"** retire du selecteur du drawer (plus de sens binaire).
15. **Bouton "Replier la carte"** (▴) retire (drawer a son ✕).
16. **Bouton "tâches" (A.6)** : distingue maintenant `analyse` vs `synthese` dans le
    dropdown, lien "Voir le resultat" pointe vers la page V2/V3 creee pour les syntheses.
17. **CSS** : 6 paires de variables `--statut-*` reduites a 2.
18. **Marginalia.js** : matrice 6 statuts -> 2 (couleur orange `#E69F00` pour
    `commente`).
19. **Templates aide** (`aide_desktop`, `aide_mobile`, `onboarding_vide`) simplifies :
    section explicative des 6 statuts -> bloc binaire + mention "le statut est automatique".
20. **Fixtures** (`charger_fixtures_demo.py`) : valeurs riches `statut_debat` retirees
    -> `nouveau` (le signal complete a `commente` quand les commentaires sont crees).

### Migrations DB / DB migrations

- `hypostasis_extractor/migrations/0029_a8_recalcul_statuts_fusion_non_pertinent.py` :
  RunPython qui fusionne `non_pertinent` -> `masquee=True` puis recalcule tous les
  statuts depuis les commentaires (option A : recalcul pur).
- `hypostasis_extractor/migrations/0030_a8_alter_statut_debat_choices.py` : AlterField
  qui reduit l'enum a 2 valeurs.

### Solde net / Net balance

- 8 phases (1-8) + 4-bis : **~-2950 lignes nettes** sur cette session
- Cumul cleanup A.1 -> A.8 : ~15500 lignes net retirees en 8 sessions

### Verification anti-regression / Anti-regression check

- Snapshot tests pre-A.8 : 743 tests / 723 OK / 0 fail / 20 errors préexistantes
- Snapshot tests post-A.8 : **690 tests / 658 OK / 0 fail** / 20 errors préexistantes (mêmes E2E + test_analysis)
- 53 tests obsoletes retires/adaptes, **aucune regression introduite**
- Test UI Chrome : page lecture, drawer Analyses (avec hypostases visibles, commentaires
  inline, bouton commenter), creation/suppression commentaire (signal -> statut auto),
  dashboard consensus avec bouton synthese, mobile (bottom_sheet) — tous OK.

### Hors perimetre / Out of scope (conserve intact)

- Synthese deliberative + analyseurs synthetiseurs
- Versionning de pages (`parent_page`, `versions_enfants`)
- Bouton "Historique" + "Comparer V1↔V2" + tabs versions
- Suppression d'extraction (`btn-supprimer-extraction`) + masquer/restaurer
- Filtre contributeurs avec dimming
- Bouton "tâches" A.6 + signal WebSocket + dropdown + marquer-lue
- Systeme de commentaires (`CommentaireExtraction`)

### References / References

- Spec A.8 : `PLAN/A.8-statuts-binaires-fusion-templates-spec.md`
- Plan d'execution : `PLAN/A.8-statuts-binaires-fusion-templates-plan.md`
- Spec maître YAGNI : `PLAN/REVUE_YAGNI_2026-05-01.md`

