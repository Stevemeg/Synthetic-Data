# Phase 4 verification

## Phase 3 baseline before any modification

Read README and all requested architecture/scope/privacy/development/API/job/
artifact/Phase 2/Phase 3/tabular documents and ADRs 0001-0008. Inspected engines,
metadata, source/split integrity, structural/exact diagnostics, models, migrations,
artifact storage, API/frontend, worker child supervision, claim/lease/token fences,
publication compensation and audit events. Preserved existing uncommitted work.

Windows, Python 3.11.0 in `.venv/Scripts/python.exe`, PostgreSQL 16, Node 24.
No baseline regression required repair. All results below preceded repository edits.

| Command | Actual result |
| --- | --- |
| `python -m pytest -q` | 154 passed, 1 symlink privilege skip, 50 deselected; 17.82 s |
| `python -m pytest -q -m model` | 24 passed, 181 deselected; 98.29 s |
| `python -m pytest -q -m integration` | 34 passed, 171 deselected; 186.87 s |
| `python -m compileall -q backend` | Passed |
| `python -m ruff check backend` | Passed |
| `python -m ruff format --check backend` | Passed, 108 files |
| `python -m pip check` | No broken requirements |
| Frontend `npm ci` | 343 packages, zero vulnerabilities |
| `npm test` | 2 passed; 68.32 s |
| `npm run typecheck` | Passed |
| `npm run lint` | Passed |
| `npm run build` | Passed, 961 modules, JS 504.13 kB; chunk-size advisory |
| `npm audit --audit-level=low` | Zero vulnerabilities |
| `python -m backend.scripts.platform_smoke_test --start-services` | SUCCEEDED, 2/2, 3 artifacts; real API restart passed |
| `python -m backend.scripts.tabular_smoke_test --start-services` | SUCCEEDED, 50/50, 80/20 train/holdout, 4 artifacts; real API restart passed |

Baseline ECG job `6f6ece05-0d3d-4b69-a355-efc358d570c0`.
Baseline tabular job `cc00a960-7ce4-4da5-9620-cc979be43134`.
Known upstream warnings remain visible. npm reported a blocked optional esbuild
install script, but the installed executable and build worked. Marker suites overlap.

Installed SDMetrics 0.32.0 and scikit-learn 1.9.1 signatures and relevant metric
implementations were inspected. The old single_table QualityReport import emits
a deprecation; use the public `sdmetrics.reports.QualityReport`. Current report
metadata uses a tables dictionary; DCR accepts this plus table_name. ML efficacy
APIs remain documented Beta, so utility uses an explicit sklearn pipeline.

## Final verification

All required Phase 4 software gates passed on 2026-10-02. Python commands below
used `.venv/Scripts/python.exe`; npm commands used the frontend directory.
The marker suites overlap, so counts must not be summed as unique tests.

| Command | Actual final result |
| --- | --- |
| `python -m pytest -q` | 169 passed, 1 Windows symlink privilege skip, 68 deselected; 33.47 s |
| `python -m pytest -q -m model` | 33 passed, 205 deselected; 448.57 s |
| `python -m pytest -q -m integration` | 44 passed, 194 deselected; 678.72 s |
| `python -m compileall -q backend` | Passed |
| `python -m ruff check backend` | Passed; repeated after final documentation/smoke work |
| `python -m ruff format --check backend` | Passed, 124 files |
| `python -m pip check` | No broken requirements |
| `python -m alembic upgrade head` | Upgraded existing development schema to 0003_evaluation |
| `python -m alembic current` | 0003_evaluation (head) |
| `python -m alembic check` | No new upgrade operations detected |
| `npm ci` | 343 packages; zero vulnerabilities; optional esbuild install-script warning |
| `npm test` | 4 passed, 2 files; final rerun 8.64 s |
| `npm run typecheck` | Passed |
| `npm run lint` | Passed |
| `npm run build` | Passed, 962 modules; JS 523.77 kB (165.66 kB gzip); existing chunk-size advisory |
| `npm audit --audit-level=low` | Zero vulnerabilities |
| `python -m backend.scripts.platform_smoke_test --start-services` | Real ECG 2/2, 3 artifacts, hashes and actual API restart passed |
| `python -m backend.scripts.tabular_smoke_test --start-services` | Real Gaussian Copula 50/50, source 100/train 80/holdout 20, 4 artifacts and API restart passed |
| `python -m backend.scripts.evaluation_smoke_test --start-services` | Real FULL evaluation, 5 evaluation artifacts plus 4 generation artifacts, input/report hashes and actual API restart passed |

