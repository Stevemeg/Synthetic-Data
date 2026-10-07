# ADR-0001-fastapi: FastAPI HTTP boundary

## Status

Accepted and implemented in Phase 2.

## Context

Flask supported the Phase 1 in-process prototype. Persistent resources need typed requests, response schemas, dependency lifecycles and generated API documentation.

## Decision

FastAPI is the single HTTP runtime, with Pydantic v2 schemas, lifespan-managed dependencies, and thin routes delegating to services. Existing generation dataclasses and offline CLIs stay compatible.

## Alternatives considered

Keep Flask with manual schema/OpenAPI tooling; run both frameworks; migrate ML code into routes.

## Consequences

The old synchronous generation/download endpoints break deliberately. Frontend/tests migrate to resources. FastAPI adds dependencies, but generated contracts replace separate manual API specifications. No asynchronous job work runs inside HTTP.
