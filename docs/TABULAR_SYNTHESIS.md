# Clinical tabular synthesis (Phase 3)

MedSynth Guard registers a single-table clinical CSV, profiles structural facts,
accepts reviewed column roles/types, trains a real model on a training partition,
samples new records, validates structure, and publishes model/data provenance.
There is no source-row resampling, independent-column placeholder, copied source
notes, or fallback to original records. Registration/preflight do not fit models.

## Engines and dependencies

| Engine | Maturity | Implementation |
| --- | --- | --- |
| gaussian_copula | Stable default | SDV GaussianCopulaSynthesizer, learned multivariate copula |
| ctgan | Beta, opt-in | SDV CTGANSynthesizer, real CTGAN conditional GAN |
| tvae | Beta, opt-in | SDV TVAESynthesizer, real tabular VAE |

Gaussian Copula is recommended as the initial operational baseline because it is
fast and inexpensive to train/test. These labels do not rank statistical fidelity,
privacy or clinical accuracy. No model comparison or winner selection exists.

Install `backend/requirements-tabular.txt` in the existing venv. Direct pins:
SDV 1.25.0, RDT 1.18.2, CTGAN 0.11.1, Copulas 0.14.1. SDV 1.25.0 was already
the offline lab pin; newer available releases were inspected, not silently
adopted. Existing NumPy 1.26.4, pandas 2.2.3 and PyTorch 2.10.0 are unchanged.
This remains an additive dependency group, not a second base requirements file.
SDV installs SDMetrics transitively; this application does not use its scoring.
Review the [SDV version's distribution/license](https://pypi.org/project/sdv/1.25.0/)
for the intended use; a software maturity designation is not a license grant.

The installed API was inspected, rather than assumed from tutorials. The adapter
uses `Metadata.detect_from_dataframe(training, table_name="clinical", infer_keys=None)`,
`update_column`, `validate`, `validate_data`, `fit`, `sample`, `save`, and the public
`sdv.utils.load_synthesizer`. It uses the current Metadata class instead of
deprecated SingleTableMetadata. See [SDV metadata documentation](https://docs.sdv.dev/sdv/concepts/metadata).
All columns are explicitly translated from application metadata; SDV key/PII
inference never promotes a clinical feature into an automatically generated key.

SDV 1.25.0 exposes public `reset_sampling()` but no public user sampling-seed setter.
One necessary, isolated `_set_random_state(seed)` bridge is guarded by exact runtime
version compatibility and real repeatability tests. Do not change these pins
without rechecking this bridge. The public SDV neural constructors accept `cuda`;
CTGAN 0.11.1 warns that its underlying `cuda` option is deprecated in favor of
`enable_gpu`. This known upstream warning is visible; no private neural internals
or epoch-progress hooks are used. No CopulaGAN is implemented.

## Reproducible partition

The v1 algorithm is `numpy-pcg64-positional-permutation`:

1. Verify the immutable source artifact SHA-256 and byte count.
2. Parse CSV in its original record order, without a pandas index column.
3. Let `h = floor(source_rows * holdout_fraction)`.
4. Below 20 source rows, set h=0 and record a warning when h would be positive.
5. Require at least 10 training/source rows operationally.
6. `Generator(PCG64(split_seed)).permutation(source_rows)` selects the first h
   positions for holdout and the remainder for training.
7. Sort positions within each partition to preserve original relative order.

Default fraction=0.20 and split_seed=42. Fraction is bounded to [0,0.5]. Both
requested fraction and realized fraction, seed, algorithm/version and partition
counts are recorded. The source hash is checked again in the child before
reconstruction, and the reconstructed split must equal the submission snapshot.
Only modelled training columns reach SDV. No ordinary artifacts contain source
training or holdout rows/indices; Phase 4 can reconstruct them from authorized
access to the immutable source. This is a random row split, not a patient-grouped,
temporal or stratified split; repeated patients may span both partitions.

Python, NumPy, PyTorch and synthesizer sampling state are seeded. CPU same-runtime
Gaussian Copula reproducibility is tested. Neural/GPU and cross-version/platform
reproducibility remain best-effort, not a bit-for-bit guarantee. Requested row
count and synthetic IDs are deterministic; model serialization includes SDV
runtime identifiers and is not promised to have identical bytes across fits.

## Worker and publication

The existing API submits PostgreSQL QUEUED work. The existing worker claims using
FOR UPDATE SKIP LOCKED, retains advisory ownership, heartbeats its lease and
spawns a supervised child in a job-specific attempt workspace. The child loads
the verified source, reconstructs training, builds SDV metadata, fits the selected
adapter, samples, restores IDs, validates and writes temporary outputs. It never
opens database connections or publishes storage objects.

The parent records actual training/sampling/validation events, then writes:
`dataset.csv`, `synthesizer.pkl`, `structural_validation.json`, and
`run_manifest.json`. One fenced transaction inserts all artifact metadata,
counts, success state and audits. Success cannot precede required validation.
Existing compensation, uncertain-commit handling and orphan reconciliation remain.
Temporary workspaces clean up normally; abrupt worker death may leave an ignored
workspace requiring maintenance. No fake percentages or epoch progress appear.

Manifests record APP_COMMIT when configured, otherwise the locally available Git
HEAD and a dirty-worktree flag. With uncommitted changes, HEAD identifies the base
commit, not a committed release of the working tree.

Models are restricted trusted internal artifacts. There is no model upload,
HTTP deserialization, or reuse endpoint. The internal adapter's load contract
requires a trusted checksum and verifies it before deserialization; test artifacts
exercise that path. Optional fit-once/sample-many model reuse is explicitly
deferred until ownership/source/metadata compatibility checks can be exposed
cleanly. Preserved legacy TVAE pickles are never loaded by this workflow.

## Operational limits

| Environment variable | Default | Configurable maximum |
| --- | --- | --- |
| TABULAR_MAX_SOURCE_ROWS | 10000 | 100000 |
| TABULAR_MAX_COLUMNS | 100 | 500 |
| TABULAR_MAX_GENERATED_ROWS | 10000 | 10000 |
| TABULAR_MAX_TRANSFORMED_CELLS | 2000000 | 10000000 |
| CTGAN_MAX_EPOCHS / TVAE_MAX_EPOCHS | 50 | 100 |
| CTGAN_WARNING_MIN_ROWS / TVAE_WARNING_MIN_ROWS | 500 | 100000 |
| TABULAR_JOB_TIMEOUT_SECONDS | 300 | 3600 |

The existing 10 MB upload bound also applies. Before neural training, a conservative
transformed-cell estimate bounds categorical one-hot expansion plus continuous
mixture/missingness features. High-cardinality requests exceeding this operational
budget fail explicitly before queueing and again in the child. This estimate is
not a hard OS-level memory quota. Source limits reject, never
truncate. Neural row thresholds are operational recommendations, not scientific
minimum sample sizes. Limits are snapshotted with the job; worker restarts do not
silently change them. Timeout terminates the supervised child and reports
TABULAR_TRAINING_TIMEOUT without publishing incomplete output.

Common configuration includes requested_samples, random_seed, holdout_fraction,
split_seed, metadata_overrides and validation_rules. Copula exposes only
default_distribution (beta/norm/truncnorm/gaussian_kde). Neural defaults: 10 epochs,
batch_size=100 (10–500, divisible by 10), embedding_dim=64 (16–256), two 128-wide
layers (1–3 layers, 16–256 per layer), cuda=false. CTGAN uses generator/discriminator
dimensions; TVAE maps these controlled fields to decoder/encoder dimensions.
CUDA must be explicitly available when requested. User-specific configuration
must match the chosen engine. The UI exposes engine, row/seed/split and neural
epochs; the API supports the additional controlled settings.

## Limits of Phase 3

CSV only, one table, no free-text generation, multi-table relationships, model
registry, privacy scoring, differential privacy, statistical-quality release
gate, ML utility evaluation or clinical certification. Identifiers are unique
within each output artifact; separate runs may reuse SYN sequence values.
OIDC and organization roles are implemented. Deployment requires reviewed
HTTPS and maintained providers; these controls do not establish clinical or regulatory validity. Local storage and
unauthenticated data downloads retain the Phase 2 operational limitations.
