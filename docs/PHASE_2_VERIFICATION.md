# Phase 2 verification record

Before Phase 2 modifications, the six required Phase 1 documents and repository
structure were reviewed. Existing changes were retained as the working baseline.

Baseline gates executed with `.venv/Scripts/python.exe` on Windows:

- `-m pytest -q`: 88 passed, 10 model tests deselected.
- `-m pytest -q -m model`: 10 passed, 88 deselected; 5 known numerical-library warnings.
- `-m compileall -q backend`: passed.
- `-m ruff check backend`: passed.
- `-m ruff format --check backend`: 47 files already formatted.
- Frontend `npm run typecheck`, `npm run lint`, `npm run build`: passed.

Docker was installed but stopped. Docker Desktop was started for genuine
PostgreSQL verification. Final Phase 2 results are recorded below after execution.

## Phase 2 final results

Executed with the repository virtual environment on Windows, real PostgreSQL 16
in Docker Desktop, and the frontend lockfile. No SQLite or fake generation
replacement was used.

| Command / check | Actual result |
| --- | --- |
| `python -m pytest -q` | 124 passed, 1 explicitly skipped, 37 deselected |
| `python -m pytest -q -m model` | 14 passed, 148 deselected |
| `python -m pytest -q -m integration` | 27 passed, 135 deselected |
| `python -m pytest -q -m model backend/tests/test_platform_models.py` | 4 passed after adding queued-job restart continuation |
| `python -m pytest -q -m integration backend/tests/test_platform_integration.py` | 23 passed after final stale-lease cleanup change |
| `python -m compileall -q backend` | Passed |
| `python -m ruff check backend` | Passed |
| `python -m ruff format --check backend` | 95 files already formatted |
| `python -m pip check` | No broken requirements found |
| `alembic upgrade head / downgrade base / upgrade head` | Passed on the initially empty development DB; also tested in disposable schemas |
| `python -m alembic current` | 0001_platform (head) |
| `python -m alembic check` | No new upgrade operations detected |
| `npm ci` | Passed with updated lockfile |
| `npm run typecheck` | Passed |
| `npm run lint` | Passed |
| `npm run build` | Passed, Vite 7.3.6; final JS artifact approximately 491.41 kB |
| `npm audit --audit-level=low` | Found 0 reported vulnerabilities |
| `python -m backend.scripts.platform_smoke_test --start-services` | Passed real API, separate worker, artifact retrieval and actual API process restart |
| `python -m backend.scripts.reconcile_storage` | Dry run: 0 old unreferenced objects, 0 deleted |
| Original/local model hashes | All seven SHA-256 values match BASELINE_AUDIT |
| Repository data hygiene | No tracked or unignored candidate source CSV, generated NPZ/PT, environment secret or log files |
| `git diff --check` | Passed; only normal Windows LF/CRLF notices |

Here `python` means `.venv/Scripts/python.exe`. Integration/model selections
overlap in four real worker tests; counts must not be added as distinct totals.
The one skipped unit test requires OS symbolic-link creation privileges, which
this Windows session does not grant. Traversal/canonical-key/boundary validation
tests still ran. Starlette's httpx TestClient deprecation and five known
SciPy/NumPy scalar-conversion deprecations remain visible; they are not hidden.
Alembic's path-separator warning was fixed.

## Platform evidence

- Health returns 200 while an unavailable database causes readiness 503. Genuine
  migrated PostgreSQL and writable storage return readiness 200.
- Two concurrent claim attempts for one queued job produce exactly one owner.
  A separate real-engine test starts two workers and confirms one execution,
  attempt_count=1 and one successful artifact set.
- Concurrent equivalent submissions with the same project/key produce one job.
  Replays return the same ID; differing requests conflict; another project may
  reuse the key.
- Live advisory ownership prevents another worker stealing an expired lease.
  Released/expired ownership is recovered with a new claim token; stale tokens
  cannot heartbeat or publish. Exhausted abandoned work becomes FAILED.
- Transient retries are bounded; permanent failures do not loop. A real flat ECG
  input reaches FAILED after one attempt with no published artifacts.
- Project/dataset/queued-job state survives recreating services. The real ECG
  test restarts HTTP before processing, then completes the pending workflow,
  then restarts again and retrieves persisted artifacts.
- Real ECG produces exactly two normalized unlabeled sequences of shape (2,96),
  a full restorable checkpoint, and run_manifest.json. Downloaded bytes match
  stored SHA-256 and size. Checkpoint HTTP download is restricted; tampered
  dataset bytes are rejected.
- A worker with changed sampling-rate/epoch/count-limit settings still uses the
  job's scientific configuration snapshot. Runtime versions are recorded.
- Real imaging worker inference produces two PNGs in a valid archive and an
  Experimental manifest identifying/hash-checking the loaded checkpoint.
- Unsupported tabular/genomic generation remains unavailable. Imaging is
  default-disabled and blocked in production configuration.
- Database transition/count constraints and audit immutability reject invalid
  direct SQL operations; migration downgrade/upgrade really executes.

Latest successful live smoke job:
`ed021aa4-5c87-4b50-85f8-752a63c38b63`, SUCCEEDED, requested=2,
produced=2, three artifacts. Smoke fixtures are invented signals, retained in
ignored local storage and PostgreSQL for review, not committed patient data.
Smoke API/worker processes were stopped; the persistent PostgreSQL development
container remains running.

The first live smoke completed generation/restart but failed Windows temporary
log cleanup. Process-tree shutdown was fixed and subsequent complete runs exited
successfully. Initial npm ci reported 17 advisories; compatible updates and a
fresh install/build/audit resolved all currently reported frontend advisories.

## Remaining limits

Authentication/tenant authorization, remote storage, automated retention, secure
erasure, and clinical/privacy/utility evaluation are absent. Running cancellation
is unsupported. Filesystem/database commits are not atomic; uncertain/crash
orphans require documented maintenance. Test success is not a deployment or
privacy certification. No browser UI automation or cross-platform certification
is claimed. Original checkpoint training provenance/licensing remains incomplete.

All Phase 2 acceptance criteria were satisfied by the implementation and checks
above. Phase 3 may begin as a separate authorized phase; it was not started here.
