"""Deterministic escaped HTML from persisted evidence. Never reads source rows or runs metrics."""

import io
import json
from html import escape
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...core.errors import AppError
from ...core.logging import log_event
from ...core.security import sanitize_filename
from ...db.models import Artifact, Dataset, EvaluationRun, GenerationJob, Project
from ...db.repositories.catalog import AuditRepository
from ..artifacts.service import artifact_response
from .inputs import verified_bytes

LIMITATIONS = (
    "A policy pass means this dataset satisfied the configured policy version. It is not a guarantee of anonymity, regulatory compliance or clinical validity.",
    "Exact matches are one possible memorization signal. Zero exact matches do not prove anonymity.",
    "Pairwise fidelity does not establish full joint-distribution equivalence.",
    "DCR overfitting marked advisory cannot satisfy a required numeric release rule. Default 80/20 splits are advisory.",
    "Disclosure results cover only the explicitly configured attack scenario.",
    "ML utility concerns the declared task, model and original holdout; no clinical validation is provided.",
    "Policy thresholds are organization/project-defined operational criteria, not universal medical, legal or privacy standards.",
    "Access controls do not establish regulatory compliance, anonymization or clinical validity. Development authentication bypass must not be used for public operation.",
)
LABELS = {
    "PASS": "Passed policy",  # nosec B105
    "FAIL": "Failed policy",
    "REVIEW_REQUIRED": "Review required",
    "NOT_EVALUATED": "Not evaluated",
    "ADVISORY_ONLY": "Advisory only",
    "gaussian_copula": "Gaussian Copula",
    "ctgan": "CTGAN",
    "tvae": "TVAE",
    "MODELLED": "Model",
    "IDENTIFIER": "Identifier",
    "EXCLUDED": "Exclude",
    "APPLICABLE": "Applicable",
    "NOT_APPLICABLE": "Not applicable",
    "INSUFFICIENT_DATA": "Insufficient data",
    "BINARY_CLASSIFICATION": "Binary classification",
    "MULTICLASS_CLASSIFICATION": "Multiclass classification",
    "REGRESSION": "Regression",
}


def value_text(value):
    if value is None:
        return "Unavailable"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float):
        return f"{value:.4f}"
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, allow_nan=False)
    return LABELS.get(str(value), str(value))


def table(headers, rows):
    head = "".join(f'<th scope="col">{escape(str(h))}</th>' for h in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(value_text(v))}</td>" for v in row) + "</tr>" for row in rows
    )
    return f"<div class='table-wrap'><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"


def facts(values):
    return table(["Field", "Recorded value"], list(values.items()))


def rule_requirement(rule):
    parts = []
    if rule.get("equals") is not None:
        parts.append("= Passed" if rule["equals"] else "= Failed")
    if rule.get("minimum") is not None:
        parts.append(f">= {rule['minimum']}")
    if rule.get("maximum") is not None:
        parts.append(f"<= {rule['maximum']}")
    parts.append("Required" if rule.get("required", True) else "Optional")
    return "; ".join(parts)


