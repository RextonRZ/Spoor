// viewport shots of #scans (top, then the cards) via the :8010 store
import { chromium } from "playwright";
import { readFileSync } from "node:fs";
const out = process.argv[2];
const env = Object.fromEntries(readFileSync(".env.local", "utf8").split("\n").filter((l) => l.includes("=") && !l.startsWith("#")).map((l) => [l.slice(0, l.indexOf("=")).trim(), l.slice(l.indexOf("=") + 1).trim()]));
const token = env.SPOOR_TOKEN_SUPERVISOR || env.SPOOR_TOKEN_INVESTIGATOR;
const b = await chromium.launch();
for (const [tag, vp] of [["d", { width: 1440, height: 900 }], ["p", { width: 390, height: 844 }]]) {
  const p = await b.newPage({ viewport: vp });
  await p.route("**/api/spoor/**", async (route) => {
    const u = new URL(route.request().url());
    const r = await fetch(`http://127.0.0.1:8010/${u.pathname.replace(/^\/api\/spoor\//, "")}${u.search}`, { headers: { Authorization: `Bearer ${token}` } });
    await route.fulfill({ status: r.status, headers: Object.fromEntries(r.headers), body: Buffer.from(await r.arrayBuffer()) });
  });
  await p.goto("http://localhost:3000/", { waitUntil: "networkidle" });
  const y = await p.evaluate(() => document.getElementById("scans").getBoundingClientRect().top + window.scrollY);
  for (let k = 0; k < 4; k++) {
    await p.evaluate((yy) => window.scrollTo(0, yy), y + k * (vp.height - 120));
    await p.waitForTimeout(2400);
    await p.screenshot({ path: `${out}/vp_${tag}_${k}.png` });
  }
  await p.close();
}
await b.close();
