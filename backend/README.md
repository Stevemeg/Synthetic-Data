# Backend

From root, migrate PostgreSQL with `python -m alembic upgrade head`, run FastAPI with `python -m backend.app`, and run the separate worker with `python -m backend.worker`.

See [README](../README.md), [development](../docs/DEVELOPMENT.md), and [API](../docs/API.md). Existing offline wrappers and original model paths remain. Install requirements-tabular.txt for real Gaussian Copula/CTGAN/TVAE jobs. Genomic synthesis remains unavailable.

## Phase 4 evaluation

Install requirements-evaluation.txt, migrate to 0003_evaluation and retain the
same separate API/worker entry points. EvaluationRun uses the existing fenced
queue with typed evaluation work items. See ../docs/EVALUATION.md for public
SDMetrics APIs, limits, sensitive report artifacts and evaluation smoke. No
HTTP handler performs model fitting or metric computation.
