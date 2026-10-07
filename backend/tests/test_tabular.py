import io
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from backend.app.core.errors import AppError
from backend.app.schemas.platform import JobCreate
from backend.app.schemas.tabular import ColumnOverride, TabularConfig, ValidationRule
from backend.app.services.tabular.engines import validate_config, validate_training_size
from backend.app.services.tabular.profile import model_input, profile, read_table, resolve_metadata
from backend.app.services.tabular.split import split_table
from backend.app.services.tabular.validation import (
    exact_row_diagnostic,
    restore_identifiers,
    validate_structure,
)
from backend.tests.tabular_fixture import clinical_fixture


def test_preflight_structural_facts_and_safety():
    frame = clinical_fixture()
    frame["empty"] = None
    frame["constant"] = "same"
    result = profile(frame)
    columns = {c["name"]: c for c in result["columns"]}
    assert columns["patient_id"]["suggested_role"] == "IDENTIFIER"
    assert columns["clinical_notes"]["suggested_role"] == "EXCLUDED"
    assert columns["age"]["inferred_type"] == "numerical"
    assert columns["smoker"]["inferred_type"] == "boolean"
    assert columns["admission_date"]["inferred_type"] == "datetime"
    assert columns["empty"]["all_null"] and columns["empty"]["null_percentage"] == 100
    assert columns["constant"]["constant"]
    assert "SOURCE-" not in str(result) and "Invented private" not in str(result)
    import json

    json.dumps(result)


@pytest.mark.parametrize(
    "raw", ["a,a\n1,2\n", "a,b\n1\n", ",a\n1,2\n", "a\n", 'a,b\n"unterminated,2\n']
)
def test_csv_rejected(settings, raw):
    with pytest.raises(AppError):
        read_table(io.StringIO(raw), settings)


def test_csv_resource_limits(settings):
    with pytest.raises(AppError, match="column limit"):
        read_table(io.StringIO("a,b\n1,2\n"), replace(settings, tabular_max_columns=1))
    with pytest.raises(AppError, match="source row limit"):
        read_table(io.StringIO("a\n1\n2\n"), replace(settings, tabular_max_source_rows=1))


def test_roles_overrides_and_model_input():
    frame = clinical_fixture()
    columns = resolve_metadata(
        frame,
        {
            "age": ColumnOverride(annotations=["QUASI_IDENTIFIER"]),
            "diagnosis_group": ColumnOverride(annotations=["SENSITIVE_ATTRIBUTE"]),
        },
        {},
    )
    data = model_input(frame, columns)
    assert "patient_id" not in data and "clinical_notes" not in data
    assert pd.api.types.is_datetime64_any_dtype(data.admission_date)
    result = restore_identifiers(data.iloc[:10], columns)
    assert result.patient_id.is_unique and result.patient_id.str.startswith("SYN-").all()
    assert not set(result.patient_id) & set(frame.patient_id)
    assert "clinical_notes" not in result
    assert validate_structure(result, columns, 10, {})["passed"]
    frame.loc[0, "patient_id"] = "SYN-000001"
    new_ids = restore_identifiers(data.iloc[:10], columns, frame)
    assert "SYN-000001" not in set(new_ids.patient_id)


@pytest.mark.parametrize(
    "overrides,rules,code",
    [
        ({"unknown": ColumnOverride(role="EXCLUDED")}, {}, "TABULAR_METADATA_INVALID"),
        ({"clinical_notes": ColumnOverride(role="MODELLED")}, {}, "TABULAR_UNSUPPORTED_COLUMN"),
        (
            {"age": ColumnOverride(identifier_strategy="synthetic_sequence")},
            {},
            "TABULAR_METADATA_INVALID",
        ),
        ({}, {"clinical_notes": ValidationRule(non_null=True)}, "TABULAR_METADATA_INVALID"),
        ({}, {"sex": ValidationRule(numeric_min=0)}, "TABULAR_METADATA_INVALID"),
        ({"sex": ColumnOverride(datetime_format="%Y")}, {}, "TABULAR_METADATA_INVALID"),
    ],
)
def test_metadata_rejections(overrides, rules, code):
    with pytest.raises(AppError) as failure:
        resolve_metadata(clinical_fixture(), overrides, rules)
    assert failure.value.code == code


def test_no_modelled_and_unsupported():
    frame = pd.DataFrame({"notes": ["text"] * 10})
    with pytest.raises(AppError) as error:
        resolve_metadata(frame, {}, {})
    assert error.value.code == "TABULAR_NO_MODELLED_COLUMNS"
    frame = pd.DataFrame({"complex": [complex(1, 2)] * 10, "age": range(10)})
    assert profile(frame)["columns"][0]["suggested_role"] == "EXCLUDED"


