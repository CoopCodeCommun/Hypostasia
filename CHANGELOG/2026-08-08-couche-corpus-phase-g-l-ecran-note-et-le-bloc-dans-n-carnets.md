# Couche corpus, phase G : l'ecran note et le bloc « Dans N carnets »

**Date :** 2026-08-08
**Migration :** Oui

**Quoi / What :** le bloc « Dans N carnets » editable sur l'ecran de
lecture (spec § 8.1) : chaque ligne montre un carnet ET les categories de
la note dans CE carnet-la, avec epingler, retirer (avertissement special
sur la DERNIERE appartenance, § 9), edition des categories par relation
(crayon → axes de CE carnet), « Ajouter a... » avec l'avertissement
carnet public dit AU MOMENT du geste (§ 7.3), et bascule de contexte
(le nom du carnet ouvre le carnet). Charge en HTMX par
GET /notes/{id}/carnets/bloc/ — aucun des 8 contextes de
lecture_principale.html n'est touche. Racines seulement (pas les versions).

**Egalement** : validateur hex strict sur CategorieDossier.couleur
(migration core.0045 — le champ finit dans un style= inline).

| Fichier | Changement |
|---|---|
| `front/views_corpus.py` | `bloc_carnets` (GET) + bloc enrichi (droits par ligne, carnets disponibles) |
| `front/templates/front/corpus/partials/carnets_de_la_note.html` | Reecrit : edition complete par relation |
| `front/templates/front/includes/lecture_principale.html` | + conteneur lazy du bloc |
| `core/migrations/0045_alter_categoriedossier_couleur.py` | Validateur hex |
| `front/tests/test_corpus_phase_g.py` | 7 tests |

### Migration
- **Migration necessaire / Migration required :** Oui — core.0045 (appliquee sur dev).

---

## Ce qui a été fait

Le bloc éditable sur l'écran de lecture, chargé en HTMX
(`GET /notes/{id}/carnets/bloc/`) : par ligne — icône de visibilité
(🌐/👥/🔒 : une ligne publique = la note est publique), nom du carnet
(ouvre le carnet), catégories de la note dans CE carnet, épingler
(aria-pressed), retirer (avertissement spécial « DERNIER carnet »),
crayon d'édition des catégories par relation (axes de CE carnet).
« Ajouter à… » propose mes carnets + legacy + PARTAGÉS inscriptibles
(même règle que l'extension), les publics marqués « PUBLIC : la note y
sera visible par tous » au moment du geste (§ 7.3).

Relecture adverse passée (comparée à l'étalon maquette.html) :
B2 corrigé (partagés dans le select), N5 (versions refusées sur le bloc),
N6 (visibilité par ligne), N4 (retrait du role=status théâtral),
S4 (aria-pressed), B1 (commentaire menteur corrigé — la vraie bascule
« même note, autre carnet » vit dans le fil d'Ariane, encore « cible »).

## Tests

```bash
docker exec hypostasia_dev_web python manage.py test front.tests.test_corpus_phase_g --noinput
```
7 tests. Sur le site : ouvrir une note (`/lire/{id}/`) — le bloc
apparaît sous le titre ; ajouter/retirer/épingler/catégoriser.

## Limites connues (relecture G)

- « DERNIER carnet » est calculé sur les appartenances VISIBLES du
  demandeur — l'avertissement peut être trop alarmiste pour un écrivain
  qui ne voit pas l'autre carnet (jamais une fuite).
- Sans JavaScript, le bloc ne se charge pas (hx-trigger="load") ; le POST
  de repli de retirer n'a pas de formulaire noscript.
- L'avertissement dernier-carnet ne chiffre pas les analyses/commentaires
  (l'étalon maquette:1792-1799 le demande) — à faire quand le compteur
  d'extractions par note sera disponible dans le bloc.
- Fil d'Ariane à bascule : toujours « cible », à construire avec l'écran
  note complet (maquette.html:912-931).

