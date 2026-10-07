# API

## Phase 5 additions

Workspace routes use bounded `limit`/`offset` pages and existing request-ID errors. They never return source rows or storage keys.

| Route | Purpose |
| --- | --- |
| `GET /api/v1/workspace/projects` | Grouped counts, latest activity and decision |
| `GET /api/v1/workspace/projects/{id}/summary` | Project dashboard |
| `GET /api/v1/workspace/datasets?project_id=` | Dataset inventory |
| `GET /api/v1/workspace/runs` | Generation inventory with project/dataset/status/engine filters and date sort |
| `GET /api/v1/workspace/evaluations?project_id=` | Evaluation inventory with batched job reads |
| `GET /api/v1/workspace/reports?project_id=` | Governance report inventory |
| `GET /api/v1/workspace/activity?project_id=&entity_id=` | Event identity/time/actor without diagnostic metadata |
| `GET /api/v1/workspace/projects/{id}/policy-usage` | Aggregated immutable version usage |
| `PUT /api/v1/datasets/{id}/tabular/governance` | Validate/save `{overrides: {column: ColumnOverride}}` |
| `POST /api/v1/evaluations/{id}/governance-report` | Create/reuse persisted HTML artifact (201); incomplete 409 |

Saved governance affects subsequent review, not existing run snapshots. Reports use the established artifact-ID download and size/hash verification. No public static report URL or model-download relaxation exists. See REPORTING.md. Authentication/tenant authorization remains absent.

FastAPI generates /docs and /openapi.json. Request/response models are typed. Pages return items, total, limit and offset; default limit 50, maximum 100. IDs are UUIDs.

| Method | Path | Behavior |
| --- | --- | --- |
| GET | /health | Process alive |
| GET | /ready | Migrated PostgreSQL and writable storage; 503 on failure |
| GET | /api/v1/capabilities | Maturity, availability and limits |
| POST, GET | /api/v1/projects | Create / paginated list |
| GET, PATCH | /api/v1/projects/{project_id} | Retrieve / update name, description, status |
| POST, GET | /api/v1/projects/{project_id}/datasets | Register multipart CSV / list |
| GET | /api/v1/datasets/{dataset_id} | Structural metadata and SHA-256 |
| POST, GET | /api/v1/projects/{project_id}/jobs | Queue / list |
| GET | /api/v1/jobs/{job_id} | Durable status, counts, timings, safe errors |
| POST | /api/v1/jobs/{job_id}/cancel | Pending/queued only |
| POST | /api/v1/jobs/{job_id}/retry | Retryable failure within budget |
| GET | /api/v1/jobs/{job_id}/artifacts | Paginated artifacts |
| GET | /api/v1/artifacts/{artifact_id} | Metadata without storage key |
| GET | /api/v1/artifacts/{artifact_id}/download | Integrity-checked stream; checkpoints restricted |

Create project: `{"name":"Local research","description":"Authorized local work"}`.

Registration fields: name, modality (timeseries/tabular), file (CSV). ECG is headerless numeric samples plus ignored final label; tabular CSV has a header. Metadata contains columns/dtypes/counts, never patient-row previews.

ECG job: `{"modality":"timeseries","dataset_id":"<UUID>","requested_samples":2,"random_seed":42}`.

Imaging job: `{"modality":"imaging","imaging_modality":"MRI","requested_samples":2,"random_seed":42}`. MRI/X-Ray/Skin are supported only in an explicitly enabled non-production lab. No source conditioning. Genomic jobs return ENGINE_NOT_AVAILABLE (501).

Job POST returns 202 immediately after durable queueing. Idempotency-Key is an optional safe 1-128-character ASCII project-scoped key; equivalent replay returns 200/the same job, conflicting payload returns IDEMPOTENCY_CONFLICT (409). Without a key each submission is independent.

## Errors and correlation

```json
{"error":{"code":"DATASET_NOT_FOUND","message":"Dataset does not exist","request_id":"..."}}
```

X-Request-ID accepts safe 1-64 ASCII characters or is generated. Errors, response headers and logs include it. Validation uses REQUEST_VALIDATION_FAILED (422) without echoing input values. Database failures are 503; unexpected errors are INTERNAL_ERROR (500). Other stable domain codes include PROJECT_NOT_FOUND, JOB_NOT_FOUND, ARTIFACT_NOT_FOUND, DATASET_MISMATCH, CANCELLATION_UNSUPPORTED, RETRY_NOT_ALLOWED, ARTIFACT_UNAVAILABLE and ARTIFACT_INTEGRITY_FAILED.

Public responses omit storage keys. Checkpoints are downloadable=false and return ARTIFACT_DOWNLOAD_RESTRICTED (403). Sources have no download endpoint. Audit actors include authenticated user UUIDs and organization/request context; system/worker remain machine actors, and development bypass remains an unauthenticated placeholder. CORS is not authorization.

## Tabular API extension

