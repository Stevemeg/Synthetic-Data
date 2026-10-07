# Baseline audit — Phase 1

Audit date: 2026-09-30. The audit covers the actual working tree, including
pre-existing local edits. No root README existed in the working tree or HEAD;
`backend/README.md` contained only `# Synthetic-Data`. The frontend README was
the Vite template. Claims requested for review are distinguished below from
claims actually present in those files. No absent README text is reconstructed.

## Inventory and repository architecture before stabilization

All application Python files, React components, styles, TypeScript/build/lint
configuration, requirement files, Git ignores, tracked model inventory, and
local artifact/data directories were examined. Source record contents were not
needed for this audit and were not used as tests.

| Area/files | Baseline behavior/evidence |
| --- | --- |
| `backend/app.py` | Global Flask instance, unrestricted CORS, forced debug, cwd-derived paths, raw upload filenames, unbounded persistence, subprocess imaging; three success placeholder routes |
| `generate_tabular.py` | Drops/imputes/scales input, then samples source dataframe rows with replacement; no synthesizer |
| `generate_genomic.py` | Preprocesses a CSV then generates uniform random values; no genomic model or sequence format |
| `generate_images.py` | Loads DCGAN checkpoint, optional classifier gate, samples noise; ZIP contains a single grid of at most 64 samples rather than individual requested images |
| `run_pipeline.py` | CSV ECG cleaning/peak extraction, 50-epoch PyTorch VAE, generates extracted-window count, copies source labels, saves only a partial decoder; broken `add_-argument` CLI |
| `train_tabular_model.py` | Genuine SDV TVAE training from CSV, drops incomplete rows, saves pickle; disconnected from upload generation |
| Local `train_validator.py` | Experimental ResNet18/ImageFolder classifier training, hard-coded developer path, no held-out evaluation |
| `evaluate_ml.py` | TensorFlow CNN trained on the invalid synthetic labels; developer-specific real-test path; TensorFlow not declared in existing requirements |
| `evaluate_visuals.py` | Random waveform plots using fixed relative NPZ names; no quantitative fidelity score |
| `frontend/src/App.tsx` | Four disconnected forms, `any` types, automatic download requiring a `fileUrl` absent from success placeholders, raw details prioritized on failure |
| `frontend/src/components/*.tsx` | Unsupported dataset/FASTA/FASTQ/sequence-length controls; sample counts not consistently bounded; imaging upload only classified, not used in generation |
| Styles/assets | Vite dark/flex/button rules conflict with MUI; `App.css` contains dead TSX-like template code; Vite/React logos and template title remain |
| Package/config files | React 19, TypeScript 5.8, Material UI 7, Vite 7, Axios, ESLint; package lock present, no test script; strict TypeScript enabled |
| Requirements | Root untracked list duplicates/expands backend runtime with unused notebook/ydata/OpenCV/seaborn packages; backend includes Flask/ML packages but no consistent pins; optional evaluation/training not separated |
| Local source data | 7 files under `backend/uploads`, 13 nested uploads under `backend/backend/uploads`; `data_for_validation` contains 300 Brain, 234 Chest, 66 Skin images; these were untracked |
| Local screenshots | 8 PNGs under misspelled `assests/`, including sample/evaluation screenshots and architecture images; untracked historical illustrations are not evaluation evidence |
| Git/environment | No tracked CSV, NPZ, JPG/JPEG, or PNG datasets in current tree; local venv and node_modules present; several user edits existed before this work |

### Baseline data, training, generation, and evaluation flow

The React frontend sends multipart config and an optional file to Flask.
Flask stores raw filenames under cwd-dependent upload paths. Imaging alone
invokes a script, passing a selected model and optional source-image path;
classifier output only gates the request and does not condition generation.
Depending on startup cwd, script/model and generated/upload directory paths
are inconsistent. Tabular, genomic, and ECG working-tree routes simply return
success messages without generated artifacts. Thus an HTTP success does not
demonstrate any generation.

