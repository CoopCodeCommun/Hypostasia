# Couche corpus, phase H : la base de connaissances

**Date :** 2026-08-08
**Migration :** Non

**Quoi / What :** le troisieme niveau du modele Praxis : GET /bases/ et
/bases/{slug}/ (carnets de la base avec les categories de CHAQUE relation
carnet-base — meme patron que la note, un cran au-dessus),
POST carnets/ (ranger un carnet, idempotent, exige ecriture base +
lecture carnet), GET/POST categories/ (axes de la base, validation
phase B deja en place). Acces : public / owner / legacy — pas de partage
fin en v1 (§ 6.2), pas de bypass superuser en ecriture. On ne nomme
jamais un carnet que le demandeur ne peut pas lire.

| Fichier | Changement |
|---|---|
| `front/views_corpus.py` | + BaseViewSet + les deux fonctions d'acces base |
| `front/templates/front/corpus/` | bases_liste, base_detail, partials/categories_de_la_base |
| `front/urls.py`, `front/templates/front/base.html` | routes /bases/ + branches de cascade |
| `front/tests/test_corpus_phase_h.py` | 11 tests |

### Relecture / Review
Relecture adverse passee (8 aout), 4 bloquants corriges avec tests :
- le compteur de carnets de la liste ne compte plus les carnets
  invisibles (meme doctrine « jamais de fuite » que « dans N carnets ») ;
- la clause legacy est RETIREE des bases : BaseDeConnaissances est un
  modele neuf, owner=None ne peut venir que d'un compte supprime — une
  base privee orpheline se FERME, elle ne s'ouvre pas a tout authentifie ;
- POST /bases/ cree une base (sinon aucune base ne pouvait exister,
  l'admin etant desactive) + formulaire dans la liste ;
- formulaires « Ajouter un carnet » et « + Axe » dans le detail (les
  endpoints etaient orphelins), liens croises /carnets/ ↔ /bases/.
Egalement : 404 (pas 403) sur base privee — le slug EST le nom, un 403
serait un oracle d'existence ; et POST .../carnets/{id}/retirer/ —
l'owner de la base OU l'owner du carnet peut retirer (doctrine du 8 aout).

### Trous de spec § 9 releves (a trancher)
La relation carnet-base a des categories, un epinglage et un ordre manuel
au modele (§ 3.2) mais AUCUN endpoint dans la spec § 9 pour les poser
(pas d'equivalent de categoriser/epingler/reordonner cote base). Le
patron « meme chose, un cran au-dessus » s'arrete a mi-chemin.

### Migration
- **Migration necessaire / Migration required :** Non.

