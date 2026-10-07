import math

from .common import bounded_sample, json_safe, metadata_for, metric


def fidelity(real, synthetic, columns, seed, max_rows, minimum_rows):
    from sdmetrics.reports import QualityReport

    if len(real) < 2 or len(synthetic) < 2:
        return metric(
            status="INSUFFICIENT_DATA",
            warnings=["At least two rows per input are needed for this report"],
        )
    real_sample = bounded_sample(real, max_rows, seed)
    synthetic_sample = bounded_sample(synthetic, max_rows, seed + 1)
    report = QualityReport()
    report.generate(
        {"clinical": real_sample},
        {"clinical": synthetic_sample},
        metadata_for(columns),
        verbose=False,
    )
    limited = len(real_sample) < minimum_rows
    status = "ADVISORY_ONLY" if limited else "APPLICABLE"
    properties = {}
    for row in report.get_properties().to_dict("records"):
        score = row["Score"]
        properties[row["Property"]] = metric(
            score, status if math.isfinite(score) else "NOT_APPLICABLE"
        )
    details = {}
    for name in properties:
        rows = report.get_details(name, table_name="clinical").to_dict("records")
        for row in rows:
            row["applicability"] = status if math.isfinite(row["Score"]) else "NOT_APPLICABLE"
        details[name] = json_safe(rows)
    return metric(
        report.get_score(),
        status if math.isfinite(report.get_score()) else "NOT_APPLICABLE",
        warnings=["Small holdout: operationally limited estimate, no confidence interval claimed"]
        if limited
        else [],
        properties=properties,
        column_metrics=details.get("Column Shapes", []),
        pair_metrics=details.get("Column Pair Trends", []),
        sampling={
            "mode": "SUBSAMPLED" if len(real) > max_rows or len(synthetic) > max_rows else "FULL",
            "real_rows": len(real_sample),
            "synthetic_rows": len(synthetic_sample),
            "seed": seed,
            "iterations": 1,
        },
        interpretation="Distribution and pairwise fidelity only; not structural validity or complete joint-distribution equivalence",
    )
