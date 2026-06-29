"""
CorrelationIDMiddleware

For every inbound request:
  1. Read X-Correlation-ID header (set by an upstream gateway/load balancer) or generate a fresh UUID.
  2. Store it in the correlation_id ContextVar — all log calls within this request's async
     context will automatically pick it up via the JSONFormatter.
  3. Echo it back in the response header so clients/gateways can trace end-to-end.
"""

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import correlation_id
from app.core.metrics import REQUEST_COUNT, REQUEST_LATENCY, REQUESTS_IN_FLIGHT

logger = logging.getLogger(__name__)


def _route_path(request: Request) -> str:
    """
    Return the matched route template (e.g. '/documents/{doc_id}') rather than
    the real URL path ('/documents/42'). This prevents cardinality explosion —
    without this, every unique ID becomes a separate Prometheus time series.
    Falls back to the raw path for unmatched routes (404s, /metrics, /health).
    """
    route = request.scope.get("route")
    return route.path if route else request.url.path


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        req_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())

        # Set the ContextVar for this async context — all downstream code inherits it.
        token = correlation_id.set(req_id)

        method = request.method
        # Path isn't template-resolved yet (route matching happens inside call_next),
        # so we read it after the response returns.
        start = time.perf_counter()
        response: Response | None = None
        try:
            response = await call_next(request)
        finally:
            duration_s = time.perf_counter() - start
            path = _route_path(request)
            status_code = response.status_code if response is not None else 500

            REQUEST_COUNT.labels(method=method, path=path, status_code=status_code).inc()
            REQUEST_LATENCY.labels(method=method, path=path).observe(duration_s)

            logger.info(
                "request completed",
                extra={
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": round(duration_s * 1000, 1),
                },
            )
            correlation_id.reset(token)

        if response is None:
            response = Response("Internal Server Error", status_code=500)

        response.headers["X-Correlation-ID"] = req_id
        return response
