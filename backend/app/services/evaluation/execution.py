import json
from datetime import datetime, timezone
from platform import python_version
from time import perf_counter

from ...core.errors import AppError
from ...schemas.evaluation import PolicyCreate
from ..jobs.provenance import repository_revision
from ..tabular.validation import exact_row_diagnostic
from .common import json_safe, metric, runtime_versions
from .inputs import reconstruct_inputs
from .policy import evaluate_policy, evidence_catalog, policy_hash
from .privacy import DISCLAIMER, dcr_evaluation, disclosure_evaluation
from .quality import fidelity
from .utility import utility_evaluation


def execute(spec, workspace, settings, on_event=lambda event: None):
    started_at = datetime.now(timezone.utc)
    start = perf_counter()
    cfg = spec["configuration"]
    (
        training,
        holdout,
        synthetic,
        columns,
        split,
        group,
        structural,
        request,
        generation_manifest,
    ) = reconstruct_inputs(
        cfg, spec["source_path"], spec["synthetic_path"], spec["manifest_path"], settings
    )
    on_event("QUALITY_EVALUATION_STARTED")
    quality = {
        "structural_validation": structural,
        "training": fidelity(
            training, synthetic, columns, request.random_seed, settings.quality_subsample_rows, 2
        ),
        "holdout": fidelity(
            holdout,
            synthetic,
            columns,
            request.random_seed + 2,
            settings.quality_subsample_rows,
            request.minimum_holdout_rows,
        ),
    }
    on_event("QUALITY_EVALUATION_COMPLETED")
    privacy = {
        "disclaimer": DISCLAIMER,
        "exact_training": exact_row_diagnostic(synthetic, training),
        "exact_holdout": {
            **exact_row_diagnostic(synthetic, holdout),
            "comparison": "modelled columns; typed equality vs holdout only; nulls equal",
        },
        "group_assessment": group,
        "dcr_baseline_protection": metric(),
        "dcr_overfitting_protection": metric(),
        "disclosure_protection": metric(),
    }
    if request.profile in {"STANDARD", "FULL"}:
        privacy["dcr_baseline_protection"], privacy["dcr_overfitting_protection"] = dcr_evaluation(
            training, synthetic, holdout, columns, request, settings, group
        )
    if request.profile == "FULL":
        privacy["disclosure_protection"] = disclosure_evaluation(
            holdout, synthetic, request.privacy, request, settings, group
        )
    on_event("PRIVACY_EVALUATION_COMPLETED")
    utility = (
        utility_evaluation(
            training, synthetic, holdout, columns, request.utility, request, settings, group
        )
        if request.profile == "FULL"
        else metric()
    )
    if request.utility:
        on_event("UTILITY_EVALUATION_COMPLETED")
    policy = cfg["policy"]
    if (
        policy is not None
        and policy_hash({key: policy[key] for key in PolicyCreate.model_fields})
        != policy["policy_hash"]
    ):
        raise AppError("Release policy snapshot integrity failed", "EVALUATION_POLICY_INVALID")
    decision = evaluate_policy(
        policy, evidence_catalog(structural, quality, privacy, utility, group), request
    )
    on_event("POLICY_EVALUATED")
    warnings = group["warnings"] + quality["holdout"]["warnings"]
    if privacy["exact_training"]["exact_matching_generated_rows"]:
        warnings.append(
            "Exact training-row matches observed; neither matches nor zero matches establish privacy"
        )
    for key in ("dcr_baseline_protection", "dcr_overfitting_protection", "disclosure_protection"):
        warnings.extend(privacy[key]["warnings"])
    warnings.extend(utility["warnings"])
    duration = perf_counter() - start
    summary = json_safe(
        {
            "structural": structural,
            "quality": quality,
            "privacy": privacy,
            "utility": utility,
            "release": decision,
            "warnings": warnings,
            "duration_seconds": duration,
            "generation_performance": generation_manifest["tabular"]["performance"],
        }
    )
    commit, dirty = repository_revision()
    manifest = json_safe(
        {
            "manifest_version": 1,
            "evaluation_run_id": cfg["evaluation_run_id"],
            "generation_job_id": generation_manifest["job_id"],
            "execution_job_id": spec["job_id"],
            "project_id": spec["project_id"],
            "dataset_id": spec["dataset_id"],
            "inputs": cfg["inputs"],
            "evaluation_profile": request.profile,
            "configuration": cfg,
            "source_split": split,
            "group_assessment": group,
            "application_version": settings.app_version,
            "application_commit": settings.app_commit or commit,
            "application_build_timestamp": settings.app_build_timestamp,
            "application_worktree_dirty": dirty,
            "python_version": python_version(),
            "library_versions": runtime_versions(),
            "metric_outputs": summary,
            "policy": policy,
            "decision": decision["decision"],
            "decision_reasons": decision["reasons"],
            "started_at": started_at.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "duration_seconds": duration,
            "random_seed": request.random_seed,
            "reproducibility": "Seeded utility and explicit sampling; upstream DCR random baseline lacks a public seed hook; exact baseline scores may vary",
            "warnings": warnings,
        }
    )
    root = workspace / "generated" / spec["token"]
    root.mkdir(parents=True, exist_ok=True)
    reports = {"QUALITY_REPORT": quality, "PRIVACY_REPORT": privacy, "RELEASE_DECISION": decision}
    if request.utility:
        reports["UTILITY_REPORT"] = utility
    for name, report in reports.items():
        (root / f"{name.lower()}.json").write_text(
            json.dumps(json_safe(report), indent=2, allow_nan=False), encoding="utf-8"
        )
    return {"reports": list(reports), "manifest": manifest, "summary": summary}
