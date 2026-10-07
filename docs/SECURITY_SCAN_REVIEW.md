# Security scan disposition

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