Standalone tabular training creates a real TVAE model, but standalone generation
does not use it. Standalone genomic generation has no training flow. Imaging has
inference architecture/checkpoints but no GAN trainer in the repo. The optional
classifier trains a modality classifier without a held-out evaluation design.
ECG training extracts 96-sample heartbeat windows from rows with a final label,
z-score normalizes them, and trains a sigmoid-output VAE. That normalization/output
range is inconsistent. Decoder flattening assumes lengths divisible by four;
generation ignores requested count and a one-sample output can lose its batch
dimension via `squeeze()`. The saved transposed-convolution state omits the latent
projection and dimensions needed to reconstruct generation.

ECG supervised evaluation uses copied source labels on unconditional samples,
so its accuracy is not a supported utility measurement. It also requires absent
local files and undeclared TensorFlow. Plotting unrelated random windows is
descriptive and does not establish statistical similarity, clinical fidelity,
privacy, or release readiness.

## Models actually present and preservation

| Artifact | Evidence and use after Phase 1 | SHA-256 (unchanged) |
| --- | --- | --- |
| `diabetes_model.pkl` | Static pickle opcode inspection identifies SDV TVAESynthesizer and metadata including encounter/patient identifiers; not deserialized or API-integrated | `1b4aaa67b69f14f86ac245de93d2db1e53af1bac8d691530bfd0c2ce32a803d1` |
| `heart_disease_model.pkl` | Static inspection identifies SDV TVAESynthesizer and clinical column metadata; not API-integrated | `f441a4982c690d115ac009ab112c81fe63e2bdaa353ef7c9ea5a954bcd4e9457` |
| `generator_brain.pth` | DCGAN state dict; real load and two-image inference/export verified | `42a1f07470466d88a6e6291942e09f13e47ffac838ddc287699b17696dad21a9` |
| `generator_chest.pth` | DCGAN state dict; real load and two-image inference/export verified | `6c1783a75d81b8a93dce64713c0579b5f15bcc8dd51f724bc619036cbee82307` |
| `generator_skin.pth` | DCGAN state dict; real load and two-image inference/export verified | `c9f3c60eb63ce3f2d2dc2f967c958972a1b06a09c5cb3d9f92c528813c5c1ac0` |
| `vae_decoder_model.keras` | Keras ZIP metadata: version 2.13.1, saved 2025-08-16, latent input 16 and 96×1 sigmoid decoder; incompatible with PyTorch path and retained unused | `e5b68ce39d342702a1ec1b69695fa7916c25d6fe2ff1a7a5aa8d1265892ea145` |
| Local `medical_validator.pth` | Untracked experiment preserved/ignored; restricted state load found `classes` and `model_state`, three-class classifier with 3×512 final weights; not used by API | `e4f36ae46cc0735d0587bae56c26cab2e0ee0c6e3fc5ec40ad3e160d09bd1c6b` |

No binary was moved, overwritten, or deleted. API model lookup defaults to the
original `backend/` directory. TVAE and Keras compatibility beyond static inspection
is unverified; their training source, authorization/licensing, train/test splits,
and disclosure behavior are not established by these files. Classifier state
shape is not proof of diagnostic or modality-classification performance.

## Claims versus implementation

The only backend README statement was the project title. The root README was
absent. “README claim” therefore records absence where appropriate; additional
UI/script/model-name claims are explicitly identified as such.

