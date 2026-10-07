# ADR-0019: Structured events and bounded internal metrics

Accepted, Phase 6. JSON application logs retain request/job/user/organization
identifiers, status and durations, excluding payloads, tokens and exception
text. Prometheus-compatible HTTP, storage and worker measurements use bounded
route/operation/status labels, never object keys, emails or dataset values.
API /internal/metrics and optional worker /metrics require a generated bearer
token and private network access. Worker metrics are collected separately;
the API does not pretend to aggregate another process's counters. PostgreSQL
job-state gauges expose actual queue counts. Health remains process liveness;
readiness checks migrated PostgreSQL and required storage, not worker presence.

Tracing and a hosted monitoring stack are deferred. These controls support
diagnosis; they do not constitute a security certification or availability SLA.
