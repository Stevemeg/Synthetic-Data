import hashlib
import json
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from threading import Barrier
from time import monotonic, sleep
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from backend.app import create_app
from backend.app.config import ROOT
from backend.app.core.errors import AppError
from backend.app.db.models import (
    Artifact,
    AuditEvent,
    Dataset,
    GenerationJob,
    ReleasePolicy,
)
from backend.app.db.repositories.jobs import JobClaim, QueueRepository, utcnow
from backend.app.db.session import Database
from backend.app.storage.factory import artifact_store
from backend.app.storage.local import LocalArtifactStore
from backend.app.workers.runner import Worker
from backend.tests.evaluation_fixture import evaluation_fixture
from backend.tests.test_platform_integration import dataset, project

pytestmark = pytest.mark.integration

FULL_REQUEST = {
    "profile": "FULL",
    "group_key": "patient_id",
    "privacy": {
        "known_columns": ["age", "sex"],
        "sensitive_columns": ["diagnosis_group"],
        "continuous_columns": ["age"],
    },
    "utility": {"task": "BINARY_CLASSIFICATION", "target": "readmitted"},
}


def generate(client, settings, **options):
    pid = project(client)
    raw = evaluation_fixture().to_csv(index=False, lineterminator="\n").encode()
    data = dataset(client, pid, raw, "tabular")
    response = client.post(
        f"/api/v1/projects/{pid}/jobs",
        json={
            "modality": "tabular",
            "dataset_id": data["id"],
            "requested_samples": 400,
            "random_seed": 42,
            "metadata_overrides": {
                "age": {"annotations": ["QUASI_IDENTIFIER"]},
                "sex": {"annotations": ["QUASI_IDENTIFIER"]},
                "diagnosis_group": {"annotations": ["SENSITIVE_ATTRIBUTE"]},
            },
            **options,
        },
    )
    assert response.status_code == 202, response.text
    generation = response.json()
    database = Database(settings)
    try:
        assert Worker(settings, database, artifact_store(settings)).run_once()
    finally:
        database.dispose()

    assert client.get(f"/api/v1/jobs/{generation['id']}").json()["status"] == "SUCCEEDED"
    return data, generation, raw


def submit(client, generation, body=None):
    response = client.post(
        f"/api/v1/generation-jobs/{generation['id']}/evaluations", json=body or FULL_REQUEST
    )
    assert response.status_code == 202, response.text
    return response.json()


def test_two_workers_one_evaluation(pg_client, pg_settings):
    _, generation, _ = generate(pg_client, pg_settings)
    evaluation = submit(pg_client, generation)
    database = Database(pg_settings)
    store = LocalArtifactStore(pg_settings.artifact_storage_path)
    barrier = Barrier(2)

    def run(index):
        worker = Worker(pg_settings, database, store, f"evaluation-worker-{index}")
        barrier.wait()
        return worker.run_once()

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, range(2)))
        assert sorted(results) == [False, True]
        result = pg_client.get(f"/api/v1/evaluations/{evaluation['id']}").json()
        assert result["status"] == "SUCCEEDED" and result["attempt_count"] == 1
        assert pg_client.get(f"/api/v1/evaluations/{evaluation['id']}/reports").json()["total"] == 5
        with database.sessions() as session:
            events = list(
                session.scalars(
                    select(AuditEvent.event_type).where(
                        AuditEvent.entity_id == UUID(evaluation["id"])
                    )
                )
            )
        assert (
            events.count("EVALUATION_STARTED")
            == events.count("QUALITY_EVALUATION_COMPLETED")
            == events.count("UTILITY_EVALUATION_COMPLETED")
            == 1
        )
    finally:
        database.dispose()


