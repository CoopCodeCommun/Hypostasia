# Quatre juges locaux remplacent ShieldStral / Four local judges replace ShieldStral

**Date :** 2026-08-19
**Migration :** **Oui** — `core/migrations/0072_avis_des_juges_locaux.py`
(`docker exec -w /app hypostasia_web python manage.py migrate core`)

## Résumé / Summary

**Quoi / What :** le second avis devient **pluriel**. Quatre encodeurs NLI notent
chaque citation à côté du juge de production, et leurs avis s'affichent sur la fiche
de preuve dans un bloc pliable. ShieldStral est **débranché**.
*/ The second opinion becomes plural: four NLI encoders, shown in a collapsible block.*

**Pourquoi / Why :** ShieldStral coûtait **~24 000 ms de processeur par paire** et
7,7 Go. Les quatre juges retenus coûtent **45 à 352 ms**, pour un pouvoir de
détection au moins égal — mesuré le 19 août sur un jeu adverse où un comptage de mots
obtient 0,500 par construction.
*/ ~24 s and 7.7 GB per pair, against 45–352 ms for at least equal detection.*

### Fichiers / Files

| Fichier | Changement |
|---|---|
| `core/models.py` | **`AvisDeVerification`** — un avis par juge et par citation |
| `core/migrations/0072_avis_des_juges_locaux.py` | **neuve** |
| `core/services/juges_locaux.py` | **neuf** — les 4 juges, résidents, cadrage `directe` |
| `core/services/verification.py` | `poser_un_avis_local`, `paires_sans_avis`, `accord_des_juges_locaux` |
| `core/services/synthese.py` | **le report des avis** — sans lui, chaque mise à jour de wiki les effacerait |
| `core/services/juge_local.py` | en-tête : **débranché**, conservé pour le banc |
| `front/tasks.py` | la tâche note avec les 4, un juge à la fois |
| `front/views_synthese.py` | `avis_locaux` et `accord_local` au contexte |
| `front/templates/front/corpus/partials/preuve.html` | bloc `<details>` pliable |
| `core/tests/test_avis_des_juges_locaux.py` | **neuf** — 14 tests |
| `front/tests/test_second_avis_a_l_ecran.py` | 11 repris + **3 neufs** (cas « partagé », barres par juge, neutralité) = 14 |

### Pourquoi une table, alors que le second avis tenait en quatre colonnes

Le modèle le disait lui-même : *« un troisième exigerait la table, et il faudrait alors
régler le report »*. C'est exactement ce qui arrive.

**Le report est la moitié du travail.** `indexer_les_citations` **détruit et recrée**
tous les `SourceLink` d'un article à chaque mise à jour de wiki. La clé étrangère
étant en CASCADE, chaque tour effacerait tous les avis — c'est-à-dire précisément les
données que la campagne accumule. Les avis sont donc capturés **avant** la suppression
et recréés sur le nouveau lien, à côté du report des verdicts.
`test_la_reindexation_conserve_TOUS_les_avis` l'exige.

### Ce qui a décidé le choix des quatre

**Pas leur accord avec l'étalon gelé.** Sur ce jeu, un simple **comptage de mots**
obtient 0,889 — au-dessus de tous les modèles, ShieldStral compris. Les deux
références du dossier sont lexicalement saturées : le paragraphe a été écrit *à partir*
de ses sources et en reprend le vocabulaire.

**C'est le jeu adverse qui a tranché** : chaque affirmation vraie est perturbée
mécaniquement sans que son vocabulaire change, si bien qu'un comptage de mots y obtient
**0,500 par construction**. Sur deux types d'erreur indépendants :

| juge | négation | quantificateur | ms/passe |
|---|---|---|---|
| CamemBERTa v2 XNLI | **0,788** | 0,548 | 171 |
| mDeBERTa v3 XNLI | **0,764** | **0,695** | 199 |
| bge-m3 zeroshot | **0,760** | 0,662 | 352 |
| distilCamemBERT NLI | 0,675 | 0,603 | **45** |
| *LettuceDetect 210m FR* | *0,516* | *0,517* | *279* |
| *LettuceDetect 610m FR* | *0,492* | *0,459* | *1088* |

> Ces chiffres sont ceux de la **campagne corrigée** — celle qui a écarté les deux
> perturbations invalides. Une première passe, publiée quelques heures plus tôt,
> donnait 0,789 / 0,766 / 0,762 : elle mélangeait les quatre perturbations, dont deux
> ne fabriquaient pas d'affirmation fausse. **C'est cette table-ci qui fait foi**, et
> elle concorde avec `benchmarks/juge_de_verification/README.md`.

