# Phase 3 verification

## Phase 2 baseline, before repository modifications

Reviewed README, ARCHITECTURE, PRODUCT_SCOPE, PRIVACY_MODEL, DEVELOPMENT, API,
JOB_LIFECYCLE, ARTIFACT_MODEL, PHASE_2_VERIFICATION and ADR-0001 through 0005;
inspected routes, schemas, repositories, migration, worker supervision, storage,
provenance, audits and frontend. Existing uncommitted Phase 1/2 work was preserved.

All Python commands use `.venv/Scripts/python.exe` (Python 3.11.0).

| Command | Actual result |
| --- | --- |
| `python -m pytest -q` | 124 passed, 1 OS symlink privilege skip, 37 deselected |
| `python -m pytest -q -m model` | 14 passed, 148 deselected, 150.24 seconds |
| `python -m pytest -q -m integration` | 27 passed, 135 deselected, 168.34 seconds |
| `python -m compileall -q backend` | Passed |
| `python -m ruff check backend` | Passed |
| `python -m ruff format --check backend` | Passed, 95 files |
| `python -m pip check` | No broken requirements |
| `npm ci` | Passed, 267 packages, 0 reported vulnerabilities |
| `npm run typecheck` | Passed |
| `npm run lint` | Passed |
| `npm run build` | Passed, Vite 7.3.6, 960 modules |
| `python -m backend.scripts.platform_smoke_test --start-services` | Passed: real ECG, hashes, manifest, restricted checkpoint, API restart |
| `python -m alembic current` | 0001_platform (head) |
| `docker compose ps` | PostgreSQL 16 healthy, loopback port 55432 |

Docker Desktop was initially stopped. Initial smoke failed readiness and initial
DB-dependent runs encountered unavailable PostgreSQL. Docker Desktop was started
and `docker compose up -d postgres` reused the existing volume. The complete
model/integration/smoke runs above subsequently passed before any repository edit.
No Phase 2 code regression was found. Known Starlette and SciPy warnings remain.
Baseline smoke job: `0aabc303-2612-444a-9b92-f8a85a3c0af0`, SUCCEEDED, 2/2,
three artifacts; fixture is invented ECG, not patient data.

The SDV stack was absent from the runtime; the offline lab had pinned SDV 1.25.0.
`pip index versions sdv/rdt/ctgan` inspected available releases; a dry run for
SDV 1.25.0, RDT 1.18.2, CTGAN 0.11.1 required no existing numerical/ML upgrades.

## Phase 3 final results

Verified locally on 2026-10-02, Windows, Python 3.11.0, Node 24.18.0,
PostgreSQL 16. All Python commands below use `.venv/Scripts/python.exe`; npm
commands run in `frontend`. Model/integration markers overlap: do not add their
counts to the default suite as if they were distinct tests.

| Command | Final observed result |
| --- | --- |
| `python -m pytest -q` | 154 passed, 1 OS symlink privilege skip, 50 deselected; 28.67 s |
| `python -m pytest -q -m model` | 24 passed, 181 deselected; 167.31 s |
| `python -m pytest -q -m integration` | 34 passed, 171 deselected; 171.56 s |
| `python -m compileall -q backend` | Passed |
| `python -m ruff check backend` | Passed |
| `python -m ruff format --check backend` | Passed, 108 files |
| `python -m pip check` | No broken requirements |
| `python -m alembic upgrade head` | Development database upgraded 0001_platform to 0002_tabular |
| `python -m alembic current` | 0002_tabular (head) |
| `python -m alembic check` | No new upgrade operations detected |
| `npm ci` | Passed, 343 packages, 0 vulnerabilities |
| `npm run typecheck` | Passed |
| `npm run lint` | Passed |
| `npm run build` | Passed, Vite 7.3.6, 961 modules; JS 504.13 kB, gzip 160.47 kB |
| `npm test` | 2 DOM workflow tests passed, Vitest 4.1.11; latest run 72.22 s |
| `npm audit --audit-level=low` | 0 vulnerabilities |
| `python -m backend.scripts.platform_smoke_test --start-services` | Passed: real ECG 2/2, 3 artifacts, hashes, restricted checkpoint, actual API restart |
| `python -m backend.scripts.tabular_smoke_test --start-services` | Passed: real Gaussian Copula 50/50, 4 artifacts, hashes, restricted model, actual API restart |
| `python -m backend.scripts.reconcile_storage` | Dry run: 0 old unreferenced objects, 0 deleted |
| `git diff --check` | Passed; Windows LF/CRLF conversion notices |

