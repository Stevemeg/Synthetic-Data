# Security scan disposition

**Phase 6 remains incomplete.** The sections below headed "Local scans on
2026-10-05" describe the original review. The closure review at the end records
new evidence and supersedes its statements about remote CI and scan scope.

Local scans on 2026-10-05 are evidence about the scanned build and advisory database, not a penetration test or proof of security. Full JSON and the CycloneDX SBOM are retained under ignored `backend/.work`; CI publishes corresponding review artifacts. No scan report containing environment secrets is committed.

## Application dependency checks

`pip-audit`: no known advisories after upgrading Pillow, pip, pytest, requests, setuptools and CPU PyTorch. `npm audit --audit-level=low`: zero findings. Bandit: zero findings after narrow documented annotations; warnings about redundant `nosec` annotations are disclosed. Gitleaks found no secrets in repository history and the exported nonignored working tree.

Initial host Python scanning found 63 advisories across six packages. Initial API image scanning found five Critical OS findings and Python findings. Available distribution upgrades, Debian trixie, CPU-only runtime dependencies and removal of unnecessary runtime pip/global setuptools eliminated the fixable findings. This does not eliminate the remaining advisories below.

## Container findings

Trivy 0.75.0, full vulnerability scan without `--ignore-unfixed`:

| Image | Critical | High | Medium | Low | Unknown | Fix available | Python findings |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| api | 0 | 44 | 59 | 61 | 2 | 0 | 0 |
| worker | 0 | 44 | 59 | 61 | 2 | 0 | 0 |
| frontend | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

API and worker share the same base packages. Their 44 High package findings correspond to eight distinct CVEs, not 44 distinct CVEs:

| Advisory | Affected installed packages | Current disposition |
| --- | --- | --- |
| CVE-2025-69720 | libncursesw6, libtinfo6, ncurses-base, ncurses-bin | No fix reported in this scan; release risk review pending |
| CVE-2026-16742 | libsystemd0, libudev1 | No fix reported in this scan; release risk review pending |
| CVE-2026-54369 | libacl1 | No fix reported in this scan; release risk review pending |
| CVE-2026-76642 | bsdutils, libblkid1, liblastlog2-2, libmount1, libsmartcols1, libuuid1, login, mount, util-linux | No fix reported in this scan; release risk review pending |
| CVE-2026-78408 | bsdutils, libblkid1, liblastlog2-2, libmount1, libsmartcols1, libuuid1, login, mount, util-linux | No fix reported in this scan; release risk review pending |
| CVE-2026-78409 | bsdutils, libblkid1, liblastlog2-2, libmount1, libsmartcols1, libuuid1, login, mount, util-linux | No fix reported in this scan; release risk review pending |
| CVE-2026-78410 | bsdutils, libblkid1, liblastlog2-2, libmount1, libsmartcols1, libuuid1, login, mount, util-linux | No fix reported in this scan; release risk review pending |
| CVE-2026-9538 | perl-base | No fix reported in this scan; release risk review pending |

Non-root users, dropped capabilities, read-only backend roots, restricted network exposure, private object storage and immutable images limit some attack surfaces. These controls are not proof that each CVE is unreachable. Reachability/exploitability of all eight advisories has not been established. The absence of a reported fix is not risk acceptance. Rebuild/rescan as distribution updates become available; an operator/security review must explicitly dispose of remaining risks before release approval. No blanket CVE suppression or VEX assertion was added.

The locally executed CI-style gate for **fixable** High/Critical advisories passes; the full scan still reports the table above. This distinction is intentional. Supporting PostgreSQL, Keycloak and development MinIO images were not container-scanned in this run. The archived community MinIO source build is a protocol test fixture, not a production recommendation; use maintained services and scan them for the chosen deployment.

## Release status

Remote GitHub Actions execution is unverified. The workflow passes local actionlint syntax checking and corresponding local engineering checks, but that is not a green remote pipeline. Release-candidate designation is withheld pending remote CI and explicit disposition of remaining container findings. See [Phase 6 verification](PHASE_6_VERIFICATION.md).

## Closure review — 2026-10-07

### Scan scope

API, worker, frontend, PostgreSQL 16, Keycloak 26.8.0 and the repository-built
development MinIO fixture were scanned. No other proxy/service is shipped;
nginx is included in the frontend image. These are baseline scans, **not final
scans of the remediation recipes**. Supporting services no longer have an
unexamined scope exclusion.

### Scanner and findings summary

