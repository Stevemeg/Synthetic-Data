import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { signIn } from "./support/identity";

const browserURL = process.env.MEDSYNTH_BROWSER_URL || "http://127.0.0.1:5173";
test.skip(process.env.MEDSYNTH_AUTH_E2E !== "1", "Requires the real local OIDC provider and API in AUTH_MODE=oidc");
test.setTimeout(120000);


test("real OIDC PKCE, organization switch, denied deep link, CSRF and revoked logout", async ({ page }) => {
  expect((await page.request.get("http://127.0.0.1:5000/api/v1/projects")).status()).toBe(401);
  expect((await page.request.get("http://127.0.0.1:5000/internal/metrics")).status()).toBe(404);
  await signIn(page, "researcher-b");
  const me = await page.request.get("http://127.0.0.1:5000/api/v1/auth/me");
  const identity = await me.json() as { csrf_token: string; organizations: { id: string }[] };
  const created = await page.request.post("http://127.0.0.1:5000/api/v1/projects", { headers: {
    "Origin": browserURL, "X-CSRF-Token": identity.csrf_token, "X-Organization-ID": identity.organizations[0].id
  }, data: { name: "Demo organization isolation research", description: "Generated fixture workspace only" } });
  expect(created.status()).toBe(201);
  const project = await created.json() as { id: string };
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("link", { name: "Sign in", exact: true })).toBeVisible();
  expect((await page.request.get("http://127.0.0.1:5000/api/v1/projects")).status()).toBe(401);

  await signIn(page, "researcher-a");
  for (const width of [1440, 1024, 768]) {
    await page.setViewportSize({ width, height: 1000 });
    await expect(page.getByRole("combobox", { name: "Organization" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    expect((await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze()).violations).toEqual([]);
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole("combobox", { name: "Organization" }).click();
  await page.getByRole("option", { name: "Development workspace" }).click();
  await page.goto(`/projects/${project.id}`);
  await expect(page.getByText(/Resource not found/).first()).toBeVisible();
  await page.getByRole("combobox", { name: "Organization" }).click();
  await page.getByRole("option", { name: "Demo secondary research organization" }).click();
  await expect(page).toHaveURL(`${browserURL}/`);
  await page.goto("/projects");
  await expect(page.getByRole("button", { name: "Create project" })).toBeDisabled();
  const changed = await page.request.get("http://127.0.0.1:5000/api/v1/auth/me");
  const changedIdentity = await changed.json() as { csrf_token: string };
  const denied = await page.request.post("http://127.0.0.1:5000/api/v1/projects", { headers: {
    "Origin": browserURL, "X-CSRF-Token": changedIdentity.csrf_token, "X-Organization-ID": identity.organizations[0].id
  }, data: { name: "Viewer forbidden mutation" } });
  expect(denied.status()).toBe(403);
  const csrf = await page.request.post("http://127.0.0.1:5000/api/v1/projects", { data: { name: "Invalid CSRF" } });
  expect(csrf.status()).toBe(403);
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(results.violations).toEqual([]);
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("link", { name: "Sign in", exact: true })).toBeVisible();
  expect((await page.request.get("http://127.0.0.1:5000/api/v1/projects")).status()).toBe(401);
});
