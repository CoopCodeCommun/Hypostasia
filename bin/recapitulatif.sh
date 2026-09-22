#!/bin/bash
# =============================================================================
# bin/recapitulatif.sh — Le recapitulatif du matin, lance a la main
# / bin/recapitulatif.sh — The morning recap, run by hand
#
# S'EXECUTE DEPUIS L'HOTE, comme bin/backup.sh et pour la meme raison :
# il pilote Docker (`docker compose exec`). Un script qui vit dans le
# conteneur ne peut pas le faire.
# / Runs from the HOST: it drives Docker.
#
# LE MAIL PART DEJA TOUT SEUL, chaque matin : c'est le planificateur
# Celery qui le lance (`hypostasia/celery.py`, `beat_schedule`). Ce
# script sert a l'envoyer A LA MAIN — un essai, un rattrapage. Il
# n'appelle aucun modele. Les options passent telles quelles a la
# commande Django :
#
#   bin/recapitulatif.sh --a-blanc              qui recevrait quoi
#   bin/recapitulatif.sh --adresse-de-test X    un essai SMTP, sans trace
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

[ -f "$FICHIER_COMPOSE" ] || {
    echo "[recapitulatif] docker-compose.yml introuvable : $FICHIER_COMPOSE" >&2
    exit 1
}

echo "[recapitulatif $(date '+%Y-%m-%d %H:%M:%S')] envoi…"
docker compose -f "$FICHIER_COMPOSE" exec -T web \
    python manage.py envoyer_le_recapitulatif_du_matin "$@"
echo "[recapitulatif $(date '+%Y-%m-%d %H:%M:%S')] termine."
