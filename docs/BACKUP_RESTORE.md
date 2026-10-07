# PostgreSQL and object backup/restore

Back up PostgreSQL using `pg_dump -Fc --no-owner --no-acl`, retaining the migration revision and build identity. Store backups encrypted and access-controlled according to your organization policy. Restore into a new database with `pg_restore --exit-on-error`, then verify counts, tenant relationships, memberships, reports and audit history before switching application configuration.

The development round-trip helper uses binary subprocess pipes, not PowerShell text redirection:

```sh
python -m backend.scripts.backup_restore_test --verify-storage
```

It creates a random disposable database, compares projects/datasets/jobs/evaluations/policies/artifacts/users/organizations/memberships/audit counts, and removes only that disposable database. The ignored dump/result is under `backend/.work/backup-restore`. This was actually run against PostgreSQL 16.15 with generated development records; results are in Phase 6 verification. Never restore over the live database to rehearse recovery.

Database backups do not include artifact objects or IdP state. Back up objects and provider configuration separately, retaining object hashes and versions. Before reopening restored metadata, verify referenced bytes and replay deletion tombstones against storage. A deleted object may exist in a backup/version; restoring bytes does not authorize undeleting its project.

Recovery rehearsal should verify a report download digest from the restored metadata while the corresponding object backup is available. No proven RTO/RPO or disaster recovery guarantee is asserted. Establish operational goals through your own measured rehearsals.

The final local rehearsal restored all ten table counts unchanged: 47 projects, 39 datasets, 71 generation jobs, 24 evaluations, 15 policies, 310 artifacts, 2 organizations, 3 memberships, 2 users and 952 audit events. The 428,796-byte PostgreSQL backup was restored into a new disposable database; all 349 active source/artifact references matched private S3 object sizes and SHA-256 hashes. This validates metadata restoration against existing test objects, not recovery of a destroyed object store or identity provider. The disposable database was removed after verification.
