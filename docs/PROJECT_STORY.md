# MedSynth Guard: engineering story

## Problem

Healthcare data/ML teams need reproducible experimentation without confusing synthetic generation with evidence that data may be released. Source access, metadata decisions, model fitting, holdout evaluation, policy decisions and artifact handling need a coherent traceable workflow.

## Why synthetic health data

Synthetic cohorts support engineering experiments and controlled methodological research. They do not automatically anonymize source data, validate clinical conclusions or remove re-identification risk. This project measures separate evidence dimensions and makes configured operational criteria visible.

## Initial limitations and evolution

The original forms/scripts evolved into persistent project/dataset/job resources, PostgreSQL-backed execution, registered artifacts and bounded source parsing. Later phases introduced single-table Gaussian Copula, CTGAN and TVAE synthesis, schema governance, structural validation, train/holdout fidelity, privacy diagnostics, TRTR/TSTR utility and immutable policy versions. Phase 5 added a routed governed workspace, persisted-evidence HTML reports and generated fake-data demos.

## Security and reliability

Phase 6 adds standards-based OIDC sessions, organization membership, tenant-scoped query authorization, private S3-compatible storage and background object deletion. Existing claim locks/leases/tokens and fenced publication remain. Integrity uses independently recorded SHA-256, not object-store ETag. Authenticated and machine actors are distinguished in an append-only application audit trail.

## Testing and trade-offs

Evidence includes unit/model/PostgreSQL tests, real worker smoke workflows, Chromium UI/visual/accessibility tests, issuer/subject sessions, cross-tenant UUID swapping, real local OIDC, S3 conformance and backup/restore rehearsal. Exact current counts and outstanding gates belong in PHASE_6_VERIFICATION.md, rather than a marketing claim.

The architecture keeps one API, one PostgreSQL queue and worker processes. Request scoping is implemented without untested RLS. HTML reports avoid browser rendering infrastructure. Manual retention avoids surprising deletion. MinIO is a local test fixture; maintained storage, TLS, encryption/backups, IdP administration and operational policy remain deployment responsibilities.

## Current limitations

No formal regulatory certification, differential privacy, clinical validation, free-text synthesis, multi-table synthesis or automated best-model ranking. ECG remains Beta, imaging Experimental, genomics unavailable. Thresholds are organization-defined. The local IdP differs from a deployed provider; physical storage erasure and backups require provider/operator controls. Release-candidate status depends on the documented acceptance results.
