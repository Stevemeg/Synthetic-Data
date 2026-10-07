# ADR-0017: Private S3-compatible storage behind the existing interface

Accepted, Phase 6. Local storage remains available for tests and lightweight
development. Production requires S3-compatible storage with maintained boto3,
credential-provider support and optional provider server-side encryption.
Generated canonical keys and conditional writes prevent accidental overwrite.
The application hashes bytes with SHA-256; ETags are not integrity evidence.
Authorized API downloads spool and verify bytes before returning attachments.
No public buckets, public report URLs or presigned URLs are created.

Offline migration copies registered local objects, verifies both digests,
flushes/fsyncs rollback information and then updates the locked reference.
Originals remain until the operator separately removes them. A source-built
archived MinIO release is a local conformance fixture only; deployments must
select a maintained storage provider. Readiness checks required bucket access.
