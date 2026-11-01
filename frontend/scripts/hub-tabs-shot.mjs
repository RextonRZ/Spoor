// The Hub's tabs (Open cases, Places, Resolved) and a place chosen into the spotlight. With an API argument the page's
// /api/spoor calls go to that backend (the investigator token from .env.local); without it, the live dev server as is.
//   node scripts/hub-tabs-shot.mjs <out dir> [api] [tag]
import { chromium } from "playwright";
import { readFileSync } from "node:fs";
const [out, API, tag = API ? "api" : "live"] = process.argv.slice(2);
const env = Object.fromEntries(readFileSync(".env.local", "utf8").split("\n").filter((l) => l.includes("=") && !l.startsWith("#"))
  .map((l) => [l.slice(0, l.indexOf("=")).trim(), l.slice(l.indexOf("=") + 1).trim()]));
const token = env.SPOOR_TOKEN_SUPERVISOR || env.SPOOR_TOKEN_INVESTIGATOR;
const b = await chromium.launch();
const errors = [];
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
p.on("console", (m) => m.type() === "error" && errors.push(m.text()));
p.on("pageerror", (e) => errors.push(String(e)));
if (API) {
  await p.route("**/api/spoor/**", async (route) => {
    const u = new URL(route.request().url());
    const r = await fetch(`${API}/${u.pathname.replace(/^\/api\/spoor\//, "")}${u.search}`, { headers: { Authorization: `Bearer ${token}` } });
    await route.fulfill({ status: r.status, headers: Object.fromEntries(r.headers), body: Buffer.from(await r.arrayBuffer()) });
  });
}
await p.goto("http://localhost:3000/hub", { waitUntil: "networkidle" });
await p.waitForTimeout(2500);
await p.getByRole("tab", { name: /Places/ }).click();
await p.waitForTimeout(800);
const bar = await p.locator(".hb-bar").boundingBox();
await p.evaluate((y) => window.scrollTo(0, y - 90), bar.y + (await p.evaluate(() => window.scrollY)));
await p.waitForTimeout(500);
await p.screenshot({ path: `${out}/places_${tag}.png` });
const stalled = p.locator(".hb-pl[data-stalled]");
if (await stalled.count()) {
  await stalled.first().click();
  await p.waitForTimeout(1200);
  await p.evaluate(() => window.scrollTo(0, 0));
  await p.waitForTimeout(300);
  await p.screenshot({ path: `${out}/places_spot_${tag}.png` });
}
await b.close();
console.log("console errors:", errors.length ? errors.slice(0, 5) : "none");
