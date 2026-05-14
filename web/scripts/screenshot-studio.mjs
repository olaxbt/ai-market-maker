import fs from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { chromium } from "playwright-core";

const url = process.env.STUDIO_URL || "http://localhost:3021/studio";
const outDir = process.env.OUT_DIR || path.resolve(process.cwd(), "out");
const outPath = path.join(outDir, "studio.png");
const skipBoot = (process.env.SKIP_BOOT_OVERLAY ?? "1") !== "0";

async function main() {
  await fs.mkdir(outDir, { recursive: true });

  // playwright-core does not bundle browsers. Prefer installed Chrome if available.
  const browser = await chromium.launch({
    headless: true,
    channel: process.env.PLAYWRIGHT_CHANNEL || "chrome",
  });
  const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
  if (skipBoot) {
    await page.addInitScript(() => {
      try {
        sessionStorage.setItem("nexus_boot_done_v1", "1");
      } catch {}
    });
  }
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60_000 });
  // Wait for Studio UI to render (avoid capturing the boot overlay).
  await page.getByText("Sessions", { exact: true }).waitFor({ timeout: 60_000 });
  await page.waitForTimeout(250);
  await page.screenshot({ path: outPath, fullPage: true });
  await browser.close();

  // eslint-disable-next-line no-console
  console.log(`Saved: ${outPath}`);
}

main().catch((err) => {
  // eslint-disable-next-line no-console
  console.error(err?.message || err);
  process.exit(1);
});

