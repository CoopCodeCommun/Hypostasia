# Couche corpus, phase B — validation des catégories

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
