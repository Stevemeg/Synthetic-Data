# Phase 6 verification

Status: PHASE 6 NOT COMPLETE as a release gate. Local implementation and engineering verification are complete; remote CI execution and explicit review of unfixed High container advisories remain pending. No release-candidate designation is made.

## Phase 5 baseline before modification

2026-10-05, Windows, Python 3.11.0 (.venv), Node 24.18.0, npm 12.0.2, PostgreSQL 16.15, Chromium 153. Reviewed the requested documentation/ADRs and application, repository/query, report, worker, claim/lease/token, storage, frontend and Compose boundaries. No CI or production Dockerfiles existed. Inherited uncommitted work was preserved.

| Command | Actual result |
| --- | --- |
| pytest -q | 170 passed, 1 Windows symlink privilege skip, 70 deselected; 15.60s |
| pytest -q -m model | 33 passed, 208 deselected; 264.27s |
| pytest -q -m integration | 46 passed, 195 deselected; 329.75s |
| compileall / Ruff check / Ruff format check | Passed; 131 Python files formatted |
| pip check | No broken requirements |
| Alembic current / check | 0004_governance_reports head; no drift |
| npm ci | Passed; 337 packages added, 338 audited; local npm blocked esbuild postinstall, platform binary/build still worked |
| npm test | 11 passed in 2 files; 76.65s |
| typecheck / lint / build | Passed; build 7.66s, initial JS 475.51 kB, gzip 155.86 kB |
| npm audit --audit-level=low | 0 vulnerabilities |
| product browser E2E | 9 passed; 1.4m |
| visual/accessibility/responsive | 3 passed; 12 baseline image comparisons, axe and overflow checks at 1440/1024/768 × 1000; 36.7s |
| live browser API/worker workflow | 1 passed; 52.4s; actual generation, evaluation and downloaded report digest |
| platform smoke --start-services | Passed: ECG 2 outputs, 3 artifacts, hashes, API restart |
| tabular smoke --start-services | Passed: 50 outputs, 4 artifacts, hashes, API restart |
| evaluation smoke --start-services | Passed: 400 outputs, 9 artifacts, Full evidence, API restart |
| product smoke --start-services | Passed: 400 outputs, 10 artifacts, report and API restart |

Baseline product report c8c95729-7ad2-4240-be9f-bbf1e8524c2d: 25,883 bytes; SHA-256 acc7701dafbd1fdef4435df4232ff0562cbac8fa5bef90b67452edb9eacf9413. Decision Review required under illustrative policy. All fixtures are programmatically generated fake data. Existing upstream deprecation/methodology warnings remain.

## Implemented architecture

React/TypeScript/Material UI with OIDC identity and organization selection -> FastAPI authentication/authorization -> PostgreSQL and private S3-compatible storage -> the existing durable PostgreSQL queue/worker. Provider-neutral Authlib OIDC Code/S256 PKCE validates discovery/issuer/subject/signature/audience/expiry/state/nonce. PostgreSQL stores externally verified users, revocable opaque application sessions, Organizations and Owner/Editor/Viewer memberships. Server-side query criteria scope projects and descendants; foreign UUIDs return 404, insufficient roles 403, missing sessions 401. No RLS or custom identity protocol was introduced.

The migration adds revision 0005 without changing history 0001-0004. Existing claims, advisory locks, leases, tokens, heartbeats, supervised timeouts, fenced publication, integrity checks and scientific methodologies remain. S3 uses private generated keys, conditional immutable writes and byte-based SHA-256/size checks, independent of ETag. Downloads authorize first and stream the exact verified spool. No source preview, arbitrary model upload, public report or permanent object URL exists.

Manual retention is persisted. Owner exact-name project deletion progresses ACTIVE -> DELETION_REQUESTED -> PURGING -> DELETED through background cleanup; metadata/provenance/audit remain and descendants become inaccessible. No automatic expiry or physical erasure is claimed. Local artifacts remain supported for tests; the verified offline migration retains originals and rollback mappings and refuses to republish deletion tombstones.

