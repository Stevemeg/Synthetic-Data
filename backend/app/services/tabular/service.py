import io
import json
from pathlib import Path
from time import perf_counter

from pydantic import ValidationError

from ...config import Settings
from ...core.errors import AppError
from ...db.repositories.catalog import AuditRepository, DatasetRepository
from ...schemas.tabular import ColumnMetadata, TabularConfig, ValidationRule
from ...storage.base import ArtifactStore
from ...storage.local import hash_stream
from .engines import available_engines, create_engine, validate_config, validate_training_size
from .profile import (
    METADATA_VERSION,
    canonical_hash,
    model_input,
    profile,
    read_table,
    resolve_metadata,
)
from .split import split_table
from .validation import (
    StructuralValidationError,
    exact_row_diagnostic,
    restore_identifiers,
    validate_structure,
)


def load_registered(dataset, store: ArtifactStore, settings: Settings):
    if (
        dataset.modality != "tabular"
        or dataset.status != "READY"
        or dataset.metadata_json.get("format") != "headered_tabular_csv"
    ):
        raise AppError("A ready single-table CSV dataset is required", "TABULAR_DATASET_INVALID")
    with store.get(dataset.storage_key) as source:
        info = hash_stream(source)
        if info.sha256 != dataset.sha256 or info.size_bytes != dataset.size_bytes:
            raise AppError(
                "Registered source integrity check failed", "SOURCE_ARTIFACT_INTEGRITY_FAILED"
            )
        source.seek(0)
        raw = source.read(settings.max_upload_mb * 1024**2 + 1)
    if len(raw) > settings.max_upload_mb * 1024**2:
        raise AppError("Source exceeds the upload limit", "TABULAR_DATASET_TOO_LARGE")
    try:
        return read_table(io.StringIO(raw.decode("utf-8-sig")), settings)
    except UnicodeError as error:
        raise AppError("Dataset must be UTF-8 CSV", "TABULAR_DATASET_INVALID") from error


def preflight(session, store, settings, dataset_id):
    with session.begin():
        dataset = DatasetRepository(session).get(dataset_id)
        analysis = {
            "dataset_id": str(dataset.id),
            "source_sha256": dataset.sha256,
            **profile(load_registered(dataset, store, settings)),
        }
        dataset.metadata_json = {**dataset.metadata_json, "tabular_profile": analysis}
        AuditRepository(session).record(
            "TABULAR_PREFLIGHT_COMPLETED",
            "dataset",
            dataset.id,
            metadata={
                "row_count": analysis["row_count"],
                "column_count": analysis["column_count"],
                "compatible": analysis["compatible"],
            },
        )
    return analysis


def prepare_submission(dataset, store, settings, request):
    engine = request.engine or "gaussian_copula"
    if engine not in {item["name"] for item in available_engines()}:
        raise AppError("Install the supported tabular runtime", "TABULAR_ENGINE_NOT_AVAILABLE", 501)
    validate_config(engine, request.configuration, request.requested_samples, settings)
    frame = load_registered(dataset, store, settings)
    columns = resolve_metadata(frame, request.metadata_overrides, request.validation_rules)
    typed = model_input(frame, columns)
    training, _, split = split_table(typed, request.configuration)
    validate_training_size(engine, training, columns, settings)
    warnings = ["Automatic role/type inference is advisory and can be wrong"]
    warnings.extend(w for c in columns for w in c.warnings)
    warnings.extend(split["warnings"])
    if engine != "gaussian_copula" and len(training) < getattr(
        settings, f"{engine}_warning_min_rows"
    ):
        warnings.append(
            f"Training rows are below the configured {engine.upper()} operational recommendation; this is not a quality guarantee"
        )
    metadata = [c.model_dump(mode="json") for c in columns]
    return engine, {
        "tabular": request.configuration.model_dump(mode="json"),
        "metadata_version": METADATA_VERSION,
        "columns": metadata,
        "metadata_hash": canonical_hash(metadata),
        "metadata_overrides": {
            name: override.model_dump(exclude_none=True)
            for name, override in request.metadata_overrides.items()
        },
        "validation_rules": {
            name: rule.model_dump() for name, rule in request.validation_rules.items()
        },
        "source_sha256": dataset.sha256,
        "split": split,
        "warnings": warnings,
        "limits": {
            name: getattr(settings, name)
            for name in (
                "tabular_max_source_rows",
                "tabular_max_columns",
                "tabular_max_generated_rows",
                "tabular_max_transformed_cells",
                "ctgan_max_epochs",
                "tvae_max_epochs",
                "tabular_job_timeout_seconds",
                "max_upload_mb",
            )
        },
    }


