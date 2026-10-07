import { Alert, Box, Button, Typography } from "@mui/material";
import { Link } from "react-router-dom";
import { useResource } from "../hooks/useResource";
import type { Activity, Page, Project } from "../types/domain";
import {
  ActivityView,
  DataTable,
  Empty,
  PageTitle,
  Section,
  State,
  Status,
} from "../components/Workspace";
export default function Overview({ notFound = false }: { notFound?: boolean }) {
  const projects = useResource<Page<Project>>(
    "/api/v1/workspace/projects?limit=5",
  );
  const activity = useResource<Page<Activity>>(
    "/api/v1/workspace/activity?limit=10",
  );
  return (
    <>
      {notFound && (
        <Alert severity="info">
          This page does not exist. Use workspace navigation to open a resource.
        </Alert>
      )}
      <PageTitle
        title="MedSynth Guard"
        description="Governed synthetic health data generation and evaluation."
        action={
          <Button component={Link} to="/projects" variant="contained">
            Open projects
          </Button>
        }
      />
      <Section title="Your workflow">
        <Typography>
          Project → Source dataset → Preflight & schema governance → Generation
          → Evaluation → Evidence → Release policy → Governance report →
          Controlled export
        </Typography>
      </Section>
      <Box className="summary-grid">
        {[
          ["Clinical tabular", "Stable"],
          ["Tabular evaluation", "Beta"],
          ["ECG generation", "Beta"],
          ["Medical imaging", "Experimental"],
        ].map(([title, status]) => (
          <Section key={title} title={title}>
            <Status value={status} />
          </Section>
        ))}
      </Box>
      <Section title="Recent projects">
        <State {...projects} />
        {projects.data &&
          (projects.data.items.length ? (
            <DataTable
              label="Recent projects"
              headers={[
                "Project",
                "Datasets",
                "Runs",
                "Evaluations",
                "Release decision",
              ]}
              rows={projects.data.items.map((p) => [
                <Link to={`/projects/${p.id}`}>{p.name}</Link>,
                p.datasets,
                p.runs,
                p.evaluations,
                <Status value={p.latest_decision ?? "NOT_EVALUATED"} />,
              ])}
            />
          ) : (
            <Empty title="No projects yet">
              Create a project to organize datasets, runs and governance
              evidence.
            </Empty>
          ))}
      </Section>
      <Section title="Recent activity">
        <State {...activity} />
        {activity.data && <ActivityView items={activity.data.items} />}
      </Section>
    </>
  );
}
