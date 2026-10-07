from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import Field, model_validator

from .platform import Name, Schema

ColumnName = Annotated[str, Field(min_length=1, max_length=128)]
MetricName = Literal[
    "structural_validation",
    "training_column_shapes",
    "training_column_pair_trends",
    "holdout_column_shapes",
    "holdout_column_pair_trends",
    "exact_training_match_fraction",
    "dcr_baseline_protection",
    "dcr_overfitting_protection",
    "dcr_overfitting_gating_eligible",
    "disclosure_protection",
    "tstr_trtr_ratio",
    "group_leakage_free",
]


class DisclosureConfig(Schema):
    known_columns: list[ColumnName] = Field(min_length=1, max_length=20)
    sensitive_columns: list[ColumnName] = Field(min_length=1, max_length=10)
    continuous_columns: list[ColumnName] = Field(default_factory=list, max_length=30)
    num_discrete_bins: int = Field(default=10, strict=True, ge=2, le=50)
    computation_method: Literal["cap", "zero_cap", "generalized_cap"] = "cap"
    estimated: bool = False

    @model_validator(mode="after")
    def disjoint(self):
        known, sensitive = set(self.known_columns), set(self.sensitive_columns)
        if len(known) != len(self.known_columns) or len(sensitive) != len(self.sensitive_columns):
            raise ValueError("Disclosure columns must be unique")
        if known & sensitive or not set(self.continuous_columns) <= known | sensitive:
            raise ValueError("Known/sensitive must be disjoint; continuous must be selected")
        return self


class UtilityConfig(Schema):
    target: ColumnName
    task: Literal["BINARY_CLASSIFICATION", "MULTICLASS_CLASSIFICATION", "REGRESSION"]
    datetime_features: bool = False


class EvaluationCreate(Schema):
    profile: Literal["BASIC", "STANDARD", "FULL"] = "BASIC"
    privacy: DisclosureConfig | None = None
    utility: UtilityConfig | None = None
    group_key: ColumnName | None = None
    independent_rows: bool = False
    random_seed: int = Field(default=42, strict=True, ge=0, le=4294967295)
    minimum_holdout_rows: int = Field(default=20, strict=True, ge=2, le=1000)
    dcr_max_train_validation_ratio: float = Field(default=1.25, ge=1, le=2, allow_inf_nan=False)
    release_policy_id: UUID | None = None

    @model_validator(mode="after")
    def profile_configuration(self):
        if self.profile != "FULL" and (self.privacy or self.utility):
            raise ValueError("Disclosure and utility configuration require FULL profile")
        if self.group_key and self.independent_rows:
            raise ValueError("Declare either group_key or independent rows")
        return self


class PolicyRule(Schema):
    required: bool = True
    minimum: float | None = Field(default=None, allow_inf_nan=False)
    maximum: float | None = Field(default=None, allow_inf_nan=False)
    equals: bool | None = None
    when: Literal["ALWAYS", "DISCLOSURE_CONFIGURED", "UTILITY_CONFIGURED"] = "ALWAYS"

    @model_validator(mode="after")
    def threshold(self):
        if self.equals is not None and (self.minimum is not None or self.maximum is not None):
            raise ValueError("Boolean and numeric thresholds cannot be combined")
        if self.equals is None and self.minimum is None and self.maximum is None:
            raise ValueError("An explicit threshold is required")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("Minimum exceeds maximum")
        return self


class PolicyCreate(Schema):
    name: Name
    version: int = Field(strict=True, ge=1, le=100000)
    description: str = Field(default="", max_length=2000)
    rules: dict[MetricName, PolicyRule] = Field(min_length=1, max_length=20)
    illustrative: bool = False

    @model_validator(mode="after")
    def typed_thresholds(self):
        booleans = {
            "structural_validation",
            "dcr_overfitting_gating_eligible",
            "group_leakage_free",
        }
        for name, rule in self.rules.items():
            if (name in booleans) != (rule.equals is not None):
                raise ValueError("Threshold type must match metric")
        return self


class PolicyRead(PolicyCreate):
    id: UUID
    project_id: UUID
    policy_hash: str
    created_at: datetime


class EvaluationRead(Schema):
    id: UUID
    project_id: UUID
    dataset_id: UUID
    generation_job_id: UUID
    execution_job_id: UUID
    synthetic_artifact_id: UUID
    status: str
    profile: str
    policy_id: UUID | None
    policy_version: int | None
    policy_hash: str | None
    configuration_json: dict[str, Any]
    result_summary_json: dict[str, Any]
    created_at: datetime
    queued_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    error_code: str | None
    error_message: str | None
    attempt_count: int
    worker_id: str | None


class ComparisonRequest(Schema):
    evaluation_ids: list[UUID] = Field(min_length=2, max_length=10)
