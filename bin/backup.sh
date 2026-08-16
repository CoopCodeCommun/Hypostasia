#!/bin/bash
# =============================================================================
# bin/backup.sh — Sauvegarde Hypostasia vers un depot borg
# / bin/backup.sh — Hypostasia backup to a borg repository
#
# S'EXECUTE DEPUIS L'HOTE, jamais dans le conteneur — a l'inverse de
# bin/install.sh. Il pilote Docker (`docker compose exec`) et sera pose
# dans le crontab de l'hote : un script qui vit dans le conteneur ne
# peut faire ni l'un ni l'autre.
# / Runs from the HOST, unlike bin/install.sh: it drives Docker and sits
# in the host's crontab.
#
# CE QUI PART DANS L'ARCHIVE, ET POURQUOI SEULEMENT CA
#
#   le dump PostgreSQL   la base entiere, au format custom (pg_restore)
#   media/               les PDF, audios et transcriptions — 504 Mo au
#                        16 aout 2026, hors git, et irremplacables
#   .env                 les cles API et les mots de passe
#
# Le reste du depot est dans git : code, docker-compose.yml, nginx/,
# sample/. Le rearchiver chaque nuit n'apporterait rien qu'un `git
# clone` ne rende deja. Une restauration complete se lit donc :
#
#   git clone <depot> && cp <.env restaure> .env && make install
#   make restore
#
# CONFIGURATION : ce script ne contient AUCUN secret. Il lit le `.env`
# de la racine, que git ignore. Un script est fait pour etre versionne
# et partage — une passphrase ecrite dedans finit poussee sur la forge
# au premier `git add -A` distrait.
#
# Le `.env` part donc dans l'archive, passphrase du depot comprise.
# C'est sans consequence : il faut deja connaitre cette passphrase pour
# ouvrir l'archive qui la contient.
#
# USAGE
#   make backup     c'est tout.
#
# UNE SEULE COMMANDE, ET C'EST VOULU
#
# Au premier lancement sur une machine, rien n'est configure : ce script
# enchaine alors sur `bin/init_backup.sh` — cle SSH, depot sur
# borgwarehouse, ecriture du .env, cron — qui se termine par une
# premiere sauvegarde et sa verification. Les fois suivantes, il
# sauvegarde directement.
#
# Il n'y a donc PAS de commande d'initialisation a retenir. Une commande
# qu'on ne tape qu'une fois dans la vie d'une machine est une commande
# qu'on ne retrouve pas le jour ou on en a besoin.
# / One command only: on a fresh machine this script chains into the
# setup, then backs up. A command typed once in a machine's lifetime is
# a command nobody finds again.
#
# Le mot de passe PostgreSQL n'est pas recopie ici : il est lu DANS le
# conteneur, au moment du dump.
# / The PostgreSQL password is read inside the container at dump time.
# =============================================================================
set -euo pipefail

## Surveillance optionnelle via Sentry :
# export SENTRY_DSN=''
# eval "$(sentry-cli bash-hook)"

REPERTOIRE_DU_SCRIPT="$(cd -- "$(dirname -- "$0")" && pwd)"
REPERTOIRE_DU_PROJET="$(dirname "$REPERTOIRE_DU_SCRIPT")"

FICHIER_ENV="${ENV_FILE:-$REPERTOIRE_DU_PROJET/.env}"
FICHIER_COMPOSE="$REPERTOIRE_DU_PROJET/docker-compose.yml"
REPERTOIRE_DES_MEDIAS="$REPERTOIRE_DU_PROJET/media"

[ -f "$FICHIER_ENV" ] || {
    echo "[sauvegarde] .env introuvable : $FICHIER_ENV" >&2
    exit 1
}
# `UID` et `GID` figurent dans le .env (docker compose les lit pour
# aligner l'utilisateur du conteneur sur celui de l'hote), or ce sont
# des variables en LECTURE SEULE de bash. Un `. "$FICHIER_ENV"` brut
# echoue dessus, et avec `set -e` le script s'arretait LA : mesure du
# 16 aout 2026, la sauvegarde sortait en 11 ms sans rien archiver, sur
# une seule ligne d'erreur. On les ecarte a la lecture ; le conteneur,
# lui, continue de les lire dans le fichier.
# / UID and GID are read-only in bash: a plain source aborts the script
# under set -e, which silently produced no backup at all.
set -a
# shellcheck disable=SC1090
. <(grep -vE '^[[:space:]]*(UID|GID)=' "$FICHIER_ENV")
set +a

