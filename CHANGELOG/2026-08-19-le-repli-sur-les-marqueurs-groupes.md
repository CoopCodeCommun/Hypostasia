# Le repli sur les marqueurs groupés / Grouped citation markers fallback

**Date :** 2026-08-19
**Migration :** Non.

## Résumé / Summary

**Quoi / What :** l'indexeur de citations accepte désormais la forme groupée
`[[ext:1, ext:2, ext:3]]` et la réécrit en marqueurs consécutifs
`[[ext:1]][[ext:2]][[ext:3]]`. Le nombre de groupes réécrits est **compté** et
rendu dans le bilan.
*/ The citation indexer now accepts the grouped marker form and rewrites it
into consecutive markers, counting the rewrites.*

**Pourquoi / Why :** le prompt exige des marqueurs **consécutifs** et le dit
avec un exemple. `mistral-small-latest` désobéit. Le motif de l'indexeur ne les
voyait même pas : **107 citations perdues sur 142 produites**, mesuré sur deux
articles réels, et le balisage brut restait **affiché en clair** dans le HTML.
*/ One model disobeys a documented format; 107 of 142 citations were silently
lost and raw markup reached the screen.*

### Fichiers modifiés / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `core/services/synthese.py` | `MOTIF_DE_MARQUEUR_GROUPE`, `normaliser_les_marqueurs_groupes`, appel en amont de `indexer_les_citations`, `marqueurs_groupes_normalises` au bilan |
| `core/tests/test_marqueurs_groupes.py` | **nouveau** — 9 tests |

## Ce que ça coûtait, mesuré

| | renvois reconnus | renvois **perdus** | balisage brut à l'écran |
|---|---|---|---|
| wiki | 10 | **57** (7 groupes) | 8 marqueurs en clair |
| synthèse | 25 | **50** (21 groupes) | idem |
| **total** | **35** | **107** | |

Et **rien ne le signalait**. L'indexeur dénonce bruyamment un marqueur
*halluciné* — `marqueurs_retires` — mais il était **aveugle** à celui-là : une
perte silencieuse, la catégorie de défaut que tout ce projet est écrit pour
empêcher.

## Trois décisions

### Le repli vit EN AMONT de tout

`normaliser_les_marqueurs_groupes` est appelée en tête de
`indexer_les_citations`, avant même le comptage des identifiants cités.
Conséquence : l'indexation, le texte enregistré, la vérification et l'affichage
voient tous **une seule forme canonique**, et aucun d'eux n'a besoin de
connaître l'existence du format groupé. Une seconde tolérance ailleurs finirait
par diverger de celle-ci.

### Les groupes sont COMPTÉS, pas avalés

`bilan["marqueurs_groupes_normalises"]`. Réparer en silence excuserait la
désobéissance, et on ne saurait plus **quel** modèle la commet — or c'est un
signal de qualité utile : sur la même consigne, `mistral-large-latest` obéit à
100 %.

### La règle des marqueurs hallucinés ne change pas

Un groupe mêlant un identifiant connu et un inconnu garde le connu, retire
l'inconnu, et **le signale** dans `marqueurs_retires`. Un test le verrouille.

## Ce que ça change aux mesures publiées

**Cela retourne la comparaison Small / Large sur la rédaction.** Le texte déjà
produit par Small, repassé dans le repli — sans un seul appel de modèle —
donne **142 citations contre 127 pour Large**. L'avantage de Large tenait
**entièrement** à ce défaut, pas à une infériorité de Small.

Détail : `benchmarks/2026-08-19-mistral-small-contre-large.md`.

**Ce qui n'est pas mesuré** : la FORCE des 107 citations récupérées. Elles n'ont
jamais été jugées.

---

## Comment tester (à la main) / Manual test

### Test 1 — un groupe devient des renvois cliquables

1. Produire un article avec `mistral-small-latest` comme rédacteur.
2. Ouvrir l'article.
3. **Attendu** : **aucun** `[[ext:14, ext:15, …]]` visible en clair dans le
   texte. Chaque source est un renvoi `[N]` cliquable qui ouvre son panneau.
4. Avant ce repli, le wiki en affichait **huit** en clair.

### Test 2 — le bilan compte les groupes

```bash
docker exec -w /app hypostasia_web python manage.py shell -c "
from hypostasis_extractor.models import ExtractionJob
for j in ExtractionJob.objects.filter(raw_result__contains={'est_wiki': True}).order_by('-pk')[:2]:
    print(j.pk, {k: v for k, v in (j.raw_result or {}).items() if 'marqueur' in k or 'citation' in k})
"
```
**Attendu** : `marqueurs_retires` vide (aucune hallucination) et, si le rédacteur
a groupé, un compte non nul de groupes réécrits.

### Test 3 — le format attendu traverse intact

Un article dont le rédacteur respecte la consigne (`mistral-large-latest`)
doit donner **exactement** le même résultat qu'avant ce repli : zéro groupe
réécrit, même nombre de liens. Vérifié par test automatique
(`test_un_marqueur_seul_n_est_pas_touche`).
