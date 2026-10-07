import { useIdentity } from "../identity/context";
import { useState } from "react";
import { Alert, Button, Stack, Typography } from "@mui/material";
import { Link, useParams } from "react-router-dom";
import { api, errorMessage } from "../../api/client";
import { useResource } from "../../hooks/useResource";
import type {
  Activity,
  Artifact,
  Evaluation,
  Page,
  Summary,
} from "../../types/domain";
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
import FidelityView from "./FidelityView";
import { PrivacyView, UtilityView } from "./Diagnostics";
import ReleaseView from "./ReleaseView";
export default function EvaluationDetail() {
  const { canEdit } = useIdentity();
  const { evaluationId } = useParams();
  const resource = useResource<Evaluation>(
    `/api/v1/evaluations/${evaluationId}`,
    true,
  );
  const e = resource.data;
  const reports = useResource<Page<Artifact>>(
    e?.status === "SUCCEEDED"
      ? `/api/v1/evaluations/${evaluationId}/reports`
      : null,
  );
  const activity = useResource<Page<Activity>>(
    `/api/v1/workspace/activity?entity_id=${evaluationId}&limit=100&run_state=${resource.data?.status ?? "loading"}`,
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const s =
    e?.status === "SUCCEEDED" ? (e.result_summary_json as Summary) : undefined;
  async function report() {
    setBusy(true);
    setError("");
    try {
      await api.post(`/api/v1/evaluations/${evaluationId}/governance-report`);
      reports.reload();
      activity.reload();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <State {...resource} />
      {e && (
        <>
          <PageTitle
            title={`Evaluation ${e.id.slice(0, 8)}`}
            description="Separate evidence for structure, fidelity, selected privacy diagnostics and declared utility."
            action={
              s ? (
                <Button
                  variant="contained"
                  disabled={busy || !canEdit}
                  onClick={() => void report()}
                >
                  {busy ? "Preparing…" : "Generate governance report"}
                </Button>
              ) : undefined
            }
          />
          {error && <Alert severity="error">{error}</Alert>}
          <Stack direction="row" gap={2}>
            <Link to={`/projects/${e.project_id}`}>Project</Link>
            <Link to={`/datasets/${e.dataset_id}`}>Source dataset</Link>
            <Link to={`/runs/${e.generation_job_id}`}>Synthetic run</Link>
          </Stack>
          <Section title="Evaluation summary">
            <Facts
              values={{
                Status: <Status value={e.status} />,
                Engine: human(
                  e.configuration_json.generation_engine ?? "Unavailable",
                ),
                Profile: human(e.profile),
                "Release decision": (
                  <Status value={s?.release.decision ?? "NOT_EVALUATED"} />
                ),
                Completed: date(e.finished_at),
                Duration: duration(e.started_at, e.finished_at),
              }}
            />
            <Alert severity="info" sx={{ mt: 2 }}>
              A policy pass means this dataset satisfied the configured policy
              version. It is not a guarantee of anonymity, regulatory compliance
              or clinical validity.
            </Alert>
          </Section>
          {e.error_message && (
            <Alert severity="error">Evaluation failed: {e.error_message}</Alert>
          )}
          {!s && (
            <Typography>
              Evidence appears after evaluation succeeds. Queued and running
              states reflect recorded platform status.
            </Typography>
          )}
          {s && (
            <>
              <Section title="Structural validation">
                <StructuralView value={s.structural} />
              </Section>
              <Section title="Statistical fidelity">
                <FidelityView summary={s} />
              </Section>
              <Section title="Privacy diagnostics">
                <PrivacyView summary={s} />
              </Section>
              <Section title="ML utility">
                <UtilityView value={s.utility} />
              </Section>
              <Section title="Release policy">
                <ReleaseView value={s.release} />
              </Section>
              <Section title="Artifacts">
                <State {...reports} />
                {reports.data && <Artifacts items={reports.data.items} />}
              </Section>
              {s.warnings.map((w, i) => (
                <Alert key={`${i}-${w}`} severity="warning">
                  {w}
                </Alert>
              ))}
              <Section title="Technical details">
                <details>
                  <summary>Evaluation identity and configuration</summary>
                  <Facts
                    values={{
                      "Evaluation ID": e.id,
                      "Generation job ID": e.generation_job_id,
                      "Dataset ID": e.dataset_id,
                      Created: date(e.created_at),
                    }}
                  />
                  <Typography
                    component="pre"
                    sx={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}
                  >
                    {JSON.stringify(e.configuration_json, null, 2)}
                  </Typography>
                </details>
              </Section>
            </>
          )}
          <Section title="Recorded activity">
            <State {...activity} />
            {activity.data && <ActivityView items={activity.data.items} />}
          </Section>
        </>
      )}
    </>
  );
}