The final model/integration commands additionally used
`--junitxml=backend/.work/phase4-{model,integration}.xml -o junit_logging=system-out -o junit_log_passing_tests=true`
to retain passing-test aggregate output. Isolated UUID schemas were removed after
integration tests; live smoke projects/artifacts remain for inspection.

### Additional implementation checks and corrected failures

- `python -m pip install --dry-run -r backend/requirements-evaluation.txt` and
  `python -m pip install -r backend/requirements-evaluation.txt`: requirements
  already satisfied, no numerical/ECG/imaging package upgrades.
- `python -m pytest -q backend/tests/test_evaluation.py`: 15 passed, 4.47 s.
  The first collection used pytest's reserved parameter name `request`; renamed
  the test parameter, then collection/tests passed.
- `python -m pytest -q -m model backend/tests/test_evaluation_models.py`:
  initial 7 passed in 46.79 s; later 7 passed in 45.32 s.
- `python -m pytest -q -m model backend/tests/test_evaluation_models.py::test_real_estimated_disclosure_and_seeded_sampling`:
  1 passed, 6.84 s. All eight evaluation model cases passed in final full model suite.
- `python -m pytest -q -m integration backend/tests/test_evaluation_integration.py`:
  first 9 passed, 308.00 s; expanded suite 10 passed, 354.48 s; all ten also
  passed in final 44-case integration suite.
- Focused three-engine comparison `pytest -q -s -m model ...::test_three_real_engines_compatible_comparison_and_policy_versions`
  first failed while its running parent held the old audit-stage whitelist and
  a freshly spawned child loaded a newly added stage. Restarting both with the
  same code resolved it; final model and integration comparison tests passed.
  No model substitution or fallback was used.
- First frontend run had 3 passes and a 5-second timeout in the longer interaction
  test. Its explicit timeout became 15 seconds; subsequent runs had all 4 pass
  (18.10 s, 102.58 s during concurrent suites, final 8.64 s). Typecheck/lint/build
  passed at each final frontend gate. No dependency change was needed.
- `ruff check --fix backend` / `ruff format backend`: corrected unused imports
  and formatting; final non-mutating check/format gates passed.
- Manual compatibility runner initially used an invalid `backend..work` module
  path. Corrected invocation `python backend/.work/verify_phase3_compatibility.py`
  with repository PYTHONPATH passed. This was an invocation error, not platform failure.
- The first FULL smoke passed with the preexisting local APP_VERSION=0.2.0 override.
  Only that local setting was updated to 0.4.0 (credentials preserved), then the
  smoke was repeated to verify current application-version provenance.

Known visible upstream warnings: Starlette httpx deprecation, RDT sre_parse,
SDV metadata persistence recommendation (application metadata is already in JSON
manifests), CTGAN cuda alias deprecation, SciPy/NumPy scalar warning in existing
ECG processing, and SDMetrics warning about the 80/20 DCR size imbalance. These
were not hidden or reinterpreted as scientific evidence.

### Persistent FULL smoke evidence

Generation job `e2a2f608-9a2d-47a8-ab41-fd2c64a07c82`; evaluation `ebe06c18-d0a6-4006-82f2-2d27c871804d`.
Source SHA-256 `c4ea8807a68df2206dc900568b00d1ee162d70c983f8191ccc8a99bc3e89638a`.
Synthetic SHA-256 `d583c8b2307a271fe2d6d01368e153c886b005d1a3338d8438d874707608bc06`.

400 source rows, 320 training, 80 holdout, 400 requested/produced synthetic rows.
Schema, new identifier uniqueness, excluded-column absence, source/synthetic integrity
and all report hashes passed. Generation and evaluation both SUCCEEDED; evaluation
and report references survived a real API process restart. Model downloads remained
restricted. Reports use only modelled fields; no source records are embedded.

| Fidelity view | QualityReport aggregate | Column Shapes | Column Pair Trends |
| --- | ---: | ---: | ---: |
| training | 0.84960470 | 0.96023437 | 0.73897503 |
| holdout | 0.81091403 | 0.91187500 | 0.70995306 |

