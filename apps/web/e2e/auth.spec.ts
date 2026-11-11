import { expect, test } from "@playwright/test";
import { newUser } from "./helpers";

test("register, onboard with a persona and reach the inbox; wrong password is rejected", async ({ page }) => {
  const email = await newUser(page);
  await expect(page.getByRole("heading", { name: "Job inbox" })).toBeVisible();
  await page.getByText("Sign out").click();
  await page.goto("/login");
  await page.getByTestId("email").fill(email);
  await page.getByTestId("password").fill("wrong-password");
  await page.getByTestId("login-submit").click();
  await expect(page.getByTestId("login-error")).toContainText("wrong email or password");
});
