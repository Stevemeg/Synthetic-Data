# ADR-0013: deterministic HTML governance artifacts

Status: Accepted. Phase 5.

## Context

Completed evaluations already persist a verified manifest and independent metrics. Product reporting must preserve that evidence, not recompute it or introduce heavy rendering infrastructure.

## Decision

Use escaped, self-contained HTML with print CSS and a restrictive CSP. An explicit lightweight endpoint reads verified persisted evidence and creates one immutable `GOVERNANCE_REPORT` per evaluation under a row lock. Register bytes/size/hash and policy/evaluation metadata through the established artifact store and transaction/compensation semantics. No queue, browser renderer, external assets or PDF dependency is introduced.

## Consequences

Reports are portable and inexpensive at current bounded single-table sizes. Explicit generation also supports historical completed evaluations. Download continues through registered artifact IDs; reports remain sensitive internal artifacts. Authentication is still absent. Unknown commit outcomes retain bytes for maintenance. Larger future reports may justify worker execution, but that architecture is not required for current bounded HTML assembly.
