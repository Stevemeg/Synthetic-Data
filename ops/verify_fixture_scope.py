"""Record sanitized runtime evidence for the supplied local-only service scope."""

import json
import subprocess
from pathlib import Path

import httpx

COMPOSE = [
    "docker",
    "compose",
    "-p",
    "synthetic-data",
    "-f",
    "compose.yaml",
    "-f",
    "compose.security.yaml",
    "-f",
    "compose.runtime.yaml",
]


def capture(*arguments):
    return subprocess.check_output([*COMPOSE, *arguments], text=True)


def main():
    evidence = {}
    for service in ("api", "worker", "frontend", "postgres", "keycloak", "minio"):
        identifier = capture("ps", "-q", service).strip()
        info = json.loads(subprocess.check_output(["docker", "inspect", identifier], text=True))[0]
        environment = info["Config"].get("Env", [])
        identity_names = [
            v.split("=", 1)[0]
            for v in environment
            if v.startswith(("MINIO_IDENTITY_OPENID_", "MINIO_IDENTITY_LDAP_"))
        ]
        if service == "minio":
            assert not identity_names, "MinIO identity configuration changes invalidate this review"
        ports = info["HostConfig"].get("PortBindings") or {}
        assert all(p["HostIp"] == "127.0.0.1" for binding in ports.values() for p in binding)
        evidence[service] = {
            "image_id": info["Image"],
            "image_user": info["Config"].get("User"),
            "cap_drop": info["HostConfig"].get("CapDrop"),
            "security_opt": info["HostConfig"].get("SecurityOpt"),
            "read_only": info["HostConfig"].get("ReadonlyRootfs"),
            "all_published_ports_loopback": True,
            "process_status": capture(
                "exec",
                "-T",
                service,
                "sh",
                "-c",
                "grep -E '^(Uid|Gid|CapEff|NoNewPrivs):' /proc/1/status",
            )
            if service != "keycloak"
            else capture(
                "exec",
                "-T",
                service,
                "/bin/bash",
                "-c",
                "grep -E '^(Uid|Gid|CapEff|NoNewPrivs):' /proc/1/status",
            ),
        }
    maps = capture("exec", "-T", "keycloak", "/bin/bash", "-c", "cat /proc/1/maps")
    for service, status in evidence.items():
        fields = dict(line.split(":", 1) for line in status["process_status"].splitlines())
        assert all(int(uid) != 0 for uid in fields["Uid"].split()), f"{service}: root workload"
        assert int(fields["CapEff"].strip(), 16) == 0, f"{service}: effective capabilities"
        assert fields["NoNewPrivs"].strip() == "1", f"{service}: privilege elevation allowed"
    assert "pcre" not in maps.lower(), "Keycloak native PCRE reachability review changed"
    evidence["keycloak"]["java_pcre_mapped_after_auth_tests"] = False
    schema_xml = capture(
        "exec",
        "-T",
        "postgres",
        "sh",
        "-c",
        'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT count(*) FROM information_schema.columns WHERE table_schema=\'public\' AND data_type=\'xml\'"',
    )
    assert schema_xml.strip() == "0", "Application schema now uses XML"
    evidence["postgres"]["application_xml_columns"] = 0
    absent = capture(
        "exec",
        "-T",
        "postgres",
        "sh",
        "-ec",
        'if command -v systemd-homed; then exit 1; fi; if find /usr -name "libxml2mod*" -o -name systemd-homed | grep .; then exit 1; fi; echo "systemd-homed and libxml2 Python bindings absent"',
    )
    evidence["postgres"]["absent_components"] = absent.strip()
    evidence["minio"]["identity_environment_names"] = []
    evidence["minio"]["sts_probes"] = []
    for action, parameters in (
        ("AssumeRoleWithWebIdentity", {"WebIdentityToken": "invalid-fixture-token"}),
        (
            "AssumeRoleWithLDAPIdentity",
            {"LDAPUsername": "invalid-fixture-user", "LDAPPassword": "invalid-fixture-password"},
        ),
    ):
        response = httpx.post(
            "http://127.0.0.1:9000/",
            data={"Action": action, "Version": "2011-06-15", **parameters},
            timeout=10,
        )
        assert response.status_code == 400 and "<Credentials>" not in response.text
        evidence["minio"]["sts_probes"].append(
            {"action": action, "status": response.status_code, "credentials_issued": False}
        )
    output = Path("release-artifacts/fixture-runtime.json")
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print("Verified supplied loopback fixture scope; no credential values recorded.")


if __name__ == "__main__":
    main()
