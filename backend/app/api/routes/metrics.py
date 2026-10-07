import hmac

from fastapi import APIRouter, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, generate_latest
from prometheus_client.core import GaugeMetricFamily
from sqlalchemy import func, select

from ...core.errors import AppError
from ...db.models import GenerationJob

router = APIRouter(tags=["Internal operations"])


@router.get("/internal/metrics", include_in_schema=False)
def metrics(request: Request):
    runtime = request.app.state.runtime
    supplied = request.headers.get("Authorization", "")
    if not runtime.settings.metrics_token or not hmac.compare_digest(
        supplied, "Bearer " + runtime.settings.metrics_token
    ):
        raise AppError("Internal endpoint unavailable", "not_found", 404)
    with runtime.database.sessions() as session:
        counts = dict(
            session.execute(
                select(GenerationJob.status, func.count()).group_by(GenerationJob.status)
            ).all()
        )
    gauge = GaugeMetricFamily("medsynth_jobs", "Persisted work items by state", labels=["status"])
    for status in ("QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"):
        gauge.add_metric([status.lower()], counts.get(status, 0))

    class QueueRegistry:
        def collect(self):
            yield gauge

    content = generate_latest(REGISTRY) + generate_latest(QueueRegistry())
    return Response(content, media_type=CONTENT_TYPE_LATEST)