def test_evaluation_retry_compensates_and_fences(pg_client, pg_settings, monkeypatch):
    _, generation, _ = generate(pg_client, pg_settings)
    evaluation = submit(pg_client, generation)
    database = Database(pg_settings)
    store = LocalArtifactStore(pg_settings.artifact_storage_path)
    worker = Worker(pg_settings, database, store)
    actual_put = store.put

    def fail_privacy(key, stream):
        if key.endswith("privacy_report.json"):
            raise OSError("Controlled temporary publication failure")
        return actual_put(key, stream)

    try:
        monkeypatch.setattr(store, "put", fail_privacy)
        assert worker.run_once()
        first = pg_client.get(f"/api/v1/evaluations/{evaluation['id']}").json()
        assert first["status"] == "QUEUED" and first["attempt_count"] == 1
        assert first["result_summary_json"] == {}
        assert not list(store.root.rglob("quality_report.json"))
        with database.sessions() as session:
            old_job = session.get(GenerationJob, UUID(evaluation["execution_job_id"]))
        with database.engine.begin() as connection:
            connection.execute(
                update(GenerationJob)
                .where(GenerationJob.id == old_job.id)
                .values(available_at=utcnow() - timedelta(seconds=1))
            )
        monkeypatch.setattr(store, "put", actual_put)
        assert worker.run_once()
        second = pg_client.get(f"/api/v1/evaluations/{evaluation['id']}").json()
        assert second["status"] == "SUCCEEDED" and second["attempt_count"] == 2
        with database.sessions() as session:
            assert session.get(GenerationJob, old_job.id).claim_token != old_job.claim_token
        assert pg_client.get(f"/api/v1/evaluations/{evaluation['id']}/reports").json()["total"] == 5
    finally:
        database.dispose()


@pytest.mark.parametrize(
    "kind,code",
    [
        ("source", "EVALUATION_SOURCE_INTEGRITY_FAILED"),
        ("synthetic", "EVALUATION_SYNTHETIC_INTEGRITY_FAILED"),
        ("manifest", "EVALUATION_MANIFEST_INVALID"),
    ],
)
def test_input_mutation_before_submission_and_execution(kind, code, pg_client, pg_settings):
    data, generation, _ = generate(pg_client, pg_settings)
    evaluation = submit(pg_client, generation, {"profile": "BASIC", "group_key": "patient_id"})
    database = Database(pg_settings)
    store = LocalArtifactStore(pg_settings.artifact_storage_path)
    try:
        with database.sessions() as session:
            if kind == "source":
                record = session.get(Dataset, UUID(data["id"]))
            else:
                record = session.scalar(
                    select(Artifact).where(
                        Artifact.job_id == UUID(generation["id"]),
                        Artifact.artifact_type
                        == ("SYNTHETIC_DATASET" if kind == "synthetic" else "RUN_METADATA"),
                    )
                )
        path = store.path(record.storage_key)
        original = path.read_bytes()
        path.write_bytes(b"mutated test-only bytes")
        rejected = pg_client.post(
            f"/api/v1/generation-jobs/{generation['id']}/evaluations", json={"profile": "BASIC"}
        )
        assert rejected.status_code == 400 and rejected.json()["error"]["code"] == code
        assert Worker(pg_settings, database, store).run_once()
        result = pg_client.get(f"/api/v1/evaluations/{evaluation['id']}").json()
        assert (
            result["status"] == "FAILED"
            and result["error_code"] == code
            and result["attempt_count"] == 1
        )
        assert pg_client.get(f"/api/v1/evaluations/{evaluation['id']}/reports").json()["total"] == 0
        path.write_bytes(original)
    finally:
        database.dispose()


def test_policy_database_immutability_migration_and_configuration(pg_client, pg_settings):
    database = Database(pg_settings)
    config = Config(str(ROOT / "alembic.ini"))
    try:
        with database.engine.begin() as connection:
            config.attributes["connection"] = connection
            command.downgrade(config, "0002_tabular")
            command.upgrade(config, "head")
            command.check(config)
        database.ready()
        pid = project(pg_client)
        body = {
            "name": "Local policy",
            "version": 1,
            "rules": {"structural_validation": {"equals": True}},
        }
        first = pg_client.post(f"/api/v1/projects/{pid}/release-policies", json=body)
        assert first.status_code == 201
        assert (
            pg_client.post(f"/api/v1/projects/{pid}/release-policies", json=body).status_code == 409
        )
        second = pg_client.post(
            f"/api/v1/projects/{pid}/release-policies", json={**body, "version": 2}
        )
        assert (
            second.status_code == 201
            and second.json()["policy_hash"] != first.json()["policy_hash"]
        )
        with pytest.raises(IntegrityError), database.engine.begin() as connection:
            connection.execute(
                update(ReleasePolicy)
                .where(ReleasePolicy.id == UUID(first.json()["id"]))
                .values(description="mutated")
            )
        with pytest.raises(RuntimeError), database.engine.begin() as connection:
            config.attributes["connection"] = connection
            command.downgrade(config, "0002_tabular")
    finally:
        database.dispose()


