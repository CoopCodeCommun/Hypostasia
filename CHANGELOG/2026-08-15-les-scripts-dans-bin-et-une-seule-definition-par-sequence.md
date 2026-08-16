# LES SCRIPTS DANS bin/, ET UNE SEULE DEFINITION PAR SEQUENCE

**Date :** 2026-08-15
**Migration :** Non

**Quoi / What :** `install.sh` et `start.sh` quittent la racine pour
`bin/`, le demarrage se separe en dev et prod, et le Makefile cesse de
recopier leurs commandes. / The scripts move to bin/, startup splits in
two, and the Makefile stops duplicating their commands.

### POURQUOI PAS TOUT DANS LE MAKEFILE

La question s'est posee : unifier vers `make`. La reponse est non, et
elle tient a un fait verifiable — **`docker` n'existe pas dans le
conteneur**. Or chaque cible du Makefile passe par `docker exec`. Le
Makefile ne peut donc tourner que depuis l'hote.

Ce sont deux plans distincts. Les scripts s'executent DANS le conteneur,
au demarrage, quand aucun hote n'est au bout du fil : au boot de la
machine, apres un redeploiement, quand la restart policy relance le
service. C'est precisement ce qui garantit « les fixtures chargees a
chaque installation, prod comme dev ». Le Makefile, lui, vit sur l'hote
et ne fait que les APPELER.

### CE QUI CHANGE

    bin/install.sh      la sequence, avec une etape en argument :
                        tout (defaut) | fixtures | statiques | llm
    bin/start-dev.sh    installation → supervisord-dev.conf (runserver)
    bin/start-prod.sh   attente PostgreSQL → installation → supervisord.conf

Les deux fichiers compose choisissent lequel lancer selon `DEBUG` ; ils
ne portent plus aucune sequence. Une commande ecrite dans un YAML est une
commande que personne ne peut tester.

`make fixtures` et `make collectstatic` appellent desormais les etapes du
script (`bash bin/install.sh fixtures`) au lieu de reecrire les commandes
Django. Un test refuse toute cible du Makefile qui nommerait directement
une commande que le script porte deja : deux definitions d'une meme
sequence finissent toujours par diverger, et c'est ce qui a produit les
deux dernieres pannes.

### LE MAKEFILE REFUSE DE TOURNER SANS DOCKER

Il pilote Docker, il ne l'installe pas. Sans lui, chaque cible echouait
sur un « command not found » qui ne dit pas quoi faire ; elle rend
maintenant un message et un lien.

### DEBUG ET NGINX_CONF VONT ENSEMBLE

Verifie a cette occasion : la production sert le HTTP par gunicorn sur
**8001** et le WebSocket par daphne sur **8000** ; le developpement sert
les deux depuis runserver sur **8000**. Les deux configurations nginx
suivent cette difference et se choisissent par `NGINX_CONF`.

Rien ne tenait ces deux reglages ensemble. `DEBUG=true` avec la conf de
prod envoie `/` vers 8001, ou personne n'ecoute : **502 sur tout le
site**. L'inverse laisse gunicorn sans trafic. Deux tests le verrouillent
desormais. Pas de conflit de port, en revanche : 8000 et 8001 sont
internes au conteneur, seul traefik expose 80 et 443, et les deux stacks
ne tournent jamais ensemble.

### LE GARDE-FOU D'INSTALLATION RESTE PAR COMMANDE

La question s'est posee d'ajouter un garde global « si la base est
peuplee, ne rien faire ». C'est un recul : il empecherait de rattraper
une installation partielle — une analyse LLM qui a echoue faute de cle
doit pouvoir repartir au demarrage suivant, alors meme que la base est
pleine. Chaque commande saute ce qui la concerne, ce qui est plus fin et
deja mesure : 10 s au second passage, rien de reecrit.