#### PREMIER LANCEMENT : RIEN N'EST ENCORE CONFIGURE ####
# `make backup` sur une machine neuve doit SAUVEGARDER, pas refuser. Le
# script sait deja que rien n'est configure : c'est a lui d'enchainer
# sur l'initialisation — cle SSH, depot, .env, cron — qui se termine
# justement par une premiere sauvegarde et sa verification.
#
# `exec` remplace ce process au lieu de l'appeler : aucune pile ne
# s'empile, et le .env desormais complet fait que la sauvegarde relancee
# par l'initialisation ne repasse pas par ici.
# / `make backup` on a fresh machine must back up, not refuse. `exec`
# replaces this process, so nothing stacks up, and the now-complete
# .env means the backup it launches will not come back here.
if [ -z "${BORG_PREFIX:-}" ] || [ -z "${BORG_REPO:-}" ] || [ -z "${BORG_PASSPHRASE:-}" ]; then
    echo "[sauvegarde] Aucune sauvegarde configuree sur cette machine."
    if [ ! -t 0 ]; then
        echo "[sauvegarde] La configuration demande un terminal : elle" >&2
        echo "             genere une cle SSH, cree le depot, et te fait" >&2
        echo "             mettre la passphrase au coffre." >&2
        echo "[sauvegarde] La lancer une premiere fois a la main :  make backup" >&2
        exit 1
    fi
    echo "[sauvegarde] Configuration, puis premiere sauvegarde."
    exec bash "$REPERTOIRE_DU_SCRIPT/init_backup.sh"
fi

PREFIXE="$BORG_PREFIX"

# Cle SSH DEDIEE a ce depot. Sur borgwarehouse, une cle publique donne
# acces a UN depot et un seul ; une machine qui sauvegarde deux cibles a
# donc besoin de deux cles. Le nom vient du prefixe, ce qui les fait
# cohabiter sans collision.
# / One SSH key = one repository on borgwarehouse.
CLE_SSH="$REPERTOIRE_DU_SCRIPT/.ssh/${PREFIXE}_ed25519"

# Dossier de travail du dump, supprime apres l'archivage. Ce chemin
# n'est PAS surchargeable : il l'etait par une variable `DUMP_DIR`
# heritee du kit, que personne n'utilisait — et qu'une ligne `DUMP_DIR=`
# egaree dans le .env, lu juste au-dessus, aurait detournee en silence.
# / Not overridable: a stray DUMP_DIR in the sourced .env would have
# silently redirected it.
REPERTOIRE_DU_DUMP="$REPERTOIRE_DU_PROJET/.dump-pg-$PREFIXE"


#### PREPARATION ####
# Le depot peut avoir change d'adresse (serveur BWH renomme, dossier
# deplace, restauration sur une autre machine) : borg demande alors une
# confirmation interactive, qu'un cron ne pourra jamais donner. Les
# trois scripts posent la MEME variable — sans quoi la sauvegarde
# passerait et la verification echouerait, ou l'inverse.
# / Set identically in all three scripts, or backup would pass where
# check fails.
export BORG_RELOCATED_REPO_ACCESS_IS_OK=yes

# Les outils AVANT de s'en servir : `flock` etait verifie apres avoir
# ete utilise, et son absence rendait « une sauvegarde est deja en
# cours » — un message qui envoie chercher un probleme qui n'existe pas.
# / Tools checked before use: flock was checked after being used, and
# its absence read as "a backup is already running".
for outil in borg docker flock; do
    command -v "$outil" >/dev/null || {
        echo "[sauvegarde] $outil introuvable dans le PATH" >&2
        exit 1
    }
