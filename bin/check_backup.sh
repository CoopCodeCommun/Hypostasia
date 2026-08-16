#!/bin/bash
# =============================================================================
# bin/check_backup.sh — La derniere sauvegarde est-elle RESTAURABLE ?
# / bin/check_backup.sh — Is the last backup actually restorable?
#
# S'EXECUTE DEPUIS L'HOTE.   Lance par :  make backup-check
#
# Verifier qu'une archive EXISTE ne dit rien. Ce script repond a la
# seule question qui compte — « est-ce restaurable ? » — sans rien
# restaurer, et sort en code non nul des que quelque chose cloche : il
# est utilisable tel quel dans un monitoring.
# / Checking that an archive exists says nothing. This answers "is it
# restorable?" without restoring, and exits non-zero on any problem.
#
# TROIS QUESTIONS, DANS L'ORDRE
#
#   1. Fraicheur — la derniere archive date de moins de AGE_MAX_HEURES.
#      Sinon le cron est mort, et personne ne l'avait remarque.
#   2. Contenu — le dump, media/ et le .env sont bien dedans.
#   3. Exploitabilite — et c'est la que ca se joue.
#
# POURQUOI LE DUMP EST DEROULE ENTIEREMENT
#
# Un dump tronque — disque plein, conteneur tue en plein dump — a une
# taille credible, se trouve bien dans l'archive, et ne se restaure pas.
# `pg_restore -l` ne le voit PAS : mesure du 16 aout 2026 sur ce projet,
# PostgreSQL 17.10, dump de 417 Ko ampute de 100 octets seulement :
#
#     pg_restore -l              -> code 0   (au VERT)
#     pg_restore -f /dev/null    -> code 1   (« could not read from
#                                   input file: end of file »)
#
# Le meme resultat a 5 Ko et 50 Ko de perte. Seul un DEROULEMENT
# integral demasque la coupure ; la liste de la table des matieres, non.
# / Measured: a dump missing its last 100 bytes passes `pg_restore -l`
# and fails `pg_restore -f /dev/null`. Only a full unroll catches it.
#
# Rien n'est ecrit dans la base : `-f /dev/null` demande a pg_restore de
# produire le SQL, pas de l'appliquer. / Nothing is written to the
# database: -f /dev/null asks for SQL output, not execution.
#
# CE QU'IL NE TESTE PAS : ta copie de coffre-fort. Il utilise le .env de
# la machine, pas la passphrase que tu as archivee ailleurs — or c'est
# celle-la, et elle seule, qui servira le jour ou la machine aura brule.
# Verifie une fois, depuis une AUTRE machine, qu'un `borg list` passe
# avec les elements du coffre.
# =============================================================================
set -euo pipefail

REPERTOIRE_DU_SCRIPT="$(cd -- "$(dirname -- "$0")" && pwd)"
REPERTOIRE_DU_PROJET="$(dirname "$REPERTOIRE_DU_SCRIPT")"

FICHIER_ENV="${ENV_FILE:-$REPERTOIRE_DU_PROJET/.env}"
FICHIER_COMPOSE="$REPERTOIRE_DU_PROJET/docker-compose.yml"

# Age maximum tolere pour la derniere archive. 25 h = la sauvegarde
# quotidienne d'hier, plus une heure de marge. C'est aussi le reglage de
# l'alerte posee sur borgwarehouse par make backup : les deux
# doivent rester coherents. / 25 h = yesterday's daily backup plus one
# hour; it is also the alert threshold set on borgwarehouse.
AGE_MAX_HEURES="${AGE_MAX_HEURES:-25}"

NOMBRE_D_ERREURS=0
ok()     { echo "  [ok]   $*"; }
ko()     { echo "  [KO]   $*" >&2; NOMBRE_D_ERREURS=$((NOMBRE_D_ERREURS + 1)); }
fatal()  { echo "[verification] ERREUR : $*" >&2; exit 2; }

[ -f "$FICHIER_ENV" ] || fatal ".env introuvable : $FICHIER_ENV"
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

: "${BORG_PREFIX:?BORG_PREFIX absent du .env — sauvegarde non configuree, voir : make backup}"
: "${BORG_REPO:?BORG_REPO absent du .env — sauvegarde non configuree, voir : make backup}"
: "${BORG_PASSPHRASE:?BORG_PASSPHRASE absent du .env}"
command -v borg   >/dev/null || fatal "borg introuvable dans le PATH."
command -v docker >/dev/null || fatal "docker introuvable dans le PATH."

CLE_SSH="$REPERTOIRE_DU_SCRIPT/.ssh/${BORG_PREFIX}_ed25519"
# Chemin entre quotes simples : borg decoupe BORG_RSH comme un shell.
# / Single-quoted path: borg splits BORG_RSH shell-style.
[ -f "$CLE_SSH" ] && export BORG_RSH="/usr/bin/ssh -oStrictHostKeyChecking=accept-new -oIdentitiesOnly=yes -i '$CLE_SSH'"

# Meme reglage que bin/backup.sh et bin/restore.sh. Sans lui, une
# verification lancee apres un demenagement du depot attendrait une
# confirmation interactive qu'un monitoring ne donnera jamais — et la
# sauvegarde, elle, serait passee : on aurait une alerte sur une
# sauvegarde saine.
# / Same setting as the other two: otherwise the check would hang on a
# prompt where the backup passed, alerting on a healthy backup.
export BORG_RELOCATED_REPO_ACCESS_IS_OK=yes

echo "[verification] depot : $BORG_REPO"
echo


#### 1. UNE ARCHIVE RECENTE EXISTE-T-ELLE ? ####
echo "1. Fraicheur"

