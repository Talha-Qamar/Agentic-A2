import { expect, test } from "@playwright/test";
import { newUser } from "./helpers";

test("scout finds jobs with decisions; another user cannot see them (tenant isolation)", async ({ page, browser }) => {
  await newUser(page);
  await page.getByTestId("advance").click();
  await page.getByTestId("scout-now").click();
  await expect(page.getByTestId("inbox-row").first()).toBeVisible({ timeout: 90_000 });
  const jobs = await (await page.request.get("/api/jobs")).json();
  expect(jobs.length).toBeGreaterThan(0);
  const other = await browser.newPage();
  await newUser(other);
  const r = await other.request.get(`/api/jobs/${jobs[0].job_id}`);
  expect(r.status()).toBe(404);
  await other.close();
});
