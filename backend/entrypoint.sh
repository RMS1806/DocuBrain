#!/bin/sh
# backend/entrypoint.sh
#
# This script is the container's entry point.
# It starts the FastAPI server in a mode suitable for the environment:
#   - Production (PaaS): no --reload, binds to $PORT injected by the platform.
#   - Local Docker:      falls back to port 8000 if $PORT is not set.
#
# The "wait for services" problem is fully solved by Docker's
# healthchecks + depends_on condition:service_healthy in docker-compose.yml,
# so by the time this script runs, all dependencies are ready.

set -e

# PaaS platforms (Render, Railway) inject $PORT at runtime.
# Fall back to 8000 so local docker-compose keeps working without changes.
APP_PORT="${PORT:-8000}"

echo "🔥 Booting Neural Worker (Celery)..."
celery -A app.docubrain_tasks worker --loglevel=info --concurrency=1 &

echo "🚀 Starting DocuBrain backend on port ${APP_PORT}..."

exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${APP_PORT}" \
    --workers 1
