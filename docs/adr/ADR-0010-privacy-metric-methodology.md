# ADR-0010: Explicit privacy methodology and applicability

Status: Accepted. Date: 2026-10-02.

DCR and disclosure metrics address different questions and can be inapplicable.
Use public SDMetrics 0.32.0 breakdown APIs on modelled columns; preserve outputs
and missing values. Keep complete original training/holdout DCR references or
decline computation above limits. Default 80/20 DCR overfitting is advisory;
operational comparable-size eligibility is explicit, configurable and not a
scientific or SDMetrics threshold. Never rebalance the trained reference silently.

Disclosure attacker configuration is explicit, evaluated against holdout, and
estimation is opt-in. Group leakage is assessed using a configured source key;
original split provenance is not rewritten. Baseline random generator lacks a
public seed hook; do not mutate private internals or promise full reproducibility.
No metric proves anonymity, compliance or differential privacy.
