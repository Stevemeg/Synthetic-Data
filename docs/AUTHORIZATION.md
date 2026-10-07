# Authorization

All project/dataset/job/evaluation/policy/report/artifact/workspace routes require authentication in OIDC mode. Health, readiness, capability metadata and OIDC session endpoints have intentionally separate behavior. Internal metrics require their own bearer credential and must also be blocked at the public proxy.

| Role | Read resources / permitted downloads / compare | Upload, schema, generation, evaluation, reports | Policies and project settings | Membership and project deletion |
| --- | --- | --- | --- | --- |
| Viewer | Yes | No | No | No |
| Editor | Yes | Yes | No | No |
| Owner | Yes | Yes | Yes | Yes |

Editors may create projects. Used policy versions remain immutable for every role. Models remain non-downloadable for all browser roles. Source records have no preview or direct download endpoint. Owners can change/remove memberships; the final active Owner cannot be removed or demoted. Provisioning additional identities is an operator action, not a pretend email invitation.

`security/auth.py` centralizes authentication, CSRF and route capability enforcement. Request sessions use `TenantSession` and organization predicates for projects and their descendants before SQL reads. Identity-map shortcuts are overridden for scoped entities. Pagination/count queries are scoped too. Ordinary worker sessions do not represent browser users.

Foreign resource UUIDs consistently produce 404 without confirming existence. Selecting an organization without membership produces 403. Authenticated roles lacking an operation receive 403. Organization membership is refreshed on each request, so revoked users cannot continue using a cached frontend role. No authorization decision depends solely on frontend hiding.

The frontend disables submission controls for Viewers, restricts generation/evaluation routes, limits policy changes to Owners, and provides Owner membership/deletion controls. Organization switching resets project navigation and remounts scoped resources. Stale responses from another organization are discarded.