The last code addition was best-effort Git commit/dirty-worktree provenance.
After the full suites above, its focused platform unit suite and a fresh-process
tabular smoke were rerun. Documentation-only edits followed verification.

### Focused tests and corrected intermediate failures

| Command or check | Observed result/history |
| --- | --- |
| `python -m pytest -q backend/tests/test_tabular.py` | Final 30 passed; initial complex-numeric inference failure corrected |
| `python -m pytest -q -m model backend/tests/test_tabular_models.py` | Initial 4 passed; expanded to 6 real-model cases, all passed in final model suite |
| `python -m pytest -q -m integration backend/tests/test_tabular_integration.py` | Initial 6 failed/1 passed from NumPy bool JSON encoding; corrected, then 7 passed; expanded to 8 cases, all passed in final integration suite |
| `python -m pytest -q -m integration backend/tests/test_tabular_integration.py::test_required_structural_failure_is_permanent_and_reports_facts` | 1 passed, 17.11 s |
| `python -m pytest -q backend/tests/test_platform_unit.py` | 54 passed, 1 OS symlink privilege skip after Git provenance addition |
| Default unit suite during implementation | One non-tabular default-configuration round-trip regression corrected; final 154 passed |
| Alembic first upgrade attempt | Failed on double-prefixed constraint name; corrected using `op.f`, then upgrade/drift/downgrade tests passed |
| Final frontend `npm ci`, first attempt | Windows EPERM because this session's Vite/esbuild process held its executable; stopped that verified process and clean install passed |
| Initial Vitest dependency installation/audit | Older Vitest patch had 1 moderate/1 critical advisory; upgraded only Vitest to 4.1.11; final audit 0 |
| Fresh smoke manifest inspection | Detected earlier frontend-session worker had claimed a smoke job using stale code; stopped this session's API/worker and repeated with fresh processes |

Dependency checks included `pip index versions sdv`, `pip index versions rdt`,
`pip index versions ctgan`, an install dry run, installation through
`backend/requirements-tabular.txt`, installed distribution version/signature/source
inspection, and `pip check`. Compatible direct pins: SDV 1.25.0, RDT 1.18.2,
CTGAN 0.11.1, Copulas 0.14.1. Existing NumPy 1.26.4, Pandas 2.2.3 and
PyTorch 2.10.0 were retained. Public metadata detection/update/validation and
public synthesizer fit/sample/save/load APIs were verified against this installation.
The isolated, version-guarded private random-state bridge is documented in
TABULAR_SYNTHESIS; SDV 1.25.0 does not expose a public seed setter.

### Real model and platform evidence

Each engine actually fitted the invented clinical fixture's 80-row training
partition and generated 15 records. Tests observed the real fit input to verify
that holdout positions, identifiers and clinical notes never reached fitting.
Gaussian Copula, CTGAN and TVAE all passed schema/ID checks, model serialization,
same-runtime seeded sampling, different-seed sampling and checksum rejection
before loading a tampered model. Each also passed fresh CPU fit repeatability.
Neural tests used one epoch, batch size 20, embedding 16 and 32-unit dimensions;
these tests establish integration, not clinical fidelity or model superiority.

PostgreSQL tests ran two actual workers against one Gaussian Copula job: one
claim, one attempt, one training stage, one model and one four-artifact set.
Publication failure after partial filesystem writes was compensated: attempt 1
published no successful output; attempt 2 used a new claim token and succeeded.
Invalid metadata was not queued/retried. Source corruption was rejected before
submission and before fitting. An actual worker was terminated during CTGAN
training, its lease advanced to expiry, and recovery produced a fresh second
claim; stale heartbeat and completion were rejected. A one-second timeout killed
the supervised child with no published outputs. Required structural-rule failure
was permanent, preserved row-free violation counts and published no outputs.

Migration tests built the clean schema (Phase 1 had no PostgreSQL migration),
upgraded through 0001_platform to 0002_tabular, safely downgraded an empty Phase 3
schema to 0001 and upgraded again, and checked migration drift. Populated Phase 3
downgrade is intentionally rejected to avoid destroying records.