## Local final quality gates

| Command / gate | Actual result |
| --- | --- |
| python -m pytest -q | 183 passed, 1 Windows symlink privilege skip, 75 deselected; 36.97s |
| python -m pytest -q -m model | 33 passed, 225 deselected; 151.96s |
| MEDSYNTH_S3_TEST=1 python -m pytest -q -m integration | 51 passed, 207 deselected; 337.30s; real PostgreSQL and MinIO |
| Targeted identity/IDOR/role tests | 3 passed; 35.42s; included in integration suite |
| Targeted S3 integrity/migration/workflow/deletion | 2 passed; real private S3-compatible buckets; included in integration suite |
| Report regression after adding build timestamp provenance | 2 passed; 38.13s; no recomputation, escaped injection, source/path absence and digest checks |
| compileall / Ruff check / Ruff format | Passed; 158 Python files formatted |
| pip check | No broken requirements |
| Alembic current / check | 0005_identity_tenancy head; no new upgrade operations |
| Clean migrations / populated upgrade | Passed; original 0001-0004 history preserved |
| npm ci | Passed; 337 added, 338 audited, zero vulnerabilities; npm policy blocks esbuild postinstall but platform binary/build works |
| npm test | 14 passed in 4 files; 11.03s on final loading-label update |
| npm run typecheck / lint | Passed |
| npm run build | Passed; 4.63s; largest JS chunk 306.73 kB, gzip 94.38 kB |
| npm audit --audit-level=low | Zero findings |
| product E2E | 9 passed; 1.2m, including 3 visual/resource and 3 keyboard/form responsive tests |
| visual regression | 12 reviewed comparisons, four pages at 1440/1024/768 x 1000; no unexplained differences |
| real OIDC authentication E2E | 1 passed; 17.3s; actual Keycloak, sign-in/out, session denial, organization switch, foreign deep link, viewer mutation denial, CSRF and axe at all three widths |
| authenticated S3 live browser workflow | 1 passed; 1.4m; generated fake fixture, reviewed generation, Full evaluation, explicit disclosure/TSTR, policy reasons, report download SHA/size, deep-link reload, actual API+worker restart |
| Docker builds | API, worker and static frontend built successfully; non-root 10001/10001/101 |
| Local Compose | PostgreSQL, private MinIO fixture, Keycloak, API, worker and static frontend running; readiness/API/frontend/storage health checks passed |
| GitHub workflow syntax | actionlint passed locally; remote Actions run NOT executed |
| pip-audit / Bandit | Zero findings; upstream deprecation/redundant nosec warnings disclosed |
| Gitleaks | Gitleaks 8.30.1: zero leaks in history and final 327-file nonignored working tree export; generated local secrets remain ignored |
| Trivy / SBOM | Full API/worker/frontend JSON scans and CycloneDX SBOM generated; remaining findings below |

Test groups overlap (some evaluation model tests carry both model/integration markers); do not add suite counts as distinct tests. Upstream Authlib/Starlette HTTPX, RDT, SDV/CTGAN and SciPy warnings remain. Windows symlink privileges caused the single existing skip; it is not reported as passed.

## Baseline data and object migration

`verify_identity_migration` compared IDs/counts on the populated Phase 5 database: 31 projects, 31 datasets, 49 generation jobs, 14 evaluations, 9 policies, 204 artifacts and 621 audit records preserved. All projects received the deterministic development Organization; historical actors remain historical. The immutable organization relationship and composite same-project constraints are retained. The identity/lifecycle downgrade refuses destructive data loss.

Offline LocalArtifactStore -> S3 migration copied and verified 235 registered source/artifact references before updating storage references. Rollback mappings were flushed before database updates and local originals retained. S3 integration tests verified repeat invocation, original SHA after copy/download, conditional overwrite rejection, anonymous reads denied and tombstone anti-resurrection.

## Backup/restore rehearsal