def render_report(project, dataset, generation, run, manifest, artifacts):
    summary = run.result_summary_json
    release = summary["release"]
    sections = []

    def section(title, content):
        sections.append(f"<section><h2>{escape(title)}</h2>{content}</section>")

    section(
        "Executive summary",
        facts(
            {
                "Engine": generation.engine,
                "Produced rows": generation.produced_samples,
                "Structural validation": "Passed" if summary["structural"]["passed"] else "Failed",
                "Holdout Column Shapes": summary["quality"]["holdout"]
                .get("properties", {})
                .get("Column Shapes", {})
                .get("score"),
                "Holdout Column Pair Trends": summary["quality"]["holdout"]
                .get("properties", {})
                .get("Column Pair Trends", {})
                .get("score"),
                "Exact training matches": summary["privacy"]["exact_training"][
                    "exact_matching_generated_rows"
                ],
                "DCR baseline": summary["privacy"]["dcr_baseline_protection"]["score"],
                "DCR overfitting applicability": summary["privacy"]["dcr_overfitting_protection"][
                    "applicability"
                ],
                "Disclosure protection": summary["privacy"]["disclosure_protection"]["score"],
                "TSTR/TRTR F1 ratio"
                if summary["utility"].get("task") == "BINARY_CLASSIFICATION"
                else "Task-specific utility ratio": summary["utility"]["score"],
                "Release decision": release["decision"],
            }
        ),
    )
    section(
        "Source dataset",
        facts(
            {
                "Name": dataset.name,
                "Filename": dataset.original_filename,
                "Dataset ID": str(dataset.id),
                "Rows": dataset.row_count,
                "Columns": dataset.column_count,
                "Source SHA-256": dataset.sha256,
                "Registered": dataset.created_at.isoformat(),
            }
        ),
    )
    section(
        "Generation configuration",
        facts(
            {
                "Run": str(generation.id),
                "Engine": generation.engine,
                "Seed": generation.random_seed,
                "Requested rows": generation.requested_samples,
                "Produced rows": generation.produced_samples,
                "Configuration": generation.configuration_json.get("tabular", {}),
                "Original split": generation.configuration_json.get("split", {}),
            }
        ),
    )
    section(
        "Schema governance",
        table(
            ["Column", "Type", "Role", "Annotations"],
            [
                [
                    c["name"],
                    c["semantic_type"],
                    c["role"],
                    [a.replace("_", " ").title() for a in c.get("annotations", [])],
                ]
                for c in generation.configuration_json.get("columns", [])
            ],
        ),
    )
    section("Structural validation", facts(summary["structural"]))
    fidelity = "<p>Higher values indicate greater similarity under this metric; scores do not indicate safety. Training and holdout remain separate.</p>"
    for partition in ("training", "holdout"):
        quality = summary["quality"][partition]
        fidelity += f"<h3>{partition.title()} fidelity</h3>" + table(
            ["Metric", "Score", "Applicability"],
            [
                [name, metric["score"], metric["applicability"]]
                for name, metric in quality.get("properties", {}).items()
            ],
        )
        fidelity += table(
            ["Column", "Metric", "Score", "Applicability"],
            [
                [r["Column"], r["Metric"], r["Score"], r["applicability"]]
                for r in quality.get("column_metrics", [])
            ],
        )
        fidelity += table(
            ["Variable 1", "Variable 2", "Metric", "Score"],
            [
                [r["Column 1"], r["Column 2"], r["Metric"], r["Score"]]
                for r in quality.get("pair_metrics", [])
            ],
        )
    section("Statistical fidelity", fidelity)
    exact = summary["privacy"]["exact_training"]
    privacy = facts(
        {
            "Matching generated rows": exact["exact_matching_generated_rows"],
            "Generated rows": generation.produced_samples,
            "Exact training match fraction": exact["exact_match_fraction"],
        }
    )
    for key in ("dcr_baseline_protection", "dcr_overfitting_protection", "disclosure_protection"):
        metric = summary["privacy"][key]
        privacy += f"<h3>{key.replace('_', ' ').title()}</h3>" + facts(
            {
                k: metric.get(k)
                for k in (
                    "score",
                    "applicability",
                    "breakdown",
                    "methodology",
                    "configuration",
                    "real_partition",
                    "warnings",
                )
            }
        )
    section("Privacy diagnostics", privacy)
    utility = summary["utility"]
    section(
        "ML utility",
        "<p>TRTR trains on real training data; TSTR trains on synthetic data. Both evaluate on the same untouched real holdout.</p>"
        + facts(
            {
                "Task": utility.get("task"),
                "Target": utility.get("target"),
                "Applicability": utility["applicability"],
            }
        )
        + table(
            ["Metric", "TRTR", "TSTR", "TSTR minus TRTR", "Ratio", "Ratio semantics"],
            [
                [
                    name,
                    utility.get("trtr", {}).get(name),
                    utility.get("tstr", {}).get(name),
                    comparison.get("absolute_delta"),
                    comparison.get("ratio"),
                    comparison.get("ratio_semantics"),
                ]
                for name, comparison in utility.get("comparisons", {}).items()
            ],
        ),
    )
    section(
        "Release policy",
        facts(release.get("policy") or {"Policy": "None selected"})
        + table(
            ["Rule", "Observed", "Requirement", "Status", "Reason"],
            [
                [
                    r["metric"].replace("_", " "),
                    r["actual_value"],
                    rule_requirement(r["threshold"]),
                    "Passed"
                    if r["status"] == "PASS"
                    else "Failed"
                    if r["status"] == "FAIL"
                    else r["status"],
                    r["reason"],
                ]
                for r in release["rules"]
            ],
        ),
    )
    section(
        "Decision rationale",
        facts(
            {
                "Decision": release["decision"],
                "Reasons": release["reasons"],
                "Meaning": LIMITATIONS[0],
            }
        ),
    )
    provenance = {
        k: manifest.get(k)
        for k in (
            "application_version",
            "application_commit",
            "application_build_timestamp",
            "application_worktree_dirty",
            "library_versions",
            "started_at",
            "finished_at",
            "source_split",
            "inputs",
        )
    }
    provenance.update(
        {
            "Project": str(project.id),
            "Generation job": str(generation.id),
            "Evaluation": str(run.id),
            "Policy version": run.policy_version,
            "Policy hash": run.policy_hash,
            "Engine version": generation.metadata_json.get("engine_version")
            or generation.metadata_json.get("tabular", {}).get("engine_version"),
        }
    )
    section(
        "Provenance",
        facts(provenance)
        + table(
            ["Artifact ID", "Type", "Bytes", "SHA-256"],
            [[str(a.id), a.artifact_type, a.size_bytes, a.sha256] for a in artifacts],
        ),
    )
    section(
        "Warnings and limitations",
        "<ul>"
        + "".join(f"<li>{escape(w)}</li>" for w in [*LIMITATIONS, *summary.get("warnings", [])])
        + "</ul>",
    )
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'\"><title>MedSynth Guard governance report</title><style>body{font:15px/1.6 'Segoe UI',Arial,sans-serif;color:#20313e;background:#f4f6f8;margin:0}main{max-width:1100px;margin:32px auto;background:white;padding:40px}h1{font-size:32px}h2{border-bottom:1px solid #dce3e8;padding-bottom:8px;margin-top:36px}table{width:100%;border-collapse:collapse;margin:16px 0}td,th{border:1px solid #dce3e8;padding:9px;text-align:left;overflow-wrap:anywhere}th{background:#edf2f4}.notice{padding:16px;background:#fff4df}.table-wrap{overflow-x:auto}@media(max-width:768px){main{margin:0;padding:20px}}@media print{body{background:white}main{margin:0;padding:0}thead{display:table-header-group}tr{break-inside:avoid}}</style></head><body><main><header><p>SENSITIVE INTERNAL ARTIFACT</p><h1>MedSynth Guard</h1><p>Synthetic health data governance report</p><h2>"
        + escape(project.name)
        + "</h2><p>Evaluation "
        + escape(str(run.id))
        + "</p></header><p class='notice'>"
        + escape(LIMITATIONS[0])
        + "</p>"
        + "".join(sections)
        + "</main></body></html>"
    ).encode("utf-8")


