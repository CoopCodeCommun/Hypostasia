# Neuf passes : le bruit mesuré / Nine passes: the noise, measured

**Date :** 2026-08-19
**Migration :** Non

## Resume / Summary

**Quoi / What :** un banc qui REPETE la comparaison des rédacteurs — 3 modèles
× 3 passes × 4 articles — et sépare le **bruit**, l'effet du **sujet** et
l'effet du **modèle**.
/ A bench that repeats the writers' comparison and separates noise, subject
effect and model effect.

**Pourquoi / Why :** toutes les campagnes précédentes faisaient UNE passe par
modèle. Elles ne pouvaient pas distinguer un écart de modèle d'un écart de
tirage — et publiaient quand même des classements à cinq points d'écart.
/ Every previous campaign ran ONE pass per model and still published rankings.

### Fichiers modifies / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `benchmarks/redaction/lancer_les_passes.py` | **Neuf.** Répète les passes, crée les wikis manquants, garde les jobs, réessaie une passe écartée |
| `benchmarks/redaction/analyser_les_passes.py` | **Neuf.** Étendue par condition, verdict « tranche / dans le bruit », effet du sujet |
| `benchmarks/redaction/passes_repetees.json` | **Neuf.** Les neuf passes |
| `benchmarks/redaction/2026-08-19_trois-redacteurs-a-un-seul-extracteur.md` | encart ⚠️ en tête + § 9 |

### Ce que la mesure a trouvé / What it found

- **Le « % vérifiées » ne discrimine rien.** `mistral-large` rend 29,4 %,
  40,6 % puis 31,1 % sur trois passes identiques à température 0 : **11 points
  d'amplitude avec lui-même**, pour 7,8 points d'écart entre modèles.
- **Tranchent, eux** : le nombre de citations (Small 279 vs Medium 173), la
  longueur (Medium 19 k vs Small 32 k caractères), les extractions distinctes,
  et — de justesse — la prose sans marqueur (Medium 10 % vs Large 26 %).
- **L'effet du SUJET égale celui du modèle** : Small va de **4,5 %** de prose
  nue sur « open badges » à **35,2 %** sur « gouvernance collective », le sujet
  que le corpus couvre le moins. Un article sur un sujet mal couvert se dégrade
  en prose non sourcée — et ce n'est pas le modèle qu'il faut alors changer.
- **Large n'est premier sur aucun critère et il est le plus instable.**

⚠️ **Trois répétitions, c'est peu** : l'étendue sur trois points sous-estime la
dispersion. Les verdicts « tranche » les plus serrés sont des indices, pas des
preuves. Et **le juge a sa propre variation**, qui n'est pas isolée ici.

---

## Comment tester (a la main) / Manual test

### Test 1 — rejouer l'analyse (gratuit, aucun appel de modèle)
```bash
docker compose exec -T web python benchmarks/redaction/analyser_les_passes.py
```
Attendu : trois blocs — chaque mesure passe par passe avec son étendue, le
verdict « tranche / dans le bruit » par mesure, puis l'effet du sujet.

### Test 2 — relancer des passes (FACTURÉ)
```bash
docker compose exec -T -e NOMBRE_DE_PASSES=3 \
    -e MODELES_DU_BANC='{"small": 1, "medium": 5, "large": 4}' \
    web python benchmarks/redaction/lancer_les_passes.py
```
⚠️ **Redémarrer le worker avant** (`make restart S=celery_worker`).

Deux pièges que le script ferme, et qu'il faut connaître :
- **les envois sont sérialisés** : en parallèle, l'API répond `429 Rate limit
  exceeded`, le job part en `error` et la garde écarte la passe entière ;
- **une passe écartée est réessayée une fois** : perdre une répétition
  fausserait la mesure du bruit qu'on vient chercher.

### Retirer les wikis créés par le banc
Le banc crée deux wikis dans le carnet étalon (« Les limites de
l'explicabilité des systèmes d'IA », « La gouvernance collective des outils
numériques ») et les laisse en place — ils sont son corpus. Pour les retirer :
```bash
docker compose exec -T web python manage.py shell -c "
from core.models import Wiki
for sujet in [\"Les limites de l'explicabilité des systèmes d'IA\",
              'La gouvernance collective des outils numériques']:
    for wiki in Wiki.objects.filter(sujet=sujet):
        wiki.page.delete()
        wiki.delete()
print('retirés')"
```
