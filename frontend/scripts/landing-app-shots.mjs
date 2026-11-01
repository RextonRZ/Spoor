// Small real visuals of the app for the landing's "How Spoor investigates" steps (re-run after the S2 case is
// reseeded): node scripts/landing-app-shots.mjs  ->  public/landing/app/{plan,analysts,verifier,answer}.jpg
// Clips are CSS-pixel rectangles of the 1440 x 900 layout (review/refs/flow widths), at 2x.
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
const base = process.env.SPOOR_URL ?? "http://localhost:3000";
const out = "public/landing/app";
mkdirSync(out, { recursive: true });
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
const cases = await (await fetch(`${base}/api/spoor/v1/cases`)).json();
const id = cases[0].case.case_id;
const shots = [
  ["plan", `/cases/${id}/investigate`, { x: 997, y: 171, width: 378, height: 284 }],
  ["analysts", `/cases/${id}/investigate`, { x: 1015, y: 600, width: 342, height: 257 }],
  ["verifier", `/cases/${id}/investigate`, { x: 1000, y: 770, width: 372, height: 279 }],
  ["answer", `/cases/${id}`, { x: 64, y: 160, width: 590, height: 443 }],
];
for (const [name, url, clip] of shots) {
  await p.goto(`${base}${url}`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1200);
  await p.screenshot({ path: `${out}/${name}.jpg`, type: "jpeg", quality: 80, clip, fullPage: true });
}
await b.close();
console.log("landing app shots:", id);
