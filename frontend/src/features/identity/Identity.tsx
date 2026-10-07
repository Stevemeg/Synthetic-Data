import { useEffect, useState, type ReactNode } from "react";
import { Alert, Box, Button, CircularProgress, MenuItem, Stack, TextField, Typography } from "@mui/material";
import { useNavigate } from "react-router-dom";
import { api, configureIdentity, errorMessage } from "../../api/client";
import { isAxiosError } from "axios";

import { IdentityContext, useIdentity, type Identity } from "./context";
export function EditorRoute({ children }: { children: ReactNode }) {
  return useIdentity().canEdit ? children : <Alert severity="info">Your viewer role permits reading evidence and allowed downloads. An editor or owner can submit work.</Alert>;
}

export function IdentityProvider({ children }: { children: ReactNode }) {
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const navigate = useNavigate();
  async function signOut() {
    try {
      await api.post("/api/v1/auth/logout");
      sessionStorage.removeItem("medsynth-organization"); configureIdentity(null, null);
      setIdentity(null); setSelected(null); navigate("/");
    } catch (e) { setError(errorMessage(e)); }
  }
  async function load() {
    setLoading(true); setError("");
    try {
      const { data } = await api.get<Identity>("/api/v1/auth/me");
      const previous = sessionStorage.getItem("medsynth-organization");
      const organization = data.organizations.find((o) => o.id === previous) ?? data.organizations[0];
      setIdentity(data); setSelected(organization?.id ?? null);
      configureIdentity(organization?.id ?? null, data.csrf_token);
    } catch (e) {
      configureIdentity(null, null); setIdentity(null); setSelected(null);
      setError(isAxiosError(e) && e.response?.status === 401 ? "Sign in to access your organization workspace." : errorMessage(e));
    } finally { setLoading(false); }
  }
  useEffect(() => {
    void load();
    const expired = () => { configureIdentity(null, null); setIdentity(null); setSelected(null); setError("Your session expired. Sign in again."); };
    window.addEventListener("medsynth-session-expired", expired);
    return () => window.removeEventListener("medsynth-session-expired", expired);
  }, []);
  const organization = identity?.organizations.find((o) => o.id === selected) ?? null;
  if (loading) return <Box role="status" sx={{ p: 6 }}><CircularProgress size={24} aria-label="Checking workspace access" /> Checking workspace access…</Box>;
  if (!identity || !organization) return <Box component="main" sx={{ maxWidth: 600, m: "10vh auto", p: 3 }}>
    <Typography variant="h4" component="h1" gutterBottom>MedSynth Guard</Typography>
    <Typography sx={{ mb: 3 }}>Governed synthetic health data generation and evaluation.</Typography>
    {error && <Alert severity="info" sx={{ mb: 3 }}>{error}</Alert>}
    {identity?.user ? <><Alert severity="warning">No organization membership is assigned. Contact your organization owner.</Alert><Button onClick={() => void signOut()}>Sign out</Button></> :
      <Button variant="contained" href={`${api.defaults.baseURL}/api/v1/auth/login`}>Sign in</Button>}
    <Button onClick={() => void load()}>Check access</Button>
  </Box>;
  return <IdentityContext.Provider value={{ identity, organization, canEdit: organization.role !== "VIEWER", isOwner: organization.role === "OWNER",
    selectOrganization: (id) => {
      if (!identity.organizations.some((o) => o.id === id)) return;
      sessionStorage.setItem("medsynth-organization", id);
      configureIdentity(id, identity.csrf_token); setSelected(id); navigate("/");
    }, logout: signOut }}>
    {error && <Alert severity="error">{error}</Alert>}
    <Box key={organization.id}>{children}</Box>
  </IdentityContext.Provider>;
}

export function IdentityControls() {
  const { identity, organization, selectOrganization, logout } = useIdentity();
  return <Stack direction="row" gap={1} alignItems="center" flexWrap="wrap">
    {identity?.organizations && identity.organizations.length > 1 ?
      <TextField select label="Organization" size="small" value={organization?.id ?? ""} onChange={(e) => selectOrganization(e.target.value)}>
        {identity.organizations.map((o) => <MenuItem key={o.id} value={o.id}>{o.name}</MenuItem>)}
      </TextField> : <Typography variant="body2">{organization?.name}</Typography>}
    <Typography variant="body2">{identity?.user?.display_name || (identity?.mode === "development" ? "Development mode" : "Signed in")} · {organization?.role.toLowerCase()}</Typography>
    {identity?.mode === "oidc" && <Button size="small" onClick={() => void logout()}>Sign out</Button>}
  </Stack>;
}
