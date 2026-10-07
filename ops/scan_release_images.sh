#!/usr/bin/env bash
set -euo pipefail
mkdir -p release-artifacts
images=(
  'api=medsynth-api:ci'
  'worker=medsynth-worker:ci'
  'frontend=medsynth-frontend:ci'
  'postgres=medsynth-postgres-development:16'
  'keycloak=quay.io/keycloak/keycloak:26.8.0@sha256:b0f60d489d51c5d113390bdf5461d4c06e6051be026c05549f2e1e10ec352bcc'
  'minio=medsynth-minio-development:7aac2a2'
)
scanner=(docker run --rm -v /var/run/docker.sock:/var/run/docker.sock
  -v "$PWD/release-artifacts:/out" -v medsynth-trivy-cache:/root/.cache/trivy aquasec/trivy:0.75.0)
for pair in "${images[@]}"; do
  name=${pair%%=*}
  image=${pair#*=}
  docker image inspect "$image" > "release-artifacts/$name-image.json"
  "${scanner[@]}" image --scanners vuln --format json --output "/out/$name-vulnerabilities.json" "$image"
  "${scanner[@]}" image --format cyclonedx --output "/out/$name-sbom.json" "$image"
done
"${scanner[@]}" version --format json > release-artifacts/scanner-version.json
docker run --rm --entrypoint minio medsynth-minio-development:7aac2a2 --version > release-artifacts/minio-version.txt
python3 ops/review_container_findings.py release-artifacts --inventory-only
