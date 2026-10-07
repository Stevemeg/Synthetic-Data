import math
import random

import numpy as np

from .common import bounded_sample, metadata_for, metric

DISCLAIMER = "These metrics measure selected statistical disclosure and overfitting risks. They do not prove anonymity or regulatory compliance."


def dcr_evaluation(training, synthetic, holdout, columns, request, settings, group):
    from sdmetrics.single_table import DCRBaselineProtection, DCROverfittingProtection

    selected = list(training.columns)
    sampled = bounded_sample(synthetic, settings.dcr_max_rows, request.random_seed)
    sampling = {
        "mode": "SUBSAMPLED" if len(sampled) < len(synthetic) else "FULL",
        "synthetic_rows": len(sampled),
        "training_rows": len(training),
        "validation_rows": len(holdout),
        "iterations": 1,
        "seed": request.random_seed,
        "reference_subsampling": False,
    }
    ratio = len(training) / len(holdout) if len(holdout) else None
    maximum = request.dcr_max_train_validation_ratio
    eligible = bool(
        ratio is not None
        and 1 / maximum <= ratio <= maximum
        and len(holdout) >= request.minimum_holdout_rows
        and group["gating_eligible"]
    )
    methodology = {
        "training_rows": len(training),
        "validation_rows": len(holdout),
        "train_validation_ratio": ratio,
        "operational_ratio_range": [1 / maximum, maximum],
        "minimum_holdout_rows": request.minimum_holdout_rows,
        "threshold_origin": "MedSynth Guard operational policy; not an SDMetrics requirement",
        "gating_eligible": eligible,
        "full_training_reference": True,
    }
    warnings = (
        []
        if eligible
        else [
            "DCR overfitting is advisory: imbalanced/limited holdout or entity leakage/undeclared semantics; training was not downsampled to manufacture balance"
        ]
    )
    baseline = metric(columns_used=selected, sampling=sampling)
    overfit = metric(
        columns_used=selected, sampling=sampling, methodology=methodology, warnings=warnings
    )
    # Bound reference distance computation without silently replacing the original training set.
    if len(training) > settings.dcr_max_rows:
        reason = ["Full training reference exceeds DCR operational limit; metric not computed"]
        baseline.update(applicability="INSUFFICIENT_DATA", warnings=reason)
        overfit.update(applicability="INSUFFICIENT_DATA", warnings=reason + warnings)
        return baseline, overfit
    np.random.seed(request.random_seed)
    random.seed(request.random_seed)
    breakdown = DCRBaselineProtection.compute_breakdown(
        training, sampled, metadata_for(columns), "clinical"
    )
    baseline = metric(
        breakdown["score"],
        "APPLICABLE" if math.isfinite(breakdown["score"]) else "NOT_APPLICABLE",
        columns_used=selected,
        sampling=sampling,
        breakdown=breakdown,
        warnings=[
            "Random baseline uses upstream default_rng without a public seed hook; repeated scores may vary"
        ],
    )
    if not math.isfinite(breakdown["score"]):
        baseline["warnings"].append(
            "INSUFFICIENT_DOMAIN: zero random baseline distance; no numeric replacement"
        )
    if len(holdout) < 2 or len(holdout) > settings.dcr_max_rows:
        overfit.update(applicability="INSUFFICIENT_DATA")
        return baseline, overfit
    breakdown = DCROverfittingProtection.compute_breakdown(
        training, sampled, holdout, metadata_for(columns), "clinical"
    )
    overfit = metric(
        breakdown["score"],
        ("APPLICABLE" if eligible else "ADVISORY_ONLY")
        if math.isfinite(breakdown["score"])
        else "NOT_APPLICABLE",
        columns_used=selected,
        sampling=sampling,
        methodology=methodology,
        warnings=warnings,
        breakdown=breakdown,
    )
    if baseline["score"] is None:
        overfit.update(score=None, applicability="NOT_APPLICABLE")
        overfit["methodology"]["gating_eligible"] = False
        overfit["warnings"].append("Degenerate distance domain: no release-gating interpretation")
    return baseline, overfit


def disclosure_evaluation(holdout, synthetic, config, request, settings, group):
    from sdmetrics.single_table import DisclosureProtection, DisclosureProtectionEstimate

    if config is None:
        return metric(warnings=["No explicit attacker model configured"])
    if len(holdout) < 2:
        return metric(
            status="INSUFFICIENT_DATA", configuration=config.model_dump(), real_partition="HOLDOUT"
        )
    estimated = config.estimated
    if not estimated and max(len(holdout), len(synthetic)) > settings.disclosure_max_rows:
        return metric(
            status="INSUFFICIENT_DATA",
            warnings=[
                "Full disclosure exceeds operational limit; explicitly request estimated computation"
            ],
            configuration=config.model_dump(),
            real_partition="HOLDOUT",
        )
    np.random.seed(request.random_seed)
    random.seed(request.random_seed)
    kwargs = dict(
        known_column_names=config.known_columns,
        sensitive_column_names=config.sensitive_columns,
        computation_method=config.computation_method,
        continuous_column_names=config.continuous_columns or None,
        num_discrete_bins=config.num_discrete_bins,
    )
    if estimated:
        kwargs.update(
            num_rows_subsample=settings.disclosure_estimate_rows,
            num_iterations=settings.disclosure_estimate_iterations,
            verbose=False,
        )
    implementation = DisclosureProtectionEstimate if estimated else DisclosureProtection
    breakdown = implementation.compute_breakdown(holdout, synthetic, **kwargs)
    applicable = len(holdout) >= request.minimum_holdout_rows and group["gating_eligible"]
    warnings = (
        []
        if applicable
        else ["Limited holdout or entity leakage/undeclared semantics: advisory only"]
    )
    return metric(
        breakdown["score"],
        ("APPLICABLE" if applicable else "ADVISORY_ONLY")
        if math.isfinite(breakdown["score"])
        else "NOT_APPLICABLE",
        metric_type=implementation.__name__,
        breakdown=breakdown,
        configuration=config.model_dump(),
        real_partition="HOLDOUT",
        sampling={
            "mode": "ESTIMATED" if estimated else "FULL",
            "sample_rows": settings.disclosure_estimate_rows if estimated else None,
            "actual_real_sample_rows": min(len(holdout), settings.disclosure_estimate_rows)
            if estimated
            else len(holdout),
            "actual_synthetic_sample_rows": min(len(synthetic), settings.disclosure_estimate_rows)
            if estimated
            else len(synthetic),
            "iterations": settings.disclosure_estimate_iterations if estimated else 1,
            "seed": request.random_seed,
        },
        warnings=warnings,
    )
