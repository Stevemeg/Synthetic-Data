import { useIdentity } from "../features/identity/context";
import { useState } from "react";
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  Stack,
  TextField,
} from "@mui/material";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, errorMessage } from "../api/client";
import { useResource } from "../hooks/useResource";
import {
  Artifacts,
  DataTable,
  Empty,
  PageTitle,
  Pager,
  Section,
  State,
  Status,
} from "../components/Workspace";
import type { Artifact, Dataset, Evaluation, Job, Page } from "../types/domain";
import { date, duration, human, number } from "../utils/format";
export default function Inventory({ kind }: { kind: string }) {
  const { canEdit } = useIdentity();
  const { projectId } = useParams();
  const navigate = useNavigate();
  const [offset, setOffset] = useState(0);
  const [status, setStatus] = useState("");
  const [engine, setEngine] = useState("");
  const [dataset, setDataset] = useState("");
  const [sort, setSort] = useState("desc");
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [file, setFile] = useState<File>();
  const [modality, setModality] = useState("tabular");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const query = new URLSearchParams({
    limit: "20",
    offset: String(offset),
    sort,
    ...(projectId ? { project_id: projectId } : {}),
    ...(status ? { status } : {}),
    ...(engine ? { engine } : {}),
    ...(dataset ? { dataset_id: dataset } : {}),
  });
  const resource = useResource<Page<Dataset | Job | Evaluation | Artifact>>(
    `/api/v1/workspace/${kind}?${query}`,
  );
  const datasets = useResource<Page<Dataset>>(
    kind === "runs"
      ? `/api/v1/workspace/datasets?limit=100${projectId ? `&project_id=${projectId}` : ""}`
      : null,
  );
  const title = kind === "runs" ? "Synthetic runs" : human(kind);
  async function upload() {
    setBusy(true);
    setError("");
    try {
      if (!file || !file.name.toLowerCase().endsWith(".csv"))
        throw new Error("Choose a nonempty CSV file.");
      const form = new FormData();
      form.append("name", name.trim());
      form.append("modality", modality);
      form.append("file", file);
      const r = await api.post<Dataset>(
        `/api/v1/projects/${projectId}/datasets`,
        form,
      );
      navigate(`/datasets/${r.data.id}`);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  const items = resource.data?.items ?? [];
  return (
    <>
      <PageTitle
        title={title}
        description={
          projectId
            ? "Resources in this project."
            : "Resources in the selected organization."
        }
        action={
          kind === "datasets" && projectId && canEdit ? (
            <Button variant="contained" onClick={() => setOpen(true)}>
              Register dataset
            </Button>
          ) : kind === "evaluations" && projectId ? (
            <Button component={Link} to={`/projects/${projectId}/compare`}>
              Compare evaluations
            </Button>
          ) : undefined
        }
      />
      {kind === "datasets" && !projectId && (
        <Alert severity="info">Open a project to register a dataset.</Alert>
      )}
      {kind === "runs" && (
        <Stack direction={{ xs: "column", md: "row" }} gap={2}>
          <TextField
            select
            label="Status filter"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setOffset(0);
            }}
            fullWidth
          >
            <MenuItem value="">All states</MenuItem>
            {["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"].map(
              (v) => (
                <MenuItem value={v} key={v}>
                  {human(v)}
                </MenuItem>
              ),
            )}
          </TextField>
          <TextField
            select
            fullWidth
            label="Engine filter"
            value={engine}
            onChange={(e) => {
              setEngine(e.target.value);
              setOffset(0);
            }}
          >
            <MenuItem value="">All engines</MenuItem>
            {[
              "gaussian_copula",
              "ctgan",
              "tvae",
              "pytorch-ecg-vae",
              "dcgan-64-rgb",
            ].map((v) => (
              <MenuItem value={v} key={v}>
                {human(v)}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            select
            fullWidth
            label="Dataset filter"
            value={dataset}
            onChange={(e) => {
              setDataset(e.target.value);
              setOffset(0);
            }}
          >
            <MenuItem value="">All datasets</MenuItem>
            {datasets.data?.items.map((d) => (
              <MenuItem key={d.id} value={d.id}>
                {d.name}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            select
            fullWidth
            label="Date order"
            value={sort}
            onChange={(e) => {
              setSort(e.target.value);
              setOffset(0);
            }}
          >
            <MenuItem value="desc">Newest first</MenuItem>
            <MenuItem value="asc">Oldest first</MenuItem>
          </TextField>
        </Stack>
      )}
      <Section title={`${title} inventory`}>
        <State {...resource} />
        {resource.data &&
          (!items.length ? (
            <Empty title={`No ${kind} yet`}>
              {kind === "evaluations"
                ? "Evaluate a successful tabular run to measure fidelity, privacy diagnostics and utility."
                : kind === "reports"
                  ? "Generate a governance report from a completed evaluation."
                  : kind === "datasets"
                    ? "Register a clinical dataset to begin a synthesis workflow."
                    : "Start synthesis from a reviewed dataset."}
            </Empty>
          ) : kind === "reports" ? (
            <Artifacts items={items as Artifact[]} />
          ) : kind === "datasets" ? (
            <DataTable
              label="Dataset inventory"
              headers={[
                "Dataset",
                "Modality",
                "Rows",
                "Columns",
                "Size",
                "Status",
                "Created",
              ]}
              rows={(items as Dataset[]).map((d) => [
                <Link to={`/datasets/${d.id}`}>{d.name}</Link>,
                human(d.modality),
                d.row_count,
                d.column_count,
                `${number(d.size_bytes)} bytes`,
                <Status value={d.status} />,
                date(d.created_at),
              ])}
            />
          ) : kind === "runs" ? (
            <DataTable
              label="Run inventory"
              headers={[
                "Run",
                "Source dataset",
                "Engine",
                "Rows",
                "Status",
                "Started",
                "Duration",
                "Evaluation",
              ]}
              rows={(items as Job[]).map((j) => [
                <Link to={`/runs/${j.id}`}>Run {j.id.slice(0, 8)}</Link>,
                j.dataset_id ? (
                  <Link to={`/datasets/${j.dataset_id}`}>
                    {j.dataset_id.slice(0, 8)}
                  </Link>
                ) : (
                  "Unconditional"
                ),
                human(j.engine),
                `${j.produced_samples} / ${j.requested_samples}`,
                <Status value={j.status} />,
                date(j.started_at),
                duration(j.started_at, j.finished_at),
                j.status === "SUCCEEDED" && j.modality === "tabular" ? (
                  <Link to={`/runs/${j.id}/evaluate`}>Evaluate dataset</Link>
                ) : (
                  "Unavailable"
                ),
              ])}
            />
          ) : (
            <DataTable
              label="Evaluation inventory"
              headers={[
                "Evaluation",
                "Synthetic run",
                "Profile",
                "Status",
                "Decision",
                "Completed",
              ]}
              rows={(items as Evaluation[]).map((e) => [
                <Link to={`/evaluations/${e.id}`}>
                  Evaluation {e.id.slice(0, 8)}
                </Link>,
                <Link to={`/runs/${e.generation_job_id}`}>Open run</Link>,
                human(e.profile),
                <Status value={e.status} />,
                <Status
                  value={
                    e.result_summary_json.release?.decision ?? "NOT_EVALUATED"
                  }
                />,
                date(e.finished_at),
              ])}
            />
          ))}
        {resource.data && (
          <Pager
            offset={offset}
            total={resource.data.total}
            onChange={setOffset}
          />
        )}
      </Section>
      <Dialog
        open={open}
        onClose={() => !busy && setOpen(false)}
        maxWidth="sm"
        fullWidth
        aria-labelledby="upload-title"
      >
        <DialogTitle id="upload-title">Register dataset</DialogTitle>
        <DialogContent>
          <Stack gap={3} sx={{ pt: 1 }}>
            {error && <Alert severity="error">{error}</Alert>}
            <TextField
              autoFocus
              label="Dataset name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              slotProps={{ htmlInput: { maxLength: 120 } }}
            />
            <TextField
              select
              label="Modality"
              value={modality}
              onChange={(e) => setModality(e.target.value)}
            >
              <MenuItem value="tabular">Clinical tabular · Stable</MenuItem>
              <MenuItem value="timeseries">ECG · Beta</MenuItem>
            </TextField>
            <label>
              CSV file
              <input
                aria-label="CSV file"
                type="file"
                accept=".csv"
                onChange={(e) => setFile(e.target.files?.[0])}
              />
            </label>
            <Alert severity="info">
              Source records are never previewed. Upload size and schema limits
              are enforced by the platform.
            </Alert>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)} disabled={busy}>
            Cancel
          </Button>
          <Button
            disabled={busy || !name.trim() || !file?.size}
            onClick={() => void upload()}
            variant="contained"
          >
            {busy ? "Registering…" : "Register"}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
