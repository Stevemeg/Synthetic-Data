# Artifact and provenance model

## Phase 5 governance artifacts

`GOVERNANCE_REPORT` is self-contained escaped HTML from persisted completed evaluation data. It is registered to the evaluation execution job with content type, size, SHA-256, evaluation ID, policy version/hash and creation time. It is a sensitive internal artifact, downloaded through the existing artifact-ID integrity boundary without a public static URL. Filename sanitization applies to report identity and every HTTP download. Learned model artifacts remain restricted. Creation is idempotent and does not read source rows or recompute metrics. See REPORTING.md and ADR-0013.

PostgreSQL stores metadata, UUIDs, foreign keys, private storage keys, sizes and SHA-256. Source/output bytes and patient rows are not stored in metadata.

ArtifactStore exposes put/get/delete/exists/metadata. LocalArtifactStore is the only implementation; S3/MinIO are deferred. Keys use generated IDs rather than unsafe filenames. The store rejects absolute/ambiguous/traversing keys and symlink escapes; immutable put refuses overwrite.

```text
projects/<project-id>/datasets/<dataset-id>/source.csv
projects/<project-id>/jobs/<job-id>/attempts/<claim-token>/<artifact-id>/<filename>
```

Public identifiers are UUIDs, never paths. Types implemented:
- SYNTHETIC_DATASET: ECG dataset.npz.
- IMAGE_ARCHIVE: ZIP containing every requested PNG.
- MODEL_CHECKPOINT: full ECG vae.pt, HTTP download restricted.
- RUN_METADATA: run_manifest.json.

No fake evaluation reports or log-summary artifacts exist.

Phase 3 adds SYNTHESIS_MODEL (trusted fitted SDV model; HTTP download restricted)
and STRUCTURAL_VALIDATION_REPORT (objective schema/count/rule checks). Tabular
SYNTHETIC_DATASET is dataset.csv with stable reviewed column order and no pandas
index: modelled samples and new synthetic identifiers only, no excluded text.
All four artifacts including RUN_METADATA publish in the existing fenced success
transaction after immutable byte writes. Source/holdout partitions have no new
download route. There is no arbitrary model upload/deserialization endpoint.

## Manifest fields

manifest_version, job_id, project_id, dataset_id, source_dataset_sha256, modality, maturity, engine_name, engine_version, model identifier/SHA-256, configuration, random_seed, requested_count, produced_count, started_at, finished_at, attempt_count, application_version, optional application_commit, runtime_versions, source_schema_summary, warnings, and output artifact IDs/types/filenames/hashes/sizes.

ECG identifies the newly trained full checkpoint. Imaging hashes the exact loaded bytes. The manifest does not recursively hash itself; its database artifact record supplies that hash. APP_COMMIT can specify a verified build commit; otherwise Phase 3 records the locally available Git HEAD and a dirty-worktree flag (null if Git is unavailable). Original checkpoint training provenance/licensing is not invented.

## Publication and maintenance

Bytes precede a single success transaction inserting all artifacts, job metadata/status and audit. Failure compensation deletes only confirmed unreferenced bytes after a fresh DB check. Uncertain commit outcomes retain bytes and log reconciliation; known committed success retains its objects. Crash orphans are possible.

The reconciliation script is a count-only dry run by default, considering objects older than 24 hours. Stop API/workers before --apply. Organization manual retention and owner-requested background project deletion are implemented. Secure physical erasure, automatic expiry and backup orchestration are outside application guarantees.

Downloads require a registered record and valid storage key; stored hash/size are verified before streaming. Missing/changed bytes return sanitized 503. Storage root must be operator-controlled; privileged filesystem changes are outside these controls.

Sources have no API download route. Learned checkpoint/model downloads remain restricted, including for OWNER. Other downloads require active authenticated organization membership and are audited before returning SHA-256 verified attachments. No public reports are published.

Scientific settings and engine input/output limits are snapshotted at submission, including heartbeat segment cap, sampling rate, epochs and count limits. A worker restart with different settings does not silently change these controls. Runtime package versions are recorded separately.

Tabular manifests record actual engine/library versions, restricted model ID/hash,
canonical application metadata version/hash/roles and overrides, training/sampling
configuration, source hash, split algorithm/version/seed/requested and realized
fractions/train and holdout counts, structural report, exact-row diagnostic,
source/training/holdout/generated counts, column counts, training/sampling/total
durations, device, warnings and synthetic artifact ID/hash. Model artifact metadata
includes engine/version, its hash, source hash, metadata hash, training config,
split/training count, creation timestamp and job ID. The manifest also includes
application version/optional APP_COMMIT, Python version, job/project/dataset IDs,
timestamps, requested/produced counts and artifact hashes. No raw source rows.
Exact overlap is not a privacy score.

## Phase 4 artifacts

QUALITY_REPORT, PRIVACY_REPORT, optional UTILITY_REPORT, RELEASE_DECISION and
EVALUATION_MANIFEST are UTF-8 JSON with strict finite-number serialization
(NaN becomes null plus applicability). They attach to the evaluation execution
work item, carry SHA-256/size and sensitive_internal metadata, and use existing
artifact-ID download/path/integrity protections. No public URL or pickle upload
exists. Reports contain aggregate source-derived statistics and are sensitive;
no patient records or matched source rows are included. No trained utility
classifier is retained.

The manifest includes input and report IDs/hashes, full configuration/limits,
original split/group semantics, library/application/Git versions, seeds, metrics/
applicability, policy identity/hash/rule reasons, timestamps and duration.
Success requires all artifacts plus summary committed under the valid claim
token. Failed publication compensates object writes; crash orphan reconciliation
remains the existing operator workflow. Artifact download remains unauthenticated
and must be restricted to local/internal use.

## Phase 6 security and operations

See [authentication](AUTHENTICATION.md), [authorization](AUTHORIZATION.md),
[tenancy](TENANCY.md), [storage](STORAGE.md), [data lifecycle](DATA_LIFECYCLE.md)
and [actual verification](PHASE_6_VERIFICATION.md). Protected API resources require
a revocable application session and selected organization membership. Mutations
require X-CSRF-Token and an allowed Origin; X-Organization-ID selects a membership.
Unauthorized foreign resources return 404; role denial returns 403; no session
returns 401. Reports remain private and HTML-escaped. Existing trained-model
download restrictions remain. Production startup rejects insecure defaults.
