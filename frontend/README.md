# Frontend

React + TypeScript + Material UI consumes the versioned FastAPI API. Run npm ci, copy .env.example to ignored .env if needed, then npm run dev -- --host 127.0.0.1. VITE_API_URL defaults to http://127.0.0.1:5000.

The governed workspace contains Overview, Projects, Datasets, Runs, Evaluations and Reports, with project navigation and refreshable resource URLs. Active polling backs off, cleans up on unmount, recovers from temporary failures and stops on terminal responses.

Tabular runs support registered CSV selection, structural preflight, role/type and
annotation overrides, synthetic identifiers, Stable Gaussian Copula/Beta CTGAN/Beta
TVAE, row/seed/holdout/epoch configuration, explicit validation rules, durable job
states and artifact download. Models remain restricted. Evaluation displays independent measured evidence rather than a composite score.

Checks: npm run typecheck, npm run lint, npm run build. See [root README](../README.md) for database/API/worker setup.

`npm run test` verifies tabular controls and the submission/artifact flow in jsdom.
Transport is mocked for DOM tests; the backend has separate real-model/worker tests.

## Phase 4 functional evaluation

The Evaluations tab configures a successful tabular run, explicit disclosure/
utility/group semantics and immutable project policies. It polls durable status
and displays structural, fidelity, privacy, utility and policy sections plus
compatible engine comparisons. No universal score or automatic winner is added.
Phase 5 adds the route-based professional workspace and escaped HTML governance reports. Downloads contain sensitive internal statistics.
Run npm test, typecheck, lint, build and audit; DOM tests mock HTTP while backend
smokes verify genuine worker execution and API restart.

## Browser verification

Install Chromium with `npm exec -- playwright install chromium`. Run `npm run test:e2e` for workflow, keyboard, deep-link, comparison, visual regression and axe checks at 1440/1024/768px. `npm run test:visual` isolates visual/accessibility/responsive cases. Windows Chromium baselines use stable fake fixture identities/times and reduced motion. `npm run test:live` requires the local API/worker and generated demo bootstrap; it executes actual generation/evaluation, downloads the report and verifies its size/hash. See [UX](../docs/UX.md), [demo](../docs/DEMO.md) and [verification](../docs/PHASE_5_VERIFICATION.md).

Source rows and filesystem paths are not shown. Phase 6 adds real OIDC sessions, organization selection and role-aware controls backed by server authorization. Do not deploy publicly without the production configuration, operational review and release gates documented in ../docs/DEPLOYMENT.md and ../docs/PHASE_6_VERIFICATION.md.
