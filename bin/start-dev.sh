#!/bin/bash
# =============================================================================
# bin/start-dev.sh — Demarrage du conteneur en DEVELOPPEMENT
# / bin/start-dev.sh — Container startup in DEVELOPMENT
#
# Appele par docker-compose.yml quand DEBUG=true. Enchaine
# l'installation puis supervisord, qui devient le PID 1 du conteneur.
# / Called by docker-compose.yml when DEBUG=true.
#
# CE QUI DIFFERE DE LA PRODUCTION
#
#   runserver (port 8000, ASGI) au lieu de gunicorn + daphne. Le
#   runserver de Django sert le HTTP *et* le WebSocket — daphne est en
#   tete d'INSTALLED_APPS — et il recharge le code automatiquement. La
#   production, elle, separe : gunicorn sur 8001 pour le HTTP, daphne
#   sur 8000 pour le WebSocket, et nginx/default.conf aiguille vers les
#   deux. C'est pourquoi nginx a DEUX configurations, choisies par
#   NGINX_CONF : la conf de prod pointerait `/` vers 8001, ou personne
#   n'ecoute en dev, et tout le site rendrait 502.
# / Dev serves HTTP and WebSocket from one autoreloading process on
# 8000; production splits them across 8001 and 8000, which is why nginx
# has two configurations selected by NGINX_CONF.
#
# Supervisord tourne au PREMIER PLAN, journaux sur la sortie standard :
# c'est ce qui rend `docker compose logs -f` utile en developpement.
# / Foreground, logs to stdout: what makes `docker compose logs -f`
# useful in development.
# =============================================================================
set -e

cd "$(dirname "$0")/.."

echo "=== Hypostasia — demarrage DEV ==="

bash bin/install.sh

echo "Demarrage des services (runserver + 2 workers Celery)..."
exec supervisord -c /app/supervisord-dev.conf
