"""Configure fake local identities and a private development bucket. Never production."""

import os
import secrets
from pathlib import Path

import boto3
import httpx
from dotenv import dotenv_values

from backend.app.config import ROOT


def main():
    values = {**dotenv_values(ROOT / ".env"), **os.environ}
    if values.get("APP_ENV", "development") != "development":
        raise SystemExit("This bootstrap only supports APP_ENV=development")
    origin = "http://127.0.0.1:8180"
    admin_password = values.get("OIDC_DEV_ADMIN_PASSWORD")
    password = values.get("OIDC_DEV_USER_PASSWORD") or secrets.token_urlsafe(24)
    if not admin_password:
        raise SystemExit("Set OIDC_DEV_ADMIN_PASSWORD in your ignored .env")
    with httpx.Client(timeout=20) as client:
        response = client.post(
            origin + "/realms/master/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": values.get("OIDC_DEV_ADMIN_USER", "development-operator"),
                "password": admin_password,
            },
        )
        response.raise_for_status()
        headers = {"Authorization": "Bearer " + response.json()["access_token"]}
        for username in ("researcher-a", "researcher-b", "research-viewer"):
            users = client.get(
                origin + "/admin/realms/medsynth-development/users",
                params={"username": username, "exact": "true"},
                headers=headers,
            )
            users.raise_for_status()
            user = users.json()[0]
            updated = client.put(
                origin + "/admin/realms/medsynth-development/users/" + user["id"],
                headers=headers,
                json={
                    "email": username + "@example.invalid",
                    "emailVerified": True,
                    "requiredActions": [],
                },
            )
            updated.raise_for_status()
            response = client.put(
                origin
                + "/admin/realms/medsynth-development/users/"
                + user["id"]
                + "/reset-password",
                headers=headers,
                json={"type": "password", "temporary": False, "value": password},
            )
            response.raise_for_status()
    store = boto3.client(
        "s3",
        endpoint_url="http://127.0.0.1:9000",
        region_name="us-east-1",
        aws_access_key_id=values["S3_ACCESS_KEY"],
        aws_secret_access_key=values["S3_SECRET_KEY"],
    )
    bucket = values.get("S3_BUCKET", "medsynth-development")
    existing = [b["Name"] for b in store.list_buckets()["Buckets"]]
    if bucket not in existing:
        store.create_bucket(Bucket=bucket)
    # MinIO has no AWS PublicAccessBlock implementation. Remove any public policy;
    # verify anonymous reads are denied in storage tests. AWS deployments use account/bucket blocks.
    from botocore.exceptions import ClientError

    try:
        store.delete_bucket_policy(Bucket=bucket)
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "NoSuchBucketPolicy":
            raise
    # Keep the generated credential out of console output, reports and tracked files.
    output = Path(ROOT / "backend/.work/development-identity.env")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("OIDC_DEV_USER_PASSWORD=" + password + "\n", encoding="utf-8")
    print(
        "Development identities and private bucket configured; generated test password stored in ignored backend/.work/development-identity.env"
    )


if __name__ == "__main__":
    main()
