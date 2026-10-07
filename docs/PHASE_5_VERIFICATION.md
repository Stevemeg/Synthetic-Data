# Phase 5 verification

Verified on 2026-10-05 using Windows 10.0.26300, Python 3.11.0 in `.venv`, Node 24.18.0, npm 12.0.2, Docker Desktop/PostgreSQL 16.15 and Playwright Chromium 153.0.8010.12. Phase 6 was not implemented. Existing uncommitted Phase 1–4 work was preserved.

## Phase 4 baseline before product changes

Inspected README and all requested architecture, product scope, privacy, API, development, artifact, job, tabular, evaluation, fidelity, privacy evaluation, utility, release policy and Phase 3/4 verification documents and ADRs 0001–0012. Inspected the complete original React application, domain/configuration controls, API transport, transient tab navigation, polling, evaluation/comparison, artifact handling, styling and tests. The established MUI stack and scientific/worker architecture were retained.

| Command | Actual baseline result |
| --- | --- |
| `python -m pytest -q` | 169 passed, 1 Windows symlink skip, 68 deselected; 21.04s |
| `python -m pytest -q -m model` | Initial 32 passed / 1 PostgreSQL setup error; after starting Docker/PostgreSQL, full rerun 33 passed, 205 deselected; 167.59s |
| `python -m pytest -q -m integration` | Initial 43 passed / 1 PostgreSQL setup error, 194 deselected; failed two-worker evaluation case rerun passed after PostgreSQL startup (1 passed; 30.43s). This was not a second full baseline integration run. |
| `compileall`, Ruff check/format check, `pip check` | Passed; 124 Python files formatted; no broken requirements |
| Alembic current/check | 0003_evaluation head; no drift |
| `npm ci` | Passed |
| `npm test` | 4 passed in 2 files; 67.31s |
| Typecheck / lint / build | Passed; JS 523.77 kB / gzip 165.66 kB; chunk advisory |
| `npm audit --audit-level=low` | Initial 9 high transitive lint-tool advisories; compatible `npm audit fix` repaired them, repeat audit 0 vulnerabilities |
| Platform smoke `--start-services` | Passed; 2 ECG outputs, 3 artifacts, restricted model, hashes and actual API restart |
| Tabular smoke `--start-services` | Passed; 100 source / 80 training / 20 holdout / 50 generated rows; 4 artifacts and restart |
| Evaluation smoke `--start-services` | Passed; 400 generated rows, 9 artifacts, Full evidence and restart |

Docker was off when the first two database-dependent suites started. It was started and readiness checked before repairs/retries; no scientific baseline regression was concealed. Dependency repair affected development lint tooling, not synthesis/evaluation libraries. Local logs and JUnit XML are ignored, not committed.

## Product implementation and acceptance evidence

| Acceptance criteria | Implemented and verified evidence |
| --- | --- |
| 1–6: shell, navigation, URLs and projects | Responsive MUI shell; Overview/Projects/Datasets/Runs/Evaluations/Reports; project subnavigation; simple create dialog; counts/decision/activity; stable React Router resources and browser reload tests |
| 7–10: project/dataset governance | Dashboard branches and meaningful counts; bounded inventory; dimensions/filename/hash; advisory preflight; role/type/annotation table; saved validated governance; no row previews |
| 11–18: generation and run resources | Six-step intentional wizard, factual engine maturity, bounded basic/advanced controls, run filters/date sort/pages, timestamp timeline, structural checks/provenance/artifacts and contextual evaluation |
| 19–23: configuration and policies | Basic/Standard/Full, explicit known/sensitive confirmation, typed utility target filtering, entity grouping/independence, constrained builder, immutable versions, hash/date/usage and new-version action |
| 24–33: independent evidence and decisions | Separate training/holdout bars with fixed 0–1 scale, searchable/filterable/sortable paged columns and pairs, distinct exact/DCR/disclosure diagnostics, advisory gating, TRTR/TSTR table and deltas/ratios, regression directions, per-rule reason/status/requirement and visible disclaimer |
| 34–36: comparison | Backend-enforced compatibility including source/hash, schema/split, profile, attacker/task, limits/seeds and policy; incompatible message clears results; no ranking/winner |
| 37–43: reports | Persisted-evidence HTML, complete sections/limitations/provenance, registered size/hash/policy metadata, internal artifact-ID download, escaped strings/CSP, no recomputation or compliance/anonymity guarantee |
| 44–55: operation and architecture | Safe audit fields/actor labels; explicit states/request-ID errors; cancellable backoff polling; responsive forms/tables/dialogs; keyboard/focus and axe checks; numeric chart alternatives; centralized typed client and decomposed lazy features |
| 56–59: performance/demo | Initial chunk advisory removed; generated fake-data bootstrap and six-minute DEMO.md; no database/source observations committed |
| 60–68: verification | Browser/visual/responsive suites, live API/worker browser workflow, DOM behavior tests, real backend/model/PostgreSQL and all four smoke workflows passed; ECG retained |
| 69–76: boundaries | Imaging Experimental, Genomics Unavailable, artifact/concurrency protections retained, documented startup exercised, accurate README, explicit absent auth/tenant authorization, no Phase 6 implementation |

