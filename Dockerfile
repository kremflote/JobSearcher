# JobSearcher: one image with the API, the scheduler and the built dashboard (ARCHITECTURE §12).
# Builds for linux/arm64 (the Pi) and linux/amd64. Data lives in the /data volume.

# --- 1. Frontend -------------------------------------------------------------------------
FROM node:22-bookworm-slim AS web
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# --- 2. App --------------------------------------------------------------------------------
FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /usr/local/bin/uv

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# Same uid as the Pi user, so files in the volume stay owned by kremflote.
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /app /data \
    && chown app:app /app /data
USER app
WORKDIR /app

# Claude Code CLI for the optional `claude_code` backend (ARCHITECTURE §8.1, §19 #8).
ENV DISABLE_AUTOUPDATER=1
RUN curl -fsSL https://claude.ai/install.sh | bash

# Dependencies first, so code changes don't reinstall them.
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY --chown=app:app pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

# The app runs from /app (config.ROOT): config/, prompts, migrations and web/dist resolve there.
COPY --chown=app:app README.md alembic.ini ./
COPY --chown=app:app src/ src/
COPY --chown=app:app config/ config/
COPY --chown=app:app context/prompts/ context/prompts/
COPY --from=web --chown=app:app /app/web/dist web/dist
RUN uv sync --locked --no-dev

ENV PATH="/app/.venv/bin:/home/app/.local/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    TZ=Europe/Oslo \
    DATA_DIR=/data \
    PROFILE_DIR=/data/profile \
    DERIVED_DIR=/data/derived

VOLUME /data
EXPOSE 8765
HEALTHCHECK --interval=60s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8765/api/health', timeout=4)"
CMD ["jobsearcher", "serve", "--host", "0.0.0.0", "--no-build"]
