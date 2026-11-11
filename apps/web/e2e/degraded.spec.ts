import { expect, test } from "@playwright/test";
import { newUser } from "./helpers";

test("when the marketplace is down the UI shows degraded mode, and recovers", async ({ page }) => {
  await newUser(page);
  await page.request.post("/api/demo/fault", { data: { down: true } });
  await page.reload();
  await expect(page.getByTestId("degraded-banner")).toBeVisible();
  await page.request.post("/api/demo/fault", { data: { down: false } });
  await page.reload();
  await expect(page.getByTestId("degraded-banner")).toHaveCount(0, { timeout: 30_000 });
});
