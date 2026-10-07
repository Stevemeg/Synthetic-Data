# Development

## Phase 5 development

Use migration head `0005_identity_tenancy`. Existing data is assigned to the deterministic development organization; migrations 0001-0004 and worker fencing remain intact. Root `VERSION` is the canonical release source (0.6.0); remove stale APP_VERSION overrides in existing ignored .env.

Frontend retains React/MUI and adds React Router. History routes require an SPA fallback on a future static host; Vite provides it locally. Playwright Chromium and axe are dev dependencies.

```powershell
.venv/Scripts/python.exe -m backend.scripts.product_smoke_test --start-services
.venv/Scripts/python.exe -m backend.scripts.create_demo_project
cd frontend
npm ci
npm exec -- playwright install chromium
npm test
npm run typecheck
npm run lint
npm run build
npm audit --audit-level=low
npm run test:e2e
npm run test:visual
# Requires local API + worker and generated demo bootstrap:
npm run test:live
```

The regular browser suite mocks the local application API with generated aggregates; the live suite uses the real local API/worker and verifies report bytes. Committed screenshot baselines target Windows Chromium. Use `npm exec -- playwright test product.spec.ts --update-snapshots` only after inspecting intentional changes. Ordinary verification compares existing baselines. Fixed viewports, timestamps, IDs and reduced motion stabilize fixtures. Runtime database state stays ignored. See UX.md, REPORTING.md, DEMO.md and PHASE_5_VERIFICATION.md.

The Phase 1 baseline gates were run before changes; see PHASE_2_VERIFICATION.md. BASELINE_AUDIT remains historical. Phase 2 replaces HTTP/persistence boundaries and retains scientific engines. Phase 3 extends this platform; see PHASE_3_VERIFICATION.md for the pre-modification Phase 2 checks and actual Phase 3 results.

## Dependencies and environment

Use Python 3.11 and a dedicated venv. Install backend/requirements-dev.txt plus requirements-ml.txt for all verified workflows. Root requirements forwards to backend/requirements.txt. Flask is not required. Werkzeug is dev-only for upload fixtures, not a server. Optional offline lab requirements remain.

Copy .env.example to ignored .env and set a new local POSTGRES_PASSWORD. Compose refuses empty passwords. DATABASE_URL overrides derived POSTGRES_* configuration and must use postgresql+psycopg. Never log connection strings. Entry points load .env without overriding existing environment variables.

Configuration:
- APP_ENV/HOST/PORT, CORS_ORIGINS, LOG_LEVEL.
- MAX_UPLOAD_MB, MAX_GENERATION_SAMPLES/IMAGES, MAX_SOURCE_ROWS, MAX_ECG_SEGMENTS.
- ECG_EPOCHS, ECG_SAMPLING_RATE, ENABLE_IMAGING_LAB, MODEL_DIR.
- DATABASE_URL or POSTGRES_DB/USER/PASSWORD/PORT.
- ARTIFACT_STORAGE_BACKEND (local or s3), ARTIFACT_STORAGE_PATH; see STORAGE.md for private bucket configuration and verified migration.
- JOB_POLL_INTERVAL, JOB_MAX_ATTEMPTS (1-5), JOB_LEASE_SECONDS, JOB_HEARTBEAT_SECONDS.
- APP_VERSION, optional APP_COMMIT (otherwise null).
- UPLOAD_DIR/GENERATED_DATA_DIR remain for offline compatibility.

## Run and migrate

From root:

```powershell
docker compose up -d postgres
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m backend.app
# Separate terminal:
.venv/Scripts/python.exe -m backend.worker
```

--once executes at most one claimed job. Graceful SIGINT/SIGTERM stops new claims and finishes current work; forced Windows termination can be abrupt. PostgreSQL and artifact bytes must both be retained.

Initial migration includes tables, indexes, foreign keys, checks, job-transition and immutable-audit triggers. API startup never runs migrations or create_all.

Only on a disposable database/schema:

```powershell
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m alembic downgrade base
.venv/Scripts/python.exe -m alembic upgrade head
```

Downgrade destroys records. Integration tests perform this in isolated schemas. alembic check verifies model drift; triggers are maintained explicitly.

