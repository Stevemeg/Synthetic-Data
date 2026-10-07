# Job lifecycle

States: PENDING, QUEUED, RUNNING, SUCCEEDED, FAILED, CANCELLED.

| From | To | Condition |
| --- | --- | --- |
| PENDING | QUEUED | Durable submission |
| PENDING | CANCELLED | Pending cancellation |
| QUEUED | RUNNING | Atomic claim, new token, increment attempt |
| QUEUED | CANCELLED | Cancellation before claim |
| RUNNING | SUCCEEDED | Exact count and artifact metadata commit |
| RUNNING | FAILED | Failure / recovered abandoned ownership |
| FAILED | QUEUED | Retryable flag and remaining budget |

SUCCEEDED/CANCELLED cannot restart. FAILED cannot directly succeed. Application validation and PostgreSQL triggers enforce the graph; database checks enforce counts/status/timestamps/ownership. Insertion starts at PENDING.

## Ownership

A short transaction selects eligible QUEUED or expired RUNNING work with FOR UPDATE SKIP LOCKED. A session advisory lock derived from UUID is retained on the same connection for the whole attempt. Another worker cannot own that job while this connection is alive, even after lease expiration. Lock hash collisions serialize unrelated jobs rather than permit duplicates.

Heartbeats update only matching RUNNING/token/worker ownership. Success locks the row and verifies the claim token. The spawned ML child has no DB connections, watches parent liveness and a shared monotonic deadline, and exits if supervision is lost. The parent terminates computation on heartbeat failure. Stale attempts cannot publish.

Concurrent claims and fenced publication are tested. A crash may cause later recomputation of abandoned work; no exactly-once computation across failures is claimed. Recovery needs database availability, shared storage and roughly synchronized wall clocks.

## Failure, retry and shutdown

Bad datasets/configuration, unsupported engines and missing/incompatible checkpoints are permanent failures. Transient storage/OSError and operational DB failures are retryable; unexpected errors are sanitized and non-retryable. Future remote storage requires more precise classification.

Retryable failures record RUNNING -> FAILED -> QUEUED with exponential available_at delay capped at 60 seconds, up to max_attempts (default three). Attempts increment on claim. Automatic retries already requeue ordinary transient failures; HTTP retry accepts only eligible retryable FAILED state within budget.

Recovery waits for expired lease and loss of the old ownership connection, records WORKER_LOST, and reclaims within budget. Exhausted work stays FAILED. An active ownership session is never stolen just because its lease expired.

Only pending/queued cancellation is supported. Running cancellation is rejected. Graceful worker shutdown stops new claims and finishes current work; forced OS termination uses recovery. Windows force termination may be abrupt.

Success writes bytes, then commits all artifact records, metadata, exact count, state and audit together. See ARTIFACT_MODEL for compensation. Preserve both PostgreSQL and local storage across restarts.

## Tabular job extension

Phase 3 uses this same path. TABULAR_JOB_TIMEOUT_SECONDS is snapshotted at
submission and supervised by the parent; timeout terminates the child, fails with
TABULAR_TRAINING_TIMEOUT and publishes no incomplete artifact set. Metadata,
source integrity and required structural failures are non-retryable. Training,
sampling and validation audits are received from actual child stages under current
claim ownership; model-created/succeeded events commit with all four artifacts.
No invented progress percentages are shown.

## Evaluation work items

GenerationJob.job_kind defaults to GENERATION; EVALUATION items execute an
EvaluationRun through the existing lifecycle. Status, claims, leases, timestamps,
attempts and errors derive from that persistent work item. No separate unsafe
queue exists. Completion count is one evaluation, not generated record count.
SKIP LOCKED, advisory ownership, token fencing, bounded retries and parent/child
supervision remain unchanged. Recovery cannot accept stale-token publication.

Stages are actual audit events: EVALUATION_SUBMITTED/STARTED,
QUALITY_EVALUATION_STARTED/COMPLETED, PRIVACY_EVALUATION_COMPLETED, configured
UTILITY_EVALUATION_COMPLETED, POLICY_EVALUATED, EVALUATION_SUCCEEDED/FAILED. No
percentage progress is invented and no row payloads are logged.

Evaluation timeout terminates the child and fails with EVALUATION_TIMEOUT.
Corrupt inputs/invalid configuration/target/classes are permanent; controlled
transient storage failures retry with a new fenced token. Policy FAIL or
REVIEW_REQUIRED does not mean computation FAILED: successful computation persists
its independent release decision. A deferred constraint requires all reports
and result summary before the execution item can commit SUCCEEDED.
