import { test, expect } from "@playwright/test";
import { dismissCookieConsent } from "./helpers";

test("executive overview date-range filter changes the displayed KPIs", async ({ page }) => {
  await page.goto("/login");
  await dismissCookieConsent(page);
  await page.getByLabel("Email", { exact: true }).fill("analyst@meridianauto.example");
  await page.getByLabel("Password").fill("MeridianDemo!Analyst1");
  await page.getByRole("button", { name: "Sign In" }).click();
  await expect(page).toHaveURL(/\/portal$/, { timeout: 10_000 });

  const totalRevenueValue = () => page.getByText("Total Revenue").locator("..").locator("p").nth(1);

  // Default preset is 30D; wait for the KPI to load before reading its value.
  await expect(totalRevenueValue()).not.toHaveText("", { timeout: 15_000 });
  const before = await totalRevenueValue().textContent();

  await page.getByRole("button", { name: "12M", exact: true }).click();
  await expect(totalRevenueValue()).not.toHaveText(before ?? "", { timeout: 15_000 });
});
