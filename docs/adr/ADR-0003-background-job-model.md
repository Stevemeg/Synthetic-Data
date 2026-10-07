# ADR-0003-background-job-model: PostgreSQL-backed worker

## Status

Accepted and implemented in Phase 2.

## Context

Generation can train models and must outlive HTTP requests. Multiple workers need safe ownership without duplicating owned execution.

## Decision

A dedicated process claims with FOR UPDATE SKIP LOCKED in a short transaction, retains a session advisory lock, renews a lease and fences completion with a UUID claim token. Computation runs in a supervised spawned child; it stops when parent/deadline supervision is lost.

## Alternatives considered

Redis queue library; Celery; in-process background tasks; plain status-check/update polling.

## Consequences

No Redis is needed. Each active worker reserves a DB connection and supervises a child. Recovery may recompute abandoned work but cannot publish with an old token. Lease expiry alone never steals a live session lock. Ownership depends on database availability; clocks should be synchronized.

## References

[PostgreSQL row and advisory locks](https://www.postgresql.org/docs/current/explicit-locking.html).
