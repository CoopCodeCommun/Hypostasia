# Couche corpus, phase C : permissions par les carnets

**Date :** 2026-08-08
**Migration :** Non

**Quoi / What :** les trois fonctions de permission de la couche corpus
(SPEC-corpus § 5.2) : `_utilisateur_a_acces_page`,
`_utilisateur_peut_ecrire_page`, `_est_proprietaire_page`, plus le helper
`_dossiers_contenant_la_page` (contrat prefetch, § 5.3).

**Pourquoi / Why :** sous le N-N, « le dossier de la page » n'existe plus.
L'acces se derive des carnets (le plus permissif gagne), la propriete
s'ELARGIT (owner de la note OU owner d'un carnet la contenant) — le prof
garde la moderation sur les captures des eleves, l'eleve garde ses droits.
Le comportement legacy (note sans carnet sans owner → tout authentifie)
est preserve.

### Fichiers modifies / Modified files
| Fichier / File | Changement / Change |
|---|---|
| `front/views.py` | + les 3 fonctions + helper ; `_est_proprietaire_dossier` marquee DEPRECIEE (bascule des appelants en phase D, en un seul lot) |
| `core/tests/test_corpus_permissions.py` | 17 tests : carnet le plus permissif, anonyme sur carnet public, legacy, cas-piege (owner sans acces : les carnets decident), partage direct et par groupe, superuser (lecture oui / ecriture non), moderation du prof, droits de l'auteur, lecture != ecriture, zero requete avec prefetch (chemins sans DossierPartage) |

### Relecture / Review
Relecture adverse passee (8 aout) : 1 bloquant corrige — le bypass
superuser en ECRITURE, absent de la spec et de l'existant, a ete retire
(seule la lecture a un bypass, prescrit). 4 points « a trancher avant la
phase D » consignes dans la fiche A TESTER (ecriture des orphelines,
proprietaire sans lecture, dossiers legacy owner=None — 0 en dev —,
assertNumQueries de la vue de liste).

### Migration
- **Migration necessaire / Migration required :** Non. Aucun appelant
  converti : les vues existantes lisent toujours `page.dossier` (phase D).

---

## Ce qui a été fait

Les trois fonctions du § 5.2 de la spec corpus, dans `front/views.py` :

| Fonction | Règle |
|---|---|
| `_utilisateur_a_acces_page` | accès si accès à AU MOINS UN carnet contenant la note ; sans carnet : legacy préservé (owner=None → tout authentifié, sinon propriétaire) |
| `_utilisateur_peut_ecrire_page` | écriture si écriture sur AU MOINS UN carnet ; lecture publique ≠ écriture |
| `_est_proprietaire_page` | owner de la note OU owner d'un carnet la contenant (le prof modère les captures des élèves, l'élève garde ses droits) |

Plus `_dossiers_contenant_la_page(page, dossiers_precharges)` : le contrat
anti-N+1 — toute vue de liste doit passer les carnets préchargés.

**Aucun appelant n'est converti** : les vues existantes lisent toujours
`page.dossier`. La bascule est la phase D, en un seul lot (spec § 4.3).

## Tests à réaliser

### Test 1 : suite automatique
```bash
docker exec hypostasia_dev_web python manage.py test core.tests.test_corpus_permissions --noinput
```
12 tests attendus verts. Le test `test_pas_de_n_plus_un_sur_la_liste`
verrouille le contrat : 0 requête avec les carnets préchargés.

### Test 2 : rien ne change à l'écran
Les fonctions ne sont branchées nulle part : naviguer dans l'application
doit être strictement identique à avant. Toute différence de comportement
d'accès est un bug de cette phase.

## Compatibilité

- `_est_proprietaire_dossier` reste en place, marquée dépréciée, utilisée
  par les vues actuelles jusqu'à la phase D.
- Superuser : bypass en LECTURE seulement (prescrit § 5.2). PAS de bypass
  en écriture — ni la spec ni `_utilisateur_peut_ecrire_dossier` n'en ont ;
  en ajouter un aurait été un changement de gouvernance dormant
  (relecture C, défaut B1, corrigé et testé).
- « 0 requête avec prefetch » ne vaut que pour les chemins sans
  DossierPartage (public, owner, legacy). Un carnet privé partagé coûte
  jusqu'à 2 requêtes DossierPartage par carnet, prefetch ou pas.

## À trancher avant la phase D (relevé par la relecture C)

1. **Écriture des notes orphelines `owner=None`** : aujourd'hui inscriptibles
   par tout authentifié (les vues ne vérifient que si `page.dossier` existe) ;
   `_utilisateur_peut_ecrire_page` les rendra inscriptibles par personne.
   La correction n°6 de la spec ne préserve que la lecture. Durcissement
   probablement souhaitable, mais à dire explicitement.
2. **Propriétaire aveugle** : `_est_proprietaire_page` rend True via
   `page.owner` même sans accès en lecture (note dans le carnet privé
   d'autrui). Prescrit par § 5.2, mais en phase D ça donne des droits de
   modération sans droit de lecture. Tension de spec à trancher.
3. **Dossiers legacy `owner=None` sous N-N** : « le plus permissif gagne »
   étendrait leur écriture-pour-tous aux notes co-rangées. Mesuré sur dev
   le 8 août : **0 dossier concerné** — risque vide ici, à re-mesurer en
   prod avant bascule.
4. Le `assertNumQueries` sur la vue de liste principale (§ 5.3) ne peut
   exister qu'en phase D — dette tracée.

