import { expect, test } from "@playwright/test";
import { analyseToApproval, devJob, newUser } from "./helpers";

test("editing a draft sends it back through compliance and asks again with the edited text", async ({ page }) => {
  await newUser(page);
  await analyseToApproval(page, devJob(1));
  const box = page.getByTestId("draft-text");
  const marker = "Happy to walk you through a short Loom video of similar work.";
  await box.fill((await box.inputValue()) + "\n\n" + marker);
  await expect(page.getByTestId("approve")).toBeDisabled();
  await page.getByTestId("save-edit").click();
  await expect(async () => {
    await page.reload();
    await expect(page.getByTestId("draft-text")).toHaveValue(new RegExp(marker.slice(0, 30)));
  }).toPass({ timeout: 90_000 });
});
