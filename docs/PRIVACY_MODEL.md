# Privacy model and current limits

## Synthetic does not mean anonymous

This repository provides no proof that outputs or learned weights are anonymous.
A generative model can memorize unusual records or combinations of attributes.
Overfitting, repeated records, small training sets, sensitive rare patterns,
and downstream linkage may create disclosure risks even when generation samples
new latent values. An output should not be released solely because it is called
synthetic or looks different from the source.

Statistical fidelity and privacy are different dimensions. Preserving detailed
distributions can help utility while retaining sensitive patterns. Low fidelity
also does not demonstrate privacy protection. Clinical plausibility and task
utility require separate evidence.

## What Phase 1 actually does

- Removes the source-row resampling path and the random genomic placeholder.
- Bounds and validates uploads and generation requests; deletes request files
  during normal completion/failure; avoids logging source records and filenames.
- Publishes generation configuration, source shape summaries, counts, warnings,
  and checkpoint hashes for imaging. These are basic provenance aids, not a
  complete lineage or dataset governance system.
- Keeps generated artifacts and new weights ignored by Git. Learned ECG weights
  are not downloaded through the API.

These engineering controls do not measure privacy risk and do not prevent all
memorization or linkage. No differential privacy mechanism, privacy budget,
membership-inference defense, or formal anonymity guarantee is implemented.
No HIPAA/GDPR compliance claim is made. No source-data rights are inferred from
the existence of a checkpoint or local file.

## Handling source data and outputs

Use source datasets only under appropriate authorization and data-handling
requirements. Avoid unnecessary identifiers. Keep the local service on loopback
and restrict access to source files, generated artifacts, and models. Local
temporary-file cleanup is not secure erasure, encryption, or a retention policy.
Backups and synchronized folders may retain copies; repository ignore rules do
not control those copies. Existing local uploads are preserved for the owner to
manage and remain ignored. No source datasets are tracked in the audited tree.

Pretrained provenance and licensing are incomplete. TVAE pickles were inspected
statically, not treated as trusted clinical models. Never load an uploaded pickle
or checkpoint; only reviewed local artifacts may be loaded. The permitted
imaging lab is an experiment, not an approval to share its outputs.

## Future measured release process

Later phases must define the threat model and intended recipients/use before
selecting tests. Planned evaluation includes record-distance/disclosure measures,
exact/near-duplicate comparisons, relevant memorization or membership tests,
statistical fidelity, schema/clinical constraints, and downstream task utility
on independently held-out data. Thresholds must be documented with known
limitations; a single aggregate score is not enough to establish release safety.

Future differential privacy work, if adopted, must specify where noise is
applied, clipping, accountant assumptions, epsilon/delta, and what the guarantee
covers. Until an implementation and evidence exist, differential privacy is
not claimed. Phase 1 metadata contains warnings, not a release approval.

## Phase 2 provenance and persistence

PostgreSQL persists structural metadata, SHA-256 values, jobs, artifact references and unauthenticated audit events. Source/output bytes remain in local storage. Metadata omits source row values/previews; column names themselves can still be sensitive. Every successful job records a run manifest, engine/configuration/seed/count/timing and checkpoint hash. These are lineage aids, not privacy evaluation or release approval.

Complete ECG learned weights remain restricted artifacts without HTTP download. Other downloads require authenticated organization membership. OIDC and role enforcement do not establish anonymization, regulatory compliance or clinical validity. Persistent database/storage/backups expand the data-handling surface; cleanup is not secure erasure. No differential privacy or compliance guarantee has been added.

## Phase 3 tabular handling

Synthetic data may reduce dependence on real records in development workflows.
Privacy risk still requires evaluation. Direct identifiers are excluded from
fitting by default and replaced with clearly synthetic sequences; potential free
text is excluded. Advisory inference can be wrong and must be reviewed.
Governance annotations do not implement privacy algorithms. Models train on a
deterministic training partition with holdout reconstruction metadata retained.

Exact source-row overlap is reported as a diagnostic over modelled columns vs
training rows. Neither matches nor zero matches establish privacy safety. Phase 4
adds separate disclosure/fidelity/utility evaluation and explicit policy gates
as described below. No differential privacy mechanism is implemented. Tabular
models are restricted internal artifacts without HTTP download/upload/deserialization;
optional API reuse is deferred. See TABULAR_METADATA.md and TABULAR_VALIDATION.md.

## Phase 4 evidence boundary

Selected privacy diagnostics are now implemented, independently of statistical
fidelity, ML utility and structural validity. Exact overlap is a memorization
signal only. Real SDMetrics DCR baseline/overfitting and explicit holdout disclosure
scenarios measure selected statistical risks; none proves anonymity or regulatory
compliance. Default 80/20 DCR overfitting is advisory and cannot pass a required
numeric release gate. Entity leakage or undeclared row independence limits
relevant evidence. No DP mechanism or compliance assertion is implemented.

Policy PASS means only compliance with the configured version, not release
safety. Reports reveal source-derived statistics and require sensitive internal
handling alongside source/output/model artifacts. No public report URLs exist;
artifact downloads require authenticated organization membership. These access
controls do not establish regulatory compliance or clinical validity. See PRIVACY_EVALUATION.md and RELEASE_POLICIES.md.
