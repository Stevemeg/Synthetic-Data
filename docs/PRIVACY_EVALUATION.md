# Selected privacy and disclosure diagnostics

These metrics measure selected statistical disclosure and overfitting risks.
They do not prove anonymity or regulatory compliance. No differential privacy
mechanism, epsilon/delta accounting, HIPAA de-identification or GDPR anonymization
is implemented. Results remain separate; there is no single privacy score.

## Exact overlap

Typed equality across modelled columns compares each generated row against
training rows, and separately against holdout. Nulls compare equal. Counts and
fractions are persisted, never matched source records. Identifiers/excluded
columns are absent from this comparison. Exact matches are one memorization
signal; zero matches do not establish privacy. Duplicate synthetic matches count
as generated rows, not unique matched training records.

## DCR baseline

Public `sdmetrics.single_table.DCRBaselineProtection.compute_breakdown` uses
modelled training/synthetic frames and translated table metadata. JSON preserves
score, synthetic median DCR, random-baseline median DCR, columns, sample sizes,
iterations and warnings. DCR_MAX_ROWS bounds complete training reference and
sampled synthetic size. No training truncation is hidden.

Zero random baseline distance can yield NaN for a small/degenerate domain. It
becomes null and NOT_APPLICABLE with INSUFFICIENT_DOMAIN warning, never zero or
one; the degenerate domain also prevents overfitting gating. SDMetrics 0.32.0's
baseline uses an unseeded `default_rng` unless private state is modified. There
is no supported public seed hook; this platform does not set private internals.
Explicit platform sampling/utility are seeded, but repeated random-baseline
scores may vary. This limitation is in reports/manifests.

## DCR overfitting

Public `DCROverfittingProtection.compute_breakdown(training, synthetic, holdout,
metadata, "clinical")` compares distances to the complete original training
and unseen holdout. Breakdown stores closer-to-training/holdout percentages.
It is not a re-identification probability or formal privacy guarantee.

**The Phase 3 default 80/20 split gives a train/validation ratio of 4.0. Its DCR
overfitting result is ADVISORY_ONLY and not release-gating eligible.** The score
may still be shown. We do not downsample training to manufacture balanced evidence.

Eligibility additionally requires assessed entity independence/no configured
group overlap, minimum holdout rows and a comparable-size ratio. Default request
`dcr_max_train_validation_ratio=1.25` requires ratio in [0.8,1.25]. The configurable
range is 1–2. This numeric range is a **MedSynth Guard operational policy**,
not an SDMetrics mathematical requirement or scientifically validated standard.
[Upstream guidance](https://docs.sdv.dev/sdmetrics/data-metrics/privacy/dcroverfittingprotection)
recommends comparable training/validation sizes. Persist actual counts, ratio,
configured range, warnings and `gating_eligible`; policies cannot use an advisory
score as passing evidence. A separate boolean eligibility rule may explicitly
fail when eligibility is false.

## Disclosure attacker configuration

FULL evaluations may explicitly configure known_columns and sensitive_columns.
They must be nonempty, distinct, disjoint sets of modelled columns. Governance
annotations provide suggestions only after user selection; no hidden attacker
model is inferred. Selected numerical/datetime attack columns must explicitly
appear in continuous_columns. Bin count is bounded (2–50, default 10).

Public `DisclosureProtection.compute_breakdown` uses **real holdout** as attack
reference and synthetic data as attacker information. Persist metric type, score,
CAP/baseline protection, known/sensitive/continuous columns, cap/zero_cap/generalized_cap
method, binning and sampling. No source values are exposed. Incomplete/group-leaky
holdout evidence is advisory. Above DISCLOSURE_MAX_ROWS, full computation declines
unless `estimated=true` was explicitly requested. Then the supported
`DisclosureProtectionEstimate` runs with recorded bounded row samples/iterations,
NumPy seed and ESTIMATED label. Same-runtime estimate seed repeatability is tested;
cross-version bit-for-bit identity is not promised.

No simplistic k-anonymity release gate, membership-inference analysis, DP claim
or unrestricted-sharing claim is introduced. The configured scenarios cover
selected attacks, not every adversary or possible disclosure channel. Protect
these aggregate reports as sensitive internal artifacts.
