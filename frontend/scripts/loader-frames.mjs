// Frames of the Spoor loader across one press (the Hub's data held back), stitched into one strip.
import { chromium } from "playwright";
const out = process.argv[2];
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
await p.route("**/api/spoor/v1/sites/*/exceptions*", async (r) => { await new Promise((ok) => setTimeout(ok, 6000)); await r.continue(); });
await p.goto("http://localhost:3000/hub");
await p.waitForSelector(".sl-mark", { timeout: 20000 });
const box = await p.locator(".sl").first().boundingBox();
for (let i = 0; i < 10; i++) {
  await p.screenshot({ path: `${out}/sl_${i}.png`, clip: { x: box.x + box.width / 2 - 80, y: box.y, width: 160, height: box.height } });
  await p.waitForTimeout(240);
}
await b.close();
