# ADR-0015: OIDC with revocable application sessions

Accepted, Phase 6. Authlib performs Authorization Code with S256 PKCE, state,
nonce and signed ID-token validation against configured discovery. Identity is
issuer + subject. Provider access/refresh tokens are not persisted or sent to
React. A random opaque HttpOnly cookie addresses a SHA-256 session record in
PostgreSQL. Production requires Secure cookies and HTTPS. Session mutations
require a synchronizer CSRF header and explicit Origin. Logout deletes the
record; provider SSO logout is intentionally separate. Sessions expire after
eight hours by default. There is no automatic organization enrollment.

An optional private discovery/token/JWKS origin supports containers while
preserving the public issuer and browser authorization endpoint. Discovery
issuer must match; token validation still uses the public issuer. Production
requires HTTPS for both origins. This is routing configuration, not a custom
identity protocol. Local development bypass is explicit and production rejects it.
