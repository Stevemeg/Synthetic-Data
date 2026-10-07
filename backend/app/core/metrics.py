"""Bounded operational labels; no identities, project names or dataset values."""

from prometheus_client import Counter, Histogram

HTTP_REQUESTS = Counter(
    "medsynth_http_requests_total", "HTTP requests", ["route", "method", "status"]
)
HTTP_LATENCY = Histogram("medsynth_http_seconds", "HTTP duration", ["route", "method"])
STORAGE_LATENCY = Histogram(
    "medsynth_storage_seconds", "Storage duration", ["operation", "backend"]
)
STORAGE_FAILURES = Counter(
    "medsynth_storage_failures_total", "Storage failures", ["operation", "backend"]
)
JOB_CLAIMS = Counter("medsynth_worker_claims_total", "Owned work items claimed")
JOB_RETRIES = Counter("medsynth_worker_retries_total", "Claimed attempts after the first")
JOB_TIMEOUTS = Counter("medsynth_worker_timeouts_total", "Execution timeouts")
JOB_DURATION = Histogram(
    "medsynth_worker_execution_seconds",
    "Execution duration",
    ["kind"],
    buckets=(1, 5, 15, 30, 60, 120, 300, 600, 1800),
)