done
[ -f "$FICHIER_COMPOSE" ] || {
    echo "[sauvegarde] docker-compose.yml introuvable : $FICHIER_COMPOSE" >&2
    exit 1
}

# Une seule sauvegarde a la fois. Sans ce verrou, un lancement manuel
# qui tombe pendant le cron partage le meme dossier de dump : le premier
# a finir le supprime — trap EXIT — pendant que l'autre archive encore,
# et on obtient une archive SANS DUMP, silencieusement.
# / Without this lock, one run deletes the dump directory while the
# other is still archiving: an archive with no dump, silently.
exec 9>"$REPERTOIRE_DU_PROJET/.backup-$PREFIXE.lock"
flock -n 9 || {
    echo "[sauvegarde] une sauvegarde est deja en cours — abandon." >&2
    exit 1
}

# Les SECONDES comptent dans le nom : borg refuse deux archives
# homonymes, et l'horodatage a la minute — celui du kit d'origine —
# faisait echouer deux `make backup` lances a la suite sur un
# « Archive ... already exists » suivi d'un « code 2 » qui ne dit pas
# pourquoi (constate le 16 aout 2026). Une sauvegarde manuelle juste
# apres une autre est un geste normal ; elle ne doit pas echouer.
# / Seconds matter: borg refuses homonymous archives, and minute
# granularity made two consecutive `make backup` fail.
HORODATAGE=$(date +%Y-%m-%d-%H-%M-%S)

# Force l'usage de CETTE cle, et d'elle seule : sans
# -oIdentitiesOnly=yes, l'agent SSH proposerait d'abord une autre cle et
# borgwarehouse refuserait la connexion.
# / Forces this key only; otherwise the agent offers another one first.
if [ -f "$CLE_SSH" ]; then
    chmod 600 "$CLE_SSH" 2>/dev/null || true
    # Le chemin est entre quotes SIMPLES a l'interieur de la variable :
    # borg decoupe BORG_RSH comme un shell, donc un projet installe sous
    # un chemin a espaces (`/media/Mon Disque/...`) casserait ssh.
    # / borg splits BORG_RSH shell-style; a path with spaces would break.
    export BORG_RSH="/usr/bin/ssh -oStrictHostKeyChecking=accept-new -oIdentitiesOnly=yes -i '$CLE_SSH'"
else
    echo "[sauvegarde] [INFO] aucune cle a $CLE_SSH — SSH utilisera la config systeme." >&2
fi



#### DUMP POSTGRESQL ####
# Nettoyage garanti du dump, meme en cas d'erreur.
trap 'rm -rf "$REPERTOIRE_DU_DUMP"' EXIT
rm -rf "$REPERTOIRE_DU_DUMP"
mkdir -p "$REPERTOIRE_DU_DUMP"
FICHIER_DU_DUMP="$REPERTOIRE_DU_DUMP/hypostasia.dump"

echo "$HORODATAGE dump de la base PostgreSQL (format custom)"
# -Fc : format custom, compresse, restaurable par pg_restore — et
# surtout DEROULABLE, ce dont bin/check_backup.sh se sert pour prouver
# qu'un dump n'est pas tronque.
#
# Les identifiants viennent de l'environnement DU CONTENEUR : ils ne
# transitent pas par ce script, donc pas par le crontab ni par les
# journaux. / Credentials come from the container's own environment.
# `PGPASSWORD=... exec pg_dump` et non `exec env PGPASSWORD=...` : avec
# `env`, le mot de passe apparait dans la ligne de commande du process,
# donc dans un `ps` lance au meme instant. Sous cette forme, il n'est
# qu'une variable d'environnement du process, invisible a `ps`.
# / With `env`, the password shows in the process's argv.
docker compose -f "$FICHIER_COMPOSE" exec -T postgres \
    sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" \
        exec pg_dump -Fc -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
    > "$FICHIER_DU_DUMP"

# Garde-fou : un dump vide s'archive proprement et ne restaure rien.
# / An empty dump archives cleanly and restores nothing.
if [ ! -s "$FICHIER_DU_DUMP" ]; then
    echo "[sauvegarde] dump vide ($FICHIER_DU_DUMP) — abandon" >&2
    exit 1
