# Les quatre juges locaux, installés et survivants
/ The four local judges, installed and surviving

**Date :** 2026-08-20
**Migration :** Non

## Resume / Summary

**Quoi / What :** les quatre juges locaux tournent enfin **tous les quatre**,
survivent à un `docker compose down -v`, et notent tout le carnet étalon à
l'installation. Les avis perdus lors d'une mise à jour d'article sont désormais
**comptés**.
/ All four local judges now run, survive a `down -v`, and score the whole
reference notebook at install time.

**Pourquoi / Why :** le dossier annonçait « quatre juges branchés en
production » — **il en tournait trois**. `sentencepiece` n'existait que dans
`/tmp/banc_deps`, atteint par un `PYTHONPATH` que le worker ne portait pas :
`distilcamembert` levait `ModuleNotFoundError` à chaque paquet, notait zéro
paire, et la garde `arret_sans_progres` **stoppait toute la campagne**, y
compris pour les trois juges sains.
/ The dossier claimed four judges; three ran. The fourth's failure stopped
every campaign.

### Fichiers modifies / Modified files

| Fichier / File | Changement / Change |
|---|---|
| `pyproject.toml`, `uv.lock` | `sentencepiece` et `transformers` **déclarés** — ils n'arrivaient que transitivement par `docling` |
| `front/management/commands/noter_avec_les_juges_locaux.py` | **Neuf.** Met un job par article en file. Gratuite, hors réseau, idempotente |
| `bin/install.sh` | l'étape des juges locaux, **après** la vérification |
| `core/services/synthese.py` | `avis_perdus` au bilan de réindexation |
| `core/tests/test_installation_des_juges_locaux.py` | **Neuf**, 5 tests |
| `front/tests/test_notation_par_les_juges_locaux.py` | **Neuf**, 4 tests |
| `core/tests/test_avis_perdus_au_report.py` | **Neuf**, 3 tests |
| `front/tests/test_script_d_installation.py` | 3 tests : la chaîne va jusqu'aux juges, dans le bon ordre |
| `benchmarks/2026-08-20_dossier-de-relecture-par-les-pairs.md` | **Neuf.** Le dossier de relecture des deux sessions |

### Ce que la mise en service a mesuré / What it measured

**836 avis écrits, 209 par juge** — parfaitement équilibré. Les 16 citations non
notées sur 225 sont toutes `introuvable` : sain, une citation dont le passage
n'existe plus n'a pas de paire à juger.

**⚠️ Résultat neuf : deux des quatre juges sont muets 85 % du temps.**

| juge | AUC appariée | **ne tranche pas** | confirme |
|---|---|---|---|
| CamemBERTa v2 | **0,853** | **85 %** | 13 % |
| mDeBERTa v3 | **0,840** | **85 %** | 12 % |
| bge-m3 | 0,801 | 4 % | 39 % |
| distilCamemBERT | 0,737 | 8 % | 29 % |

La `MARGE_DE_NEUTRALITE = 2,5` est appliquée uniformément à des échelles
différentes : les juges à contradiction rendent `(P(ent) − P(contra) + 1)/2`,
très concentré autour de 50 — CamemBERTa v2 va de 43,1 à 78,4, médiane 50,1.
`bge-m3` rend `P(entailment)` brut, étalé de 0,3 à 99,2.

**Conséquence non dite jusqu'ici : l'accord affiché repose de fait sur
`bge-m3`** — précisément le juge **sans** classe contradiction, c'est-à-dire
sans le seul signal que le dossier défend. **Arbitrage attendu du mainteneur :
une marge par juge, ou une échelle commune.**

### Pourquoi la table des avis était vide / Why the table was empty

Un avis ne survit à une mise à jour d'article que si sa paire est **strictement
identique** — même extraction ET même texte de paragraphe, au mot près
(`_cle_de_paire`). La campagne de comparaison de rédacteurs du 19 août a
**régénéré les wikis neuf fois** : les 165 avis existants sont partis par
CASCADE, **sans qu'une ligne, un compteur ou un écran ne le signale**.

Perdre un avis dont l'affirmation a changé est correct — il ne vaut plus rien.
Le perdre **en silence** ne l'est pas : les contestations humaines, elles, sont
comptées depuis toujours. Le bilan porte maintenant `avis_perdus`.

---

## Comment tester (a la main) / Manual test

### Test 1 — les tests automatiques
```bash
docker compose exec -T web python manage.py test \
    core.tests.test_installation_des_juges_locaux \
    front.tests.test_notation_par_les_juges_locaux \
    core.tests.test_avis_perdus_au_report \
    front.tests.test_script_d_installation
```
Attendu : **38 tests OK**.

### Test 2 — le quatrième juge charge vraiment
```bash
docker compose exec -T web python -c "
from transformers import AutoTokenizer
print(type(AutoTokenizer.from_pretrained('cmarkea/distilcamembert-base-nli')).__name__)"
```
Attendu : `CamembertTokenizer`. Avant, `ModuleNotFoundError: sentencepiece`.

### Test 3 — faire noter tout le carnet
```bash
make restart S=celery_worker_juge_local
docker compose exec -T web python manage.py noter_avec_les_juges_locaux
```
Puis, quand les jobs sont finis :
```bash
docker compose exec -T web python manage.py shell -c "
from core.models import AvisDeVerification
from collections import Counter
c = Counter(AvisDeVerification.objects.values_list('methode', flat=True))
for m, n in sorted(c.items()): print(f'{m:34} {n:4}')"
```
Attendu : **les quatre méthodes, au même compte**. Si `distilCamemBERT` manque,
`sentencepiece` n'est pas installé.

Relancer la commande une seconde fois doit afficher « déjà noté — sauté » : elle
tourne à chaque démarrage de conteneur, et sans cette garde un redémarrage
rejouerait tout le corpus sur un worker à concurrence 1.

### Test 4 — à l'œil, sur la fiche de preuve
Ouvrir un article, cliquer un renvoi `[N]`, déplier « avis des juges locaux ».
Attendu : quatre barres, chacune avec son score, son seuil et sa date.
Les avis de CamemBERTa v2 et mDeBERTa v3 afficheront le plus souvent
**« ne tranche pas »** — c'est le résultat mesuré ci-dessus, pas une panne.

⚠️ **La vérification au navigateur en clair ET en sombre, contrastes calculés,
reste à faire** — exigence d'`AGENTS.md` que rien ne remplace.
