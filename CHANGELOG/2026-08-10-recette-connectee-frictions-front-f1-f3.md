# Recette connectee : les trois frictions FRONT sont corrigees (F1, F2, F3)

**Date :** 2026-08-10
**Migration :** Non

**Quoi / What :** les trois defauts d'experience releves par la recette
connectee du carnet 1 (PLAN/recette-connectee-2026-08-10.md). Ils
avaient un point commun : **le produit travaillait sans le dire**.

**F1 — une production se lancait sans le moindre retour.** « Creer le
wiki » et « Produire la synthese » renvoyaient LA LISTE. Le nouvel
objet y apparaissait comme s'il etait fini — « tour 1 · 0 sources · 465
ecartees » — alors que la tache venait de partir. Rien ne disait
d'attendre, rien ne se rafraichissait : en recette, la conclusion
naturelle etait « le wiki est vide » et le reflexe, recliquer.

**F2 — la verification ne disait jamais qu'elle etait finie.** Son
message « Verification lancee… » restait affiche POUR TOUJOURS : le
partial etait rendu sans `hx_get`, donc sans interrogation. Les
verdicts n'apparaissaient qu'apres un rechargement manuel que rien ne
suggerait.

**F3 — appliquer un diff depuis l'URL d'un article ne faisait RIEN.**
Le formulaire visait `#corpus-panneau-onglet`, qui n'existe que dans
l'onglet du carnet : un utilisateur arrive par lien partage ou par F5
cliquait « Appliquer les operations cochees » sans aucun effet. La
cible est desormais l'article lui-meme (`closest
[data-testid='synthese-article']`, remplace en `outerHTML`), present
dans les DEUX contextes — et la reponse EST l'article.

**Un seul point d'entree pour F1 et F2** : `GET /wikis/{pk}/etat/` et
`GET /syntheses/{page_pk}/etat/`, avec `?job_id=N`. Tant que le job
tourne, il se renvoie lui-meme (`hx-trigger="load delay:3s"`) ; quand
il finit, il rend ce que l'utilisateur attend — la LISTE apres une
production (il est dans l'onglet, il voit sa ligne avec ses vrais
compteurs), l'ARTICLE apres une verification (il y est deja, ce sont
les verdicts qu'il attend).

**Trois garde-fous**, parce qu'un ecran qui interroge en boucle est une
friction de plus : un compteur d'essais transforme un worker mort en
MESSAGE au bout de ~5 minutes au lieu d'interroger indefiniment ; un
job en erreur le dit et rassure (« Rien n'a ete modifie ») ; et un job
qui appartient a une AUTRE page n'est pas suivi (404) — le suivi
respecte l'acces a l'article comme le reste du produit.

10 tests neufs verrouillent le tout, y compris ce qu'on ne peut pas
exercer au navigateur sans declencher un appel LLM facture : job en
attente, plafond d'essais, job en erreur, job d'une autre page. Verifie
aussi au navigateur (endpoint, cablage, non-regression, aucune erreur
JS), sans lancer une seule production.

591 tests unitaires + 104 e2e verts.

| Fichier | Changement |
|---|---|
| `front/views_synthese.py` | `_etat_de_la_tache()`, action `etat` sur les deux ViewSets, retours de creation et de verification |
| `front/templates/front/corpus/partials/diff_operations.html` | la cible d'application existe enfin dans les deux contextes |
| `front/tests/test_retour_de_production.py` | **nouveau** : 10 tests (F1, F2, F3, garde-fous, acces) |

### Migration
- **Migration necessaire / Migration required :** Non.

