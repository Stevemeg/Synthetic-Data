import { lazy, Suspense } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { CssBaseline, ThemeProvider } from "@mui/material";
import { theme } from "./theme";
import Shell from "./layouts/Shell";
import { State } from "./components/Workspace";
import { IdentityProvider, EditorRoute } from "./features/identity/Identity";
const Overview = lazy(() => import("./pages/Overview"));
const Projects = lazy(() => import("./pages/Projects"));
const ProjectDetail = lazy(() => import("./pages/ProjectDetail"));
const Inventory = lazy(() => import("./pages/Inventory"));
const DatasetDetail = lazy(() => import("./features/datasets/DatasetDetail"));
const Generation = lazy(() => import("./features/generation/Generation"));
const RunDetail = lazy(() => import("./features/generation/RunDetail"));
const EvaluationConfig = lazy(
  () => import("./features/evaluation/EvaluationConfig"),
);
const EvaluationDetail = lazy(
  () => import("./features/evaluation/EvaluationDetail"),
);
const Policies = lazy(() => import("./features/evaluation/Policies"));
const Comparison = lazy(() => import("./features/evaluation/Comparison"));
const Members = lazy(() => import("./features/identity/Members"));
export default function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter>
        <IdentityProvider>
        <Shell>
          <Suspense fallback={<State loading error="" reload={() => {}} />}>
            <Routes>
              <Route path="/organization/members" element={<Members />} />
              <Route path="/" element={<Overview />} />
              <Route path="/projects" element={<Projects />} />
              <Route path="/projects/:projectId" element={<ProjectDetail />} />
              {["datasets", "runs", "evaluations", "reports"].map((kind) => (
                <Route
                  key={kind}
                  path={`/${kind}`}
                  element={<Inventory kind={kind} />}
                />
              ))}
              {["datasets", "runs", "evaluations", "reports"].map((kind) => (
                <Route
                  key={kind}
                  path={`/projects/:projectId/${kind}`}
                  element={<Inventory kind={kind} />}
                />
              ))}
              <Route path="/datasets/:datasetId" element={<DatasetDetail />} />
              <Route
                path="/datasets/:datasetId/generate"
                element={<EditorRoute><Generation /></EditorRoute>}
              />
              <Route path="/runs/:jobId" element={<RunDetail />} />
              <Route
                path="/runs/:jobId/evaluate"
                element={<EditorRoute><EvaluationConfig /></EditorRoute>}
              />
              <Route
                path="/evaluations/:evaluationId"
                element={<EvaluationDetail />}
              />
              <Route
                path="/projects/:projectId/policies"
                element={<Policies />}
              />
              <Route
                path="/projects/:projectId/compare"
                element={<Comparison />}
              />
              <Route path="*" element={<Overview notFound />} />
            </Routes>
          </Suspense>
        </Shell>
        </IdentityProvider>
      </BrowserRouter>
    </ThemeProvider>
  );
}
