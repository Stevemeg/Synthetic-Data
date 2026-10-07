from ...schemas.evaluation import PolicyCreate
from ..tabular.profile import canonical_hash
from .common import metric

PASS_MEANING = "PASS means only that the artifact satisfied this configured MedSynth Guard policy version. It does not mean anonymity, zero privacy risk, medical validity or regulatory approval."  # nosec B105


def policy_hash(policy):
    return canonical_hash(PolicyCreate.model_validate(policy).model_dump(mode="json"))


def evidence_catalog(structural, quality, privacy, utility, group):
    result = {
        "structural_validation": metric(structural["passed"], "APPLICABLE"),
        "group_leakage_free": metric(
            group["gating_eligible"], "APPLICABLE" if group["assessed"] else "NOT_APPLICABLE"
        ),
    }
    for partition in ("training", "holdout"):
        props = quality[partition].get("properties", {})
        for name, property_name in (
            ("column_shapes", "Column Shapes"),
            ("column_pair_trends", "Column Pair Trends"),
        ):
            result[f"{partition}_{name}"] = props.get(property_name, metric())
    result["exact_training_match_fraction"] = metric(
        privacy["exact_training"]["exact_match_fraction"], "APPLICABLE"
    )
    for key in ("dcr_baseline_protection", "dcr_overfitting_protection", "disclosure_protection"):
        result[key] = privacy[key]
    methodology = privacy["dcr_overfitting_protection"].get("methodology")
    result["dcr_overfitting_gating_eligible"] = (
        metric(methodology["gating_eligible"], "APPLICABLE") if methodology else metric()
    )
    result["tstr_trtr_ratio"] = utility
    return result


def evaluate_policy(policy, evidence, request):
    if policy is None:
        return {
            "decision": "NOT_EVALUATED",
            "rules": [],
            "reasons": ["No release policy selected"],
            "meaning": PASS_MEANING,
            "policy": None,
        }
    typed = PolicyCreate.model_validate({key: policy[key] for key in PolicyCreate.model_fields})
    results = []
    for name, rule in typed.rules.items():
        item = evidence.get(name, metric())
        value, applicability = item["score"], item["applicability"]
        configured = (
            rule.when == "ALWAYS"
            or (rule.when == "DISCLOSURE_CONFIGURED" and request.privacy is not None)
            or (rule.when == "UTILITY_CONFIGURED" and request.utility is not None)
        )
        required = rule.required and configured
        if not configured:
            status, reason = "NOT_APPLICABLE", "Rule condition does not apply"
        elif applicability == "FAILED":
            status, reason = "ERROR", "Metric failed"
        elif applicability in {"INSUFFICIENT_DATA", "ADVISORY_ONLY"}:
            status, reason = "INSUFFICIENT_DATA", "Evidence is not eligible for release gating"
        elif applicability == "NOT_APPLICABLE" or value is None:
            status, reason = "NOT_APPLICABLE", "Metric unavailable; no passing value inferred"
        else:
            passes = (
                (rule.equals is None or value == rule.equals)
                and (rule.minimum is None or value >= rule.minimum)
                and (rule.maximum is None or value <= rule.maximum)
            )
            status, reason = (
                ("PASS", "Configured threshold satisfied")
                if passes
                else ("FAIL", "Configured threshold violated")
            )
        results.append(
            {
                "metric": name,
                "actual_value": value,
                "metric_applicability": applicability,
                "threshold": rule.model_dump(),
                "required": required,
                "status": status,
                "reason": reason,
            }
        )
    if any(r["status"] == "FAIL" for r in results):
        decision = "FAIL"
    elif any(r["required"] and r["status"] != "PASS" for r in results) or not any(
        r["status"] == "PASS" for r in results
    ):
        decision = "REVIEW_REQUIRED"
    else:
        decision = "PASS"
    return {
        "decision": decision,
        "policy": {k: policy[k] for k in ("id", "name", "version", "policy_hash", "illustrative")},
        "rules": results,
        "reasons": [f"{r['metric']}: {r['status']} — {r['reason']}" for r in results],
        "meaning": PASS_MEANING,
        "warnings": [
            "Illustrative operational thresholds; not scientific, medical, legal or regulatory standards"
        ]
        if typed.illustrative
        else [],
    }
