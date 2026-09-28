import { test, expect } from "@playwright/test";
import { currentAdminTotpCode, dismissCookieConsent } from "./helpers";

test("staff login enforces MFA for the admin role and reaches the portal", async ({ page }) => {
  await page.goto("/login");
  await dismissCookieConsent(page);

  await page.getByLabel("Email", { exact: true }).fill("admin@meridianauto.example");
  await page.getByLabel("Password").fill("MeridianDemo!Admin1");
  await page.getByRole("button", { name: "Sign In" }).click();

  await expect(page.getByLabel("6-digit authentication code")).toBeVisible({ timeout: 10_000 });

  await page.getByLabel("6-digit authentication code").fill(currentAdminTotpCode());
  await page.getByRole("button", { name: "Verify" }).click();

  await expect(page).toHaveURL(/\/portal$/, { timeout: 10_000 });
});

test("a wrong MFA code is rejected", async ({ page }) => {
  await page.goto("/login");
  await dismissCookieConsent(page);

  await page.getByLabel("Email", { exact: true }).fill("admin@meridianauto.example");
  await page.getByLabel("Password").fill("MeridianDemo!Admin1");
  await page.getByRole("button", { name: "Sign In" }).click();

  await expect(page.getByLabel("6-digit authentication code")).toBeVisible({ timeout: 10_000 });
  await page.getByLabel("6-digit authentication code").fill("000000");
  await page.getByRole("button", { name: "Verify" }).click();

  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page).toHaveURL(/\/login$/);
});
