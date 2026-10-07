# ADR-0012: Immutable rule-based policies

Status: Accepted. Date: 2026-10-02.

Scientific dimensions cannot be meaningfully combined by arbitrary platform
weights. Policies instead name explicit metrics, thresholds, applicability and
required/conditional behavior. Versions are immutable and canonical hashed.
No production default exists; demo policies are conspicuously illustrative.

Unavailable required metrics cause REVIEW_REQUIRED; violations cause FAIL;
PASS denotes configured policy compliance only. Persist every rule value/status/
reason and policy snapshot as JSON. Do not use SAFE/UNSAFE labels, public-release
automation or healthcare/compliance guarantees.
