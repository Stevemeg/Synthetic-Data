"""Release gate must permit evidenced risk while rejecting stale/unknown findings."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def scan_review(tmp_path):
    source = Path(__file__).resolve().parents[2] / "ops"
    shutil.copyfile(source / "review_container_findings.py", tmp_path / "review.py")
    (tmp_path / "manual_container_findings.json").write_text("[]", encoding="utf-8")
    (tmp_path / "VERSION").write_text("0.6.0", encoding="utf-8")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    for image in ("api", "worker", "frontend", "postgres", "keycloak", "minio"):
        (evidence / f"{image}-vulnerabilities.json").write_text(
            json.dumps({"Results": []}), encoding="utf-8"
        )
    vulnerability = {
        "VulnerabilityID": "CVE-2099-12345",
        "PkgName": "fixture-lib",
        "InstalledVersion": "1.0",
        "Severity": "HIGH",
    }
    (evidence / "api-vulnerabilities.json").write_text(
        json.dumps({"Results": [{"Vulnerabilities": [vulnerability]}]}),
        encoding="utf-8",
    )
    review = {
        "image": "api",
        "cve": "CVE-2099-12345",
        "packages": [["fixture-lib", "1.0"]],
        "disposition": "MITIGATED",
        "evidence": "fixture evidence",
        "rationale": "fixture rationale",
        "runtime_presence": "fixture present",
        "runtime_purpose": "fixture purpose",
        "reachability": "fixture path",
        "privilege_required": "fixture privilege",
        "attack_preconditions": "fixture precondition",
        "compensating_controls": "fixture control",
        "review_date": "2099-01-01",
    }
    return tmp_path, evidence, review


def run_review(root, reviews):
    (root / "container_dispositions.json").write_text(
        json.dumps({"dispositions": reviews}), encoding="utf-8"
    )
    return subprocess.run(
        [sys.executable, str(root / "review.py"), str(root / "evidence")],
        cwd=root,
        env={**os.environ, "GITHUB_SHA": "a" * 40},
        capture_output=True,
        text=True,
        check=False,
    )


def test_individually_reviewed_high_does_not_require_zero_high(scan_review):
    root, evidence, review = scan_review
    result = run_review(root, [review])
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads((evidence / "normalized-findings.json").read_text())
    assert report["summary"]["api"]["HIGH"] == 1
    assert report["findings"][0]["disposition"] == "MITIGATED"


@pytest.mark.parametrize("failure", ["unknown", "version", "expired", "fixable", "critical"])
def test_unresolved_or_changed_risk_fails_closed(scan_review, failure):
    root, evidence, review = scan_review
    reviews = [review]
    if failure == "unknown":
        reviews = []
    elif failure == "version":
        review["packages"] = [["fixture-lib", "0.9"]]
    elif failure == "expired":
        review["review_date"] = "2020-01-01"
    else:
        path = evidence / "api-vulnerabilities.json"
        scan = json.loads(path.read_text())
        vulnerability = scan["Results"][0]["Vulnerabilities"][0]
        if failure == "fixable":
            vulnerability["FixedVersion"] = "1.1"
        else:
            vulnerability["Severity"] = "CRITICAL"
        path.write_text(json.dumps(scan), encoding="utf-8")
    result = run_review(root, reviews)
    assert result.returncode == 1, result.stdout + result.stderr
    report = json.loads((evidence / "normalized-findings.json").read_text())
    assert report["release_gate_errors"]
    assert report["findings"][0]["disposition"] == "BLOCKING"
