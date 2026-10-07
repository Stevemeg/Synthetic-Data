# ADR-0005-job-state-machine: Job state machine

## Status

Accepted and implemented in Phase 2.

## Context

Free-form status updates can make a failed or cancelled job appear successful. Retries need finite attempts and an auditable transition history.

## Decision

Use PENDING, QUEUED, RUNNING, SUCCEEDED, FAILED and CANCELLED with an explicit transition graph. PostgreSQL triggers enforce it in addition to Python validation. Retry requires a retryable flag and remaining budget; success requires exact count and artifact records.

## Alternatives considered

Unvalidated strings; derive state only from timestamps; create a new job record for every retry.

## Consequences

SUCCEEDED/CANCELLED are terminal. Retries keep job identity but change claim token and increment attempts on claim. Cancellation supports pending/queued work only. Audit actors are explicit unauthenticated placeholders. Immutable audit triggers prevent ordinary update/delete but are not cryptographic tamper evidence.
