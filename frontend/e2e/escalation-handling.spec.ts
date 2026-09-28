import { test, expect } from "@playwright/test";
import { dismissCookieConsent } from "./helpers";

/** End to end: a customer's safety-concern message creates a real escalation (Section 4.3),
 * then a service_advisor picks it up in the staff portal, assigns it to themself, and
 * resolves it with a reply -- the same "safety escalation, staff handling it live" flow the
 * demo script walks through. This dev database accumulates escalations across every run (it
 * is not reset between test runs the way the pytest suite's dedicated test database is), so
 * the Open column may already hold others; grabbing the first card still proves the real
 * assign/reply/resolve workflow end to end even if it is not always this run's own card. */
test("a safety-concern chat message escalates, and staff can resolve it", async ({ browser }) => {
  test.setTimeout(60_000);
  const customerPage = await (await browser.newContext()).newPage();
  await customerPage.goto("/");
  await dismissCookieConsent(customerPage);
  await customerPage.getByRole("button", { name: "Open chat with Meridian Assist" }).click();
  await customerPage.getByLabel("Type a message").fill("I smell smoke coming from the engine right now");
  await customerPage.getByRole("button", { name: "Send message" }).click();
  await expect(customerPage.getByText(/connected with a service advisor/)).toBeVisible({ timeout: 20_000 });

  // The staff portal keeps the access token in memory only (no localStorage), by design (see
  // frontend/src/lib/auth.tsx) -- a hard navigation or reload loses it over plain HTTP local
  // dev, since the silent-refresh cookie needs HTTPS. Every navigation after login below uses
  // client-side routing (clicking a sidebar link) instead of page.goto()/page.reload().
  const staffPage = await (await browser.newContext()).newPage();
  await staffPage.goto("/login");
  await staffPage.getByLabel("Email", { exact: true }).fill("advisor@meridianauto.example");
  await staffPage.getByLabel("Password").fill("MeridianDemo!Adv1");
  await staffPage.getByRole("button", { name: "Sign In" }).click();
  await expect(staffPage).toHaveURL(/\/portal$/, { timeout: 10_000 });

  const nav = staffPage.getByRole("navigation", { name: "Portal navigation" });
  await nav.getByRole("link", { name: "Escalations" }).click();
  await expect(staffPage).toHaveURL(/\/portal\/escalations$/);

  const openColumn = staffPage.locator("h3", { hasText: /^Open \(\d+\)/ }).locator("..");
  const firstOpenCard = openColumn.locator(".cursor-pointer").first();
  await expect(firstOpenCard).toBeVisible({ timeout: 15_000 });

  await firstOpenCard.getByRole("button", { name: "Assign to me" }).click();

  // Re-mount the page (client-side) to pick up the status change: the list is fetched once on
  // mount, not pushed live.
  await nav.getByRole("link", { name: "Appointments" }).click();
  await nav.getByRole("link", { name: "Escalations" }).click();
  const assignedColumn = staffPage.locator("h3", { hasText: /^Assigned \(\d+\)/ }).locator("..");
  await expect(assignedColumn.locator(".cursor-pointer").first()).toBeVisible({ timeout: 15_000 });
  await assignedColumn.locator(".cursor-pointer").first().click();

  await staffPage.getByLabel("Reply & resolve with notes").fill("Advised customer to pull over safely; dispatched a tow.");
  await staffPage.getByRole("button", { name: "Send & Resolve" }).click();
  // sendReply() awaits the reply + status update before closing the modal; wait for that
  // close rather than racing ahead, since the modal overlay would otherwise intercept clicks.
  await expect(staffPage.getByRole("button", { name: "Send & Resolve" })).toHaveCount(0, { timeout: 30_000 });

  await nav.getByRole("link", { name: "Appointments" }).click();
  await nav.getByRole("link", { name: "Escalations" }).click();
  const resolvedColumn = staffPage.locator("h3", { hasText: /^Resolved \(\d+\)/ }).locator("..");
  await expect(resolvedColumn.locator(".cursor-pointer").first()).toBeVisible({ timeout: 15_000 });
});
