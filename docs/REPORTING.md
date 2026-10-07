# Governance reports

Reports are portable HTML artifacts assembled from persisted completed evaluation evidence. They do not run metrics, train models, reconstruct source rows or render a browser inside the API. PDF generation is deferred.

`POST /api/v1/evaluations/{evaluation_id}/governance-report` verifies the persisted evaluation manifest and creates a report. The operation is idempotent under an evaluation row lock: subsequent calls return the registered artifact. Incomplete evaluations return 409. Integrity failure returns an explicit error. Creation is a small bounded synchronous operation; see ADR-0013. Artifact bytes are immutable and publication uses the existing storage/database compensation pattern. An uncertain commit retains bytes for reconciliation rather than deleting possibly committed data.

## Content

The report contains identity, executive summary, source dataset summary, generation configuration, reviewed schema governance, structural validation, separate training/holdout fidelity and per-column/pair evidence, separate privacy diagnostics with applicability and attack configuration, TRTR/TSTR utility, immutable policy/version/hash, every rule and decision rationale, provenance and warnings/limitations. Technical appendices include application/build/library versions, source and artifact hashes, IDs, split and timestamps. No filesystem paths or source rows are included. Technical configuration dictionaries are preserved in the appendix/evidence tables for reproducibility.

There is no composite score. A policy pass means the configured version was satisfied. Exact matches are one memorization signal; absence of matches does not prove anonymity. Advisory DCR cannot satisfy a required numerical rule. Disclosure evidence covers the selected attacker scenario. Utility measures the declared task and holdout, without clinical validation. Thresholds belong to the organization/project and are not universal medical, legal or privacy standards.

## Artifact and handling

The artifact type is `GOVERNANCE_REPORT`, content type `text/html; charset=utf-8`. Registered metadata stores evaluation ID, policy version/hash, sensitivity, creation time, byte size and SHA-256. It belongs to the evaluation execution job. Download only through `/api/v1/artifacts/{artifact_id}/download`, which checks registered size/hash and retains existing restricted-model behavior. No public static report URL or source preview endpoint is added. Download names use a sanitized `medsynth-guard_<project>_<evaluation>_governance-report.html` pattern.

All strings are HTML-escaped, including project/dataset/column names and policy reasons. The document has no scripts, remote resources or browser-dependent rendering and includes a restrictive Content Security Policy. Reports contain sensitive source-derived statistics and must remain internal. The artifact API enforces active organization membership before downloads. Artifact IDs are not authorization. Reports remain private; source/model restrictions and SHA-256 checks persist.

## Verification

Integration tests run a real completed Full evaluation, prohibit report-time metric execution, check sections and provenance, attempt HTML injection, check repeated creation, verify download size/hash and corrupted-byte rejection, and reject incomplete evaluations. Tests and the product smoke assert forbidden compliance/anonymity/privacy-guarantee claims are absent. The product smoke verifies persistence after actual API restart. Browser tests initiate artifact download; the opt-in live browser test verifies the downloaded bytes against registered metadata.

## Phase 6 security and operations

See [authentication](AUTHENTICATION.md), [authorization](AUTHORIZATION.md),
[tenancy](TENANCY.md), [storage](STORAGE.md), [data lifecycle](DATA_LIFECYCLE.md)
and [actual verification](PHASE_6_VERIFICATION.md). Protected API resources require
a revocable application session and selected organization membership. Mutations
require X-CSRF-Token and an allowed Origin; X-Organization-ID selects a membership.
Unauthorized foreign resources return 404; role denial returns 403; no session
returns 401. Reports remain private and HTML-escaped. Existing trained-model
download restrictions remain. Production startup rejects insecure defaults.
