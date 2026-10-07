"""Verify signals from the local security fixture without exposing its credentials."""

import json
import re
import subprocess
from pathlib import Path

from dotenv import dotenv_values


def docker(*args):
    result = subprocess.run(["docker", *args], capture_output=True, check=True)
    return (result.stdout + result.stderr).decode("utf-8", errors="replace")


def metrics(container, endpoint):
    # The bearer credential stays inside the container, not command arguments/output.
    code = (
        "import os,urllib.request; "
        f"r=urllib.request.Request({endpoint!r}, "
        "headers={'Authorization':'Bearer '+os.environ['METRICS_TOKEN']}); "
        "print(urllib.request.urlopen(r,timeout=5).read().decode())"
    )
    return docker("exec", container, "python", "-c", code)


def positive(text, prefix):
    return any(
        float(line.rsplit(" ", 1)[1]) > 0
        for line in text.splitlines()
        if line.startswith(prefix) and not line.startswith("#")
    )


def main():
    api = "synthetic-data-api-1"
    worker = "synthetic-data-worker-1"
    api_metrics = metrics(api, "http://127.0.0.1:5000/internal/metrics")
    worker_metrics = metrics(worker, "http://127.0.0.1:9091/metrics")
    logs = docker("logs", api) + docker("logs", worker)
    events = []
    for line in logs.splitlines():
        if line.startswith("{"):
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    secrets = [
        value
        for key, value in dotenv_values(".env").items()
        if re.search("SECRET|PASSWORD|ACCESS_KEY|METRICS_TOKEN", key) and value and len(value) >= 8
    ]
    results = {
        "request_count_positive": positive(api_metrics, "medsynth_http_requests_total"),
        "storage_count_positive": positive(api_metrics, "medsynth_storage_seconds_count"),
        "persisted_queue_gauges": 'medsynth_jobs{status="succeeded"}' in api_metrics,
        "worker_claims_positive": positive(worker_metrics, "medsynth_worker_claims_total"),
        "worker_execution_positive": positive(
            worker_metrics, "medsynth_worker_execution_seconds_count"
        ),
        "correlated_user_requests": sum(
            bool(e.get("request_id") and e.get("user_id") and e.get("organization_id"))
            for e in events
            if e.get("event") == "http_request"
        ),
        "worker_job_context": sum(bool(e.get("job_id")) for e in events),
        "secret_values_absent": all(value not in logs for value in secrets),
        "log_records": len(events),
    }
    assert all(results.values()), "Operational verification failed; inspect safe result fields"
    output = Path("backend/.work/operations-verification.json")
    output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results))


if __name__ == "__main__":
    main()
