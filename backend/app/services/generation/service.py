import json
import re
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from time import perf_counter

from ...config import Settings
from ...core.errors import AppError, UnavailableError
from ...core.logging import log_event
from ...schemas.generation import (
    GenerationArtifact,
    GenerationMetadata,
    GenerationRequest,
    GenerationResult,
)
from .base import GenerationEngine

PRIVACY_WARNING = (
    "Privacy, disclosure risk, clinical validity, and downstream utility have not been measured."
)


class GenerationService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._lock = Lock()

    def ensure_available(self, modality: str):
        if modality == "tabular":
            raise UnavailableError(
                "Use the registered-dataset tabular job workflow. This legacy direct generation contract has no tabular configuration; source-row resampling is absent."
            )
        if modality == "genomic":
            raise UnavailableError(
                "Genomics is Experimental / Not available in production workflow. No validated synthesis engine is implemented."
            )
        if modality == "imaging" and (
            not self.settings.enable_imaging_lab or self.settings.app_env == "production"
        ):
            raise UnavailableError(
                "Imaging is an experimental lab. Enable ENABLE_IMAGING_LAB in a non-production environment to run it."
            )

    def generate(self, request: GenerationRequest) -> GenerationResult:
        GenerationRequest.parse(
            request.modality,
            {
                "count": request.count,
                "seed": request.seed,
                **({"modality": request.imaging_modality} if request.modality == "imaging" else {}),
            },
            self.settings,
        )
        if not re.fullmatch(r"[a-f0-9]{32}", request.run_id):
            raise AppError("Invalid run ID")
        self.ensure_available(request.modality)
        if not self._lock.acquire(blocking=False):
            raise AppError(
                "A generation run is already active; retry after it finishes",
                "generation_busy",
                409,
            )
        start = perf_counter()
        checkpoint = self.settings.model_dir / "trained" / request.run_id / "vae.pt"
        if (self.settings.generated_dir / request.run_id).exists() or checkpoint.parent.exists():
            self._lock.release()
            raise AppError("Run ID already exists; choose a new run", "run_exists", 409)
        try:
            engine: GenerationEngine
            if request.modality == "timeseries":
                from .ecg import ECGEngine

                engine = ECGEngine(self.settings, checkpoint)
            else:
                from .imaging import ImagingEngine

                engine = ImagingEngine(self.settings)
            log_event(
                "run_start",
                run_id=request.run_id,
                modality=request.modality,
                engine=engine.name,
                sample_count=request.count,
            )
            root = self.settings.generated_dir
            root.mkdir(parents=True, exist_ok=True)
            with TemporaryDirectory(prefix=".run_", dir=root) as temporary:
                working = Path(temporary) / "artifacts"
                working.mkdir()
                output = engine.generate(request, working)
                if output.produced_count != request.count:
                    raise RuntimeError("Generation engine violated sample count contract")
                if not output.artifacts or not any(a.role == "dataset" for a in output.artifacts):
                    raise RuntimeError("Generation engine returned no dataset artifact")
                for artifact in output.artifacts:
                    target = working / artifact.location
                    if (
                        target.parent != working
                        or not target.is_file()
                        or target.stat().st_size == 0
                    ):
                        raise RuntimeError("Generation engine returned an invalid artifact")
                metadata = GenerationMetadata(
                    request.run_id,
                    request.modality,
                    engine.name,
                    request.count,
                    output.produced_count,
                    request.seed,
                    round(perf_counter() - start, 4),
                    output.schema,
                    [PRIVACY_WARNING, *output.warnings],
                    engine.maturity,
                )
                result = GenerationResult(
                    metadata,
                    [
                        *output.artifacts,
                        GenerationArtifact("metadata.json", "application/json", "metadata"),
                    ],
                )
                (working / "metadata.json").write_text(
                    json.dumps(result.to_dict(), indent=2), encoding="utf-8"
                )
                working.rename(root / request.run_id)
            log_event(
                "run_complete",
                run_id=request.run_id,
                modality=request.modality,
                sample_count=output.produced_count,
                duration=metadata.duration_seconds,
            )
            return result
        except Exception as error:
            log_event(
                "run_failed",
                run_id=request.run_id,
                modality=request.modality,
                exception_type=type(error).__name__,
            )
            if checkpoint.parent.exists():
                shutil.rmtree(checkpoint.parent)
            raise
        finally:
            self._lock.release()
