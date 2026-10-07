# Security boundaries and limitations

MedSynth Guard is an engineering/research platform. It does not by itself establish HIPAA/GDPR compliance, clinical validity, anonymization or zero re-identification risk.

Implemented controls include OIDC code/PKCE authentication, revocable database sessions, issuer/subject identity keys, organization-scoped ORM queries, centralized role checks, CSRF token plus Origin validation, explicit credentialed CORS, private registered-artifact downloads, SHA-256 verification, bounded narrow CSV ingestion, escaped HTML reports, restricted model downloads and append-only application audit events.

Production startup rejects development authentication, debug logging, local storage, wildcard/malformed CORS, missing OIDC/session/metrics settings, HTTP browser/identity/storage endpoints and common/default database passwords. Cookies are HttpOnly, Secure and SameSite=Lax. API responses include nosniff, frame restrictions, no-referrer, Permissions-Policy and production CSP/HSTS. Production disables public interactive API docs. The static frontend's CSP permits inline styles for Emotion, but not arbitrary inline scripts. Use HTTPS at a trusted reverse proxy and do not trust forwarded headers from arbitrary clients.

Submission bursts have a per-process limit; reverse-proxy limits remain necessary across replicas and for authentication/upload abuse. Upload size/CSV bounds, generated names and isolated temporary files remain. No arbitrary model/pickle upload or user-selected deserialization path is supported. Trusted trained model files still require integrity and restricted access.

Logs/audits must never contain tokens, credentials, patient rows or report content. Structured application logs allow only safe fields; user and organization UUIDs are permitted correlation values, not metric labels. Internal metrics use a dedicated credential and are blocked by the bundled public proxy. Protect logs and audit databases as sensitive operational metadata.

Service/database/object-store administrators remain trusted; no RLS, tamper-proof ledger, clinical certification or penetration-test certification is claimed. Audit triggers prevent ordinary updates/deletes but an administrator can alter the database. Infrastructure encryption, object version cleanup, backups, IdP MFA/conditional access and credential rotation are operator responsibilities.

Security scanners are engineering evidence, not proof of safety. Review all findings and rerun regressions after upgrades. See [threat model](THREAT_MODEL.md), [authentication](AUTHENTICATION.md), [authorization](AUTHORIZATION.md), [storage](STORAGE.md), and [verification](PHASE_6_VERIFICATION.md).

## Static scan review

Targeted Bandit annotations cover explicit null guest/development CSRF values,
policy decision/limitation strings, constant git commands resolved to an absolute
executable, and the optional internally bound, bearer-protected worker metrics
port. These are narrow reviewed findings, not blanket suppression. The immutable
runtime removes unnecessary global/venv pip installation tooling and applies
available distribution security upgrades. Full container reports still disclose
unfixed distribution advisories; absence of a fix is not a security assurance.

See [actual scanner findings and release disposition](SECURITY_SCAN_REVIEW.md).