## Final backend and database gates

| Gate | Actual result |
| --- | --- |
| `python -m pytest -q` | **170 passed, 1 skipped, 70 deselected**; 14.97s |
| `python -m pytest -q -m model` | **33 passed, 207 deselected**; 448.55s; real tabular engines, evaluation/utility, ECG and preserved imaging cases |
| `python -m pytest -q -m integration` | **46 passed, 194 deselected**; 866.61s; PostgreSQL/real worker ownership, integrity, immutability, recovery and new reporting/workspace tests |
| Final focused report/workspace integration | **2 passed**; 100.45s after final wording/query fixes |
| Compileall / Ruff check / Ruff format check | Passed; 131 Python files formatted |
| `pip check` | No broken requirements |
| Alembic current / check | `0004_governance_reports (head)`; no new upgrade operations |
| Clean migrations | Full PostgreSQL integration suite exercised disposable-schema base downgrade/head upgrade and Phase 4 safe downgrade/upgrade with the new head. Migration 0004 refuses destructive downgrade when governance reports exist. |

The model/full integration results were recorded before the final report-only unit test was added (their deselection counts therefore differ from current collection). The subsequent changes affected report wording and aggregate queries; focused reporting/workspace regression was rerun. Scientific engines and concurrency code were not rewritten.

One intermediate focused integration run, concurrent with live browser/model work, hit the established 15-second PostgreSQL idle-in-transaction timeout during cold metadata preparation: 1 failed / 1 passed. PostgreSQL logs identified the timeout. The isolated rerun passed both cases; timeout/concurrency safeguards were not weakened. This is a local heavy-load limitation, not a clinical or distributed deployment certification. Upstream deprecation/methodology warnings remain visible. The symlink test skips because this Windows environment lacks creation permission.

## Final product smoke and persisted report

All commands used real separate API/worker processes and `--start-services`, verified registered bytes/hashes and an actual API process restart.

| Workflow | Actual result |
| --- | --- |
| Platform / Phase 2 | Passed; job `96ac23b8-772d-4bd0-b8e0-2657dad44f90`; 2 ECG outputs, 3 artifacts |
| Tabular / Phase 3 | Passed; job `fbb18b43-9704-4a7d-964f-f31c29e77dd8`; 50 outputs, 4 artifacts |
| Evaluation / Phase 4 | Passed; generation `f8fec9e4-398f-4871-aaa2-8d54a530800c`, evaluation `fbe3ce3f-ed58-4d98-8091-499d33247c28`; 400 outputs, 9 artifacts |
| Product / Phase 5 | Passed; project `397b8310-747a-4a6e-bc63-9939d7a5afe5`, dataset `bd9c7f0f-1ffa-4db6-8014-984eab410ded`, generation `e5a21038-3618-4a10-9d7b-5d1f0124e1b9`, evaluation `ffd5b599-051a-410d-aa89-f816beb568ed`; 400 outputs, 10 total artifacts |

Final smoke report: `7c1a6959-4940-4d0c-8ca2-d80d793be155`, `GOVERNANCE_REPORT`, `text/html; charset=utf-8`, **25,883 bytes**, SHA-256 **`ba6e38b5f6a867fbb25ce0b45e32a4e14988b01738c7abac88498e07f21d5b7e`**. Download matched size/hash, contained required sections/provenance/limitations and correct policy thresholds, omitted source rows/paths/forbidden claims, and remained valid after API restart. Decision: Review required under Illustrative Research Demo Policy v1, because required DCR overfitting evidence is advisory. Model downloads remained restricted.

## Final frontend and browser gates

