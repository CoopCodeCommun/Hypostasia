# Trous de spec § 9 bouches, e2e § 10, audit UX/UI

**Date :** 2026-08-08
**Migration :** Non

**Quoi / What :**
1. La relation carnet-base est complete : POST /bases/{slug}/carnets/{id}/categories/
   (validation phase B en filet) et .../epingler/, avec l'UI (crayon +
   epingle dans le detail de base). 19 tests.
2. Les 5 scenarios e2e que la spec § 10 prevoyait existent enfin :
   front/tests/e2e/test_22_corpus.py (2e carnet, categorisation isolee,
   filtres ET/OU, avertissement dernier carnet, ordre au clavier) —
   verts dans un vrai navigateur. Les 37 controles de l'etalon passent.
3. Audit UX/UI en navigation reelle (agent Opus, donnees = copie de
   prod) : rapport complet dans PLAN/audit-ux-ui-2026-08-08.md
   (16 defauts D1-D16, 18 propositions P1/P2/P3). Corrections immediates
   appliquees : navigation « Carnets » / « Bases » dans la barre (une
   fonctionnalite sans point d'entree n'existe pas), etat vide didactique
   de /bases/, compteurs a zero tus, onglets « cible » regroupes en un
   indicateur « a venir » (jargon de spec retire), bloc « Dans N
   carnets » SOUS le titre (ordre de l'etalon), middleware
   Cache-Control: no-cache sur le HTML (UI perimee constatee en direct).

**Incident repare / Incident fixed :** hyp.nasjo.fr etait en 500 depuis
~7 h — workers gunicorn demarres avant les changements du jour (vieux
models.py en memoire, views.py neuf sur disque). Redemarrage du conteneur
dev. A retenir : redemarrer hypostasia_dev_web apres chaque session de
dev (ou ajouter --reload au gunicorn de dev).

### Migration
- **Migration necessaire / Migration required :** Non.

