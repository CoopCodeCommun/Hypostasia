# Sauvegarde borg, restauration, et bilan de production

**Date :** 2026-08-16
**Migration :** Non

Le projet n'avait aucune sauvegarde. La base vit dans un volume Docker,
`media/` porte 504 Mo de PDF, d'audios et de transcriptions hors git, et
`.env` porte les cles API : trois choses qu'un `docker compose down -v`
efface et qu'aucun `git clone` ne rend.

Six scripts dans `bin/`, quatre cibles au Makefile. La stack suit le kit
[borgwarehouse](https://github.com/CoopCodeCommun/borgwarehouse) —
depot chiffre distant, une cle SSH dediee par depot, aucun secret dans
un script versionne — applique ici a une stack Docker Compose, comme le
fait le depot Ghost pour MySQL.
/ The project had no backup at all: the database lives in a Docker
volume, media/ holds 504 MB outside git, and .env holds the API keys.

**Fichiers ajoutes**

| Fichier | Role |
|---|---|
| `bin/backup.sh` | dump PostgreSQL + `media/` + `.env` dans une archive |
| `bin/check_backup.sh` | la derniere archive est-elle VRAIMENT restaurable ? |
| `bin/restore.sh` | restauration, avec confirmation tapee |
| `bin/init_backup.sh` | cle SSH, depot BWH, `.env`, cron — appele par `backup.sh` |
| `bin/verifier_prod.sh` | bilan : depot, cron, secrets, `DEBUG`/`NGINX_CONF` |
| `bin/configurer_env.sh` | fabrique le `.env` d'une machine neuve |
| `front/tests/test_sauvegarde_borg.py` | 34 tests (52 avec `test_script_d_installation`) |

**Quatre cibles, pas six.** `make backup` / `backup-check` / `restore` /
`verif-prod`. Il n'y a **pas** de cible d'initialisation : au premier
lancement, `make backup` voit que rien n'est configure et enchaine
lui-meme sur `bin/init_backup.sh` avant de sauvegarder. Une cible qu'on
ne tape qu'une fois dans la vie d'une machine est une cible qu'on ne
retrouve pas le jour ou on en a besoin.

De meme, `make install` ne suppose plus qu'un `.env` existe : il le
fabrique, en trois questions, secrets tires au hasard.

**Le nom des archives vient de la machine**, il n'est pas demande :
`hypostasia-<hostname -s>`, d'ou `hypostasia-jonas-FW13-2026-08-16-12-05-13`.
Ce prefixe sert a deux choses, et le nom de machine convient aux deux —
reconnaitre d'ou vient une sauvegarde quand plusieurs machines
partagent un serveur, et donner a la cle SSH du depot un nom unique sur
la machine. Les caracteres hors `[a-zA-Z0-9_-]` deviennent des tirets :
ils casseraient le glob de la rotation, et l'utilisateur ne choisit pas
le nom de sa machine.

**Fichiers modifies :** `Makefile`, `.gitignore`, `.env.example`,
`README.md`, `GUIDELINES.md`, `.claude/skills/hypostasia/SKILL.md`,
`front/tests/test_script_d_installation.py`. Et, dans le depot voisin
`borgwarehouse`, `scripts/init_backup.sh` et `scripts/README.md`
(lecture du jeton).

---

## 1. Ce qui part dans une archive, et ce qui n'y part pas

Le dump PostgreSQL au format custom, `media/`, et `.env`. Le reste —
code, `docker-compose.yml`, `nginx/`, `sample/` — est dans git : le
rearchiver chaque nuit n'apporterait rien qu'un `git clone` ne rende.
Une restauration complete se lit donc `git clone` + `.env` du coffre +
`make install` + `make restore`.

Mesure du 16 aout 2026, premiere archive : 483 Mo d'origine, 400 Mo
compresses, **2,18 Mo dedupliques**, en 4,2 s. Le rapport n'est pas une
erreur de borg : `media/` contient 7245 fichiers pour **18 contenus
distincts**, les fixtures reimportant les memes documents a chaque
passage.

Le mot de passe PostgreSQL ne transite pas par le script : il est lu
dans l'environnement du conteneur, au moment du dump. Il n'apparait donc
ni dans le crontab, ni dans les journaux.

## 2. `make backup-check` deroule le dump, il ne le liste pas

Verifier qu'une archive existe ne dit rien. Un dump tronque — disque
plein, conteneur tue en plein dump — a une taille credible, se trouve
bien dans l'archive, et ne se restaure pas.

Mesure du 16 aout 2026, PostgreSQL 17.10, dump de 417 Ko :

| Amputation | `pg_restore -l` | `pg_restore -f /dev/null` |
|---|---|---|
| 100 octets | **code 0** (au vert) | code 1 |
| 5 Ko | **code 0** | code 1 |
| 50 Ko | **code 0** | code 1 |
| 53 % du fichier | code 1 | code 1 |

La liste de la table des matieres passe au vert sur tout ce qui n'ampute
pas l'en-tete. Seul le deroulement integral demasque la coupure — c'est
ce que fait la verification, sans rien ecrire en base (`-f /dev/null`
demande le SQL, pas son application).

Eprouve de bout en bout : une archive portant un dump ampute de 100
octets est bien declaree **non restaurable**, code de sortie 1.

## 3. La restauration protege le `.env` en service

`make restore` ecrase la base : elle exige donc de taper `RESTAURER`, et
refuse une entree non interactive. Elle arrete le conteneur web le temps
de l'operation — Django et Celery tiennent des connexions ouvertes, et
`pg_restore --clean` attendrait leurs verrous indefiniment — puis le
redemarre quoi qu'il arrive.

Le `.env` de l'archive est **depose a cote, jamais installe**. Il porte
peut-etre une passphrase perimee ; l'installer rendrait le depot en
service inaccessible, et on ne s'en apercevrait qu'a la restauration
suivante.

`media/` est recopie PAR-DESSUS, sans suppression : un fichier arrive
depuis l'archive reste en place. Ses lignes en base ont disparu avec le
`--clean`, il devient un orphelin inerte — preferable a une suppression
definitive faite par un script.

Les trois contenus (dump, `media/`, `.env`) sont **cherches** dans
l'arborescence extraite, jamais reconstruits par concatenation. borg
archive des chemins absolus : reconstruire reviendrait a supposer que la
machine qui restaure porte le projet au MEME chemin que celle qui a
sauvegarde. C'est vrai a l'essai, sur la machine d'origine — et faux le
jour du sinistre, quand on remonte ailleurs. Le dump se restaurerait, et
`media/` serait declare absent.

## 4. `make install` dit ce qui manque a une prod

`bin/verifier_prod.sh` controle la configuration (secrets restes a
`CHANGEZ_MOI`, `DEBUG` et `NGINX_CONF` coherents, `DOMAIN` renseigne) et
la sauvegarde (depot joignable, age de la derniere archive, ligne de
cron). Lance seul, il sort en code non nul au moindre probleme.

`make install` l'appelle avec `--a-l-installation`, ce qui change deux
choses : il se **saute entierement** sur un poste de dev (`DEBUG=true`),
et il n'arrete **jamais** l'installation. Le depot se cree depuis la
machine installee : exiger qu'il existe deja tiendrait de l'oeuf et de
la poule.

## 5. Un defaut corrige au passage : `make install` bouclait sans fin en prod

`supervisord-dev.conf` ouvre `/tmp/supervisor-dev.sock`,
`supervisord.conf` ouvre `/tmp/supervisor.sock`. L'attente d'`install`
etait codee en dur sur celle de DEV : sur une machine de production, la
boucle tournait indefiniment sur « attente des services », sans qu'une
ligne dise pourquoi. Le socket se choisit desormais selon `DEBUG`.

## 6. Deux pieges de shell trouves en EXECUTANT les scripts

Aucun des deux ne leve d'erreur visible, et tous deux rendent la
sauvegarde fausse. Les tests statiques ne les auraient jamais vus.

**`UID` est en lecture seule dans bash.** Le `.env` du projet declare
`UID=1000` et `GID=1000` pour docker compose. Un `. "$FICHIER_ENV"` brut
echoue sur cette ligne, et sous `set -e` le script s'arrete LA :
`bash bin/backup.sh` sortait en **11 ms**, sur une seule ligne d'erreur,
sans avoir rien archive. Un cron ne lit pas les lignes d'erreur. Les
deux variables sont desormais ecartees a la lecture.

**`printf | grep -q` ment sous `pipefail`.** `grep -q` sort des la
premiere correspondance, l'ecrivain du tube prend un SIGPIPE et rend
141, et `pipefail` fait de ce 141 le statut du pipeline : une
correspondance TROUVEE est lue comme une ABSENCE. Mesure sur la table
des matieres reelle d'un dump (625 lignes) : avec `pipefail`, les QUATRE
tables cherchees sont declarees absentes ; sans, aucune. Sur trois
lignes, le meme code passe au vert — c'est pourquoi un essai jouet ne le
montre pas, et pourquoi le defaut est intermittent. Toutes les
recherches passent desormais par des here-strings.

## 7. `make install` fabrique le `.env`

L'installation commencait par une etape **non ecrite** : « copier
`.env.example` et le remplir », dont seul le README portait la trace.
Son oubli le plus courant ne casse rien tout de suite — il laisse
`CHANGEZ_MOI_EN_PROD` comme `SECRET_KEY`, en production.

`bin/configurer_env.sh` tourne sur l'hote, **avant** `docker compose up`
(compose LIT le `.env` : sans lui, `POSTGRES_PASSWORD` est vide et
PostgreSQL refuse de s'initialiser). Il pose trois questions :

| Question | Ce qu'elle ecrit |
|---|---|
| dev, ou production ? | `DEBUG` **et** `NGINX_CONF`, ensemble |
| le domaine ? | `DOMAIN` |
| une cle de modele ? (facultative) | `GOOGLE_API_KEY`, `OPENAI_API_KEY`, … |

`SECRET_KEY` et `POSTGRES_PASSWORD` ne sont jamais demandees : elles
sont tirees a `openssl rand -hex`. Une cle saisie a la main est une cle
faible, ou recopiee d'un autre projet.

**Une seule question pour deux variables couplees**, parce que les
demander separement offrirait la possibilite de les mettre en desaccord
— et la conf nginx de prod avec `DEBUG=true` rend 502 sur tout le site.
Un test refuse desormais toute question portant sur `NGINX_CONF`.

Le script part de `.env.example` et n'en remplace que les lignes
concernees : la forme du fichier — l'ordre, les commentaires, les
variables facultatives — reste definie a un seul endroit.

**Idempotent** : un `.env` present n'est jamais touche. `make install`
est rejoue a chaque demarrage de conteneur ; le regenerer perdrait les
cles API, le mot de passe de la base — donc l'acces aux donnees — et la
passphrase du depot, ce qui rendrait toutes les archives illisibles.

Sans terminal (`make install` appele depuis un script), il prend les
valeurs par defaut **de production** plutot que d'attendre une reponse :
`DEBUG=true` sur une machine qu'on croyait de prod expose les traces
d'erreur, l'inverse ne prive qu'un poste de dev du rechargement
automatique. On se trompe du cote qui ne fuit pas.

Verifie : `docker compose config` lit le fichier fabrique sans un
avertissement, et le mot de passe qu'il voit est au caractere pres celui
du fichier (48 caracteres hexadecimaux).

## 8. Deux sauvegardes a la suite echouaient

Le nom d'archive porte l'horodatage, a la minute — la granularite du kit
d'origine. Or borg refuse deux archives homonymes, et une sauvegarde
prend 4 s : deux `make backup` lances a la suite echouaient donc sur
`Archive ... already exists`, rendu a l'utilisateur sous la forme d'un
`code 2` qui ne dit pas pourquoi. L'horodatage porte desormais les
secondes.

## 9. Ce qu'une relecture adverse a trouve, et qui est corrige

Relecture par un agent, avec consigne de chercher ce qui est faux. Neuf
constats retenus, tous verifies avant correction — dont deux qui
contredisaient ce qui est ecrit ci-dessus.

**Le coffre ne suffisait pas a restaurer.** Il listait l'adresse du
depot, la passphrase et `borg key export` : les trois ouvrent le
CHIFFREMENT. Aucun n'ouvre l'ACCES. Sur borgwarehouse, le depot
n'accepte que la cle publique enregistree sur lui ; sans la cle privee —
qui vit dans `bin/.ssh/`, ignoree par git a raison, et absente de
l'archive — une machine de secours se fait refuser par SSH avant meme
d'avoir a prouver qu'elle connait la passphrase. La restauration decrite
dans le README s'arretait la. Le coffre compte desormais **quatre**
elements.

Et il les affiche **en entier**, entre deux lignes `----8<----`, avec la
recette de restauration complete : ce que l'on ne voit pas, on ne le
copie pas. Une premiere version n'affichait que le CHEMIN de la cle
privee — ce qui obligeait a aller chercher le fichier, et la cle restait
sur la machine, la seule qui ne sera plus la le jour ou on en aura
besoin.

**Le NOM du fichier de cle compte**, et rien ne le disait : les scripts
cherchent `bin/.ssh/${BORG_PREFIX}_ed25519`, exactement. Une cle sortie
du coffre sous un autre nom n'est pas vue, ssh se rabat sur la
configuration systeme, et le refus parle de permissions — jamais de nom
de fichier. Le bloc du coffre porte donc le nom exact, et `make restore`
le rappelle quand la cle manque et que le depot est distant (eprouve).

**La restauration annoncait « Terminee » apres n'avoir rien restaure.**
`pg_restore` rend un code non nul pour un avertissement benin comme pour
un echec total — mesure : base injoignable, code 1 ; conteneur absent,
code 1. On ne peut donc rien conclure de son code de retour, et s'en
contenter laissait le script derouler la recopie de `media/` puis
annoncer la fin. Il verifie desormais le RESULTAT : la base
contient-elle des notes, apres coup ? Eprouve postgres arrete — code 1,
diagnostic explicite, base intacte.

*Et un defaut dans le correctif lui-meme, trouve en l'eprouvant : sous
`set -e`, la substitution de commande qui compte les notes tuait le
script sur place quand la base ne repondait pas — le seul cas qu'elle
existe pour attraper. Le code de sortie etait bon, le diagnostic ne
s'affichait jamais.*

**`media/` absent donnait des archives vertes.** `borg create` sur un
chemin inexistant ne rend qu'un **code 1** (mesure, borg 1.4.4), que la
tolerance aux avertissements laissait passer. Un volume non monte, et
des semaines d'archives « fraiches » sans un seul media — decouvert en
restaurant. La sauvegarde refuse maintenant de tourner sans `media/`,
qui est sa raison d'etre.

**`borg prune` ne libere aucune place depuis borg 1.2.** Mesure sur
depot local, 4 archives de 20 Mo aleatoires : 77 Mo avant, **77 Mo
apres un prune qui a pourtant supprime trois archives**, 20 Mo apres
`borg compact`. La retention n'existait que sur le papier ; le quota du
depot se serait rempli jusqu'a ce que la sauvegarde echoue, des mois
plus tard, pour une raison sans rapport apparent. *Le kit d'origine a le
meme defaut.*

**Un chiffre invente.** « `pg_restore -f /dev/null` -> code 3 » etait
ecrit trois fois. Le code mesure est **1**. La mesure d'origine avait
constate « non nul » sans capturer le nombre.

**Le conteneur postgres arrete faisait dire « dump TRONQUE »** a la
verification, sur une archive parfaitement saine — un monitoring
reveillerait quelqu'un pour rien. Elle distingue les deux cas.

**Quatre tests ne prouvaient rien**, demontre par mutation : un secret
en dur entre quotes simples passait au vert (et la forme quotee est
justement celle qu'on ecrit a la main), un secret pose par `export`
aussi, le garde-fou d'idempotence du `.env` pouvait etre supprime sans
qu'un test bouge, et la protection du `.env` courant etait verifiee sur
un message d'affichage au lieu d'un comportement. Tous resserres, et
les onze mutations correspondantes rougissent desormais.

**Divers, corriges** : le seuil de fraicheur ne suivait pas la frequence
a la reprise d'une configuration (cron horaire sous un seuil de 25 h) ;
`restore.sh` ne prenait pas le verrou de la sauvegarde (un cron tombant
pendant une restauration archivait une base a moitie restauree, dans un
dump parfaitement valide — `check_backup.sh`, lui, ne le prend pas non
plus, et c'est voulu : il ne fait que lire, et refuser une verification
pendant une sauvegarde n'aiderait personne) ; `DOMAIN` reste a
`example.com` — la valeur ecrite quand la configuration tourne sans
terminal — passait le bilan de prod ;
`BORG_RELOCATED_REPO_ACCESS_IS_OK` n'etait posee que par la sauvegarde,
si bien qu'apres un demenagement du depot la sauvegarde serait passee et
la verification aurait attendu une confirmation qu'un monitoring ne
donne jamais ; `flock` etait verifie APRES avoir ete utilise ; le mot de
passe passait par `env`, donc par l'argv visible en `ps` ; `BORG_RSH` ne
supportait pas un chemin a espaces ; `DUMP_DIR` restait surchargeable
par une ligne egaree du `.env`.

**Un constat verifie et ecarte** : la relecture signalait l'absence de
`migrate` apres restauration. Le redemarrage du conteneur rejoue
`bin/install.sh`, donc `migrate`, AVANT que supervisord ne serve —
verifie dans les journaux (« [3/6] Migrations... »). Rien ne le disait,
c'est maintenant ecrit.

## 10. Le jeton borgwarehouse

`make backup`, au premier lancement, cree le depot tout seul quand
`borgwarehouse_ccc_api` est exportee (c'est le cas sur les serveurs de
production) ; sinon `BW_API_TOKEN`, sinon la saisie au clavier. Il n'est
stocke nulle part et ne sert qu'a un unique `POST` : un jeton de
permission `create` seule suffit.

La passphrase est tiree en **hexadecimal**, pas en base64 comme dans le
kit d'origine : ce `.env` est aussi lu par docker compose, dont
l'analyseur interprete `$`. Une passphrase base64 en portant un
produirait une valeur differente cote conteneur et cote script.
32 octets hexadecimaux, c'est toujours 256 bits d'entropie.

---

## Comment tester (a la main) / Manual test

### A. Le tout premier `make backup` — sur la machine de production

```bash
make backup
```

Il doit annoncer « Aucune sauvegarde configuree », enchainer sur la
configuration, puis sauvegarder. Il ne reste qu'a repondre a la
frequence : le prefixe vient du nom de la machine, et le depot se cree
tout seul si `borgwarehouse_ccc_api` est exportee.

**Attendu :** une archive nommee `hypostasia-<nom de la machine>-<date>`.

**Attendu :** une cle dans `bin/.ssh/`, un bloc `BORG_*` ajoute au
`.env`, la passphrase et la cle du depot affichees avec une demande de
`OUI`, une ligne de cron, puis une premiere sauvegarde suivie de sa
verification.

**A faire vraiment :** copier passphrase + `borg key export` + adresse
du depot dans un coffre-fort, MAINTENANT. Sans elles les archives sont
illisibles a jamais. Puis, **depuis une autre machine**, verifier qu'un
`borg list` passe avec ces elements-la : `make backup-check` utilise le
`.env` de la machine, pas la copie du coffre.

### B. Sauvegarder et verifier

```bash
make backup
make backup-check ; echo "code : $?"
```

**Attendu :** les trois blocs au vert (fraicheur, contenu, dump deroule)
et un code 0.

### C. Prouver que la verification n'est pas complaisante

Fabriquer une archive portant un dump tronque, puis relancer le check :

```bash
# ... apres un `make backup`, avec les variables du .env chargees
borg list --short "$BORG_REPO" | tail -1     # la derniere archive
```

Une reproduction complete est dans l'historique de ce chantier : dump
extrait, ampute de 100 octets, rearchive avec un horodatage plus recent.
`make backup-check` doit rendre **`dump TRONQUE`** et un code 1. S'il
reste au vert, la verification ne sert a rien.

### D. Restaurer

```bash
make restore              # la derniere archive
make restore ARCHIVE=hypostasia-2026-08-16-03-00-12
bash bin/restore.sh --liste
```

**Attendu :** un encart rappelant que la base sera ecrasee, puis
l'invite `Taper RESTAURER pour continuer`. Taper autre chose doit
annuler sans rien toucher.

Apres coup, compter les lignes avant/apres pour verifier :

```bash
docker compose exec -T postgres psql -U hypostasia -d hypostasia -tAc \
  "select 'pages='||(select count(*) from core_page)
       ||' elements='||(select count(*) from core_elementdocument)
       ||' users='||(select count(*) from auth_user);"
```

Verifier aussi que le `.env` courant n'a PAS bouge, et que celui de
l'archive attend dans `.restauration-<horodatage>/`.

### E. Le bilan de production

```bash
make verif-prod ; echo "code : $?"
```

Sur un poste de dev, il signale l'absence de depot et de cron et sort en
1 — c'est normal, il n'est pas fait pour un poste de dev. Le lancer
plutot sur la machine de production, ou il doit finir par
**`Rien a signaler`** et un code 0.

Verifier au passage que `make install` ne l'a PAS fait echouer sur un
poste de dev : il doit y afficher une seule ligne,
« poste de developpement (DEBUG=true) — verifications de production
sautees ».
