import { expect, test } from "@playwright/test";
import { createHash } from "node:crypto";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import { signIn } from "./support/identity";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
import AxeBuilder from "@axe-core/playwright";

// Opt-in: requires the documented local API, worker and generated demo bootstrap.
test("live governed workflow uses the local API and worker and verifies downloaded report", async ({
  page,
  playwright,
}) => {
  test.setTimeout(240000);
  const base = "http://127.0.0.1:5000/api/v1";
  let headers: Record<string, string> = {};
  if (process.env.MEDSYNTH_AUTH_E2E === "1") {
    await signIn(page, "researcher-a");
    if (await page.getByRole("combobox", { name: "Organization" }).count()) {
      await page.getByRole("combobox", { name: "Organization" }).click();
      await page.getByRole("option", { name: "Development workspace" }).click();
    }
    const identity = await (await page.request.get(`${base}/auth/me`)).json() as { csrf_token: string; organizations: { id: string; name: string }[] };
    const organization = identity.organizations.find((v) => v.name === "Development workspace");
    const cookie = (await page.context().cookies()).find((v) => v.name === "medsynth_session");
    if (!organization || !cookie) throw new Error("Real owner session is required");
    const origin = process.env.MEDSYNTH_BROWSER_URL || "http://127.0.0.1:5173";
    headers = { "X-Organization-ID": organization.id, "X-CSRF-Token": identity.csrf_token, "Origin": origin };
    const root = resolve(process.cwd(), "..");
    const python = process.platform === "win32" ? resolve(root, ".venv/Scripts/python.exe") : resolve(root, ".venv/bin/python");
    execFileSync(python, ["-m", "backend.scripts.create_demo_project", "--authenticated"], {
      cwd: root, stdio: "pipe", timeout: 180000,
      env: { ...process.env, MEDSYNTH_DEMO_SESSION: cookie.value, MEDSYNTH_DEMO_CSRF: identity.csrf_token, MEDSYNTH_DEMO_ORGANIZATION: organization.id, MEDSYNTH_DEMO_ORIGIN: origin }
    });
  }
  const request = await playwright.request.newContext({ storageState: await page.context().storageState(), extraHTTPHeaders: headers });

  const projects = await request.get(`${base}/workspace/projects?limit=100`);
  expect(
    projects.ok(),
    "Start API and bootstrap the generated fake-data demo first",
  ).toBeTruthy();
  const p = (await projects.json()).items.find(
    (v: { name: string; description: string }) =>
      v.name === "Cardio Readmission Research" &&
      v.description.includes("fake data"),
  );
  expect(p, "Run python -m backend.scripts.create_demo_project").toBeTruthy();
  const datasets = await request.get(
    `${base}/workspace/datasets?project_id=${p.id}`,
  );
  const d = (await datasets.json()).items[0];
  await mkdir("../docs/screenshots", { recursive: true });
  await page.goto(`/projects/${p.id}`);
  await expect(
    page.getByRole("heading", { name: p.name, exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "../docs/screenshots/project-overview.png",
    fullPage: true,
  });
  await page.getByRole("link", { name: "Open datasets" }).click();
  await page.getByRole("link", { name: d.name, exact: true }).click();
  await page
    .getByRole("button", { name: "Run preflight", exact: true })
    .click();
  await expect(page.getByText(/Preflight completed/)).toBeVisible();
  await page.getByRole("button", { name: "Save governance" }).click();
  await expect(page.getByText(/Schema governance saved/)).toBeVisible();
  await page.screenshot({
    path: "../docs/screenshots/dataset-governance.png",
    fullPage: true,
  });
  await page.getByRole("link", { name: "Start synthesis" }).click();
  for (let i = 0; i < 4; i++)
    await page.getByRole("button", { name: "Continue", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Review run" })).toBeVisible();
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.getByRole("button", { name: "Submit synthetic run" }).click();
  await expect(
    page.getByRole("link", { name: "Evaluate dataset" }),
  ).toBeVisible({ timeout: 120000 });
  const run = page.url().split("/").pop();
  await page.reload();
  await expect(
    page.getByRole("link", { name: "Evaluate dataset" }),
  ).toBeVisible();
  await page.screenshot({
    path: "../docs/screenshots/synthetic-run.png",
    fullPage: true,
  });
  await page.getByRole("link", { name: "Evaluate dataset" }).click();
  await page.getByRole("combobox", { name: "Evaluation profile" }).click();
  await page.getByRole("option", { name: /Full/ }).click();
  await page.getByRole("combobox", { name: "Entity group key" }).click();
  await page.getByRole("option", { name: "patient_id", exact: true }).click();
  await page
    .getByRole("checkbox", { name: "Configure disclosure analysis" })
    .check();
  await page
    .getByRole("button", { name: "Use annotation suggestions" })
    .click();
  await expect(
    page.getByRole("checkbox", { name: "Known age_group", exact: true }),
  ).toBeChecked();
  await page
    .getByRole("checkbox", {
      name: "Confirm selected known and sensitive attributes",
    })
    .check();
  await page
    .getByRole("checkbox", { name: "Configure ML utility", exact: true })
    .check();
  await page.getByRole("combobox", { name: "Target column" }).click();
  await page.getByRole("option", { name: "readmitted", exact: true }).click();
  await page.getByRole("combobox", { name: "Release policy version" }).click();
  await page
    .getByRole("option", { name: /Illustrative Research Demo Policy/ })
    .click();
  await page.getByRole("button", { name: "Review evaluation" }).click();
  await page.getByRole("button", { name: "Submit evaluation" }).click();
  await expect(
    page.getByRole("button", { name: "Generate governance report" }),
  ).toBeVisible({ timeout: 120000 });
  const evaluation = page.url().split("/").pop();
  await expect(
    page.getByRole("table", { name: "Policy decision explanation" }),
  ).toBeVisible();
  await expect(
    page.getByRole("rowheader", { name: "Synthetic median DCR", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("rowheader", { name: "Baseline median DCR", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("rowheader", {
      name: "Closer-to-training fraction",
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.getByText("NaN", { exact: true })).toHaveCount(0);
  await page
    .getByRole("button", { name: "Generate governance report" })
    .click();
  await expect(
    page.getByRole("button", { name: "Download Governance report" }),
  ).toBeVisible();
  await page.screenshot({
    path: "../docs/screenshots/evaluation-dashboard.png",
    fullPage: true,
  });
  await page
    .getByRole("heading", { name: "Release policy", exact: true })
    .locator("..")
    .screenshot({ path: "../docs/screenshots/release-decision.png" });
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  const downloadEvent = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Download Governance report" })
    .click();
  const download = await downloadEvent;
  const bytes = await readFile((await download.path())!);
  const reports = (
    await (
      await request.get(`${base}/evaluations/${evaluation}/reports`)
    ).json()
  ).items;
  const report = reports.find(
    (v: { artifact_type: string }) => v.artifact_type === "GOVERNANCE_REPORT",
  );
  expect(bytes.length).toBe(report.size_bytes);
  expect(createHash("sha256").update(bytes).digest("hex")).toBe(report.sha256);
  expect(download.suggestedFilename()).toMatch(
    /^medsynth-guard_.*governance-report\.html$/,
  );
  const html = bytes.toString("utf8");
  expect(html).not.toMatch(
    /HIPAA compliant|GDPR compliant|zero privacy risk|100% anonymous|safe to share|re-identification impossible|storage_key|source_path/i,
  );
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Evaluation summary" }),
  ).toBeVisible();
  await page.goto(`/runs/${run}`);
  await expect(
    page.getByRole("link", { name: "Evaluate dataset" }),
  ).toBeVisible();
  if (process.env.MEDSYNTH_AUTH_E2E === "1") {
    const samples: number[] = [];
    let failures = 0;
    const start = performance.now();
    for (let batch = 0; batch < 10; batch++) {
      await Promise.all(Array.from({ length: 10 }, async (_, index) => {
        const at = performance.now();
        const response = await request.get(index % 2 ? `${base}/datasets/${d.id}` : `${base}/workspace/projects?limit=20`);
        if (response.status() !== 200) failures++;
        samples.push(performance.now() - at);
      }));
    }
    samples.sort((a, b) => a - b);
    await mkdir("../backend/.work", { recursive: true });
    await writeFile("../backend/.work/authenticated-load-smoke.json", JSON.stringify({ requests: 100, concurrency: 10, failures, duration_ms: performance.now() - start, p50_ms: samples[49], p95_ms: samples[94], maximum_ms: samples[99], scope: "Local authenticated project lists and dataset metadata; no enterprise scale claim" }, null, 2));
    expect(failures).toBe(0);
    if (process.env.MEDSYNTH_CONTAINER_RESTART_E2E === "1") {
      const root = resolve(process.cwd(), "..");
      const python = process.platform === "win32" ? resolve(root, ".venv/Scripts/python.exe") : resolve(root, ".venv/bin/python");
      execFileSync(python, ["-m", "backend.scripts.verify_operations"], { cwd: root, stdio: "pipe", timeout: 30000 });
      execFileSync("docker", ["compose", "-f", "compose.yaml", "-f", "compose.security.yaml", "-f", "compose.runtime.yaml", "restart", "api", "worker"], { cwd: resolve(process.cwd(), ".."), stdio: "pipe", timeout: 60000 });
      await expect.poll(async () => {
        try { return (await request.get("http://127.0.0.1:5000/ready")).status(); }
        catch { return 0; }
      }, { timeout: 60000, intervals: [1000, 2000, 3000] }).toBe(200);
      expect((await request.get(`${base}/evaluations/${evaluation}`)).status()).toBe(200);
      const afterRestart = await request.get(`${base}/artifacts/${report.id}/download`);
      expect(afterRestart.status()).toBe(200);
      expect(createHash("sha256").update(await afterRestart.body()).digest("hex")).toBe(report.sha256);
      await page.goto(`/evaluations/${evaluation}`);
      await expect(page.getByRole("heading", { name: "Evaluation summary" })).toBeVisible();
    }
  }
  await page.setContent(html);
  await page.screenshot({ path: "../docs/screenshots/governance-report-cover.png" });
  await page.screenshot({
    path: "../docs/screenshots/governance-report.png",
    fullPage: true,
  });
  await request.dispose();
});
