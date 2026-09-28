import { test, expect } from "@playwright/test";
import { dismissCookieConsent } from "./helpers";

test("public booking wizard books a real appointment end to end", async ({ page }) => {
  await page.goto("/book");
  await dismissCookieConsent(page);

  // Step 1: Vehicle. NHTSA's vPIC API returns makes/models in upper case (verified directly
  // against GET /api/v1/nhtsa/makes and /models), and the <select> options use that as-is.
  await page.getByLabel("Year").selectOption("2021");
  await expect(page.getByLabel("Make")).toBeEnabled({ timeout: 15_000 });
  await page.getByLabel("Make").selectOption("HONDA");
  await expect(page.getByLabel("Model")).toBeEnabled({ timeout: 15_000 });
  await page.getByLabel("Model").selectOption("CIVIC");
  await page.getByRole("button", { name: "Continue" }).click();

  // Step 2: Service
  await page.getByRole("button", { name: /Oil Change/i }).first().click();
  await page.getByRole("button", { name: "Continue" }).click();

  // Step 3: Date & Time -- pick the first open slot for the default location.
  const firstSlot = page.locator("div.grid.gap-2 button").first();
  await firstSlot.waitFor({ state: "visible", timeout: 20_000 });
  await firstSlot.click();
  await page.getByRole("button", { name: "Continue" }).click();

  // Step 4: Contact
  const uniquePhone = `614-555-${String(Math.floor(1000 + Math.random() * 9000))}`;
  await page.getByLabel("Full Name").fill("Playwright E2E");
  await page.getByLabel("Phone").fill(uniquePhone);
  await page.getByRole("button", { name: "Confirm Booking" }).click();

  await expect(page.getByText("Appointment confirmed")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText(/^MRD-\d{6}$/)).toBeVisible();
});
