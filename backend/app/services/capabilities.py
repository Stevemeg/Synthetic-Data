from importlib.metadata import PackageNotFoundError, version
from importlib.util import find_spec

from ..config import Settings
from .generation.imaging import MODEL_FILES
from .tabular.engines import available_engines


def capabilities(settings: Settings):
    tabular_engines = available_engines()
    ecg_ready = all(find_spec(module) is not None for module in ("torch", "neurokit2", "requests"))
    image_ready = find_spec("torch") is not None and all(
        (settings.model_dir / name).is_file() for name in MODEL_FILES.values()
    )
    try:
        evaluation_ready = version("sdmetrics") == "0.32.0" and version("scikit-learn") == "1.9.1"
    except PackageNotFoundError:
        evaluation_ready = False
    return {
        "evaluation": {
            "maturity": "Beta",
            "available": evaluation_ready,
            "sdmetrics_version": "0.32.0" if evaluation_ready else None,
            "profiles": ["BASIC", "STANDARD", "FULL"] if evaluation_ready else [],
            "reason": "Independent dimensions and explicit policy decisions; no certification",
        },
        "capabilities": {
            "tabular": {
                "maturity": "Stable",
                "available": bool(tabular_engines),
                "reason": "Single-table synthesis; Gaussian Copula is the stable default"
                if tabular_engines
                else "Install pinned tabular dependencies",
                "engines": tabular_engines,
            },
            "timeseries": {
                "maturity": "Beta",
                "available": ecg_ready,
                "reason": "Normalized unlabeled ECG heartbeat windows"
                if ecg_ready
                else "Install ML dependencies",
            },
            "imaging": {
                "maturity": "Experimental",
                "available": settings.enable_imaging_lab
                and settings.app_env != "production"
                and image_ready,
                "reason": "Opt-in experimental checkpoint inference; no source conditioning",
            },
            "genomic": {
                "maturity": "Experimental",
                "available": False,
                "reason": "Experimental / unavailable",
            },
        },
        "limits": {
            "max_samples": settings.max_samples,
            "max_images": settings.max_images,
            "max_upload_mb": settings.max_upload_mb,
            "tabular_max_generated_rows": settings.tabular_max_generated_rows,
            "ctgan_max_epochs": settings.ctgan_max_epochs,
            "tvae_max_epochs": settings.tvae_max_epochs,
        },
    }