Latest ECG smoke job: `5d4efc7e-80b3-49be-8111-878fe809e8e4`, SUCCEEDED, 2/2.
Existing ECG and Imaging model/regression tests passed in the complete suites;
Imaging remains Experimental and Genomics unavailable. Seven original model
files were separately SHA-256 checked against the recorded baseline: all matched.
The pre-Phase-3 ECG idempotency request was replayed through HTTP and returned the
same baseline job with status 200, without retraining.

### Final fresh-process tabular smoke

Job `fd995ca7-f8d1-4026-a0a0-611fb2384268`, project
`edcd7237-c4e9-4c97-9b5c-f8ef1fa2ef44`, dataset
`d53ba7b7-bfff-4cfa-b5e1-1eb94ed7cce8`:

| Fact | Actual result |
| --- | --- |
| Source / training / holdout rows | 100 / 80 / 20 |
| Requested / produced rows | 50 / 50 |
| Source / modelled / excluded columns | 9 / 7 / 1, plus one identifier |
| Schema / identifier uniqueness / download hashes | PASS / PASS / PASS |
| Exact training-row matches | 0, fraction 0.0; diagnostic only |
| State / artifacts | SUCCEEDED / 4 |
| Training / sampling / child duration | 4.3420 / 0.0605 / 4.4537 seconds, CPU |
| Parent run duration | 6.7282 seconds |
| API restart persistence | Passed |
| Application identity | 0.3.0; HEAD fc60aca8128f52cd6f595cc801cdc4626760bfae; dirty worktree true |

Source SHA-256:
`29d5d2c5463aa54dd75777f97e0976248704b6d85655c5f4eecb694916b70131`.

| Artifact | ID | SHA-256 |
| --- | --- | --- |
| SYNTHETIC_DATASET | 6699d2e6-72ef-4712-a7af-1f9412697028 | d4d7ad92b38849d9c02cf7bf0b43032b3effe325ff3d15c20f13e99317615387 |
| SYNTHESIS_MODEL | ba6d9937-3034-489f-a948-ad671d3381eb | 8af13eb9fafe0566913c4809b67d05f8d96c5fc64faa65be3e2ac6ed2ac0ddc6 |
| RUN_METADATA | 7174a3af-17f7-46b0-8528-05afe15315dc | 2692116464d4ac5544727b5bc88e5abed1b76fb378732d23f12ca28181d0fbe8 |
| STRUCTURAL_VALIDATION_REPORT | dbd4242e-4c68-4d8e-9a91-c7f410489f35 | 015e00e52a522656feae77953c6b1919f96b75906136435f6e8537919badc510 |

The final manifest was additionally read from the trusted artifact store and its
SHA-256, application version, available Git identity/dirty flag and source hash
independently checked: PASS. The old local worker's earlier successful run is
not used as evidence for this final provenance addition. Model downloads remain
403; model bytes/hash are tested internally rather than exposed by HTTP.

### Frontend and limitations

Two Vitest/jsdom tests exercise the real React components with mocked HTTP
transport: preflight gating, role/type/annotation changes, locked free-text
exclusion, neural configuration submission, factual job metadata, dataset
download and model restriction. These complement the real HTTP/API/worker tests.
The computer-use connector reported no available browser, so no visual browser
walkthrough is claimed. Build emits the existing-style Vite chunk-size advisory
at 504.13 kB; upstream Starlette, SciPy/NumPy, RDT and SDV/CTGAN warnings remain.

No formal privacy evaluation, differential privacy, statistical-quality release
gate, ML utility evaluation, multi-table or free-text synthesis is implemented.
No authentication or tenant authorization exists: do not deploy as a public
multi-user healthcare service. Storage is local. Model reuse is explicitly
deferred; internal trusted loading is checksum guarded, and no model upload or
model download endpoint was added. GPU/cross-runtime determinism is best-effort.
Resource boundaries are operational source/column/generated-row/epoch/estimated
transformed-cell/time limits, not a hard OS memory quota. Row-level splitting
does not separate repeated patients without an explicit future grouping policy.
Identifiers are unique within each artifact and avoid source identifiers, but
may repeat across independently generated artifacts. Abrupt worker death may
leave temporary directories for maintenance; orphan reconciliation is preserved.
The working tree includes preserved uncommitted Phase 1/2 work; a recorded Git
HEAD plus dirty flag is not an immutable release identity for those edits.
