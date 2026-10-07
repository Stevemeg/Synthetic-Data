import { useIdentity } from "../identity/context";
import { Alert, Button, Stack, Typography } from "@mui/material";
import { Link, useParams } from "react-router-dom";
import { useResource } from "../../hooks/useResource";
import { api, errorMessage } from "../../api/client";
import { useState } from "react";
import type { Activity, Artifact, Job, Page } from "../../types/domain";
import {
  ActivityView,
  Artifacts,
  Facts,
  PageTitle,
  Section,
  State,
  Status,
  StructuralView,
} from "../../components/Workspace";
import { date, duration, human } from "../../utils/format";
export default function RunDetail() {
  const { canEdit } = useIdentity();
  const { jobId } = useParams();
  const resource = useResource<Job>(`/api/v1/jobs/${jobId}`, true);
  const artifacts = useResource<Page<Artifact>>(
    resource.data?.status === "SUCCEEDED"
      ? `/api/v1/jobs/${jobId}/artifacts`
      : null,
  );
  const activity = useResource<Page<Activity>>(
    `/api/v1/workspace/activity?entity_id=${jobId}&limit=100&run_state=${resource.data?.status ?? "loading"}`,
  );
  const [error, setError] = useState("");
  const j = resource.data;
  const tabular = j?.metadata_json.tabular;
  return (
    <>
      <State {...resource} />
      {j && (
        <>
          <PageTitle
            title={`Synthetic run ${j.id.slice(0, 8)}`}
            description={`${human(j.engine)} · ${human(j.modality)}`}
            action={
              canEdit && j.status === "SUCCEEDED" && j.modality === "tabular" ? (
                <Button
                  variant="contained"
                  component={Link}
                  to={`/runs/${j.id}/evaluate`}
                >
                  Evaluate dataset
                </Button>
              ) : undefined
            }
          />
          <Stack direction="row" gap={2}>
            <Status value={j.status} />
            <Link to={`/projects/${j.project_id}`}>Open project</Link>
            {j.dataset_id && (
              <Link to={`/datasets/${j.dataset_id}`}>Source dataset</Link>
            )}
          </Stack>
          {(error || j.error_message) && (
            <Alert severity="error">
              Job failed: {error || j.error_message}
            </Alert>
          )}
          {canEdit && j.status === "QUEUED" && (
            <Button
              onClick={async () => {
                try {
                  await api.post(`/api/v1/jobs/${j.id}/cancel`);
                  resource.reload();
                } catch (e) {
                  setError(errorMessage(e));
                }
              }}
            >
              Cancel queued run
            </Button>
          )}
          <Section title="Run summary">
            <Facts
              values={{
                Status: <Status value={j.status} />,
                Engine: human(j.engine),
                "Requested rows": j.requested_samples,
                "Produced rows": j.produced_samples,
                Duration: duration(j.started_at, j.finished_at),
                Seed: j.random_seed,
                Created: date(j.created_at),
                Started: date(j.started_at),
                Completed: date(j.finished_at),
              }}
            />
          </Section>
          <Section title="Workflow timeline">
            <Typography sx={{ mb: 2 }}>
              Recorded lifecycle timestamps; no estimated completion percentage.
            </Typography>
            <Facts
              values={{
                Submitted: date(j.created_at),
                Queued: date(j.queued_at),
                Running: date(j.started_at),
                Completed: date(j.finished_at),
              }}
            />
            <State {...activity} />
            {activity.data && <ActivityView items={activity.data.items} />}
          </Section>
          {j.modality === "tabular" && (
            <Section title="Structural validation">
              <StructuralView
                value={
                  tabular?.structural_validation ??
                  j.metadata_json.structural_validation
                }
              />
            </Section>
          )}
          {j.metadata_json.warnings?.map((w) => (
            <Alert key={w} severity="warning">
              {w}
            </Alert>
          ))}
          <Section title="Artifacts">
            <State {...artifacts} />
            {artifacts.data ? (
              <Artifacts items={artifacts.data.items} />
            ) : (
              <Typography>
                Artifacts are available after successful publication.
              </Typography>
            )}
          </Section>
          <Section title="Provenance">
            <details>
              <summary>Technical details and integrity</summary>
              <Facts
                values={{
                  "Source hash":
                    tabular?.source_sha256 ??
                    j.metadata_json.source_dataset_sha256 ??
                    "Not recorded",
                  "Model hash": tabular?.model_sha256 ?? "Not recorded",
                  "Synthetic hash":
                    tabular?.synthetic_artifact?.sha256 ?? "Not recorded",
                  "Engine version":
                    tabular?.engine_version ??
                    j.metadata_json.engine_version ??
                    "Not recorded",
                  "Application version":
                    j.metadata_json.application_version ?? "Not recorded",
                  "Git commit":
                    j.metadata_json.application_commit ?? "Not recorded",
                  "Training duration":
                    tabular?.performance.training_duration_seconds ??
                    "Not recorded",
                  "Sampling duration":
                    tabular?.performance.sampling_duration_seconds ??
                    "Not recorded",
                }}
              />
              <Typography
                component="pre"
                sx={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}
              >
                Split configuration:{" "}
                {JSON.stringify(
                  j.configuration_json.split ?? tabular?.split ?? {},
                  null,
                  2,
                )}
              </Typography>
            </details>
          </Section>
        </>
      )}
    </>
  );
}