| Claim/topic | Available README claim | Implementation evidence | Complete? / experimental? | Required disposition after Phase 1 |
| --- | --- | --- | --- | --- |
| Synthetic medical generation | Backend title only; root absent | Real ECG VAE/DCGAN scripts plus fake tabular/genomic paths and placeholder HTTP successes | Incomplete, research | Rewrite around current gates and research workflows |
| Privacy / zero re-identification / anonymity / safe sharing | No substantiating README text | No disclosure tests or formal mechanism | Not implemented | Make no guarantee; document unmeasured risks |
| HIPAA/GDPR compliance | No such claim in available READMEs | No compliance controls/evidence | Not implemented | No compliance claim |
| Nine datasets | No such claim in available READMEs | Two TVAE files, three image checkpoints, ECG code; no nine-dataset registry or reproducible evaluation | Unsupported | Do not advertise nine datasets |
| TVAE | No README model claim; trainer/artifacts name TVAE | Genuine SDV trainer and two static-identifiable pickles; upload path does not use them | Offline experiment only | Preserve artifacts/trainer; gate tabular API pending Phase 3 |
| TabDDPM | No such claim | No code/checkpoint | Absent | Do not advertise |
| CopulaGAN | No such claim | No integration/checkpoint; package presence is not implementation | Absent | Do not advertise |
| DCGAN/cGAN | No README model claim; image code resembles DCGAN | Unconditional noise-input DCGAN, separate checkpoints; no conditional generator | Experimental DCGAN only | Describe DCGAN, never cGAN or source conditioning |
| Genomics | UI offers sequences, FASTA/FASTQ, length | Uniform random numerical CSV values; none of offered formats/controls | Placeholder, not synthesis | Remove engine; experimental/unavailable label only |
| Medical imaging dataset | UI says generate images; API says data generated | ZIP previously contains one grid only | Misleading export; research | Export every sample; label 64×64 RGB lab limitations |
| ML utility | No README metrics; standalone CNN intended utility | Unjustified copied labels and hard-coded paths | Invalid measurement | Disable supervised utility report with explicit reason |
| Statistical similarity / visually indistinguishable | No supported README metrics | Random waveform plots; historical screenshots | Unmeasured | Descriptive plots only; no fidelity claims |
| Production readiness | No README evidence | Debug, wildcard CORS, unsafe paths, no tests, placeholder successes | Not established | Describe local Phase 1 baseline, never production grade |
| ECG requested count / labels | UI accepts count | Pipeline generates extraction count and copies source labels | Incorrect | Exact requested count; no labels; document window semantics |

## Stabilization decisions and correctness fixes

Tabular follows the authorized **Option B**. Pretrained TVAE schemas/provenance
are not verified for arbitrary uploads; connecting them would not establish a
legitimate upload workflow. Source resampling is removed from both API and CLI.
Genomic random arrays and ignored format/length controls are removed. Both fail
unavailable, before uploaded source files are persisted.

Flask remains, with factory/config/API/service boundaries and lightweight
generation contracts. No Phase 2 infrastructure is introduced. CLI declarations
and all developer-specific paths are corrected; direct services replace HTTP
subprocess calls. API debug/reloader are disabled, CORS uses configured explicit
origins, requests are bounded, filenames sanitized, extensions/MIME/text/CSV
schemas checked, error messages sanitized, and ordinary temporary-file cleanup
is automatic. Models and upload storage no longer depend on startup cwd.

ECG extraction validates numeric finite rectangular data, source-label exclusion,
nonempty inputs/peaks, inclusive end boundaries, segment limits, and failures.
VAE dimensions support nonmultiples of four; normalized `[0,1]` inputs match the
sigmoid decoder. Requested count and batch dimension are preserved. A complete
checkpoint is saved with reconstruction metadata. Training defaults are now
10 bounded/configured epochs, rather than an unchangeable 50. Copied labels and
the associated supervised evaluation are removed.

Imaging loads trusted state dicts directly, validates modality/count, disallows
unsupported source uploads, and exports every requested PNG without a shared
temporary-directory race. Its classifier is retained only as an offline
experiment. Labs are opt-in and blocked in the production environment.

The UI now distinguishes maturity and availability, reads limits/capabilities,
removes ignored controls and template assets, displays useful run metadata and
safe backend errors, and provides explicit downloads. “Stable” describes input
contracts, not synthetic data quality or release safety.