Trivy 0.75.0, vulnerability DB schema 2 updated
2026-10-07T00:53:05.111120428Z; Java DB schema 1 updated
2026-10-07T01:10:24.784068105Z. Scans ran 2026-10-07 without unfixed exclusions.
Raw JSON, image inspections, runtime probes and logs are retained locally in
ignored `backend/.work/phase6-closure/`. The normalized starting inventory is
`docs/security/closure-baseline-inventory.csv`; unknown reachability is explicitly
marked for review, never inferred from a missing fixed version.

| Starting image | Critical | High | Medium | Low | Unknown |
| --- | ---: | ---: | ---: | ---: | ---: |
| API | 0 | 44 | 58 | 61 | 2 |
| Worker | 0 | 44 | 58 | 61 | 2 |
| Frontend | 0 | 0 | 0 | 0 | 0 |
| PostgreSQL | 16 | 101 | 211 | 174 | 6 |
| Keycloak | 0 | 6 | 47 | 29 | 0 |
| MinIO | 10 | 105 | 149 | 126 | 4 |

API image ID: `sha256:765d15edd0effdbde100a9660cf56b2e9845cf728a2a379e6f0e9b981caba4c1`.
Worker image ID: `sha256:d0b946daa3eb39dae15849c510b2c287d4cbaef48677689f8c5d7e3135936307`.
Frontend image ID: `sha256:2c39c11658af4b92c100b024665d825af5695692e7b1a45ad1e9cc8cff0d459b`.
These are the IDs returned by local Docker inspection, not published release
images. Service IDs and repo digests are recorded individually in the inventory.

### Distinct API/worker High CVEs — evidence and outstanding validation

All packages below are inherited Debian 13 runtime packages, not pip packages.
No stable compatible fixed version was reported by these scans. The same CVE
appearing against several binaries/source-package members is counted once per
image in the inventory. Replacing trixie with an unsupported distribution or
deleting scientific/native runtime libraries is not justified.

| CVE | Package | Image | Fix | Runtime relevance and evidence | Current release disposition |
| --- | --- | --- | --- | --- | --- |
| CVE-2025-69720 | ncurses 6.5+20250216-2 | API, worker | No trixie fix reported | `infocmp` is present. Application source has no invocation or terminfo input path. The issue requires processing attacker-provided terminfo with the vulnerable utility. | BLOCKING pending final-image reachability validation |
| CVE-2026-16742 | libsystemd0/libudev1 257.13-1~deb13u1 | API, worker | No trixie fix reported | Vulnerable `systemd-homed` executable/service is absent in the inspected runtime; installed shared libraries are distinct from that service. | BLOCKING pending final-image absence validation |
| CVE-2026-54369 | libacl1 2.3.2-2+b1 | API, worker | No stable ABI-compatible fix reported | ACL pathname/symlink behavior requires a relevant privileged caller. Native scientific imports did not map libacl; no app ACL invocation was found. | BLOCKING pending final-image/control validation |
| CVE-2026-76642 | util-linux 1:2.41.5-0+deb13u1 | API, worker | No trixie fix reported | Mount-helper privilege flow; runtime has UID 10001, no capabilities, no privilege escalation and no configured fstab mounts. | BLOCKING pending final-image/control validation |
| CVE-2026-78408 | util-linux, same version | API, worker | No trixie fix reported | `nsenter --join-cgroup` is present. No app invocation, root/cgroup authority or host namespace access is configured. Its option must not be reported absent. | BLOCKING pending final-image/control validation |
| CVE-2026-78409 | util-linux, same version | API, worker | No trixie fix reported | X-mount.subdir symlink handling requires mount authorization; supplied containers lack SYS_ADMIN/fstab authorization. | BLOCKING pending final-image/control validation |
| CVE-2026-78410 | util-linux, same version | API, worker | No trixie fix reported | Restricted bind mount TOCTOU requires relevant mount authority/attacker-controlled paths; the supplied containers lack that authority. | BLOCKING pending final-image/control validation |
| CVE-2026-9538 | perl-base 5.40.1-6+deb13u1 | API, worker | No trixie fix reported | `perl -MArchive::Tar` failed and no `Archive/Tar.pm` was found. This is component-absence evidence, not a claim that all Perl is safe. | BLOCKING pending final-image absence validation |

