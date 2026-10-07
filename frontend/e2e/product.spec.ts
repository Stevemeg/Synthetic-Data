import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import {
  activity,
  artifact,
  caps,
  dataset,
  evaluation,
  job,
  pageOf,
  policy,
  profile,
  project,
  summary,
} from "./fixtures";
async function mock(page: Page) {
  await page.route("http://127.0.0.1:5000/**", async (route) => {
    const req = route.request();
    const path = new URL(req.url()).pathname;
    let data: unknown;
    let status = 200;
    if (path === "/ready") data = { ready: true };
    else if (path === "/api/v1/auth/me") data = { mode: "development", user: null, csrf_token: null,
      organizations: [{ id: "organization-demo", name: "Development workspace", role: "OWNER" }] };
    else if (path.endsWith("/capabilities")) data = caps;
    else if (path.endsWith("/download")) {
      await route.fulfill({
        status: 200,
        contentType: "text/html",
        headers: {
          "Content-Disposition": `attachment; filename="${artifact.filename}"`,
        },
        body: '<!doctype html><html lang="en"><title>Governance report</title><h1>Governance report</h1><p>Persisted aggregate evidence. No clinical validity guarantee.</p></html>',
      });
      return;
    } else if (path.endsWith("/governance-report")) data = artifact;
    else if (path.endsWith("/preflight")) data = profile;
    else if (path.endsWith("/governance")) data = dataset;
    else if (path.endsWith("/summary")) data = project;
    else if (path.endsWith("/policy-usage")) data = { [policy.id]: 1 };
    else if (path.endsWith("/compare"))
      data = {
        rows: [
          {
            evaluation_id: "evaluation-demo",
            engine: "gaussian_copula",
            results: summary,
          },
          {
            evaluation_id: "evaluation-second",
            engine: "ctgan",
            results: summary,
          },
        ],
      };
    else if (path.endsWith("/release-policies"))
      data = req.method() === "POST" ? policy : pageOf([policy]);
    else if (path.endsWith("/artifacts"))
      data = pageOf([
        {
          ...artifact,
          artifact_type: "SYNTHETIC_DATASET",
          filename: "medsynth-guard_demo_synthetic.csv",
        },
        {
          ...artifact,
          id: "model-artifact",
          artifact_type: "SYNTHESIS_MODEL",
          downloadable: false,
        },
      ]);
    else if (path.endsWith("/reports")) data = pageOf([artifact]);
    else if (path.endsWith("/activity")) data = pageOf(activity);
    else if (path.endsWith("/projects"))
      data = req.method() === "POST" ? project : pageOf([project]);
    else if (path.endsWith(`/projects/${project.id}`)) data = project;
    else if (path.endsWith(`/datasets/${dataset.id}`)) data = dataset;
    else if (path.endsWith("/datasets")) data = pageOf([dataset]);
    else if (path.endsWith(`/jobs/${job.id}`)) data = job;
    else if (path.endsWith("/jobs") || path.endsWith("/runs"))
      data = req.method() === "POST" ? job : pageOf([job]);
    else if (
      path.endsWith(`/evaluations/${evaluation.id}`) ||
      path.endsWith("/evaluations/evaluation-second")
    )
      data = evaluation;
    else if (path.endsWith("/evaluations"))
      data =
        req.method() === "POST"
          ? evaluation
          : pageOf([
              evaluation,
              {
                ...evaluation,
                id: "evaluation-second",
                configuration_json: { generation_engine: "ctgan" },
              },
            ]);
    else {
      status = 404;
      data = {
        error: {
          message: "Resource does not exist",
          request_id: "fixture-request",
          code: "NOT_FOUND",
        },
      };
    }
    await route.fulfill({ status, json: data });
  });
}
test.beforeEach(async ({ page }) => {
  await mock(page);
});
test("project → dataset → reviewed generation → run → FULL evaluation → evidence → report", async ({
  page,
}) => {
  await page.goto("/projects");
  await page.getByRole("link", { name: project.name, exact: true }).click();
  await expect(
    page.getByRole("heading", { name: project.name, exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Open datasets" }).click();
  await page.getByRole("link", { name: dataset.name, exact: true }).click();
  await expect(
    page.getByRole("table", { name: "Dataset schema governance" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Run preflight", exact: true })
    .click();
  await expect(
    page.getByText("Dataset compatible for schema review"),
  ).toBeVisible();
  await page.getByRole("button", { name: "Save governance" }).click();
  await expect(page.getByText(/Schema governance saved/)).toBeVisible();
  await page.getByRole("link", { name: "Start synthesis" }).click();
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await expect(
    page.getByText("Fast statistical baseline.", { exact: false }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.getByLabel("Rows to generate").fill("400");
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Review run" })).toBeVisible();
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  const generationRequest = page.waitForRequest(
    (r) => r.method() === "POST" && r.url().endsWith("/jobs"),
  );
  await page.getByRole("button", { name: "Submit synthetic run" }).click();
  expect((await generationRequest).postDataJSON()).toMatchObject({
    dataset_id: dataset.id,
    engine: "gaussian_copula",
    requested_samples: 400,
  });
  await expect(
    page.getByRole("heading", { name: "Run summary" }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Structural validation", exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Evaluate dataset" }).click();
  await page.getByRole("combobox", { name: "Evaluation profile" }).click();
  await page.getByRole("option", { name: /Full ·/ }).click();
  await page
    .getByRole("checkbox", { name: "Configure disclosure analysis" })
    .check();
  await page
    .getByRole("button", { name: "Use annotation suggestions" })
    .click();
  await page
    .getByRole("checkbox", {
      name: "Confirm selected known and sensitive attributes",
    })
    .check();
  await page
    .getByRole("checkbox", { name: "Configure ML utility", exact: true })
    .check();
  await page.getByRole("combobox", { name: "Target column" }).click();
  await expect(
    page.getByRole("option", { name: "patient_id", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("option", { name: "readmitted", exact: true }).click();
  await page.getByRole("button", { name: "Review evaluation" }).click();
  const evaluationRequest = page.waitForRequest(
    (r) => r.method() === "POST" && r.url().endsWith("/evaluations"),
  );
  await page.getByRole("button", { name: "Submit evaluation" }).click();
  expect((await evaluationRequest).postDataJSON()).toMatchObject({
    profile: "FULL",
    privacy: { known_columns: ["age"], sensitive_columns: ["diagnosis_group"] },
    utility: { task: "BINARY_CLASSIFICATION", target: "readmitted" },
  });
  await expect(
    page.getByRole("heading", { name: "Evaluation summary" }),
  ).toBeVisible();
  await expect(
    page.getByRole("table", { name: "Policy decision explanation" }),
  ).toBeVisible();
  await expect(
    page.getByText(
      "Advisory only. This score cannot satisfy a required numeric release rule.",
    ),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Generate governance report" })
    .click();
  const downloadPromise = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Download Governance report" })
    .click();
  expect((await downloadPromise).suggestedFilename()).toBe(artifact.filename);
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "ML utility", exact: true }),
  ).toBeVisible();
});
for (const width of [1440, 1024, 768])
  test(`visual, accessibility and responsive resource pages at ${width}`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 1000 });
    for (const [path, name] of [
      [`/projects/${project.id}`, "project-overview"],
      [`/datasets/${dataset.id}`, "dataset-schema"],
      [`/runs/${job.id}`, "run-detail"],
      [`/evaluations/${evaluation.id}`, "evaluation-detail"],
    ]) {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await expect(page.getByText("Loading workspace…")).toHaveCount(0);
      await expect(page.getByText("Platform ready")).toBeVisible();
      const accessibility = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze();
      expect(accessibility.violations).toEqual([]);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      ).toBe(true);
      await expect(page).toHaveScreenshot(`${name}-${width}.png`, {
        fullPage: true,
        animations: "disabled",
      });
    }
    if (width === 768) {
      await page.getByRole("button", { name: "Open navigation" }).click();
      await expect(
        page.getByRole("navigation", { name: "Primary navigation" }),
      ).toBeVisible();
      await page.keyboard.press("Escape");
    }
  });
test("keyboard dialog, deep links and compatible comparison", async ({
  page,
}) => {
  await page.goto("/projects");
  await page.getByRole("button", { name: "Create project" }).click();
  await expect(page.getByLabel("Project name")).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("button", { name: "Create project" }),
  ).toBeFocused();
  await page.goto(`/projects/${project.id}/compare`);
  await page.getByRole("checkbox").first().check();
  await page.getByRole("checkbox").nth(1).check();
  await page
    .getByRole("button", { name: "Compare selected evaluations" })
    .click();
  await expect(
    page.getByRole("table", { name: "Independent model comparison" }),
  ).toBeVisible();
  await expect(
    page.getByRole("rowheader", { name: "CTGAN", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "../docs/screenshots/model-comparison.png",
    fullPage: true,
  });
});

for (const width of [1440, 1024, 768])
  test(`forms, dialogs and keyboard accessibility at ${width}`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto("/projects");
    await page.getByRole("button", { name: "Create project" }).click();
    await expect(page.getByLabel("Project name")).toBeFocused();
    expect(
      (
        await new AxeBuilder({ page })
          .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
          .analyze()
      ).violations,
    ).toEqual([]);
    await page.keyboard.press("Shift+Tab");
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(
      page.getByRole("button", { name: "Create project" }),
    ).toBeFocused();
    await page.goto(`/datasets/${dataset.id}/generate`);
    await expect(
      page.getByRole("heading", { name: "Create synthetic run" }),
    ).toBeVisible();
    for (let i = 0; i < 3; i++)
      await page.getByRole("button", { name: "Continue", exact: true }).click();
    await page.getByText("Advanced configuration", { exact: true }).click();
    await expect(page.getByLabel("Holdout fraction")).toBeVisible();
    expect(
      (
        await new AxeBuilder({ page })
          .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
          .analyze()
      ).violations,
    ).toEqual([]);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.goto(`/runs/${job.id}/evaluate`);
    await page.getByRole("combobox", { name: "Evaluation profile" }).click();
    await page.getByRole("option", { name: /Full/ }).click();
    await page
      .getByRole("checkbox", { name: "Configure disclosure analysis" })
      .check();
    await page
      .getByRole("checkbox", { name: "Configure ML utility", exact: true })
      .check();
    expect(
      (
        await new AxeBuilder({ page })
          .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
          .analyze()
      ).violations,
    ).toEqual([]);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  });
test("incompatible comparison explains why and clears equivalent results", async ({
  page,
}) => {
  await page.route("**/evaluations/compare", (route) =>
    route.fulfill({
      status: 400,
      json: {
        error: {
          code: "EVALUATION_COMPARISON_INCOMPATIBLE",
          message:
            "Source, split, task, profile or policy configurations differ",
          request_id: "comparison-request",
        },
      },
    }),
  );
  await page.goto(`/projects/${project.id}/compare`);
  await page.getByRole("checkbox").first().check();
  await page.getByRole("checkbox").nth(1).check();
  await page
    .getByRole("button", { name: "Compare selected evaluations" })
    .click();
  await expect(
    page.getByText(/Comparison unavailable.*configurations differ/),
  ).toBeVisible();
  await expect(
    page.getByRole("table", { name: "Independent model comparison" }),
  ).toHaveCount(0);
});
