# Product scope

## Phase 5 workspace

Workflow-oriented navigation, deep links, project summaries, dataset/preflight/schema governance, reviewed bounded generation, contextual evaluation, distinct evidence dashboards, immutable policy creation/version inspection, compatibility-checked comparison, internal HTML artifacts and a generated fake-data demo are included. Actual browser, responsive, accessibility and visual verification is recorded in PHASE_5_VERIFICATION.md. That Phase 5 delivery introduced no authentication or tenant isolation. Phase 6 adds OIDC, organization roles, private S3-compatible storage, controlled deletion and release operations; no new scientific engine, differential privacy or cloud deployment is added.

MedSynth Guard V1 serves healthcare AI/data teams preparing synthetic data for
development, testing, analytics, and ML workflows. It reports
structural validity, statistical fidelity, selected disclosure diagnostics,
declared downstream utility, provenance and explicit policy compliance for
single-table workflows. Phase 1 establishes the engineering
baseline; it does not claim those evaluations already exist.

## First-class V1 capabilities

1. **Clinical tabular synthetic data.** Clinical tables offer explicit schemas,
   constraints, and task-specific evaluation targets. The repository has an
   offline TVAE trainer and two preserved TVAE artifacts, but the upload path
   only resampled source rows. Phase 1 deliberately gates API generation until
   Phase 3 rather than adopting unverified pretrained schemas/provenance.
2. **ECG/time-series synthetic data.** The repository contains a real convolutional
   VAE workflow. Phase 1 stabilizes its normalized heartbeat-window generation,
   count contract, shapes, and checkpoint export. This remains a Beta research
   workflow with no justified diagnostic labels or measured clinical utility.

“First-class” identifies product investment and future evaluation obligations;
it does not mean a currently unavailable capability is implemented.

## Experimental Labs

3. **Medical imaging.** Three usable DCGAN checkpoints support 64×64 RGB samples.
   Training provenance, diagnostic fidelity, imaging metadata, and disclosure
   risk are not established. Imaging is disabled by default and cannot be enabled
   in the application's production environment. No input-image validation or
   conditioning is advertised.
4. **Genomics.** No legitimate genomic model or biological evaluation exists.
   Random floating-point arrays cannot represent validated genomic synthesis.
   The workspace shows “Unavailable”; no genomic generation action exists.
   No FASTA/FASTQ support is implemented.

These boundaries concentrate future quality and governance work on two bounded
workflows while preserving the imaging research assets and the genomic research
direction without overclaiming their maturity.

## Maturity labels

| Label | Meaning in this repository |
| --- | --- |
| Stable | Tested input/generation contracts; does not certify model output or deployment |
| Beta | First-class workflow foundation with explicit limits; opt-in CTGAN/TVAE are Beta |
| Experimental | Research lab outside production workflows; can be entirely unavailable |

Availability is displayed separately from maturity. The UI uses backend gates;
an unavailable lab cannot generate. Generation retains its evidence limitations. Tabular evaluation provides selected
measurements; none establishes clinical validity or privacy guarantees.

## Phase 2 platform boundaries

FastAPI, PostgreSQL metadata and a PostgreSQL-backed worker queue now support durable project/dataset/job/artifact workflows. Dataset registration covers clinical tabular and ECG CSV; Phase 3 now implements tabular synthesis. ECG generation is Beta. Imaging remains an opt-in non-production lab and genomics remains unavailable.

Phase 2 adds provenance, not disclosure measurement or clinical evidence. Authentication, remote object storage, analytics dashboard and cloud deployment remain deferred; Phase 4 evaluation is described below. See ARCHITECTURE.md and JOB_LIFECYCLE.md for current implementation.

## Phase 3 implemented scope

Clinical Tabular is Stable with Gaussian Copula as operational default; CTGAN and
TVAE are Beta. Register one CSV -> preflight -> reviewed roles/types -> real fitted
model -> new records -> objective structural report and provenance. Legacy pickles
are never loaded. Training excludes default identifiers/free text and holdout rows.
Exact-row overlap is a diagnostic only. Phase 3 itself added no statistical fidelity, disclosure-risk or utility scoring
or release gates; Phase 4 extends it as described below. No dashboard redesign
or enterprise infrastructure is added. ECG remains Beta; imaging Experimental; genomics unavailable/research roadmap.

## Phase 4 delivered scope

Tabular Evaluation is Beta: asynchronous evaluation of existing Phase 3 outputs,
real SDMetrics training/holdout fidelity, DCR baseline/overfitting, explicit
holdout disclosure scenarios, declared binary/multiclass/regression sklearn
TRTR/TSTR, independent metrics and immutable project release-policy rules.
Compatibility-checked side-by-side comparison does not rank models. Reports
contain source-derived aggregate evidence and are sensitive internal artifacts.
Clinical Tabular Synthesis remains Stable; ECG Beta; Imaging Experimental;
Genomics Unavailable. Phase 4 itself added no Phase 5 redesign, universal healthcare/privacy score,
formal DP, enterprise identity or cloud deployment was added. Original row split
is reconstructed, not repaired when configured patient groups overlap.
