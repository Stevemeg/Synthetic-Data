import json
from pathlib import Path

import pandas as pd
from pydantic import ValidationError

from ...core.errors import AppError
from ...schemas.evaluation import EvaluationCreate
from ...schemas.tabular import ColumnMetadata, TabularConfig, ValidationRule
from ...storage.local import hash_stream
from ..tabular.profile import canonical_hash, model_input, read_table
from ..tabular.split import split_table
from ..tabular.validation import validate_structure


def verified_bytes(store, key, sha, size, code, maximum):
    try:
        with store.get(key) as stream:
            actual = hash_stream(stream)
            if actual.sha256 != sha or actual.size_bytes != size:
                raise AppError("Evaluation input integrity verification failed", code)
            if size > maximum:
                raise AppError(
                    "Evaluation input exceeds the operational byte limit",
                    "EVALUATION_RESOURCE_LIMIT",
                )
            stream.seek(0)
            return stream.read(maximum + 1)
    except FileNotFoundError as error:
        raise AppError("Required evaluation input bytes are unavailable", code) from error


def validate_manifest(manifest, generation, dataset, synthetic):
    try:
        configuration = manifest["configuration"]
        tabular = manifest["tabular"]
        expected = configuration["split"]
        columns = [ColumnMetadata.model_validate(c) for c in configuration["columns"]]
        TabularConfig.model_validate(configuration["tabular"])
        if (
            manifest["job_id"] != str(generation.id)
            or manifest["project_id"] != str(dataset.project_id)
            or manifest["dataset_id"] != str(dataset.id)
            or manifest["source_dataset_sha256"] != dataset.sha256
            or configuration["source_sha256"] != dataset.sha256
            or tabular["source_sha256"] != dataset.sha256
            or configuration["metadata_hash"] != canonical_hash(configuration["columns"])
            or tabular["metadata_hash"] != configuration["metadata_hash"]
            or tabular["column_roles"] != configuration["columns"]
            or configuration != generation.configuration_json
            or tabular["split"] != expected
            or expected["algorithm"] != "numpy-pcg64-positional-permutation"
            or expected["algorithm_version"] != "1"
            or tabular["synthetic_artifact"]["id"] != str(synthetic.id)
            or tabular["synthetic_artifact"]["sha256"] != synthetic.sha256
            or manifest["produced_count"] != generation.produced_samples
        ):
            raise ValueError("Manifest references disagree")
        output = next(a for a in manifest["artifacts"] if a["id"] == str(synthetic.id))
        if output["sha256"] != synthetic.sha256 or output["size_bytes"] != synthetic.size_bytes:
            raise ValueError("Manifest artifact differs")
        return columns
    except (KeyError, ValueError, TypeError, StopIteration, ValidationError) as error:
        raise AppError(
            "Generation manifest is incomplete or inconsistent", "EVALUATION_MANIFEST_INVALID"
        ) from error


def validate_columns(request, columns):
    modelled = {c.name: c for c in columns if c.role == "MODELLED"}
    if request.group_key:
        group_column = next((c for c in columns if c.name == request.group_key), None)
        if group_column is None or group_column.role == "EXCLUDED":
            raise AppError(
                "Group key must be a supported non-excluded source column",
                "EVALUATION_CONFIG_INVALID",
            )
    if request.privacy:
        referenced = set(request.privacy.known_columns + request.privacy.sensitive_columns)
        if not referenced <= set(modelled):
            raise AppError(
                "Disclosure requires modelled known/sensitive columns", "EVALUATION_CONFIG_INVALID"
            )
        continuous = {
            name for name in referenced if modelled[name].semantic_type in {"numerical", "datetime"}
        }
        if continuous != set(request.privacy.continuous_columns):
            raise AppError(
                "Explicit continuous-column configuration must match selected numerical/datetime types",
                "EVALUATION_CONFIG_INVALID",
            )
    if request.utility:
        target = modelled.get(request.utility.target)
        if target is None or target.name == request.group_key:
            raise AppError(
                "Utility target must be a modelled non-group column", "UTILITY_TARGET_INVALID"
            )
        if (request.utility.task == "REGRESSION") != (target.semantic_type == "numerical"):
            raise AppError(
                "Declared task is incompatible with target semantic type", "UTILITY_TARGET_INVALID"
            )
        if target.semantic_type == "datetime":
            raise AppError("Datetime targets are unsupported", "UTILITY_TARGET_INVALID")


