# UN MAKEFILE, POUR QUE LES COMMANDES CESSENT DE DERIVER

**Date :** 2026-08-14
**Migration :** Non

**Quoi / What :** un `Makefile` a la racine rassemble le demarrage, les
tests et la mise a jour de production. / A Makefile gathers startup,
tests and production update.

### POURQUOI, PRECISEMENT

Le lancement de dev avait derive pendant des semaines sans que personne
ne le voie : un worker Celery unique tirait `-Q celery,ingestion_docling`
a concurrence 2, la ou la production declare un worker DEDIE a
concurrence 1. La commande exacte vivait dans une passation Markdown —
un document qu'on lit, pas qu'on execute. Le Makefile la rend
EXECUTABLE : ce qui se tape ne peut plus diverger de ce qui est ecrit.

Les cibles sont une FACADE, jamais une reimplementation : `make install`
appelle `install.sh`, `make dev` appelle `supervisord-dev.conf`. Deux
descriptions du meme demarrage finiraient par diverger — c'est
exactement la panne qu'on vient de corriger.

### LES TESTS, PAR CE QU'ILS COUTENT

    make test-rapide     tout sauf e2e/docling/llm — le geste quotidien
    make test-suite S=…  une suite precise
    make test-e2e        30 fichiers Playwright, plusieurs minutes
    make test-docling    conversions Docling REELLES (~85 s)
    make test-llm        appels LLM REELS — FACTURES, confirmation demandee
    make test-tout       rapide + e2e + docling, PAS le LLM payant

`test-tout` exclut deliberement le LLM : un geste machinal ne doit pas
coûter d'argent.

**Une ligne a rendu `test-rapide` possible** : `@tag("e2e")` sur
`PlaywrightLiveTestCase` (front/tests/e2e/base.py), la classe de base
dont heritent les 37 classes des 30 fichiers navigateur. Sans elle,
`manage.py test` sans argument lance TOUT, Playwright compris, et il
n'existait aucun moyen d'obtenir la suite rapide seule. Verifie :
`--exclude-tag=e2e` rend 0 test sur `front.tests.e2e`, `--tag=e2e` en
rend 222.

### LA PRODUCTION, AVEC UN GARDE-FOU

`make prod-update` (git pull, uv sync, migrate, collectstatic, restart
des 4 programmes) et `make prod-status` **refusent de tourner si `.env`
porte `DEBUG=true`** : sur un poste de developpement, elles s'arretent
avec un message plutot que de faire des degats a moitie. Le nom du
conteneur est surchargeable (`CONTENEUR=…`), car `docker-compose-prod.yml`
nomme les siens `hypostasia_dev_web`.

### CE QUI N'A PAS ETE FAIT, ET POURQUOI

**Pas de cible `pytest`** : pytest n'est pas installe dans ce depot,
tout passe par `manage.py test`. Une cible serait morte des le premier
jour. Y migrer est un chantier a part entiere.

**Pas de distinction e2e court / e2e long** : rien ne les separe
aujourd'hui. `make test-e2e S=test_09_alignement` cible un fichier ; une
categorie « long » demanderait d'abord de taguer les lents.

**Pas de `collectstatic` dans `make dev`** : il ne sert a rien en
developpement — `nginx/dev.conf` n'a aucun `location /static/`, le
runserver sert les statiques par les finders quand `DEBUG=true`. La
cible existe, explicite, pour l'avant-deploiement.

**Pas de verification « les fixtures sont-elles chargees »** :
`charger_fixtures_demo` est idempotent par `get_or_create`
(install.sh § 5). Verifier par-dessus reviendrait a controler ce que la
commande garantit deja.

