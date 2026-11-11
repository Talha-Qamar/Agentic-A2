import { expect, Page } from "@playwright/test";
import fs from "fs";
import path from "path";

/** A job from the dev set (synthetic, labelled) that the stub pipeline takes to the approval step. */
export function devJob(index = 0): string {
  const lines = fs.readFileSync(path.resolve(process.cwd(), "../../evals/datasets/dev_set.jsonl"), "utf8").trim().split("\n");
  const jobs = lines.map((l) => JSON.parse(l)).filter((j) => j.persona === "ai_ml_engineer" && j.labels.gold_decision === "bid" && j.budget_type === "fixed");
  return jobs[index].job_id;
}

export async function newUser(page: Page) {
  const email = `pw-${Date.now()}-${Math.floor(Math.random() * 1e6)}@test.local`;
  await page.goto("/login");
  await page.getByRole("button", { name: "Create account" }).first().click();
  await page.locator("input").first().fill("Playwright");
  await page.getByTestId("email").fill(email);
  await page.getByTestId("password").fill("pw-password-123");
  await page.getByTestId("login-submit").click();
  await page.waitForURL(/onboarding/);
  await page.getByTestId("persona-ai_ml_engineer").click();
  await page.getByTestId("onboard-continue").click();
  await page.waitForURL(/inbox/);
  return email;
}

export async function analyseToApproval(page: Page, jobId: string) {
  await page.getByTestId("job-id-input").fill(jobId);
  await page.getByTestId("analyse-job").click();
  await expect(page.getByTestId("approvals-panel")).toBeVisible({ timeout: 90_000 });
  await page.getByTestId("open-approval").first().click();
  await page.waitForURL(/studio/);
  await expect(page.getByTestId("preview")).toBeVisible();
}
