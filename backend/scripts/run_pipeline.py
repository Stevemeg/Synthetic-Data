import argparse
import logging
import shutil
from dataclasses import replace
from pathlib import Path

from dotenv import load_dotenv

from backend.app.config import ROOT, Settings
from backend.app.core.errors import AppError
from backend.app.schemas.generation import GenerationRequest
from backend.app.services.generation.service import GenerationService


def run_full_pipeline(input_file, output_file, model_output_file, count=100, seed=42, epochs=None):
    settings = Settings.from_env()
    if epochs is not None:
        if type(epochs) is not int or not 1 <= epochs <= 50:
            raise AppError("epochs must be between 1 and 50")
        settings = replace(settings, ecg_epochs=epochs)
    output, model_output = Path(output_file), Path(model_output_file)
    if output.suffix != ".npz" or model_output.suffix != ".pt":
        raise AppError("Output paths must end in .npz and .pt respectively")
    if output.exists() or model_output.exists():
        raise AppError("Output files already exist; choose new paths")
    request = GenerationRequest.parse("timeseries", {"count": count, "seed": seed}, settings)
    request = replace(request, source_path=Path(input_file).resolve())
    result = GenerationService(settings).generate(request)
    output.parent.mkdir(parents=True, exist_ok=True)
    model_output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(settings.generated_dir / request.run_id / "dataset.npz", output)
    shutil.copy2(settings.model_dir / "trained" / request.run_id / "vae.pt", model_output)
    shutil.copy2(
        settings.generated_dir / request.run_id / "metadata.json",
        output.with_suffix(".metadata.json"),
    )
    return result


def main():
    load_dotenv(ROOT / ".env", override=False)
    parser = argparse.ArgumentParser(
        description="Train a Beta ECG VAE and generate unlabeled 96-sample heartbeat windows."
    )
    parser.add_argument("--input_file", required=True)
    parser.add_argument("--output_file", required=True)
    parser.add_argument("--model_output_file", required=True)
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--epochs", type=int, default=None)
    args = parser.parse_args()
    logging.basicConfig(level=Settings.from_env().log_level)
    try:
        result = run_full_pipeline(**vars(args))
    except AppError as error:
        parser.exit(1, f"{error}\n")
    logging.info(
        "ECG run completed run_id=%s count=%s",
        result.metadata.run_id,
        result.metadata.produced_sample_count,
    )


if __name__ == "__main__":
    main()
