"""Prometheus metrics collector & exporter for Kubernetes horizontal pod autoscaling & dashboards."""
import time
from typing import Dict, Optional, Tuple

try:
    from prometheus_client import (
        Counter,
        Gauge,
        Histogram,
        REGISTRY,
        generate_latest,
        CONTENT_TYPE_LATEST,
    )
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False


if HAS_PROMETHEUS:
    HTTP_REQUESTS_TOTAL = Counter(
        "fandom_http_requests_total",
        "Total HTTP request count",
        ["method", "endpoint", "status"],
    )

    HTTP_REQUEST_DURATION = Histogram(
        "fandom_http_request_duration_seconds",
        "HTTP request latency in seconds",
        ["method", "endpoint"],
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    )

    COMMENTS_INGESTED_TOTAL = Counter(
        "fandom_comments_ingested_total",
        "Total fan comments ingested",
        ["platform", "title"],
    )

    BACKLASH_EPISODES_ACTIVE = Gauge(
        "fandom_backlash_episodes_active",
        "Active backlash crisis episodes currently detected",
        ["title", "severity"],
    )

    SENTIMENT_SCORE = Gauge(
        "fandom_net_sentiment_score",
        "Current net sentiment score (-1.0 to 1.0)",
        ["title"],
    )

    ML_INFERENCE_LATENCY = Histogram(
        "fandom_ml_inference_duration_seconds",
        "ML inference execution time in seconds",
        ["component"],
        buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0),
    )
else:
    # Minimal fallback metrics tracker
    class DummyMetric:
        def inc(self, *a, **k): pass
        def set(self, *a, **k): pass
        def observe(self, *a, **k): pass
        def labels(self, *a, **k): return self

    HTTP_REQUESTS_TOTAL = DummyMetric()
    HTTP_REQUEST_DURATION = DummyMetric()
    COMMENTS_INGESTED_TOTAL = DummyMetric()
    BACKLASH_EPISODES_ACTIVE = DummyMetric()
    SENTIMENT_SCORE = DummyMetric()
    ML_INFERENCE_LATENCY = DummyMetric()


def export_metrics() -> Tuple[bytes, str]:
    """Generates Prometheus scrape body and content type."""
    if HAS_PROMETHEUS:
        return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
    body = (
        b"# HELP fandom_http_requests_total Total HTTP request count (stub)\n"
        b"# TYPE fandom_http_requests_total counter\n"
        b"fandom_http_requests_total 0\n"
    )
    return body, "text/plain; version=0.0.4; charset=utf-8"
