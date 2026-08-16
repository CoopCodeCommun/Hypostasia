#!/bin/bash
# =============================================================================
# bin/verifier_prod.sh — Ce qui manque a cette machine pour tenir en prod
# / bin/verifier_prod.sh — What this machine still lacks for production
#
# S'EXECUTE DEPUIS L'HOTE.   Lance par :  make verif-prod
# Appele aussi par `make install`, avec `--a-l-installation`.
#
# CE QU'IL REGARDE
#
#   Configuration   secrets d'exemple encore en place, DEBUG et
#                   NGINX_CONF coherents, DOMAIN renseigne
#   Sauvegarde      depot borg configure ET joignable, age de la
#                   derniere archive, ligne de cron posee
#
# POURQUOI CES CONTROLES-LA
#
# Aucun des trois defauts qu'il cherche ne se signale tout seul :
#   - une prod tournant avec la SECRET_KEY du fichier d'exemple
#     fonctionne parfaitement, jusqu'au jour ou quelqu'un forge une
#     session ;
#   - `DEBUG=true` avec la conf nginx de prod envoie `/` vers le port
#     8001, ou personne n'ecoute : 502 sur tout le site ;
#   - un cron absent, c'est une sauvegarde qui n'existe pas, et rien ne
#     le dit avant le jour ou on en a besoin.
# / None of these announces itself; each shows up at the worst moment.
#
# DEUX COMPORTEMENTS
#
#   make verif-prod              controle TOUT, sort en code non nul au
#                                moindre probleme (utilisable en
#                                monitoring)
#   --a-l-installation           saute tout sur un poste de dev
#                                (DEBUG=true) : la sauvegarde borg n'y a
#                                pas de sens. Sur une machine de prod, il
#                                affiche le bilan sans jamais faire
#                                echouer l'installation — le depot se
#                                cree DEPUIS la machine installee, exiger
#                                qu'il existe deja tiendrait de l'oeuf et
#                                de la poule.
# / Standalone: checks everything, non-zero on any problem. At install
# time: skipped on a dev box, advisory on production.
# =============================================================================
set -uo pipefail

REPERTOIRE_DU_SCRIPT="$(cd -- "$(dirname -- "$0")" && pwd)"
REPERTOIRE_DU_PROJET="$(dirname "$REPERTOIRE_DU_SCRIPT")"
FICHIER_ENV="${ENV_FILE:-$REPERTOIRE_DU_PROJET/.env}"
SCRIPT_DE_SAUVEGARDE="$REPERTOIRE_DU_SCRIPT/backup.sh"

A_L_INSTALLATION=0
[ "${1:-}" = "--a-l-installation" ] && A_L_INSTALLATION=1

NOMBRE_D_ERREURS=0
ok()   { echo "  [ok]   $*"; }
ko()   { echo "  [KO]   $*"; NOMBRE_D_ERREURS=$((NOMBRE_D_ERREURS + 1)); }
note() { echo "  [--]   $*"; }

if [ ! -f "$FICHIER_ENV" ]; then
    echo "[prod] .env introuvable : $FICHIER_ENV" >&2
    exit 1
fi
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

# Sur un poste de dev, ces controles n'ont pas de sens : ni depot borg,
# ni cron, ni secrets de production. / On a dev box these checks are
# meaningless.
EN_DEV=0
case "${DEBUG:-}" in
    true|True|TRUE|1|yes) EN_DEV=1 ;;
esac
if [ "$A_L_INSTALLATION" = 1 ] && [ "$EN_DEV" = 1 ]; then
    echo "[prod] poste de developpement (DEBUG=true) — verifications de production sautees."
    exit 0
fi

echo
echo "[prod] Bilan de production — $REPERTOIRE_DU_PROJET"
echo


#### 1. CONFIGURATION ####
echo "1. Configuration"

# Les valeurs du fichier d'exemple, restees telles quelles.
# / The example file's values, left as they are.
MOTIF_D_EXEMPLE="CHANGEZ_MOI"
for variable in SECRET_KEY POSTGRES_PASSWORD; do
    valeur="${!variable:-}"
    if [ -z "$valeur" ]; then
        ko "$variable est vide dans le .env."
    elif case "$valeur" in *"$MOTIF_D_EXEMPLE"*) true ;; *) false ;; esac; then
        ko "$variable porte encore la valeur du fichier d'exemple."
    else
        ok "$variable renseignee."
    fi
done

# `example.com` n'est pas qu'un detail de forme : c'est la valeur que
# `bin/configurer_env.sh` ecrit quand il tourne SANS TERMINAL, faute de
# pouvoir poser la question. Une prod installee par un script part donc
# avec ce domaine-la, traefik route un hote qui n'existe pas, et le
# bilan dirait « rien a signaler » s'il se contentait du non-vide.
# / It is the value written when the config script runs with no
# terminal: a scripted production install starts with a fake domain.
case "${DOMAIN:-}" in
    "")
        ko "DOMAIN est vide : traefik ne peut router aucun hote."
        ;;
    *example.com|*example.org|*exemple.fr)
        ko "DOMAIN vaut $DOMAIN — le domaine d'exemple. Traefik route un hote qui n'existe pas."
        ;;
    *)
        ok "DOMAIN : $DOMAIN"
        ;;
