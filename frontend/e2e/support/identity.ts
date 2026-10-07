import { expect, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
const root = resolve(process.cwd(), "..");
const python = process.platform === "win32" ? resolve(root, ".venv/Scripts/python.exe") : resolve(root, ".venv/bin/python");
const browserURL = process.env.MEDSYNTH_BROWSER_URL || "http://127.0.0.1:5173";
export async function signIn(page: Page, username: string) {
  const config = readFileSync(resolve(root, "backend/.work/development-identity.env"), "utf8");
  const password = config.split("\n").find((line) => line.startsWith("OIDC_DEV_USER_PASSWORD="))?.slice("OIDC_DEV_USER_PASSWORD=".length);
  if (!password) throw new Error("Run the development identity bootstrap first");
  await page.goto("/");
  await page.getByRole("link", { name: "Sign in", exact: true }).click();
  await page.locator("#password").waitFor();
  if (await page.getByRole("button", { name: "Restart login" }).count()) {
    await page.getByRole("button", { name: "Restart login" }).click();
  }
  await page.locator("#username").fill(username);
  await page.locator("#password").fill(password);
  await page.locator("#kc-login").click();
  await page.waitForURL(`${browserURL}/**`);
  // Assignment follows a real issuer/subject sign-in. The operator command cannot create sessions.
  execFileSync(python, ["-m", "backend.scripts.configure_demo_memberships"], { cwd: root, stdio: "pipe" });
  await page.reload();
  await expect(page.getByRole("heading", { name: "MedSynth Guard", exact: true }).first()).toBeVisible();
}