def reconstruct_inputs(configuration, source_path, synthetic_path, manifest_path, settings):
    for name, path, code in (
        ("source", source_path, "EVALUATION_SOURCE_INTEGRITY_FAILED"),
        ("synthetic", synthetic_path, "EVALUATION_SYNTHETIC_INTEGRITY_FAILED"),
        ("generation_manifest", manifest_path, "EVALUATION_MANIFEST_INVALID"),
    ):
        descriptor = configuration["inputs"][name]
        with Path(path).open("rb") as stream:
            actual = hash_stream(stream)
        if actual.sha256 != descriptor["sha256"] or actual.size_bytes != descriptor["size_bytes"]:
            raise AppError("Materialized evaluation input integrity failed", code)
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if canonical_hash(manifest) != configuration["generation_manifest_hash"]:
        raise AppError("Materialized generation manifest differs", "EVALUATION_MANIFEST_INVALID")
    source = read_table(Path(source_path), settings)
    columns = [ColumnMetadata.model_validate(c) for c in manifest["configuration"]["columns"]]
    typed = model_input(source, columns)
    training, holdout, split = split_table(
        typed, TabularConfig.model_validate(manifest["configuration"]["tabular"])
    )
    if (
        split != manifest["tabular"]["split"]
        or set(training.index) & set(holdout.index)
        or set(training.index) | set(holdout.index) != set(range(len(source)))
    ):
        raise AppError("Source partition reconstruction failed", "EVALUATION_MANIFEST_INVALID")
    request = EvaluationCreate.model_validate(configuration["request"])
    validate_columns(request, columns)
    group = {
        "semantics": "ROW_SPLIT",
        "group_key": request.group_key,
        "independent_rows_declared": request.independent_rows,
        "assessed": bool(request.group_key or request.independent_rows),
        "gating_eligible": request.independent_rows,
        "warnings": [],
    }
    if request.group_key:
        values = source[request.group_key]
        if values.isna().any():
            raise AppError("Group key must be complete", "EVALUATION_CONFIG_INVALID")
        train_groups, held_groups = set(values.loc[training.index]), set(values.loc[holdout.index])
        collisions = len(train_groups & held_groups)
        group.update(
            training_groups=len(train_groups),
            holdout_groups=len(held_groups),
            overlapping_groups=collisions,
            gating_eligible=collisions == 0,
        )
        if collisions:
            group["warnings"].append(
                "EVALUATION_LEAKAGE_WARNING: configured groups span the original row split; no retrospective correction or retraining performed"
            )
    elif not request.independent_rows:
        group["warnings"].append(
            "Entity independence is undeclared; no patient-group separation guarantee"
        )
    raw_generated = pd.read_csv(Path(synthetic_path))
    generated = raw_generated.copy()
    sampled = model_input(raw_generated, columns)
    for name in sampled:
        generated[name] = sampled[name]
    for c in columns:
        if c.role == "IDENTIFIER" and c.name in generated:
            generated[c.name] = generated[c.name].map(lambda v: str(v) if pd.notna(v) else v)
    structural = validate_structure(
        generated,
        columns,
        manifest["requested_count"],
        {
            name: ValidationRule.model_validate(rule)
            for name, rule in manifest["configuration"]["validation_rules"].items()
        },
    )
    return training, holdout, sampled, columns, split, group, structural, request, manifest
