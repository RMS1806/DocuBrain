# DocuBrain Backend — Developer shortcuts
#
# These commands mirror exactly what CI runs, so "it passes locally" means
# "it will pass in CI". No more "works on my machine" surprises.
#
# Usage:
#   make lint        — check code style (same as CI lint job)
#   make lint-fix    — auto-fix style issues
#   make test        — run full test suite (needs local Postgres + Redis)
#   make run         — start dev server with hot reload
#   make migrate     — apply pending Alembic migrations
#   make shell       — open a Python shell with app context

.PHONY: lint lint-fix test run migrate shell

# ── Linting ───────────────────────────────────────────────────────────────────
# Ruff is a Rust-based Python linter — 100x faster than flake8.
# The rules it checks:
#   E/W = pycodestyle (PEP 8 style)
#   F   = pyflakes (undefined names, unused imports)
#   I   = isort (import ordering)
#   UP  = pyupgrade (use modern Python syntax)
lint:
	ruff check app/ tests/

lint-fix:
	ruff check app/ tests/ --fix

# ── Tests ─────────────────────────────────────────────────────────────────────
# -v: verbose — show each test name as it runs
# --tb=short: short traceback on failure (long tracebacks bury the actual error)
test:
	pytest tests/ -v --tb=short

# Run a single test file:
#   make test FILE=tests/test_smoke.py
test-file:
	pytest $(FILE) -v --tb=long

# ── Dev server ────────────────────────────────────────────────────────────────
run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# ── Database ──────────────────────────────────────────────────────────────────
migrate:
	alembic upgrade head

migrate-down:
	alembic downgrade -1

migration:
	alembic revision --autogenerate -m "$(MSG)"

# ── Utilities ─────────────────────────────────────────────────────────────────
# Open an async Python shell with the SQLAlchemy session available.
# Useful for running one-off queries against the dev database.
shell:
	python -c "import asyncio; from app.database import AsyncSessionLocal; print('Session available as: AsyncSessionLocal()')"
