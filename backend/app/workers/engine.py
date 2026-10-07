import multiprocessing
import os
import signal
import threading
from dataclasses import replace
from pathlib import Path
from time import monotonic

from ..config import Settings
from ..core.logging import configure_logging, job_context
from ..schemas.generation import GenerationRequest
from ..services.generation.service import GenerationService
from ..services.jobs.failures import classify_failure


def generation_child(send, settings: Settings, spec: dict, workspace: str, deadline):
    """Only the child computes. It never owns DB connections or publishes artifacts."""
    configure_logging(settings.log_level)
    job_context.set({key: spec[key] for key in ("job_id", "project_id", "dataset_id")})
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    def guard():
        parent = multiprocessing.parent_process()
        while True:
            if parent is None or not parent.is_alive() or monotonic() > deadline.value:
                os._exit(70)
            threading.Event().wait(0.2)

    threading.Thread(target=guard, daemon=True).start()
    try:
        root = Path(workspace)
        scientific = spec["configuration"]
        if spec.get("job_kind") == "EVALUATION":
            from ..services.evaluation.execution import execute

            runtime_settings = replace(settings, **scientific["limits"])
            result = execute(
                spec, root, runtime_settings, lambda event: send.send({"event": event})
            )
            send.send({"ok": True, "result": result})
            return
        if spec["modality"] == "tabular":
            from ..services.tabular.service import execute

            runtime_settings = replace(settings, **scientific["limits"])
            result = execute(
                spec, root, runtime_settings, lambda event: send.send({"event": event})
            )
            send.send({"ok": True, "result": result})
            return
        runtime_settings = replace(
            settings,
            generated_dir=root / "generated",
            upload_dir=root / "uploads",
            model_dir=root / "models" if spec["modality"] == "timeseries" else settings.model_dir,
            ecg_epochs=scientific["ecg_epochs"],
            ecg_sampling_rate=scientific["ecg_sampling_rate"],
            **{
                key: scientific.get(key, getattr(settings, key))
                for key in (
                    "max_ecg_segments",
                    "max_source_rows",
                    "max_upload_mb",
                    "max_samples",
                    "max_images",
                )
            },
        )
        request = GenerationRequest(
            spec["modality"],
            spec["count"],
            spec["seed"],
            scientific.get("modality"),
            Path(spec["source_path"]) if spec["source_path"] else None,
            run_id=spec["token"],
        )
        result = GenerationService(runtime_settings).generate(request)
        send.send({"ok": True, "result": result.to_dict()})
    except Exception as error:
        failure = classify_failure(error)
        send.send(
            {
                "ok": False,
                "failure": {
                    "code": "EVALUATION_FAILED"
                    if spec.get("job_kind") == "EVALUATION" and failure.code == "GENERATION_FAILED"
                    else failure.code,
                    "message": "Evaluation failed without publishing a completed report set"
                    if spec.get("job_kind") == "EVALUATION" and failure.code == "GENERATION_FAILED"
                    else failure.message,
                    "retryable": failure.retryable,
                    "diagnostics": failure.diagnostics,
                },
            }
        )
    finally:
        send.close()
