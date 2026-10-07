import re
import shutil
import subprocess  # nosec B404
from datetime import datetime
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from platform import python_version

from ...config import ROOT, Settings
from ...db.models import Dataset, GenerationJob


@lru_cache(maxsize=1)
def repository_revision():
    """Best-effort local build identity; never include filenames or source contents."""
    try:
        executable = shutil.which("git")
        if not executable:
            return None, None
        revision = subprocess.run(
            [executable, "rev-parse", "HEAD"],  # nosec B603
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        commit = revision.stdout.strip()
        if revision.returncode or not re.fullmatch(r"[0-9a-f]{40,64}", commit):
            return None, None
        status = subprocess.run(
            [executable, "status", "--porcelain"],  # nosec B603
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        return commit, bool(status.stdout) if status.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None, None


def build_manifest(
    job: GenerationJob,
    dataset: Dataset | None,
    result: dict,
    artifacts: list[dict],
    model: dict,
    finished_at: datetime,
    settings: Settings,
) -> dict:
    runtime_versions = {"python": python_version()}
    for package in ("numpy", "pandas", "torch", "neurokit2", "sdv", "rdt", "ctgan", "copulas"):
        try:
            runtime_versions[package] = version(package)
        except PackageNotFoundError:
            runtime_versions[package] = None
    metadata = result["metadata"]
    if metadata["produced_sample_count"] != job.requested_samples:
        raise ValueError("Manifest count contract failed")
    warnings = [
        "Complete learned checkpoint is retained as a restricted MODEL_CHECKPOINT artifact."
        if warning.startswith("A full VAE checkpoint was saved")
        else warning
        for warning in metadata["warnings"]
    ]
    commit, dirty = repository_revision()
    return {
        "manifest_version": 1,
        "job_id": str(job.id),
        "project_id": str(job.project_id),
        "dataset_id": str(dataset.id) if dataset else None,
        "source_dataset_sha256": dataset.sha256 if dataset else None,
        "modality": job.modality,
        "maturity": metadata["maturity"],
        "engine_name": job.engine,
        "engine_version": metadata.get("tabular", {}).get("engine_version", "1"),
        "model": model,
        "configuration": job.configuration_json,
        "random_seed": job.random_seed,
        "requested_count": job.requested_samples,
        "produced_count": metadata["produced_sample_count"],
        "started_at": job.started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "attempt_count": job.attempt_count,
        "application_version": settings.app_version,
        "application_commit": settings.app_commit or commit,
        "application_build_timestamp": settings.app_build_timestamp,
        "application_worktree_dirty": dirty,
        "runtime_versions": runtime_versions,
        "source_schema_summary": metadata["source_schema_summary"],
        "warnings": warnings,
        "artifacts": artifacts,
        "duration_seconds": (finished_at - job.started_at).total_seconds(),
        **(
            {
                "tabular": {
                    **metadata["tabular"],
                    "source_sha256": dataset.sha256,
                    "model_artifact_id": model["artifact_id"],
                    "model_sha256": model["sha256"],
                    "synthetic_artifact": next(
                        a for a in artifacts if a["artifact_type"] == "SYNTHETIC_DATASET"
                    ),
                }
            }
            if job.modality == "tabular"
            else {}
        ),
    }
