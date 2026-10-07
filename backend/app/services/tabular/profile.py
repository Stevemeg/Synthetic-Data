import csv
import hashlib
import io
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import ValidationError

from ...config import Settings
from ...core.errors import AppError
from ...schemas.tabular import ColumnMetadata, ColumnOverride, ValidationRule

METADATA_VERSION = "1"
ID_NAME = re.compile(
    r"(^id$|(^|_)(patient_id|member_id|medical_record_number|mrn|email|phone|ssn|government_id)($|_))",
    re.I,
)
TEXT_NAME = re.compile(
    r"(^|_)(notes?|clinical_notes|comments?|doctor_comments|discharge_summary|address|free_text|description)($|_)",
    re.I,
)


def canonical_hash(value: dict | list) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def read_table(source: Path | io.StringIO, settings: Settings) -> pd.DataFrame:
    """Check the actual CSV header/shape before pandas can mangle duplicate names."""
    try:
        if isinstance(source, Path):
            stream = source.open(encoding="utf-8-sig", newline="")
        else:
            stream = io.StringIO(source.getvalue())
        with stream:
            reader = csv.reader(stream, strict=True)
            header = next(reader)
            if (
                not header
                or any(not c.strip() or len(c) > 128 for c in header)
                or len(set(header)) != len(header)
            ):
                raise AppError(
                    "CSV column names must be nonempty, unique and at most 128 characters",
                    "TABULAR_DATASET_INVALID",
                )
            if len(header) > settings.tabular_max_columns:
                raise AppError(
                    "CSV exceeds the configured column limit", "TABULAR_DATASET_TOO_LARGE"
                )
            rows = 0
            for row in reader:
                if len(row) != len(header):
                    raise AppError(
                        "CSV must be rectangular with no blank records", "TABULAR_DATASET_INVALID"
                    )
                rows += 1
                if rows > settings.tabular_max_source_rows:
                    raise AppError(
                        "CSV exceeds the configured source row limit", "TABULAR_DATASET_TOO_LARGE"
                    )
            if rows == 0:
                raise AppError("CSV contains no records", "TABULAR_DATASET_INVALID")
        if not isinstance(source, Path):
            source = io.StringIO(source.getvalue())
        frame = pd.read_csv(source, encoding="utf-8-sig", low_memory=False)
        if list(frame.columns) != header or len(frame) != rows:
            raise AppError("CSV parser shape does not match its header", "TABULAR_DATASET_INVALID")
        return frame
    except (
        ValueError,
        csv.Error,
        StopIteration,
        pd.errors.ParserError,
        pd.errors.EmptyDataError,
        UnicodeError,
    ) as error:
        raise AppError(
            "Dataset must be a rectangular UTF-8 CSV", "TABULAR_DATASET_INVALID"
        ) from error


def profile(frame: pd.DataFrame) -> dict:
    columns = []
    for name in frame.columns:
        series = frame[name]
        nonnull = series.dropna()
        unique = int(nonnull.nunique())
        ratio = unique / max(len(nonnull), 1)
        warnings = []
        inferred = "categorical"
        unsupported = pd.api.types.is_complex_dtype(series) or not (
            pd.api.types.is_numeric_dtype(series)
            or pd.api.types.is_bool_dtype(series)
            or pd.api.types.is_datetime64_any_dtype(series)
            or all(isinstance(v, str) for v in nonnull)
        )
        if pd.api.types.is_bool_dtype(series) or (
            len(nonnull) and set(nonnull.astype(str).str.lower()) <= {"true", "false"}
        ):
            inferred = "boolean"
        elif pd.api.types.is_numeric_dtype(series) and not unsupported:
            inferred = "numerical"
            if not np.isfinite(nonnull.to_numpy(dtype=float)).all():
                unsupported = True
        elif pd.api.types.is_datetime64_any_dtype(series):
            inferred = "datetime"
        elif (
            len(nonnull) and nonnull.astype(str).str.match(r"^\d{4}-\d{2}-\d{2}(?:[ T].*)?$").all()
        ):
            if pd.to_datetime(nonnull, errors="coerce", format="ISO8601").notna().all():
                inferred = "datetime"
        text = bool(TEXT_NAME.search(str(name))) or (
            inferred == "categorical"
            and len(nonnull) > 0
            and (
                nonnull.astype(str).str.len().max() > 80
                or (ratio > 0.8 and nonnull.astype(str).str.contains(r"\s").mean() > 0.5)
            )
        )
        identifier = bool(ID_NAME.search(str(name))) or (
            inferred == "categorical"
            and len(nonnull) > 0
            and nonnull.astype(str).str.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$").all()
        )
        role = "IDENTIFIER" if identifier else "MODELLED"
        if text or unsupported or not len(nonnull):
            role = "EXCLUDED"
        if text:
            warnings.append("Possible free text: excluded; free-text synthesis is outside Phase 3")
        if identifier:
            warnings.append("Possible direct identifier: verify this advisory classification")
        if unique <= 1:
            warnings.append("All-null column" if not len(nonnull) else "Constant column")
        if ratio > 0.8:
            warnings.append("High cardinality: review type and role")
        if unsupported:
            warnings.append("Unsupported column type or non-finite source numbers")
        columns.append(
            {
                "name": str(name),
                "inferred_type": "unsupported" if unsupported else inferred,
                "suggested_role": role,
                "null_percentage": round(float(series.isna().mean()) * 100, 6),
                "unique_count": unique,
                "cardinality_ratio": round(ratio, 6),
                "possible_identifier": bool(identifier),
                "possible_free_text": bool(text),
                "constant": unique == 1,
                "all_null": not len(nonnull),
                "high_cardinality": ratio > 0.8,
                "warnings": warnings,
            }
        )
    return {
        "profile_version": "1",
        "row_count": len(frame),
        "column_count": len(frame.columns),
        "columns": columns,
        "compatible": len(frame) >= 10 and any(c["suggested_role"] == "MODELLED" for c in columns),
        "warnings": ["Automatic role/type inference is advisory and can be wrong"]
        + (["At least 10 source rows are required operationally"] if len(frame) < 10 else []),
    }


