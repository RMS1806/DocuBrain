"""
app/config.py

Central configuration — single source of truth for every environment variable.
All os.getenv() calls are consolidated here. No other file should call os.getenv().

In a full enterprise setup this would use pydantic-settings for automatic
type coercion and .env loading. This version keeps the same contract without
adding a new dependency.
"""

import os


class Settings:
    def __init__(self) -> None:
        # ── Auth ──────────────────────────────────────────────────────────────
        self.SECRET_KEY: str = os.getenv("SECRET_KEY", "")
        self.ALGORITHM: str = "HS256"
        self.ACCESS_TOKEN_EXPIRE_MINUTES: int = 15   # short-lived: 15 min
        self.REFRESH_TOKEN_EXPIRE_DAYS: int = 7      # long-lived: 7 days in Redis

        # "development" | "production" — controls cookie Secure + SameSite flags
        self.ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

        # ── Database ──────────────────────────────────────────────────────────
        self.DATABASE_URL: str = os.getenv("DATABASE_URL", "")
        self.SYNC_DATABASE_URL: str = os.getenv("SYNC_DATABASE_URL", "")
        # Optional read replica. If not set, read queries fall back to the primary.
        # In production: set this to your replica's connection string.
        # In dev / single-server: leave unset — behaviour is identical to before.
        self.READ_REPLICA_URL: str = os.getenv("READ_REPLICA_URL", "")

        # ── Redis ─────────────────────────────────────────────────────────────
        # REDIS_CACHE_URL takes precedence; falls back to REDIS_URL then local.
        self.REDIS_URL: str = (
            os.getenv("REDIS_CACHE_URL")
            or os.getenv("REDIS_URL")
            or "redis://redis:6379/0"
        )

        # ── S3 / Object Storage ───────────────────────────────────────────────
        self.AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
        self.AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
        self.AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
        self.S3_BUCKET_NAME: str = os.getenv("S3_BUCKET_NAME", "docubrain-uploads-1806")
        self.S3_ENDPOINT: str = os.getenv("S3_ENDPOINT", "")

        # ── AI / ML ───────────────────────────────────────────────────────────
        self.GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
        self.PINECONE_API_KEY: str = os.getenv("PINECONE_API_KEY", "")
        self.PINECONE_INDEX_NAME: str = os.getenv("PINECONE_INDEX_NAME", "docubrain-index")

        # ── CORS ──────────────────────────────────────────────────────────────
        self.FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")

        # Comma-separated list of explicitly allowed origins.
        # Example production value: "https://docubrain.vercel.app,https://docubrain-staging.vercel.app"
        _raw = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
        self.ALLOWED_ORIGINS: list[str] = [o.strip() for o in _raw.split(",") if o.strip()]

        # Always allow localhost in case it wasn't included explicitly.
        if "http://localhost:5173" not in self.ALLOWED_ORIGINS:
            self.ALLOWED_ORIGINS.append("http://localhost:5173")

    def validate(self) -> None:
        """Crash loudly at startup if any critical variable is missing."""
        required = {
            "SECRET_KEY": self.SECRET_KEY,
            "DATABASE_URL": self.DATABASE_URL,
            "GEMINI_API_KEY": self.GEMINI_API_KEY,
            "PINECONE_API_KEY": self.PINECONE_API_KEY,
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            raise RuntimeError(
                f"Missing required environment variables: {', '.join(missing)}\n"
                "Check your .env file or deployment secrets."
            )


settings = Settings()