def test_evaluation_timeout_no_report_publication(pg_client, pg_settings):
    _, generation, _ = generate(pg_client, pg_settings)
    limited = replace(pg_settings, evaluation_timeout_seconds=1)
    with TestClient(create_app(limited)) as client:
        evaluation = submit(client, generation)
        database = Database(limited)
        try:
            assert Worker(
                limited, database, LocalArtifactStore(limited.artifact_storage_path)
            ).run_once()
            result = client.get(f"/api/v1/evaluations/{evaluation['id']}").json()
            assert result["status"] == "FAILED" and result["error_code"] == "EVALUATION_TIMEOUT"
            assert (
                client.get(f"/api/v1/evaluations/{evaluation['id']}/reports").json()["total"] == 0
            )
        finally:
            database.dispose()


def crash_worker(settings):
    database = Database(settings)
    try:
        Worker(settings, database, LocalArtifactStore(settings.artifact_storage_path)).run_once()
    finally:
        database.dispose()


def test_evaluation_worker_death_recovery_and_stale_completion(pg_client, pg_settings):
    _, generation, _ = generate(pg_client, pg_settings)
    # Full quality runs in the child after the genuine evaluation-start audit.
    evaluation = submit(pg_client, generation)
    database = Database(pg_settings)
    queue = QueueRepository(database, pg_settings.job_lease_seconds)
    process = multiprocessing.get_context("spawn").Process(target=crash_worker, args=(pg_settings,))
    process.start()
    try:
        deadline = monotonic() + 90
        while monotonic() < deadline:
            with database.sessions() as session:
                old_job = session.get(GenerationJob, UUID(evaluation["execution_job_id"]))
                metric_started = session.scalar(
                    select(AuditEvent.id).where(
                        AuditEvent.entity_id == UUID(evaluation["id"]),
                        AuditEvent.event_type == "QUALITY_EVALUATION_STARTED",
                    )
                )
            if metric_started:
                break
            assert process.is_alive()
            sleep(0.05)
        assert old_job.status == "RUNNING" and metric_started
        # A real child stage audit proves metrics started; never fake progress.
        process.kill()
        process.join(timeout=10)
        assert not process.is_alive()
        with database.engine.begin() as connection:
            connection.execute(
                update(GenerationJob)
                .where(GenerationJob.id == old_job.id)
                .values(lease_expires_at=utcnow() - timedelta(seconds=1))
            )
        claim = queue.claim("recovered-evaluation")
        assert (
            claim and claim.job.attempt_count == 2 and claim.job.claim_token != old_job.claim_token
        )
        try:
            stale = JobClaim(old_job, claim.connection, claim.key)
            with pytest.raises(AppError):
                queue.heartbeat(stale)
            with pytest.raises(AppError):
                queue.succeed(stale, [], {}, 1, utcnow())
            queue.fail(claim, "CONTROLLED_RETRY", "Recovery checked", True)
        finally:
            claim.release()
        with database.engine.begin() as connection:
            connection.execute(
                update(GenerationJob)
                .where(GenerationJob.id == old_job.id)
                .values(available_at=utcnow() - timedelta(seconds=1))
            )
        assert Worker(
            pg_settings, database, LocalArtifactStore(pg_settings.artifact_storage_path)
        ).run_once()
        result = pg_client.get(f"/api/v1/evaluations/{evaluation['id']}").json()
        assert result["status"] == "SUCCEEDED" and result["attempt_count"] == 3
        assert pg_client.get(f"/api/v1/evaluations/{evaluation['id']}/reports").json()["total"] == 5
    finally:
        if process.is_alive():
            process.kill()
            process.join(timeout=10)
        database.dispose()


