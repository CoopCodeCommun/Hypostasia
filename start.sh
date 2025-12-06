#!/bin/bash
set -e

echo "uv sync --freeze"
uv sync --freeze

echo "Running migrations..."
uv run manage.py migrate

echo "Collecting static files..."
uv run manage.py collectstatic --noinput

echo "Starting Gunicorn..."
# Bind to 0.0.0.0 to be accessible outside the container
uv run gunicorn hypostasia.wsgi:application --bind 0.0.0.0:8000 --capture-output --reload -w 3
