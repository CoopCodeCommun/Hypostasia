#!/bin/bash
set -e

echo "Running migrations..."
uv run manage.py migrate

echo "Collecting static files..."
uv run manage.py collectstatic --noinput

echo "Starting Gunicorn..."
# Bind to 0.0.0.0 to be accessible outside the container
exec uv run gunicorn hypostasia.wsgi:application --bind 0.0.0.0:8000
