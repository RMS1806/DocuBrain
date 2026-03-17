#!/usr/bin/env bash
# dev-reset.sh
#
# DocuBrain Development Reset Script
# ═══════════════════════════════════
# Wipes ALL Docker volumes (Postgres, MinIO, ChromaDB) and rebuilds
# from scratch. Run this whenever you make model/schema changes that
# `create_all()` cannot handle automatically (e.g. dropped or renamed columns).
#
# Usage:
#   bash dev-reset.sh          # Interactive (asks for confirmation)
#   bash dev-reset.sh --force  # Non-interactive (for CI / scripted use)
#
# WARNING: All persistent data (uploaded files, vector embeddings,
# database rows) will be permanently deleted.

set -euo pipefail

COMPOSE_FILE="docker-compose.yml"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Colour helpers ─────────────────────────────────────────────────────────────
RED='\033[0;31m'
YLW='\033[1;33m'
GRN='\033[0;32m'
CYN='\033[0;36m'
RST='\033[0m'

banner() { echo -e "${CYN}══════════════════════════════════════════${RST}"; }

# ── Confirmation ───────────────────────────────────────────────────────────────
if [[ "${1:-}" != "--force" ]]; then
    banner
    echo -e "${RED}⚠️  WARNING: This will PERMANENTLY DELETE all local data.${RST}"
    echo -e "   • Postgres database (all users, documents, links)"
    echo -e "   • MinIO object storage (all uploaded PDFs)"
    echo -e "   • ChromaDB vector store (all embeddings)"
    banner
    read -rp "$(echo -e ${YLW}"Type 'yes' to confirm, anything else to abort: "${RST})" CONFIRM
    if [[ "${CONFIRM}" != "yes" ]]; then
        echo -e "${GRN}Aborted. No data was changed.${RST}"
        exit 0
    fi
fi

cd "${PROJECT_DIR}"

echo ""
echo -e "${CYN}[1/4] Stopping all containers…${RST}"
docker compose -f "${COMPOSE_FILE}" down --remove-orphans

echo -e "${CYN}[2/4] Removing all named volumes…${RST}"
docker compose -f "${COMPOSE_FILE}" down -v

echo -e "${CYN}[3/4] Rebuilding images (no cache for backend/frontend)…${RST}"
docker compose -f "${COMPOSE_FILE}" build --no-cache backend worker frontend

echo -e "${CYN}[4/4] Starting fresh stack…${RST}"
docker compose -f "${COMPOSE_FILE}" up -d

echo ""
banner
echo -e "${GRN}✅ Dev reset complete! Fresh stack is starting up.${RST}"
echo -e "   Backend:  http://localhost:8000"
echo -e "   Frontend: http://localhost:5173"
echo -e "   MinIO UI: http://localhost:9001"
echo -e "   ChromaDB: http://localhost:8001/api/v1/heartbeat"
banner
echo ""
echo -e "   Follow logs with:  ${CYN}docker compose logs -f backend worker${RST}"
