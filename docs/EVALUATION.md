# Tabular evaluation — Beta

MedSynth Guard evaluates a successful Phase 3 tabular run without retraining it.
Structural validity, statistical fidelity, selected disclosure/overfitting diagnostics,
declared ML utility and policy compliance remain separate. There is no universal
synthetic-data score, automatic winner or unrestricted-sharing approval.

## Persistent execution

`EvaluationRun` references a generation job, immutable source dataset, synthetic
artifact, profile, configuration and optional policy snapshot. A linked
`GenerationJob` with `job_kind=EVALUATION` is its execution work item. Its lifecycle,
attempt count, errors, worker, token and lease are the authoritative execution
state exposed by evaluation responses. The evaluation is a separate domain;
generation lists filter out evaluation work items.

FastAPI validates the request and input integrity, then queues work. A worker
claims it through the existing SKIP LOCKED/advisory ownership mechanism. A
supervised child reconstructs inputs and computes reports. Parent publication
stores all bytes/hashes and commits artifacts, result summary and fenced success
in one database transaction. Filesystem compensation removes failed writes;
crash orphans use existing storage reconciliation. No evaluation model fits in
an HTTP handler. The work item's count of one denotes completed evaluation,
not a synthetic row count.

## Profiles

| Profile | Computation |
| --- | --- |
| BASIC | Structural revalidation, training/holdout fidelity, exact overlap |
| STANDARD | BASIC plus DCR baseline and overfitting where calculable |
| FULL | STANDARD plus explicitly configured disclosure and/or utility |

Profiles select computation, not thresholds. Inapplicable metrics remain
unavailable, never a fabricated zero or passing result. Results use APPLICABLE,
NOT_APPLICABLE, INSUFFICIENT_DATA, ADVISORY_ONLY or FAILED.

## Integrity and partitions

Source and synthetic SHA-256/size must match their database records. Generation
manifest SHA-256/size and its job/source/artifact/configuration/metadata/split
references must agree. Checks repeat before child computation. The original
`numpy-pcg64-positional-permutation` version `1` split is reconstructed using
source order, split seed and holdout fraction. Counts must equal provenance;
partition row positions must be disjoint and cover the source. Neither source
partition becomes a downloadable report.

Configure `group_key` explicitly to assess whether source entities span both
partitions, or explicitly declare independent rows. Non-excluded source columns,
including identifier columns, can be group keys; they are not metric features.
Missing group values are rejected. Group overlap produces
`EVALUATION_LEAKAGE_WARNING` and makes relevant disclosure/utility/DCR evidence
advisory. Undeclared entity semantics also prevents those gates. A row-split job
is never relabeled GROUP_SPLIT or retrospectively fixed: correction would require
new group-aware generation/training, outside this implementation.

## Artifacts and provenance

JSON QUALITY_REPORT, PRIVACY_REPORT, optional UTILITY_REPORT, RELEASE_DECISION
and EVALUATION_MANIFEST are sensitive internal artifacts. Use artifact IDs and
existing checksum/path-protected downloads. Reports contain aggregates, column
names and configurations, not source records or matching patient values. No
SDMetrics pickle upload/load endpoint exists.

The manifest records evaluation/execution/generation/project/dataset IDs;
source, synthetic and generation-manifest IDs/hashes/sizes; full request and
snapshotted limits; split algorithm/version/seed/fraction/counts; group assessment;
quality/privacy/utility outputs and applicability; policy identity/version/hash,
rules and reasons; library/Python/application versions and Git commit/dirty state;
seeds, warnings, start/finish/duration and report artifact IDs/hashes/sizes.

Comparison requires the same source descriptor, metadata hash, split semantics,
full request/profile/task/attack/group/seeds, limits and policy snapshot. It
preserves selection order and associates each engine with its own result. It
does not rank or select a winner.

## Runtime and limits

Install `backend/requirements-evaluation.txt`; it forwards the tabular/ML groups.
Verified direct versions are SDMetrics **0.32.0**, scikit-learn **1.9.1**, SDV
1.25.0, RDT 1.18.2 and CTGAN 0.11.1. Existing NumPy/Pandas/PyTorch pins are retained.
Evaluation capability is Beta and advertised only for the supported installed
SDMetrics/sklearn versions.

| Environment variable | Default | Hard configuration bound |
| --- | ---: | ---: |
| EVALUATION_TIMEOUT_SECONDS | 300 | 3600 |
| DCR_MAX_ROWS | 2000 | 5000 |
| DISCLOSURE_MAX_ROWS | 2000 | 5000 |
| DISCLOSURE_ESTIMATE_ROWS | 500 | 2000 |
| DISCLOSURE_ESTIMATE_ITERATIONS | 3 | 10 |
| QUALITY_SUBSAMPLE_ROWS | 2000 | 10000 |
| UTILITY_MAX_ROWS | 10000 | 100000 |
| UTILITY_MAX_ENCODED_CELLS | 2000000 | 10000000 |

These are operational boundaries, not scientific confidence guarantees. Quality
sampling is bounded and recorded; DCR retains complete training/holdout references
or declines calculation if they exceed limits. Disclosure estimation is opt-in.
Utility bounds row and estimated encoded-cell counts. Limits and timeout prevent
unbounded requests; this local platform does not enforce an OS memory quota.

Run `python -m backend.scripts.evaluation_smoke_test --start-services` for invented
data, genuine HTTP/API/worker execution, FULL reports, explicit illustrative policy,
hash verification and actual API restart. See [verification](PHASE_4_VERIFICATION.md).

OIDC and organization roles are implemented. Deployment requires reviewed
HTTPS and maintained providers; these controls do not establish clinical or regulatory validity. Evaluation reports
themselves reveal source-derived statistics and must not be published unrestricted.