Exact training matches: 0/400, fraction 0.0; holdout matches 0. This is a diagnostic, not anonymity evidence.
DCR baseline: 0.62337643; synthetic median 0.07743904, random baseline median 0.12422517.
DCR overfitting: 0.375; closer to training 0.8125, holdout 0.1875. Ratio 4.0; ADVISORY_ONLY, gating_eligible=false. Complete training reference retained.
Default operational eligible ratio is [0.8,1.25] with minimum holdout 20,
explicit independence/group assessment and adequate reference sizes. These are
MedSynth Guard operational choices, not SDMetrics/scientific requirements.

DisclosureProtection against holdout: known age_group/sex, sensitive diagnosis_group, continuous=[], cap method, bins=10, FULL/one iteration; score 1, CAP protection 0.67138207, baseline protection 0.66666667. A score of one under this selected attack does not mean no disclosure risk.

| Binary readmitted utility | TRTR | TSTR |
| --- | ---: | ---: |
| f1 | 0.94117647 | 0.86666667 |
| accuracy | 0.93750000 | 0.85000000 |
| precision | 0.93023256 | 0.81250000 |
| recall | 0.95238095 | 0.92857143 |
| roc_auc | 0.96303258 | 0.94987469 |

F1 delta -0.07450980; TSTR/TRTR F1 ratio 0.92083333.
Real training/synthetic/holdout anonymous class counts: 119/201, 147/253, 38/42.
Both pipelines use the identical 80 real holdout rows only for prediction/scoring.
Actual binary/multiclass/regression fit instrumentation and Phase 3 synthesizer
fit spies passed: no real holdout reaches preprocessing/estimator/synthesizer fit.

Policy **Illustrative smoke policy**, version 1, hash `bda85fa403d89dd4320caefd8b7e936f6fbc13468233b52783fde9a11c094013`.
Illustrative only; no production default. Required structure equals true: PASS;
required holdout shapes minimum 0.0: PASS; required DCR overfitting minimum 0.0:
INSUFFICIENT_DATA due advisory methodology. Final **REVIEW_REQUIRED**. PASS means
configured policy compliance only, never anonymity/compliance/clinical approval.

| Evaluation artifact | ID | SHA-256 |
| --- | --- | --- |
| RELEASE_DECISION | `2dec9e74-0b2a-45c7-b5b0-836acdb52804` | `4c5447b13527ec017187bff32e78255fb591ba471abf26d1ec932ddd060e991a` |
| UTILITY_REPORT | `3e684d22-f114-4456-a09d-62bf98d0cc12` | `7a6ec376a4952979c863a565b9aa4e7918417fd4e99d8b70ab1718e6a3d17475` |
| PRIVACY_REPORT | `56040602-50fe-4c6b-ae31-267193d84b92` | `11f0b0b655d592497f6c504726eca0b17647d47f189fd34ca24abd61386122ec` |
| EVALUATION_MANIFEST | `966583f3-7279-4135-ac22-d01c454ddeaf` | `ce86555f8304a5423a079b31c604833be5fc0552768f6406acc51221f075d19f` |
| QUALITY_REPORT | `a2275622-43f9-430a-9629-3f073da511bb` | `bfc0cfad1bb7056adfc8454e5ad5f988749f61d363e8ab7da2c6df28c87c8518` |

Final manifest: application 0.4.0, Python 3.11.0, SDMetrics 0.32.0, sklearn 1.9.1,
NumPy 1.26.4, pandas 2.2.3, SDV 1.25.0. Git base commit
fc60aca8128f52cd6f595cc801cdc4626760bfae with dirty worktree explicitly recorded.
Evaluation duration 10.9901 s, real synthesis training 13.2337 s. No universal
score or clinical interpretation is derived from these operational timings.

### Worker, integrity and migration evidence

Two concurrent Worker instances returned [False, True]: one claim, one attempt,
one quality/utility execution audit set and five artifacts. Controlled storage
failure during privacy publication compensated the already-written quality bytes,
published no partial result and returned to QUEUED; second claim used a new token
and succeeded at attempt two.

A real evaluation worker was killed after QUALITY_EVALUATION_STARTED. Test forced
the persisted lease into the past after process death, recovered with a new token
at attempt two, rejected stale heartbeat/completion, then completed the actual
child/report workflow at attempt three after a controlled retry. This tests
recovery without waiting the normal 60-second lease. Timeout at one second
terminated computation, persisted EVALUATION_TIMEOUT and zero reports.