The final real PostgreSQL pg_dump/pg_restore round trip retained all ten table counts: 47 projects, 39 datasets, 71 jobs, 24 evaluations, 15 policies, 310 artifacts, 2 Organizations, 3 memberships, 2 users and 952 audit events. The backup was 428,796 bytes. All 349 active restored source/artifact references matched available private S3 byte sizes and SHA-256 hashes. Restoration used a new random disposable database, which was removed afterward; the live database was not overwritten. This is not a destroyed-object-store/IdP recovery test or an RTO/RPO guarantee.

## Tenant and role matrix

Two users/two Organizations were tested on real PostgreSQL. Organization B included a real generated tabular dataset, successful generation, Full evaluation, policy, reports and artifacts; requests from Organization A with swapped UUIDs returned 404 for project/dataset/run/evaluation/policy/report/artifact metadata/download, nested artifact/report lists, preflight, schema update, submission/model reuse, evaluation/report creation, comparison, cancellation and deletion. Scoped inventory/activity lists returned zero B resources. Selecting a foreign Organization without membership returned 403.

Viewer reads and permitted report/synthetic downloads succeeded; viewer writes failed 403 with otherwise valid CSRF. Editor preflight/schema/workflow/report actions succeeded, while policy administration/destruction/membership actions failed. Owner administration succeeded, incorrect deletion confirmation returned 422, and removal/demotion of the last Owner returned 409. Foreign deletion failed. Queued work is blocked during deletion. Database composite FKs rejected a manipulated cross-project reference, and a deliberately tampered detached worker claim failed TENANT_INVARIANT_FAILED without publication.

Backend tests establish roles authoritatively. Browser tests use real provider sign-in: User B's project is hidden from A's first organization; A can explicitly switch to its Viewer membership in B's organization, which clears old project context and disables creation. Direct mutation still returns 403. Application logout deletes the persisted session; the old copied cookie cannot restore access. Provider SSO logout is separate and sign-in requests prompt=login.

## Security and operational verification

Production configuration rejects development auth/debug/local storage, wildcard or malformed CORS, absent identity/session/metrics settings, short/weak signing secret, common/default database credentials and non-HTTPS browser/identity/storage URLs. Browser cookies are HttpOnly/SameSite=Lax and Secure in production; the local fixture intentionally uses loopback HTTP. CSRF requires a session-bound header plus explicitly allowed Origin. React rendering and HTML reports escape names/reasons; reports use restrictive CSP and no scripts/remote resources. API/proxy headers, upload bounds, model download restrictions and internal metrics boundaries remain. No public HTTPS deployment or penetration test was performed.

Production-format logs whitelist safe IDs/status/durations; arbitrary third-party message text and exception payloads are omitted. Actual container verification observed positive HTTP/storage counts, persisted queue gauges, worker claims/execution, correlated authenticated requests and job context, and no configured secret values in captured logs (224 correlated authenticated requests, 36 worker job-context records, 341 JSON records captured before restart). Unit tests also inject known fake secrets/patient values into log and unexpected-error paths and verify sanitization. Metric labels use bounded route templates/method/status/operation/kind, never names/emails/row values. Worker metrics are collected from their own private process, not incorrectly attributed to API counters. OpenTelemetry tracing is deferred.

All four existing --start-services smoke workflows passed again against private S3-compatible storage: platform ECG (2 outputs/3 artifacts), tabular (50 outputs/4 artifacts), evaluation (400 outputs/9 artifacts) and product/report (400 outputs/10 artifacts). They verified registered hashes and actual API restart persistence. These legacy smoke invocations explicitly use development bypass and are not presented as authenticated evidence. The separate real OIDC browser workflow covers authenticated container operation and restart with the same report digest.

Final legacy product smoke report: 25,893 bytes; SHA-256 21ed9e9b3158dda813e9f2a99fc7ab70dc1276fc23ee400b14b3b4bf282d724f. Its illustrative policy decision was Review required. Reporting still uses persisted results and does not recompute metrics.

Reliability tests preserve concurrent SKIP LOCKED/advisory ownership, lease/token fencing, stale claim and evaluation crash recovery, retries/timeouts, storage compensation, and restart persistence. Local filesystem orphan reconciliation remains tested; S3 orphan inventory/reconciliation is a documented operator review, not an automated capability claim.

