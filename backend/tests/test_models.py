"""Real, tiny CPU integration checks; optional via pytest -m model."""

import json
from dataclasses import replace
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pytest

from backend.app.config import ROOT
from backend.app.schemas.generation import GenerationRequest
from backend.app.services.generation.service import GenerationService

pytestmark = pytest.mark.model


@pytest.fixture(autouse=True)
def cpu_threads():
    torch = pytest.importorskip("torch")
    original = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(original)


@pytest.mark.parametrize("sequence_length", [95, 96, 97, 101])
def test_nondivisible_decoder_and_one_sample(sequence_length):
    import torch

    from backend.app.services.generation.ecg_model import VAE

    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(42)
        model = VAE(sequence_length)
        reconstruction, _, _ = model(torch.zeros(1, 1, sequence_length))
        assert reconstruction.shape == (1, 1, sequence_length)
        assert model.decode(torch.zeros(3, 16)).shape == (3, 1, sequence_length)
        assert torch.isfinite(reconstruction).all()
        assert reconstruction.min() >= 0 and reconstruction.max() <= 1


@pytest.mark.parametrize("count", [1, 3])
def test_real_ecg_api_count_artifacts_checkpoint_and_reproducibility(settings, count):
    import neurokit2 as nk
    import torch

    signal = nk.ecg_simulate(duration=8, sampling_rate=125, heart_rate=70, random_state=42)
    source = (",".join(map(str, signal)) + ",source-label-not-a-generated-diagnosis\n").encode()
    source_path = settings.upload_dir / "simulated.csv"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_bytes(source)
    outputs = []
    for _ in range(2):
        request = GenerationRequest("timeseries", count, seed=17, source_path=source_path)
        result = GenerationService(settings).generate(request)
        metadata = result.to_dict()["metadata"]
        assert metadata["requested_sample_count"] == metadata["produced_sample_count"] == count
        assert metadata["duration_seconds"] >= 0 and metadata["warnings"]
        run_id = metadata["run_id"]
        with np.load(
            settings.generated_dir / run_id / "dataset.npz", allow_pickle=False
        ) as archive:
            assert "labels" not in archive.files
            generated = archive["synthetic_sequences"]
            assert generated.shape == (count, 96)
            assert np.isfinite(generated).all()
            assert generated.min() >= 0 and generated.max() <= 1
            outputs.append(generated)
        checkpoint = torch.load(
            settings.model_dir / "trained" / run_id / "vae.pt", weights_only=True
        )
        assert checkpoint["seq_len"] == 96 and checkpoint["latent_dim"] == 16
        from backend.app.services.generation.ecg_model import VAE

        restored = VAE(checkpoint["seq_len"], checkpoint["latent_dim"])
        restored.load_state_dict(checkpoint["model_state"])
        assert restored.decode(torch.zeros(count, checkpoint["latent_dim"])).shape == (count, 1, 96)
        sidecar = json.loads((settings.generated_dir / run_id / "metadata.json").read_text())
        assert sidecar["metadata"] == metadata
        assert not any(p.name.startswith(".run_") for p in settings.generated_dir.iterdir())
    np.testing.assert_array_equal(*outputs)


@pytest.mark.parametrize("modality", ["MRI", "X-Ray", "Skin"])
def test_preserved_dcgan_checkpoint_exports_every_image(settings, modality):
    settings = replace(settings, enable_imaging_lab=True, model_dir=ROOT / "backend")
    request = GenerationRequest("imaging", 2, seed=42, imaging_modality=modality)
    result = GenerationService(settings).generate(request)
    assert result.metadata.produced_sample_count == 2
    assert result.metadata.source_schema_summary["image_shape"] == [64, 64, 3]
    with ZipFile(settings.generated_dir / request.run_id / "dataset.zip") as archive:
        assert archive.namelist() == ["image_00001.png", "image_00002.png"]
    assert Path(settings.generated_dir / request.run_id / "metadata.json").is_file()


def test_real_ecg_cli_execution(settings, tmp_path, monkeypatch):
    import neurokit2 as nk

    from backend.scripts.run_pipeline import main

    signal = nk.ecg_simulate(duration=8, sampling_rate=125, random_state=42)
    source = tmp_path / "simulated.csv"
    source.write_text(",".join(map(str, signal)) + ",source-label\n", encoding="utf-8")
    output = tmp_path / "cli.npz"
    model = tmp_path / "cli.pt"
    monkeypatch.setenv("GENERATED_DATA_DIR", str(settings.generated_dir))
    monkeypatch.setenv("MODEL_DIR", str(settings.model_dir))
    monkeypatch.setenv("ECG_SAMPLING_RATE", "125")
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_pipeline",
            "--input_file",
            str(source),
            "--output_file",
            str(output),
            "--model_output_file",
            str(model),
            "--count",
            "2",
            "--seed",
            "42",
            "--epochs",
            "1",
        ],
    )
    main()
    with np.load(output, allow_pickle=False) as archive:
        assert archive["synthetic_sequences"].shape == (2, 96)
        assert "labels" not in archive.files
    assert model.is_file() and output.with_suffix(".metadata.json").is_file()
