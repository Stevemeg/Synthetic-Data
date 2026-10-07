from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from ..config import Settings
from ..core.errors import AppError


@dataclass(frozen=True)
class GenerationRequest:
    modality: str
    count: int
    seed: int = 42
    imaging_modality: str | None = None
    source_path: Path | None = None
    run_id: str = field(default_factory=lambda: uuid4().hex)

    @classmethod
    def parse(cls, modality: str, config: Any, settings: Settings) -> "GenerationRequest":
        if modality not in {"tabular", "timeseries", "imaging", "genomic"}:
            raise AppError("Unknown generation modality", "unsupported_modality", 404)
        if not isinstance(config, dict):
            raise AppError("config must be a JSON object")
        allowed = {"type", "count", "seed"} | ({"modality"} if modality == "imaging" else set())
        if set(config) - allowed:
            raise AppError("config contains unsupported fields")
        if config.get("type", modality) != modality:
            raise AppError("config type does not match endpoint")
        count = config.get("count")
        maximum = settings.max_images if modality == "imaging" else settings.max_samples
        if type(count) is not int or not 1 <= count <= maximum:
            raise AppError(f"count must be an integer between 1 and {maximum}")
        seed = config.get("seed", 42)
        if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
            raise AppError("seed must be an integer between 0 and 4294967295")
        image_kind = config.get("modality")
        if modality == "imaging" and image_kind not in {"MRI", "X-Ray", "Skin"}:
            raise AppError("Imaging modality must be MRI, X-Ray, or Skin")
        return cls(modality, count, seed, image_kind)


@dataclass(frozen=True)
class GenerationArtifact:
    location: str
    media_type: str
    role: str = "dataset"


@dataclass(frozen=True)
class GenerationMetadata:
    run_id: str
    modality: str
    engine: str
    requested_sample_count: int
    produced_sample_count: int
    seed: int
    duration_seconds: float
    source_schema_summary: dict[str, Any]
    warnings: list[str]
    maturity: str


@dataclass(frozen=True)
class GenerationResult:
    metadata: GenerationMetadata
    artifacts: list[GenerationArtifact]

    def to_dict(self) -> dict:
        return asdict(self)
