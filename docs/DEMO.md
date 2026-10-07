# Development demo: generated fake data only

The demo contains programmatically generated engineering relationships, never hospital observations or real patient data. It is labelled **Demo synthetic source fixture**. The invented readmission signal demonstrates software behavior, not a clinical relationship.

## Start and bootstrap

Use the README setup, start Docker Desktop/PostgreSQL, install the evaluation dependencies and migrate to head. In separate terminals from repository root:

```powershell
docker compose up -d postgres
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m backend.app
# Separate terminal
.venv/Scripts/python.exe -m backend.worker
# Separate terminal
cd frontend
npm ci
npm run dev -- --host 127.0.0.1
```

With API and worker running, from root:

```powershell
.venv/Scripts/python.exe -m backend.scripts.create_demo_project
```

Alternatively `--start-services` starts temporary API/worker processes, retains the demo resources, verifies API restart, and stops those processes. Start the ordinary development services afterward to browse them. Every invocation creates a separate clearly marked project; it does not overwrite existing work. No credentials or database state are committed. All registration, preflight, metadata, generation, evaluation and report operations use the normal API/worker validation paths.

Bootstrap creates Cardio Readmission Research, a 400-row fake clinical cohort, reviewed identifier/excluded/annotated roles, a Gaussian Copula run and Full evaluation. The Illustrative Research Demo Policy has example operational thresholds only, not a medical, legal, regulatory or privacy standard. An 80/20 split leaves DCR overfitting advisory, so its required rule explains Review required; this is intentional, not a promise of a fixed set of random DCR scores. The script downloads the governance report and verifies its SHA-256 and size.

## Six-minute walkthrough

1. **0:00–0:40:** Open Projects and Cardio Readmission Research. Show counts, recent activity and the branch-aware workflow narrative.
2. **0:40–1:30:** Open the synthetic source fixture. Explain the fake-data label, dimensions/hash and absence of source previews. Inspect preflight warnings, synthetic identifiers, excluded text and annotations.
3. **1:30–2:15:** Open Start synthesis. Review Gaussian Copula Stable versus Beta neural options, bounded advanced settings and the review summary. The already completed demo run avoids waiting for neural training.
4. **2:15–2:50:** Open the completed run. Show structural checks, recorded lifecycle, restricted model and expandable provenance.
5. **2:50–3:30:** Open its evaluation. Explain Full as selected computations, the known/sensitive scenario and readmitted classification target.
6. **3:30–4:20:** Inspect separate training and holdout fidelity. Use the column filter and pair table; higher similarity is not greater privacy.
7. **4:20–5:00:** Show exact overlap, baseline DCR, prominently advisory overfitting and scenario-specific disclosure. Explain TRTR/TSTR side by side and the explicitly named F1 ratio.
8. **5:00–6:00:** Read each release-rule reason. Explain organization-defined thresholds and Review required. Download/open the governance report with provenance and limitations. No compliance, anonymity or clinical validity guarantee follows.

The comparison page accepts two or more compatible completed evaluations. To demonstrate multiple engines, create additional runs/evaluations with the same source, split, profile, attacker/task and policy; one-epoch Beta runs are demonstrations, not a comparative clinical study. The browser fixture suite also exercises compatible and incompatible comparison without a winner.

## Reproducible verification

```powershell
.venv/Scripts/python.exe -m backend.scripts.product_smoke_test --start-services
cd frontend
npm exec -- playwright install chromium
npm run test:e2e
npm run test:visual
# Requires local API + worker and the bootstrap above:
npm run test:live
```

The live test creates an additional reviewed run/evaluation in a fake-data demo project, verifies report bytes and captures documentation screenshots. The regular browser suite uses explicit generated fixtures and stable timestamps/IDs for visual regression. Keep local fixture APIs on loopback. Phase 6 supports real OIDC and organization roles; see the authenticated container demo below.

## Authenticated local container demo

1. Follow README local OIDC/container startup. Sign in at 127.0.0.1:8088 using
   researcher-a and the generated password in ignored
   backend/.work/development-identity.env. These are test identities only.
2. After the real first login, run `python -m backend.scripts.configure_demo_memberships`
   and refresh. Development workspace is OWNER; secondary organization is VIEWER.
3. The authenticated browser test seeds the generated cohort through actual APIs,
   then performs the reviewed generation/evaluation/report workflow:

```powershell
$env:MEDSYNTH_AUTH_E2E='1'
$env:MEDSYNTH_BROWSER_URL='http://127.0.0.1:8088'
cd frontend
npm run test:auth
npm run test:live
```

The test's temporary in-memory session is passed to the development CLI through
its child environment, never printed or written into browser storage. There is
no test authentication bypass. Repeated seeding creates an isolated fake-data
project without replacing work. Once seeded, use the original six-minute product
walkthrough and add identity/organization/role and authenticated audit context.
The legacy unauthenticated CLI remains available only with explicit development
authentication. S3 validation never falls back to local storage.
