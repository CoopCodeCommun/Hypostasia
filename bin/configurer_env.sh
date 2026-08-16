#!/bin/bash
# =============================================================================
# bin/configurer_env.sh — Fabrique le .env d'une machine neuve
# / bin/configurer_env.sh — Builds a fresh machine's .env
#
# S'EXECUTE DEPUIS L'HOTE, AVANT `docker compose up`. Appele par
# `make install`, en premier.
#
# POURQUOI CE SCRIPT EXISTE
#
# `docker compose` LIT le .env : sans lui, POSTGRES_PASSWORD est vide et
# PostgreSQL refuse de s'initialiser. L'installation commencait donc par
# une etape non ecrite — « copier .env.example et le remplir » — dont
# seul le README portait la trace. Son oubli le plus courant ne casse
# rien tout de suite : il laisse `CHANGEZ_MOI_EN_PROD` comme SECRET_KEY,
# en production, et personne ne le voit.
# / compose READS the .env. The install began with an unwritten step
# whose most common outcome is a production SECRET_KEY still reading
# CHANGEZ_MOI_EN_PROD, silently.
#
# TROIS QUESTIONS, PAS DIX
#
#   1. dev ou prod ?     ecrit DEBUG **et** NGINX_CONF, ensemble
#   2. le domaine ?
#   3. une cle de modele ? (facultative, et modifiable ensuite dans
#      l'interface : la priorite est champ DB > variable d'environnement)
#
# Les SECRETS NE SONT JAMAIS DEMANDES : SECRET_KEY et POSTGRES_PASSWORD
# sont tirees au hasard. Une cle saisie a la main est une cle faible, ou
# recopiee d'un autre projet.
#
# UNE SEULE QUESTION POUR DEUX VARIABLES COUPLEES
#
# `DEBUG` et `NGINX_CONF` doivent bouger ENSEMBLE. La conf de prod avec
# `DEBUG=true` envoie `/` vers le port 8001, ou personne n'ecoute : 502
# sur tout le site. Les demander separement, c'est offrir la possibilite
# de se tromper — on ne pose donc qu'une question et on ecrit les deux
# lignes. / One question writes both, because getting them out of step
# 502s the whole site.
#
# IDEMPOTENT : si un .env existe, ce script ne fait RIEN. `make install`
# est rejoue a chaque demarrage de conteneur ; regenerer le fichier y
# perdrait les cles API, le mot de passe de la base — donc l'acces aux
# donnees — et la passphrase du depot de sauvegarde, ce qui rendrait
# toutes les archives illisibles.
# / Idempotent: regenerating would lose the API keys, the database
# password, and the backup passphrase.
# =============================================================================
set -euo pipefail

REPERTOIRE_DU_SCRIPT="$(cd -- "$(dirname -- "$0")" && pwd)"
REPERTOIRE_DU_PROJET="$(dirname "$REPERTOIRE_DU_SCRIPT")"

FICHIER_ENV="${ENV_FILE:-$REPERTOIRE_DU_PROJET/.env}"
FICHIER_MODELE="$REPERTOIRE_DU_PROJET/.env.example"

dire() { echo "[env] $*"; }
demander() {  # demander <invite> [defaut] -> reponse sur stdout
    local invite="$1" defaut="${2:-}" reponse=""
    if [ -n "$defaut" ]; then
        read -r -p "  $invite [$defaut] : " reponse || true
        echo "${reponse:-$defaut}"
    else
        read -r -p "  $invite : " reponse || true
        echo "$reponse"
    fi
}


#### RIEN A FAIRE SI LE FICHIER EXISTE ####
if [ -f "$FICHIER_ENV" ]; then
    dire ".env deja present — inchange."
    exit 0
fi

[ -f "$FICHIER_MODELE" ] || {
    echo "[env] .env.example introuvable : $FICHIER_MODELE" >&2
    exit 1
}
command -v openssl >/dev/null || {
    echo "[env] openssl introuvable : impossible de tirer les secrets." >&2
    exit 1
}


#### LES SECRETS, TIRES AU HASARD ####
# En hexadecimal : ce fichier est lu par docker compose, dont
# l'analyseur interprete `$`. Une valeur base64 en portant un donnerait
# une valeur differente cote conteneur et cote script. 32 octets
# hexadecimaux, c'est 256 bits d'entropie.
# / Hex, because compose interprets `$` in this file.
CLE_SECRETE="$(openssl rand -hex 32)"
MOT_DE_PASSE_POSTGRES="$(openssl rand -hex 24)"


#### LES TROIS QUESTIONS ####
MODE="prod"
DOMAINE="hypo.example.com"
NOM_DE_LA_CLE=""
VALEUR_DE_LA_CLE=""

