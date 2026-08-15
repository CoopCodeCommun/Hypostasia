# Installation — le bon jeu de données, analysé par le vrai LLM

> Écrit le 15 août 2026. Réfère : CHANGELOG du 15 août, `install.sh`,
> `docker-compose.yml`, décisions du mainteneur prises en séance.

## Le défaut trouvé

`install.sh` appelait `charger_fixtures_demo` — des notes **fictives**
écrites en dur, **aucune base de connaissances**. Les documents de
`sample/` sont chargés par `charger_fixtures_sample`, leurs extractions
par `charger_extractions_demo` : ni l'une ni l'autre n'était appelée.
Symptôme constaté à l'écran par le mainteneur : `/bases/` vide.

## Ce que fait maintenant une installation

```
docker compose up -d
  └─ bin/start-dev.sh   (DEBUG=true)   |   bin/start-prod.sh  (DEBUG=false)
       └─ bin/install.sh
            ├─ migrate, collectstatic
            ├─ charger_fixtures_sample      6 documents, la base, le carnet
            ├─ charger_extractions_demo     extractions + commentaires
            └─ charger_fixtures_llm_reel    2 notes → VRAI LLM, en file Celery
       └─ supervisord (PID 1)
            dev  : runserver:8000 + 2 workers Celery
            prod : gunicorn:8001 + daphne:8000 + 2 workers Celery
```

Les scripts sont dans **`bin/`** et s'exécutent **dans le conteneur** —
c'est ce qui leur permet de tourner au démarrage sans hôte. Le Makefile
vit sur l'hôte et ne fait que les appeler : `make fixtures` lance
`bash bin/install.sh fixtures`, il ne recopie aucune commande.

Chaque étape est appelable seule :
`bash bin/install.sh fixtures | statiques | llm`.

Premier passage ~3 min (deux conversions PDF Docling). Passages suivants
**10 s** : tout est idempotent, rien n'est refait, **rien n'est
refacturé**.

## Vérifié en conditions réelles

- `make install` sur une base **vierge** (après ton `docker compose
  down -v`) : migrations, 6 documents, base « Démonstration » créée.
- Second passage : **10 s**, tout sauté.
- Analyses réelles par **Gemini 2.5 Flash** : 4 puis 3 extractions,
  jobs `completed`, envoyées par `.delay()` et traitées par le worker.
- `docker compose logs -f web` montre les trois services, en **DEBUG**.
- Le carnet analysé appartient à **jonas**, qui voit ses 2 notifications
  dans le menu des tâches (`_calculer_etat_bouton`).
- **1734 tests verts** avant ces derniers changements ; suite relancée
  après (voir plus bas).

## À tester à la main

1. **L'installation depuis zéro.** `docker compose down -v && docker
   compose up -d`, puis `docker compose logs -f web`. Tu dois voir les
   sept étapes défiler, puis les trois services démarrer. Compter
   ~3 min. À la fin : `/bases/` affiche « Démonstration », et le carnet
   « Documents étalons » porte six notes.

2. **Le propriétaire.** Sur cette base neuve, tout doit appartenir à
   **jonas** (`admin1234`) — c'est le compte que crée
   `charger_fixtures_sample` quand la base n'a aucun utilisateur. Vérifie
   que son menu des tâches montre bien les deux analyses.

3. **Le test des clés API.** Coupe volontairement `GOOGLE_API_KEY` dans
   `.env`, refais une install neuve : l'étape 7 doit le signaler au lieu
   de passer en silence.

4. **Pas de refacturation.** `docker compose restart web` : l'étape 7
   doit afficher « Démonstration déjà analysée par le modèle — rien à
   refaire ». Si elle relance des appels, la garde est cassée.

5. **`make fixtures-llm`** (rejoue les analyses, **facturé**, demande
   confirmation) : vérifie que répondre autre chose que `oui` annule.

6. **`reset_demo`.** Sur une base que tu peux perdre uniquement : la
   commande vide **puis** recharge. Avant ce chantier elle vidait sans
   recharger. Ne la lance pas sur une base qui compte.

7. **Le switch dev ↔ prod.** C'est le piège que j'ai trouvé en te
   répondant, et il n'était protégé par rien : `DEBUG` et `NGINX_CONF`
   doivent changer **ensemble**. Bascule `.env` en `DEBUG=false` +
   `NGINX_CONF=default.conf`, `docker compose up -d --force-recreate web`,
   et vérifie que le site répond — gunicorn sert alors `/` sur 8001 et
   daphne le `/ws/` sur 8000. Si tu oublies `NGINX_CONF`, tu auras un 502
   sur tout le site : c'est le symptôme à reconnaître. Pas de conflit de
   port, la base est partagée sans souci.

8. **`make` sans Docker.** `env PATH=/un/chemin/sans/docker make install`
   doit rendre un message clair, pas un « command not found ».

## Ce qui reste ouvert

**Les quatre fixtures JSON ne sont supprimées.** Tu as validé leur
suppression, mais je ne l'ai pas faite : les trois `demo_*.json` portent
la correction du référentiel famille 4 de l'autre session, **non
committée**. Les supprimer maintenant effacerait ce travail du working
tree. Commite d'abord, je supprime ensuite — et je retire alors la liste
`FIXTURES_PORTANT_LE_REFERENTIEL` de
`hypostasis_extractor/tests/test_referentiel_des_hypostases.py`, sinon ce
test échouera.

**Ta base actuelle est mélangée.** Elle porte encore les cinq notes
fictives de mon premier `make install` (avant correction), et `marie`
possède les documents de `sample/` chargés avant la correction du
propriétaire. Un `down -v` + `make install` donnera l'état propre.

**L'ampleur de l'analyse LLM n'est pas tranchée.** Aujourd'hui seules
deux notes témoins passent par le modèle ; les six documents de `sample/`
gardent des extractions écrites à la main, qui couvrent exprès des cas
limites qu'un modèle ne produit pas de façon fiable. Les faire tous
analyser coûterait : 121 éléments pour les cinq petites notes, **549
pour la seule Présentation V3** (73 % du total). Question laissée
ouverte.
