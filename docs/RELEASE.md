# Release engineering

The root `VERSION` is the default application version source (currently 0.6.0). API/manifests/reports use the configured build version and commit. An environment override must match the release being built. A version number is not evidence that all release criteria passed; see the verification document.

Before tagging: run Python unit/model/PostgreSQL tests, Ruff/format/compileall/pip check, clean/populated Alembic migrations and drift checks, frontend install/unit/type/lint/build/audit, real-browser product/OIDC/tenant checks, visual/accessibility/responsive checks, S3 workflow/migration/deletion, backup/restore, smoke/recovery tests and security scans. Review every remaining finding and unverified gate explicitly.

Build all images without development secrets; record digests/commit/build timestamp and generate an SBOM as a CI artifact. Rehearse deployment with private fake data and production-like containers. Compare readiness, artifact digests and scoped memberships after restart.

For rollout: back up metadata and objects, stop incompatible worker versions, migrate once, verify head/readiness, deploy API/static frontend/workers, then run an authenticated fake-data smoke. Never automate destructive production deployment without a specific authorized target. Rollback may require database/reference restoration plus deletion-tombstone replay; do not automatically downgrade populated identity data.

Recommended GitHub settings: require quality/security CI and pull-request review, restrict direct main-branch writes and force pushes, and retain release artifacts. These are recommendations; repository branch settings have not been changed by this implementation. Dependency updates should be weekly/grouped and reviewed, especially model-runtime changes. Do not automatically merge major upgrades.

Current release disposition: local engineering verification passed; remote CI execution and explicit review of unfixed High container advisories remain pending. Do not tag a release candidate from local scanner exit codes alone. See [scanner disposition](SECURITY_SCAN_REVIEW.md). The private frontend package has no independent product version; root VERSION remains the default release identity.