## Checks

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m pytest -q -m integration
.venv/Scripts/python.exe -m pytest -q -m model
.venv/Scripts/python.exe -m compileall -q backend
.venv/Scripts/python.exe -m ruff check backend
.venv/Scripts/python.exe -m ruff format --check backend
.venv/Scripts/python.exe -m pip check
.venv/Scripts/python.exe -m backend.scripts.platform_smoke_test --start-services
.venv/Scripts/python.exe -m backend.scripts.tabular_smoke_test --start-services
cd frontend
npm ci
npm run typecheck
npm run lint
npm run build
```

Default suite excludes model/integration tests. PostgreSQL tests create/drop random schemas in TEST_DATABASE_URL or the configured database. The role needs schema/function privileges. Model tests include tiny one-epoch ECG training and real ECG/imaging worker persistence. Large models are not trained.

Smoke uses invented input, genuine HTTP and separate processes, and retains a fixture project/artifacts for inspection. --start-services verifies actual API restart. The old smoke_test module delegates to it. Known SciPy/NumPy model warnings are not suppressed. Windows can deny symbolic-link creation; the OS-dependent test explicitly skips then.

## Maintenance

```powershell
.venv/Scripts/python.exe -m backend.scripts.reconcile_storage
# Stop all API/workers before applying:
.venv/Scripts/python.exe -m backend.scripts.reconcile_storage --apply
```

Default is count-only and considers unreferenced objects older than 24 hours. Stop all writers before applying because DB scan and filesystem deletion are not atomic. Ignored backend/.work may retain abandoned crash workspaces; inspect before manual cleanup. No scheduled retention, secure erasure or backup orchestration exists.

Do not commit source data, secrets, outputs, learned weights, logs or database volumes. Preserve original model hashes. Official HTTP is /api/v1 on FastAPI; old synchronous Flask routes are removed. GenerationService and dataclass interfaces, existing config import, and offline CLI wrappers remain. Offline outputs are not automatically platform records.

The frontend dependency audit initially reported 17 advisories. Compatible dependency updates were applied, and the final audit result is recorded in PHASE_2_VERIFICATION.md. Failed internal .write_ storage temporaries are excluded from the object reconciliation tool and require operator inspection after writers stop.

API shutdown disposes its pools. Workers keep session ownership locks on dedicated connections, and release/invalidate those connections after each attempt. Statement/lock/idle-transaction timeouts bound ordinary DB stalls. Machine clocks and local storage must be managed consistently; distributed partition behavior has not been certified.

## Tabular development

Install backend/requirements-tabular.txt for Phase 3. The old tabular-lab group
forwards to it without duplicated pins; existing numerical/ECG versions remain.
Configuration adds TABULAR_MAX_SOURCE_ROWS/COLUMNS/GENERATED_ROWS,
TABULAR_MAX_TRANSFORMED_CELLS,
CTGAN_MAX_EPOCHS/TVAE_MAX_EPOCHS, CTGAN_WARNING_MIN_ROWS/TVAE_WARNING_MIN_ROWS,
and TABULAR_JOB_TIMEOUT_SECONDS. See TABULAR_SYNTHESIS.md for exact defaults.

Migration 0002_tabular upgrades the established 0001_platform schema without
editing history or removing ECG/imaging records. Downgrade is supported only
before tabular jobs/artifacts exist; it refuses destructive removal otherwise.
Disposable-schema tests cover base->0001->0002, 0002->0001->0002 and drift checks.

Frontend `npm run test` runs Vitest 4.1.11 with jsdom and Testing Library: role/type/
annotation edits, protected free text, preflight gating, engine configuration,
submission payload, factual run display and downloadable/restricted artifacts.
These DOM tests mock HTTP transport; real backend generation is separately tested.
They are not a visual browser certification. The current browser connector exposed
no browsers for an interactive walkthrough during Phase 3 verification.

## Phase 4 development

Install `backend/requirements-evaluation.txt` (forwards tabular and existing ML
groups; pins SDMetrics 0.32.0 without changing existing numerical dependencies).
scikit-learn remains 1.9.1 in requirements-ml.txt. Run Alembic upgrade head to
0003_evaluation. This new migration preserves 0001_platform/0002_tabular history,
adds policy/evaluation references and constraints, and supports empty-schema
downgrade to 0002. It refuses downgrade if evaluation/policy data would be lost.
Real PostgreSQL tests cover clean upgrade, safe downgrade/upgrade, immutability,
publication invariants and model drift.

Run all commands above plus:

```powershell
.venv/Scripts/python.exe -m backend.scripts.evaluation_smoke_test --start-services
.venv/Scripts/python.exe -m alembic current
.venv/Scripts/python.exe -m alembic check
cd frontend
npm test
npm audit --audit-level=low
```

EVALUATION.md documents exact operational configuration defaults/bounds; .env.example
contains the matching variables. Requests snapshot limits, seeds and policies.
DCR random baseline has no public upstream seed hook and may vary across reruns.

Model tests run actual QualityReport/DCR/disclosure and binary/multiclass/regression
pipelines; fit instrumentation checks holdout isolation. Integration tests use
real workers/PostgreSQL for FULL evaluation, two-worker contention, storage retry,
actual worker death during quality, token fencing, timeouts, immutable policies,
input integrity, API persistence and compatible three-engine comparison.
Frontend DOM tests exercise requests and independent result/policy/comparison
rendering with mocked HTTP; they are not visual browser certification. The smoke
uses separate HTTP API/worker processes and actual API restart. All fixtures are
invented engineering data, not clinical observations. See PHASE_4_VERIFICATION.md.

## Phase 6 security and operations

See [authentication](AUTHENTICATION.md), [authorization](AUTHORIZATION.md),
[tenancy](TENANCY.md), [storage](STORAGE.md), [data lifecycle](DATA_LIFECYCLE.md)
and [actual verification](PHASE_6_VERIFICATION.md). Protected API resources require
a revocable application session and selected organization membership. Mutations
require X-CSRF-Token and an allowed Origin; X-Organization-ID selects a membership.
Unauthorized foreign resources return 404; role denial returns 403; no session
returns 401. Reports remain private and HTML-escaped. Existing trained-model
download restrictions remain. Production startup rejects insecure defaults.
