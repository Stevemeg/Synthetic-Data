from datetime import datetime
from typing import Annotated, Any, Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from .tabular import ColumnOverride, EngineName, TabularConfig, ValidationRule

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Modality = Literal["timeseries", "imaging", "tabular", "genomic"]


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class ProjectCreate(Schema):
    name: Name
    description: str = Field(default="", max_length=2000)


class ProjectPatch(Schema):
    name: Name | None = None
    description: str | None = Field(default=None, max_length=2000)
    status: Literal["ACTIVE", "ARCHIVED"] | None = None

    @model_validator(mode="after")
    def require_fields(self):
        if not self.model_fields_set or any(
            getattr(self, key) is None for key in self.model_fields_set
        ):
            raise ValueError("Patch must contain non-null fields")
        return self


class ProjectRead(ProjectCreate):
    id: UUID
    status: str
    created_at: datetime
    updated_at: datetime


class DatasetRead(Schema):
    id: UUID
    project_id: UUID
    name: str
    modality: str
    original_filename: str
    content_type: str
    size_bytes: int
    sha256: str
    status: str
    row_count: int
    column_count: int
    metadata_json: dict[str, Any]
    created_at: datetime


class JobCreate(Schema):
    modality: Modality
    dataset_id: UUID | None = None
    requested_samples: int = Field(strict=True, ge=1, le=10000)
    random_seed: int = Field(default=42, strict=True, ge=0, le=4294967295)
    imaging_modality: Literal["MRI", "X-Ray", "Skin"] | None = None
    engine: EngineName | None = None
    configuration: TabularConfig = Field(default_factory=TabularConfig)
    metadata_overrides: dict[str, ColumnOverride] = Field(default_factory=dict)
    validation_rules: dict[str, ValidationRule] = Field(default_factory=dict)

    @model_validator(mode="after")
    def tabular_only(self):
        if self.modality != "tabular" and (
            self.engine is not None
            or self.metadata_overrides
            or self.validation_rules
            or self.configuration.model_dump() != TabularConfig().model_dump()
        ):
            raise ValueError("Tabular options require tabular modality")
        return self


class JobRead(Schema):
    id: UUID
    project_id: UUID
    dataset_id: UUID | None
    modality: str
    engine: str
    status: Literal["PENDING", "QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"]
    requested_samples: int
    produced_samples: int
    random_seed: int
    configuration_json: dict[str, Any]
    created_at: datetime
    queued_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    heartbeat_at: datetime | None
    lease_expires_at: datetime | None
    error_code: str | None
    error_message: str | None
    attempt_count: int
    max_attempts: int
    worker_id: str | None
    metadata_json: dict[str, Any]


class ArtifactRead(Schema):
    id: UUID
    job_id: UUID
    artifact_type: str
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    metadata_json: dict[str, Any]
    created_at: datetime
    downloadable: bool = False


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class HealthRead(BaseModel):
    status: Literal["ok"] = "ok"
    product: str = "MedSynth Guard"


class ReadyRead(BaseModel):
    ready: bool


class CapabilityRead(BaseModel):
    maturity: Literal["Stable", "Beta", "Experimental"]
    available: bool
    reason: str
    engines: list[dict[str, str]] = Field(default_factory=list)


class CapabilitiesRead(BaseModel):
    capabilities: dict[Modality, CapabilityRead]
    limits: dict[str, int]
    evaluation: dict[str, Any] = Field(default_factory=dict)
