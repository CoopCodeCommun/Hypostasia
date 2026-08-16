# Première installation en production — deux pannes, et un proxy de trop

**Date :** 2026-08-16
**Migration :** Non

Premier `make install` sur une machine neuve (`beta.hypostasia.org`, VPS
Ubuntu 26.04, clone frais). Trois problèmes, dont deux qui n'existent
**que** sur un clone neuf — donc invisibles depuis une machine de
développement où tout est en place depuis des semaines.

**Fichiers modifiés :** `docker-compose.yml`, `Makefile`, `AGENTS.md`,
`front/tests/test_script_d_installation.py`.

---

## 1. `docker compose up -d` avant le `.env` — déjà corrigé, pas encore déployé

```
env file /home/ubuntu/Hypostasia/.env not found
make: *** [Makefile:142: install] Error 1
```

La machine tournait le Makefile du commit `55cd9f9`, qui ne connaît pas
`bin/configurer_env.sh`. Le correctif était sur `dev` ; il manquait un
`git pull`. Rien à corriger — mais la trace est gardée, parce que le
message d'erreur ne dit pas « ton Makefile est vieux ».

Après le pull, la fabrication du `.env` a fonctionné du premier coup :
trois questions, secrets tirés au hasard, et au second passage
`[env] .env deja present — inchange.`

## 2. Docker crée les points de montage manquants **en root**

C'est la panne de fond, et elle boucle.

```
PermissionError: [Errno 13] Permission denied: '/app/staticfiles/admin'
```

La chaîne, mesurée :

1. `staticfiles/` et `media/` sont **ignorés par git** : un clone frais
   ne les a pas.
2. `docker-compose.yml` les monte dans `nginx`
   (`./staticfiles:/app/staticfiles:ro`, `./media:/app/media:ro`).
3. Au premier `up -d`, le **démon** Docker crée les dossiers absents.
   Mesure du 16 août 2026, `docker run -v <chemin absent>:/x` : ils
   apparaissent en **`0 0`** (root:root), mode 755.
4. Le conteneur web tourne en **uid 1000** (`USER hypostasia`,
   Dockerfile) : `collectstatic` ne peut pas créer `staticfiles/admin`.
5. `bin/install.sh` s'arrête sous `set -e`, `bin/start-dev.sh` sort, et
   `restart: unless-stopped` relance — **en boucle**.

Constaté sur la machine : `logs/` en `1000 1000` (il arrive avec le
clone, `logs/init` est suivi), `media/` et `staticfiles/` en `0 0`,
créés à la seconde près par le premier `up -d`. L'utilisateur `ubuntu`
est bien uid 1000 : il n'y a **pas** de décalage d'uid, seulement deux
dossiers posés par root.

**Pourquoi ça ne se voit jamais en développement :** les deux dossiers
existent depuis des semaines, créés par l'utilisateur.

**Pourquoi le `mkdir -p` de `bin/install.sh` ne rattrape rien :** il
tourne **dans** le conteneur, après que Docker a créé les dossiers, et
`mkdir -p` réussit sur un dossier existant quel qu'en soit le
propriétaire. Il ne lève donc aucune erreur — l'étape `[2/6]
Repertoires...` passe au vert, et c'est `[4/6] Collectstatic` qui tombe.

**Correctif :** `make install` crée les dossiers **sur l'hôte**, avant
`docker compose up -d`. Trois tests le tiennent, et l'un d'eux relit
`docker-compose.yml` : tout montage hôte ignoré par git devra être créé
par `make install`, sinon la panne se rejouera à la première ligne de
volume ajoutée.

*Remise en état d'une machine déjà touchée :*
`sudo chown -R 1000:1000 staticfiles media`.

## 3. Le compose embarquait son propre Traefik

Il prenait `0.0.0.0:80` et `:443`, alors que ces ports appartiennent au
**Traefik partagé** de la machine — celui qui détient le réseau
`frontend`, déclaré `external: true` dans ce même fichier, et qui
définit le résolveur `myresolver` que les labels de `nginx` réclament.

La contradiction était dans le fichier depuis le début : on déclare un
réseau externe (donc possédé par une autre stack) **et** on embarque le
proxy censé le posséder. Deuxième symptôme, lui aussi mesuré : notre
Traefik ne définissait **aucun** `certificatesresolvers`, alors que le
label `certresolver=myresolver` en demande un. Le site ne répondait
qu'en TLS auto-signé — `curl -sk` passait, un navigateur aurait affiché
un avertissement.

Le service est retiré. La stack ne publie **plus aucun port de l'hôte** ;
`nginx` s'inscrit auprès du proxy partagé par ses labels, et c'est tout.

> **Prérequis désormais explicite :** le Traefik partagé doit tourner
> **avant** cette stack. Sans lui, tous les conteneurs démarrent
> parfaitement et rien ne répond sur le domaine — personne n'écoute sur
> 80, et aucun message ne le dit.

---

## Comment tester (à la main) / Manual test

### A. Le cas qui a produit la panne — un clone vraiment neuf

Sur une machine où le projet n'a jamais tourné, ou en simulant :

```bash
git clone <depot> /tmp/essai-clone && cd /tmp/essai-clone
ls -d staticfiles media          # doivent être ABSENTS
make install
```

**Attendu :** `make install` crée les deux dossiers avant de lancer
Docker, l'installation va jusqu'au bout, et :

```bash
ls -ldn staticfiles media        # tous deux en <ton uid> <ton gid>
```

**Le signe de la panne :** `0 0` au lieu de ton uid. Le conteneur web
boucle alors sur `PermissionError` — visible par
`docker compose logs web | grep PermissionError`.

### B. Le proxy est bien dehors

```bash
docker compose config --services     # postgres redis web nginx — pas de traefik
docker compose ps --format '{{.Service}}\t{{.Ports}}'
```

**Attendu :** aucune ligne ne publie `0.0.0.0:80` ni `:443`.

Puis, le Traefik partagé étant démarré :

```bash
docker network inspect frontend --format '{{range .Containers}}{{.Name}} {{end}}'
curl -s -o /dev/null -w '%{http_code}\n' https://<ton domaine>/
```

**Attendu :** `hypostasia_nginx` figure sur le réseau, et le domaine
répond `200` — **sans** `-k`, le certificat étant délivré par le
résolveur du proxy partagé.

**Si le proxy n'est pas démarré :** les conteneurs sont tous `Up`, et le
domaine ne répond pas. C'est le comportement attendu, pas une panne de
cette stack.
