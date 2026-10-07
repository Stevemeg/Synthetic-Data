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

### Individual closure dispositions

The next closure run must validate the following **individual, configuration-scoped
reviews**. They supersede the earlier pending-review rows only if its required
runtime, authentication, tenant, storage, model and scan jobs pass. There are
41 image/CVE reviews representing 25 distinct CVEs. Exact installed versions,
CVSS, package membership, scanner fixed versions and individual rationale are
retained in `ops/container_dispositions.json` and the CI normalized inventory;
the raw scanner findings remain unchanged. Review date: **2026-11-06**, or
immediately after a package, service configuration or exposure change.

| CVE | Package | Image | Compatible fix reported | Disposition | Evidence and scope |
| --- | --- | --- | --- | --- | --- |
| CVE-2025-69720 | ncurses | API, worker, PostgreSQL | No | NOT_REACHABLE | infocmp remains installed; no invocation/attacker terminfo path in app, worker, server or supplied startup |
| CVE-2026-16742 | systemd libraries | API, worker, PostgreSQL | No | NOT_PRESENT | vulnerable systemd-homed executable/service absent; shared libraries remain |
| CVE-2026-54369 | libacl1 | API, worker, PostgreSQL | No | MITIGATED | non-root workloads; trusted startup paths; no privileged tenant ACL call; backend read-only roots |
| CVE-2026-76642 | util-linux | API, worker, PostgreSQL | No | MITIGATED | no SYS_ADMIN, relevant fstab authorization or app mount invocation; no-new-privileges |
| CVE-2026-78408 | util-linux | API, worker, PostgreSQL | No | MITIGATED | nsenter option present; no privileged cgroup/root descriptors, host authority or invocation |
| CVE-2026-78409 | util-linux | API, worker, PostgreSQL | No | MITIGATED | no authorized X-mount.subdir configuration/host mount authority |
| CVE-2026-78410 | util-linux | API, worker, PostgreSQL | No | MITIGATED | no authorized restricted bind mounts; non-root and no-new-privileges |
| CVE-2026-9538 | perl-base | API, worker | No | NOT_PRESENT | Archive::Tar module load and filesystem absence probes |
| CVE-2026-9538 | full Perl | PostgreSQL | No | NOT_REACHABLE | Archive::Tar present; app/cluster startup does not process untrusted archives through Perl |
| CVE-2026-6653 | libxml2 | PostgreSQL | No | NOT_REACHABLE | SQL/XML retained; no XML columns, XML query/cast or arbitrary SQL endpoint in MedSynth |
| CVE-2026-74860 | libxml2 | PostgreSQL | No | NOT_PRESENT | vulnerable Python SAX binding is absent; native library remains |
| CVE-2026-86138 | libxml2 | PostgreSQL | No | NOT_REACHABLE | no XML qualified-name dictionary input from the application |
| CVE-2026-86139 | libxml2 | PostgreSQL | No | NOT_REACHABLE | no XML URI escaping call/input from the application |
| CVE-2026-86140 | libxml2 | PostgreSQL | No | NOT_REACHABLE | no DTD formatting or validation workflow |
| CVE-2026-86142 | libxml2 | PostgreSQL | No | NOT_REACHABLE | no XPointer evaluation workflow |
| CVE-2026-86143 | libxml2 | PostgreSQL | No | NOT_REACHABLE | report output uses Python HTML/JSON, not libxml2 XML callbacks |
| CVE-2026-86144 | libxml2 | PostgreSQL | No | NOT_REACHABLE | no XInclude workflow/resource loader |
| CVE-2026-103111 | pcre2/pcre2-syntax | Keycloak | No vendor patch reported | NOT_REACHABLE | no attacker-selected native JIT patterns; Java PID PCRE mapping checked after auth |
| CVE-2026-86145 | pcre2/pcre2-syntax | Keycloak | No vendor patch reported | NOT_REACHABLE | no native DFA matching caller; constant shell health pattern |
| CVE-2026-89161 | pcre2/pcre2-syntax | Keycloak | No vendor patch reported | NOT_REACHABLE | no native PCRE2 JIT subject/context caller in supplied auth flow |
| CVE-2026-33322 | github.com/minio/minio | MinIO | AIStor fix; no compatible CE release | NOT_REACHABLE | fresh supplied fixture has no MinIO OIDC provider/client secret; negative STS probe |
| CVE-2026-33419 | github.com/minio/minio | MinIO | AIStor fix; no compatible CE release | NOT_REACHABLE | no MinIO LDAP server/provider; negative STS probe |
| CVE-2026-34204 | github.com/minio/minio | MinIO | AIStor fix; no compatible CE release | MITIGATED | trusted-only raw storage credentials; app sends fixed sha256 metadata, no replication-header forwarding |
| CVE-2026-39414 | github.com/minio/minio | MinIO | AIStor fix; no compatible CE release | MITIGATED | app never calls/proxies S3 Select; raw storage credential holders limited to trusted processes/operators |
| CVE-2026-40344 | github.com/minio/minio | MinIO | AIStor fix; no compatible CE release | MITIGATED | loopback-only fixture; generated unpublished access keys; no tenant Snowball/header proxy |
| CVE-2026-41145 | github.com/minio/minio | MinIO | AIStor fix; no compatible CE release | MITIGATED | loopback-only fixture; generated unpublished access keys; SDK-generated storage requests, no query/header proxy |

