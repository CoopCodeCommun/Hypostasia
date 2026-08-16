# Couche corpus, phase B : validation des categories

**Date :** 2026-08-08
**Migration :** Non

**Quoi / What :** la validation « qui n'a pas le droit de manquer »
(SPEC-corpus § 3.4) : une categorie appliquee a une appartenance doit venir
du carnet (ou de la base) de cette appartenance.

**Pourquoi / Why :** sans elle, le vocabulaire d'un carnet fuit dans un
autre — exactement ce que la categorie portee par la relation existe pour
empecher. Deux etages : le serializer (erreur de formulaire propre) et les
signaux m2m_changed (filet de securite, meme un .add() en shell est refuse).

### Fichiers ajoutes / Added files
| Fichier / File | Role / Purpose |
|---|---|
| `core/services/corpus.py` | Les deux validateurs (cote carnet, cote base) |
| `core/signals.py` | Les deux signaux m2m_changed, avec le kwarg `reverse` gere dans les deux sens (le cas que la v1.0 de la spec cassait) |

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `core/apps.py` | `ready()` importe les signaux |
| `core/serializers.py` | + `CategoriserUneNoteSerializer` |
| `core/tests/test_corpus_modele.py` | + 14 tests de validation (sens direct, inverse — nominal ET refus —, .set(), cote base, serializer : etrangere, introuvable, liste vide) |

### Relecture / Review
Relecture adverse passee (8 aout) : pas de bloquant. Correctifs appliques —
tests nominaux de la branche reverse (le seul trou par lequel une regression
sur LE point v1.0 serait passee), garde de contexte du serializer,
`dispatch_uid` sur les signaux, docstring honnete sur la limite du through
(les ecritures directes sur la table de liaison ne declenchent aucun signal),
borne `max_length=100` sur la liste.

### Piege documente / Documented pitfall
Une ValidationError levee par le signal sort du bloc atomique interne du
`.add()` : dans un test (ou une vue sous transaction), les requetes
suivantes exigent un savepoint (`with transaction.atomic():` autour de
l'appel refuse). Les tests montrent le patron.

### Migration
- **Migration necessaire / Migration required :** Non.

---

## Ce qui a été fait

La validation du § 3.4 de la spec corpus, en deux étages :
1. **Serializer** (`CategoriserUneNoteSerializer`) : refuse en erreur de
   formulaire une catégorie qui ne vient pas du carnet de l'appartenance.
2. **Signaux `m2m_changed`** (`core/signals.py`) : filet de sécurité ORM,
   les deux sens (`appartenance.categories.add(...)` ET
   `categorie.appartenances.add(...)`, kwarg `reverse`), côté carnet ET
   côté base.

### Modifications
| Fichier | Changement |
|---|---|
| `core/services/corpus.py` | Les deux validateurs |
| `core/signals.py` | Les deux signaux, câblés par `CoreConfig.ready()` |
| `core/serializers.py` | `CategoriserUneNoteSerializer` |
| `core/tests/test_corpus_modele.py` | 9 tests de validation |

## Tests à réaliser

### Test 1 : suite automatique
```bash
docker exec hypostasia_dev_web python manage.py test core.tests --noinput
```
39 tests attendus verts.

### Test 2 : le filet en shell (démonstration manuelle)
```bash
docker exec -it hypostasia_dev_web python manage.py shell
```
```python
from core.models import *
# Prendre une appartenance et une catégorie d'un AUTRE carnet :
a = AppartenancePageDossier.objects.first()
cat_etrangere = CategorieDossier.objects.exclude(liste__dossier=a.dossier).first()
a.categories.add(cat_etrangere)   # → ValidationError attendue
```

## Compatibilité

- Aucune migration ; aucun comportement existant modifié (les signaux ne
  portent que sur les nouvelles tables M2M, vides jusqu'à la phase F/G).
- Piège pour les vues futures : si un appel refusé est fait sous
  transaction, envelopper dans `transaction.atomic()` (savepoint) pour
  pouvoir continuer à requêter après le refus — patron visible dans les
  tests.

