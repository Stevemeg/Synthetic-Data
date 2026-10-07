# ADR-0009: Separate evaluation domain, existing execution queue

Status: Accepted. Date: 2026-10-02.

Evaluation needs durable references, configuration and result provenance separate
from generation. Duplicating queue machinery would risk different fencing and
recovery guarantees. EvaluationRun owns its domain state and links to a typed
EVALUATION work item in the existing GenerationJob queue. Lifecycle/timestamps/
claims/errors derive from that item. Existing SKIP LOCKED, ownership locks,
leases, supervised children, retries and transactional publication are reused.

New JSON report artifacts use existing storage and access checks. Database
constraints and deferred success publication checks protect references/result sets.
Generation lists exclude evaluation work items. The queue item's completion unit
is one evaluation, explicitly distinct from generated row count. No second broker
or infrastructure is added.