Source/synthetic/manifest mutations failed both submission and queued execution
with the corresponding integrity errors; deterministic failures stayed at one
attempt and published no reports. Actual artifact downloads checked hashes.
Clean base->0001_platform->0002_tabular->0003_evaluation upgrade, safe empty
0003->0002->0003 and base downgrade/upgrade passed in disposable PostgreSQL schemas.
Current/check report head/no drift. Policy SQL mutation and populated Phase 4
downgrade were rejected. Earlier migration files were not rewritten.

The duplicate-patient fixture had 51 overlapping groups in the original 320/80
row split. Leakage warning and advisory utility were verified; ROW_SPLIT provenance
remained unchanged, with no retrospective repair. Balanced 50/50 DCR test:
deliberately copied test-only training rows scored 0, the fitted Gaussian Copula
fixture scored higher; eligible methodology recorded. Constant-domain DCR NaN
was null/NOT_APPLICABLE. Estimated disclosure ran the real public API with 20-row
samples/two iterations and same-runtime seeded repetition passed.

An existing pre-edit Phase 3 job `cc00a960-7ce4-4da5-9620-cc979be43134` was evaluated
without regeneration: evaluation `0d99b2df-8793-4b01-8b2d-17dbcf8a4821` SUCCEEDED,
source unchanged, decision NOT_EVALUATED (no policy).

Existing final ECG smoke job `57e0fdad-d666-477e-aed8-e37433217f09` and tabular smoke
job `e7e962c8-fa45-48dc-b39e-c127b5af476d` SUCCEEDED with actual API restart.
Real ECG/imaging model and worker regressions passed; imaging remains Experimental
and production-blocked, genomics Unavailable.

### Same-input model comparison

Real Gaussian Copula, CTGAN and TVAE used the same fake source, 320/80 split,
FULL request (known age/sex, sensitive diagnosis_group, continuous age), binary
readmitted target and policy version. Neural fixtures used one epoch for
engineering validation, not quality benchmarking.

| Engine | Holdout shapes | Holdout pairs | DCR baseline | DCR overfitting | Disclosure | TSTR F1 | TSTR/TRTR F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| gaussian_copula | 0.911875 | 0.709953 | 0.686804 | 0.375000 | 0.940705 | 0.866667 | 0.920833 |
| ctgan | 0.873750 | 0.641478 | 0.871594 | 0.385000 | 1.000000 | 0.820000 | 0.871250 |
| tvae | 0.754687 | 0.579158 | 0.653287 | 0.435000 | 1.000000 | 0.674157 | 0.716292 |

TRTR F1 is 0.941176 for all three. DCR overfitting is advisory in all three.
Comparison demo policy requires structure only: all PASS, which is no claim
about privacy, fidelity or utility thresholds. Different policy versions and
source hashes were rejected. No winner/ranking/composite exists. Baseline DCR
values vary across runs because the upstream random baseline has no public seed hook.

### Security review, limitations and phase boundary

Reviewed production evaluation code, API, worker logging, report serialization
and UI/docs for unsupported safe/anonymous/100%/weighted-score claims: none added.
No patient-row logging, source-path exposure, public report URLs or arbitrary
serialized-object upload/deserialization was introduced. Reports are internal
sensitive source-derived artifacts; existing download checks and model restrictions
remain. Row/byte/encoded-cell/metric/timeout limits are enforced and persisted.

No formal differential privacy, anonymity or HIPAA/GDPR compliance guarantee.
No authentication/RBAC/tenant isolation; do not expose this as a public multi-user
healthcare service. Local artifact storage, single-table CSV evaluation only,
no free-text/multi-table evaluation or synthesis. Policies define thresholds,
not universal scientific standards. Pairwise fidelity does not prove full joint
equivalence. Some computations are explicitly bounded/subsampled/estimated.
DCR baseline lacks a public seed hook; cross-platform reproducibility is limited.
Original row-split group leakage is diagnosed, not corrected. Original pretrained
imaging provenance remains incomplete. No hard OS memory quota. Frontend DOM
contracts and real backend HTTP smokes passed; no visual browser certification
is claimed. Phase 5/enterprise/cloud/DP work has not started.

All mandatory Phase 4 acceptance criteria passed through the documented tests
and evidence. Tabular evaluation stays Beta because methodology/reporting
limitations and cross-runtime validation remain. READY FOR PHASE 5; no Phase 5
implementation performed.
