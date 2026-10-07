import { useState } from "react";
import { Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle, TextField, Typography } from "@mui/material";
import { useNavigate } from "react-router-dom";
import { api, errorMessage } from "../../api/client";
import { useIdentity } from "./context";
export default function DeleteProject({ id, name }: { id: string; name: string }) {
  const { isOwner } = useIdentity();
  const [open, setOpen] = useState(false), [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState(""), [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  if (!isOwner) return null;
  async function submit() {
    setBusy(true);
    try { await api.post(`/api/v1/projects/${id}/deletion`, { confirmation }); navigate("/projects"); }
    catch (e) { setError(errorMessage(e)); }
    finally { setBusy(false); }
  }
  return <><Button color="error" onClick={() => setOpen(true)}>Request project deletion</Button>
    <Dialog open={open} onClose={() => !busy && setOpen(false)} fullWidth maxWidth="sm" aria-labelledby="delete-title">
      <DialogTitle id="delete-title">Delete project artifacts</DialogTitle><DialogContent>
        <Typography sx={{ mb: 2 }}>This hides the project and requests background deletion of source, synthetic, model and report objects. Metadata, provenance and audit history remain. Object-store versions and backups follow the provider's policies. Cancel queued work and wait for running work first.</Typography>
        {error && <Alert severity="error">{error}</Alert>}
        <TextField autoFocus fullWidth label="Enter project name to confirm" helperText={name} value={confirmation} onChange={(e) => setConfirmation(e.target.value)} />
      </DialogContent><DialogActions><Button disabled={busy} onClick={() => setOpen(false)}>Cancel</Button>
        <Button color="error" disabled={busy || confirmation !== name} onClick={() => void submit()}>Request deletion</Button>
      </DialogActions>
    </Dialog></>;
}