## Browser and visual inspection

Chromium 153.0.8010.12 on Windows, 1440/1024/768 x 1000. Populated project overview, dataset schema, run and evaluation pages have twelve stabilized visual baselines. Screenshots were inspected for overlaps/overflow, table controls, readable labels and critical actions. Actual authenticated project and governance report screenshots were also inspected. The expanded live-auth accessibility check caught an unlabeled loading spinner; both workspace and identity loading indicators now have accessible names, with a focused assertion and passing rerun. No full WCAG certification is claimed.

README screenshots refreshed with programmatically generated fake data only: project overview, dataset governance, synthetic run, evaluation dashboard, release decision, governance report and executive-summary cover. No real person, hospital data, credential or local directory is displayed. Username labels explicitly identify development demo researchers.

## Performance and query behavior

Baseline initial JS was 475.51 kB (155.86 kB gzip), total JS 647,321 bytes in 19 chunks. Final UI splits shared Material UI/Emotion into a 306.73 kB chunk and an approximately 284.14 kB entry; total JS is 651,933 bytes in 17 chunks. Largest individual chunk decreased, while combined initial transfer increased because identity UI is added; this is not claimed as overall transfer reduction. Route-level lazy loading remains. Existing aggregated workspace endpoints avoid per-card/per-artifact N+1 requests. Tenant predicates add scoped database queries; no new distributed queue or oversized pools were introduced.

The authenticated engineering load smoke made 100 project-list/dataset-metadata requests at concurrency 10, with zero failures. Final median 214.85 ms, p95 367.95 ms, maximum 426.71 ms; run duration 3.01s. Values are retained in backend/.work/authenticated-load-smoke.json; this localhost exercise does not establish enterprise capacity.

Final local image IDs: API `sha256:765d15edd0effdbde100a9660cf56b2e9845cf728a2a379e6f0e9b981caba4c1`, worker `sha256:d0b946daa3eb39dae15849c510b2c287d4cbaef48677689f8c5d7e3135936307`, frontend `sha256:2c39c11658af4b92c100b024665d825af5695692e7b1a45ad1e9cc8cff0d459b`. API release metadata reports 0.6.0, source HEAD fc60aca8128f52cd6f595cc801cdc4626760bfae and build timestamp 2026-10-05T10:38:34.2652695Z; the inherited working tree is uncommitted, so this is not a clean release revision.

## CI, scans and remaining release gates

quality.yml has backend (PostgreSQL, unit/model/integration/migration/lint/audit/Bandit/smoke), Windows frontend (install/unit/type/lint/build/audit/Chromium visual/product), containers/security (three builds, Gitleaks, full Trivy JSON, fixable High/Critical gate and CycloneDX SBOM), and real local OIDC/S3 browser/backup jobs. No production credentials are required for pull requests. Actions are pinned, dependencies updated weekly/grouped, and no automatic major-version merge or production deployment is added. Local workflow syntax and corresponding commands passed. Remote GitHub Actions execution and recommended branch protections have not been performed/enabled.

API and worker each report 44 High, 59 Medium, 61 Low and 2 Unknown OS package findings, zero Critical, zero fixable findings, and zero Python findings in Trivy 0.75.0. Forty-four High package findings map to eight distinct CVEs. Static frontend scan reports zero findings. Supporting provider/database fixture images were not container-scanned. The locally executed fixable High/Critical gate passes; this does not hide or accept the full findings. See SECURITY_SCAN_REVIEW.md for all eight CVEs and disposition. Remaining advisory reachability/risk acceptance is unverified; release approval is withheld. Archived MinIO is conformance-only, not supported production infrastructure.

Claims were reviewed across current UI, reports, README and docs; historical Phase 1-5 verification remains historical. No affirmative HIPAA/GDPR compliance, guaranteed anonymity, clinical validity, zero privacy risk, secure physical erasure or tamper-proof claim was introduced. Generated fake data only was used/committed for tests/demos. No production credentials, source preview/public report endpoint, unsafe HTML or arbitrary uploaded-model deserialization was introduced. Existing trusted historical imaging weights remain with their original licensing/provenance limitations.

