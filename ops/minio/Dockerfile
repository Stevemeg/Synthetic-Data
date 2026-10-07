# Development S3 conformance fixture, built from pinned archived upstream source.
# MinIO's community repository is archived; select maintained storage for deployment.
FROM golang:1.26-bookworm@sha256:dc9ad6c05acc7a88e5b71bde60a5fe3bd4b9f0db209011711b464107438a8107 AS build
ENV CGO_ENABLED=0 GOTOOLCHAIN=local
# Last archived upstream revision. Source ancestry is not proof of CVE resolution;
# keep the old release's MinIO advisories in the review even if Go reports (devel).
RUN git init /src && git -C /src fetch --depth=1 https://github.com/minio/minio.git 7aac2a2c5b7c882e68c1ce017d8256be2feea27f && git -C /src checkout --detach FETCH_HEAD
WORKDIR /src
# Target the modules with compatible security releases; compilation and real S3
# regression gates must pass before this fixture can be accepted.
RUN go get github.com/apache/thrift@v0.24.0 github.com/buger/jsonparser@v1.1.2 github.com/go-jose/go-jose/v4@v4.1.4 github.com/prometheus/prometheus@v0.311.3 github.com/rabbitmq/amqp091-go@v1.13.0 golang.org/x/crypto@v0.55.0 google.golang.org/grpc@v1.83.2 && go build -mod=mod -trimpath -buildvcs=true -o /minio . && go list -m all > /go-dependency-manifest.txt
FROM alpine:3.24@sha256:294b683cb724975bec92580e1e685676bd4b50bda910ddb8c51d4cabeaec77e6
RUN apk add --no-cache ca-certificates curl && addgroup -g 10001 minio && adduser -D -u 10001 -G minio minio && mkdir /data && chown minio:minio /data
COPY --from=build /minio /usr/local/bin/minio
USER 10001:10001
EXPOSE 9000
ENTRYPOINT ["minio"]