# --glob-archives : on ne regarde QUE les archives de cette stack. Sans
# ce filtre, l'archive fraiche d'une AUTRE sauvegarde partageant le
# depot suffirait a nous rassurer.
# / Without this filter, another stack's fresh archive would reassure us.
DERNIERE="$(borg list --glob-archives "$BORG_PREFIX-*" --last 1 \
    --format '{archive}{TAB}{time:%Y-%m-%d %H:%M:%S}{NL}' "$BORG_REPO")"
[ -n "$DERNIERE" ] || fatal "aucune archive '$BORG_PREFIX-*' dans le depot. La sauvegarde n'a jamais tourne."

ARCHIVE="${DERNIERE%%	*}"
DATE_DE_L_ARCHIVE="${DERNIERE#*	}"

AGE_EN_HEURES=$(( ( $(date +%s) - $(date -d "$DATE_DE_L_ARCHIVE" +%s) ) / 3600 ))
if [ "$AGE_EN_HEURES" -le "$AGE_MAX_HEURES" ]; then
    ok "derniere archive : $ARCHIVE (il y a ${AGE_EN_HEURES} h)"
else
    ko "derniere archive : $ARCHIVE — ${AGE_EN_HEURES} h, soit plus de ${AGE_MAX_HEURES} h."
    ko "le cron ne tourne plus. Verifier :  crontab -l"
fi


#### 2. L'ARCHIVE CONTIENT-ELLE CE QU'IL FAUT ? ####
echo
echo "2. Contenu de l'archive"

CONTENU="$(borg list --format '{path}{NL}' "$BORG_REPO::$ARCHIVE")"

CHEMIN_DU_DUMP="$(grep -E '/hypostasia\.dump$' <<< "$CONTENU" | head -n1 || true)"
if [ -n "$CHEMIN_DU_DUMP" ]; then
    ok "dump PostgreSQL present"
else
    ko "aucun dump PostgreSQL dans l'archive."
fi

# media/ porte les PDF, les audios et les transcriptions : il est hors
# git, donc irremplacable. / media/ is outside git, so irreplaceable.
NOMBRE_DE_MEDIAS="$(grep -cE '/media/.+' <<< "$CONTENU" || true)"
if [ "$NOMBRE_DE_MEDIAS" -gt 0 ]; then
    ok "media/ present ($NOMBRE_DE_MEDIAS fichiers)"
else
    ko "media/ est absent de l'archive : les PDF, audios et transcriptions ne seraient pas restaures."
fi

if grep -qE '/\.env$' <<< "$CONTENU"; then
    ok ".env present (la stack est remontable telle quelle)"
else
    ko ".env absent : une restauration demanderait de resaisir toutes les cles."
fi


#### 3. LE DUMP EST-IL EXPLOITABLE, ET COMPLET ? ####
echo
echo "3. Le dump est-il restaurable ?"

if [ -z "$CHEMIN_DU_DUMP" ]; then
    ko "pas de dump a verifier."
else
    # Le dump est tire UNE fois dans un fichier temporaire, puis
    # eprouve deux fois. Le retirer du depot a chaque passe doublerait
    # le transfert reseau pour rien.
    # / Pulled once, tested twice: two pulls would double the transfer.
    DUMP_TEMPORAIRE="$(mktemp)"
    trap 'rm -f "$DUMP_TEMPORAIRE"' EXIT
    borg extract --stdout "$BORG_REPO::$ARCHIVE" "$CHEMIN_DU_DUMP" > "$DUMP_TEMPORAIRE"

    dans_postgres() {
        docker compose -f "$FICHIER_COMPOSE" exec -T postgres "$@"
    }

    # Les deux epreuves qui suivent tournent DANS le conteneur
    # postgres : s'il ne tourne pas, elles echouent toutes les deux et
    # le verdict serait « dump TRONQUE » sur une archive parfaitement
    # saine. Un monitoring reveillerait quelqu'un la nuit pour une
    # sauvegarde qui n'a rien. On distingue donc les deux cas.
    # / Both tests run inside the postgres container: with the stack
    # down, a healthy archive would be declared truncated.
    if ! dans_postgres true >/dev/null 2>&1; then
        fatal "le conteneur postgres ne repond pas — impossible d'eprouver le dump.
                 Demarrer la stack (make install), puis relancer."
    fi

    # a) le schema attendu est-il la ? Un dump d'une base VIDE se
    #    deroule parfaitement — il ne restaure simplement rien.
    #    / An empty database's dump unrolls perfectly and restores nothing.
    TABLES="$(dans_postgres pg_restore -l < "$DUMP_TEMPORAIRE" 2>/dev/null || true)"
    TABLES_MANQUANTES=""
    for table in core_page core_argument core_elementdocument auth_user; do
        grep -q " $table " <<< "$TABLES" || TABLES_MANQUANTES="$TABLES_MANQUANTES $table"
    done
    if [ -z "$TABLES_MANQUANTES" ]; then
        ok "schema Hypostasia retrouve (pages, arguments, elements, utilisateurs)"
    else
        ko "tables absentes du dump :$TABLES_MANQUANTES"
    fi

    # b) le dump va-t-il jusqu'au bout ? C'est LA question.
    if dans_postgres pg_restore -f /dev/null < "$DUMP_TEMPORAIRE" >/dev/null 2>&1; then
        ok "dump deroule entierement (aucune troncature)"
    else
        ko "dump TRONQUE : pg_restore n'arrive pas au bout du fichier."
        ko "cette sauvegarde n'est PAS restaurable."
    fi
fi


#### VERDICT ####
echo
if [ "$NOMBRE_D_ERREURS" -eq 0 ]; then
    echo "[verification] La derniere sauvegarde est restaurable."
    exit 0
fi
echo "[verification] $NOMBRE_D_ERREURS probleme(s). Cette sauvegarde n'est pas fiable." >&2
exit 1
