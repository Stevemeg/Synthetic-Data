# Artifact storage

The existing `ArtifactStore` interface now supports LocalArtifactStore and S3ArtifactStore. Local storage remains for tests/lightweight development. Production requires S3-compatible storage; local storage is rejected. AWS-style credential providers work when explicit keys are absent. Configure `S3_BUCKET`, `S3_REGION`, optional `S3_ENDPOINT`, paired `S3_ACCESS_KEY`/`S3_SECRET_KEY`, and optional `S3_SERVER_SIDE_ENCRYPTION=AES256` or `aws:kms`.

Object keys are platform-generated project/dataset/job/evaluation identifiers, never raw upload filenames. Canonical key checks reject traversal. Writes use conditional PutObject (`IfNoneMatch=*`) to preserve immutable publication. Bytes are spooled to temporary files rather than retained entirely in RAM. SHA-256 and size are calculated from bytes; ETag is not the platform integrity hash. Critical reads and controlled downloads verify registered digests.

Downloads are streamed through registered artifact IDs only, after tenant/role authorization. There are no public report links or pre-signed URLs. Content-Disposition filenames are sanitized. Model downloads remain restricted. Source storage is private and has no patient preview endpoint. Keep buckets private and enforce least-privilege application credentials; development MinIO root keys are not a production recommendation.

Local MinIO is built from upstream `RELEASE.2025-10-15T17-29-55Z` as a conformance fixture. Its community repository is archived. The old published image could not be fetched, and an older security release should not be represented as supported production storage. Choose a maintained S3-compatible service for deployment and review its licensing/patch lifecycle.

Existing local artifacts can be copied during an offline maintenance window:

```sh
python -m backend.scripts.migrate_artifacts_to_s3 --maintenance-window
```

The script verifies local and remote size/SHA before updating each registered storage reference, writes rollback mappings under ignored `backend/.work/storage-migration.jsonl`, retains local originals, and safely skips completed mappings on repetition. Stop API/workers first; back up PostgreSQL and objects. After all references migrate, switch the configured backend to S3. Do not run local-only services against migrated references. Rollback requires restoring reference mappings/backup and selecting local storage; do not overwrite trusted immutable objects.

Encryption at rest is a storage-provider responsibility unless the S3 encryption option is configured and verified. No end-to-end encryption claim is made. Object versioning, replicas, lifecycle rules and backups need separate administration.

Migration excludes deletion tombstones: retained backup bytes must never republish
a deleted project. Restoring a backup requires replaying deletion tombstones and
checking provider versions/replicas before reopening access. Authorized downloads
return the exact spooled bytes verified once, avoiding a second-object retrieval
between integrity checking and streaming.
