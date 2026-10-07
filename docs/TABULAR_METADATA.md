# Tabular metadata and preflight

`POST /api/v1/datasets/{id}/tabular/preflight` verifies source integrity and returns
dataset ID/hash, row/column counts and structural facts per column: name, inferred
numerical/categorical/boolean/datetime/unsupported type, null percentage, unique
count, cardinality ratio, possible identifier/text, constant/all-null/high-cardinality
flags, suggested role and warnings. Profiles persist under the dataset metadata's
`tabular_profile` key with version=1. They contain no patient rows, examples, top
values, category vocabularies or arbitrary lists of source values. Names can still
be sensitive. Preflight compatibility is advisory; submission validates overrides.

CSV headers are checked before pandas parsing: unique, nonblank, <=128 characters,
rectangular records, bounded rows/columns, UTF-8, no empty table. Source filenames
are sanitized and storage keys remain generated/private. ISO-like datetimes and
true/false boolean strings are inferred conservatively; numeric 0/1 fields remain
numerical unless explicitly configured as boolean.

Application metadata version 1 defines each column's `name`, `role`,
`semantic_type`, `nullable`, `unique`, `inferred_type`, `sdv_type`,
`datetime_format`, `identifier_strategy`, `annotations`, and `warnings`.
It is a platform representation, not a raw SDV object. It is resolved before
queueing, hashed with SHA-256 over canonical sorted compact JSON, snapshotted
with user overrides, then revalidated in the worker. The adapter builds validated
SDV metadata from modelled training columns only.

| Role / annotation | Behavior |
| --- | --- |
| MODELLED | Included in the learned joint tabular model |
| IDENTIFIER | Original values excluded from fit; new SYN-000001 sequences |
| EXCLUDED | Removed from fitting and generated dataset |
| QUASI_IDENTIFIER | Persisted annotation for later governance; no special privacy algorithm |
| SENSITIVE_ATTRIBUTE | Persisted annotation for later governance; no special privacy algorithm |

Annotations can accompany roles. Identifier handling supports only
`synthetic_sequence`; identifiers must be unique, non-null and categorical.
Formatting of real identifiers is never copied. No government-identifier format
is synthesized. Sequence uniqueness is per artifact, not a global identity service. If source IDs
already contain a candidate SYN sequence value, that candidate is skipped. Source
IDs are used only for this collision check, never for fitting or formatting.

Name/content heuristics identify possible patient/member/MRN/email/phone/SSN
columns and possible notes/comments/discharge summary/address/free-text fields.
Identifier inference is advisory and can be overridden by an explicitly reviewed
role. Text is excluded by default and cannot be fed into SDV in Phase 3, even
through a MODELLED override. All-null, complex/nonfinite or unsupported columns
cannot be modelled; they can be excluded or replaced by synthetic identifiers.
High cardinality and constants produce warnings, not statistical evaluations.

Example submission overrides:

```json
{
  "age": {"semantic_type": "numerical", "role": "MODELLED", "annotations": ["QUASI_IDENTIFIER"]},
  "diagnosis_code": {"semantic_type": "categorical", "role": "MODELLED", "annotations": ["SENSITIVE_ATTRIBUTE"]},
  "patient_id": {"role": "IDENTIFIER", "identifier_strategy": "synthetic_sequence"},
  "notes": {"role": "EXCLUDED"}
}
```

Unknown columns, invalid roles/types/annotations, identifier contradictions,
datetime formatting on other types, numeric rules on non-numeric columns, rules
on excluded columns and zero modelled columns are rejected. Overrides cannot
make unparseable source values into valid numbers/booleans/datetimes. Metadata
uses type/nullability constraints, not inferred medical truths. Source categories
may be learned internally by the model; the profile does not expose their values.
