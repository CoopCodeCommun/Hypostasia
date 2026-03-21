# =============================================================================
# Hypostasia — Image unifiee dev/prod
#
# Inclut les dependances Playwright (Chromium) pour les tests E2E.
# Le comportement dev/prod est determine par DEBUG dans .env,
# pas par l'image Docker.
#
# Build :  docker compose build
# Dev :    docker compose up -d  (avec DEBUG=true dans .env)
# Prod :   docker compose up -d  (avec DEBUG=false dans .env)
# / Unified dev/prod image.
# / Includes Playwright (Chromium) dependencies for E2E tests.
# / Dev/prod behavior is determined by DEBUG in .env, not by the Docker image.
# =============================================================================

FROM ghcr.io/astral-sh/uv:python3.14-trixie

# Paquets systeme : git, ffmpeg (audio), pg_isready (healthcheck),
# + dependances Chromium pour Playwright E2E
# / System packages: git, ffmpeg (audio), pg_isready (healthcheck),
# / + Chromium dependencies for Playwright E2E
RUN apt-get update && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
        git curl ffmpeg postgresql-client \
        # Dependances Playwright Chromium / Playwright Chromium dependencies
        libnss3 libnspr4 libatk1.0-0t64 libatk-bridge2.0-0t64 \
        libatspi2.0-0t64 libcups2t64 libxcomposite1 libxdamage1 \
        libxkbcommon0 libpango-1.0-0 libcairo2 libasound2t64 \
        libdbus-1-3 libdrm2 libgbm1 libglib2.0-0t64 \
        libx11-6 libxcb1 libxext6 libxfixes3 libxrandr2 \
        libfontconfig1 libfreetype6 \
        # Xvfb pour les tests headless / Xvfb for headless tests
        xvfb \
        # Polices pour le rendu correct / Fonts for correct rendering
        fonts-liberation fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

# Creer un user non-root avec uid 1000 (match le defaut docker-compose)
# / Create a non-root user with uid 1000 (matches docker-compose default)
RUN useradd -ms /bin/bash -u 1000 hypostasia
COPY .bashrc /home/hypostasia/.bashrc
USER hypostasia

WORKDIR /app

# Copier les fichiers de dependances en premier (layer cache Docker)
# / Copy dependency files first (Docker layer cache)
COPY --chown=hypostasia:hypostasia pyproject.toml uv.lock ./

# Installer les dependances Python / Install Python dependencies
RUN uv sync --frozen

# Installer les browsers Playwright (Chromium uniquement)
# / Install Playwright browsers (Chromium only)
RUN uv run playwright install chromium

# Copier le code source / Copy source code
# En dev, le volume mount ecrase ce COPY — c'est voulu.
# En prod sans volume, le code est dans l'image.
# / In dev, the volume mount overrides this COPY — that's intentional.
# / In prod without volume, the code is baked in the image.
COPY --chown=hypostasia:hypostasia . .

# Creer les repertoires necessaires / Create required directories
RUN mkdir -p db staticfiles logs tmp/audio media

ENV PATH="/app/.venv/bin:$PATH"
