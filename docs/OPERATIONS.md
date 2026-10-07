# Operations

`/health` is API liveness. `/ready` checks the exact migrated database head and required storage readiness, without requiring a worker to be alive. Inspect worker process/container state and structured `worker_started`, `job_claimed`, execution and failure logs separately. An API can be ready while work is queued awaiting a worker.

The PostgreSQL queue retains SKIP LOCKED claims, ownership advisory locks, leases, claim tokens, heartbeats, timeouts and fenced completion. Restarting API processes does not lose registered resources/jobs. Restarting a worker releases its process connection; stale ownership is recovered under the established lock/lease rules. Do not manually mark a job succeeded or insert unverified publication records.

Production JSON logs correlate request IDs and authenticated user/organization UUIDs. Worker logs correlate job/project/organization IDs and attempts. `/internal/metrics` requires `Authorization: Bearer <METRICS_TOKEN>` and must be reachable only by an internal collector. HTTP labels use route templates/method/status; queue labels use bounded states. No dataset values, names, emails or arbitrary IDs are metric labels. Each process has its own execution counters; set WORKER_METRICS_PORT and collect each worker /metrics separately with the same internal bearer-token requirement. No worker port is published by Compose. OpenTelemetry tracing is deferred.

API and worker pools each default to five connections with five overflow, pre-ping, short connection/statement/lock timeouts. Budget their combined maxima against database capacity. Avoid adding large replicas without reducing per-process pools. Cold ML imports occur before submission transactions.

For database/migration failure: stop rollout, retain current application version, inspect sanitized failure codes, restore/repair using a verified backup. Migrations run once as an operator task, never automatically from every API/worker container. Identity/lifecycle downgrade is deliberately refused once data exists.

Storage publication failures retain the established compensation/fencing rules. Inspect orphan-reconciliation events; compare registered keys/hashes before deleting unreferenced objects. Existing local reconciliation is for LocalArtifactStore only. S3 reconciliation needs an explicit administrative inventory/review; do not run a local filesystem reconciliation command against S3 and claim it reconciled objects.

IdP outage blocks new sign-in; existing unexpired application sessions can continue until expiry or revocation. Rotate signing secrets to invalidate temporary login state, invalidate database application sessions for incident response, and rotate provider/store/database credentials through the deployment secret mechanism. Never print credentials to diagnose startup.

Deletion purges retry on subsequent worker polls; `PURGING` is not a claim of successful cleanup. See [lifecycle](DATA_LIFECYCLE.md), [backup/restore](BACKUP_RESTORE.md) and [storage](STORAGE.md). TLS, maintained provider services, host monitoring and backup/version deletion are infrastructure responsibilities.

For local fixture verification after real browser work, run `python -m backend.scripts.verify_operations`. It reads the metrics credential inside each container, checks positive request/storage/worker signals, counts safe correlated log records and checks that configured secrets are absent. It never prints those credentials. Actual results are recorded in Phase 6 verification.
