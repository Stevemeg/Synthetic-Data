// @vitest-environment jsdom
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render as renderBase,
  screen,
  waitFor,
  within,
  configure,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { useState } from "react";
import {
  activity,
  artifact,
  caps,
  dataset,
  evaluation,
  job,
  overrides,
  pageOf,
  policy,
  profile,
  project,
  summary,
} from "../e2e/fixtures";
import App from "./App";
import { IdentityContext } from "./features/identity/context";
import type { ReactElement } from "react";
function render(ui: ReactElement) {
  return renderBase(<IdentityContext.Provider value={{ identity: null, organization: null, selectOrganization: () => {}, logout: async () => {}, canEdit: true, isOwner: true }}>{ui}</IdentityContext.Provider>);
}
import TabularConfiguration from "./components/TabularConfiguration";
import type { Overrides } from "./components/TabularConfiguration";
import EvaluationConfig from "./features/evaluation/EvaluationConfig";
import ReleaseView from "./features/evaluation/ReleaseView";
import { PrivacyView, UtilityView } from "./features/evaluation/Diagnostics";
import Policies from "./features/evaluation/Policies";
import { Empty, State } from "./components/Workspace";
const transport = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
}));
configure({ asyncUtilTimeout: 10000 });
vi.mock("./api/client", () => ({
  api: transport,
  errorMessage: (e: unknown) =>
    e instanceof Error ? e.message : "Request failed",
  downloadArtifact: vi.fn(),
  configureIdentity: vi.fn(),
}));
beforeEach(() => {
  vi.clearAllMocks();
  Element.prototype.scrollIntoView = vi.fn();
  window.history.replaceState({}, "", "/");
  transport.get.mockImplementation(async (path: string) => {
    if (path === "/api/v1/auth/me") return { data: { mode: "development", user: null, csrf_token: null,
      organizations: [{ id: "organization-demo", name: "Development workspace", role: "OWNER" }] } };
    if (path === "/ready") return { data: { ready: true } };
    if (path.endsWith("/capabilities")) return { data: caps };
    if (path.includes("/activity")) return { data: pageOf(activity) };
    if (path.includes("/release-policies")) return { data: pageOf([policy]) };
    if (path.includes("/policy-usage")) return { data: { [policy.id]: 1 } };
    if (path.includes("/summary") || path.endsWith(`/projects/${project.id}`))
      return { data: project };
    if (path.includes("/workspace/projects"))
      return { data: pageOf([project]) };
    if (path.endsWith(`/datasets/${dataset.id}`)) return { data: dataset };
    if (path.endsWith(`/jobs/${job.id}`)) return { data: job };
    if (path.endsWith(`/evaluations/${evaluation.id}`))
      return { data: evaluation };
    if (path.endsWith("/artifacts")) return { data: pageOf([artifact]) };
    if (path.endsWith("/reports")) return { data: pageOf([artifact]) };
    if (path.includes("/datasets")) return { data: pageOf([dataset]) };
    if (path.includes("/runs")) return { data: pageOf([job]) };
    if (path.includes("/evaluations")) return { data: pageOf([evaluation]) };
    return { data: pageOf([]) };
  });
  transport.post.mockImplementation(async (path: string) => ({
    data: path.endsWith("/preflight")
      ? profile
      : path.endsWith("/jobs")
        ? job
        : path.endsWith("/evaluations")
          ? evaluation
          : policy,
  }));
  transport.put.mockResolvedValue({ data: dataset });
});
afterEach(cleanup);

