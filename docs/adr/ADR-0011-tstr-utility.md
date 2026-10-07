# ADR-0011: Transparent task-specific utility pipelines

Status: Accepted. Date: 2026-10-02.

SDMetrics ML-efficacy remains Beta. Use simple scikit-learn 1.9.1 LogisticRegression
and Ridge baselines with separately fitted, identical preprocessing architectures.
Targets/tasks are explicit. TRTR and TSTR share the untouched real holdout,
which never enters fit or tuning. Persist individual metrics and metric-aware
ratios/deltas, not a universal utility grade. Missing classes and invalid targets
are errors, never successful-looking metrics. No AutoML or classifier artifacts
are needed. Instrumented fit tests verify the holdout boundary.
