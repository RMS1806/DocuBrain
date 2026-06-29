"""
Circuit Breaker — resilience pattern for external service calls.

State machine:

  CLOSED ──[failure_threshold reached]──→ OPEN ──[recovery_timeout elapsed]──→ HALF-OPEN
    ↑                                                                                │
    └───────────────────────[test call succeeds]─────────────────────────────────────┘
    (HALF-OPEN also returns to OPEN immediately if the test call fails)

Usage:
    result = await gemini_breaker.call(lambda: anyio.to_thread.run_sync(my_sync_fn))

`call` accepts a zero-argument async callable (a "thunk") so the circuit breaker
controls whether the call is even attempted — it never touches the coroutine/awaitable
directly, which keeps the API simple and composable.
"""

import asyncio
import logging
import time
from enum import Enum
from typing import Awaitable, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    CLOSED = "closed"        # healthy — calls go through
    OPEN = "open"            # tripped — calls are rejected immediately (fail fast)
    HALF_OPEN = "half_open"  # cooldown over — one test call allowed through


class CircuitOpenError(Exception):
    """
    Raised when a call is rejected because the circuit is open.
    Services should catch this and return HTTP 503 with a user-friendly message
    rather than letting it propagate as a 500.
    """
    def __init__(self, service: str):
        super().__init__(
            f"'{service}' is temporarily unavailable. Please try again in a moment."
        )
        self.service = service


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
    ):
        """
        name              — human-readable label used in logs and error messages
        failure_threshold — consecutive failures before tripping (CLOSED → OPEN)
        recovery_timeout  — seconds to wait in OPEN before trying again (OPEN → HALF-OPEN)
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at: float | None = None
        # asyncio.Lock is safe at class-init time in Python 3.10+ (no longer binds to a loop)
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    # ── Private state transitions ─────────────────────────────────────────────

    def _trip(self) -> None:
        """CLOSED / HALF-OPEN → OPEN. Records the timestamp so we know when to try again."""
        self._state = CircuitState.OPEN
        self._opened_at = time.monotonic()
        logger.warning(
            "Circuit OPEN — service=%s failures=%d/%d",
            self.name, self._failure_count, self.failure_threshold,
        )

    def _reset(self) -> None:
        """Any state → CLOSED. A successful call always fully resets the breaker."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at = None
        logger.info("Circuit CLOSED — service=%s recovered", self.name)

    def _check_recovery(self) -> None:
        """
        Called at the start of every attempt while holding the lock.
        If enough time has passed since the circuit opened, promote to HALF-OPEN
        so the next call becomes a live test.
        """
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - (self._opened_at or 0.0)
            if elapsed >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                logger.info(
                    "Circuit HALF-OPEN — service=%s testing recovery after %.0fs",
                    self.name, elapsed,
                )

    # ── Public API ────────────────────────────────────────────────────────────

    async def call(self, coro_fn: Callable[[], Awaitable[T]]) -> T:
        """
        Execute `coro_fn()` guarded by the circuit breaker.

        `coro_fn` is a zero-argument async callable — a thunk.
        Example:
            await s3_breaker.call(lambda: anyio.to_thread.run_sync(upload_fn))

        The thunk pattern means we never construct the coroutine until we know
        the circuit is CLOSED — a small but correct detail.
        """
        async with self._lock:
            self._check_recovery()

            if self._state == CircuitState.OPEN:
                # Fail fast — no network call attempted.
                raise CircuitOpenError(self.name)

            # Remember whether we entered as HALF-OPEN so we handle failure correctly below.
            was_half_open = (self._state == CircuitState.HALF_OPEN)

        # ── Run the actual call — lock is NOT held here ───────────────────────
        # Holding the lock across a network call would serialize all requests through
        # this breaker, destroying async concurrency. We only lock for state reads/writes.
        try:
            result = await coro_fn()

        except CircuitOpenError:
            raise  # already a circuit error — don't double-count

        except Exception as exc:
            async with self._lock:
                if was_half_open:
                    # Test call failed — service still broken. Re-open immediately.
                    self._trip()
                else:
                    self._failure_count += 1
                    logger.warning(
                        "Circuit failure %d/%d — service=%s error=%s",
                        self._failure_count, self.failure_threshold, self.name, exc,
                    )
                    if self._failure_count >= self.failure_threshold:
                        self._trip()
            raise

        else:
            async with self._lock:
                # Any success (including a HALF-OPEN test) fully resets the breaker.
                self._reset()
            return result


# ── Singleton instances — one per external service ────────────────────────────
#
# Gemini gets a longer recovery_timeout (60s) because AI APIs often take longer
# to recover from overload. S3 gets a lower failure_threshold (3) because
# storage errors are almost always infra-level and shouldn't be retried aggressively.

pinecone_breaker = CircuitBreaker(name="pinecone", failure_threshold=5, recovery_timeout=30.0)
gemini_breaker   = CircuitBreaker(name="gemini",   failure_threshold=5, recovery_timeout=60.0)
s3_breaker       = CircuitBreaker(name="s3",       failure_threshold=3, recovery_timeout=20.0)
