// The Hub console on the live dev server: default view, a case opened in the detail panel, the Places tab with a place
// opened, the collapsed sidebar, and the phone layout.
import { chromium } from "playwright";
const out = process.argv[2];
const b = await chromium.launch();
const errors = [];
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
p.on("console", (m) => m.type() === "error" && !/scan-points/.test(m.location()?.url ?? "") && errors.push(m.text()));
p.on("pageerror", (e) => errors.push(String(e)));
await p.goto("http://localhost:3000/hub", { waitUntil: "networkidle" });
await p.evaluate(() => { try { localStorage.removeItem("spoor.sidebar"); } catch {} });
await p.reload({ waitUntil: "networkidle" });
await p.waitForTimeout(2500);
await p.screenshot({ path: `${out}/console.png` });
const row = p.locator("button.hb-tr").first();
if (await row.count()) {
  await row.click();
  await p.waitForTimeout(900);
  await p.screenshot({ path: `${out}/console_case.png` });
  await p.keyboard.press("Escape");
  await p.waitForTimeout(400);
}
await p.getByRole("tab", { name: /Places/ }).click();
await p.waitForTimeout(500);
const place = p.locator("button.hb-tr[data-stalled]").first();
if (await place.count()) {
  await place.click();
  await p.waitForTimeout(900);
  await p.screenshot({ path: `${out}/console_place.png` });
  await p.keyboard.press("Escape");
  await p.waitForTimeout(400);
}
await p.locator(".sb-toggle").click();
await p.waitForTimeout(600);
await p.screenshot({ path: `${out}/console_rail.png` });
await p.locator(".sb-toggle").click();
await p.close();
const ph = await b.newPage({ viewport: { width: 390, height: 844 } });
await ph.goto("http://localhost:3000/hub", { waitUntil: "networkidle" });
await ph.waitForTimeout(2500);
await ph.screenshot({ path: `${out}/console_phone.png`, fullPage: true });
console.log("phone overflow px:", await ph.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth));
await b.close();
console.log("console errors (besides the old backend's missing scan-points):", errors.length ? errors.slice(0, 5) : "none");
