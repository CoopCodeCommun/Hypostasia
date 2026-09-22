# La relecture des deux merges / Reviewing the two merges

**Date :** 2026-09-22
**Migration :** Non

## Résumé / Summary

**Quoi / What :** triple relecture (deux agents indépendants et une relecture
directe) du retrait de la passe de nuit, de l'estimation de coût, et des deux merges
qui ont suivi (`f320573` sur la machine A, `2f4da77` + `98c41e7` sur la machine B).
Aucun défaut bloquant. Une régression corrigée, trois tests ajoutés, la documentation
remise d'accord avec le code.
*/ Triple review of the nightly-pass removal, the cost estimate and both merges. No
blocker; one regression fixed, three tests added, docs brought back in line.*

**Pourquoi / Why :** deux merges successifs sur le même chemin — la mise à jour d'un
wiki, qu'une branche supprimait côté nuit et que l'autre enrichissait (provenance,
analyseur de rédaction). Ce genre de fusion casse à l'exécution, pas à la fusion.
*/ Two merges on the same path break at run time, not at merge time.*

### Ce qui a été corrigé / What was fixed

| # | Constat | Correction |
|---|---|---|
| 1 | **Régression du merge 1.** `borne_du_dernier_essai` prenait pour borne le tour `REPARATION_DE_TITRES` que la proposition écrit elle-même, juste avant d'appeler le modèle. Sur un article hérité à `###`, le tour accepté comptait alors **0** nouveauté et aucune note déclenchante (historique et mail vides). | la borne ignore les tours de réparation — test `test_la_reparation_des_titres_ne_masque_pas_les_nouveautes`, vu échouer (`0 != 1`) avant la correction |
| 2 | Aucun test ne suivait le **vrai chemin** de l'estimation (clic, job, tâche) avec un rédacteur non défaut : le test existant appelait la proposition sans job, donc avec la même expression que l'estimation. | `LeVraiCheminDuGesteTest` : wiki à rédacteur choisi, pièce de prompt reconnaissable, `POST mise_a_jour/`, tâche exécutée, tokens comparés au prompt réellement envoyé |
| 3 | **Test perdu au merge 2** : un ancien job de nuit ne doit pas allumer le badge des tâches. | `front/tests/test_les_vestiges_de_la_nuit.py`, avec un témoin (un job ordinaire, lui, l'allume) |
| 4 | Documents faux : le test manuel n° 2 du merge comparait des tokens (`data-tokens`) à des caractères (`ProvenanceDeProduction.longueur`) ; « ne pas lancer `migrate` » ne suffisait pas, puisqu'il part seul au démarrage ; `tail -2` du CHANGELOG du 21 ; `PLAN/PASSATION.md` sans entrée depuis le 1er septembre. | corrigés ; entrée datée du 22 septembre en tête de la passation |
| 5 | La nuit décrite au présent (docstring `Wiki`, `hypostasis_extractor/views.py`, un test de permissions, les fixtures de la phase C) ; `provenance.py` affirmait qu'aucun geste ne porte d'analyseur ; deux docstrings promettaient un lien tour → provenance que rien n'écrit. | commentaires au présent ; encarts datés dans quatre notes `PLAN/TODO` |

### Vérifié, sans défaut / Verified

- L'estimation compte **le même prompt** que la tâche : même constructeur
  (`rediger_le_prompt_de_mise_a_jour`), même analyseur (celui du wiki, sinon le défaut
  du type — la vue pose `analyseur_id` depuis ce champ), mêmes écartées figées avant la
  réparation des titres. Vérifié ligne à ligne par les trois relectures, et désormais
  épinglé par le test du point 2.
- La nuit a disparu du code actif (beat, tâches, supervisord, Makefile, `bin/`,
  `.env.example`, `AGENTS.md`). Graphe des migrations linéaire (core → 0082,
  hypostasis_extractor → 0041). Aucun `Co-Authored-By` depuis `05a7ff9`.
- Aucune base déployée ne peut porter l'ancien nom `core.0077_retrait_de_la_passe_de_nuit` :
  ces commits n'ont été poussés qu'avec le merge 1, déjà renuméroté ; la seule base
  qui l'avait (le poste A) a été recréée.

### Laissé en l'état, signalé / Left as is

`prod-update` ne relance pas `celery_worker_juge_local` ; `.config/pulse/*` est suivi
par git ; les wikis antérieurs à `core.0082` n'ont pas d'analyseur figé (ils suivent le
défaut du moment) ; deux compteurs différents s'appellent « tours » (liste et article) ;
« jamais sous-évalué » (estimation) est vrai à quelques tokens près ; le commit
`2f4da77` seul n'est pas cohérent (sa migration arrive en `98c41e7`).

### Fichiers modifiés / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `front/tasks.py` | `borne_du_dernier_essai` ignore `REPARATION_DE_TITRES` ; docstrings de provenance |
| `front/tests/test_appliquer_un_tour_de_wiki.py` | test de la borne |
| `front/tests/test_estimation_de_la_mise_a_jour.py` | `LeVraiCheminDuGesteTest` |
| `front/tests/test_les_vestiges_de_la_nuit.py` | **neuf** — 2 tests |
| `core/models.py`, `hypostasis_extractor/models.py`, `hypostasis_extractor/views.py`, `hypostasis_extractor/services/provenance.py`, `hypostasis_extractor/tests/test_qui_peut_modifier_un_prompt.py`, `front/tests/test_synthese_phase_c.py` | commentaires et docstrings (aucun `help_text` touché : pas de migration) |
| `CHANGELOG/2026-09-22-le-merge-du-retrait-de-la-nuit.md` | ordre des opérations sur la base ; test manuel n° 2 |
| `CHANGELOG/2026-09-21-la-mise-a-jour-des-wikis-redevient-un-geste.md` | `showmigrations` |
| `PLAN/PASSATION.md` | entrée du 22 septembre ; trois passages caducs annotés |
| `PLAN/TODO/2026-08-22-borner-…`, `2026-08-23-deriver-…`, `2026-08-23-la-provenance-…`, `2026-08-23-le-prompt-de-mise-a-jour-…` | encarts datés |

---

## Comment tester (à la main) / Manual test

### Test 1 — la raison d'un tour sur un article hérité

1. Prendre un wiki dont l'article porte encore un `###` (ou en poser un à la main).
2. Ajouter une note au carnet, l'analyser.
3. « Mettre à jour », accepter une opération.
4. Déplier « Historique » : le tour accepté nomme la note qui l'a appelé. Un tour
   « Réparation des niveaux de titre » le précède, sans rien raconter.

### Vérifs automatiques

```bash
make test-suite S="front.tests.test_appliquer_un_tour_de_wiki front.tests.test_estimation_de_la_mise_a_jour front.tests.test_les_vestiges_de_la_nuit"
```
