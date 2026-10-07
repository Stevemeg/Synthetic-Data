import { useIdentity } from "../features/identity/context";
import { useRef, useState } from "react";
import {
  Alert,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  TextField,
} from "@mui/material";
import { Link, useNavigate } from "react-router-dom";
import { api, errorMessage } from "../api/client";
import { useResource } from "../hooks/useResource";
import {
  DataTable,
  Empty,
  PageTitle,
  Pager,
  Section,
  State,
  Status,
} from "../components/Workspace";
import type { Page, Project } from "../types/domain";
import { date } from "../utils/format";
export default function Projects() {
  const { canEdit } = useIdentity();
  const nameInput = useRef<HTMLInputElement>(null);
  const [offset, setOffset] = useState(0);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  const resource = useResource<Page<Project>>(
    `/api/v1/workspace/projects?limit=20&offset=${offset}`,
  );
  async function create() {
    setBusy(true);
    setError("");
    try {
      const r = await api.post<Project>("/api/v1/projects", {
        name: name.trim(),
        description,
      });
      navigate(`/projects/${r.data.id}`);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageTitle
        title="Projects"
        description="Organize sources, synthesis runs and release evidence."
        action={
          <Button disabled={!canEdit} variant="contained" onClick={() => setOpen(true)}>
            Create project
          </Button>
        }
      />
      <Section title="Project inventory">
        <State {...resource} />
        {resource.data &&
          (resource.data.items.length ? (
            <>
              <DataTable
                label="Projects"
                headers={[
                  "Project",
                  "Description",
                  "Datasets",
                  "Runs",
                  "Evaluations",
                  "Latest activity",
                  "Release decision",
                ]}
                rows={resource.data.items.map((p) => [
                  <Link to={`/projects/${p.id}`}>{p.name}</Link>,
                  p.description || "No description",
                  p.datasets,
                  p.runs,
                  p.evaluations,
                  date(p.latest_activity),
                  <Status value={p.latest_decision ?? "NOT_EVALUATED"} />,
                ])}
              />
              <Pager
                offset={offset}
                total={resource.data.total}
                onChange={setOffset}
              />
            </>
          ) : (
            <Empty title="No projects yet">
              Create your first project to begin a governed workflow.
            </Empty>
          ))}
      </Section>
      <Dialog
        slotProps={{
          transition: { onEntered: () => nameInput.current?.focus() },
        }}
        open={open}
        onClose={() => !busy && setOpen(false)}
        fullWidth
        maxWidth="sm"
        aria-labelledby="create-project-title"
      >
        <DialogTitle id="create-project-title">Create project</DialogTitle>
        <DialogContent>
          <Stack gap={3} sx={{ pt: 1 }}>
            {error && <Alert severity="error">{error}</Alert>}
            <TextField
              inputRef={nameInput}
              autoFocus
              label="Project name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              slotProps={{ htmlInput: { maxLength: 120 } }}
            />
            <TextField
              label="Description"
              multiline
              minRows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              slotProps={{ htmlInput: { maxLength: 2000 } }}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button disabled={busy} onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button
            variant="contained"
            disabled={busy || !name.trim()}
            onClick={() => void create()}
          >
            {busy ? "Creating…" : "Create"}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
