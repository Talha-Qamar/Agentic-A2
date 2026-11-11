import { expect, test } from "@playwright/test";
import { newUser } from "./helpers";

test("portfolio builder turns a repo into a case study whose claims are checked against the code", async ({ page }) => {
  await newUser(page);
  await page.getByTestId("nav-settings").click();
  await expect(page.getByTestId("portfolio-builder")).toBeVisible();
  await page.getByTestId("build-case-study").click();
  const res = page.getByTestId("builder-result");
  await expect(res).toBeVisible({ timeout: 90_000 });
  await expect(res).toContainText("builder-clause-rag.md");
  await expect(res).toContainText("code-verified");
});
