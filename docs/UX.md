# Governed workspace UX

MedSynth Guard is an internal synthetic-data workspace. The primary workflow is Project → Source Dataset → Preflight and Schema Governance → Synthetic Run → Evaluation → Evidence → Release Policy Decision → Governance Report → Artifact Export.

## Navigation and resource identity

Primary navigation contains Overview, Projects, Datasets, Runs, Evaluations and Reports. A selected project has Overview, Datasets, Synthetic Runs, Evaluations, Reports, Release Policies and Compare links. Inventories are bounded and paginated; global inventories can retain a project context. Project, dataset, run and evaluation URLs survive refresh. Unknown resources show a readable error and retry; an unknown route returns a workspace notice.

Routes: `/projects`, `/projects/:projectId`, `/projects/:projectId/{datasets,runs,evaluations,reports,policies,compare}`, `/datasets/:datasetId`, `/datasets/:datasetId/generate`, `/runs/:jobId`, `/runs/:jobId/evaluate`, `/evaluations/:evaluationId`.

The React Router shell owns navigation, not resource data. Route modules load lazily. Typed domain contracts, an Axios client and a small resource hook support features without a global store. Theme and CSS centralize typography, spacing, colors, table overflow, focus and responsive navigation. No additional chart package is required: fixed-domain horizontal bars have adjacent numeric values and fidelity tables.

## Operating the workflow

Create a project with name and description. Register a bounded CSV from its dataset inventory. Dataset detail shows dimensions, identity, a copyable SHA-256 and schema summaries, without source rows or storage paths. Preflight inference is advisory. Review Model, Identifier and Exclude roles and Quasi-identifier/Sensitive attribute annotations. Identifiers are excluded from training and replaced by new sequences. Save governance for subsequent run review; submitted runs retain their own snapshots.

The generation wizard has six small steps: Dataset, Columns, Engine, Configuration, Review, Submit. Gaussian Copula is Stable; CTGAN and TVAE are Beta. Basic controls cover row count and seed. Advanced controls expose bounded split settings, relevant neural parameters and optional validation rules. Review lists selected columns, annotations, split and warnings. Submission is intentional and retry uses an idempotency key. Successful tabular runs offer a contextual Evaluate dataset action.

Evaluation selects Basic, Standard or Full computations. Full enables a specified disclosure scenario and utility task. Annotation suggestions require explicit confirmation. Known attributes are assumed externally known; sensitive attributes are what the attacker attempts to infer. Utility targets exclude identifiers, excluded fields and incompatible types. Source entity grouping/independence declarations make methodology limits visible. Policies are immutable versions; changes create another version. Numeric rules support minimum, maximum or inclusive range; copying a version preserves both recorded bounds.

Results separate structure, training fidelity, holdout fidelity, exact overlap, DCR baseline, DCR overfitting, disclosure, TRTR/TSTR utility and release-rule reasons. Advisory DCR evidence has a prominent warning. No composite score or model ranking exists. Comparisons ask the established backend to enforce source/hash, split, profile, task and policy compatibility. A policy pass satisfies the configured version; it does not guarantee anonymity, compliance or clinical validity.

## States, accessibility and responsive behavior

Every resource uses explicit loading, error, empty and populated states. Errors distinguish validation, availability, integrity, security restriction and execution failure, retaining a request ID when available. Downloads use artifact IDs, not paths. Restricted models have no download action. Audit views omit raw metadata and distinguish authenticated user UUIDs, worker/system actors and explicit unauthenticated development callers.

Active job polling starts at approximately four seconds, backs off to fifteen seconds, retries temporary failures up to thirty-second intervals, aborts on unmount and stops at terminal responses. Only recorded status/timestamps appear; there is no invented percentage or training stage.

Desktop/laptop navigation is persistent. Below 900px it becomes a keyboard-accessible drawer; tables scroll within their containers and summary cards stack. Supported verification widths are 1440, 1024 and 768px. Phone workflows are not certified. Controls have labels, focus is visible, headings/tables are semantic, dialogs manage focus, and status has text as well as color. Automated axe checks and Chromium keyboard tests supplement direct screenshot review; this is not WCAG certification.

OIDC sign-in/sign-out, current identity, organization selection and role-aware actions are implemented in Phase 6. Backend authorization remains authoritative; only development bypass shows an unauthenticated development label.
