// Landing check: desktop hero at a few moments of the loop + console errors. node scripts/landing-shot.mjs <outdir>
import { chromium } from "playwright";
const out = process.argv[2];
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [];
p.on("console", (m) => m.type() === "error" && errors.push(m.text()));
p.on("pageerror", (e) => errors.push(String(e)));
await p.goto("http://localhost:3000/", { waitUntil: "networkidle" });
for (const ms of [6000, 12000, 20500, 25500]) {
  await p.waitForTimeout(ms - (globalThis.__t ?? 0));
  globalThis.__t = ms;
  await p.screenshot({ path: `${out}/hero_${ms}.png` });
}
await p.screenshot({ path: `${out}/landing_top.png` });
console.log(JSON.stringify({ errors }));
await b.close();
