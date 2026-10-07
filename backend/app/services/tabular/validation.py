import re

import numpy as np
import pandas as pd

from ...core.errors import AppError
from ...schemas.tabular import ColumnMetadata, ValidationRule


class StructuralValidationError(AppError):
    def __init__(self, report: dict):
        super().__init__(
            "Generated output failed structural validation", "TABULAR_STRUCTURAL_VALIDATION_FAILED"
        )
        self.diagnostics = {"structural_validation": report}


def restore_identifiers(
    frame: pd.DataFrame, metadata: list[ColumnMetadata], source: pd.DataFrame | None = None
) -> pd.DataFrame:
    result = frame.copy()
    for column in metadata:
        if column.role == "IDENTIFIER":
            original = (
                set(source[column.name].dropna().astype(str)) if source is not None else set()
            )
            identifiers = []
            index = 1
            while len(identifiers) < len(result):
                candidate = f"SYN-{index:06d}"
                if candidate not in original:
                    identifiers.append(candidate)
                index += 1
            result[column.name] = identifiers
    return result[[c.name for c in metadata if c.role != "EXCLUDED"]]


def validate_structure(
    frame: pd.DataFrame,
    metadata: list[ColumnMetadata],
    count: int,
    rules: dict[str, ValidationRule],
) -> dict:
    expected = [c.name for c in metadata if c.role != "EXCLUDED"]
    missing = [c for c in expected if c not in frame]
    unexpected = [c for c in frame.columns if c not in expected]
    dtype_mismatches = []
    nullability = []
    collisions = []
    violations = []
    for column in metadata:
        if column.role == "EXCLUDED" or column.name not in frame:
            continue
        series = frame[column.name]
        values = series.dropna()
        if not column.nullable and series.isna().any():
            nullability.append({"column": column.name, "count": int(series.isna().sum())})
        if column.unique and series.duplicated().any():
            collisions.append({"column": column.name, "count": int(series.duplicated().sum())})
        valid_type = True
        if column.semantic_type == "numerical":
            valid_type = pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(
                series
            )
            if valid_type and not np.isfinite(values.to_numpy(dtype=float)).all():
                violations.append(
                    {
                        "column": column.name,
                        "rule": "finite",
                        "count": int((~np.isfinite(values.to_numpy(dtype=float))).sum()),
                    }
                )
        elif column.semantic_type == "datetime":
            valid_type = (
                pd.to_datetime(values, errors="coerce", format=column.datetime_format or "ISO8601")
                .notna()
                .all()
            )
        elif column.semantic_type == "boolean":
            valid_type = all(isinstance(v, (bool, np.bool_)) for v in values)
        else:
            valid_type = all(isinstance(v, str) for v in values)
        if not valid_type:
            dtype_mismatches.append(column.name)
        rule = rules.get(column.name)
        if rule is None:
            continue
        checks = {}
        if rule.non_null:
            checks["non_null"] = int(series.isna().sum())
        if rule.unique:
            checks["unique"] = int(series.duplicated().sum())
        numeric = pd.to_numeric(values, errors="coerce")
        if rule.numeric_min is not None:
            checks["numeric_min"] = int(((numeric < rule.numeric_min) | numeric.isna()).sum())
        if rule.numeric_max is not None:
            checks["numeric_max"] = int(((numeric > rule.numeric_max) | numeric.isna()).sum())
        if rule.allowed_values is not None:
            checks["allowed_values"] = int((~values.isin(rule.allowed_values)).sum())
        if rule.regex is not None:
            checks["regex"] = sum(re.fullmatch(rule.regex, str(v)) is None for v in values)
        violations.extend(
            {"column": column.name, "rule": name, "count": n} for name, n in checks.items() if n
        )
    ordered = list(frame.columns) == expected
    report = {
        "report_version": "1",
        "requested_rows": count,
        "produced_rows": len(frame),
        "missing_columns": missing,
        "unexpected_columns": unexpected,
        "column_order_valid": ordered,
        "dtype_mismatches": dtype_mismatches,
        "nullability_violations": nullability,
        "identifier_collisions": collisions,
        "rule_violations": violations,
        "excluded_columns_absent": not any(
            c.name in frame for c in metadata if c.role == "EXCLUDED"
        ),
        "accidental_index_absent": not any(
            str(c).startswith("Unnamed:") and c not in expected for c in frame
        ),
    }
    report["passed"] = (
        len(frame) == count
        and ordered
        and not any((missing, unexpected, dtype_mismatches, nullability, collisions, violations))
        and report["excluded_columns_absent"]
        and report["accidental_index_absent"]
    )
    return report


def exact_row_diagnostic(generated: pd.DataFrame, training: pd.DataFrame) -> dict:
    """Exact equality after shared typed preparation; nulls compare equal, no tolerance."""
    sentinel = object()

    def rows(frame):
        return [
            tuple(sentinel if pd.isna(v) else v for v in row)
            for row in frame.itertuples(index=False, name=None)
        ]

    training_rows = set(rows(training))
    count = sum(row in training_rows for row in rows(generated[list(training.columns)]))
    return {
        "exact_matching_generated_rows": count,
        "exact_match_fraction": count / max(len(generated), 1),
        "comparison": "modelled columns only; exact typed equality; nulls equal; training partition only",
        "interpretation": "Diagnostic only; neither matches nor zero matches establish privacy",
    }