def test_split_reproducibility_no_overlap_and_small_policy():
    frame = clinical_fixture()
    train, held, info = split_table(frame, TabularConfig())
    assert len(train) == 80 and len(held) == 20
    assert not set(train.index) & set(held.index)
    assert set(train.index) | set(held.index) == set(frame.index)
    pd.testing.assert_frame_equal(train, split_table(frame, TabularConfig())[0])
    assert not train.equals(split_table(frame, TabularConfig(split_seed=43))[0])
    assert split_table(frame.iloc[:15], TabularConfig())[2]["holdout_row_count"] == 0
    assert split_table(frame.iloc[:15], TabularConfig())[2]["warnings"]
    with pytest.raises(AppError):
        split_table(frame.iloc[:9], TabularConfig())


@pytest.mark.parametrize(
    "config",
    [
        {"epochs": 10000000},
        {"batch_size": 11},
        {"holdout_fraction": 0.9},
        {"generator_dim": [1024]},
        {"split_seed": -1},
        {"cuda": "false"},
        {"unknown": 1},
    ],
)
def test_config_bounds(config):
    with pytest.raises(ValidationError):
        TabularConfig.model_validate(config)


def test_operational_limits_and_engine_specific_configuration(settings):
    for engine, config, count, expected in [
        ("gaussian_copula", TabularConfig(), 10001, "TABULAR_GENERATION_LIMIT_EXCEEDED"),
        ("ctgan", TabularConfig(epochs=51), 1, "TABULAR_TRAINING_LIMIT_EXCEEDED"),
        ("tvae", TabularConfig(epochs=51), 1, "TABULAR_TRAINING_LIMIT_EXCEEDED"),
        ("gaussian_copula", TabularConfig(epochs=1), 1, "TABULAR_CONFIG_INVALID"),
        ("ctgan", TabularConfig(default_distribution="norm"), 1, "TABULAR_CONFIG_INVALID"),
    ]:
        with pytest.raises(AppError) as error:
            validate_config(engine, config, count, settings)
        assert error.value.code == expected
    with pytest.raises(ValidationError):
        JobCreate(modality="timeseries", requested_samples=1, engine="tvae")
    frame = clinical_fixture()
    columns = resolve_metadata(frame, {}, {})
    for engine in ("ctgan", "tvae"):
        with pytest.raises(AppError) as failure:
            validate_training_size(
                engine,
                model_input(frame, columns),
                columns,
                replace(settings, tabular_max_transformed_cells=1),
            )
        assert failure.value.code == "TABULAR_DATASET_TOO_LARGE"


def test_validation_reports_objective_violations():
    frame = clinical_fixture()
    metadata = resolve_metadata(frame, {}, {})
    generated = restore_identifiers(model_input(frame, metadata).iloc[:10], metadata)
    generated["age"] = generated["age"].astype(float)
    generated.loc[1, "patient_id"] = generated.loc[0, "patient_id"]
    generated.loc[2, "age"] = np.inf
    generated.loc[3, "age"] = np.nan
    generated.loc[4, "sex"] = "invalid"
    generated.loc[5, "admission_date"] = pd.NaT
    rules = {
        "age": ValidationRule(numeric_min=0, numeric_max=120, non_null=True),
        "sex": ValidationRule(allowed_values=["M", "F", "Other"]),
        "patient_id": ValidationRule(regex="SYN-[0-9]{6}", unique=True),
    }
    report = validate_structure(generated, metadata, 11, rules)
    assert (
        not report["passed"]
        and report["identifier_collisions"]
        and report["nullability_violations"]
    )
    assert {v["rule"] for v in report["rule_violations"]} >= {
        "finite",
        "numeric_max",
        "non_null",
        "allowed_values",
        "unique",
    }
    drift = generated.drop(columns="sex").assign(unexpected=1)
    report = validate_structure(drift, metadata, 10, {})
    assert report["missing_columns"] == ["sex"] and report["unexpected_columns"] == ["unexpected"]
    generated["clinical_notes"] = "unexpected text"
    assert not validate_structure(generated, metadata, 10, {})["excluded_columns_absent"]


def test_exact_overlap_counts_duplicates_nulls_and_only_training():
    training = pd.DataFrame({"x": [1.0, np.nan], "c": ["a", "b"]})
    generated = pd.DataFrame({"x": [1.0, 1.0, np.nan, 2], "c": ["a", "a", "b", "a"]})
    result = exact_row_diagnostic(generated, training)
    assert result["exact_matching_generated_rows"] == 3 and result["exact_match_fraction"] == 0.75
    assert "neither" in result["interpretation"]


@pytest.mark.parametrize(
    "rule",
    [
        {"numeric_min": 2, "numeric_max": 1},
        {"regex": "(a+)+$"},
        {"allowed_values": []},
        {"numeric_min": float("nan")},
    ],
)
def test_rule_bounds(rule):
    with pytest.raises(ValidationError):
        ValidationRule.model_validate(rule)
