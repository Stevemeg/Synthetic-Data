# Authentication

OIDC Authorization Code flow with S256 PKCE is implemented through Authlib. Discovery, ID-token signature, issuer, audience, expiry, state and nonce validation use the library. The durable external identity is `(issuer, subject)`; email is informational. Local browser verification uses Keycloak 26.8.0, not a mocked token endpoint.

The browser receives an opaque random `medsynth_session` cookie. Only its SHA-256 lookup digest is stored in PostgreSQL. Sessions expire after `SESSION_HOURS` (default 8, maximum 24). Logout removes the database session and clears the cookie; copying the old cookie does not restore access. It ends the application session, not every session at the identity provider. Sign-in requests `prompt=login`.

Provider access/ID tokens are discarded after identity validation. They are never stored in browser localStorage/sessionStorage or reports. Authlib temporarily stores signed authorization state, nonce and PKCE verifier in an HttpOnly, SameSite=Lax state cookie with a ten-minute lifetime. This signed cookie is not encrypted. Production sets Secure on both cookies and requires a generated signing secret. Cookie domains are host-only. Use a same-origin HTTPS frontend/API deployment.

`GET /api/v1/auth/me` supplies identity, memberships and a CSRF token. The frontend holds the token in memory. Only the selected organization UUID is saved in sessionStorage; it is rechecked against membership on every load. State-changing cookie API requests require the matching CSRF header and an explicitly allowed Origin. No silent account creation grants organization access.

Configure `AUTH_MODE=oidc`, `OIDC_ISSUER`, `OIDC_CLIENT_ID`, optional `OIDC_CLIENT_SECRET`, `OIDC_REDIRECT_URI`, `FRONTEND_URL`, and `SESSION_SECRET`. Register the exact callback URL with a standards-compliant provider. Do not enable implicit or password flows for the application client. Production requires HTTPS URLs, S3 storage, explicit CORS and internal metrics credentials.

`AUTH_MODE=development` is a deliberately unauthenticated local bypass with Owner permissions only in the deterministic development organization. It is visibly marked and rejected in production. It is suitable only for fake-data development/regression tests. It is not an identity assertion.

New real identities must sign in before an operator assigns membership:

```sh
python -m backend.scripts.assign_membership --issuer <issuer> --subject <subject> --organization <slug> --name <organization-name> --role OWNER
```

The subject comes from the configured provider, not an email address. The command records a system provisioning event. Adding invitations, password management, SSO administration and provider-wide logout is outside this implementation.