NOT_PRESENT above refers to the **affected component**, not absence of the whole
source package. NOT_REACHABLE is limited to the supplied MedSynth application
and fresh fixture configuration. In particular, a trusted PostgreSQL operator
can still issue SQL/XML; enabling arbitrary SQL/XML for untrusted clients would
invalidate the XML dispositions. Adding native PCRE callers invalidates the
Keycloak review. Enabling MinIO OIDC/LDAP, reusing externally configured MinIO
state, publishing its ports or distributing storage keys invalidates its review.

MITIGATED findings remain vulnerable. The MinIO access key is high-entropy,
generated locally and confined to API/worker/operator configuration. Private
buckets alone do not mitigate its signature-bypass vulnerabilities. Application
tenants receive neither raw S3 credentials nor a generic storage request/header
proxy. Direct trusted operator requests retain residual risk. These controls
substantially limit the **development conformance fixture**; they do not approve
the archived community service for public/shared production deployment.
Upstream's [Snowball advisory](https://github.com/minio/minio/security/advisories/GHSA-9c4q-hq6p-c237)
and [unsigned-trailer advisory](https://github.com/minio/minio/security/advisories/GHSA-hv4r-mvr4-25vw)
state that all community releases are affected. The [S3 Select advisory](https://github.com/minio/minio/security/advisories/GHSA-h749-fxx7-pwpg)
and [metadata-injection advisory](https://github.com/minio/minio/security/advisories/GHSA-3rh2-v3gr-35p9)
also identify AIStor fixes. Adopting a separately licensed product/credential
requirement is not a compatible automatic update of this generated-credential
fixture. No ACCEPTED_NO_FIX approval or blanket exception was introduced.

`ops/inspect_backend_runtime.sh` inspects both exact application images under
read-only roots, dropped capabilities and no-new-privileges, asserts absence
of the two affected components, and runs the existing one-epoch CPU strategy
for Gaussian Copula/CTGAN/TVAE with fit/sample/checksum/save/reload. The OIDC
job runs all four S3 smokes **inside the final worker image**, checks the actual
service scope after authenticated tests, and then scans/SBOMs the very image IDs
it exercised. The security job independently executes pip-audit, npm audit,
Bandit, gitleaks, six full scans, six SBOMs and individual review validation.
No conditional security skip or unfixed exclusion is used.

The completed remediation scan in run
[37578284043](https://github.com/Stevemeg/Synthetic-Data/actions/runs/37578284043)
at commit `aac7c5830f21d3f842b781830bf5591160fc05a6` found API/worker each
0 Critical/44 High, frontend zero, PostgreSQL 1 Critical/54 High,
Keycloak 0 Critical/6 High and MinIO 2 Critical/4 High. All six builds and SBOMs
succeeded; its empty review file correctly failed the security gate. That is
preserved failed evidence, not final release approval. The new required run
must validate these reviews and the final container/control changes anew.

The PostgreSQL distribution refresh changes libc/collation inputs. Existing
physical volumes have not been recreated/upgraded locally. Before adopting
trixie for an existing bookworm deployment, take a verified logical backup and
restore into a new volume so indexes are rebuilt under the new collation
implementation; verify the actual deployment's data and rollback procedure.
`ops/verify_postgres_upgrade.sh` checks this path using disposable, network-isolated
PostgreSQL 16 instances and invented Unicode/indexed/JSON data. This is stronger
than testing only a fresh cluster; it is not proof that arbitrary old physical
volumes can be mounted without collation maintenance.

Distribution compatibility is part of fix availability. Debian's
[ACL advisory](https://security-tracker.debian.org/tracker/CVE-2026-54369)
reports stable packages still affected, new acl_*_at ABI/export compatibility
problems with existing tar, and a future point-release update rather than
individual backports. The [ncurses advisory](https://security-tracker.debian.org/tracker/CVE-2025-69720),
[systemd advisory](https://security-tracker.debian.org/tracker/CVE-2026-16742)
and [libxml2 advisory](https://security-tracker.debian.org/tracker/CVE-2026-6653)
also retain affected stable-package states despite newer upstream/unstable
fixes. These are not "not vulnerable" states. Stable vendor refreshes were
tried; mixing unstable system libraries into scientific/vendor images without
established compatibility is not the chosen remediation. Re-review when
compatible vendor packages arrive. Digest maintenance remains enabled for
both `/ops` and `/ops/minio`; Go module fixes require reviewed recipe updates
and the same compile/runtime/scan gates.

Run 37580240762 exposed a verification-command bug: its first read-only
backend inspection omitted the writable `/tmp` tmpfs used by the real runtime,
so SciPy import failed with "No usable temporary directory". The inspection
now supplies the same restricted temporary mount as production Compose.
Root read-only/non-root/capability restrictions were preserved. Smoke CLI
processes also run in disposable instances of the final worker image, so their
metrics listener cannot collide with the persistent worker. Failed/incorrect
verification attempts do not count as final passes.
