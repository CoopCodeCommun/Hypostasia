# Couche corpus, phase E : endpoints du carnet et du rangement

**Date :** 2026-08-08
**Migration :** Non

**Quoi / What :** la premiere couche HTTP de la couche corpus
(SPEC-corpus § 9) : `CarnetViewSet` (liste, detail, notes filtrees par
facettes, gestion des axes/categories, ordre manuel) et
`NoteCorpusViewSet` (ajouter a un carnet, retirer — sans jamais supprimer
la note —, categoriser par relation, epingler). Reponses HTML/HTMX
uniquement, `AllowAny` avec controle PAR OBJET.

**Pourquoi / Why :** les phases A-D ont pose la mecanique ; ces endpoints
la rendent actionnable. Les filtres § 8.2 : OU dans un axe, ET entre les
axes. Ranger exige la lecture de la note ET l'ecriture sur le carnet
cible (on ne range pas — donc on n'expose pas — ce qu'on ne peut pas lire).

### Fichiers ajoutes / Added files
| Fichier / File | Role / Purpose |
|---|---|
| `front/views_corpus.py` | Les deux ViewSets + le filtre par facettes |
| `front/templates/front/corpus/` | 2 ecrans + 4 partials (bloc « Dans N carnets », notes filtrees, categories, erreurs) — mise en forme definitive en phase F contre l'etalon corpus.html |
| `front/tests/test_corpus_phase_e.py` | 21 tests : permissions par objet, anonyme sur public, ET/OU des facettes, rangement/retrait, categorie etrangere en 400, epinglage, reordonnancement |

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `front/serializers.py` | + AjouterAUnCarnetSerializer, ReordonnerLeCarnetSerializer, GererCategoriesSerializer |
| `front/urls.py` | + routes `/carnets/` et `/notes/` |

### Relecture / Review
Relecture adverse + comparaison structurelle a l'etalon (agent Opus)
passees le 8 aout. 3 bloquants corriges, chacun avec son test :
- IDOR sur retirer_d_un_carnet (l'appartenance doit exister → 404, sinon
  l'endpoint servait d'oracle d'enumeration) ;
- le bloc « Dans N carnets » ne montre plus que les carnets que le
  DEMANDEUR peut lire (nommer le carnet prive d'un tiers etait une fuite) ;
- ?categorie=abc ne fait plus de 500 (ids numeriques seulement).
Egalement : versions non rangeables (404), reordonner en transaction +
bulk_update, les notes sans ordre manuel (0) trient APRES les ordonnees.
Le cahier des charges de la phase F (ecarts vs corpus.html + 7 arbitrages
spec/etalon) est dans PLAN/corpus-phase-f-cahier-des-charges.md.

### Question ouverte relevee / Open question raised
Le proprietaire d'une note ne peut pas la retirer d'un carnet ou il n'a
pas l'ecriture — alors qu'un tiers peut ranger sa note dans un carnet
public et la rendre publique. La spec § 9 ne tranche pas ; « ecriture sur
le carnet OU propriete de la note » serait defendable. A trancher.

### Migration
- **Migration necessaire / Migration required :** Non.

---

## Ce qui a été fait

La première couche HTTP de la spec corpus (§ 9), en HTML/HTMX uniquement :

| Route | Rôle |
|---|---|
| `GET /carnets/` | Mes carnets + partagés + publics (anonyme : publics) |
| `GET /carnets/{id}/` | Le carnet, ses notes, ses facettes |
| `GET /carnets/{id}/notes/?categorie=N` | Partial filtré — OU dans un axe, ET entre axes (§ 8.2) |
| `GET/POST /carnets/{id}/categories/` | Axes et catégories (créer axe / créer catégorie) |
| `POST /carnets/{id}/reordonner/` | Ordre manuel (l'ordre de la liste reçue = 1, 2, 3…) |
| `POST /notes/{id}/carnets/` | Ajoute la note à un carnet |
| `DELETE /notes/{id}/carnets/{carnet_id}/` | Retire — ne supprime JAMAIS la note |
| `POST /notes/{id}/carnets/{carnet_id}/categories/` | Catégories de CETTE relation |
| `POST /notes/{id}/carnets/{carnet_id}/epingler/` | Bascule l'épinglage |

Règle de rangement : lecture de la note ET écriture sur le carnet cible
(on ne range pas — donc on n'expose pas — ce qu'on ne peut pas lire).

## Tests à réaliser

### Test 1 : suite automatique
```bash
docker exec hypostasia_dev_web python manage.py test front.tests.test_corpus_phase_e --noinput
```
21 tests verts.

### Test 2 : sur le site (anonyme)
Ouvrir `https://hyp.nasjo.fr/carnets/` sans être connecté : seuls les
carnets publics apparaissent. Cliquer un carnet : ses notes s'affichent.

### Test 3 : les facettes
Créer un axe et des catégories (connecté, sur son carnet) :
```bash
curl -X POST .../carnets/{id}/categories/ -d "action=creer_liste&nom=Type"
```
puis catégoriser une note et vérifier le filtre `?categorie=N` sur
`/carnets/{id}/notes/`.

## Compatibilité et limites

- Les écrans sont des pages autonomes MINIMALES : la mise en forme
  définitive (étalon `tmp/maquettes/corpus.html`) est la phase F —
  l'agent de comparaison à la maquette a produit le cahier des écarts.
- htmx n'est pas chargé par ces pages autonomes : les attributs hx-* ne
  s'activeront qu'intégrés au gabarit du site (phase F).
- L'avertissement « dernière appartenance » et « carnet public » (§ 9,
  § 7.3) sont des gestes d'interface : phases F/G.

