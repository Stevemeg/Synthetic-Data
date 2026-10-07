# ADR-0016: Organization boundary and three membership roles

Accepted, Phase 6. Projects belong to one organization. OWNER administers
membership, policies, project settings and deletion; EDITOR operates the
generation/evaluation workflow; VIEWER reads and downloads allowed output.
Every protected router uses central authentication, CSRF and role enforcement.
A request-scoped SQLAlchemy session injects organization predicates into ORM
resource and aggregate reads, including Session.get. Cross-tenant UUID swaps
return 404; role denial returns 403; missing authentication returns 401.

Database keys/checks and an immutable project-organization trigger provide
relationship protection. Workers independently validate project/dataset/job
relationships before execution. Ordinary machine sessions are not scoped to
one user; these invariants remain necessary. PostgreSQL RLS is not implemented.
The appended migration assigns existing projects and audits to a deterministic
development organization without changing existing resource IDs or bytes.
