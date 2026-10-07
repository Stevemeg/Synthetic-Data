"""Normalize raw Trivy evidence and fail closed on individually unreviewed risks.

This is a release-evidence check, not a scanner suppression mechanism. Raw scans
and SBOMs are kept intact. An empty review file deliberately cannot approve High
or Critical findings. See docs/SECURITY_SCAN_REVIEW.md for review requirements.
"""

import argparse
import json
import os
import subprocess
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path


def inventory(root):
    findings = []
    summaries = {}
    for path in sorted(root.glob("*-vulnerabilities.json")):
        image = path.name.removesuffix("-vulnerabilities.json")
        scan = json.loads(path.read_text(encoding="utf-8"))
        counts = Counter()
        grouped = {}
        for result in scan.get("Results", []):
            for vulnerability in result.get("Vulnerabilities", []):
                counts[vulnerability["Severity"]] += 1
                if vulnerability["Severity"] not in ("HIGH", "CRITICAL"):
                    continue
                key = vulnerability["VulnerabilityID"]
                item = grouped.setdefault(
                    key,
                    {
                        "cve": key,
                        "image": image,
                        "image_id": scan.get("Metadata", {}).get("ImageID"),
                        "repo_digests": scan.get("Metadata", {}).get("RepoDigests", []),
                        "os": scan.get("Metadata", {}).get("OS"),
                        "severity": vulnerability["Severity"],
                        "cvss": vulnerability.get("CVSS", {}),
                        "packages": [],
                        "disposition": "BLOCKING",
                        "runtime_presence": "REVIEW_REQUIRED",
                        "runtime_purpose": "REVIEW_REQUIRED",
                        "reachability": "REVIEW_REQUIRED",
                        "privilege_required": "REVIEW_REQUIRED",
                        "attack_preconditions": "REVIEW_REQUIRED",
                        "compensating_controls": "REVIEW_REQUIRED",
                    },
                )
                package = {
                    "name": vulnerability["PkgName"],
                    "installed": vulnerability["InstalledVersion"],
                    "fixed": vulnerability.get("FixedVersion", ""),
                    "fix_available": bool(vulnerability.get("FixedVersion")),
                    "vendor_status": vulnerability.get("Status"),
                    "source": vulnerability.get("PrimaryURL"),
                }
                if package not in item["packages"]:
                    item["packages"].append(package)
        findings.extend(grouped.values())
        summaries[image] = {**dict(counts), "distinct_high_critical": len(grouped)}
    # A source-built main Go module may report (devel), which scanners cannot
    # version-match. Preserve upstream's findings rather than mistaking that
    # metadata gap for remediation. Each remains individually reviewable.
    if "minio" in summaries:
        known = json.loads(Path(__file__).with_name("manual_container_findings.json").read_text())
        seen = {(item["image"], item["cve"]) for item in findings}
        for item in known:
            if (item["image"], item["cve"]) not in seen:
                findings.append(item)
            else:
                actual = next(
                    f for f in findings if f["image"] == item["image"] and f["cve"] == item["cve"]
                )
                actual["vendor_fix"] = item["packages"][0]["fixed"]
                actual["vendor_source"] = item["source"]
        summaries["minio"]["manual_source_findings"] = len(known)
    return summaries, findings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--inventory-only", action="store_true")
    args = parser.parse_args()
    summaries, findings = inventory(args.evidence)
    review_path = Path(__file__).with_name("container_dispositions.json")
    reviews = json.loads(review_path.read_text(encoding="utf-8"))["dispositions"]
    required_images = {"api", "worker", "frontend", "postgres", "keycloak", "minio"}
    errors = []
    if set(summaries) != required_images:
        errors.append("Missing or unexpected runtime image scans")
    for item in findings:
        matches = [
            review
            for review in reviews
            if review.get("cve") == item["cve"] and review.get("image") == item["image"]
        ]
        if len(matches) != 1:
            errors.append(f"{item['image']}: {item['cve']}: no unique individual review")
            continue
        review = matches[0]
        expected = sorted((p["name"], p["installed"]) for p in item["packages"])
        if sorted(tuple(p) for p in review.get("packages", [])) != expected:
            errors.append(f"{item['image']}: {item['cve']}: reviewed packages/version changed")
            continue
        state = review.get("disposition")
        if state not in {"NOT_PRESENT", "NOT_REACHABLE", "MITIGATED", "ACCEPTED_NO_FIX"}:
            errors.append(f"{item['image']}: {item['cve']}: unresolved disposition")
            continue
        fields = (
            "evidence",
            "rationale",
            "runtime_presence",
            "runtime_purpose",
            "reachability",
            "privilege_required",
            "attack_preconditions",
            "compensating_controls",
            "review_date",
        )
        if any(not review.get(field) for field in fields):
            errors.append(f"{item['image']}: {item['cve']}: incomplete review")
            continue
        if date.fromisoformat(review["review_date"]) < date.today():
            errors.append(f"{item['image']}: {item['cve']}: expired review")
            continue
        if any(p["fix_available"] for p in item["packages"]) or item.get("vendor_fix"):
            if review.get("compatible_fix") is not False or not review.get(
                "incompatible_fix_evidence"
            ):
                errors.append(f"{item['image']}: {item['cve']}: compatible fix must be applied")
                continue
        if item["severity"] == "CRITICAL" and state not in {"NOT_PRESENT", "NOT_REACHABLE"}:
            errors.append(f"{item['image']}: {item['cve']}: unresolved Critical risk")
            continue
        item.update({field: review[field] for field in fields})
        item["disposition"] = state
    commit = (
        os.getenv("GITHUB_SHA")
        or subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    )
    for image in ("api", "worker"):
        inspection = args.evidence / f"{image}-image.json"
        if inspection.exists():
            info = json.loads(inspection.read_text())[0]
            if f"APP_COMMIT={commit}" not in info["Config"]["Env"]:
                errors.append(f"{image}: image build commit does not match workflow commit")
    base_images = {}
    for image, recipe in (
        ("api", "ops/Dockerfile.backend"),
        ("worker", "ops/Dockerfile.backend"),
        ("frontend", "ops/Dockerfile.frontend"),
        ("postgres", "ops/Dockerfile.postgres"),
        ("minio", "ops/minio/Dockerfile"),
    ):
        if Path(recipe).exists():
            lines = Path(recipe).read_text().splitlines()
            candidates = [line.split()[1] for line in lines if line.startswith("FROM ")]
            base_images[image] = next(
                (
                    line.split()[1]
                    for line in lines
                    if line.startswith("FROM ") and line.endswith(" AS runtime")
                ),
                candidates[-1],
            )
    if Path("compose.security.yaml").exists():
        base_images["keycloak"] = next(
            line.strip().removeprefix("image: ")
            for line in Path("compose.security.yaml").read_text().splitlines()
            if "image: quay.io/keycloak/" in line
        )
    for item in findings:
        item["base_image"] = base_images.get(item["image"], "not supplied in test fixture")
        item["scanner"] = "Trivy 0.75.0 plus individual upstream source review"
    report = {
        "commit": commit,
        "version": Path("VERSION").read_text(encoding="utf-8").strip(),
        "scan_date": datetime.now(timezone.utc).isoformat(),
        "scanner": json.loads((args.evidence / "scanner-version.json").read_text())
        if (args.evidence / "scanner-version.json").exists()
        else "pending",
        "summary": summaries,
        "findings": findings,
        "release_gate_errors": errors,
    }
    (args.evidence / "normalized-findings.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"commit": commit, "summary": summaries, "unresolved": len(errors)}, indent=2))
    if errors and not args.inventory_only:
        print(
            "Container release gate FAILED. See normalized-findings.json; no findings were suppressed."
        )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
