import logging
from pathlib import Path

import numpy as np

from ...config import Settings
from ...core.errors import UnavailableError
from ...schemas.generation import GenerationArtifact, GenerationRequest
from ...utils.ecg_input import SEQUENCE_LENGTH, extract_segments, read_ecg_csv
from .base import EngineOutput

logger = logging.getLogger(__name__)


def train_and_sample(
    segments: np.ndarray,
    count: int,
    seed: int,
    epochs: int,
    checkpoint_path: Path,
    sampling_rate: int = 125,
) -> np.ndarray:
    try:
        import torch
        from torch.utils.data import DataLoader, TensorDataset

        from .ecg_model import VAE, loss_function
    except ImportError as exc:
        raise UnavailableError(
            "ECG model dependencies are missing. Install backend/requirements-ml.txt."
        ) from exc
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed)
        model = VAE(seq_len=segments.shape[1])
        tensor = torch.from_numpy(segments).unsqueeze(1)
        loader = DataLoader(
            TensorDataset(tensor),
            batch_size=min(128, len(tensor)),
            shuffle=True,
            generator=torch.Generator().manual_seed(seed),
        )
        optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
        model.train()
        for _ in range(epochs):
            for (data,) in loader:
                optimizer.zero_grad()
                reconstruction, mean, logvar = model(data)
                loss = loss_function(reconstruction, data, mean, logvar)
                if not torch.isfinite(loss):
                    raise RuntimeError("Nonfinite ECG training loss")
                loss.backward()
                optimizer.step()
        model.eval()
        with torch.no_grad():
            generated = model.decode(torch.randn(count, model.latent_dim)).squeeze(1).numpy()
        if generated.shape != (count, segments.shape[1]) or not np.isfinite(generated).all():
            raise RuntimeError("Invalid ECG decoder output")
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "format_version": 1,
                "engine": "pytorch-ecg-vae",
                "seq_len": model.seq_len,
                "latent_dim": model.latent_dim,
                "model_state": model.state_dict(),
                "normalization": "per_segment_minmax_0_1",
                "seed": seed,
                "epochs": epochs,
                "sampling_rate_hz": sampling_rate,
                "torch_version": str(torch.__version__),
            },
            checkpoint_path,
        )
    return generated


class ECGEngine:
    name = "pytorch-ecg-vae"
    maturity = "Beta"

    def __init__(self, settings: Settings, checkpoint_path: Path):
        self.settings = settings
        self.checkpoint_path = checkpoint_path

    def generate(self, request: GenerationRequest, output_dir: Path) -> EngineOutput:
        if request.source_path is None:
            from ...core.errors import AppError

            raise AppError("An ECG source CSV is required")
        signals = read_ecg_csv(request.source_path, self.settings)
        segments, skipped = extract_segments(signals, self.settings)
        generated = train_and_sample(
            segments,
            request.count,
            request.seed,
            self.settings.ecg_epochs,
            self.checkpoint_path,
            self.settings.ecg_sampling_rate,
        )
        np.savez_compressed(
            output_dir / "dataset.npz",
            synthetic_sequences=generated,
            sampling_rate=np.int64(self.settings.ecg_sampling_rate),
            normalization=np.array("per_segment_minmax_0_1"),
        )
        return EngineOutput(
            len(generated),
            {
                "source_rows": len(signals),
                "signal_samples_per_row": signals.shape[1],
                "sequence_length": SEQUENCE_LENGTH,
                "extracted_segments": len(segments),
                "skipped_rows": skipped,
                "sampling_rate_hz": self.settings.ecg_sampling_rate,
                "epochs": self.settings.ecg_epochs,
                "normalization": "per_segment_minmax_0_1",
                "labels": "not generated",
            },
            [GenerationArtifact("dataset.npz", "application/octet-stream")],
            [
                "Unconditional generated sequences have no diagnostic labels. Source labels are ignored.",
                "Outputs are normalized heartbeat windows, not calibrated voltages or full ECG recordings.",
                "A full VAE checkpoint was saved locally under MODEL_DIR/trained; it is not published for download.",
            ],
        )
