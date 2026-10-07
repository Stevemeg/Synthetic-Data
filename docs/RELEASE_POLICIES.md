# Versioned release policies

Policies are named, project-scoped, versioned, canonical-SHA-256-hashed and
immutable from creation, including database UPDATE/DELETE protection. A new
version is a new row; no mutation endpoint exists. Evaluation snapshots the
identity, full rules and hash and verifies it again before application.

There is **no production default policy** and no weighted score. Users supply
explicit project-specific rules. `illustrative=true` labels demo thresholds as
engineering choices, not scientific, medical, legal or regulatory standards.
The smoke demo's numerical thresholds are permissive illustrations to exercise
rule handling, not advice for releasing healthcare data.

Supported metric keys: structural_validation, training_column_shapes,
training_column_pair_trends, holdout_column_shapes, holdout_column_pair_trends,
exact_training_match_fraction, dcr_baseline_protection, dcr_overfitting_protection,
dcr_overfitting_gating_eligible, disclosure_protection, tstr_trtr_ratio and
group_leakage_free. Numerical rules supply minimum/maximum; boolean rules supply
equals. All thresholds must be explicit, finite and type compatible. Rules can
be required/optional and conditional on DISCLOSURE_CONFIGURED or UTILITY_CONFIGURED.

Each rule records metric value, applicability, threshold, required status,
PASS/FAIL/NOT_APPLICABLE/INSUFFICIENT_DATA/ERROR and reason. Advisory results are
INSUFFICIENT_DATA for gating. Unavailable values never pass.

| Condition | Decision |
| --- | --- |
| No selected policy | NOT_EVALUATED |
| Any applicable threshold violation, including optional rule | FAIL |
| Required metric unavailable/advisory/error, or no passing rules | REVIEW_REQUIRED |
| All required rules pass, at least one rule passes, no violation | PASS |

Optional unavailable evidence remains visibly unavailable but does not block
passing required rules. Explicit boolean eligibility=false may fail an equals=true
rule; a required advisory numeric DCR score normally requires review instead.

**PASS means only that the artifact satisfied the configured MedSynth Guard
policy version. It does not mean anonymity, zero privacy risk, medical validity
or regulatory approval.** A successful evaluation can have FAIL or REVIEW_REQUIRED
as its release decision: computation success and policy compliance are separate.
RELEASE_DECISION JSON makes all rules/reasons auditable. Reports remain sensitive
internal artifacts; no automatic public release or dataset approval platform exists.
