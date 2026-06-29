#!/bin/sh
# backend/entrypoint.sh
#
# Container startup sequence:
#   1. Wait for DB (handled by Docker healthcheck / Alembic connection retry)
#   2. Run Alembic migrations  — schema is always up to date before app starts
#   3. Start Celery worker     — background PDF processing
#   4. Start uvicorn           — FastAPI API server

set -e

APP_PORT="${PORT:-8000}"

echo "⬆️  Running database migrations..."
alembic upgrade head

echo "🔥 Starting Celery worker..."
celery -A app.workers.document_worker:celery_app worker --loglevel=info --concurrency=1 &

echo "🚀 Starting DocuBrain API on port ${APP_PORT}..."
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${APP_PORT}" \
    --workers 1