fi
echo "$HORODATAGE dump : $(du -h "$FICHIER_DU_DUMP" | cut -f1)"

# media/ est la RAISON D'ETRE de cette sauvegarde : la base se
# reconstruit, les PDF et les audios non. Sans ce garde-fou, un dossier
# renomme ou un volume non monte donne une archive que borg cree quand
# meme — `borg create` sur un chemin absent rend un code 1, que la
# tolerance ci-dessous laisse passer (mesure du 16 aout 2026, borg
# 1.4.4). Des semaines d'archives « fraiches » sans un seul media, et
# on ne l'apprend qu'en restaurant.
# / media/ is why this backup exists. borg create on a missing path
# returns 1, which the tolerance below would swallow.
if [ ! -d "$REPERTOIRE_DES_MEDIAS" ]; then
    echo "[sauvegarde] media/ introuvable : $REPERTOIRE_DES_MEDIAS" >&2
    echo "[sauvegarde] Volume non monte ? Dossier renomme ? On n'archive PAS" >&2
    echo "             une sauvegarde amputee de ce qu'elle sert a proteger." >&2
    exit 1
fi


#### CREATION DE L'ARCHIVE ####
# Codes de sortie borg : 0 succes, 1 avertissement (un fichier a bouge
# pendant la lecture), 2 et plus vraie erreur. Avec `set -e`, un simple
# avertissement tuerait le script — or media/ change pendant qu'on
# l'archive des qu'un import tourne. On tolere 1, on echoue des 2. Le
# dump, lui, reste strict : il est deja verifie plus haut.
# / borg exit code 1 is a warning; media/ moves while being archived.
borg_tolerant() {
    local code=0
    "$@" || code=$?
    if [ "$code" -ge 2 ]; then
        echo "[sauvegarde] ERREUR : borg a echoue (code $code)" >&2
        exit "$code"
    fi
    [ "$code" -eq 1 ] && echo "[sauvegarde] (avertissement borg ignore, code 1)" >&2
    return 0
}

echo "$HORODATAGE creation de l'archive : dump + media/ + .env"
borg_tolerant borg create -vs --compression lz4 \
    "$BORG_REPO::$PREFIXE-$HORODATAGE" \
    "$REPERTOIRE_DU_DUMP" \
    "$REPERTOIRE_DES_MEDIAS" \
    "$FICHIER_ENV"

echo "$HORODATAGE rotation des anciennes archives :"
# --glob-archives : la rotation ne touche QUE les archives de cette
# stack. Si deux sauvegardes partagent un depot, sans ce filtre elles se
# rognent mutuellement leur retention, en silence.
# / The prune only touches this stack's archives.
borg_tolerant borg prune -v --list \
    --glob-archives "$PREFIXE-*" \
    --keep-within=7d --keep-daily=30 --keep-weekly=12 \
    --keep-monthly=-1 --keep-yearly=-1 \
    "$BORG_REPO"

# `prune` DELIE les archives, il ne rend pas la place : depuis borg 1.2,
# c'est `compact` qui la libere, et lui seul. Mesure du 16 aout 2026,
# borg 1.4.4, depot local, 4 archives de 20 Mo aleatoires :
#
#     avant prune  : 77 Mo
#     apres prune  : 77 Mo   (3 archives pourtant supprimees)
#     apres compact: 20 Mo
#
# Sans cette ligne, la retention n'existe que sur le papier : le quota
# du depot se remplit jusqu'a ce que `borg create` echoue, des mois plus
# tard, pour une raison qui n'aura plus rien a voir avec ce jour-la.
# Le kit d'origine ne l'appelle pas non plus.
# / `prune` unlinks archives; since borg 1.2 only `compact` frees the
# space. Measured: 77 MB before, 77 MB after prune, 20 MB after compact.
echo "$HORODATAGE liberation de la place :"
borg_tolerant borg compact "$BORG_REPO"

echo "$HORODATAGE termine. Verifier qu'elle est restaurable : make backup-check"
