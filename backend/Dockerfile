# backend/Dockerfile

# ── Stage 1: Dependency installer ──────────────────────────────────────────────
# Separate stage so requirements are cached independently of app code changes.
FROM python:3.11-slim AS builder

WORKDIR /build

# System dependencies required by libmagic and psycopg2
RUN apt-get update && apt-get install -y \
    libmagic1 \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: Runtime image ─────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Re-install only the runtime system libs (no build tools)
RUN apt-get update && apt-get install -y \
    libmagic1 \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder stage
COPY --from=builder /install /usr/local

WORKDIR /code

# ── Non-root user for security ─────────────────────────────────────────────────
# useradd --create-home gives appuser a real home dir (/home/appuser).
# Without this, the home resolves to /nonexistent and sentence-transformers
# crashes trying to write its model cache there.
RUN groupadd --system appgroup && \
    useradd --system --create-home --gid appgroup appuser

# ── HuggingFace model cache ────────────────────────────────────────────────────
# Bake the cache path into the image so it is set for every process
# (uvicorn AND celery worker) regardless of how the container is started.
# /home/appuser/.cache is owned by appuser so writes never fail.
ENV HF_HOME=/home/appuser/.cache/huggingface \
    TRANSFORMERS_CACHE=/home/appuser/.cache/huggingface

# Pre-create the cache dir and hand it to appuser before switching users
RUN mkdir -p /home/appuser/.cache/huggingface && \
    chown -R appuser:appgroup /home/appuser

# Copy application code
COPY --chown=appuser:appgroup . .

# Copy and make entrypoint executable
COPY --chown=appuser:appgroup entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER appuser

EXPOSE 8000

CMD ["/entrypoint.sh"]