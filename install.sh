#!/bin/bash
# =============================================================================
# install.sh — Installation / mise a jour Hypostasia
# / install.sh — Hypostasia install / update
#
# Idempotent : peut etre relance sans risque (ne casse rien, n'ecrase rien).
# - uv sync : installe/met a jour les dependances
# - migrate : applique les nouvelles migrations (skip celles deja appliquees)
# - collectstatic : copie les fichiers CSS/JS (ecrase les anciens, pas de perte)
# - charger_fixtures_demo : cree les donnees de demo si absentes (get_or_create)
#
# / Idempotent: can be re-run safely (no data loss, no overwrites).
# =============================================================================
set -e

echo "=== Hypostasia install ==="

# 1. Installer / mettre a jour les dependances Python
# / Install / update Python dependencies
echo "[1/5] uv sync..."
uv sync

# 2. Creer les repertoires necessaires
# / Create required directories
echo "[2/5] Repertoires..."
mkdir -p logs tmp/audio staticfiles

# 3. Appliquer les migrations (idempotent — skip celles deja faites)
# / Apply migrations (idempotent — skips already applied ones)
echo "[3/5] Migrations..."
uv run python manage.py migrate

# 4. Collecter les fichiers statiques (CSS, JS, images)
# / Collect static files (CSS, JS, images)
echo "[4/5] Collectstatic..."
uv run python manage.py collectstatic --noinput

# 5. Charger les fixtures de demonstration (idempotent — get_or_create)
# Les users, pages, extractions et commentaires sont crees seulement s'ils n'existent pas
# / Load demo fixtures (idempotent — get_or_create)
# / Users, pages, extractions and comments are created only if missing
echo "[5/5] Fixtures demo..."
uv run python manage.py charger_fixtures_demo

echo "=== Installation terminee ==="
