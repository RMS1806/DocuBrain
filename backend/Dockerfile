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
RUN groupadd --system appgroup && \
    useradd --system --create-home --gid appgroup appuser

# Copy application code
COPY --chown=appuser:appgroup . .

# Copy and make entrypoint executable
COPY --chown=appuser:appgroup entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# ── Writable runtime directories ───────────────────────────────────────────────
# ChromaDB writes its persistent store to ./chroma_db
# documents.py saves uploaded PDFs to ./uploads
# Both must exist and be owned by appuser BEFORE switching to non-root.
RUN mkdir -p /code/chroma_db /code/uploads && \
    chown -R appuser:appgroup /code

USER appuser

EXPOSE 8000

CMD ["/entrypoint.sh"]