esac

# DEBUG et NGINX_CONF vont ENSEMBLE. En dev, runserver sert le HTTP et
# le WebSocket sur 8000 ; en prod, gunicorn tient le 8001 et daphne le
# 8000. Croiser les deux reglages donne un site entierement en 502.
# / DEBUG and NGINX_CONF must move together, or the whole site 502s.
CONF_NGINX="${NGINX_CONF:-default.conf}"
if [ "$EN_DEV" = 1 ] && [ "$CONF_NGINX" != "dev.conf" ]; then
    ko "DEBUG=true avec NGINX_CONF=$CONF_NGINX : nginx enverrait / vers le port 8001, ou personne n'ecoute (502 sur tout le site)."
elif [ "$EN_DEV" = 0 ] && [ "$CONF_NGINX" = "dev.conf" ]; then
    ko "DEBUG=false avec NGINX_CONF=dev.conf : gunicorn tourne sur 8001 mais ne recevrait aucun trafic."
else
    ok "DEBUG et NGINX_CONF coherents (DEBUG=${DEBUG:-non defini}, $CONF_NGINX)."
fi

if [ "$EN_DEV" = 1 ]; then
    note "DEBUG=true : cette machine n'est PAS une machine de production."
fi


#### 2. SAUVEGARDE ####
echo
echo "2. Sauvegarde"

if ! command -v borg >/dev/null; then
    ko "borg n'est pas installe sur cette machine (apt install borgbackup)."
elif [ -z "${BORG_REPO:-}" ] || [ -z "${BORG_PASSPHRASE:-}" ] || [ -z "${BORG_PREFIX:-}" ]; then
    ko "aucun depot configure dans le .env. Le configurer :  make backup"
else
    ok "depot declare : $BORG_REPO"

    CLE_SSH="$REPERTOIRE_DU_SCRIPT/.ssh/${BORG_PREFIX}_ed25519"
    if [ -f "$CLE_SSH" ]; then
        ok "cle SSH dediee presente."
        export BORG_RSH="/usr/bin/ssh -oStrictHostKeyChecking=accept-new -oIdentitiesOnly=yes -i $CLE_SSH"
    else
        note "aucune cle dediee a $CLE_SSH — SSH utilisera la config systeme."
    fi

    # Joignable ? C'est la seule preuve qui compte : un depot declare
    # dans un .env et injoignable ne sauvegarde rien.
    # / Reachable? A declared but unreachable repository backs up nothing.
    DERNIERE="$(borg list --glob-archives "$BORG_PREFIX-*" --last 1 \
        --format '{archive}{TAB}{time:%Y-%m-%d %H:%M:%S}{NL}' "$BORG_REPO" 2>/dev/null || true)"
    if [ -z "$DERNIERE" ]; then
        if borg list "$BORG_REPO" >/dev/null 2>&1; then
            ko "depot joignable mais AUCUNE archive '$BORG_PREFIX-*' : la sauvegarde n'a jamais tourne (make backup)."
        else
            ko "depot INJOIGNABLE : ni la cle SSH, ni la passphrase, ni l'adresse ne repondent."
        fi
    else
        ARCHIVE="${DERNIERE%%	*}"
        DATE_DE_L_ARCHIVE="${DERNIERE#*	}"
        AGE_EN_HEURES=$(( ( $(date +%s) - $(date -d "$DATE_DE_L_ARCHIVE" +%s) ) / 3600 ))
        SEUIL="${AGE_MAX_HEURES:-25}"
        if [ "$AGE_EN_HEURES" -le "$SEUIL" ]; then
            ok "derniere archive : $ARCHIVE (il y a ${AGE_EN_HEURES} h)"
        else
            ko "derniere archive vieille de ${AGE_EN_HEURES} h (seuil : ${SEUIL} h) — le cron ne tourne plus."
        fi
        note "restaurabilite reelle : make backup-check (deroule le dump)"
    fi
fi

# Le cron vit sur l'HOTE, pas dans le conteneur : c'est pour cela que ce
# script tourne sur l'hote. / The cron lives on the host.
CRON_ACTUEL="$(crontab -l 2>/dev/null || true)"
if grep -Fq "$SCRIPT_DE_SAUVEGARDE" <<< "$CRON_ACTUEL"; then
    ok "cron pose : $(grep -F "$SCRIPT_DE_SAUVEGARDE" <<< "$CRON_ACTUEL" | head -n1)"
else
    ko "aucune ligne de cron pour $SCRIPT_DE_SAUVEGARDE : la sauvegarde ne tourne pas toute seule (make backup)."
fi


#### VERDICT ####
echo
if [ "$NOMBRE_D_ERREURS" -eq 0 ]; then
    echo "[prod] Rien a signaler."
    exit 0
fi

echo "[prod] $NOMBRE_D_ERREURS point(s) a regler avant de considerer cette machine comme une prod."
if [ "$A_L_INSTALLATION" = 1 ]; then
    # A l'installation, on informe : on n'arrete pas. Le depot borg se
    # cree DEPUIS la machine installee. / At install time we inform.
    echo "[prod] (l'installation continue : ce bilan n'est qu'un avertissement)"
    exit 0
fi
exit 1