POST /api/v1/datasets/{dataset_id}/tabular/preflight verifies integrity and returns
compatible, row_count, column_count, columns and warnings without rows/category lists.

Submit through the existing project job endpoint (202, no training inside HTTP):

```json
{
  "modality":"tabular", "dataset_id":"<UUID>", "engine":"gaussian_copula",
  "requested_samples":1000, "random_seed":42,
  "configuration":{"holdout_fraction":0.2,"split_seed":42},
  "metadata_overrides":{"patient_id":{"role":"IDENTIFIER","identifier_strategy":"synthetic_sequence"}},
  "validation_rules":{"age":{"numeric_min":0,"numeric_max":120}}
}
```

Engine may be omitted for Gaussian Copula. CTGAN/TVAE are opt-in Beta; configuration
supports bounded epochs, batch_size, embedding_dim, generator_dim,
discriminator_dim and cuda. See TABULAR_SYNTHESIS.md for defaults/limits,
TABULAR_METADATA.md for overrides and TABULAR_VALIDATION.md for rules/errors.
Capabilities retain the existing capabilities map and add tabular engines (name,
maturity, actual SDV version). Unsupported runtime versions are not advertised.
SYNTHESIS_MODEL downloads are restricted; no model upload/reuse API exists.

## Phase 4 evaluation and policies

Capabilities now include a Beta evaluation section with supported SDMetrics/
sklearn versions and BASIC/STANDARD/FULL profiles.

- `POST /api/v1/generation-jobs/{job_id}/evaluations`: 202, separate queued evaluation.
- `GET /api/v1/evaluations/{id}`: configuration, persistent lifecycle, attempts, sanitized error and result summary.
- `GET /api/v1/projects/{id}/evaluations`: project evaluation list.
- `GET /api/v1/evaluations/{id}/reports`: report artifact references.
- `POST /api/v1/projects/{id}/evaluations/compare`: 2?10 successful compatible evaluation IDs, separate result rows in request order. Incompatible inputs/policy/configuration return domain error.
- `POST /api/v1/projects/{id}/release-policies`: 201, explicit immutable name/version/rules; duplicate version 409.
- `GET /api/v1/projects/{id}/release-policies` and `GET /api/v1/release-policies/{id}`: immutable policy identities, hashes and definitions.

Example evaluation (no implicit release policy):

```json
{"profile":"FULL","random_seed":42,"group_key":"patient_id","privacy":{"known_columns":["age","sex"],"sensitive_columns":["diagnosis_group"],"continuous_columns":["age"],"num_discrete_bins":10,"estimated":false},"utility":{"task":"BINARY_CLASSIFICATION","target":"readmitted"}}
```

Optional release_policy_id selects a same-project immutable policy. No policy
means NOT_EVALUATED. Configuration rejects absent/non-modelled attack/target
columns, overlapping known/sensitive sets, incompatible tasks and excluded group
keys. Explicit group_key and independent_rows are mutually exclusive. BASIC/
STANDARD cannot request FULL-only computation. No expensive evaluation runs in
handlers. Source/synthetic/manifest integrity must pass before queue submission
and worker computation; stable EVALUATION_* and UTILITY_* errors use the existing
sanitary domain error envelope. Timeout is EVALUATION_TIMEOUT; permanent invalid
inputs do not retry.

PASS means only satisfaction of the configured policy version, not anonymity,
legal/clinical/regulatory approval. Reports are sensitive internal artifacts
accessed through existing artifact IDs and checksum-protected downloads. No raw
records, filesystem paths or uploaded serialized models are exposed.

## Phase 6 security and operations

See [authentication](AUTHENTICATION.md), [authorization](AUTHORIZATION.md),
[tenancy](TENANCY.md), [storage](STORAGE.md), [data lifecycle](DATA_LIFECYCLE.md)
and [actual verification](PHASE_6_VERIFICATION.md). Protected API resources require
a revocable application session and selected organization membership. Mutations
require X-CSRF-Token and an allowed Origin; X-Organization-ID selects a membership.
Unauthorized foreign resources return 404; role denial returns 403; no session
returns 401. Reports remain private and HTML-escaped. Existing trained-model
download restrictions remain. Production startup rejects insecure defaults.

### Identity/lifecycle endpoints

- GET /api/v1/auth/login; GET /api/v1/auth/callback: OIDC authorization.
- GET /api/v1/auth/me: current verified identity, memberships, CSRF token.
- POST /api/v1/auth/logout: CSRF-protected application session revocation.
- GET /api/v1/organization/members: OWNER's selected organization only.
- PATCH /api/v1/organization/members/{id}: OWNER role/status change, last owner protected.
- POST /api/v1/projects/{id}/deletion: OWNER + exact-name confirmation; 202 background purge.
- GET /api/v1/version: version, commit and build timestamp (no secrets).
- GET /internal/metrics: private operational token only, not browser membership.