One authoritative Python base dependency file replaces duplicated lists, with
additive pinned ML/dev/offline-training groups. An isolated install uncovered
NeuroKit's undeclared `requests` import; it is now explicitly pinned. No unused
model name is inferred from a dependency. Local uploads, 600 source images,
historical screenshots, generated data, and new training outputs remain ignored
and were not committed or deleted.

## Remaining risks and evidence limits

Phase 1 engineering tests are not clinical/statistical/privacy validation. The
ECG model is unconditional and outputs normalized windows only; the sampling
rate is operator-supplied. Source-label semantics and physical calibration are
not inferred. TVAE/Keras training and compatibility are unverified. No training
provenance is established for imaging beyond its checkpoint hash and architecture.

No database, authentication, authorization, queue, object store, deployment,
retention scheduler, privacy scoring, or release decision exists. The application
run lock is per instance; multi-process/CLI concurrency is not coordinated.
Successful outputs persist locally; crashes can leave staging. Direct dependencies
are pinned, but transitive dependencies and cross-hardware reproducibility are
not fully controlled. The legacy numerical stack emits a known deprecation
warning during the simulated ECG fixture; this is not hidden.

## Verification record

Executed on Windows, Python 3.11, Node 24.18.0, using a fresh isolated `.venv`
and `npm ci`. These outcomes describe the final code state:

| Command/check | Actual outcome |
| --- | --- |
| `python -m pytest -q` | 88 passed, 10 model tests deselected |
| `python -m pytest -q -m model` | 10 passed, 88 deselected; 5 unsuppressed numerical-library deprecation warnings |
| `python -m compileall -q backend` | Passed |
| Import all application/script modules via `pkgutil`/`importlib` | 28 modules imported successfully |
| `python -m ruff check backend` | All checks passed |
| `python -m ruff format --check backend` | 47 Python files already formatted |
| `python -m pip check` | No broken requirements found |
| `python backend/run_pipeline.py --help` | Correct CLI usage, exit 0; real CLI execution also covered by model test |
| `python -m backend.scripts.smoke_test` | Real HTTP health 200, ECG generation 201, dataset download 200; `(1,96)`, no labels, uploads cleaned |
| `python -m backend.app` with test port override | Started with debug off; live health returned HTTP 200; server stopped after check |
| `npm run dev -- --host 127.0.0.1 --port <test-port>` | Started; HTML HTTP 200 with MedSynth Guard title; server stopped after check |
| `npm run build` | Passed, Vite production build |
| `npm run typecheck` | Passed, strict TypeScript project checks |
| `npm run lint` | Passed, ESLint |
| `git diff --check` | Passed; Git emitted local LF/CRLF conversion notices, no whitespace errors |
| Backend developer-path/forced-debug scan | No developer-specific absolute paths or forced debug found |
| Tracked source dataset extension inventory / untracked-file review | No tracked source datasets; local uploads/images remain ignored |
| All seven original/local model SHA-256 values | Rechecked and identical to pre-change values |

The first optional integration run failed because of NeuroKit's undeclared
`requests` import; adding the explicit dependency resolved it. A combined run
then exposed a new blueprint/package name collision; the blueprint import was
renamed and both final suites passed. A PowerShell empty marker argument was
replaced in documentation with `-m "model or not model"`. No failed result was
reported as a pass. The frontend install emitted an npm 12 notice about an
unapproved esbuild postinstall script; the actual build still succeeded.

See `docs/DEVELOPMENT.md` for repeatable commands, optional-model selection,
and warning interpretation. No real source datasets or new learned artifacts
were staged/committed during stabilization. Phase 1 acceptance is met for the
local baseline, with the deliberately unavailable workflows and limitations
documented above; this is not production or model-release certification.

## Historical audit status

This document records the Phase 1 audit and stabilization. Phase 2 subsequently migrated HTTP to FastAPI and added PostgreSQL persistence, a separate worker and artifact provenance. Current runtime behavior is documented in README, ARCHITECTURE, API and JOB_LIFECYCLE; the original audit and model hashes are retained as historical evidence.
