"""
Prometheus metric objects — defined once as module-level singletons.

Import these into middleware to record values; import generate_latest + CONTENT_TYPE_LATEST
into main.py to expose /metrics.

Three metrics:
  - REQUEST_COUNT      Counter   — total requests, labelled by method/path/status
  - REQUEST_LATENCY    Histogram — seconds per request, labelled by method/path
  - REQUESTS_IN_FLIGHT Gauge     — how many requests are currently being processed
"""

from prometheus_client import Counter, Gauge, Histogram

REQUEST_COUNT = Counter(
    name="http_requests_total",
    documentation="Total HTTP requests received.",
    labelnames=["method", "path", "status_code"],
)

# Buckets cover fast API responses through slow AI calls (quiz generation can take ~5s).
REQUEST_LATENCY = Histogram(
    name="http_request_duration_seconds",
    documentation="HTTP request latency in seconds.",
    labelnames=["method", "path"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

REQUESTS_IN_FLIGHT = Gauge(
    name="http_requests_in_progress",
    documentation="Number of HTTP requests currently being processed.",
    labelnames=["method", "path"],
)
