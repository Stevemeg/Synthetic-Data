from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from ...schemas.generation import GenerationArtifact, GenerationRequest


@dataclass
class EngineOutput:
    produced_count: int
    schema: dict[str, Any]
    artifacts: list[GenerationArtifact]
    warnings: list[str]


class GenerationEngine(Protocol):
    name: str
    maturity: str

    def generate(self, request: GenerationRequest, output_dir: Path) -> EngineOutput: ...