## Acceptance disposition

| Criteria | Local evidence / status |
| --- | --- |
| 1-20 identity, roles, tenant isolation, migration | Implemented and locally verified with actual provider browser, PostgreSQL role/IDOR and preserving upgrade tests |
| 21-28 audit/private storage/integrity/download | Implemented and locally verified; append-only application trail, real private S3 workflow |
| 29-35 production/web security | Configuration/header/escaping/CSRF controls implemented and tested; public HTTPS deployment not performed |
| 36-47 lifecycle/observability/readiness | Manual retention/background authorized deletion and actual safe logs/metrics verified |
| 48-60 images/local stack/backup/reliability/science | Locally verified; ECG Beta, imaging Experimental, genomics unavailable |
| 61 CI exists and passes | Workflow exists and local checks pass; remote runner execution pending, so mandatory acceptance is not fully satisfied |
| 62-65 scanning/build automation | Configured; scanners/builds actually run locally; unfixed High findings await explicit disposition |
| 66-70 authenticated/tenant/S3/deletion/browser regression | Local real-provider/storage browser and authoritative backend checks pass |
| 71-79 data/secrets/claims/restricted artifacts | Audited; no real healthcare data or production secret added; claims remain qualified |
| 80-90 docs/demo/remaining limits/scope | Required docs and fake-data demo implemented; no new scientific algorithms or prestige infrastructure |

PHASE 6 NOT COMPLETE. Do not designate MedSynth Guard a release candidate or start another phase automatically. Pending work is release validation/review, not new algorithms or infrastructure: execute the remote CI workflow and explicitly resolve/dispose of container advisories for the selected maintained deployment services.

## Remaining product/deployment limitations

No formal regulatory/clinical certification, differential privacy, free-text or multi-table synthesis, automated model recommendations, RLS, automatic invitations/provider administration, scheduled expiry or dataset-only deletion. Local OIDC differs from a production provider; local fixtures use HTTP. Object-store physical erasure/version/backups depend on provider policy. S3 orphan reconciliation is administrative. PostgreSQL restoration was verified against available test objects, not destroyed-store disaster recovery; no RTO/RPO guarantee. Policy thresholds remain organization-defined. Model transitive dependencies are not fully locked, upstream DCR baseline varies, and existing imaging training provenance/licensing remains incomplete. Chromium/Windows desktop/tablet checks are not cross-browser certification. Inherited uncommitted work was preserved; a supplied source HEAD is not claimed to represent a clean committed release.

## Closure verification — starting baseline, 2026-10-07

Status remains **PHASE 6 NOT COMPLETE**. These are starting closure results, not final release approval. The starting local HEAD was `fc60aca8128f52cd6f595cc801cdc4626760bfae` on `main`, with extensive inherited uncommitted Phase 6 implementation. Remote `main` was `c485d1c47ee9bc996f8bb749df272f60622bf921`; no remote branch is overwritten by the closure branch.

The initial model command had 31 passes and two PostgreSQL connection-timeout errors while Docker Desktop was unavailable. Docker startup recovery restored the engine without deleting volumes. The daemon interruption stopped other unfinished commands; completed evidence was retained and interrupted commands were rerun. The initial frontend audit found one fixable High advisory, CVE-2026-93749 / GHSA-68fv-2mgg-jv7q. The only baseline dependency change was `source-map-js` 1.2.1 → 1.2.2 in the lockfile. The patched audit and frontend regressions passed.