def test_full_evaluation_real_worker_reports_restart(pg_client, pg_settings):
    data, generation, raw = generate(pg_client, pg_settings)
    policy_response = pg_client.post(
        f"/api/v1/projects/{generation['project_id']}/release-policies",
        json={
            "name": "Engineering demonstration",
            "version": 1,
            "illustrative": True,
            "rules": {
                "structural_validation": {"equals": True},
                "holdout_column_shapes": {"minimum": 0.0},
                "dcr_overfitting_gating_eligible": {"equals": True},
            },
        },
    )
    assert policy_response.status_code == 201, policy_response.text
    policy = policy_response.json()
    response = pg_client.post(
        f"/api/v1/generation-jobs/{generation['id']}/evaluations",
        json={**FULL_REQUEST, "release_policy_id": policy["id"]},
    )
    assert response.status_code == 202, response.text
    evaluation = response.json()
    database = Database(pg_settings)
    store = LocalArtifactStore(pg_settings.artifact_storage_path)
    try:
        assert Worker(pg_settings, database, store).run_once()
        with TestClient(create_app(pg_settings)) as restarted:
            result = restarted.get(f"/api/v1/evaluations/{evaluation['id']}").json()
            assert result["status"] == "SUCCEEDED", result
            summary = result["result_summary_json"]
            assert summary["quality"]["training"]["score"] is not None
            assert summary["quality"]["holdout"]["score"] is not None
            assert (
                summary["privacy"]["dcr_overfitting_protection"]["applicability"] == "ADVISORY_ONLY"
            )
            assert (
                summary["privacy"]["dcr_overfitting_protection"]["methodology"][
                    "train_validation_ratio"
                ]
                == 4
            )
            assert summary["privacy"]["disclosure_protection"]["score"] is not None
            assert summary["utility"]["trtr"]["f1"] is not None
            assert summary["utility"]["tstr"]["f1"] is not None
            assert summary["release"]["decision"] == "FAIL"
            reports = restarted.get(f"/api/v1/evaluations/{evaluation['id']}/reports").json()[
                "items"
            ]
            assert len(reports) == 5
            for report in reports:
                downloaded = restarted.get(f"/api/v1/artifacts/{report['id']}/download")
                assert downloaded.status_code == 200
                assert hashlib.sha256(downloaded.content).hexdigest() == report["sha256"]
                assert report["metadata_json"]["sensitive_internal"]
                assert (
                    "SOURCE-" not in downloaded.text and "Invented private" not in downloaded.text
                )
                if report["artifact_type"] == "EVALUATION_MANIFEST":
                    manifest = downloaded.json()
                    assert manifest["inputs"]["source"]["sha256"] == data["sha256"]
                    assert manifest["source_split"]["training_row_count"] == 320
                    assert manifest["policy"]["policy_hash"] == policy["policy_hash"]
            assert all(
                j["engine"] != "evaluation-v1"
                for j in restarted.get(f"/api/v1/projects/{generation['project_id']}/jobs").json()[
                    "items"
                ]
            )
        with database.sessions() as session:
            dataset = session.get(Dataset, UUID(data["id"]))
            source_key = dataset.storage_key
        assert store.metadata(source_key).sha256 == hashlib.sha256(raw).hexdigest()
        print(
            json.dumps(
                {
                    "evaluation_id": evaluation["id"],
                    "generation_id": generation["id"],
                    "policy": policy,
                    "summary": summary,
                    "artifacts": reports,
                },
                indent=2,
            )
        )
    finally:
        database.dispose()


