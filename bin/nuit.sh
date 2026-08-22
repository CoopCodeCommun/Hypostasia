#!/bin/bash
# =============================================================================
# bin/nuit.sh — La passe de nuit des wikis, puis le recapitulatif du matin
# / bin/nuit.sh — The nightly wiki pass, then the morning recap
#
# S'EXECUTE DEPUIS L'HOTE, comme bin/backup.sh et pour la meme raison :
# il pilote Docker (`docker compose exec`) et vit dans le crontab de
# l'hote. Un script qui vit dans le conteneur ne peut faire ni l'un ni
# l'autre.
# / Runs from the HOST: it drives Docker and sits in the host's crontab.
#
# CE SCRIPT EST LA PORTE MANUELLE, PAS LA PLANIFICATION.
#
# La planification vit DANS L'APPLICATION : `hypostasia/celery.py`
# (`beat_schedule`), lue par le programme `celery_beat` de supervisord.
# Elle est versionnee, relue en revue, et elle voyage avec le depot —
# ce qu'un crontab d'hote ne fait pas : il ne se deplace pas avec le
# code, et un clone frais ne l'a pas.
#
# NE PAS POSER CE SCRIPT DANS UN CRON. Il ferait partir la passe DEUX
# fois par nuit — une par le beat, une par le cron — sur les memes
# wikis, donc la facture du redacteur doublee. Il sert a lancer la
# chose A LA MAIN, quand on veut la voir tourner tout de suite.
# / This script is the manual door. The schedule lives in the app; do
# not put this in a crontab or the pass would fire twice.
#
# Les heures se reglent par variables d'environnement, dans le .env :
#     HEURE_PASSE_DE_NUIT=2     (defaut, en UTC)
#     HEURE_RECAPITULATIF=6     (defaut, en UTC)
#
# DEUX ETAPES, A DEUX HEURES DIFFERENTES
#
#   passe          met a jour les wikis dont le perimetre a du neuf.
#                  APPELLE UN VRAI MODELE : c'est facture, un appel par
#                  wiki examine. A poser tard, quand personne ne lit.
#   recapitulatif  envoie un mail par personne, au maximum un par jour.
#                  ATTEND la fin de la passe avant de partir — le mail
#                  annonce le travail de la nuit, il ne peut pas le
#                  preceder. Voir la commande Django, qui refuse plutot
#                  que d'annoncer a moitie.
#
#                  ATTENTION : cette attente porte sur une passe DEJA
#                  OUVERTE. Lancee juste apres `passe`, elle ne verrait
#                  rien — la mise en file rend la main en quelques
#                  millisecondes. C'est pourquoi l'etape `tout`
#                  ci-dessous passe `--attendre` a la premiere.
#   tout           les deux a la suite. Pour un essai a la main : en
#                  production, le mail doit partir LE MATIN, donc plus
#                  tard que la passe.
#
# POUR VERIFIER QUE LA PLANIFICATION TOURNE :
#
#   make status                       (le programme celery_beat)
#   docker compose logs -f web        (« beat: Starting... » au demarrage)
#
# L'ENVOI REEL EXIGE EMAIL_HOST* DANS LE .env. Sans eux, le backend par
# defaut est la CONSOLE : les mails s'impriment dans les journaux du
# conteneur et personne ne recoit rien — sans la moindre erreur.
# / Without EMAIL_HOST*, the console backend swallows every mail silently.
# =============================================================================
set -euo pipefail

REPERTOIRE_DU_SCRIPT="$(cd -- "$(dirname -- "$0")" && pwd)"
REPERTOIRE_DU_PROJET="$(dirname "$REPERTOIRE_DU_SCRIPT")"
FICHIER_COMPOSE="$REPERTOIRE_DU_PROJET/docker-compose.yml"

ETAPE="${1:-tout}"

[ -f "$FICHIER_COMPOSE" ] || {
    echo "[nuit] docker-compose.yml introuvable : $FICHIER_COMPOSE" >&2
    exit 1
}

dire() {
    echo "[nuit $(date '+%Y-%m-%d %H:%M:%S')] $*"
}

dans_le_conteneur() {
    docker compose -f "$FICHIER_COMPOSE" exec -T web python manage.py "$@"
}

case "$ETAPE" in
    passe)
        dire "mise a jour automatique des wikis…"
        dans_le_conteneur mettre_a_jour_les_wikis "${@:2}"
        ;;
    recapitulatif)
        dire "recapitulatif du matin…"
        dans_le_conteneur envoyer_le_recapitulatif_du_matin "${@:2}"
        ;;
    tout)
        # `--attendre` EST INDISPENSABLE ICI, et pas un confort : la
        # commande ne fait que METTRE EN FILE et rend la main en
        # quelques millisecondes. Sans elle, le recapitulatif partirait
        # avant meme que la passe n'existe — donc avant le travail
        # qu'il annonce. / Without --attendre the recap would mail
        # before the pass even exists.
        dire "mise a jour automatique des wikis (on attend la fin)…"
        dans_le_conteneur mettre_a_jour_les_wikis --attendre
        dire "recapitulatif du matin…"
        dans_le_conteneur envoyer_le_recapitulatif_du_matin
        ;;
    *)
        echo "[nuit] etape inconnue : $ETAPE" >&2
        echo "Usage : bin/nuit.sh [passe|recapitulatif|tout]" >&2
        exit 1
        ;;
esac

dire "termine."
