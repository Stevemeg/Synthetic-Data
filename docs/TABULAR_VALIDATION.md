# Structural validation and diagnostics

Validation checks requested vs produced count; exact expected columns/order;
absence of excluded fields and accidental pandas index columns; required non-null
columns; configured uniqueness (including all synthetic identifiers); finite
numeric values; parseable datetimes; boolean/categorical/numeric structural types;
and explicit rule violations. It persists objective PASS/failure facts, missing
and unexpected column names, dtype mismatch names, nullability/collision counts,
and per-rule violation counts. No offending patient/generated rows are included.

Every successful tabular run has a STRUCTURAL_VALIDATION_REPORT artifact and the
same report in its manifest. A failed required check produces
TABULAR_STRUCTURAL_VALIDATION_FAILED, is non-retryable and cannot publish a
successful artifact set. Failed validation retains a row-free structural report
in job metadata for diagnosis, without successful output artifacts. Rules validate model output; the platform does not
silently clamp, relabel, copy source rows or retry sampling until it looks valid.

Declarative rules: `non_null`, `numeric_min`, `numeric_max`, `allowed_values`,
`regex`, `unique`. Bounds are finite, min<=max, allowed_values has 1–100 explicit
scalar values, and patterns are limited to literals and bounded character classes
(e.g. `SYN-[0-9]{6}`); arbitrary regex operators/backtracking are rejected.
Range/category/pattern rules check non-null values; use non_null for requiredness.
User-provided allowed values are configuration, not inferred patient vocabularies.

```json
{"age":{"numeric_min":0,"numeric_max":120},"sex":{"allowed_values":["M","F","Other"]}}
```

These are user constraints, not clinical guidance. No automatic heart-rate,
blood-pressure or other purported medical truths are inferred.

`exact_row_diagnostic` counts generated rows whose **complete tuple of modelled
columns** exactly equals a training tuple after common typed preparation. Nulls
compare equal, no numerical tolerance is used, duplicate generated matches each
count, and identifiers/excluded columns and holdout records are not compared.
It records `exact_matching_generated_rows`, `exact_match_fraction`, comparison
definition and interpretation. Matches trigger a warning. Zero matches does not
establish privacy, and a match alone does not establish disclosure. This is not a
privacy score, re-identification test, compliance test or guarantee.

Schema drift is a validity diagnostic (missing/unexpected columns, types,
nullability, identifiers, rules). It does not measure statistical similarity,
clinical validity or downstream utility. Phase 4 provides separate statistical,
privacy-diagnostic and task-utility reports; see EVALUATION.md. Structural
validation remains its own dimension and never substitutes for that evidence.

Stable errors include TABULAR_DATASET_INVALID, TABULAR_METADATA_INVALID,
TABULAR_UNSUPPORTED_COLUMN, TABULAR_NO_MODELLED_COLUMNS,
TABULAR_ENGINE_NOT_AVAILABLE, TABULAR_CONFIG_INVALID, TABULAR_DATASET_TOO_LARGE,
TABULAR_GENERATION_LIMIT_EXCEEDED, TABULAR_TRAINING_LIMIT_EXCEEDED,
TABULAR_TRAINING_FAILED, TABULAR_TRAINING_TIMEOUT, TABULAR_SAMPLING_FAILED,
TABULAR_STRUCTURAL_VALIDATION_FAILED, TABULAR_MODEL_INTEGRITY_FAILED, and
SOURCE_ARTIFACT_INTEGRITY_FAILED. Pydantic shape/bound failures retain the Phase 2
REQUEST_VALIDATION_FAILED error. Authored safe messages omit values, paths and
library exception text. Malformed input is permanent; transient storage/DB
failures use the existing bounded retry policy.
