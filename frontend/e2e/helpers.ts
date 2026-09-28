import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { generateSync } from "otplib";
import type { Page } from "@playwright/test";

/** The cookie consent banner sits fixed at the bottom of the viewport and intercepts clicks
 * on anything behind it (including the chat launcher) until dismissed. */
export async function dismissCookieConsent(page: Page): Promise<void> {
  const accept = page.getByRole("button", { name: "Accept" });
  if (await accept.isVisible({ timeout: 3_000 }).catch(() => false)) {
    await accept.click();
  }
}

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const BACKEND_DIR = path.resolve(__dirname, "../../backend");

/** Fetches the seeded admin's real TOTP secret from Postgres (never hardcoded, since
 * `make seed` generates a fresh random one) and returns the current 6-digit code. */
export function currentAdminTotpCode(): string {
  const secret = execFileSync(
    path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe"),
    ["scripts/print_admin_totp_secret.py"],
    { cwd: BACKEND_DIR, encoding: "utf-8" },
  ).trim();
  return generateSync({ secret, strategy: "totp" });
}