@pytest.mark.model
def test_three_real_engines_compatible_comparison_and_policy_versions(pg_client, pg_settings):
    pid = project(pg_client)
    raw = evaluation_fixture().to_csv(index=False, lineterminator="\n").encode()
    data = dataset(pg_client, pid, raw, "tabular")
    policy_body = {
        "name": "Comparison demo",
        "version": 1,
        "illustrative": True,
        "rules": {"structural_validation": {"equals": True}},
    }
    p1 = pg_client.post(f"/api/v1/projects/{pid}/release-policies", json=policy_body).json()
    p2 = pg_client.post(
        f"/api/v1/projects/{pid}/release-policies", json={**policy_body, "version": 2}
    ).json()
    database = Database(pg_settings)
    worker = Worker(pg_settings, database, LocalArtifactStore(pg_settings.artifact_storage_path))
    ids, generation_ids = [], []
    try:
        for engine in ("gaussian_copula", "ctgan", "tvae"):
            response = pg_client.post(
                f"/api/v1/projects/{pid}/jobs",
                json={
                    "modality": "tabular",
                    "dataset_id": data["id"],
                    "engine": engine,
                    "requested_samples": 400,
                    "random_seed": 42,
                    **(
                        {
                            "configuration": {
                                "epochs": 1,
                                "batch_size": 20,
                                "embedding_dim": 16,
                                "generator_dim": [32],
                                "discriminator_dim": [32],
                            }
                        }
                        if engine != "gaussian_copula"
                        else {}
                    ),
                },
            )
            assert response.status_code == 202, response.text
            generation = response.json()
            generation_ids.append(generation["id"])
            assert worker.run_once()
            assert pg_client.get(f"/api/v1/jobs/{generation['id']}").json()["status"] == "SUCCEEDED"
            evaluation = submit(
                pg_client, generation, {**FULL_REQUEST, "release_policy_id": p1["id"]}
            )
            assert worker.run_once()
            result = pg_client.get(f"/api/v1/evaluations/{evaluation['id']}").json()
            assert result["status"] == "SUCCEEDED", result
            ids.append(evaluation["id"])
        response = pg_client.post(
            f"/api/v1/projects/{pid}/evaluations/compare", json={"evaluation_ids": ids}
        )
        assert response.status_code == 200, response.text
        rows = response.json()["rows"]
        assert [row["engine"] for row in rows] == ["gaussian_copula", "ctgan", "tvae"]
        assert [row["evaluation_id"] for row in rows] == ids
        print(
            json.dumps(
                {
                    "model_comparison": [
                        {
                            "engine": row["engine"],
                            "evaluation_id": row["evaluation_id"],
                            "holdout_shapes": row["results"]["quality"]["holdout"]["properties"][
                                "Column Shapes"
                            ]["score"],
                            "holdout_pairs": row["results"]["quality"]["holdout"]["properties"][
                                "Column Pair Trends"
                            ]["score"],
                            "dcr_baseline": row["results"]["privacy"]["dcr_baseline_protection"][
                                "score"
                            ],
                            "dcr_overfitting": row["results"]["privacy"][
                                "dcr_overfitting_protection"
                            ]["score"],
                            "disclosure": row["results"]["privacy"]["disclosure_protection"][
                                "score"
                            ],
                            "trtr_f1": row["results"]["utility"]["trtr"]["f1"],
                            "tstr_f1": row["results"]["utility"]["tstr"]["f1"],
                            "ratio": row["results"]["utility"]["score"],
                            "policy": row["results"]["release"]["decision"],
                        }
                        for row in rows
                    ]
                },
                indent=2,
            )
        )
        incompatible = submit(
            pg_client, {"id": generation_ids[0]}, {**FULL_REQUEST, "release_policy_id": p2["id"]}
        )
        assert worker.run_once()
        assert (
            pg_client.post(
                f"/api/v1/projects/{pid}/evaluations/compare",
                json={"evaluation_ids": [ids[0], incompatible["id"]]},
            ).status_code
            == 400
        )
        # Different source identities/hashes are rejected, even with matching profile/task.
        modified = evaluation_fixture()
        modified["lab_value"] += 0.125
        other_data = dataset(pg_client, pid, modified.to_csv(index=False).encode(), "tabular")
        assert other_data["sha256"] != data["sha256"]
        response = pg_client.post(
            f"/api/v1/projects/{pid}/jobs",
            json={
                "modality": "tabular",
                "dataset_id": other_data["id"],
                "requested_samples": 400,
                "random_seed": 42,
            },
        )
        assert response.status_code == 202
        assert worker.run_once()
        other = submit(pg_client, response.json(), {**FULL_REQUEST, "release_policy_id": p1["id"]})
        assert worker.run_once()
        assert (
            pg_client.post(
                f"/api/v1/projects/{pid}/evaluations/compare",
                json={"evaluation_ids": [ids[0], other["id"]]},
            ).status_code
            == 400
        )
    finally:
        database.dispose()