class GovernanceReportService:
    def __init__(self, session, store):
        self.session, self.store = session, store

    def create(self, evaluation_id):
        written = None
        try:
            with self.session.begin():
                run = self.session.scalar(
                    select(EvaluationRun).where(EvaluationRun.id == evaluation_id).with_for_update()
                )
                if run is None:
                    raise AppError("Evaluation does not exist", "EVALUATION_NOT_FOUND", 404)
                job = self.session.get(GenerationJob, run.execution_job_id)
                if job.status != "SUCCEEDED":
                    raise AppError(
                        "A completed evaluation is required", "REPORT_EVALUATION_INCOMPLETE", 409
                    )
                artifacts = list(
                    self.session.scalars(
                        select(Artifact).where(
                            Artifact.job_id.in_([run.execution_job_id, run.generation_job_id])
                        )
                    )
                )
                existing = next(
                    (a for a in artifacts if a.artifact_type == "GOVERNANCE_REPORT"), None
                )
                if existing:
                    return artifact_response(existing)
                reference = next(a for a in artifacts if a.artifact_type == "EVALUATION_MANIFEST")
                raw = verified_bytes(
                    self.store,
                    reference.storage_key,
                    reference.sha256,
                    reference.size_bytes,
                    "ARTIFACT_INTEGRITY_FAILED",
                    20 * 1024**2,
                )
                manifest = json.loads(raw)
                project = self.session.get(Project, run.project_id)
                dataset = self.session.get(Dataset, run.dataset_id)
                generation = self.session.get(GenerationJob, run.generation_job_id)
                content = render_report(project, dataset, generation, run, manifest, artifacts)
                artifact_id = uuid4()
                filename = sanitize_filename(
                    f"medsynth-guard_{project.id.hex[:8]}_{run.id.hex[:8]}_governance-report.html"
                )
                key = f"projects/{project.id.hex}/evaluations/{run.id.hex}/{artifact_id.hex}/{filename}"
                info = self.store.put(key, io.BytesIO(content))
                written = key
                artifact = Artifact(
                    id=artifact_id,
                    job_id=job.id,
                    artifact_type="GOVERNANCE_REPORT",
                    filename=filename,
                    content_type="text/html; charset=utf-8",
                    size_bytes=info.size_bytes,
                    sha256=info.sha256,
                    storage_key=key,
                    metadata_json={
                        "evaluation_run_id": str(run.id),
                        "policy_version": run.policy_version,
                        "policy_hash": run.policy_hash,
                        "sensitive_internal": True,
                        "report_version": 1,
                    },
                )
                self.session.add(artifact)
                AuditRepository(self.session).record(
                    "GOVERNANCE_REPORT_GENERATED", "evaluation", run.id
                )
            return artifact_response(artifact)
        except Exception:
            if written:
                # Retain bytes on unknown commit outcomes, as in existing publication.
                try:
                    with Session(bind=self.session.get_bind()) as check:
                        referenced = check.scalar(
                            select(Artifact.id).where(Artifact.storage_key == written)
                        )
                    if referenced is None:
                        self.store.delete(written)
                except Exception:
                    log_event("orphan_reconciliation_required", artifact_id=str(artifact_id))
            raise
