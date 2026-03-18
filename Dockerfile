FROM ghcr.io/astral-sh/uv:python3.13-trixie

# Paquets systeme necessaires : git, ffmpeg (audio), pg_isready (healthcheck)
# / Required system packages: git, ffmpeg (audio), pg_isready (healthcheck)
RUN apt-get update && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends git curl ffmpeg postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Creer un user non-root avec uid 1000 (match le defaut docker-compose)
# / Create a non-root user with uid 1000 (matches docker-compose default)
RUN useradd -ms /bin/bash -u 1000 hypostasia
COPY .bashrc /home/hypostasia/.bashrc
USER hypostasia

WORKDIR /app

# Cloner le depot / Clone the repository
RUN git clone https://github.com/CoopCodeCommun/Hypostasia .

# Installer les dependances Python / Install Python dependencies
RUN uv sync --frozen

# Creer les repertoires necessaires / Create required directories
RUN mkdir -p db staticfiles logs tmp/audio media

ENV PATH="/app/.venv/bin:$PATH"
