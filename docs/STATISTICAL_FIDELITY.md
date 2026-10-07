# Statistical fidelity

Fidelity concerns distributions and relationships, separately from Phase 3 schema
and rule validity. The supported public **SDMetrics 0.32.0** API is
`sdmetrics.reports.QualityReport`; the old single_table import is deprecated.
`generate` receives dictionaries keyed by `clinical`, plus metadata with
`tables.clinical.columns` and an empty relationships list. `get_properties`,
`get_details(property_name, table_name="clinical")` and `get_score` provide JSON
results. Application metadata is translated for modelled columns only.

Two independent reports compare synthetic data with the original real training
partition and with untouched real holdout. They are never averaged. Each stores
the report's own fidelity aggregate, Column Shapes, Column Pair Trends,
per-column and per-pair details, metric names and applicability. Numeric shapes
use KSComplement; categorical shapes use TVComplement. Report-selected pairs
use CorrelationSimilarity and ContingencySimilarity where supported. Upstream
filtered/inapplicable pair values are JSON null with NOT_APPLICABLE, not zero.

Scores are the upstream metric's normalized similarities, not clinical accuracy,
privacy or utility. Pairwise resemblance does not establish complete joint
distribution equivalence or validity of downstream medical conclusions.

Quality inputs are independently sampled without replacement above
QUALITY_SUBSAMPLE_ROWS using persisted seeds. Reports label FULL or SUBSAMPLED,
actual input counts and seed. Fewer than two rows yields INSUFFICIENT_DATA.
Holdout below request `minimum_holdout_rows` (default 20) is ADVISORY_ONLY. This
is an operational recommendation, not a confidence interval. No statistical
confidence is invented. Required policy rules using advisory evidence require review.