Les deux LettuceDetect français sont **sous le hasard** : écartés — alors qu'ils
étaient premiers sur l'étalon gelé. Détail et réserves :
[des encodeurs contre l'étalon](../benchmarks/juge_de_verification/2026-08-19_des-encodeurs-contre-l-etalon.md).

### Trois choix qui ne sont pas des détails

- **Le cadrage `directe`** — la question porte sur le paragraphe entier. Prendre le
  maximum phrase par phrase laisse une phrase **non perturbée** sauver la paire :
  0,762 contre 0,638 pour mDeBERTa. C'est l'inverse de ce que dit l'étalon gelé.
- **P(contradiction) est lu**, pas jeté. C'est le seul signal qu'un comptage de mots ne
  peut pas imiter — deux textes qui se contredisent partagent leur vocabulaire. Il vaut
  **+0,170 d'AUC** chez mDeBERTa et **+0,143** chez CamemBERTa, et **ne coûte aucune passe
  avant supplémentaire**.
- **Les modèles restent résidents** dans le worker, contre ~20 s de chargement par
  modèle et par article. **Mesuré le 19 août : 5,13 Go de RSS, 6,01 Go de pic** — bien
  au-delà de la somme des poids (~4,1 Go), l'allocateur de torch faisant le reste.
  **C'est un choix d'hébergement** : ce pic, plus une conversion Docling (~2 Go), plus
  PostgreSQL, exclut un VPS à 4 ou 8 Go, et `nice` ne protège pas de l'OOM killer. Le
  levier est `bge-m3`, qui coûte **2,40 Go à lui seul** — plus que les trois autres
  réunis — et qui est aussi le plus lent.

### Les seuils, mesurés sur le jeu adverse

| juge | AUC | appariée | **seuil** | accord |
|---|---|---|---|---|
| CamemBERTa v2 | 0,728 | **0,853** | **49,7** | 190/273 |
| mDeBERTa v3 | **0,743** | 0,840 | **50,0** | 193/273 |
| bge-m3 | 0,737 | 0,801 | **70,0** | 188/273 |
| distilCamemBERT | 0,656 | 0,737 | **63,7** | 169/273 |

**Ce que la mesure a corrigé.** Les deux juges qui lisent la contradiction optimisent
*exactement* au point neutre — logique après coup : c'est là que P(entailment) égale
P(contradiction). Mais **`bge-m3` optimise à 70**, pas à 50 : il rend P(entailment)
brut, et lui poser 50 l'aurait fait confirmer beaucoup trop de citations **sans
qu'aucune erreur ne le dise**. C'est précisément pour cela qu'un seuil se mesure juge
par juge.

**Ils sont sur-ajustés**, comme tout seuil choisi après coup sur les points qui servent
à l'évaluer, et le jeu adverse n'éprouve que **deux types d'erreur**. Ils valent comme
point de départ, pas comme vérité.

Ils se règlent par l'environnement : `SEUIL_CAMEMBERTAV2`, `SEUIL_MDEBERTA`,
`SEUIL_BGE_M3`, `SEUIL_DISTILCAMEMBERT`. Le seuil est **figé sur chaque avis**, donc en
changer ne rejuge rien.

### Le coût réel, mesuré de bout en bout

Les quatre juges chargés et résidents, sur une paire vraie et sa négation :

| juge | affirmation vraie | affirmation niée | ms/paire |
|---|---|---|---|
| CamemBERTa v2 | 99,2 | 1,0 | 147 |
| mDeBERTa v3 | 99,9 | 0,3 | 145 |
| bge-m3 | 99,0 | 1,4 | 160 |
| distilCamemBERT | 98,5 | 1,7 | **42** |

Les quatre séparent nettement. Compter **~0,5 s par citation pour les quatre réunis**,
contre ~24 s pour ShieldStral seul.

### Ce qui n'est pas supprimé, et pourquoi

`core/services/juge_local.py` (ShieldStral) et les quatre colonnes
`*_du_second_avis` **restent**. Le module porte le cadrage exact avec lequel ShieldStral
a été mesuré, et `comparer_shieldstral.py` l'importe sans copie : le supprimer rendrait
ces mesures irrejouables. Les colonnes portent les seules données de cette campagne.

`poser_un_second_avis` **n'a plus aucun appelant en production** et le dit dans sa
docstring. À trancher par le mainteneur : archive, ou migration dans la table.

---

## Comment tester (à la main) / Manual test

### Test 1 — la migration

```bash
docker exec -w /app hypostasia_web python manage.py migrate core
```

Attendu : `Applying core.0072_avis_des_juges_locaux... OK`.

### Test 2 — quatre avis sur une citation

1. Ouvrir un wiki qui porte des citations.
2. Cliquer **« Vérifier les citations »**, attendre la fin.
3. Cliquer le geste qui lance le second avis.
4. Ouvrir la fiche de preuve d'une citation.

**Attendu** : un bloc pliable « *N juges locaux sur M tranchent, et confirment le juge de
production* ». Au clic, **quatre barres**, chacune avec **son propre seuil**.

Compter moins d'une seconde par citation et par juge — contre une vingtaine de
secondes auparavant.

### Test 3 — les avis survivent à une mise à jour de wiki

1. Après le test 2, modifier le wiki **sans toucher aux paragraphes cités**, puis
   enregistrer (ce qui réindexe).
2. Rouvrir la même fiche de preuve.

**Attendu** : les quatre avis sont **toujours là**, avec leurs scores et leurs seuils.
C'est le report ; sans lui ils auraient disparu en silence.

### Test 4 — le cas « partagé »

Poser deux avis de part et d'autre du seuil et vérifier que le résumé annonce
« *2 juges locaux sur 4* » et non « d'accord » ou « divergent ». C'est ce que les
colonnes ne savaient pas dire.

### Vérifs

```bash
# les avis en base, par juge
docker exec -w /app hypostasia_web python manage.py shell -c "
from core.models import AvisDeVerification
from collections import Counter
print(Counter(AvisDeVerification.objects.values_list('methode', flat=True)))"
```

**Reste à faire** : la vérification au navigateur du bloc pliable, en clair **et** en
sombre, contrastes calculés. **Elle n'a pas été faite.**
