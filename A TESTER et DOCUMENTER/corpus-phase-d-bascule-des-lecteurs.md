# Couche corpus, phase D — bascule des lecteurs vers la table de liaison

## Ce qui a été fait

Tous les lecteurs et écrivains de `Page.dossier` convertis en un seul lot
(liste fermée du § 4.3 de la spec). La table de liaison fait foi partout ;
la FK ne sert plus qu'à porter le « premier carnet » pendant la
coexistence, écrite uniquement par le service de rangement.

**Ce que ça débloque, visible à l'écran** : une note rangée dans deux
carnets apparaît sous les deux dans l'arbre, participe à l'alignement des
deux, est vue par la dédup de capture, et les fins de synthèse notifient
les propriétaires de tous ses carnets.

## Tests à réaliser

### Test 1 : suites automatiques
```bash
docker exec hypostasia_dev_web python manage.py test core.tests front.tests.test_corpus_phase_d --noinput
```

### Test 2 : multi-rangement à la main (le geste nouveau)
En shell (`docker exec -it hypostasia_dev_web python manage.py shell`) :
```python
from core.models import Page, Dossier
from core.services.corpus import ranger_une_note_dans_un_carnet
page = Page.objects.filter(dossier__isnull=False).first()
autre = Dossier.objects.exclude(pk=page.dossier_id).first()
ranger_une_note_dans_un_carnet(page, autre)
```
Puis recharger l'interface : la note doit apparaître sous SES DEUX
carnets dans l'arbre, avec les deux compteurs incrémentés.

### Test 3 : suppression d'un carnet
Supprimer un carnet contenant une note multi-rangée : la note doit rester
visible dans son autre carnet (la FK est réaffectée, pas mise à NULL).

### Test 4 : non-régression visuelle
Navigation, lecture, imports, drag-drop de pages, suppression de pages :
strictement identiques à avant pour les notes mono-carnet.

## Compatibilité et limites

- `Page.dossier` reste en base ; son retrait est la migration 3 (§ 4.2),
  à ne faire qu'après recette de cette phase.
- L'interface n'offre PAS encore le multi-rangement (c'est la phase G) :
  seule la mécanique est en place, exerçable en shell.
- L'arbre est verrouillé à 12 requêtes (assertNumQueries) — l'ancien
  template faisait 5 COUNT par dossier affiché.
- Les tests de `front/tests/test_phases.py` qui créaient des pages avec la
  FK seule ont reçu l'appartenance correspondante (7 setUp, prévu § 4.3).
