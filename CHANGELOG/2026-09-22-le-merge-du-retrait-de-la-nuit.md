# Le merge du retrait de la passe de nuit / Merging the nightly pass removal

**Date :** 2026-09-22
**Migration :** **Oui** — `core.0081_le_wiki_porte_son_redacteur` est **renumérotée
en `0082`** et dépend désormais de `core.0081_retrait_de_la_passe_de_nuit`. La base
de dev porte déjà l'ancien nom : voir « Ce qu'il reste à faire sur la base » plus bas.
**Ne pas lancer `migrate` sans avoir lu cette section.**

## Résumé / Summary

**Quoi / What :** `origin/dev` (retrait de la passe de nuit, 21 septembre) a été
fusionnée dans `dev` (chantier « provenance d'un prompt », 1er septembre). Les deux
branches touchaient le même chemin — la mise à jour d'un wiki — l'une pour le
supprimer, l'autre pour l'enrichir. La passe de nuit disparaît ; tout ce que le
chantier de provenance apportait au **geste manuel** est conservé.
*/ Merged the nightly-pass removal into the prompt-provenance work. The pass is
gone; everything provenance brought to the human gesture is kept.*

**Pourquoi / Why :** la décision du 21 septembre est postérieure et documentée
(addendum dans `PLAN/specs/SPEC-synthese-carnet.md`) : aucune tâche planifiée
n'appelle plus de modèle. Elle fait donc foi sur tout ce qui touche la nuit.

### Les deux conflits que git a signalés

| Fichier | Résolution |
|---|---|
| `front/tests/test_la_passe_de_nuit_des_wikis.py` | **supprimé** — il teste une passe qui n'existe plus |
| `front/tasks.py` | quatre zones : la passe retirée (`_fermer_la_passe`, `_rendre_la_main_a_la_passe`, `mettre_a_jour_un_wiki_la_nuit_task`, `_ecrire_le_job_d_un_tour_de_nuit`, `_ecrire_un_tour_d_echec`, `_rattacher_la_provenance`, `TourDeNuitDejaRaconte`), la provenance gardée |

### Les trois conflits que git n'a PAS signalés

Aucun n'apparaît comme conflit : le fichier n'existe que d'un côté, ou le champ
supprimé l'est par une migration de l'autre branche. Tous les trois cassaient à
l'exécution, pas à la fusion.

| Où | Ce qui cassait |
|---|---|
| `hypostasis_extractor/tests/test_la_provenance_d_une_production.py` | `LaProvenanceD_unTourDeNuitTest` appelait `mettre_a_jour_les_wikis`, commande supprimée → **rebranchée sur le geste manuel** (`LaProvenanceD_unTourDeMiseAJourTest`) |
| `front/tests/test_les_ecrans_de_cout_disent_environ.py` | créait un `PromptPiece(name=…)` — champ supprimé par `0039_le_morceau_de_prompt_n_a_pas_de_nom` |
| `front/tests/test_les_ecrans_de_cout_disent_environ.py` | créait un `AnalyseurSyntaxique(inclure_extractions=…, inclure_texte_original=…)` — champs supprimés par `0040_les_deux_bascules_d_injection_disparaissent` |

### Les deux branches avaient écrit le MÊME prompt, sous deux noms

`rediger_le_prompt_de_mise_a_jour(texte, ecartees)` (origin/dev, pour que la modale
compte le prompt **avant** le clic) et `assembler_le_prompt_de_mise_a_jour(wiki,
analyseur)` (provenance, pour figer l'analyseur). Garder les deux textes en aurait
fait deux versions — exactement ce que le commentaire d'origin/dev interdit : « une
copie de ce texte pour l'estimation finirait par diverger ».

**`assembler_…` délègue donc à `rediger_…`, qui gagne un paramètre `analyseur`.** Un
seul texte, deux entrées : l'une lit la base et ferme la provenance, l'autre
normalise en mémoire sans rien écrire. L'estimation (`WikiViewSet.estimation`) passe
désormais le même analyseur que la tâche — sans quoi elle annonçait le coût d'un
autre prompt système.

Le texte retenu est celui d'`origin/dev` : « un humain les acceptera une par une ».
Celui du chantier de provenance promettait « appliquées TELLES QUELLES, sans
relecture humaine », ce qui n'était vrai **que** de la nuit.

### Un piège d'ordre, trouvé par un test

`construire_la_proposition_d_operations` répare les `###` hérités **en écrivant**
l'article, ce qui le réindexe : une extraction dont le marqueur était déjà dans le
texte y retrouve son ancrage et **sort des écartées**. Les recalculer après la
réparation faisait diverger le prompt envoyé de celui que la modale avait compté —
elle n'écrit rien et ne peut pas connaître l'état d'après.

**Les écartées se figent donc avant la réparation**, comme le faisait `origin/dev`.
`test_sur_un_article_a_reparer_le_compte_est_celui_d_apres_reparation` l'épingle :
sans ce figeage, il tombe à 436 tokens annoncés contre 414 envoyés.

### Fichiers modifiés / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `front/tasks.py` | passe de nuit retirée ; `assembler_…` délègue à `rediger_…` et accepte des `ecartees` figées ; écartées figées avant la réparation des titres |
| `front/views_synthese.py` | l'estimation passe l'analyseur du rédacteur au constructeur de prompt |
| `front/tests/test_appliquer_un_tour_de_wiki.py` | dépaquette les **trois** valeurs rendues (la provenance est la troisième) |
| `front/tests/test_les_ecrans_de_cout_disent_environ.py` | `PromptPiece.name` et les deux bascules d'injection retirés |
| `hypostasis_extractor/tests/test_la_provenance_d_une_production.py` | `LaProvenanceD_unTourDeMiseAJourTest` — 3 tests rebranchés sur le geste |
| `core/migrations/0082_le_wiki_porte_son_redacteur.py` | renumérotée depuis `0081`, dépend du retrait de la passe |
| `PLAN/Diagrams/README.md` | la légende du cadre violet affirmait que la nuit applique sans humain |
| `PLAN/Diagrams/02-du-prompt-a-l-article-source.md` | le nœud « ou LA NUIT applique sans lui » |
| `CHANGELOG/2026-09-01-la-provenance-d-un-prompt.md`, `…-le-locuteur-l-aide-et-la-doc.md` | encart daté : ce qu'ils disent de la nuit est de l'histoire |
| `PLAN/TODO/2026-09-01-la-planche-04-de-la-nuit-des-wikis.md` | **supprimé** — il demandait de diagrammer la passe |

---

## Ce qu'il reste à faire sur la base / Database follow-up

**La base de dev est beta.hypostasia.org.** Elle porte déjà
`core.0081_le_wiki_porte_son_redacteur` **appliquée** — le nom d'avant la
renumérotation. La colonne `wiki.analyseur_de_redaction` existe donc déjà, et
rejouer la migration échouerait sur un `column already exists`.

La séquence, dans cet ordre :

```bash
# 1. Oublier l'ancien nom, SANS toucher a la colonne (elle reste).
docker exec -w /app hypostasia_web python manage.py shell -c "
from django.db import connection
with connection.cursor() as c:
    c.execute(\"DELETE FROM django_migrations WHERE app='core' AND name='0081_le_wiki_porte_son_redacteur'\")
    print(c.rowcount, 'ligne(s) retiree(s)')
"

# 2. Appliquer le retrait de la passe (DROP de la table PasseDeNuit).
docker exec -w /app hypostasia_web python manage.py migrate core 0081_retrait_de_la_passe_de_nuit

# 3. Marquer la renumerotee comme faite : la colonne est deja la.
docker exec -w /app hypostasia_web python manage.py migrate core 0082_le_wiki_porte_son_redacteur --fake

# 4. Verifier : une seule feuille, tout applique.
docker exec -w /app hypostasia_web python manage.py showmigrations core | tail -4
```

**Puis redémarrer les workers** — ils tournent avec l'ancien code et connaissent
encore les tâches de la nuit :

```bash
make restart S=celery_worker
make restart S=celery_beat
```

**Le beat surtout** : un beat qui tourne garde son ancien horaire en mémoire et
enverrait chaque nuit une tâche qui n'existe plus (« unregistered task » dans les
journaux — rien de facturé, mais du bruit).

**Et le crontab de l'hôte** : `crontab -l`. S'il porte des lignes `bin/nuit.sh`, les
retirer — le script n'existe plus.

## Comment tester (à la main) / Manual test

### Test 1 — la mise à jour d'un wiki reste un geste

1. Ouvrir un carnet qui porte un wiki avec des extractions non reprises.
2. Cliquer « Mettre à jour » sur l'article : la modale annonce un coût « environ N ».
3. Accepter une opération : l'article change, un tour est écrit.
4. Vérifier qu'aucune tâche planifiée n'appelle de modèle :
   `docker exec -w /app hypostasia_web python -c "from hypostasia.celery import celery_app; print(celery_app.conf.beat_schedule)"`
   → une seule entrée, `le-recapitulatif-du-matin`.

### Test 2 — le coût annoncé est celui du prompt envoyé

Le cas qui a cassé pendant le merge : un article portant un `###` hérité.

1. Sur un tel article, ouvrir la modale et noter le `data-tokens` annoncé.
2. Lancer la mise à jour, puis relire le prompt réellement envoyé dans la
   provenance (`ProvenanceDeProduction.longueur` du dernier job).
3. Les deux comptes doivent concorder.

### Vérifs automatiques

```bash
docker exec -w /app hypostasia_web python manage.py test \
  front.tests.test_appliquer_un_tour_de_wiki \
  front.tests.test_estimation_de_la_mise_a_jour \
  front.tests.test_l_assemblage_des_prompts_d_article \
  front.tests.test_la_liste_des_wikis_signale_le_neuf \
  front.tests.test_le_recapitulatif_du_matin \
  front.tests.test_les_ecrans_de_cout_disent_environ \
  core.tests.test_le_planificateur \
  hypostasis_extractor.tests.test_la_provenance_d_une_production \
  --settings=hypostasia.settings_test_opus --noinput
```

→ **102 tests, OK en 116 s** (mesuré le 22 septembre 2026, après résolution).
