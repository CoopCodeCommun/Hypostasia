#!/bin/bash
# =============================================================================
# bin/restore.sh — Restaure Hypostasia depuis une archive borg
# / bin/restore.sh — Restores Hypostasia from a borg archive
#
# S'EXECUTE DEPUIS L'HOTE.   Lance par :  make restore [ARCHIVE=<nom>]
#
# CETTE COMMANDE ECRASE LA BASE EN SERVICE. Elle demande donc une
# confirmation tapee au clavier, et refuse de tourner sans. C'est la
# seule commande destructrice du projet : tout le reste est idempotent.
# / This overwrites the live database and asks for typed confirmation.
#
# CE QU'ELLE FAIT, DANS L'ORDRE
#
#   1. choisit l'archive (la derniere par defaut) et la fait confirmer
#   2. ARRETE le conteneur web — Django et Celery tiennent des
#      connexions ouvertes, et `pg_restore --clean` resterait bloque a
#      attendre leurs verrous au lieu de supprimer les tables
#   3. restaure la base (--clean : on repart de l'etat de l'archive)
#   4. recopie media/ par-dessus l'existant
#   5. depose le .env de l'archive A COTE, sans jamais l'installer
#   6. redemarre le conteneur web
#
# LES MIGRATIONS SE REJOUENT TOUTES SEULES. `--clean` ramene aussi la
# table `django_migrations` a l'etat de l'archive : un code plus recent
# que l'archive — le cas normal d'un sinistre, `git clone` du HEAD plus
# une archive d'il y a trois jours — se retrouverait sur un schema en
# retard. Mais le redemarrage du conteneur rejoue `bin/start-dev.sh`,
# donc `bin/install.sh`, donc `migrate`, AVANT que supervisord ne serve
# quoi que ce soit (verifie le 16 aout 2026 : « [3/6] Migrations... »
# dans les journaux apres un `docker compose start web`).
# / Migrations replay by themselves: restarting the container re-runs
# install.sh, hence migrate, before supervisord serves anything.
#
# LE .env COURANT N'EST JAMAIS ECRASE, et c'est delibere : il porte
# BORG_PASSPHRASE, la passphrase du depot EN SERVICE. Celui d'une vieille
# archive peut en porter une autre — l'installer rendrait le depot
# inaccessible, et on ne s'en apercevrait qu'a la restauration suivante.
# / The live .env is never overwritten: it holds the passphrase of the
# repository in service.
#
# RESTAURATION COMPLETE, SUR UNE MACHINE NEUVE
#
#   git clone <depot> && cd Hypostasia
#   cp <le .env sorti du coffre> .env
#   make install                # la stack, vide
#   make restore                # les donnees
# =============================================================================
set -euo pipefail

REPERTOIRE_DU_SCRIPT="$(cd -- "$(dirname -- "$0")" && pwd)"
REPERTOIRE_DU_PROJET="$(dirname "$REPERTOIRE_DU_SCRIPT")"

FICHIER_ENV="${ENV_FILE:-$REPERTOIRE_DU_PROJET/.env}"
FICHIER_COMPOSE="$REPERTOIRE_DU_PROJET/docker-compose.yml"
REPERTOIRE_DES_MEDIAS="$REPERTOIRE_DU_PROJET/media"