def resolve_metadata(
    frame: pd.DataFrame, overrides: dict[str, ColumnOverride], rules: dict[str, ValidationRule]
) -> list[ColumnMetadata]:
    if set(overrides) - set(frame.columns) or set(rules) - set(frame.columns):
        raise AppError("Metadata/rules reference unknown columns", "TABULAR_METADATA_INVALID")
    resolved = []
    for column in profile(frame)["columns"]:
        name = column["name"]
        data = dict(
            name=name,
            role=column["suggested_role"],
            semantic_type=column["inferred_type"]
            if column["inferred_type"] != "unsupported"
            else "categorical",
            nullable=column["null_percentage"] > 0,
            inferred_type=column["inferred_type"],
            sdv_type=column["inferred_type"]
            if column["inferred_type"] != "unsupported"
            else "categorical",
            warnings=column["warnings"],
        )
        if name in overrides:
            data.update(overrides[name].model_dump(exclude_none=True))
        data["sdv_type"] = data["semantic_type"]
        if data["role"] == "IDENTIFIER":
            override = overrides.get(name)
            if override and (
                override.unique is False
                or override.nullable is True
                or (override.semantic_type is not None and override.semantic_type != "categorical")
            ):
                raise AppError(
                    "Synthetic identifiers must be unique, non-null categorical columns",
                    "TABULAR_METADATA_INVALID",
                )
            data.update(
                identifier_strategy=data.get("identifier_strategy") or "synthetic_sequence",
                unique=True,
                nullable=False,
                semantic_type="categorical",
                sdv_type="categorical",
            )
        elif data.get("identifier_strategy") is not None:
            raise AppError(
                "Identifier strategy requires IDENTIFIER role", "TABULAR_METADATA_INVALID"
            )
        if data["role"] == "MODELLED" and (
            column["possible_free_text"]
            or column["all_null"]
            or column["inferred_type"] == "unsupported"
        ):
            raise AppError(
                "Free-text, all-null and unsupported columns must be excluded",
                "TABULAR_UNSUPPORTED_COLUMN",
            )
        if data.get("datetime_format") and data["semantic_type"] != "datetime":
            raise AppError("datetime_format requires a datetime column", "TABULAR_METADATA_INVALID")
        if data["role"] == "EXCLUDED" and name in rules:
            raise AppError(
                "Validation rules cannot target excluded columns", "TABULAR_METADATA_INVALID"
            )
        if name in rules:
            rule = rules[name]
            if (rule.numeric_min is not None or rule.numeric_max is not None) and data[
                "semantic_type"
            ] != "numerical":
                raise AppError(
                    "Numeric rules require numerical columns", "TABULAR_METADATA_INVALID"
                )
        try:
            resolved.append(ColumnMetadata.model_validate(data))
        except ValidationError as error:
            raise AppError(
                "Column metadata is contradictory", "TABULAR_METADATA_INVALID"
            ) from error
    if not any(c.role == "MODELLED" for c in resolved):
        raise AppError("At least one modelled column is required", "TABULAR_NO_MODELLED_COLUMNS")
    return resolved


def model_input(frame: pd.DataFrame, metadata: list[ColumnMetadata]) -> pd.DataFrame:
    result = frame[[c.name for c in metadata if c.role == "MODELLED"]].copy()
    try:
        for column in metadata:
            if column.role != "MODELLED":
                continue
            series = result[column.name]
            if not column.nullable and series.isna().any():
                raise ValueError("Non-null constraint")
            if column.semantic_type == "numerical":
                result[column.name] = pd.to_numeric(series, errors="raise")
                if not np.isfinite(result[column.name].dropna().to_numpy(dtype=float)).all():
                    raise ValueError("Nonfinite")
            elif column.semantic_type == "datetime":
                result[column.name] = pd.to_datetime(
                    series, errors="raise", format=column.datetime_format or "ISO8601"
                )
            elif column.semantic_type == "boolean":
                converted = (
                    series.astype(str)
                    .str.lower()
                    .map({"true": True, "false": False, "1": True, "0": False})
                )
                if converted[series.notna()].isna().any():
                    raise ValueError("Invalid boolean")
                result[column.name] = converted
            else:
                result[column.name] = series.map(lambda v: str(v) if pd.notna(v) else np.nan)
    except (ValueError, TypeError) as error:
        raise AppError(
            "Source values do not satisfy configured structural types/nullability",
            "TABULAR_METADATA_INVALID",
        ) from error
    return result