Evidence: `baseline-runtime-inspection.log` records UID 10001, Debian 13.7,
exact package versions, executable/module checks, fstab and `/proc/self/maps`
after torch/numpy/scipy/psycopg/SDV/Pillow imports. Source searches found only
static provenance-git subprocess use, not calls to the vulnerable utilities.
The inspection supports possible NOT_PRESENT, NOT_REACHABLE or MITIGATED
dispositions; it does not approve an untested final image. Upstream states are
available in the individual [Debian security tracker](https://security-tracker.debian.org/tracker/)
entries keyed by the CVEs above. A `will_not_fix`/`affected` state is retained as
vulnerable unless the relevant function's absence or reachability is proven.

### Supporting image remediation attempts

Refreshing PostgreSQL 16-bookworm reduced findings to 4 Critical/84 High but
retained fixable Go vulnerabilities in its gosu binary. A 16-alpine trial still
had 1 Critical/21 High in that helper. A 16-trixie vendor trial had
2 Critical/82 High. The closure recipe keeps PostgreSQL 16, rebuilds the same
gosu 1.19 source using Go 1.26.8, and removes seven repository-key import tools
confirmed build-only by an apt purge simulation. The earlier bookworm helper
rebuild compiled and executed `gosu postgres id`; the final trixie recipe still
requires scan, initialization and backup/restore compatibility verification.
Existing local database volumes have not been upgraded by this attempt.

Keycloak's refreshed maintained 26.8.0 vendor image still has six High package
findings, three distinct CVEs: CVE-2026-103111, CVE-2026-86145 and
CVE-2026-89161 (pcre2/pcre2-syntax 10.40-6.el9). Java's inspected memory maps
did not include PCRE. The health probe uses a constant HTTP-status pattern.
This narrows reachability investigation but is not final approval; each remains
BLOCKING pending an individual final-image review. No vendor image was blindly
patched internally.

The MinIO community repository is archived. The recipe pins its final source
revision `7aac2a2c5b7c882e68c1ce017d8256be2feea27f` and attempts targeted updates
to fixable Go modules using the upstream Go module resolver. Neither compilation
nor source ancestry alone proves resolution of MinIO's own vulnerabilities.
The starting release's CVE-2026-33322, CVE-2026-33419, CVE-2026-34204,
CVE-2026-39414, CVE-2026-40344 and CVE-2026-41145 must remain in manual review
even if a rebuilt Go binary identifies its main module as `(devel)`. OIDC/LDAP
are not configured on this fixture (application OIDC uses Keycloak separately),
but that observation cannot approve arbitrary storage-service exposure. See the
[upstream MinIO advisories](https://github.com/minio/minio/security/advisories).
The fixture is bound to loopback and uses generated credentials/private buckets;
it remains a development conformance service, not a production recommendation.

The pre-change backup/restore check passed: 55 projects, 45 datasets,
85 generation jobs, 30 evaluations, 376 artifacts, 421 active S3 references,
and a 617,962-byte backup. This verifies the old deployment, not the new recipe.

### Accepted risk and release gate

No risk acceptance was invented. No CVE is suppressed. Unreviewed High/Critical
findings currently have disposition **BLOCKING**. Their package/version/fix data
are individually preserved in the normalized inventory. The review file
`ops/container_dispositions.json` is deliberately empty until final evidence is
available. `ops/review_container_findings.py` requires matching image/CVE/package
versions, rationale, evidence, runtime analysis and review date; changed or new
findings fail closed. Compatible fixable High findings must be fixed, and
unresolved Critical findings cannot pass. This permits specific evidenced
dispositions rather than requiring zero High findings.

### CI, reproducibility and SBOM

Actual remote run [37575669077](https://github.com/Stevemeg/Synthetic-Data/actions/runs/37575669077)
tested commit `aaa5327d66efb59b06c2a01b15d6c7f4fd58c81a` on branch
`phase6-closure`: backend, frontend and the original API-only security job
passed; OIDC/storage/browser failed before its tests because Keycloak was not
ready. This is a failed remote run, not release verification. The closure
workflow adds health-based waits, fixes the integration-marker selector and
expands JSON scans and CycloneDX SBOMs to all six runtime images. It retains
contents:read permissions and generated/fake CI credentials; no production
secret is required. All final steps must actually run and pass for one exact
release commit. Final image inspections, DB version, SBOMs and normalized
findings are uploaded as the `supply-chain-review` artifact even when review
fails. Dockerfile/service digest pins preserve upstream inputs; apt/apk/Go
dependency resolution means built image IDs still must be recorded per run.

Local rebuilding exhausted the C: filesystem and Docker reported read-only
storage/daemon EOF. These are failed attempts, not final build/scan evidence.
Final rescans, runtime checks, SBOMs and full post-change regression are pending.

### Limitations

This review is not penetration testing, clinical validation or HIPAA/GDPR
certification. Scanner databases and vendor states can change. Local MinIO and
Keycloak fixtures do not certify an external production service. The exact
deployment controls and vendor support status must accompany any future risk
acceptance. Phase 6 remains **NOT COMPLETE** until all release gates pass.
