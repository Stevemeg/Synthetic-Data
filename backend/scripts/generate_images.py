import argparse
import shutil
from dataclasses import replace
from pathlib import Path

from dotenv import load_dotenv

from backend.app.config import ROOT, Settings
from backend.app.core.errors import AppError
from backend.app.schemas.generation import GenerationRequest
from backend.app.services.generation.imaging import MODEL_FILES
from backend.app.services.generation.service import GenerationService


def generate_images(
    model_path, output_zip_path, num_images, input_image_path=None, modality=None, seed=42
):
    if input_image_path is not None:
        raise AppError("Image upload validation and conditioning are unsupported")
    model_path, output = Path(model_path), Path(output_zip_path)
    if modality not in MODEL_FILES or model_path.name != MODEL_FILES[modality]:
        raise AppError("Model filename must match the selected imaging modality")
    if output.suffix != ".zip" or output.exists():
        raise AppError("Choose a new .zip output path")
    settings = replace(
        Settings.from_env(), model_dir=model_path.resolve().parent, enable_imaging_lab=True
    )
    request = GenerationRequest.parse(
        "imaging", {"count": num_images, "modality": modality, "seed": seed}, settings
    )
    result = GenerationService(settings).generate(request)
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(settings.generated_dir / request.run_id / "dataset.zip", output)
    shutil.copy2(
        settings.generated_dir / request.run_id / "metadata.json",
        output.with_suffix(".metadata.json"),
    )
    return result


def main():
    load_dotenv(ROOT / ".env", override=False)
    parser = argparse.ArgumentParser(
        description="Experimental DCGAN lab: ZIP containing every generated PNG."
    )
    parser.add_argument("--model_path", required=True)
    parser.add_argument("--output_zip_path", required=True)
    parser.add_argument("--count", required=True, type=int)
    parser.add_argument("--modality", required=True, choices=list(MODEL_FILES))
    parser.add_argument(
        "--input_image_path", help="Unsupported; provided only to return a clear error"
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    try:
        generate_images(
            args.model_path,
            args.output_zip_path,
            args.count,
            args.input_image_path,
            args.modality,
            args.seed,
        )
    except AppError as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
