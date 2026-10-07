# ADR-0006: Real tabular engine adapters

Accepted in Phase 3. Use SDV Gaussian Copula (Stable default), CTGAN and TVAE
(Beta opt-in) behind the small TabularSynthesizer contract: validate_config, fit,
sample, save, checksum-checked internal load and describe. Confine SDV imports
and the necessary version-guarded sampling-seed bridge to engines.py. Persist
application metadata, not raw SDV domain objects. Reuse the existing supervised
worker/publication system. No fallback, CopulaGAN, ranking, scoring or model
registry. Optional API model reuse is deferred. See TABULAR_SYNTHESIS.md for exact
versions, API assumptions, reproducibility and license review reference.