[ -f "$FICHIER_ENV" ] || {
    echo "[restauration] .env introuvable : $FICHIER_ENV" >&2
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

: "${BORG_PREFIX:?BORG_PREFIX absent du .env — aucune sauvegarde configuree}"
: "${BORG_REPO:?BORG_REPO absent du .env — aucune sauvegarde configuree}"
: "${BORG_PASSPHRASE:?BORG_PASSPHRASE absent du .env}"
command -v borg   >/dev/null || { echo "[restauration] borg introuvable" >&2; exit 1; }
command -v docker >/dev/null || { echo "[restauration] docker introuvable" >&2; exit 1; }

CLE_SSH="$REPERTOIRE_DU_SCRIPT/.ssh/${BORG_PREFIX}_ed25519"
if [ -f "$CLE_SSH" ]; then
    # Chemin entre quotes simples : borg decoupe BORG_RSH comme un shell.
    # / Single-quoted path: borg splits BORG_RSH shell-style.
    export BORG_RSH="/usr/bin/ssh -oStrictHostKeyChecking=accept-new -oIdentitiesOnly=yes -i '$CLE_SSH'"
elif [ "${BORG_REPO#ssh://}" != "$BORG_REPO" ]; then
    # LE CAS DE LA MACHINE DE SECOURS. Sans ce message, borg echoue sur
    # un refus SSH qui parle de permissions et jamais de nom de fichier
    # — or c'est presque toujours le nom qui cloche : les scripts
    # cherchent EXACTEMENT `${BORG_PREFIX}_ed25519`, et une cle sortie
    # du coffre sous un autre nom n'est tout simplement pas vue.
    # / The recovery-machine case: borg's refusal talks about
    # permissions and never about the file name, which is almost always
    # what is actually wrong.
    echo "[restauration] Aucune cle SSH a $CLE_SSH." >&2
    echo "               Le depot est distant : sans elle, borgwarehouse" >&2
    echo "               refusera la connexion." >&2
    echo "               Sortir la cle privee du coffre et la reposer SOUS" >&2
    echo "               CE NOM EXACT, dans bin/.ssh/ :" >&2
    echo "                 ${BORG_PREFIX}_ed25519      (chmod 600)" >&2
    echo "               Un autre nom ne serait pas vu, et le refus SSH ne" >&2
    echo "               le dirait pas." >&2
    echo >&2
fi

# Une restauration se fait souvent sur une AUTRE machine, ou le depot
# n'est plus au meme chemin : borg demande alors une confirmation. Meme
# reglage que dans bin/backup.sh, sans quoi la sauvegarde passerait la
# ou la restauration s'arreterait.
# / Same setting as backup.sh: a restore often happens elsewhere.
export BORG_RELOCATED_REPO_ACCESS_IS_OK=yes


#### CHOIX DE L'ARCHIVE ####
if [ "${1:-}" = "--liste" ]; then
    borg list --glob-archives "$BORG_PREFIX-*" \
        --format '{archive}{TAB}{time:%Y-%m-%d %H:%M}{NL}' "$BORG_REPO"
    exit 0
fi

ARCHIVE="${1:-}"
if [ -z "$ARCHIVE" ]; then
    ARCHIVE="$(borg list --glob-archives "$BORG_PREFIX-*" --last 1 \
        --format '{archive}{NL}' "$BORG_REPO")"
    [ -n "$ARCHIVE" ] || {
        echo "[restauration] aucune archive '$BORG_PREFIX-*' dans le depot." >&2
        exit 1
    }
fi

echo
echo "================================================================"
echo " RESTAURATION — cette operation ECRASE la base en service."
echo
echo " Archive  : $ARCHIVE"
echo " Depot    : $BORG_REPO"
echo " Base     : $POSTGRES_DB"
echo " Medias   : $REPERTOIRE_DES_MEDIAS"
echo
echo " Toute donnee saisie depuis cette archive sera perdue."
echo " Le .env courant est PROTEGE : celui de l'archive sera depose a"
echo " cote, jamais installe (il porte la passphrase du depot)."
echo "================================================================"
echo
echo " Choisir une autre archive :  make restore ARCHIVE=<nom>"
echo " Les lister :                 bash bin/restore.sh --liste"
echo
[ -t 0 ] || {
    echo "[restauration] entree non interactive : la confirmation est impossible." >&2
    exit 1
}
read -r -p "Taper RESTAURER pour continuer : " CONFIRMATION
[ "$CONFIRMATION" = "RESTAURER" ] || {
    echo "[restauration] annule."
    exit 1
}


#### LE MEME VERROU QUE LA SAUVEGARDE ####
# Le cron ne sait pas qu'une restauration est en cours. S'il tombe au
# milieu, il archive une base a moitie restauree — un dump parfaitement
# valide, que `make backup-check` declarera restaurable, et qui ne
# porte qu'une moitie des donnees. Le verrou existe deja cote
# sauvegarde ; l'etendre ici ne coute rien.
# / The cron does not know a restore is running: it would archive a
# half-restored database into a perfectly valid-looking dump.
exec 9>"$REPERTOIRE_DU_PROJET/.backup-$BORG_PREFIX.lock"
flock -n 9 || {
    echo "[restauration] une sauvegarde est en cours — reessayer apres." >&2
    exit 1
}


#### EXTRACTION ####
# Le dossier d'extraction est dans le projet : media/ y est donc sur le
# MEME systeme de fichiers, et la recopie ne traverse pas de montage.
# Il faut transitoirement la place de media/ (504 Mo au 16 aout 2026).
# / Same filesystem as media/, so the copy stays local; it transiently
# needs media/'s size in free space.
DOSSIER_DE_RESTAURATION="$REPERTOIRE_DU_PROJET/.restauration-$(date +%Y-%m-%d-%H-%M)"
mkdir -p "$DOSSIER_DE_RESTAURATION"

echo
echo "[restauration] extraction de l'archive..."
(
    cd "$DOSSIER_DE_RESTAURATION"
    # borg restitue les chemins absolus prives de leur `/` initial :
    # l'archive se deplie donc dans une arborescence miniature ici.
    # / borg strips the leading slash: the archive unfolds locally.
    borg extract "$BORG_REPO::$ARCHIVE"
)

# Les trois contenus sont CHERCHES, pas reconstruits. Reconstruire
# revient a supposer que la machine qui restaure porte le projet au MEME
# chemin que celle qui a sauvegarde — l'hypothese qui tombe precisement
# le jour d'un vrai sinistre, quand on remonte sur une autre machine,
# souvent sous un autre chemin. On ne s'en apercevrait qu'a ce
# moment-la : le dump se restaurerait, et media/ serait declare absent.
# / Searched, not rebuilt: rebuilding assumes the restoring machine
# holds the project at the same path, which is exactly what fails on
# the day of a real disaster.
DUMP_EXTRAIT="$(find "$DOSSIER_DE_RESTAURATION" -type f -name 'hypostasia.dump' -print -quit)"
MEDIAS_EXTRAITS="$(find "$DOSSIER_DE_RESTAURATION" -type d -name 'media' -print -quit)"
ENV_DE_L_ARCHIVE="$(find "$DOSSIER_DE_RESTAURATION" -type f -name '.env' -print -quit)"

[ -n "$DUMP_EXTRAIT" ] || {
    echo "[restauration] aucun dump dans cette archive — abandon." >&2
    exit 1
}


#### ARRET DU WEB, LE TEMPS DE LA RESTAURATION ####
# Django et Celery tiennent des connexions ouvertes sur la base :
# `pg_restore --clean` attendrait leurs verrous indefiniment.
# / Django and Celery hold connections; --clean would wait on locks.
echo "[restauration] arret du conteneur web..."
docker compose -f "$FICHIER_COMPOSE" stop web
# Quoi qu'il arrive ensuite, le web repart : une restauration ratee ne
# doit pas laisser le site eteint.
# / Whatever happens, the web comes back up.
trap 'echo "[restauration] redemarrage du conteneur web..."; docker compose -f "$FICHIER_COMPOSE" start web' EXIT


#### RESTAURATION DE LA BASE ####
echo "[restauration] restauration de la base $POSTGRES_DB..."
# --clean --if-exists : on supprime avant de recreer, sans crier sur ce
# qui n'existe pas encore (base neuve). Sans --clean, la restauration
# s'empile sur les donnees en place et echoue sur chaque contrainte
# d'unicite : base a moitie ancienne, a moitie restauree.
# --no-owner : le proprietaire est celui de la base d'arrivee, meme si
# l'archive vient d'une autre installation.
#
# pg_restore rend un code non nul aussi bien pour un avertissement
# benin que pour un echec TOTAL — mesure du 16 aout 2026 : base
# injoignable, code 1 ; conteneur absent, code 1 ; ce sont les memes
# codes qu'un avertissement. On ne peut donc RIEN conclure de son code
# de retour, et s'en contenter laissait le script annoncer « Terminee »
# apres n'avoir rien restaure du tout.
#
# On verifie donc le RESULTAT, pas le code : la base contient-elle,
# apres coup, ce qu'elle doit contenir ? C'est la seule question dont la
# reponse ne ment pas.
# / pg_restore returns 1 for a benign warning and for a total failure
# alike. We check the outcome, not the code.
docker compose -f "$FICHIER_COMPOSE" exec -T postgres \
    sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" \
        exec pg_restore --clean --if-exists --no-owner \
        -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
    < "$DUMP_EXTRAIT" 2>&1 | tail -5 || true

# `|| true` : sous `set -e`, une substitution de commande qui echoue
# dans une affectation tue le script SUR PLACE. C'est exactement ce qui
# arrivait quand la base ne repondait pas — le seul cas que ce controle
# existe pour attraper : le script sortait bien en 1, mais sans jamais
# afficher le diagnostic ci-dessous (constate le 16 aout 2026, postgres
# arrete). Un code de sortie sans explication renvoie chercher la panne
# a l'aveugle.
# / Under set -e, a failing command substitution kills the script on the
# spot — precisely in the case this check exists to catch.
NOMBRE_DE_PAGES="$(docker compose -f "$FICHIER_COMPOSE" exec -T postgres \
    sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" \
        exec psql -tAq -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
        -c "select count(*) from core_page"' 2>/dev/null | tr -d '[:space:]' || true)"

case "$NOMBRE_DE_PAGES" in
    ''|*[!0-9]*)
        echo >&2
        echo "[restauration] ECHEC : la base ne repond pas apres la restauration." >&2
        echo "               La table core_page est introuvable — rien n'a ete" >&2
        echo "               restaure. Causes habituelles : conteneur postgres" >&2
        echo "               arrete, mot de passe change depuis l'archive, dump" >&2
        echo "               illisible (le verifier : make backup-check)." >&2
        echo "               La base est PROBABLEMENT VIDE : ne pas remettre le" >&2
        echo "               site en service avant d'avoir refait une" >&2
        echo "               restauration qui aboutit." >&2
        exit 1
        ;;
