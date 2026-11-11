import { expect, test } from "@playwright/test";
import { analyseToApproval, devJob, newUser } from "./helpers";

test("owner publishes a run trace; it opens logged-out at /t/:id, and is private again after unpublishing", async ({ page, browser }) => {
  await newUser(page);
  await analyseToApproval(page, devJob(1));
  const thread = page.url().split("/studio/")[1].split(/[?#]/)[0];
  await page.goto(`/runs/${thread}`);
  await page.getByTestId("toggle-public").click();
  await expect(page.getByTestId("toggle-public")).toHaveText("Unpublish trace");
  const anon = await browser.newPage();
  await anon.goto(`/t/${thread}`);
  await expect(anon.getByTestId("trace-table")).toBeVisible();
  await page.getByTestId("toggle-public").click();
  await expect(page.getByTestId("toggle-public")).toHaveText("Make trace public");
  const r = await anon.request.get(`/api/public/traces/${thread}`);
  expect(r.status()).toBe(404);
});
