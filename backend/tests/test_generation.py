from dataclasses import replace
from io import BytesIO
from zipfile import ZipFile

import numpy as np
import pytest
from PIL import Image

from backend.app.core.errors import AppError, UnavailableError
from backend.app.schemas.generation import GenerationRequest
from backend.app.services.generation.base import EngineOutput
from backend.app.services.generation.ecg import ECGEngine
from backend.app.services.generation.imaging import export_images
from backend.app.services.generation.service import GenerationService
from backend.generate_genomic import generate_genomic_data
from backend.generate_tabular import generate_tabular_data


@pytest.mark.parametrize("function", [generate_tabular_data, generate_genomic_data])
def test_disabled_legacy_script_does_not_read_or_write(tmp_path, function):
    output = tmp_path / "out.csv"
    with pytest.raises(UnavailableError):
        function(tmp_path / "nonexistent.csv", output, 5)
    assert not output.exists()


def test_every_image_is_exported(tmp_path):
    output = tmp_path / "images.zip"
    export_images(np.zeros((3, 3, 64, 64), dtype=np.float32), output)
    with ZipFile(output) as archive:
        assert len(archive.namelist()) == 3
        assert "synthetic_image_grid.png" not in archive.namelist()
        for name in archive.namelist():
            with Image.open(BytesIO(archive.read(name))) as image:
                assert image.size == (64, 64) and image.mode == "RGB"


@pytest.mark.parametrize(
    "images", [np.empty((0, 3, 64, 64)), np.empty((1, 1, 64, 64)), np.full((1, 3, 64, 64), np.nan)]
)
def test_invalid_image_output(tmp_path, images):
    with pytest.raises(ValueError):
        export_images(images, tmp_path / "invalid.zip")


def test_count_contract_failure_cleans_partial_artifacts(settings, monkeypatch):
    def bad_output(self, request, directory):
        (directory / "partial.txt").write_text("partial")
        self.checkpoint_path.parent.mkdir(parents=True)
        self.checkpoint_path.write_bytes(b"partial")
        return EngineOutput(0, {}, [], [])

    monkeypatch.setattr(ECGEngine, "generate", bad_output)
    request = GenerationRequest("timeseries", 2)
    with pytest.raises(RuntimeError, match="sample count"):
        GenerationService(settings).generate(request)
    assert not list(settings.generated_dir.iterdir())
    assert not (settings.model_dir / "trained" / request.run_id).exists()


def test_request_count_and_run_id_are_bounded(settings):
    for request in (
        GenerationRequest("timeseries", 0),
        GenerationRequest("timeseries", 1, run_id="../outside"),
    ):
        with pytest.raises(AppError):
            GenerationService(settings).generate(request)


def test_busy_run_is_explicit(settings):
    service = GenerationService(settings)
    service._lock.acquire()
    try:
        with pytest.raises(AppError, match="already active"):
            service.generate(GenerationRequest("timeseries", 1))
    finally:
        service._lock.release()


def test_supervised_utility_evaluation_cannot_claim_accuracy(tmp_path):
    from backend.scripts.evaluate_ml import run_final_evaluation

    with pytest.raises(UnavailableError, match="justified diagnostic labels"):
        run_final_evaluation(tmp_path / "synth.npz", tmp_path / "test.csv")


def test_production_lab_cannot_be_reenabled_by_direct_settings(settings):
    service = GenerationService(replace(settings, app_env="production", enable_imaging_lab=True))
    with pytest.raises(UnavailableError):
        service.generate(GenerationRequest("imaging", 1, imaging_modality="MRI"))


def test_success_without_a_dataset_cannot_be_published(settings, monkeypatch):
    monkeypatch.setattr(ECGEngine, "generate", lambda *args: EngineOutput(1, {}, [], []))
    with pytest.raises(RuntimeError, match="no dataset artifact"):
        GenerationService(settings).generate(GenerationRequest("timeseries", 1))
    assert not list(settings.generated_dir.iterdir())


def test_reused_run_id_preserves_existing_model(settings):
    request = GenerationRequest("timeseries", 1)
    checkpoint = settings.model_dir / "trained" / request.run_id / "vae.pt"
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_bytes(b"existing-model")
    service = GenerationService(settings)
    with pytest.raises(AppError, match="already exists"):
        service.generate(request)
    assert checkpoint.read_bytes() == b"existing-model"
    assert not service._lock.locked()
