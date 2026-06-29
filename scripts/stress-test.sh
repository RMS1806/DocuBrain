#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# scripts/stress-test.sh — local stress test runner
#
# Runs the three k6 test suites in order: smoke → load → spike
# Prints metrics to terminal and saves JSON to k6/results/
#
# Usage:
#   bash scripts/stress-test.sh            # smoke + load only (safe default)
#   bash scripts/stress-test.sh --full     # smoke + load + spike (200 VUs)
#   bash scripts/stress-test.sh --smoke    # smoke only (30s sanity check)
#
# Prerequisites:
#   1. k6 installed  →  winget install k6 --source winget
#   2. Docker running
#   3. .env file exists  →  cp .env.example .env
# ──────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Windows / Git Bash: non-interactive shells skip ~/.bashrc ─────────────────
# Manually add the location where we installed k6.exe.
export PATH="$PATH:$HOME/AppData/Local/k6"

# ── Colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'   # No Colour

info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }
header()  { echo -e "\n${BOLD}${BLUE}═══ $* ═══${NC}\n"; }

# ── Parse flags ───────────────────────────────────────────────────────────────
RUN_SPIKE=false
SMOKE_ONLY=false

for arg in "$@"; do
  case $arg in
    --full)   RUN_SPIKE=true ;;
    --smoke)  SMOKE_ONLY=true ;;
    *) echo "Unknown flag: $arg"; exit 1 ;;
  esac
done

# ── Locate project root (works from any subdirectory) ─────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
RESULTS_DIR="k6/results"
mkdir -p "$RESULTS_DIR"

# k6 stats to show — these are the numbers that go on your resume
K6_TREND_STATS="avg,p(90),p(95),p(99),max"

# ── 1. Check prerequisites ────────────────────────────────────────────────────
header "Checking prerequisites"

if ! command -v k6 &>/dev/null; then
  error "k6 is not installed.\n\n  Install on Windows:  winget install k6 --source winget\n  Install on Mac:      brew install k6\n  Install on Linux:    https://k6.io/docs/get-started/installation/"
fi
success "k6 $(k6 version | head -1)"

if ! command -v docker &>/dev/null; then
  error "Docker is not installed or not in PATH."
fi
success "docker $(docker --version | cut -d' ' -f3 | tr -d ',')"

if [ ! -f ".env" ]; then
  error ".env not found. Run:  cp .env.example .env"
fi
success ".env file found"

# ── 2. Start the Docker stack ─────────────────────────────────────────────────
header "Starting Docker stack"

info "Running: docker compose up -d"
docker compose up -d

success "Containers started"

# ── 3. Wait for the app to be healthy ────────────────────────────────────────
header "Waiting for app to be ready"

HEALTH_URL="http://localhost/health"
MAX_WAIT=120   # seconds
WAITED=0

info "Polling $HEALTH_URL (timeout: ${MAX_WAIT}s)..."

until curl -sf "$HEALTH_URL" >/dev/null 2>&1; do
  if [ "$WAITED" -ge "$MAX_WAIT" ]; then
    echo ""
    error "App did not become healthy after ${MAX_WAIT}s.\n\n  Check logs:  docker compose logs backend\n               docker compose logs nginx"
  fi
  printf "."
  sleep 3
  WAITED=$((WAITED + 3))
done

echo ""
success "App is healthy at $HEALTH_URL (waited ${WAITED}s)"

# ── 4. Run database migrations ────────────────────────────────────────────────
header "Running database migrations"

info "Running: alembic upgrade head (direct to db — bypassing PgBouncer)"
# PgBouncer runs in transaction mode which drops the connection between commits.
# Alembic needs a persistent session across multiple DDL statements, so it must
# connect directly to the postgres container (db:5432), not through pgbouncer.
# We source .env to get credentials, then override SYNC_DATABASE_URL inside the container.
set -o allexport
# shellcheck disable=SC1091
source .env
set +o allexport
DIRECT_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db/${POSTGRES_DB}"
docker compose exec -T backend sh -c "SYNC_DATABASE_URL=${DIRECT_URL} alembic upgrade head"
success "Migrations applied"

# ── 5. Smoke test ─────────────────────────────────────────────────────────────
header "Smoke test — 1 VU × 30s (sanity check)"

SMOKE_RESULT="$RESULTS_DIR/smoke-$TIMESTAMP.json"

k6 run \
  --summary-trend-stats="$K6_TREND_STATS" \
  --out "json=$SMOKE_RESULT" \
  k6/smoke.js

success "Smoke test complete → $SMOKE_RESULT"

if [ "$SMOKE_ONLY" = true ]; then
  echo -e "\n${GREEN}${BOLD}Smoke test done. Run with --full to also run load + spike.${NC}"
  exit 0
fi

# ── 6. Load test ──────────────────────────────────────────────────────────────
header "Load test — ramp to 50 VUs over 5 min (the main benchmark)"

echo -e "${YELLOW}This takes ~5 minutes. These are the metrics for your resume.${NC}\n"

LOAD_RESULT="$RESULTS_DIR/load-$TIMESTAMP.json"

k6 run \
  --summary-trend-stats="$K6_TREND_STATS" \
  --out "json=$LOAD_RESULT" \
  k6/load.js

success "Load test complete → $LOAD_RESULT"

# ── 7. Spike test (optional) ──────────────────────────────────────────────────
if [ "$RUN_SPIKE" = true ]; then
  header "Spike test — ramp to 200 VUs (circuit breaker + recovery test)"

  warn "This hammers the system hard. Expect 429s and possible circuit breaker trips."

  SPIKE_RESULT="$RESULTS_DIR/spike-$TIMESTAMP.json"

  k6 run \
    --summary-trend-stats="$K6_TREND_STATS" \
    --out "json=$SPIKE_RESULT" \
    k6/spike.js

  success "Spike test complete → $SPIKE_RESULT"
else
  warn "Spike test skipped. Run with --full to include it."
fi

# ── 8. Final summary ──────────────────────────────────────────────────────────
header "Done"

echo -e "${BOLD}Results saved to:${NC}"
ls -lh "$RESULTS_DIR/"*"$TIMESTAMP"* 2>/dev/null || true

echo ""
echo -e "${BOLD}Screenshot the load test output above for your resume.${NC}"
echo -e "Key metrics to note:"
echo -e "  • ${GREEN}http_req_duration p(95)${NC} — 95th percentile response time"
echo -e "  • ${GREEN}http_reqs / s${NC}          — requests per second throughput"
echo -e "  • ${GREEN}checks rate${NC}             — percentage of assertions that passed"
echo ""
echo -e "To add Grafana dashboards later: bash scripts/start-monitoring.sh"
