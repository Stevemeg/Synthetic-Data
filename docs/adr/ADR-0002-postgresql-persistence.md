# ADR-0002-postgresql-persistence: PostgreSQL persistence

## Status

Accepted and implemented in Phase 2.

## Context

Project, dataset, queue and artifact state must survive process restarts. Claim concurrency and idempotency require durable transactions and constraints.

## Decision

Use PostgreSQL 16, SQLAlchemy 2.x and explicit repositories. Alembic creates schema, foreign keys, checks, indexes and procedural guards. Store bytes in the artifact layer, not database columns.

## Alternatives considered

SQLite default; JSON files; a separate document database.

## Consequences

Local development needs Docker/PostgreSQL. Integration tests use real PostgreSQL isolated schemas. One database holds queue and domain state, without pretending file writes join DB transactions. Backups must coordinate metadata and bytes.