test("new policy versions preserve both bounds of an existing numeric rule", async () => {
  transport.get.mockResolvedValueOnce({
    data: pageOf([
      {
        ...policy,
        rules: {
          holdout_column_shapes: {
            minimum: 0.8,
            maximum: 0.95,
            required: true,
          },
        },
      },
    ]),
  });
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={[`/projects/${project.id}/policies`]}>
      <Routes>
        <Route path="/projects/:projectId/policies" element={<Policies />} />
      </Routes>
    </MemoryRouter>,
  );
  await screen.findByRole("heading", { name: `${policy.name} · Version 1` });
  await user.click(screen.getByRole("button", { name: "Create new version" }));
  expect(
    (screen.getByLabelText("Rule 1 threshold") as HTMLInputElement).value,
  ).toBe("0.8");
  expect(
    (screen.getByLabelText("Rule 1 upper threshold") as HTMLInputElement).value,
  ).toBe("0.95");
  await user.click(
    screen.getByRole("button", { name: "Create policy version" }),
  );
  await waitFor(() =>
    expect(transport.post).toHaveBeenCalledWith(
      `/api/v1/projects/${project.id}/release-policies`,
      expect.objectContaining({
        version: 2,
        rules: {
          holdout_column_shapes: {
            minimum: 0.8,
            maximum: 0.95,
            required: true,
            when: "ALWAYS",
          },
        },
      }),
    ),
  );
});
test("stable project navigation and deep-link dataset reload", async () => {
  const user = userEvent.setup();
  render(<App />);
  await user.click(await screen.findByRole("link", { name: project.name }));
  await screen.findByRole("heading", { name: project.name });
  expect(window.location.pathname).toBe(`/projects/${project.id}`);
  await user.click(screen.getByRole("link", { name: "Open datasets" }));
  await user.click(await screen.findByRole("link", { name: dataset.name }));
  await screen.findByRole("table", { name: "Dataset schema governance" });
  expect(window.location.pathname).toBe(`/datasets/${dataset.id}`);
  cleanup();
  render(<App />);
  await screen.findByRole("heading", { name: dataset.name });
}, 20000);
test("schema review edits annotations and protects free-text modelling", async () => {
  const user = userEvent.setup();
  const changed = vi.fn();
  function Review() {
    const [values, setValues] = useState<Overrides>(overrides);
    return (
      <TabularConfiguration
        profile={profile}
        overrides={values}
        onChange={(v) => {
          changed(v);
          setValues(v);
        }}
      />
    );
  }
  render(<Review />);
  const age = screen.getByRole("row", { name: /age numerical/ });
  await user.click(
    within(age).getByRole("checkbox", { name: "age Quasi-identifier" }),
  );
  expect(changed.mock.calls.at(-1)?.[0].age.annotations).toEqual([]);
  await user.click(
    screen.getByRole("combobox", { name: /clinical_notes role/ }),
  );
  expect(
    screen.getByRole("option", { name: "Model" }).getAttribute("aria-disabled"),
  ).toBe("true");
});
test("generation requires review and sends bounded engine configuration", async () => {
  const user = userEvent.setup();
  window.history.replaceState({}, "", `/datasets/${dataset.id}/generate`);
  render(<App />);
  await screen.findByRole("heading", { name: "Dataset context" });
  await user.click(screen.getByRole("button", { name: "Continue" }));
  await user.click(screen.getByRole("button", { name: "Continue" }));
  await user.click(screen.getByRole("combobox", { name: "Engine" }));
  await user.click(screen.getByRole("option", { name: "CTGAN · Beta" }));
  expect(screen.getByText(/Training typically takes longer/)).toBeTruthy();
  await user.click(screen.getByRole("button", { name: "Continue" }));
  await user.click(screen.getByText("Advanced configuration"));
  fireEvent.change(screen.getByLabelText("Epochs"), { target: { value: "1" } });
  await user.click(screen.getByRole("button", { name: "Continue" }));
  expect(transport.post).not.toHaveBeenCalled();
  await user.click(screen.getByRole("button", { name: "Continue" }));
  await user.click(
    screen.getByRole("button", { name: "Submit synthetic run" }),
  );
  await screen.findByRole("heading", { name: "Run summary" });
  expect(transport.post).toHaveBeenCalledWith(
    `/api/v1/projects/${project.id}/jobs`,
    expect.objectContaining({
      engine: "ctgan",
      requested_samples: 400,
      configuration: {
        holdout_fraction: 0.2,
        split_seed: 42,
        epochs: 1,
        batch_size: 100,
      },
    }),
    expect.objectContaining({
      headers: { "Idempotency-Key": expect.any(String) },
    }),
  );
}, 20000);
test("FULL configuration needs explicit disclosure confirmation and excludes invalid targets", async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={[`/runs/${job.id}/evaluate`]}>
      <Routes>
        <Route path="/runs/:jobId/evaluate" element={<EvaluationConfig />} />
        <Route
          path="/evaluations/:id"
          element={<div>Evaluation submitted</div>}
        />
      </Routes>
    </MemoryRouter>,
  );
  await screen.findByRole("combobox", { name: "Evaluation profile" });
  await user.click(
    screen.getByRole("combobox", { name: "Evaluation profile" }),
  );
  await user.click(screen.getByRole("option", { name: /Full ·/ }));
  await user.click(
    screen.getByRole("checkbox", { name: "Configure disclosure analysis" }),
  );
  await user.click(
    screen.getByRole("button", { name: "Use annotation suggestions" }),
  );
  expect(
    (
      screen.getByRole("button", {
        name: "Review evaluation",
      }) as HTMLButtonElement
    ).disabled,
  ).toBe(true);
  await user.click(
    screen.getByRole("checkbox", {
      name: "Confirm selected known and sensitive attributes",
    }),
  );
  await user.click(
    screen.getByRole("checkbox", { name: "Configure ML utility" }),
  );
  await user.click(screen.getByRole("combobox", { name: "Target column" }));
  expect(screen.queryByRole("option", { name: "patient_id" })).toBeNull();
  expect(screen.queryByRole("option", { name: "clinical_notes" })).toBeNull();
  expect(screen.queryByRole("option", { name: "age" })).toBeNull();
  await user.click(screen.getByRole("option", { name: "readmitted" }));
  await user.click(screen.getByRole("button", { name: "Review evaluation" }));
  await user.click(screen.getByRole("button", { name: "Submit evaluation" }));
  await screen.findByText("Evaluation submitted");
  expect(transport.post).toHaveBeenCalledWith(
    `/api/v1/generation-jobs/${job.id}/evaluations`,
    expect.objectContaining({
      profile: "FULL",
      privacy: {
        known_columns: ["age"],
        sensitive_columns: ["diagnosis_group"],
        continuous_columns: ["age"],
        num_discrete_bins: 10,
        estimated: false,
      },
    }),
  );
}, 20000);
test("release decision gives rule applicability and reason without a guarantee", () => {
  render(<ReleaseView value={summary.release} />);
  expect(screen.getByText("Review required")).toBeTruthy();
  const row = screen.getByRole("row", { name: /DCR Overfitting Protection/ });
  expect(row.textContent).toContain("Insufficient data");
  expect(row.textContent).toContain(
    "Evidence is not eligible for release gating",
  );
  expect(screen.getByText(/not a guarantee of anonymity/)).toBeTruthy();
});
test("privacy retains exact overlap and advisory methodology; utility retains TRTR/TSTR", () => {
  render(
    <>
      <PrivacyView summary={summary} />
      <UtilityView value={summary.utility} />
    </>,
  );
  expect(
    screen.getByText(
      "Advisory only. This score cannot satisfy a required numeric release rule.",
    ),
  ).toBeTruthy();
  expect(screen.getByText(/Matching generated rows: 0 \/ 400/)).toBeTruthy();
  expect(
    screen.getByRole("rowheader", {
      name: "Synthetic median DCR",
    }),
  ).toBeTruthy();
  expect(
    screen.getByRole("rowheader", {
      name: "Closer-to-training fraction",
    }),
  ).toBeTruthy();
  expect(screen.queryByText("NaN", { exact: true })).toBeNull();
  expect(
    screen.getByRole("table", { name: "TRTR and TSTR utility" }),
  ).toBeTruthy();
  expect(screen.getAllByText(/^TSTR\/TRTR F1 ratio: 0.915$/)).toHaveLength(2);
});
test("policy builder creates a new immutable version without JSON", async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter initialEntries={[`/projects/${project.id}/policies`]}>
      <Routes>
        <Route path="/projects/:projectId/policies" element={<Policies />} />
      </Routes>
    </MemoryRouter>,
  );
  await screen.findByRole("heading", { name: `${policy.name} · Version 1` });
  await user.click(screen.getByRole("button", { name: "Create new version" }));
  expect((screen.getByLabelText("Version") as HTMLInputElement).value).toBe(
    "2",
  );
  await user.click(
    screen.getByRole("button", { name: "Create policy version" }),
  );
  await waitFor(() =>
    expect(transport.post).toHaveBeenCalledWith(
      `/api/v1/projects/${project.id}/release-policies`,
      expect.objectContaining({
        version: 2,
        rules: expect.objectContaining({
          structural_validation: {
            equals: true,
            required: true,
            when: "ALWAYS",
          },
        }),
      }),
    ),
  );
  expect(screen.queryByText("Edit version 1")).toBeNull();
});
test("loading, empty and persistent retry error surfaces", () => {
  const retry = vi.fn();
  const view = render(<State loading error="" reload={retry} />);
  expect(screen.getByRole("status")).toBeTruthy();
  expect(screen.getByRole("progressbar", { name: "Loading workspace" })).toBeTruthy();
  view.rerender(
    <State
      loading={false}
      error="Platform unavailable · Request abc"
      reload={retry}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(retry).toHaveBeenCalledOnce();
  view.rerender(
    <Empty title="No evaluations yet">
      Evaluate a successful tabular run.
    </Empty>,
  );
  expect(screen.getByText("No evaluations yet")).toBeTruthy();
});
