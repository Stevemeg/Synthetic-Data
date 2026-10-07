import { useState } from "react";
import { Alert, Button, MenuItem, Stack, TextField, Typography } from "@mui/material";
import { useResource } from "../../hooks/useResource";
import { api, errorMessage } from "../../api/client";
import { PageTitle, Section, State } from "../../components/Workspace";
import { useIdentity, type Role } from "./context";
type Member = { id: string; display_name: string; email: string | null; role: Role };
export default function Members() {
  const { isOwner } = useIdentity();
  const resource = useResource<Member[]>(isOwner ? "/api/v1/organization/members" : null);
  const [error, setError] = useState("");
  async function change(member: Member, role: Role, remove = false) {
    if (remove && !window.confirm(`Remove ${member.display_name || "this identity"} from this organization?`)) return;
    try { await api.patch(`/api/v1/organization/members/${member.id}`, { role, status: remove ? "REMOVED" : "ACTIVE" }); resource.reload(); }
    catch (e) { setError(errorMessage(e)); }
  }
  return <><PageTitle title="Organization members" description="Membership controls access to this organization's projects." />
    {!isOwner ? <Alert severity="info">Only organization owners may manage membership.</Alert> :
      <Section title="Active members"><State {...resource} />{error && <Alert severity="error">{error}</Alert>}
        {resource.data?.map((m) => <Stack key={m.id} direction={{ xs: "column", md: "row" }} gap={2} sx={{ mb: 2 }} alignItems="center">
          <Typography sx={{ flexGrow: 1 }}>{m.display_name || "Unnamed identity"} · {m.email ?? "No email supplied"}</Typography>
          <TextField select label={`Role for ${m.display_name || m.id}`} size="small" value={m.role} onChange={(e) => void change(m, e.target.value as Role)}>
            {["OWNER", "EDITOR", "VIEWER"].map((r) => <MenuItem key={r} value={r}>{r.toLowerCase()}</MenuItem>)}
          </TextField><Button onClick={() => void change(m, m.role, true)}>Remove member</Button>
        </Stack>)}<Typography color="text.secondary">New identities are assigned by the platform operator after their first OIDC sign-in. Email invitations are not implemented.</Typography>
      </Section>}</>;
}
