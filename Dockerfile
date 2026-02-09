FROM ghcr.io/astral-sh/uv:python3.13-trixie

# Install git for cloning
RUN apt-get update && apt-get upgrade -y && apt-get install -y git curl && rm -rf /var/lib/apt/lists/*
RUN curl -L code.kimi.com/install.sh | bash


RUN useradd -ms /bin/bash hypostasia
USER hypostasia

# Set working directory
WORKDIR /app

# Clone the repository
# We clone into a temporary dir and move it to /app or just clone into .
# Since /app is empty, we can clone .
RUN git clone https://github.com/CoopCodeCommun/Hypostasia .

# Install dependencies
# Using system python environment managed by uv
RUN uv sync --frozen

# Ensure the db directory exists
RUN mkdir -p db staticfiles

# Environment variables
ENV PATH="/app/.venv/bin:$PATH"


