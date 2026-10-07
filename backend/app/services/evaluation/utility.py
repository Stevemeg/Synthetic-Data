import math

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
    root_mean_squared_error,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ...core.errors import AppError
from .common import json_safe, metric


def build_pipeline(numeric, categorical, task, seed):
    transformations = []
    if numeric:
        transformations.append(
            (
                "numeric",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="median", keep_empty_features=True)),
                        ("scale", StandardScaler()),
                    ]
                ),
                numeric,
            )
        )
    if categorical:
        transformations.append(
            (
                "categorical",
                Pipeline(
                    [
                        (
                            "impute",
                            SimpleImputer(
                                strategy="constant",
                                fill_value="__MISSING__",
                                keep_empty_features=True,
                            ),
                        ),
                        ("encode", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical,
            )
        )
    model = (
        Ridge(alpha=1.0, solver="lsqr")
        if task == "REGRESSION"
        else LogisticRegression(max_iter=500, solver="lbfgs", random_state=seed)
    )
    return Pipeline([("preprocess", ColumnTransformer(transformations)), ("model", model)])


def feature_frame(frame, columns):
    result = frame[[c.name for c in columns]].copy()
    for c in columns:
        if c.semantic_type == "datetime":
            times = pd.to_datetime(result[c.name], utc=True)
            result[c.name] = times.astype("int64").astype(float) / 1e9
            result.loc[times.isna(), c.name] = np.nan
        elif c.semantic_type in {"boolean", "categorical"}:
            result[c.name] = result[c.name].map(
                lambda value: str(value) if pd.notna(value) else np.nan
            )
    return result


def compare_metric(real, synthetic, name):
    # R-squared may be negative; a ratio would not have stable utility semantics.
    lower = name in {"mae", "rmse"}
    denominator = synthetic if lower else real
    numerator = real if lower else synthetic
    ratio = numerator / denominator if name != "r2" and abs(denominator) > 1e-12 else None
    return {
        "trtr": real,
        "tstr": synthetic,
        "absolute_delta": synthetic - real,
        "ratio": ratio,
        "ratio_semantics": "TRTR/TSTR error; higher means smaller synthetic-trained error"
        if lower
        else ("TSTR/TRTR metric" if name != "r2" else "R2 delta only"),
        "higher_is_better": not lower,
        "ratio_warning": "Near-zero denominator or R2: ratio not defined"
        if ratio is None
        else None,
    }


def utility_evaluation(training, synthetic, holdout, columns, config, request, settings, group):
    if config is None:
        return metric(warnings=["No declared utility task"])
    if len(holdout) < 2:
        return metric(status="INSUFFICIENT_DATA", configuration=config.model_dump())
    if max(len(training), len(synthetic), len(holdout)) > settings.utility_max_rows:
        raise AppError(
            "Utility inputs exceed the operational row limit", "EVALUATION_RESOURCE_LIMIT"
        )
    selected = [
        c
        for c in columns
        if c.role == "MODELLED"
        and c.name != config.target
        and c.name != request.group_key
        and (c.semantic_type != "datetime" or config.datetime_features)
    ]
    if not selected:
        raise AppError("Utility requires at least one usable feature", "UTILITY_TARGET_INVALID")
    x_real, x_syn, x_hold = [
        feature_frame(frame, selected) for frame in (training, synthetic, holdout)
    ]
    numeric = [c.name for c in selected if c.semantic_type in {"numerical", "datetime"}]
    categorical = [c.name for c in selected if c.semantic_type in {"categorical", "boolean"}]
    for train_frame in (x_real, x_syn):
        width = len(numeric) + sum(train_frame[name].nunique(dropna=False) for name in categorical)
        if width * max(len(train_frame), len(x_hold)) > settings.utility_max_encoded_cells:
            raise AppError("Utility encoded feature budget exceeded", "EVALUATION_RESOURCE_LIMIT")
    targets = [frame[config.target] for frame in (training, synthetic, holdout)]
    if any(y.isna().any() for y in targets):
        raise AppError("Utility targets must be complete", "UTILITY_TARGET_INVALID")
    distributions = None
    if config.task == "REGRESSION":
        ys = [pd.to_numeric(y).to_numpy(dtype=float) for y in targets]
        if training[config.target].nunique() < 2:
            raise AppError("Regression training target is constant", "UTILITY_TARGET_INVALID")
        if any(not np.isfinite(y).all() for y in ys):
            raise AppError("Regression target must be finite", "UTILITY_TARGET_INVALID")
    else:
        # Vocabulary is defined on real training ONLY; reports use indexed class labels, without an anonymity claim.
        labels = sorted(targets[0].astype(str).unique())
        required = 2 if config.task == "BINARY_CLASSIFICATION" else 3
        if (
            len(labels) < required
            or (config.task == "BINARY_CLASSIFICATION" and len(labels) != 2)
            or len(labels) > 100
        ):
            raise AppError(
                "Target classes do not match the declared task", "UTILITY_TARGET_INVALID"
            )
        encoded = {label: i for i, label in enumerate(labels)}
        if not set(labels) <= set(targets[1].astype(str)):
            raise AppError(
                "A real training target class is absent from synthetic training",
                "UTILITY_TARGET_CLASS_MISSING",
            )
        if any(not set(y.astype(str)) <= set(labels) for y in targets[1:]):
            raise AppError(
                "Evaluation target contains a class unseen in real training",
                "UTILITY_TARGET_CLASS_MISSING",
            )
        ys = [y.astype(str).map(encoded).to_numpy(dtype=int) for y in targets]
        distributions = {
            name: {f"class_{i}": int((y == i).sum()) for i in range(len(labels))}
            for name, y in zip(("training", "synthetic", "holdout"), ys)
        }
    outputs = []
    for x_train, y_train in ((x_real, ys[0]), (x_syn, ys[1])):
        pipeline = build_pipeline(numeric, categorical, config.task, request.random_seed)
        # No holdout data reaches any .fit; preprocessing is fitted by this pipeline.
        pipeline.fit(x_train, y_train)
        predictions = pipeline.predict(x_hold)
        if config.task == "REGRESSION":
            values = {
                "r2": r2_score(ys[2], predictions),
                "mae": mean_absolute_error(ys[2], predictions),
                "rmse": root_mean_squared_error(ys[2], predictions),
            }
        elif config.task == "BINARY_CLASSIFICATION":
            values = {
                "f1": f1_score(ys[2], predictions, zero_division=0),
                "accuracy": accuracy_score(ys[2], predictions),
                "precision": precision_score(ys[2], predictions, zero_division=0),
                "recall": recall_score(ys[2], predictions, zero_division=0),
            }
            values["roc_auc"] = (
                roc_auc_score(ys[2], pipeline.predict_proba(x_hold)[:, 1])
                if len(set(ys[2])) == 2
                else None
            )
        else:
            values = {
                "macro_f1": f1_score(
                    ys[2],
                    predictions,
                    average="macro",
                    labels=list(encoded.values()),
                    zero_division=0,
                ),
                "accuracy": accuracy_score(ys[2], predictions),
                "weighted_f1": f1_score(ys[2], predictions, average="weighted", zero_division=0),
            }
        outputs.append(values)
    comparison = {
        name: compare_metric(value, outputs[1][name], name)
        for name, value in outputs[0].items()
        if value is not None and outputs[1][name] is not None
    }
    primary = (
        "mae"
        if config.task == "REGRESSION"
        else "f1"
        if config.task == "BINARY_CLASSIFICATION"
        else "macro_f1"
    )
    eligible = len(holdout) >= request.minimum_holdout_rows and group["gating_eligible"]
    report = metric(
        comparison[primary]["ratio"],
        "APPLICABLE" if eligible and comparison[primary]["ratio"] is not None else "ADVISORY_ONLY",
        configuration=config.model_dump(),
        task=config.task,
        target=config.target,
        feature_columns=[c.name for c in selected],
        excluded_columns=[c.name for c in columns if c not in selected and c.name != config.target],
        model="Ridge(alpha=1, solver=lsqr)"
        if config.task == "REGRESSION"
        else "LogisticRegression(max_iter=500, solver=lbfgs)",
        preprocessing={
            "numeric": "median imputation + StandardScaler",
            "categorical": "constant imputation + OneHotEncoder(handle_unknown=ignore)",
            "fit_scope": "corresponding real or synthetic training partition only",
            "datetime": "UTC Unix seconds" if config.datetime_features else "excluded",
        },
        random_seed=request.random_seed,
        trtr=outputs[0],
        tstr=outputs[1],
        comparisons=comparison,
        primary_metric=primary,
        target_distributions=distributions,
        counts={"training": len(training), "synthetic": len(synthetic), "holdout": len(holdout)},
        holdout_fit=False,
        warnings=[]
        if eligible
        else ["Limited holdout or entity leakage/undeclared semantics: advisory only"],
    )
    if not all(math.isfinite(v) for output in outputs for v in output.values() if v is not None):
        report.update(applicability="INSUFFICIENT_DATA", score=None)
        report["warnings"].append("At least one utility metric is not finite")
    return json_safe(report)
