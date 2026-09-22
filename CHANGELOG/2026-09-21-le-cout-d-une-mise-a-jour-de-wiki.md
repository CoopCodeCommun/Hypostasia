# Le coût d'une mise à jour de wiki, annoncé avant le clic / A wiki update's cost, shown before the click

**Date :** 2026-09-21 → 2026-09-22
**Migration :** Non

## Résumé / Summary

**Quoi / What :** la modale « Mettre à jour » d'un article de wiki annonce désormais un
coût estimé : « Coût estimé : environ 0,03 € — environ N tokens envoyés à <modèle>, pour
M extractions non reprises ». Tarif inconnu, ou comptage impossible : « non mesuré »,
jamais « 0 € ». L'estimation n'est calculée qu'à l'ouverture de la modale, et seulement
quand « Relancer » est actif. Un échec de l'estimation ne bloque jamais le geste.
*/ The wiki "update" dialog now shows an estimated cost, computed by the server when the
dialog opens; a failed estimate never blocks the gesture.*

**Pourquoi / Why :** depuis le retrait de la passe de nuit, la mise à jour est un geste
humain facturé ; celui qui clique doit voir ce qu'il engage. Le prompt envoie toutes les
extractions écartées, donc son coût grossit avec le carnet (question ouverte n° 1 de
l'addendum du 21 septembre).
*/ Updating is now a billed human gesture: whoever clicks should see the cost.*

**Ce que l'estimation compte :** le prompt que la tâche enverra. Un seul constructeur,
`rediger_le_prompt_de_mise_a_jour`, sert la tâche et l'estimation ; le texte est normalisé
en mémoire (`###` → `##`) comme la tâche le répare en base, sans rien écrire. Sur un
article hérité à réparer, la réindexation de la tâche peut retirer des marqueurs : le
compte est alors un peu surévalué, jamais sous-évalué.

**Ce que vaut le montant :** un **ordre de grandeur**, d'où « environ ». Conventions de la
confirmation de synthèse : tiktoken `cl100k_base` (approximation du tokenizer réel),
sortie à 50 % de l'entrée, marge ×1,5, plancher 0,01 €. Ce n'est pas un plafond : la
taille d'une proposition n'a jamais été mesurée, et les tokens de réflexion d'un modèle
absent de `MULTIPLICATEUR_THINKING` (gemini-3.x, gpt-5) ne sont pas comptés. La
vérification des citations nouvelles, qui suit une mise à jour appliquée, n'est pas
chiffrée — la modale le dit.

### Fichiers modifiés / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `front/tasks.py` | **extrait** : `rediger_le_prompt_de_mise_a_jour(texte, ecartees)`, appelé par `construire_la_proposition_d_operations` |
| `front/views_synthese.py` | **neuf** : `WikiViewSet.estimation` — `GET /wikis/{id}/estimation/`, même porte d'accès que « Mettre à jour » ; `disallowed_special=()` pour tiktoken ; tout échec de comptage rend « non mesuré » |
| `front/templates/front/corpus/partials/estimation_de_mise_a_jour.html` | **neuf** : le bloc du coût (montant, « non mesuré », « rien ne partirait ») |
| `front/templates/front/corpus/article.html` | `data-url-estimation` sur la ligne « Mettre à jour » ; la modale construit son corps en DOM (`textContent`) et charge le coût en HTMX à l'ouverture |
| `front/tests/test_estimation_de_la_mise_a_jour.py` | **neuf** — 10 tests : montant recalculé pas à pas sous un tarif forcé (hors plancher), même prompt que la tâche, aucune écriture sur un article à réparer, jeton spécial `<\|endoftext\|>` sans erreur, « non mesuré », modèle sans nom, rien à reprendre, lecteur d'un carnet public refusé, adresse portée par le bouton |
| `front/tests/test_appliquer_un_tour_de_wiki.py` | `with` imbriqués fusionnés (ruff SIM117) |
| `PLAN/specs/SPEC-synthese-carnet.md` | question ouverte n° 1 : le coût est désormais annoncé |

### Le 22 septembre : les deux autres écrans de coût

Les confirmations d'**analyse** et de **synthèse** avaient les deux mêmes défauts, corrigés
de la même façon :

- une note contenant le texte d'un jeton spécial (`<|endoftext|>`) faisait tomber l'écran
  en 500 : tiktoken lève dessus par défaut. Le comptage passe `disallowed_special=()` ;
- le montant s'affichait « ≤ X € », alors que les tokens de réflexion d'un modèle absent de
  `MULTIPLICATEUR_THINKING` ne sont pas comptés : il s'affiche « environ X € ».

La confirmation **audio** garde son « ≤ » : elle facture à la minute, un tarif fixe, sans
estimation de sortie — le plafond y est vrai **quand la durée est mesurée et le modèle
tarifé**. Deux cas le faussent, non corrigés : voir `CHANGELOG/DEFAUTS-DIFFERES.md`,
« Les écrans de coût ».

| Fichier / File | Changement / Change |
|---|---|
| `front/views.py` | `disallowed_special=()` aux trois comptages (analyse : prompt et texte ; synthèse : prompt) ; l'« écart < 10 % » non mesuré est retiré du commentaire |
| `front/templates/front/includes/confirmation_analyse.html`, `confirmation_synthese.html` | « environ X € », et le commentaire qui dit pourquoi |
| `front/static/front/maquettes/maquette.html` | l'étalon de la confirmation d'analyse dit « environ » (vérificateur : 37/37) |
| `front/tests/test_les_ecrans_de_cout_disent_environ.py` | **neuf** — 4 tests : jeton spécial sans erreur (bloc d'estimation rendu) et « environ », pour chacun des deux écrans |
| `core/models.py` | commentaire de `MULTIPLICATEUR_THINKING` : un modèle absent n'est pas « sans réflexion », sa réflexion n'est pas comptée |
| `CHANGELOG/DEFAUTS-DIFFERES.md` | section « Les écrans de coût » : ce que les relectures ont trouvé sans que ce soit corrigé |

---

## Comment tester (à la main) / Manual test

### Test 1 — le coût s'affiche

1. Ouvrir un wiki dont la ligne « Mettre à jour » annonce des nouveautés.
2. Cliquer « Mettre à jour » : la modale affiche d'abord « Calcul du coût… », puis
   « Coût estimé : environ X € », le nombre de tokens, le modèle, le nombre d'extractions.
3. « Fermer » : rien n'est parti (aucune tâche dans le menu des tâches).

Sur un petit wiki, le montant affiché est souvent le plancher (0,01 €) : c'est attendu.

### Test 2 — tarif inconnu

Affecter au rôle rédacteur un modèle absent de la table de tarifs
(`manage.py affecter_un_modele_a_un_role`). La modale dit « non mesuré — le tarif de … n'est
pas connu », sans aucun montant.

### Test 3 — rien de neuf

Ouvrir un wiki « rien de neuf » : la modale grise « Relancer » et n'affiche **aucun** bloc
de coût (aucune requête `/estimation/` dans l'onglet Réseau).

### Test 4 — thème sombre

Refaire le test 1 en sombre : les deux lignes restent lisibles (mesuré le 21 septembre :
15,1:1 et 6,18:1 ; en clair 16,79:1 et 5,42:1).

### Test 5 — les deux autres écrans

Ouvrir la confirmation d'analyse d'une note, puis la confirmation de synthèse : le coût se
lit « environ X € ». Une note dont le texte contient `<|endoftext|>` ouvre les deux écrans
sans erreur.