def execute(spec: dict, workspace: Path, settings: Settings, on_event=lambda event: None) -> dict:
    """Called only in the supervised worker child, after source materialization."""
    start = perf_counter()
    configuration = spec["configuration"]
    source_path = Path(spec["source_path"])
    with source_path.open("rb") as source:
        if hash_stream(source).sha256 != configuration["source_sha256"]:
            raise AppError(
                "Registered source integrity check failed", "SOURCE_ARTIFACT_INTEGRITY_FAILED"
            )
    try:
        config = TabularConfig.model_validate(configuration["tabular"])
        columns = [ColumnMetadata.model_validate(c) for c in configuration["columns"]]
        rules = {
            name: ValidationRule.model_validate(rule)
            for name, rule in configuration["validation_rules"].items()
        }
    except ValidationError as error:
        raise AppError(
            "Persisted tabular configuration is invalid", "TABULAR_CONFIG_INVALID"
        ) from error
    if canonical_hash(configuration["columns"]) != configuration["metadata_hash"]:
        raise AppError("Persisted metadata hash is invalid", "TABULAR_METADATA_INVALID")
    frame = read_table(source_path, settings)
    typed = model_input(frame, columns)
    training, _, split = split_table(typed, config)
    if split != configuration["split"]:
        raise AppError(
            "Reconstructed source split differs from submitted configuration",
            "TABULAR_METADATA_INVALID",
        )
    validate_training_size(spec["engine"], training, columns, settings)
    engine = create_engine(spec["engine"], config, spec["seed"])
    # The typed configuration snapshot includes default neural fields. Submission
    # already checked explicit engine-specific keys; enforce runtime limits here.
    if spec["count"] > settings.tabular_max_generated_rows or (
        spec["engine"] != "gaussian_copula"
        and config.epochs > getattr(settings, f"{spec['engine']}_max_epochs")
    ):
        raise AppError("Persisted request exceeds operational limits", "TABULAR_CONFIG_INVALID")
    fit_start = perf_counter()
    on_event("TABULAR_TRAINING_STARTED")
    engine.fit(training, columns)
    training_duration = perf_counter() - fit_start
    sample_start = perf_counter()
    sampled = engine.sample(spec["count"])
    on_event("TABULAR_SAMPLING_COMPLETED")
    sampling_duration = perf_counter() - sample_start
    generated = restore_identifiers(sampled, columns, frame)
    report = validate_structure(generated, columns, spec["count"], rules)
    diagnostic = exact_row_diagnostic(sampled, training)
    if not report["passed"]:
        raise StructuralValidationError(report)
    on_event("TABULAR_VALIDATION_COMPLETED")
    output = workspace / "generated" / spec["token"]
    output.mkdir(parents=True)
    generated.to_csv(output / "dataset.csv", index=False, lineterminator="\n")
    engine.save(output / "synthesizer.pkl")
    (output / "structural_validation.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    warnings = list(configuration["warnings"])
    warnings.append(
        "Privacy risk, statistical fidelity, clinical validity and ML utility have not been evaluated"
    )
    if diagnostic["exact_matching_generated_rows"]:
        warnings.append(
            "Exact training-row matches observed; this diagnostic alone does not establish privacy risk"
        )
    details = {
        **engine.describe(),
        "metadata_version": METADATA_VERSION,
        "metadata_hash": configuration["metadata_hash"],
        "column_roles": configuration["columns"],
        "split": split,
        "structural_validation": report,
        "exact_row_diagnostic": diagnostic,
        "training_configuration": configuration["tabular"],
        "sampling_configuration": {"num_rows": spec["count"], "random_seed": spec["seed"]},
        "performance": {
            "training_duration_seconds": training_duration,
            "sampling_duration_seconds": sampling_duration,
            "total_duration_seconds": perf_counter() - start,
            "source_rows": len(frame),
            "training_rows": len(training),
            "holdout_rows": split["holdout_row_count"],
            "generated_rows": len(generated),
            "source_columns": len(frame.columns),
            "modelled_columns": len(typed.columns),
            "excluded_columns": sum(c.role == "EXCLUDED" for c in columns),
            "device": engine.describe()["device"],
        },
    }
    return {
        "metadata": {
            "produced_sample_count": len(generated),
            "maturity": "Stable" if spec["engine"] == "gaussian_copula" else "Beta",
            "warnings": warnings,
            "source_schema_summary": {"rows": len(frame), "columns": len(frame.columns)},
            "tabular": details,
        }
    }