| Starting closure gate | Actual result |
| --- | --- |
| Unit suite | 183 passed, 1 existing Windows symlink privilege skip, 75 deselected; 49.82s |
| Model suite, PostgreSQL ready | 33 passed, 226 deselected; 320.71s |
| Integration, `MEDSYNTH_S3_TEST=1` | 51 passed, 208 deselected; 525.08s; real PostgreSQL and MinIO |
| Compilation / Ruff check / Ruff format | Passed; 158 files already formatted |
| `pip check` | No broken requirements |
| `pip-audit` / Bandit | Zero findings |
| `npm ci` | Passed; existing esbuild install-script policy warning retained |
| Frontend unit regression | 14 passed in four files |
| Typecheck / lint / build | Passed; regression build 5.56s |
| Patched `npm audit --audit-level=low` | Zero findings |
| Product browser regression | 9 passed; 1.2m; includes 12 image comparisons, accessibility and responsive checks |
| Real OIDC + authenticated live S3 browser regression | 2 passed; 1.5m; includes API/worker restart and report digest |
| Platform / tabular / evaluation / product smokes | All four passed with private S3, separate workers, hash checks and actual API process restart; 2/50/400/400 outputs and 3/4/9/10 artifacts |
| Gitleaks 8.30.1 | Zero findings in 15-commit history and 327-file nonignored working-tree export |
| Workflow review | Sole workflow `quality`: push/PR/manual triggers; `contents: read`; pinned action SHAs matched upstream tags; local actionlint passed. Security job currently scans only API, so full closure scope is still open. |

The first live browser command's assertions passed but its process exited 1 because dependency installation overlapped Playwright teardown. That failed command is not counted as a passed gate. The sequential rerun above exited 0. Suite counts overlap and must not be added as distinct test counts.

Fresh full Trivy 0.75.0 scans, without advisory exclusion, used vulnerability DB schema 2 updated `2026-10-07T00:53:05.111120428Z`; Java DB schema 1 updated `2026-10-07T01:10:24.784068105Z`. Starting API and worker each have 0 Critical, 44 High, 58 Medium, 61 Low and 2 Unknown findings, mapping to eight distinct High CVEs. Frontend has zero findings. Supporting-image starting scans found PostgreSQL 16 Critical / 101 High, Keycloak 0 Critical / 6 High, and MinIO 10 Critical / 105 High. Supporting findings are additional closure review work; none is accepted merely because a scanner supplies no fixed version.

Raw scans, image inspections, scanner versions and command logs are retained in ignored `backend/.work/phase6-closure/`. Starting smoke report: 25,980 bytes, SHA-256 `78f5bc1701c98f0328f10c8d618bf6a123e2b30019cd921d58c4a0aee04730d7`; illustrative policy decision `REVIEW_REQUIRED`. All fixtures remain generated fake data. No new feature or implementation phase was introduced.

Remote Actions execution for the closure commit, final container remediation/dispositions, final SBOM and final regressions remain open. Starting baseline evidence does not substitute for those gates.

## Closure verification — remote attempts and disposition candidate, 2026-10-07

Repository: `Stevemeg/Synthetic-Data`; branch: `phase6-closure`; version: `0.6.0`.
The inherited Phase 6 implementation was committed without changing remote
main. No release tag was created and no branch-protection setting was claimed.

