from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from ...db.repositories.catalog import AuditRepository, DatasetRepository
from ...schemas.platform import DatasetRead, Page
from ...schemas.tabular import ColumnOverride
from ...services.datasets.service import CsvUpload, DatasetService
from ...services.tabular.profile import resolve_metadata
from ...services.tabular.service import load_registered, preflight
from ..dependencies import Limit, Offset, RuntimeDep, SessionDep
from ..errors import ERRORS

router = APIRouter(prefix="/api/v1", tags=["Datasets"], responses=ERRORS)


@router.post(
    "/projects/{project_id}/datasets",
    response_model=DatasetRead,
    status_code=201,
    summary="Register a bounded CSV and structural metadata",
)
def upload_dataset(
    project_id: UUID,
    session: SessionDep,
    runtime: RuntimeDep,
    name: Annotated[str, Form(min_length=1, max_length=120)],
    modality: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
):
    return DatasetService(session, runtime.store, runtime.settings).register(
        project_id,
        name,
        modality,
        CsvUpload(file.filename or "", file.content_type or "", file.file),
    )


@router.get(
    "/projects/{project_id}/datasets",
    response_model=Page[DatasetRead],
    summary="List registered datasets in a project",
)
def list_datasets(
    project_id: UUID,
    session: SessionDep,
    runtime: RuntimeDep,
    limit: Limit = 50,
    offset: Offset = 0,
):
    return DatasetService(session, runtime.store, runtime.settings).list(project_id, limit, offset)


@router.get(
    "/datasets/{dataset_id}",
    response_model=DatasetRead,
    summary="Retrieve dataset metadata; source rows are excluded",
)
def get_dataset(dataset_id: UUID, session: SessionDep, runtime: RuntimeDep):
    return DatasetService(session, runtime.store, runtime.settings).get(dataset_id)


@router.post(
    "/datasets/{dataset_id}/tabular/preflight",
    summary="Analyze structural facts without source rows",
)
def tabular_preflight(dataset_id: UUID, session: SessionDep, runtime: RuntimeDep):
    return preflight(session, runtime.store, runtime.settings, dataset_id)


class GovernanceConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    overrides: dict[str, ColumnOverride] = Field(max_length=500)


@router.put("/datasets/{dataset_id}/tabular/governance", response_model=DatasetRead)
def save_governance(
    dataset_id: UUID, request: GovernanceConfiguration, session: SessionDep, runtime: RuntimeDep
):
    with session.begin():
        dataset = DatasetRepository(session).get(dataset_id)
        frame = load_registered(dataset, runtime.store, runtime.settings)
        columns = resolve_metadata(frame, request.overrides, {})
        dataset.metadata_json = {
            **dataset.metadata_json,
            "governance_overrides": {
                column.name: ColumnOverride.model_validate(
                    {
                        key: value
                        for key, value in column.model_dump(mode="json").items()
                        if key in ColumnOverride.model_fields
                    }
                ).model_dump(mode="json", exclude_none=True)
                for column in columns
            },
        }
        AuditRepository(session).record("SCHEMA_GOVERNANCE_SAVED", "dataset", dataset.id)
    return dataset
