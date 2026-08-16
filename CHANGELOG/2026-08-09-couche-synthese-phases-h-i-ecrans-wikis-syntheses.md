# Couche synthese, phases H-I : les ecrans wikis et syntheses

**Date :** 2026-08-09
**Migration :** Non

**Quoi / What :** la couche synthese devient VISIBLE (§ 10) :
- **Onglets reels** sur l'ecran carnet : Notes / Wikis / Syntheses
  dirigees (role tablist ARIA revenu avec le 2e vrai onglet, audit D8).
- **Taches carnet-niveau** (front/tasks.py) : `produire_un_wiki_task`
  (perimetre RECALCULE § 3.1.1), `produire_une_synthese_de_carnet_task`
  (multi-notes — la vue cree l'acte date et FIGE le perimetre AU MOMENT
  DU GESTE, la tache remplit), `proposer_une_maj_de_wiki_task` (des
  operations § 6 sur les ecartees, JAMAIS auto-appliquees, fraicheur
  addendum n°1), `verifier_les_citations_task` (§ 7 a la demande).
  Toutes sur le contrat phase C (marqueurs, CITATIONS_USED, perimetre
  obligatoire). NOUVELLE GARDE (constat sur GPT-4o-mini reel) : un
  article sans AUCUNE citation sur un perimetre non vide est REFUSE —
  un texte sans preuve n'est pas un succes.
- **Endpoints** (front/views_synthese.py) : WikiViewSet (liste/creer
  par carnet, article, mise_a_jour -> proposition -> appliquer,
  verifier), SyntheseViewSet (liste/creer par carnet — garde-fou § 3.3
  mecanique et DIT a l'utilisateur —, article, ecartees § 8 avec refus
  honnete des historiques, couverture § 9 par note, verifier, PAS de
  mise a jour : bouton desactive avec motif § 10), CitationViewSet
  (panneau de preuve : citation exacte, verdict AVEC provenance § 7.2,
  debat joint, etat de la source, retour a la source).
- **Phase I** : le diff des operations previsualise par UN PASSAGE A
  BLANC de l'applieur reel (jamais deux verites) — l'humain coche
  operation par operation, le replace montre l'AVANT (§ 6.4), les
  rejets mecaniques sont montres avec contenu conserve, les
  contestations perdues sont affichees apres application (relecture G).
- **Renvois [N] cliquables** : le HTML de l'article est re-rendu avec
  des ancres HTMX liees a LEUR SourceLink (couple paragraphe-extraction
  par bornes cibles) -> panneau de preuve.

Valide sur DONNEES REELLES (carnet public « Demonstration », GPT-4o-mini) :
synthese de carnet a 8 citations (verification reelle : 2 verifiees /
6 faibles, provenance posee), wiki a 9 citations apres renforcement de
la consigne de sourcage.

| Fichier | Changement |
|---|---|
| `front/views_synthese.py` | Nouveau : 3 ViewSets |
| `front/tasks.py` | + 4 taches + helpers partages + garde zero-citation |
| `front/urls.py` | Routes /wikis/, /syntheses/, /citations/ + collections carnet |
| `front/templates/front/corpus/` | liste_wikis, liste_syntheses, article + partials (preuve, ecartees, couverture, diff_operations, tache_lancee, erreur) |
| `front/templates/front/corpus/carnet_detail.html` | Onglets reels (tablist) |
| `front/tests/test_synthese_phase_h.py` | 16 tests |

### Migration
- **Migration necessaire / Migration required :** Non.

---

## Ce qui a été fait

Voir l'entrée CHANGELOG du 9 août (phases H-I). En bref : onglets réels
sur l'écran carnet, 4 tâches carnet-niveau, 3 ViewSets
(front/views_synthese.py), écran article avec renvois [N] cliquables →
panneau de preuve, écartées/couverture en `<details>` paresseux, diff
des opérations par passage à blanc de l'applieur (l'humain coche), et
la garde « zéro citation = refus ».

## Tests a réaliser

### Suites automatiques
```bash
docker exec hypostasia_dev_web python manage.py test \
  front.tests.test_synthese_phase_h --noinput
```

### Parcours réel (données de démonstration EN PLACE sur dev)
1. https://hyp.nasjo.fr/carnets/1/ (anonyme suffit — carnet public)
2. Onglet « Synthèses dirigées » → « Synthèse de démonstration du
   9 août » : 8 renvois [N] cliquables → panneau de preuve avec
   citation exacte, verdict + provenance (2 vérifiées / 6 faibles par
   GPT-4o-mini), débat, lien retour à la source.
3. Dérouler « Ce qui n'a pas été repris » et « Couverture de
   l'analyse ».
4. Onglet « Wikis » → « La gouvernance partagée » (9 citations).
5. Connecté avec l'écriture : « Proposer une mise à jour » sur le wiki
   → attendre la proposition → diff opération par opération (l'avant
   des replace affiché) → appliquer les cochées → tour incrémenté.
6. « Vérifier les citations » sur un article → verdicts avec provenance
   dans le panneau de preuve.

### Garde à connaître
- Un article généré SANS aucune citation (périmètre non vide) est
  refusé avec un message FALC — constaté en réel avec GPT-4o-mini
  avant le renforcement de la consigne.

## Limites connues (pour la bascule CSS / itérations)
- Le panneau de preuve est en bas d'article (aside), pas en panneau
  latéral overlay comme la maquette.
- Les états de vérification ne colorent pas les affirmations AU FIL DU
  TEXTE (data-verification de la maquette) — seulement le renvoi
  (data-etat) et le panneau.
- Les onglets n'affichent pas les compteurs wikis/synthèses, et l'état
  visuel actif ne migre pas après bascule HTMX.
- L'étalon corpus.html ne connaît pas encore les états source_debat /
  conteste / non_verifie (fiche phase G).
- Rapport de confrontation complet : voir l'agent maquette du 9 août
  (synthèse dans la conversation de session) + les améliorations UX/UI
  proposées.

