import { useState } from "react";
import {
  Alert,
  AppBar,
  Box,
  Breadcrumbs,
  Button,
  Chip,
  Drawer,
  Stack,
  Toolbar,
  Typography,
} from "@mui/material";
import { NavLink, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import { useResource } from "../hooks/useResource";
import type { Project } from "../types/domain";
import { IdentityControls } from "../features/identity/Identity";
import { useIdentity } from "../features/identity/context";
const navigation = [
  ["/", "Overview"],
  ["/projects", "Projects"],
  ["/datasets", "Datasets"],
  ["/runs", "Runs"],
  ["/evaluations", "Evaluations"],
  ["/reports", "Reports"],
];
export default function Shell({ children }: { children: ReactNode }) {
  const { identity, isOwner } = useIdentity();
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const projectId = location.pathname.match(/^\/projects\/([^/]+)/)?.[1];
  const project = useResource<Project>(
    projectId ? `/api/v1/projects/${projectId}` : null,
  );
  const ready = useResource<{ ready: boolean }>("/ready");
  const nav = (
    <Box sx={{ p: 3 }}>
      <Typography variant="h6" sx={{ mb: 0.5 }}>
        MedSynth Guard
      </Typography>
      <Typography variant="caption" color="text.secondary">
        Governed data workspace
      </Typography>
      <Stack
        component="nav"
        aria-label="Primary navigation"
        sx={{ mt: 4 }}
        gap={0.5}
      >
        {navigation.map(([to, label]) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            onClick={() => setOpen(false)}
          >
            {label}
          </NavLink>
        ))}
        {isOwner && <NavLink to="/organization/members" onClick={() => setOpen(false)}>Members</NavLink>}
      </Stack>
      <Box sx={{ mt: 5 }}>
        <Typography variant="caption" color="text.secondary">
          CAPABILITIES
        </Typography>
        <Stack gap={1} sx={{ mt: 1 }}>
          <Typography variant="body2">Tabular · Stable</Typography>
          <Typography variant="body2">ECG · Beta</Typography>
          <Typography variant="body2">Imaging · Experimental</Typography>
          <Typography variant="body2">Genomics · Unavailable</Typography>
        </Stack>
      </Box>
    </Box>
  );
  return (
    <Box className="app-shell">
      <a href="#main" className="skip-link">
        Skip to content
      </a>
      <Box className="sidebar">{nav}</Box>
      <Drawer open={open} onClose={() => setOpen(false)}>
        {nav}
      </Drawer>
      <Box className="workspace">
        <AppBar
          position="static"
          color="inherit"
          elevation={0}
          sx={{ borderBottom: 1, borderColor: "divider" }}
        >
          <Toolbar>
            <Button
              className="menu-button"
              onClick={() => setOpen(true)}
              aria-label="Open navigation"
            >
              Menu
            </Button>
            <Typography sx={{ flexGrow: 1 }} color="text.secondary">
              {project.data?.name ?? "Workspace"}
            </Typography>
            <Chip
              size="small"
              variant="outlined"
              label={
                ready.loading
                  ? "Checking platform"
                  : ready.data?.ready
                    ? "Platform ready"
                    : "Platform unavailable"
              }
              color={ready.data?.ready ? "success" : "warning"}
            />
            <Button onClick={ready.reload} size="small">
              Check
            </Button>
          </Toolbar>
          <Box sx={{ px: 3, pb: 1.5 }}><IdentityControls /></Box>
        </AppBar>
        <Box component="main" id="main" tabIndex={-1} className="main-content">
          <Breadcrumbs sx={{ mb: 2 }} aria-label="Breadcrumb">
            <NavLink to="/">Workspace</NavLink>
            {project.data && (
              <NavLink to={`/projects/${projectId}`}>
                {project.data.name}
              </NavLink>
            )}
            <Typography variant="body2">
              {location.pathname === "/"
                ? "Overview"
                : location.pathname.split("/").filter(Boolean).length > 1
                  ? "Resource detail"
                  : location.pathname.slice(1)}
            </Typography>
          </Breadcrumbs>
          {project.data && (
            <Stack
              component="nav"
              aria-label="Project navigation"
              direction="row"
              gap={1}
              flexWrap="wrap"
              sx={{ mb: 3 }}
            >
              {[
                ["", "Overview"],
                ["/datasets", "Datasets"],
                ["/runs", "Synthetic runs"],
                ["/evaluations", "Evaluations"],
                ["/reports", "Reports"],
                ["/policies", "Release policies"],
                ["/compare", "Comparison"],
              ].map(([path, label]) => (
                <Button
                  key={path}
                  component={NavLink}
                  end
                  to={`/projects/${projectId}${path}`}
                >
                  {label}
                </Button>
              ))}
            </Stack>
          )}
          {ready.error && (
            <Alert severity="warning" sx={{ mb: 2 }}>
              Platform connection is unavailable. Resource errors include retry
              actions.
            </Alert>
          )}
          <Stack spacing={3}>{children}</Stack>
          <Box
            component="footer"
            sx={{ mt: 6, pt: 3, borderTop: 1, borderColor: "divider" }}
          >
            <Typography variant="body2" color="text.secondary">
              {identity?.mode === "development" ? "Development authentication bypass is active. Use OIDC for authenticated operation. " : "Organization membership controls workspace access. "}
              This engineering/research platform does not establish regulatory compliance, anonymization or clinical validity.
            </Typography>
          </Box>
        </Box>
      </Box>
    </Box>
  );
}
