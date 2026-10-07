import { Box, Button, Typography } from "@mui/material";
import { Link, useParams } from "react-router-dom";
import { useResource } from "../hooks/useResource";
import {
  ActivityView,
  PageTitle,
  Section,
  State,
  Status,
} from "../components/Workspace";
import type { Activity, Page, Project } from "../types/domain";
import DeleteProject from "../features/identity/DeleteProject";
export default function ProjectDetail() {
  const { projectId } = useParams();
  const resource = useResource<Project>(
    `/api/v1/workspace/projects/${projectId}/summary`,
  );
  const activity = useResource<Page<Activity>>(
    `/api/v1/workspace/activity?project_id=${projectId}&limit=20`,
  );
  return (
    <>
      <State {...resource} />
      {resource.data && (
        <>
          <PageTitle
            title={resource.data.name}
            description={resource.data.description}
            action={
              <Button
                component={Link}
                to={`/projects/${projectId}/datasets`}
                variant="contained"
              >
                Open datasets
              </Button>
            }
          />
          <Status value={resource.data.status} />
          <Typography color="text.secondary">Retention: artifacts remain until an owner explicitly requests deletion. No automatic expiry is configured.</Typography>
          <DeleteProject id={resource.data.id} name={resource.data.name} />
          <Box className="summary-grid">
            {[
              ["Datasets", resource.data.datasets, "datasets"],
              ["Synthetic runs", resource.data.runs, "runs"],
              ["Evaluations", resource.data.evaluations, "evaluations"],
              ["Governance reports", resource.data.reports, "reports"],
            ].map(([label, count, path]) => (
              <Section title={String(label)} key={String(path)}>
                <Typography variant="h4">{count}</Typography>
                <Button component={Link} to={`/projects/${projectId}/${path}`}>
                  View {label}
                </Button>
              </Section>
            ))}
          </Box>
          <Section title="Release governance">
            <Status value={resource.data.latest_decision ?? "NOT_EVALUATED"} />
            <Typography sx={{ mt: 1 }}>
              Latest recorded decision. Each run and evaluation retains its own
              evidence and policy version.
            </Typography>
          </Section>
          <Section title="Workflow progress">
            <Typography>
              Multiple datasets and runs may proceed independently in this
              project.
            </Typography>
            <Typography sx={{ mt: 2 }}>
              Dataset registration → Schema review → Successful synthesis →
              Completed evaluation → Policy decision → Governance report
            </Typography>
            <Typography color="text.secondary" sx={{ mt: 1 }}>
              Open a dataset or run to see its recorded progress and next
              action.
            </Typography>
          </Section>
        </>
      )}
      <Section title="Recent activity">
        <State {...activity} />
        {activity.data && <ActivityView items={activity.data.items} />}
      </Section>
    </>
  );
}
