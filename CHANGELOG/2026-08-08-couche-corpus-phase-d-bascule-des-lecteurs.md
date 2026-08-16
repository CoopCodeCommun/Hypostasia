# Couche corpus, phase D : bascule des lecteurs vers la table de liaison

**Date :** 2026-08-08
**Migration :** Non

**Quoi / What :** la conversion EN UN SEUL LOT (SPEC-corpus § 4.3) de tous
les lecteurs et ecrivains de `Page.dossier` vers la table de liaison
`AppartenancePageDossier`. Une note rangee dans deux carnets apparait
desormais dans les deux, partout.

**Pourquoi / Why :** une conversion progressive etait incompatible avec la
regle « toute lecture passe par la table de liaison » — pendant la
transition, une note ajoutee a un second carnet n'y apparaissait pas.

### Le service de rangement (§ 4.3)
`core/services/corpus.py` : `ranger_une_note_dans_un_carnet` (appartenance +
FK « premier carnet », idempotent), `retirer_une_note_d_un_carnet`
(reaffectation de la FK a une appartenance restante, ou NULL),
`deplacer_une_note_vers_un_carnet` (semantique actuelle du classement).
La FK n'est plus ecrite QUE par ce service pendant la coexistence.

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `core/views.py` | Creation de page et `classer_depuis_extension` via le service ; perimetre de dedup par les appartenances |
| `front/views.py` | `_verifier_acces_page` → `_utilisateur_a_acces_page` ; 13 appels `_est_proprietaire_dossier` → `_est_proprietaire_page` (fonction supprimee) ; controles d'ecriture → `_utilisateur_peut_ecrire_page` ; imports/audio ranges via le service ; deplacement drag-drop via le service ; suppression de dossier reaffecte les FK avant delete ; arbre precharge les appartenances (`to_attr`, zero N+1) |
| `front/templates/front/includes/_dossier_node.html` | Compteurs et liste des pages par les appartenances prechargees |
| `front/views_alignement.py` | Perimetre par les appartenances |
| `front/tasks.py` | Versions de synthese : appartenances repliquees depuis la racine (§ 11) ; notifications elargies aux proprietaires des carnets, dedoublonnees (`_destinataires_de_notification`) |
| `front/tests/test_corpus_phase_d.py` | 6 tests : note visible sous ses deux carnets, compteurs, assertNumQueries(12) sur l'arbre, dedup par liaison (cas que la FK ne voyait pas), notifications dedoublonnees |
| `front/tests/test_phases.py` | 7 setUp adaptes : l'appartenance accompagne la FK (prevu par la spec § 4.3) |
| `core/tests/test_corpus_rangement.py` | 11 tests du service (FK premier carnet, reaffectation, idempotence) |
| `core/tests/test_corpus_permissions.py` | + ecriture legacy des orphelines preservee (decision point 1) |

### Les 4 decisions prealables (relecture C)
1. Ecriture des orphelines owner=None : comportement actuel PRESERVE
   (tout authentifie), symetrique de la lecture legacy. Teste.
2. Proprietaire sans lecture : § 5.2 garde tel quel — les vues verifient
   l'acces avant la propriete, l'ordre des controles protege.
3. Dossiers legacy owner=None : 0 en dev (= copie de prod), risque vide.
4. assertNumQueries : pose sur l'arbre (12 requetes, independant du nombre
   de notes — l'ancien template faisait 5 COUNT par dossier).

### Relecture / Review
Relecture adverse passee (8 aout) : 2 bloquants corriges — les comptages
d'en-tete de l'arbre restaient sur la FK (incoherence avec les noeuds,
versions comptees, N+1 que le test assertNumQueries absorbait : recale de
12 a 9 requetes, desormais independant du nombre de dossiers) ; et un 500
sur import avec dossier_id perime (le service refuse None proprement, les
4 sites d'import laissent la page orpheline comme avant). Egalement :
FK des versions ecrite par le service seul, reaffectation des FK deplacee
dans un signal pre_delete (couvre l'admin et le shell, teste), message de
suppression honnete (orphelines vs restees ailleurs), bouton « Supprimer
cette version » aligne sur la regle de l'endpoint via le filtre
`est_moderable_par` (front/templatetags/corpus_permissions.py).

### Limites connues / Known limits
- Drag-drop de page : semantique mono-carnet conservee (la vue ne connait
  que la destination ; « sortir » retire du carnet FK, pas du carnet
  d'origine du geste). A reprendre avec l'UI multi-carnets (phase G).
- L'ordre des notes dans l'arbre suit desormais le tri des appartenances
  (epinglees, ordre manuel, plus recentes d'abord).
- Notifications elargies pour la synthese seulement (§ 11) ; analyse et
  transcription restent owner-only, comme avant.

### Migration
- **Migration necessaire / Migration required :** Non (le schema date de la
  phase A). `Page.dossier` reste en place — son retrait est la migration 3,
  apres recette.

---

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

