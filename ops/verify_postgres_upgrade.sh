#!/usr/bin/env bash
# Disposable logical-restore check across the old and new vendor distributions.
set -euo pipefail
mkdir -p release-artifacts
old="medsynth-upgrade-old-${GITHUB_RUN_ID:-local}"
new="medsynth-upgrade-new-${GITHUB_RUN_ID:-local}"
trap 'docker rm -f "$old" "$new" >/dev/null 2>&1 || true' EXIT
password=$(python -c 'import secrets; print(secrets.token_urlsafe(32))')
for pair in "$old=postgres:16-bookworm@sha256:efedf3595f1d6f415c08568ba171029bf54052e754cc9f030e3f2412b21f3d67" "$new=medsynth-postgres-development:16"; do
  container=${pair%%=*}
  image=${pair#*=}
  docker run -d --name "$container" --network none --security-opt no-new-privileges \
    --tmpfs /var/lib/postgresql/data -e POSTGRES_USER=upgrade_fixture \
    -e POSTGRES_DB=upgrade_fixture -e "POSTGRES_PASSWORD=$password" \
    --health-cmd 'pg_isready -U upgrade_fixture -d upgrade_fixture' \
    --health-interval 1s --health-timeout 3s --health-retries 120 "$image"
  deadline=$((SECONDS + 180))
  until [ "$(docker inspect --format '{{.State.Health.Status}}' "$container")" = healthy ]; do
    if [ "$SECONDS" -ge "$deadline" ]; then
      docker logs "$container"
      exit 1
    fi
    sleep 1
  done
done
docker exec -i "$old" psql -U upgrade_fixture -d upgrade_fixture -v ON_ERROR_STOP=1 <<'SQL'
CREATE TABLE upgrade_probe(id integer PRIMARY KEY, label text NOT NULL UNIQUE, payload jsonb NOT NULL);
INSERT INTO upgrade_probe VALUES (1,'alpha','{"invented":true}'),(2,'Zulu','{"invented":true}'),(3,'éclair','{"invented":true}'),(4,'Ångström','{"invented":true}'),(5,'omega','{"invented":true}');
SQL
docker exec "$old" pg_dump -U upgrade_fixture -d upgrade_fixture --no-owner > release-artifacts/postgres-upgrade-fixture.sql
docker exec -i "$new" psql -U upgrade_fixture -d upgrade_fixture -v ON_ERROR_STOP=1 < release-artifacts/postgres-upgrade-fixture.sql
docker exec "$old" psql -U upgrade_fixture -d upgrade_fixture -Atc 'SELECT row_to_json(t) FROM upgrade_probe t ORDER BY id' > release-artifacts/postgres-upgrade-before.txt
docker exec "$new" psql -U upgrade_fixture -d upgrade_fixture -Atc 'SELECT row_to_json(t) FROM upgrade_probe t ORDER BY id' > release-artifacts/postgres-upgrade-after.txt
cmp release-artifacts/postgres-upgrade-before.txt release-artifacts/postgres-upgrade-after.txt
printf 'PostgreSQL 16 bookworm -> trixie logical restore: data and rebuilt unique indexes PASS. Physical-volume reuse was not tested or authorized.\n' > release-artifacts/postgres-upgrade-result.txt
