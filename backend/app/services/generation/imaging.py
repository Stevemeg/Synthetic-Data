import hashlib
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from ...config import Settings
from ...core.errors import AppError, UnavailableError
from ...schemas.generation import GenerationArtifact, GenerationRequest
from .base import EngineOutput

MODEL_FILES = {
    "MRI": "generator_brain.pth",
    "X-Ray": "generator_chest.pth",
    "Skin": "generator_skin.pth",
}


def export_images(images, destination: Path):
    """Export every [0,1] RGB image separately; no grid masquerading as a dataset."""
    import numpy as np
    from PIL import Image

    if (
        images.ndim != 4
        or images.shape[1:] != (3, 64, 64)
        or len(images) == 0
        or not np.isfinite(images).all()
    ):
        raise ValueError("Invalid generated image dimensions or values")
    with ZipFile(destination, "w", compression=ZIP_DEFLATED) as archive:
        for index, array in enumerate(images):
            pixels = (np.clip(array.transpose(1, 2, 0), 0, 1) * 255).round().astype(np.uint8)
            buffer = BytesIO()
            Image.fromarray(pixels).save(buffer, format="PNG")
            archive.writestr(f"image_{index + 1:05d}.png", buffer.getvalue())


class ImagingEngine:
    name = "dcgan-64-rgb"
    maturity = "Experimental"

    def __init__(self, settings: Settings):
        self.settings = settings

    def generate(self, request: GenerationRequest, output_dir: Path) -> EngineOutput:
        if request.imaging_modality not in MODEL_FILES:
            raise AppError("Unsupported imaging modality")
        if request.source_path is not None:
            raise AppError("Source conditioning is unsupported")
        model_path = self.settings.model_dir / MODEL_FILES[request.imaging_modality]
        if not model_path.is_file():
            raise UnavailableError("Requested imaging checkpoint is missing from MODEL_DIR")
        try:
            import torch

            from .imaging_model import Generator
        except ImportError as exc:
            raise UnavailableError(
                "Imaging model dependencies are missing. Install backend/requirements-ml.txt."
            ) from exc
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(request.seed)
            model = Generator()
            checkpoint_bytes = model_path.read_bytes()
            try:
                model.load_state_dict(
                    torch.load(BytesIO(checkpoint_bytes), map_location="cpu", weights_only=True)
                )
            except (RuntimeError, ValueError, KeyError) as exc:
                raise UnavailableError(
                    "Imaging checkpoint is incompatible with the documented DCGAN architecture"
                ) from exc
            model.eval()
            with torch.no_grad():
                images = ((model(torch.randn(request.count, 100, 1, 1)) + 1) / 2).numpy()
        export_images(images, output_dir / "dataset.zip")
        return EngineOutput(
            len(images),
            {
                "source": "pretrained checkpoint; no uploaded image",
                "checkpoint_sha256": hashlib.sha256(checkpoint_bytes).hexdigest(),
                "imaging_modality": request.imaging_modality,
                "image_shape": [64, 64, 3],
            },
            [GenerationArtifact("dataset.zip", "application/zip")],
            [
                "Experimental 64x64 RGB PNG samples; no diagnostic, DICOM, or clinical fidelity claims.",
                "Checkpoint training provenance and licensing have not been verified.",
            ],
        )
