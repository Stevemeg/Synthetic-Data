# Organizations and tenant isolation

Organization is the top-level boundary. Each Project has one non-null organization FK. Membership joins persisted users to organizations with Owner/Editor/Viewer roles. Children retain their existing project relationships; composite FKs and existing evaluation reference triggers preserve dataset/job/policy/evaluation consistency.

Migration `0005_identity_tenancy` appends to migrations 0001-0004. It creates a deterministic development organization (`00000000-0000-4000-8000-000000000001`) and assigns existing projects/audit records to it. Historical anonymous/system/worker actor semantics remain historical facts. Project organizations cannot be reassigned by normal updates. Downgrade refuses to discard populated identity/lifecycle data; use a verified backup.

`verify_identity_migration` compared every resource ID before/after migration on the populated Phase 5 database: 31 projects, 31 datasets, 49 jobs, 14 evaluations, 9 policies, 204 artifacts, 621 audit events preserved. Clean migrations and Alembic drift checks are separately tested.

This implementation uses application-layer query scoping, not PostgreSQL RLS. Database administrators and the service connection remain trusted. Never expose database or object-store credentials to application users. An organization UUID, project UUID or storage key is not an authorization credential.

The worker verifies project/dataset ownership and evaluation artifact job/project ownership before execution. Queue claims exclude projects in deletion lifecycle states. Publication retains the established fenced claim and same-project database invariants.
