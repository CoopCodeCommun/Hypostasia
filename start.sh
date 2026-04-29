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
echo "Starting services via supervisord..."
exec uv run supervisord -c /app/supervisord.conf
