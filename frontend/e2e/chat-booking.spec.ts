import { test, expect } from "@playwright/test";
import { dismissCookieConsent } from "./helpers";

/** Turn sequence mirrors backend/tests/test_scripted_conversations.py's BOOKING_CASES, since
 * that is the verified, working script the real dialog manager and intent classifier handle
 * correctly -- an E2E test should drive the same real backend through the real UI, not guess
 * at wording the bot has never been tested against. */
const TURNS = ["I need to book an oil change", "2020 Toyota Camry", "next Tuesday", "Chat E2E Test", "614-555-0177", "1"];

test("chat widget books a real appointment through the assistant", async ({ page }) => {
  await page.goto("/");
  await dismissCookieConsent(page);

  await page.getByRole("button", { name: "Open chat with Meridian Assist" }).click();
  const dialog = page.getByRole("dialog", { name: "Chat with Meridian Assist" });
  await expect(dialog).toBeVisible();

  const input = page.getByLabel("Type a message");
  for (const turn of TURNS) {
    await input.fill(turn);
    await page.getByRole("button", { name: "Send message" }).click();
    await expect(page.getByLabel("Assistant is typing")).toHaveCount(0, { timeout: 20_000 });
  }

  await expect(dialog.getByText(/MRD-\d{6}/)).toBeVisible({ timeout: 20_000 });
});
