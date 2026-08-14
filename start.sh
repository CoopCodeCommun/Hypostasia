#!/bin/bash
# =============================================================================
# start.sh — Demarrage production Hypostasia (Docker)
# / start.sh — Hypostasia production startup (Docker)
#
# 1. Attend PostgreSQL
# 2. Lance install.sh (sync, migrate, collectstatic, fixtures)
# 3. Demarre supervisord (gunicorn + celery worker)
# =============================================================================
set -e

# Attente PostgreSQL avant toute operation
# / Wait for PostgreSQL before any operation
echo "Waiting for PostgreSQL..."
until pg_isready -h ${POSTGRES_HOST:-postgres} -U ${POSTGRES_USER:-hypostasia} -q; do
    sleep 2
done
echo "PostgreSQL is ready!"

# Installation / mise a jour (idempotent)
# / Install / update (idempotent)
bash /app/install.sh

# Demarrer supervisord au premier plan (logs vers stdout/stderr)
# / Start supervisord in foreground (logs to stdout/stderr)
# Sans `uv run` : le PATH de l'image contient deja /app/.venv/bin
# (Dockerfile), et un wrapper de plus entre PID 1 et supervisord ne ferait
# qu'eloigner les signaux d'arret du conteneur de ceux qui doivent les
# recevoir. / No `uv run`: the venv is already on PATH, and a wrapper
# would only push the container's stop signals further from their target.
echo "Starting services via supervisord..."
exec supervisord -c /app/supervisord.conf
