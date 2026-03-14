#!/bin/bash
set -e

echo "uv sync"
uv sync

# Attente PostgreSQL avant migration
# / Wait for PostgreSQL before migration
echo "Waiting for PostgreSQL..."
until pg_isready -h ${POSTGRES_HOST:-postgres} -U ${POSTGRES_USER:-hypostasia} -q; do
    sleep 2
done
echo "PostgreSQL is ready!"

echo "Running migrations..."
uv run manage.py migrate

echo "Collecting static files..."
uv run manage.py collectstatic --noinput

# Creer les repertoires de logs si absents
# / Create log directories if missing
mkdir -p /app/logs /app/tmp/audio

echo "Starting services via supervisord (gunicorn + celery worker)..."
uv run supervisord -c /app/supervisord.conf &
tail -f /app/logs/*
