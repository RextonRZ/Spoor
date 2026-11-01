// Scan checkpoints, live against a second backend (default the S2 store on :8010): the landing section (desktop +
// phone), the case Answer, and the 3D hub pins on the Proof screen. The page's /api/spoor calls are sent to that
// backend with the investigator token from .env.local, so the dev server and its own backend are left alone.
//   node scripts/checkpoints-shot.mjs <out dir> [api=http://127.0.0.1:8010]
import { chromium } from "playwright";
import { readFileSync } from "node:fs";
const out = process.argv[2];
const API = process.argv[3] ?? "http://127.0.0.1:8010";
const env = Object.fromEntries(readFileSync(".env.local", "utf8").split("\n").filter((l) => l.includes("=") && !l.startsWith("#"))
  .map((l) => [l.slice(0, l.indexOf("=")).trim(), l.slice(l.indexOf("=") + 1).trim()]));
const token = env.SPOOR_TOKEN_SUPERVISOR || env.SPOOR_TOKEN_INVESTIGATOR;
const cases = await (await fetch(`${API}/v1/cases`, { headers: { Authorization: `Bearer ${token}` } })).json();
const caseId = cases[0].case.case_id;
console.log("case", caseId, cases[0].case.target_description);

const b = await chromium.launch();
const errors = [];
const page = async (vp) => {
  const p = await b.newPage({ viewport: vp, deviceScaleFactor: 1 });
  p.on("console", (m) => m.type() === "error" && errors.push(`${p.url()}: ${m.text()}`));
  p.on("pageerror", (e) => errors.push(String(e)));
  await p.route("**/api/spoor/**", async (route) => {
    const u = new URL(route.request().url());
    const target = `${API}/${u.pathname.replace(/^\/api\/spoor\//, "")}${u.search}`;
    const r = await fetch(target, { method: route.request().method(), headers: { Authorization: `Bearer ${token}`, ...(route.request().headers()["content-type"] ? { "content-type": route.request().headers()["content-type"] } : {}) },
      body: ["GET", "HEAD"].includes(route.request().method()) ? undefined : route.request().postDataBuffer() });
    await route.fulfill({ status: r.status, headers: Object.fromEntries(r.headers), body: Buffer.from(await r.arrayBuffer()) });
  });
  return p;
};

for (const [tag, vp] of [["desktop", { width: 1440, height: 900 }], ["phone", { width: 390, height: 844 }]]) {
  const p = await page(vp);
  await p.goto("http://localhost:3000/", { waitUntil: "networkidle" });
  const s = p.locator("#scans");
  await s.scrollIntoViewIfNeeded();
  await p.waitForTimeout(600);
  await p.evaluate(() => window.scrollBy(0, 300));
  await p.waitForTimeout(2600);
  await s.screenshot({ path: `${out}/scans_${tag}.png` });
  console.log(tag, "overflow px:", await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth));
  await p.close();
}
{
  const p = await page({ width: 1440, height: 1000 });
  await p.goto(`http://localhost:3000/cases/${caseId}`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1500);
  await p.screenshot({ path: `${out}/answer.png`, fullPage: true });
  await p.goto(`http://localhost:3000/cases/${caseId}/proof`, { waitUntil: "networkidle" });
  await p.getByRole("button", { name: "3D hub" }).click();
  await p.waitForSelector(".sp-scene[data-ready='true']", { timeout: 60000 }).catch(() => {});
  await p.waitForTimeout(3500);
  await p.screenshot({ path: `${out}/pins_3d.png` });
  await p.close();
}
await b.close();
console.log("console errors:", errors.length ? errors.slice(0, 8) : "none");
