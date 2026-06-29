"""
Test configuration and shared fixtures.

IMPORTANT — import order is intentional and must not be changed:

1. os.environ is populated FIRST, before any app module is imported.
   Our app reads settings at import time (module-level Settings() call),
   so env vars must exist before that happens.

2. sys.modules mocks are injected SECOND, before the app import chain runs.
   pinecone_client.py calls Pinecone(api_key=...) at module level — if we
   let that run in CI it tries to reach api.pinecone.io and fails.
   By replacing the 'pinecone' entry in sys.modules with a MagicMock before
   any app code imports it, every 'from pinecone import Pinecone' receives
   our mock instead of the real library.

3. App imports happen LAST, after the environment and mocks are in place.
"""

import os
import sys
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

# ── 1. Environment ─────────────────────────────────────────────────────────────
# setdefault: only sets the variable if it isn't already set.
# In CI, these come from the workflow's env: block (real Postgres/Redis containers).
# Locally, a developer can override by exporting them before running pytest.
os.environ.setdefault("DATABASE_URL",      "postgresql+asyncpg://test:test@localhost/docubrain_test")
os.environ.setdefault("SYNC_DATABASE_URL", "postgresql://test:test@localhost/docubrain_test")
os.environ.setdefault("REDIS_URL",         "redis://localhost:6379/15")   # DB 15 = test isolation
os.environ.setdefault("SECRET_KEY",        "test-only-secret-key-32-chars-min")
os.environ.setdefault("GEMINI_API_KEY",    "ci-placeholder-not-used-in-tests")
os.environ.setdefault("PINECONE_API_KEY",  "ci-placeholder-not-used-in-tests")
os.environ.setdefault("PINECONE_INDEX_NAME", "test-index")
os.environ.setdefault("ENVIRONMENT",       "development")

# ── 2. Module-level mocks ──────────────────────────────────────────────────────
# Replace the 'pinecone' package in Python's module registry before any app
# code can import it. Python checks sys.modules first on every import —
# if the name is there, it returns that object without touching the filesystem.
_mock_pinecone = MagicMock()
sys.modules["pinecone"] = _mock_pinecone

# google.generativeai is imported at module level in rag_service and quiz_service.
# In tests we never call RAG or quiz endpoints, but the module still loads.
_mock_genai = MagicMock()
sys.modules["google.generativeai"] = _mock_genai
sys.modules["google"] = MagicMock(generativeai=_mock_genai)

# ── 3. App import ──────────────────────────────────────────────────────────────
# Now safe to import — Settings() will find the env vars, and any 'import pinecone'
# inside the app will receive our MagicMock instead of the real library.
from app.main import app  # noqa: E402


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
async def client():
    """
    A session-scoped async HTTP client pointed at our FastAPI app.

    ASGITransport: plugs the httpx client directly into the ASGI interface —
    no real TCP socket is opened. Requests travel in-process (much faster than
    a real server) while still exercising the full middleware + routing stack.

    scope="session": the client (and the app lifespan) is created once for the
    entire test run, not once per test. This means the DB connection pool and
    Redis client are initialised once — much faster, and mirrors production
    where these are long-lived resources.
    """
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac


@pytest.fixture
async def registered_user(client: AsyncClient) -> dict:
    """
    Register a fresh user and return their credentials.
    Used by tests that need an authenticated user.
    A unique email is generated each call so tests don't collide.
    """
    import uuid
    email = f"test-{uuid.uuid4().hex[:8]}@ci.test"
    payload = {"email": email, "password": "Test1234!", "full_name": "CI User"}

    resp = await client.post("/auth/register", json=payload)
    assert resp.status_code == 201, f"Registration failed: {resp.text}"
    return {"email": email, "password": "Test1234!"}


@pytest.fixture
async def auth_headers(client: AsyncClient, registered_user: dict) -> dict:
    """
    Log in the registered user and return the Authorization header dict.
    Inject into any request that requires authentication:
        await client.get("/documents/", headers=auth_headers)
    """
    resp = await client.post("/auth/login", json=registered_user)
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
