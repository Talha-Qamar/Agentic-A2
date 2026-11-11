import { expect, test } from "@playwright/test";
import { analyseToApproval, devJob, newUser } from "./helpers";

test("job -> analysis -> proposal studio shows exact preview -> approve -> appears in pipeline", async ({ page }) => {
  await newUser(page);
  await analyseToApproval(page, devJob(0));
  await expect(page.getByTestId("preview-connects")).toContainText(/\d+/);
  await expect(page.getByTestId("claim").first()).toBeVisible();
  await page.getByTestId("approve").click();
  await expect(page.getByTestId("studio-done")).toContainText("Approved");
  await page.getByTestId("nav-pipeline").click();
  await expect(page.getByTestId("pipeline-tile").first()).toBeVisible({ timeout: 60_000 });
});
