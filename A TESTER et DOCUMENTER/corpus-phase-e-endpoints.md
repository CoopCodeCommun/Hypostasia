# Couche corpus, phase E — endpoints du carnet et du rangement

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
