import copy
import json

import pytest
from pydantic import ValidationError

from backend.app.core.errors import AppError
from backend.app.schemas.evaluation import DisclosureConfig, EvaluationCreate, PolicyCreate
from backend.app.services.evaluation.common import json_safe, metric
from backend.app.services.evaluation.inputs import validate_columns, verified_bytes
from backend.app.services.evaluation.policy import evaluate_policy, policy_hash
from backend.app.services.evaluation.utility import compare_metric
from backend.app.services.tabular.profile import resolve_metadata
from backend.app.storage.local import LocalArtifactStore
from backend.tests.tabular_fixture import clinical_fixture


def policy(**rules):
    request = PolicyCreate(name="Engineering policy", version=1, rules=rules)
    return {
        "id": "policy",
        "policy_hash": policy_hash(request.model_dump()),
        **request.model_dump(),
    }


@pytest.mark.parametrize(
    "status,expected",
    [
        ("APPLICABLE", "PASS"),
        ("NOT_APPLICABLE", "REVIEW_REQUIRED"),
        ("INSUFFICIENT_DATA", "REVIEW_REQUIRED"),
        ("ADVISORY_ONLY", "REVIEW_REQUIRED"),
        ("FAILED", "REVIEW_REQUIRED"),
    ],
)
def test_required_policy_evidence(status, expected):
    p = policy(holdout_column_shapes={"minimum": 0.5})
    result = evaluate_policy(p, {"holdout_column_shapes": metric(0.6, status)}, EvaluationCreate())
    assert result["decision"] == expected
    assert result["rules"][0]["actual_value"] == 0.6
    if status == "FAILED":
        assert result["rules"][0]["status"] == "ERROR"


def test_policy_fail_optional_unavailable_condition_and_no_policy():
    p = policy(
        structural_validation={"equals": True},
        disclosure_protection={"minimum": 0.5, "required": False},
    )
    assert (
        evaluate_policy(
            p, {"structural_validation": metric(True, "APPLICABLE")}, EvaluationCreate()
        )["decision"]
        == "PASS"
    )
    assert (
        evaluate_policy(
            p, {"structural_validation": metric(False, "APPLICABLE")}, EvaluationCreate()
        )["decision"]
        == "FAIL"
    )
    assert evaluate_policy(None, {}, EvaluationCreate())["decision"] == "NOT_EVALUATED"
    conditional = policy(
        disclosure_protection={"minimum": 0.5, "when": "DISCLOSURE_CONFIGURED"},
        structural_validation={"equals": True},
    )
    r = evaluate_policy(
        conditional, {"structural_validation": metric(True, "APPLICABLE")}, EvaluationCreate()
    )
    assert r["decision"] == "PASS" and r["rules"][0]["status"] == "NOT_APPLICABLE"


def test_policy_hash_stability_and_threshold_types():
    p = policy(structural_validation={"equals": True}, holdout_column_shapes={"minimum": 0.5})
    fields = {k: p[k] for k in PolicyCreate.model_fields}
    other = copy.deepcopy(fields)
    other["rules"] = dict(reversed(list(other["rules"].items())))
    assert policy_hash(fields) == policy_hash(other)
    other["version"] = 2
    assert policy_hash(fields) != policy_hash(other)
    with pytest.raises(ValidationError):
        PolicyCreate(name="x", version=1, rules={"structural_validation": {"minimum": 0.5}})
    with pytest.raises(ValidationError):
        PolicyCreate(
            name="x", version=1, rules={"holdout_column_shapes": {"minimum": float("nan")}}
        )


@pytest.mark.parametrize(
    "configuration",
    [
        {"profile": "BASIC", "utility": {"target": "age", "task": "REGRESSION"}},
        {"group_key": "patient_id", "independent_rows": True},
        {"minimum_holdout_rows": 1},
        {"dcr_max_train_validation_ratio": 10},
        {"random_seed": -1},
    ],
)
def test_invalid_evaluation_configuration(configuration):
    with pytest.raises(ValidationError):
        EvaluationCreate.model_validate(configuration)


def test_attacker_columns_targets_and_explicit_continuous_types():
    columns = resolve_metadata(clinical_fixture(), {}, {})
    for group_key in ("clinical_notes", "missing"):
        with pytest.raises(AppError):
            validate_columns(EvaluationCreate(group_key=group_key), columns)
    validate_columns(EvaluationCreate(group_key="patient_id"), columns)
    for target in ("patient_id", "clinical_notes", "missing", "admission_date"):
        with pytest.raises(AppError):
            validate_columns(
                EvaluationCreate(
                    profile="FULL", utility={"target": target, "task": "BINARY_CLASSIFICATION"}
                ),
                columns,
            )
    with pytest.raises(ValidationError):
        DisclosureConfig(known_columns=["age"], sensitive_columns=["age"])
    with pytest.raises(AppError):
        validate_columns(
            EvaluationCreate(
                profile="FULL",
                privacy={"known_columns": ["age"], "sensitive_columns": ["diagnosis_group"]},
            ),
            columns,
        )
    validate_columns(
        EvaluationCreate(
            profile="FULL",
            privacy={
                "known_columns": ["age", "sex"],
                "sensitive_columns": ["diagnosis_group"],
                "continuous_columns": ["age"],
            },
        ),
        columns,
    )
    with pytest.raises(AppError):
        validate_columns(
            EvaluationCreate(
                profile="FULL", utility={"target": "age", "task": "BINARY_CLASSIFICATION"}
            ),
            columns,
        )


def test_metric_aware_ratios_and_nonfinite_json():
    assert compare_metric(0.5, 0.4, "f1")["ratio"] == pytest.approx(0.8)
    assert compare_metric(2, 4, "mae")["ratio"] == 0.5
    assert compare_metric(2, 4, "rmse")["ratio"] == 0.5
    assert compare_metric(-0.5, -1, "r2")["ratio"] is None
    assert compare_metric(0, 0.2, "f1")["ratio"] is None
    assert json.dumps(json_safe({"score": float("nan")}), allow_nan=False) == '{"score": null}'


def test_integrity_bounds_and_missing_artifacts(tmp_path):
    store = LocalArtifactStore(tmp_path)
    import io

    info = store.put("source.csv", io.BytesIO(b"fake"))
    assert (
        verified_bytes(
            store, "source.csv", info.sha256, 4, "EVALUATION_SOURCE_INTEGRITY_FAILED", 10
        )
        == b"fake"
    )
    for sha, size, maximum, expected in (
        ("0" * 64, 4, 10, "EVALUATION_SOURCE_INTEGRITY_FAILED"),
        (info.sha256, 4, 3, "EVALUATION_RESOURCE_LIMIT"),
    ):
        with pytest.raises(AppError) as error:
            verified_bytes(
                store, "source.csv", sha, size, "EVALUATION_SOURCE_INTEGRITY_FAILED", maximum
            )
        assert error.value.code == expected
    store.delete("source.csv")
    with pytest.raises(AppError) as error:
        verified_bytes(
            store, "source.csv", info.sha256, 4, "EVALUATION_SOURCE_INTEGRITY_FAILED", 10
        )
    assert error.value.code == "EVALUATION_SOURCE_INTEGRITY_FAILED"
