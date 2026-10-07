import json
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression, Ridge

from backend.app.core.errors import AppError
from backend.app.schemas.evaluation import DisclosureConfig, EvaluationCreate, UtilityConfig
from backend.app.services.evaluation.execution import execute
from backend.app.services.evaluation.inputs import reconstruct_inputs
from backend.app.services.evaluation.privacy import dcr_evaluation, disclosure_evaluation
from backend.app.services.evaluation.utility import utility_evaluation
from backend.app.services.tabular.profile import resolve_metadata
from backend.tests.evaluation_fixture import real_bundle

pytestmark = pytest.mark.model


def test_real_quality_dcr_disclosure_binary_reports(tmp_path, settings):
    spec, _, _, _ = real_bundle(tmp_path, settings)
    result = execute(spec, tmp_path, settings)
    summary = result["summary"]
    for partition in ("training", "holdout"):
        quality = summary["quality"][partition]
        assert 0 <= quality["score"] <= 1
        for prop in quality["properties"].values():
            assert 0 <= prop["score"] <= 1
        assert quality["column_metrics"] and quality["pair_metrics"]
    privacy = summary["privacy"]
    assert (
        privacy["dcr_baseline_protection"]["breakdown"]["median_DCR_to_real_data"]["synthetic_data"]
        >= 0
    )
    assert "patient_id" not in privacy["dcr_baseline_protection"]["columns_used"]
    assert not privacy["dcr_overfitting_protection"]["methodology"]["gating_eligible"]
    disclosure = privacy["disclosure_protection"]
    assert disclosure["configuration"]["known_columns"] == ["age_group", "sex"]
    assert all(
        np.isfinite(disclosure["breakdown"][key])
        for key in ("score", "cap_protection", "baseline_protection")
    )
    assert disclosure["real_partition"] == "HOLDOUT"
    assert summary["utility"]["target"] == "readmitted"
    assert set(result["reports"]) == {
        "QUALITY_REPORT",
        "PRIVACY_REPORT",
        "UTILITY_REPORT",
        "RELEASE_DECISION",
    }
    for name in result["reports"]:
        report = json.loads(
            (tmp_path / "generated" / spec["token"] / f"{name.lower()}.json").read_text()
        )
        assert report


@pytest.mark.parametrize(
    "task,target",
    [
        ("BINARY_CLASSIFICATION", "readmitted"),
        ("MULTICLASS_CLASSIFICATION", "diagnosis_group"),
        ("REGRESSION", "lab_value"),
    ],
)
def test_actual_utility_no_holdout_fit(task, target, tmp_path, settings, monkeypatch):
    spec, _, _, _ = real_bundle(tmp_path, settings)
    training, held, synthetic, columns, _, group, _, request, _ = reconstruct_inputs(
        spec["configuration"],
        spec["source_path"],
        spec["synthetic_path"],
        spec["manifest_path"],
        settings,
    )
    original_holdout = held.copy(deep=True)
    preprocessing_rows, estimator_rows = [], []
    actual_transform = ColumnTransformer.fit_transform

    def record_transform(self, frame, *args, **kwargs):
        preprocessing_rows.append(frame.copy())
        return actual_transform(self, frame, *args, **kwargs)

    monkeypatch.setattr(ColumnTransformer, "fit_transform", record_transform)
    cls = Ridge if task == "REGRESSION" else LogisticRegression
    actual_fit = cls.fit

    def record_fit(self, x, y, *args, **kwargs):
        estimator_rows.append(len(y))
        return actual_fit(self, x, y, *args, **kwargs)

    monkeypatch.setattr(cls, "fit", record_fit)
    report = utility_evaluation(
        training,
        synthetic,
        held,
        columns,
        UtilityConfig(task=task, target=target),
        request,
        settings,
        group,
    )
    assert estimator_rows == [len(training), len(synthetic)]
    assert len(preprocessing_rows) == 2
    assert set(preprocessing_rows[0].index) == set(training.index)
    assert not set(preprocessing_rows[0].index) & set(held.index)
    assert len(preprocessing_rows[1]) == len(synthetic)
    pd.testing.assert_frame_equal(held, original_holdout)
    assert not report["holdout_fit"]
    assert all(
        np.isfinite(v) for key in ("trtr", "tstr") for v in report[key].values() if v is not None
    )
    if task == "REGRESSION":
        assert report["comparisons"]["r2"]["ratio"] is None
        assert report["comparisons"]["rmse"]["ratio"] == pytest.approx(
            report["trtr"]["rmse"] / report["tstr"]["rmse"]
        )
    elif task == "MULTICLASS_CLASSIFICATION":
        assert "macro_f1" in report["tstr"]
        missing = synthetic[synthetic[target] != training[target].iloc[0]]
        with pytest.raises(AppError) as error:
            utility_evaluation(
                training,
                missing,
                held,
                columns,
                UtilityConfig(task=task, target=target),
                request,
                settings,
                group,
            )
        assert error.value.code == "UTILITY_TARGET_CLASS_MISSING"


