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
#   tout           les deux a la suite. Pour un essai a la main : en
#                  production, le mail doit partir LE MATIN, donc plus
#                  tard que la passe.
#
# LES DEUX LIGNES DE CRON (heure de l'HOTE — les settings Django sont
# en UTC, l'heure locale est donc celle du cron) :
#
#   0 3 * * * bash /chemin/vers/Hypostasia/bin/nuit.sh passe \
#                  >> /var/log/hypostasia-nuit.log 2>&1
#   0 7 * * * bash /chemin/vers/Hypostasia/bin/nuit.sh recapitulatif \
#                  >> /var/log/hypostasia-nuit.log 2>&1
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
        dire "mise a jour automatique des wikis…"
        dans_le_conteneur mettre_a_jour_les_wikis
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
