import { expect, test } from "@playwright/test";
import { analyseToApproval, devJob, newUser } from "./helpers";

test("rejecting a proposal records the reason and nothing is submitted", async ({ page, request }) => {
  await newUser(page);
  await analyseToApproval(page, devJob(2));
  await page.getByTestId("reject-reason").fill("budget too low for the scope");
  await page.getByTestId("reject").click();
  await expect(async () => {
    await page.reload();
    await expect(page.getByTestId("studio-status")).toContainText("rejected");
  }).toPass({ timeout: 60_000 });
  const pipe = await (await page.request.get("/api/pipeline")).json();
  const total = Object.values(pipe.columns).reduce((n: number, c: any) => n + c.length, 0);
  expect(total).toBe(0);
});