esac
echo "[restauration] base restauree — $NOMBRE_DE_PAGES notes."


#### RESTAURATION DES MEDIAS ####
if [ -n "$MEDIAS_EXTRAITS" ] && [ -d "$MEDIAS_EXTRAITS" ]; then
    echo "[restauration] recopie de media/..."
    mkdir -p "$REPERTOIRE_DES_MEDIAS"
    # Recopie PAR-DESSUS, sans supprimer : un fichier arrive depuis
    # l'archive reste en place. Ses lignes en base, elles, ont disparu
    # avec le --clean ; il devient un orphelin inerte, ce qui est
    # preferable a une suppression definitive faite par un script.
    # / Copy over without deleting: a file added since the archive stays
    # as an inert orphan rather than being destroyed by a script.
    cp -a "$MEDIAS_EXTRAITS/." "$REPERTOIRE_DES_MEDIAS/"
    rm -rf "$MEDIAS_EXTRAITS"
    echo "[restauration] media/ restaure."
else
    echo "[restauration] [INFO] aucun media/ dans cette archive." >&2
fi


#### LE .env DE L'ARCHIVE : DEPOSE, JAMAIS INSTALLE ####
rm -f "$DUMP_EXTRAIT"
echo
if [ -n "$ENV_DE_L_ARCHIVE" ] && [ -f "$ENV_DE_L_ARCHIVE" ]; then
    echo "[restauration] Le .env de l'archive est ici, a comparer a la main :"
    echo "               $ENV_DE_L_ARCHIVE"
    echo "               Le .env courant n'a PAS ete touche (il porte la"
    echo "               passphrase du depot en service)."
else
    echo "[restauration] [INFO] aucun .env dans cette archive." >&2
fi
echo "[restauration] Dossier de travail a supprimer quand tu as fini :"
echo "               rm -rf $DOSSIER_DE_RESTAURATION"
echo
echo "[restauration] Terminee depuis l'archive $ARCHIVE."
echo "[restauration] Le redemarrage du conteneur rejoue les migrations :"
echo "               le schema sera remis a niveau avant que le site ne serve."