def test_real_overfitting_memorization_and_eligibility(tmp_path, settings):
    spec, _, _, _ = real_bundle(tmp_path, settings, holdout_fraction=0.5)
    training, held, synthetic, columns, _, group, _, request, _ = reconstruct_inputs(
        spec["configuration"],
        spec["source_path"],
        spec["synthetic_path"],
        spec["manifest_path"],
        settings,
    )
    _, normal = dcr_evaluation(training, synthetic, held, columns, request, settings, group)
    # Deliberate source copying is a test-only unsafe fixture, never a production engine.
    copied = pd.concat([training, training], ignore_index=True)
    _, memorized = dcr_evaluation(training, copied, held, columns, request, settings, group)
    assert normal["methodology"]["gating_eligible"]
    assert memorized["score"] == 0 and normal["score"] > memorized["score"]


def test_actual_dcr_nan_domain_and_limits(settings):
    real = pd.DataFrame({"flag": [True] * 100})
    columns = resolve_metadata(real, {}, {})
    request = EvaluationCreate(profile="STANDARD", independent_rows=True)
    baseline, overfit = dcr_evaluation(
        real.iloc[:50],
        real.copy(),
        real.iloc[50:],
        columns,
        request,
        settings,
        {"gating_eligible": True},
    )
    assert baseline["score"] is None and baseline["applicability"] == "NOT_APPLICABLE"
    assert overfit["score"] is None and overfit["applicability"] == "NOT_APPLICABLE"
    baseline, overfit = dcr_evaluation(
        real.iloc[:50],
        real.copy(),
        real.iloc[50:],
        columns,
        request,
        replace(settings, dcr_max_rows=20),
        {"gating_eligible": True},
    )
    assert baseline["applicability"] == overfit["applicability"] == "INSUFFICIENT_DATA"


def test_group_leakage_original_split_not_corrected(tmp_path, settings):
    spec, _, _, _ = real_bundle(tmp_path, settings, duplicated_groups=True)
    training, held, synthetic, columns, split, group, _, request, _ = reconstruct_inputs(
        spec["configuration"],
        spec["source_path"],
        spec["synthetic_path"],
        spec["manifest_path"],
        settings,
    )
    assert group["overlapping_groups"] > 0 and not group["gating_eligible"]
    assert split["training_row_count"] == 320 and split["holdout_row_count"] == 80
    assert group["semantics"] == "ROW_SPLIT"
    assert "EVALUATION_LEAKAGE_WARNING" in group["warnings"][0]
    report = utility_evaluation(
        training, synthetic, held, columns, request.utility, request, settings, group
    )
    assert report["applicability"] == "ADVISORY_ONLY"


def test_real_estimated_disclosure_and_seeded_sampling(tmp_path, settings):
    spec, _, _, _ = real_bundle(tmp_path, settings)
    training, held, synthetic, columns, _, group, _, request, _ = reconstruct_inputs(
        spec["configuration"],
        spec["source_path"],
        spec["synthetic_path"],
        spec["manifest_path"],
        settings,
    )
    config = DisclosureConfig(
        known_columns=["age_group", "sex"], sensitive_columns=["diagnosis_group"], estimated=True
    )
    bounded = replace(settings, disclosure_estimate_rows=20, disclosure_estimate_iterations=2)
    first = disclosure_evaluation(held, synthetic, config, request, bounded, group)
    second = disclosure_evaluation(held, synthetic, config, request, bounded, group)
    assert first["metric_type"] == "DisclosureProtectionEstimate"
    assert first["sampling"]["mode"] == "ESTIMATED"
    assert (
        first["sampling"]["iterations"] == 2 and first["sampling"]["actual_real_sample_rows"] == 20
    )
    assert first["score"] == second["score"] and 0 <= first["score"] <= 1
