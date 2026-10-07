# Container deployment

Use a private VM or small container platform with HTTPS termination, PostgreSQL, a maintained OIDC provider and private S3-compatible storage. No Kubernetes or cloud-specific control plane is required. Do not expose database/object-store/admin ports publicly.

Build images:

```sh
docker build -f ops/Dockerfile.backend --target api -t medsynth-api:0.6.0 .
docker build -f ops/Dockerfile.backend --target worker -t medsynth-worker:0.6.0 .
docker build -f ops/Dockerfile.frontend -t medsynth-frontend:0.6.0 .
```

API and worker run as UID 10001; static nginx runs as UID 101. Runtime images have no frontend development server or API reload mode. The backend uses CPU PyTorch and the existing bounded single-table/ECG evaluation stack. Build secrets and `.env`, local artifacts, temporary work, reports and test screenshots are excluded from the Docker context. Supply commit/build metadata as build arguments. Resolve and record image digests in the actual release.

The frontend image serves hashed assets with long-lived caching, index HTML with revalidation and SPA deep-link fallback. It proxies API calls and blocks internal metrics. Terminate TLS at an outer trusted proxy/load balancer; set HSTS at that HTTPS boundary. Match frontend/callback URLs, issuer and CORS to actual externally visible HTTPS origins. Forwarded headers must be accepted only from known proxies. Do not change cookie security to make public HTTP work.

Provision private storage and a restricted service credential. Supply secrets through environment/container secrets, not checked-in Compose defaults. `APP_ENV=production` performs fail-fast configuration checks. Run `python -m alembic upgrade head` once after backup, verify `/ready`, then roll out API/worker/frontend. Keep the previous release and backups for rollback; migrations may make simple image rollback insufficient.

The local security Compose stack is explicitly development-only: loopback Keycloak and MinIO with generated secrets. It verifies protocols; it is not an HTTPS production deployment or a supported identity/storage service recommendation. See [release](RELEASE.md) for acceptance gates.

## Provider-neutral production Compose

`compose.production.yaml` contains only API, worker, static frontend and an
explicit maintenance migration profile. PostgreSQL, OIDC and S3 are supplied as
private maintained services. Set APP_RELEASE from root VERSION and supply all
required HTTPS URLs/secrets through the deployment environment. After backup:

```sh
docker compose -f compose.production.yaml --profile maintenance run --rm migration
docker compose -f compose.production.yaml up -d
```

Only loopback port 8088 is published for the trusted TLS reverse proxy. Internal
worker metrics are not published. The template has no default password or fake
identity and forces APP_ENV=production. The verified local stack instead uses
compose.runtime.yaml and fixture HTTP services. A public HTTPS deployment has
not been performed; do not describe the local stack as such.
