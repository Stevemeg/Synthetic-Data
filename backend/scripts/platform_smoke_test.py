"""Genuine HTTP + separate worker smoke workflow using invented ECG input."""

import argparse
import hashlib
import io
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic, sleep

import httpx
import numpy as np
from dotenv import load_dotenv

from backend.app.config import ROOT, Settings


def wait_ready(client, process=None):
    deadline = monotonic() + 30
    while monotonic() < deadline:
        if process is not None and process.poll() is not None:
            raise RuntimeError("API process exited; inspect local service logs")
        try:
            if client.get("/ready").status_code == 200:
                return
        except httpx.TransportError:
            pass
        sleep(0.2)
    raise RuntimeError("API readiness did not succeed")


def workflow(client, start_worker):
    import neurokit2 as nk

    signal = nk.ecg_simulate(duration=8, sampling_rate=125, heart_rate=70, random_state=42)
    raw = (",".join(map(str, signal)) + ",invented-test-label\n").encode()
    response = client.post(
        "/api/v1/projects",
        json={"name": "Platform smoke fixture", "description": "Invented ECG; no patient data"},
    )
    response.raise_for_status()
    project = response.json()
    response = client.post(
        f"/api/v1/projects/{project['id']}/datasets",
        data={"name": "Invented ECG fixture", "modality": "timeseries"},
        files={"file": ("invented_ecg.csv", raw, "text/csv")},
    )
    response.raise_for_status()
    dataset = response.json()
    assert dataset["sha256"] == hashlib.sha256(raw).hexdigest()
    body = {
        "modality": "timeseries",
        "dataset_id": dataset["id"],
        "requested_samples": 2,
        "random_seed": 17,
    }
    key = "smoke-" + project["id"]
    response = client.post(
        f"/api/v1/projects/{project['id']}/jobs", json=body, headers={"Idempotency-Key": key}
    )
    assert response.status_code == 202, response.status_code
    job = response.json()
    replay = client.post(
        f"/api/v1/projects/{project['id']}/jobs", json=body, headers={"Idempotency-Key": key}
    )
    assert replay.status_code == 200 and replay.json()["id"] == job["id"]
    start_worker()
    deadline = monotonic() + 120
    while monotonic() < deadline:
        job = client.get(f"/api/v1/jobs/{job['id']}").json()
        if job["status"] in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        sleep(0.5)
    assert job["status"] == "SUCCEEDED", {
        k: job.get(k) for k in ("status", "error_code", "attempt_count")
    }
    assert job["requested_samples"] == job["produced_samples"] == 2
    artifacts = client.get(f"/api/v1/jobs/{job['id']}/artifacts").json()["items"]
    assert {a["artifact_type"] for a in artifacts} == {
        "SYNTHETIC_DATASET",
        "MODEL_CHECKPOINT",
        "RUN_METADATA",
    }
    for artifact in artifacts:
        response = client.get(f"/api/v1/artifacts/{artifact['id']}/download")
        if artifact["artifact_type"] == "MODEL_CHECKPOINT":
            assert response.status_code == 403
            continue
        response.raise_for_status()
        assert hashlib.sha256(response.content).hexdigest() == artifact["sha256"]
        if artifact["artifact_type"] == "SYNTHETIC_DATASET":
            with np.load(io.BytesIO(response.content), allow_pickle=False) as data:
                assert data["synthetic_sequences"].shape == (2, 96) and "labels" not in data.files
        else:
            manifest = response.json()
            assert manifest["source_dataset_sha256"] == dataset["sha256"]
            assert len(manifest["model"]["sha256"]) == 64
    return project, dataset, job, artifacts


def main(workflow_fn=workflow, restart_check=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:5000")
    parser.add_argument(
        "--authenticated",
        action="store_true",
        help="Use an existing development OIDC application session supplied through MEDSYNTH_DEMO_* environment variables",
    )
    parser.add_argument(
        "--start-services",
        action="store_true",
        help="Start API and separate worker locally, then verify API restart",
    )
    args = parser.parse_args()
    headers, cookies = {}, {}
    if args.authenticated:
        if args.start_services:
            raise SystemExit("Authenticated mode targets an already-running API and worker")
        required = ("MEDSYNTH_DEMO_SESSION", "MEDSYNTH_DEMO_CSRF", "MEDSYNTH_DEMO_ORGANIZATION")
        if not all(os.getenv(name) for name in required):
            raise SystemExit(
                "An existing application session, CSRF token and organization are required; no identity bypass is available"
            )
        cookies = {"medsynth_session": os.environ["MEDSYNTH_DEMO_SESSION"]}
        headers = {
            "X-CSRF-Token": os.environ["MEDSYNTH_DEMO_CSRF"],
            "X-Organization-ID": os.environ["MEDSYNTH_DEMO_ORGANIZATION"],
            "Origin": os.getenv("MEDSYNTH_DEMO_ORIGIN", "http://127.0.0.1:5173"),
        }
    load_dotenv(ROOT / ".env")
    Settings.from_env()
    processes = []
    with TemporaryDirectory(prefix="medsynth_smoke_") as logs:
        env = dict(os.environ)
        env.update({"ECG_EPOCHS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"})
        if args.start_services:
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
            env.update({"APP_HOST": "127.0.0.1", "APP_PORT": str(port)})
            base_url = f"http://127.0.0.1:{port}"
        else:
            base_url = args.base_url

        def launch(module):
            log = open(Path(logs) / (module.replace(".", "_") + ".log"), "ab")
            process = subprocess.Popen(
                [sys.executable, "-m", module], cwd=ROOT, env=env, stdout=log, stderr=log
            )
            log.close()
            processes.append(process)
            return process

        def stop(process):
            if process.poll() is None:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
                else:
                    process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)

        try:
            api_process = launch("backend.app") if args.start_services else None
            with httpx.Client(
                base_url=base_url, timeout=15, headers=headers, cookies=cookies
            ) as client:
                wait_ready(client, api_process)
                print("API/database readiness passed", flush=True)
                project, dataset, job, artifacts = workflow_fn(
                    client, lambda: launch("backend.worker") if args.start_services else None
                )
                print(
                    "Separate-worker generation, hashes, count, manifest and restricted model passed",
                    flush=True,
                )
                if args.start_services:
                    stop(api_process)
                    restarted = launch("backend.app")
                    wait_ready(client, restarted)
                    assert client.get(f"/api/v1/projects/{project['id']}").status_code == 200
                    assert client.get(f"/api/v1/datasets/{dataset['id']}").status_code == 200
                    assert client.get(f"/api/v1/jobs/{job['id']}").json()["status"] == "SUCCEEDED"
                    for artifact in artifacts:
                        assert client.get(f"/api/v1/artifacts/{artifact['id']}").status_code == 200
                    if restart_check:
                        restart_check(client, job)
                    print("Actual API process restart persistence passed", flush=True)
                print(
                    json.dumps(
                        {
                            "project_id": project["id"],
                            "dataset_id": dataset["id"],
                            "job_id": job["id"],
                            "produced_samples": job["produced_samples"],
                            "artifact_count": len(artifacts),
                            "status": "SUCCEEDED",
                        }
                    ),
                    flush=True,
                )
        finally:
            for process in reversed(processes):
                stop(process)


if __name__ == "__main__":
    main()
