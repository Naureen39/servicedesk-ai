import { test, expect } from "@playwright/test";
import { dismissCookieConsent } from "./helpers";

test("recall quick check finds real, live NHTSA recall data on the home page", async ({ page }) => {
  await page.goto("/");
  await dismissCookieConsent(page);

  // Home renders two RecallQuickCheck instances (one hidden below the `lg` breakpoint, one
  // above it); the desktop viewport this suite runs at shows the first one in DOM order.
  const year = page.getByLabel("Year").first();
  const make = page.getByLabel("Make").first();
  const model = page.getByLabel("Model").first();

  // NHTSA's vPIC API returns makes/models in upper case (verified directly against
  // GET /api/v1/nhtsa/makes and /models), and the <select> options use that value as-is.
  await year.selectOption("2015");
  await expect(make).toBeEnabled({ timeout: 15_000 });
  await make.selectOption("HONDA");
  await expect(model).toBeEnabled({ timeout: 15_000 });
  await model.selectOption("ACCORD");

  await page.getByRole("button", { name: "Check for Recalls" }).first().click();

  await expect(page.getByText(/recalls? found for 2015 HONDA ACCORD/).first()).toBeVisible({ timeout: 20_000 });
});
