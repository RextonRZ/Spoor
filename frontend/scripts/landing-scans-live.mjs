// #scans on the live dev server as it is (its own backend, no rerouting): what the owner sees today
import { chromium } from "playwright";
const out = process.argv[2];
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
await p.goto("http://localhost:3000/", { waitUntil: "networkidle" });
const y = await p.evaluate(() => document.getElementById("scans").getBoundingClientRect().top + window.scrollY);
for (let k = 0; k < 2; k++) {
  await p.evaluate((yy) => window.scrollTo(0, yy), y + k * 780);
  await p.waitForTimeout(2400);
  await p.screenshot({ path: `${out}/live_${k}.png` });
}
await b.close();
