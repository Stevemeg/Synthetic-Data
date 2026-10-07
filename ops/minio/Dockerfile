# Development S3 conformance fixture, built from the upstream security release.
# MinIO's community repository is archived; select maintained storage for deployment.
FROM golang:1.26-bookworm AS build
RUN CGO_ENABLED=0 go install github.com/minio/minio@RELEASE.2025-10-15T17-29-55Z
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl && rm -rf /var/lib/apt/lists/* && useradd --uid 10001 --create-home minio && mkdir /data && chown minio /data
COPY --from=build /go/bin/minio /usr/local/bin/minio
USER 10001:10001
EXPOSE 9000
ENTRYPOINT ["minio"]
