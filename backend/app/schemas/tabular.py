"""Application metadata and bounded tabular configuration; independent of SDV."""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Role = Literal["MODELLED", "IDENTIFIER", "EXCLUDED"]
SemanticType = Literal["numerical", "categorical", "boolean", "datetime"]
EngineName = Literal["gaussian_copula", "ctgan", "tvae"]
Annotation = Literal["QUASI_IDENTIFIER", "SENSITIVE_ATTRIBUTE"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class ColumnOverride(StrictModel):
    role: Role | None = None
    semantic_type: SemanticType | None = None
    nullable: bool | None = None
    unique: bool | None = None
    annotations: list[Annotation] | None = Field(default=None, max_length=2)
    datetime_format: str | None = Field(default=None, max_length=80)
    identifier_strategy: Literal["synthetic_sequence"] | None = None


class ColumnMetadata(StrictModel):
    name: str
    role: Role
    semantic_type: SemanticType
    nullable: bool
    unique: bool = False
    inferred_type: str
    sdv_type: SemanticType
    annotations: list[Annotation] = Field(default_factory=list)
    datetime_format: str | None = None
    identifier_strategy: Literal["synthetic_sequence"] | None = None
    warnings: list[str] = Field(default_factory=list)


class ValidationRule(StrictModel):
    non_null: bool = False
    numeric_min: float | None = None
    numeric_max: float | None = None
    allowed_values: list[str | int | float | bool] | None = Field(default=None, max_length=100)
    regex: str | None = Field(default=None, max_length=128)
    unique: bool = False

    @model_validator(mode="after")
    def consistent(self):
        if self.numeric_min is not None and self.numeric_max is not None:
            if self.numeric_min > self.numeric_max:
                raise ValueError("Invalid range")
        # Deliberately limited to linear, fixed character-class patterns. No user ReDoS.
        if self.regex is not None:
            if not re.fullmatch(
                r"\^?(?:[A-Za-z0-9 _.-]|\[[A-Za-z0-9-]+\](?:\{[0-9]{1,3}(?:,[0-9]{1,3})?\})?)+\$?",
                self.regex,
            ):
                raise ValueError("Only literals and bounded character classes are supported")
            re.compile(self.regex)
        if self.allowed_values is not None and not self.allowed_values:
            raise ValueError("allowed_values cannot be empty")
        return self


class TabularConfig(StrictModel):
    holdout_fraction: float = Field(default=0.2, ge=0, le=0.5)
    split_seed: int = Field(default=42, ge=0, le=4294967295)
    epochs: int = Field(default=10, ge=1, le=100)
    batch_size: int = Field(default=100, ge=10, le=500)
    embedding_dim: int = Field(default=64, ge=16, le=256)
    generator_dim: list[int] = Field(default_factory=lambda: [128, 128], min_length=1, max_length=3)
    discriminator_dim: list[int] = Field(
        default_factory=lambda: [128, 128], min_length=1, max_length=3
    )
    cuda: bool = False
    default_distribution: Literal["beta", "norm", "truncnorm", "gaussian_kde"] = "beta"

    @model_validator(mode="after")
    def dimensions(self):
        if self.batch_size % 10:
            raise ValueError("batch_size must be divisible by 10")
        if any(
            type(n) is not int or not 16 <= n <= 256
            for n in self.generator_dim + self.discriminator_dim
        ):
            raise ValueError("Network dimensions must be integers between 16 and 256")
        return self
