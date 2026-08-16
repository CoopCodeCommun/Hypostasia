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
            ├─ charger_fixtures_sample       6 documents, la base, le carnet
            ├─ charger_extractions_demo      extractions à la main (cas limites)
            └─ analyser_les_notes_etalons    5 notes → VRAI modèle, en file Celery
       └─ supervisord (PID 1)
            dev  : runserver:8000 + 2 workers Celery
            prod : gunicorn:8001 + daphne:8000 + 2 workers Celery
```

Les scripts sont dans **`bin/`** et s'exécutent **dans le conteneur** —
c'est ce qui leur permet de tourner au démarrage sans hôte. Le Makefile
vit sur l'hôte et ne fait que les appeler ; il ne recopie aucune commande.

**Pour tout refaire : `docker compose down -v && make install`.** Une
seule voie, donc aucun doute sur l'état de la base. Les cibles
`make fixtures` et `make fixtures-llm` ont existé une journée puis ont
été retirées comme redondantes : un rechargement partiel laisse un
mélange, moitié données d'avant, moitié d'après. Les étapes restent
appelables à la main : `docker exec -w /app hypostasia_web bash
bin/install.sh fixtures` (ou `statiques`, ou `llm`).

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

5. **Un seul carnet.** `/carnets/` ne doit montrer que « Documents
   étalons ». Le carnet « Démonstration — moteur réel » et ses deux
   textes inventés ont été supprimés le 15 août 2026.

6. **Les extractions viennent bien du modèle.** Ouvre « Débat IA » ou
   « Présentation des Open Badges » : elles n'avaient **aucune**
   extraction avant ce chantier, elles en portent maintenant 21 et 30,
   produites par Gemini. « Badgeons », « Palais César » et « Étude »
   portent les deux origines — celles écrites à la main (cas limites de
   design) et celles du modèle.

7. **La Présentation V3 reste sans extraction**, volontairement : 549
   éléments, 73 % du corpus. Pour l'analyser quand même (**facturé**) :
   `docker exec -w /app hypostasia_web python manage.py
   analyser_les_notes_etalons --forcer`.

8. **Rejouer les analyses** (**facturé**) : `--forcer` sur la même
   commande, ou `down -v` + `make install` pour repartir de zéro.

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

## Les quatre fixtures JSON sont supprimées

Fait après ton commit `58d18df` — elles y restent, donc récupérables.
`front/fixtures/` n'existe plus. La classe qui surveillait leurs douze
copies du référentiel a été retirée du test, avec la raison inscrite à sa
place ; les quatre sources de code restent verrouillées.

Un message d'erreur de `front/views.py` disait encore « Chargez la
fixture demo_ia.json » — il envoyait vers un fichier disparu. Il dit
maintenant « Lancez `make fixtures` ».

## Ce qui reste ouvert

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