| Actual quality run | Commit | Backend | Frontend | Containers/security | OIDC/storage/browser |
| --- | --- | --- | --- | --- | --- |
| [37575669077](https://github.com/Stevemeg/Synthetic-Data/actions/runs/37575669077) | `aaa5327d66efb59b06c2a01b15d6c7f4fd58c81a` | success | success | success, original API-only scope | failure: Keycloak connection reset before readiness |
| [37578284043](https://github.com/Stevemeg/Synthetic-Data/actions/runs/37578284043) | `aac7c5830f21d3f842b781830bf5591160fc05a6` | success | success | failure: deliberately empty disposition file | success |

Run 37578284043 successfully built/scanned API, worker, frontend, PostgreSQL,
Keycloak and MinIO and generated all six CycloneDX SBOMs. Fresh counts:
API/worker each 0 Critical/44 High/eight distinct CVEs; frontend zero;
PostgreSQL 1 Critical/54 High/16 distinct; Keycloak 0 Critical/6 High/three
distinct; MinIO 2 Critical/4 High/six distinct. This is remediation evidence,
not a green release gate. Raw findings and SBOMs are retained as its
`supply-chain-review` artifact and downloaded under ignored local evidence.

The initial Linux backend run reported 184 unit passes (the Windows symlink
skip passed on Linux), 49 integration passes/two S3 tests skipped, and 33 model
passes. The OIDC job in the second run explicitly selects `-m integration`
for those two real-S3 tests and passed authenticated browser/storage workflows,
all four host-process S3 smokes and backup/restore. Windows frontend runs passed
14 unit tests and nine product browser tests including reviewed visual,
accessibility and responsive checks. Counts overlap and must not be summed.

The candidate closure adds six release-gate regression tests: reviewed High
risks may pass; unknown, changed, expired, fixable or unresolved Critical risks
fail closed. Local post-change unit verification: 189 passed, one existing
Windows symlink skip, 75 deselected; compilation/Ruff/format/pip-check passed.
The final required run must retest these changes and the final container
configuration. It also runs real fit/sample/checksum/save/reload for all three
existing tabular engines in both final backend images, all four S3 smoke
workflows in the final worker, and scans/SBOMs those exact exercised image IDs.

The 41 individual image/CVE reviews and their evidence requirements are in
[Security scan review](SECURITY_SCAN_REVIEW.md#individual-closure-dispositions)
and `ops/container_dispositions.json`. No blanket ignore, unfixed exclusion,
invented risk acceptance or new product feature was introduced. Reviews are
limited to the supplied application/fresh loopback fixture configuration and
expire 2026-11-06 or upon relevant configuration/package/exposure changes.
They do not approve public/shared archived MinIO or arbitrary untrusted
PostgreSQL SQL/XML clients. The release gate remains open until the final
exact-commit remote run actually validates them.

Local Docker rebuilds failed after disk exhaustion/read-only filesystem/daemon
EOF. These attempts are preserved as failures. The subsequent successful
GitHub-hosted builds do not assert that the local Docker engine has recovered.
Existing local database/object volumes were not replaced; a verified pre-change
backup/restore checked 421 S3 references. The PostgreSQL distribution update
requires logical restoration/collation/index review for existing deployments;
physical-volume reuse is not certified by the fresh-cluster tests.

Status at this checkpoint: **PHASE 6 NOT COMPLETE**. A later successful exact
commit run and its immutable artifacts, final image IDs, scanner metadata and
working-tree identity are required for any final release designation.

Run [37580240762](https://github.com/Stevemeg/Synthetic-Data/actions/runs/37580240762)
tested `54eac18a37f7350d93311db310bb81477fb30b98` and exposed a security
verification-command error: read-only inspection omitted the runtime's `/tmp`
tmpfs, causing SciPy's temporary-file import to fail. Its security job failed;
no successful final scan is asserted for that run. The probe is corrected to
match the actual restricted runtime. Disposable worker smoke containers also
avoid colliding with the persistent worker's metrics port. Another exact-commit
remote run is required; its earlier successful frontend job is not substituted.

Final status of run 37580240762: backend and frontend success; security and
OIDC/storage/browser failure. The latter completed authentication, live S3,
all four container-based smokes, service-scope checks and cross-distribution
logical restore before failing on the same missing-tmpfs inspection command.
Those partial results are retained; they do not constitute a green release run.

## Important files (reference list)

VERSION; backend/app/version.py; config/security/auth+oidc+tenancy; identity/lifecycle models and Alembic 0005; authentication/membership/metrics routes; S3/factory/instrumented storage and integrity retrieval; safe logging/worker metrics and tenant execution invariants; lifecycle service; migration/bootstrap/backup/operations scripts; focused security/S3/report tests; frontend identity/membership/role-aware pages/client/shell/activity; Playwright real-auth/live/visual suites; ops Dockerfiles/nginx/fixtures; security/runtime/production Compose; GitHub quality/Dependabot; required security/tenancy/storage/lifecycle/operations/deployment/release/story docs and ADRs 0015-0019; updated README/architecture/API/privacy/artifact/development/demo/UX/reporting documentation.
