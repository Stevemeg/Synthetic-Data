# Retention and deletion

Organization records persist default retention for source, synthetic, model and report artifacts. The implemented defaults are `manual`: no automatic expiry. The UI states that objects remain until an Owner requests project deletion. Automatic timed retention and per-dataset deletion are not implemented.

An Owner enters the exact project name and submits `POST /api/v1/projects/{id}/deletion`. Active/queued work must first finish or be cancelled. The request transaction records `DELETION_REQUESTED`, archives/hides the project and appends an authenticated audit event; it does not delete storage synchronously.

Worker cleanup progresses through `PURGING` to `DELETED`. A dedicated PostgreSQL advisory lock prevents concurrent purgers. No transaction is held during storage I/O. Deletion is idempotent and a failed purge remains retryable on subsequent worker polls. Stored source, model, synthetic and report objects are removed; project/dataset/job/evaluation/policy/artifact metadata and audit records remain as tombstones/provenance. Deleted project descendants cannot be downloaded through the API.

This is logical object deletion according to configured object-store semantics. Physical media erasure is controlled by the provider. Old versions, replicas and backups may retain bytes. There is no secure physical overwrite, guaranteed destruction or cryptographic erasure claim. Restoration must replay deletion tombstones against restored objects before reopening access; never resurrect deleted projects by resetting their lifecycle state.

Metadata retention is intentionally conservative for provenance. Names, descriptions and schema labels can themselves be sensitive; organization owners must follow their actual data handling policy. A future metadata-minimization policy needs its own migration and tests.
