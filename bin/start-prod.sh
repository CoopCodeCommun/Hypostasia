#!/bin/bash
# =============================================================================
# bin/start-prod.sh — Demarrage du conteneur en PRODUCTION
# / bin/start-prod.sh — Container startup in PRODUCTION
#
# Appele par docker-compose.yml quand DEBUG=false. Anciennement
# `start.sh`, a la racine.
#
# 1. Attend PostgreSQL — le conteneur peut demarrer avant sa base, et
#    migrer trop tot echoue.
# 2. Lance l'installation (bin/install.sh) : migrations, statiques,
#    documents etalons, extractions, analyse par le vrai modele. Tout y
#    est idempotent : au deuxieme demarrage, l'etape entiere prend une
#    dizaine de secondes et ne refacture aucun appel LLM.
# 3. Demarre supervisord au premier plan : gunicorn (HTTP, port 8001),
#    daphne (WebSocket, port 8000) et les TROIS workers Celery.
#
# CE QUI DIFFERE DU DEVELOPPEMENT
#
#   La production separe le HTTP et le WebSocket sur deux process et
#   deux ports ; le dev sert les deux depuis runserver sur 8000. Les
#   deux configurations nginx suivent cette difference et se choisissent
#   par NGINX_CONF. Les deux reglages vont ENSEMBLE : `DEBUG=false` avec
#   la conf de dev laisserait gunicorn sans trafic.
# / Production splits HTTP and WebSocket across two processes and ports;
# NGINX_CONF must move together with DEBUG.
# =============================================================================
set -e

cd "$(dirname "$0")/.."

echo "=== Hypostasia — demarrage PRODUCTION ==="

# Attente PostgreSQL avant toute operation
# / Wait for PostgreSQL before any operation
echo "Waiting for PostgreSQL..."
until pg_isready -h ${POSTGRES_HOST:-postgres} -U ${POSTGRES_USER:-hypostasia} -q; do
    sleep 2
done
echo "PostgreSQL is ready!"

bash bin/install.sh

# Supervisord au premier plan (logs vers stdout/stderr)
# / supervisord in foreground (logs to stdout/stderr)
echo "Demarrage des services (gunicorn + daphne + 3 workers Celery)..."
exec supervisord -c /app/supervisord.conf
