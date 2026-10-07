# ADR-0004-artifact-storage-abstraction: Artifact storage boundary

## Status

Accepted and implemented in Phase 2.

## Context

Outputs and source datasets must be addressed safely, survive restarts and carry integrity metadata. A later remote store should not require changing routes.

## Decision

Define a typed ArtifactStore interface and implement immutable local put/get/delete/exists/metadata. Generated UUID keys replace user-controlled paths. Persist hash/size/reference separately. Downloads validate records and bytes.

## Alternatives considered

Direct route filesystem access; database blobs; implement S3 immediately.

## Consequences

Only local storage is supported. File bytes precede DB commits; compensation deletes only confirmed unreferenced objects, retaining uncertain commits for reconciliation. Crash orphans require maintenance. Operator-controlled storage is required; no encryption/secure erasure is implied.
