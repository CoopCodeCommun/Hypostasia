# L'INSTALLATION CHARGEAIT LE MAUVAIS JEU DE DONNEES

**Date :** 2026-08-15
**Migration :** Non

**Quoi / What :** une installation neuve arrivait sans aucune base de
connaissances, et les documents visibles n'etaient pas ceux du depot.
/ A fresh install came up with no knowledge base, showing documents that
were not the repository's own.

### LE DEFAUT

`install.sh` appelait `charger_fixtures_demo`, qui ecrit des notes
FICTIVES en dur et ne cree AUCUNE base de connaissances. Les documents
etalons de `sample/` — choisis pour couvrir les cinq formes d'entree du
produit : capture web, fichier ecrit, transcription deja faite, audio
brut, PDF — sont charges par `charger_fixtures_sample`, que le script
n'appelait pas. Leurs extractions viennent d'une troisieme commande,
`charger_extractions_demo`, pas davantage appelee.

Trois jeux de donnees coexistaient donc, et l'installation lancait le
seul qui ne montre pas le produit. Constate a l'ecran : `/bases/` vide.

### CE QUE CHARGE DESORMAIS UNE INSTALLATION

    migrate → collectstatic
      → charger_fixtures_sample      les 6 documents de sample/,
                                     la base, le carnet, les analyseurs
      → charger_extractions_demo     les extractions et commentaires,
                                     ecrits a la main pour couvrir des
                                     cas limites (marques imbriquees,
                                     ancre sur tableau, 0/1/2 commentaires)
      → charger_fixtures_llm_reel    2 notes analysees par le VRAI modele

Le premier passage convertit deux PDF avec Docling (~3 min) ; les
suivants prennent 10 s, tout etant deja present. C'est ce qui permet au
conteneur de rejouer ce script a chaque demarrage sans rien recouter.

### L'INSTALLATION TESTE MAINTENANT LES CLES API

Decision du mainteneur : les analyses de la demonstration passent par de
VRAIS appels au modele, plus par des extractions simulees. Deux notes
sont ingerees par le moteur ELEMENT puis analysees pour de bon — si une
cle manque ou si l'appel echoue, l'installation le dit au lieu de
laisser croire que tout va bien.

Les analyses partent dans la FILE CELERY (`--asynchrone`) : le demarrage
du conteneur n'attend pas le modele, et l'administrateur suit leur
avancement depuis le menu des taches — badge, position dans la file.
Mesure : 4 puis 3 extractions reelles produites par Gemini 2.5 Flash.

`--si-absent` empeche la facture de se repeter. Le conteneur rejoue
`install.sh` a CHAQUE demarrage ; sans cette garde, un simple
`docker compose restart` renverrait deux appels payants. Une analyse
deja EN FILE compte comme faite — sans quoi un redemarrage pendant le
traitement les aurait toutes renvoyees.

### LES FIXTURES APPARTENAIENT AU MAUVAIS UTILISATEUR

Le menu des taches ne montre a chacun que SES notes. Le proprietaire des
fixtures decide donc de qui voit l'installation travailler — et la regle
etait « le premier superuser, sinon le premier utilisateur par cle
primaire ». Or aucun compte n'est superuser dans ce projet, et le
premier par pk est un compte de demonstration : sur la base reelle,
`marie` portait douze notifications et l'administrateur `jonas` n'en
voyait aucune. La regle prefere desormais un compte d'administration
(superuser, puis staff) avant de retomber sur le premier venu.

### DEUX COMMANDES ETAIENT CASSEES

**`reset_demo` vidait la base et ne la rechargeait plus.** Il faisait
`flush` puis `loaddata demo_completes.json` — une fixture qui ne se
chargeait plus depuis le 21 mars 2026, cinq mois, a cause de deux
migrations qui ont change le schema sous elle. Qui la lancait perdait
tout sans rien recuperer. Ironie : la migration 0020 porte le
commentaire « App pas en production — reset_demo les recree
proprement ». Le filet de securite invoque etait lui-meme rompu. Il
recharge desormais par le meme chemin que `install.sh`.

**`--reset` de `charger_fixtures_llm_reel` levait une ProtectedError**
des la premiere execution reussie : une analyse produit des ancrages, un
ancrage protege son ElementDocument, qui protege sa Page. L'option de
remise a zero ne fonctionnait qu'avant d'avoir servi a quelque chose.
Elle defait maintenant l'ancrage avant la note, et cherche le carnet par
son nom seul — filtrer sur le proprietaire courant laissait un carnet
homonyme derriere elle quand ce proprietaire changeait.

### LES JOURNAUX DE DEV ETAIENT INVISIBLES

Le mode dev faisait `sleep infinity` et les services etaient lances a la
main sous un supervisord demonise, journaux dans des fichiers :
`docker compose logs -f` ne montrait RIEN. Le conteneur enchaine
desormais `install.sh` puis supervisord en PID 1, comme la production,
et tout sort sur la sortie standard — en DEBUG.

### CE QUI RESTE OUVERT

Les quatre fixtures JSON (`demo_ia`, `demo_completes`,
`exemple_deliberation`, `demo_alignement_versions`) ne sont chargees par
personne : ni l'installation, ni aucun test. Trois d'entre elles ne se
chargent plus depuis cinq mois. Leur suppression est decidee mais pas
faite — elles portent du travail non committe (la correction du
referentiel famille 4). A supprimer apres un commit, en retirant alors
la liste `FIXTURES_PORTANT_LE_REFERENTIEL` du test du referentiel.

---

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

