# Verbatim tolérant à la forme, découpage réparé, banc des rédacteurs
/ Shape-tolerant verbatim, fixed segmentation, writers' bench

**Date :** 2026-08-19
**Migration :** Non

## Resume / Summary

**Quoi / What :** trois chantiers liés, issus d'une même mesure.
1. le contrôle verbatim tolère **trois retouches de forme** (point final,
   majuscule d'amorce, espace de ponctuation) — jamais un changement de fond ;
2. l'ingestion **recolle la ponctuation** que Docling détache du mot qui la
   précède ;
3. le banc des rédacteurs gagne la **garde des jobs**, la **couverture du
   périmètre** et la **part de prose sans marqueur**, et une campagne propre a
   été exécutée.
/ Shape-tolerant verbatim, punctuation re-attached at ingestion, and a clean
writers' comparison.

**Pourquoi / Why :** 34 des 60 citations `INTROUVABLE` ne tenaient pas au fond
mais à la forme, et **les deux tiers venaient de notre propre ingestion** :
elle produit `territoire .`, le modèle recolle le point, et la chaîne de preuve
était déclarée cassée.
/ Two thirds of the broken proof chains were our own ingestion's fault.

### Fichiers modifies / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `core/services/verification.py` | `_le_verbatim_est_present` : passe stricte, puis trois tolérances de forme |
| `hypostasis_extractor/services/ingestion_docling.py` | `recoller_la_ponctuation_detachee`, appliquée à chaque élément ingéré |
| `benchmarks/redaction/mesurer_les_redacteurs.py` | garde des jobs, couverture du périmètre, prose sans marqueur |
| `benchmarks/extraction_format/typer_les_non_verbatim.py` | importe désormais les règles de la **production**, plus de copie locale |
| `core/tests/test_verbatim_tolerant_a_la_forme.py` | **Neuf**, 12 tests |
| `hypostasis_extractor/tests/test_recollage_de_la_ponctuation.py` | **Neuf**, 11 tests |
| `front/tests/test_mesures_du_banc_des_redacteurs.py` | **Neuf**, 6 tests |
| `benchmarks/redaction/2026-08-19_trois-redacteurs-a-un-seul-extracteur.md` | le rapport de campagne |

### Ce que la campagne a trouvé / What the campaign found

- **Medium source 100 % de ses phrases** (0/41). Small en laisse 12 % nues,
  **Large 50 %** — et ce sont des affirmations, pas des transitions.
- Large a le meilleur « % vérifiées » (35 %), mais sur la moitié de son texte
  seulement : l'autre moitié ne porte aucun marqueur et échappe au juge.
- Le taux d'`INTROUVABLE` tombe à **9-12 %** grâce à la tolérance, contre
  17-19 % avec le contrôle strict.
- **0 citation hors périmètre** chez les trois : le périmètre a tenu.

### Ce qui survit a un `down -v` / What survives a `down -v`

Verifie ligne a ligne, sans executer la destruction :

| | apres `down -v && make install` |
|---|---|
| modele d'**extraction** | `mistral-small-latest`, temperature **0** (tete de `MODELES_IA_PAR_CLE_D_ENVIRONNEMENT`, `MISTRAL_API_KEY` presente) |
| roles **redacteur** et **juge** | `mistral-small-latest` (`ROLES_PAR_DEFAUT`) |
| prompts d'extraction et de synthese, 30 exemples | reposes par les fixtures |
| consigne de sourcage `[[ext:N]]` | dans le **code** (`front/tasks.py`), independante de la base |
| **le recollage de la ponctuation** | s'applique a la reingestion : **les sources seront propres** |

⚠️ **`mistral-large-latest` et `mistral-medium-latest` ne survivent PAS** : ils
ont ete crees a la main pour le banc et ne figurent dans aucune fixture. La
campagne des trois redacteurs n'est pas rejouable apres une reinstallation sans
les recreer.

⚠️ **Un role pose a la main survit au redemarrage** (`get_or_create`, pas
`update_or_create`). Apres ce banc, le role redacteur etait donc reste sur
**Large** : il a ete remis a `mistral-small-latest`. Un banc qui deplace un role
doit le reposer en partant.

---

## Comment tester (a la main) / Manual test

### Test 1 — les tests automatiques
```bash
docker compose exec -T web python manage.py test \
    core.tests.test_verbatim_tolerant_a_la_forme \
    hypostasis_extractor.tests.test_recollage_de_la_ponctuation \
    hypostasis_extractor.tests.test_typage_des_non_verbatim \
    front.tests.test_mesures_du_banc_des_redacteurs
```
Attendu : **52 tests OK**.

Les tests qui comptent sont ceux qui vérifient qu'une règle de forme ne
blanchit JAMAIS un changement de sens :
- `test_une_enumeration_ne_blanchit_JAMAIS_un_nombre_decimal` et ses deux
  variantes de disposition — « les niveaux 3, 5 et 8 » ne doit jamais accepter
  « les niveaux 3,5 » ;
- `test_une_question_devenue_affirmation_reste_introuvable` ;
- `test_un_propos_laisse_en_suspens_ne_se_ferme_pas` ;
- `test_un_point_DETACHE_par_la_source_est_le_MEME_point` — celui qui distingue
  la tolérance utile de la tolérance dangereuse.

### Test 2 — la tolérance, sur les vraies données
```bash
docker compose exec -T web python \
    benchmarks/extraction_format/typer_les_non_verbatim.py
```
Attendu : le tableau des `INTROUVABLE` par cause, avec le nom du rédacteur qui
a produit les articles mesurés.

### Test 3 — le recollage, à l'œil
Ingérer un PDF et vérifier qu'aucun élément ne porte `mot .` ou `mot ,` :
```bash
docker compose exec -T web python manage.py shell -c "
from core.models import ElementDocument
import re
motif = re.compile(r'\S\s+[.,]')
for e in ElementDocument.objects.order_by('-id')[:40]:
    for f in motif.findall(e.texte or ''): print(e.id, repr(f))"
```
⚠️ **Les éléments DÉJÀ en base gardent leur texte** : le recollage ne touche
que ce qui est ingéré après lui. Les corriger décalerait les ancres des
extractions, qui portent des positions absolues.

### Test 4 — le banc, et sa garde
```bash
docker compose exec -T -e MODELE_ATTENDU=mistral-large-latest web python \
    benchmarks/redaction/mesurer_les_redacteurs.py
```
Attendu : quatre blocs, dont le **contrôle des jobs** en tête. Il doit refuser
de mesurer si le dernier job de production d'un article n'est pas `completed`,
ou s'il vient d'un autre modèle que celui attendu.

### Revenir sur le périmètre du banc
275 extractions ont été **masquées** pour ne garder qu'un seul extracteur.
Elles sont listées dans `benchmarks/redaction/perimetre_du_banc.json` :
```bash
docker compose exec -T web python manage.py shell -c "
import json
from hypostasis_extractor.models import ExtractedEntity
pks = json.load(open('/app/benchmarks/redaction/perimetre_du_banc.json'))['masquees_pour_le_banc']
for e in ExtractedEntity.objects.filter(id__in=pks):
    e.masquee = False
    e.save(update_fields=['masquee'])
print('démasquées :', len(pks))"
```
Un par un, avec `update_fields` : le signal `post_save` recalcule l'état des
éléments, ce qu'un `.update()` de masse ne ferait pas.
