# ADR-0018: Manual retention and background project deletion

Accepted, Phase 6. Organization retention explicitly defaults to manual for
source, synthetic, model and report objects. No hidden expiration runs.
OWNER confirms the exact project name. Active work blocks the request. The
project transitions ACTIVE → DELETION_REQUESTED → PURGING → DELETED and is
immediately hidden from ordinary resource access. A worker with a dedicated
PostgreSQL advisory lock deletes its registered objects outside the request
and outside long database transactions. Partial failures remain resumable.

Metadata, provenance, policy decisions and append-only audit records remain;
this is not personal-data anonymization. Object deletion follows provider
semantics. Versions, replicas, backups and physical media are operator/provider
responsibilities. No secure overwrite or guaranteed erasure is claimed.
Dataset-only deletion and automatic expiration are deferred.