if [ -t 0 ]; then
    echo
    dire "Aucun .env : je le fabrique. Trois questions."
    echo

    echo "  Cette machine est :"
    echo "    1) un poste de developpement  (runserver, rechargement auto)"
    echo "    2) une machine de production  (gunicorn + daphne)"
    case "$(demander "Ton choix" "1")" in
        2) MODE="prod" ;;
        *) MODE="dev"  ;;
    esac

    echo
    if [ "$MODE" = "dev" ]; then
        DOMAINE="$(demander "Domaine" "h.localhost")"
    else
        DOMAINE="$(demander "Domaine (ex. hypo.exemple.fr)" "")"
        while [ -z "$DOMAINE" ]; do
            echo "  Un domaine est necessaire en production : traefik route par hote."
            DOMAINE="$(demander "Domaine" "")"
        done
    fi

    echo
    echo "  Une cle de modele permet a l'installation d'analyser les"
    echo "  documents etalons pour de vrai — c'est ce qui teste la cle."
    echo "  Facultative : elle se renseigne aussi dans l'interface ensuite."
    echo "    1) Google Gemini    2) OpenAI    3) Anthropic    4) Mistral"
    echo "    5) aucune pour l'instant"
    case "$(demander "Ton choix" "5")" in
        1) NOM_DE_LA_CLE="GOOGLE_API_KEY" ;;
        2) NOM_DE_LA_CLE="OPENAI_API_KEY" ;;
        3) NOM_DE_LA_CLE="ANTHROPIC_API_KEY" ;;
        4) NOM_DE_LA_CLE="MISTRAL_API_KEY" ;;
        *) NOM_DE_LA_CLE="" ;;
    esac
    if [ -n "$NOM_DE_LA_CLE" ]; then
        read -r -s -p "  $NOM_DE_LA_CLE (saisie masquee) : " VALEUR_DE_LA_CLE || true
        echo
    fi
else
    # Sans terminal — `make install` appele depuis un script — on prend
    # les valeurs du fichier d'exemple plutot que d'attendre une reponse
    # qui ne viendra jamais. Le defaut est la PRODUCTION : `DEBUG=true`
    # sur une machine qu'on croyait de prod expose les traces d'erreur,
    # l'inverse ne fait que priver un poste de dev du rechargement
    # automatique. On se trompe donc du cote qui ne fuit pas.
    # / No terminal: take the example file's values. The default is
    # production, so a wrong guess does not leak stack traces.
    dire "aucun terminal : je prends les valeurs par defaut (production)."
fi


#### ECRITURE ####
# On part du fichier d'exemple et on ne remplace que les lignes
# concernees : sa forme — l'ordre, les commentaires, les variables
# facultatives — reste sa seule definition. La reecrire ici en
# ferait une deuxieme, et les deux divergeraient.
# / We start from the example file and only replace the relevant lines:
# its shape stays defined in one place.
cp "$FICHIER_MODELE" "$FICHIER_ENV"

remplacer_la_ligne() {  # remplacer_la_ligne <VARIABLE> <valeur>
    local variable="$1" valeur="$2"
    # `|` comme separateur : les valeurs peuvent porter des `/`
    # (adresses, chemins), jamais de `|`.
    # / `|` as separator: values may hold `/`, never `|`.
    sed -i "s|^${variable}=.*|${variable}=${valeur}|" "$FICHIER_ENV"
}

remplacer_la_ligne SECRET_KEY "$CLE_SECRETE"
remplacer_la_ligne POSTGRES_PASSWORD "$MOT_DE_PASSE_POSTGRES"
remplacer_la_ligne DOMAIN "$DOMAINE"

if [ "$MODE" = "dev" ]; then
    remplacer_la_ligne DEBUG "true"
    remplacer_la_ligne NGINX_CONF "dev.conf"
else
    remplacer_la_ligne DEBUG "false"
    remplacer_la_ligne NGINX_CONF "default.conf"
fi

[ -z "$NOM_DE_LA_CLE" ] || remplacer_la_ligne "$NOM_DE_LA_CLE" "$VALEUR_DE_LA_CLE"

# Le fichier porte des secrets : il ne se lit que par son proprietaire.
# / The file holds secrets: owner-only.
chmod 600 "$FICHIER_ENV"


#### CE QU'ON VIENT D'ECRIRE ####
echo
dire "$FICHIER_ENV cree."
dire "  mode      : $MODE   (DEBUG et NGINX_CONF ecrits ensemble)"
dire "  domaine   : $DOMAINE"
if [ -n "$NOM_DE_LA_CLE" ] && [ -n "$VALEUR_DE_LA_CLE" ]; then
    dire "  modele    : $NOM_DE_LA_CLE renseignee"
else
    dire "  modele    : aucune cle — l'analyse des documents etalons sera sautee"
fi
dire "  secrets   : SECRET_KEY et POSTGRES_PASSWORD tirees au hasard"
echo
dire "Ce fichier n'est PAS dans git, et rien ne le regenere : c'est la"
dire "seule copie du mot de passe de la base. Sur une machine de"
dire "production, le mettre au coffre."
echo