| Gate | Actual result |
| --- | --- |
| `npm ci` | Passed; 337 packages added, 338 audited. npm warned that esbuild's install script was blocked by local allowScripts policy; the installed platform package supported the successful build. |
| `npm test` | **11 passed in 2 files**; 13.95s; navigation, role/annotation behavior/free-text protection, engine/review submission, Full configuration, policies/reasons/applicability/states, preservation of both numeric policy bounds and polling recovery/termination/unmount |
| Typecheck / lint | Passed |
| `npm run build` | Passed; final 6.57s; no chunk-size advisory |
| `npm audit --audit-level=low` | **0 vulnerabilities** |
| `npm run test:e2e` | **9 passed**; final 1.3 minutes |
| `npm run test:visual` | **3 passed**; 1.3 minutes; **12 committed screenshot comparisons passed** |
| `npm run test:live` | **1 passed**; 2.2 minutes; real API/worker generation, Full evaluation, reload, decision and registered report download size/hash verification |

Chromium 153, viewports **1440×1000, 1024×1000 and 768×1000**, locale en-GB, UTC and reduced motion. Four resource pages per viewport passed axe WCAG2A/2AA/2.1AA tags and root-overflow checks. Project dialog, advanced generation controls and Full evaluation forms passed additional axe checks at all three widths. Keyboard focus on dialog open, Escape restoration, drawer behavior and form labels were exercised in the actual browser. This is targeted accessibility evidence, not full WCAG certification or a manual assistive-technology audit. The live evaluation page also passed axe.

Visual inspection opened rendered project, dataset, run, evaluation, comparison and report screenshots. Found/fixed dialog autofocus, stretched status chips, cramped schema labels and incorrectly flattened real nested DCR values. Report cover and full report were rendered directly; standalone HTML overflow checks passed at all three widths. No observed critical overlaps, broken cards, empty charts or clipped critical actions remained. Normal visual verification compared existing baselines after inspection, without update flags. An initial Windows npm script quoting error in the visual-only command was corrected; the final documented command passed.

Documentation screenshots in `docs/screenshots`: project-overview, dataset-governance, synthetic-run, evaluation-dashboard, release-decision, governance-report, governance-report-cover and model-comparison. Main workflow screenshots come from real local fake-data demo records; comparison uses explicitly labelled browser fixtures. Snapshots under frontend/e2e use stable generated fixtures, not clinical observations. IDs/times in live screenshots are persisted fake-demo identity, not personal data.

## Performance and query review

Initial JS chunk **523.77 → 475.51 kB** (about 9.2% smaller); gzip **165.66 → 155.86 kB**. Final assets total **647,321 JS bytes across 19 chunks**. Total feature code increased with the product scope, while routes/MUI controls load separately and the original >500 kB initial-chunk advisory disappeared. No heavy chart package was introduced. This is a build-size measurement, not a load-time benchmark.

Project summaries use a fixed number of grouped SQL queries independent of card count; latest activity includes persisted terminal/governance events. Bounded inventories default to 20 and cap at 100. Evaluation lifecycle data loads in a batch; instrumentation asserted at most four statements for its inventory. Dashboard pages do not request artifacts per run/project card. No speculative database indexes or infrastructure platform was added.

## Security, claim audit and limitations

Reviewed 206 initial occurrences of HIPAA/GDPR/anonymous/safe/privacy/secure/clinical/production/compliant across frontend, report code, README/docs, distinguishing negated limitations, metric names and engineering safety language. Corrected stale unused UI/genomics/future-evaluation wording and current documentation. Final report tests reject forbidden affirmative claims and verify HTML escaping, absent source rows/paths, idempotence, corrupted-byte rejection and no recomputation. No real patient data, source preview, public static report URL, filesystem-path exposure, compliance/anonymity claim or privacy guarantee was added. Authentication is absent; artifact APIs must remain internal and are not access-controlled merely by UUID.

Remaining limitations: no authentication/RBAC or tenant isolation; local artifact storage; single-table synthesis/evaluation; no differential privacy, free-text synthesis, multi-table/FHIR or clinical validation; organization-defined policy thresholds; advisory DCR for the default split; upstream DCR random-baseline variation; HTML only (no PDF); Chromium/Windows visual baselines only; tablet/desktop rather than certified phone support; metadata/metric tables can still contain sensitive column names/statistics; no public deployment certification. Actual application commit may be null when no verified commit is supplied; dirty-worktree provenance remains honest.

Phase 5 mandatory acceptance criteria are satisfied with the above scope and evidence. Phase 6 has not started.
