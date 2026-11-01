// The app's shell + Hub (spotlight + gallery) as they are on the live dev server: the first view, a stalled group
// chosen, the account menu, a case page's step tabs, and the phone layout.
import { chromium } from "playwright";
const out = process.argv[2];
const b = await chromium.launch();
const errors = [];
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
p.on("console", (m) => m.type() === "error" && errors.push(m.text()));
p.on("pageerror", (e) => errors.push(String(e)));
await p.goto("http://localhost:3000/hub", { waitUntil: "networkidle" });
await p.waitForTimeout(2500);
await p.screenshot({ path: `${out}/hub_d.png` });
await p.screenshot({ path: `${out}/hub_d_full.png`, fullPage: true });
const cards = p.locator(".hb-card");
if ((await cards.count()) > 1) {
  await cards.nth(1).click();
  await p.waitForTimeout(1200);
  await p.evaluate(() => window.scrollTo(0, 0));
  await p.waitForTimeout(400);
  await p.screenshot({ path: `${out}/hub_d_group.png` });
}
await p.locator(".tb-me").click();
await p.waitForTimeout(300);
await p.screenshot({ path: `${out}/hub_d_menu.png`, clip: { x: 900, y: 0, width: 540, height: 260 } });
await p.keyboard.press("Escape");
const caseLink = await p.evaluate(async () => {
  const r = await fetch("/api/spoor/v1/cases");
  const rows = await r.json();
  return rows[0]?.case?.case_id ?? null;
});
if (caseLink) {
  await p.goto(`http://localhost:3000/cases/${caseLink}/proof`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1500);
  await p.screenshot({ path: `${out}/case_tabs.png`, clip: { x: 0, y: 0, width: 1440, height: 170 } });
}
await p.close();
const ph = await b.newPage({ viewport: { width: 390, height: 844 } });
ph.on("console", (m) => m.type() === "error" && errors.push(m.text()));
await ph.goto("http://localhost:3000/hub", { waitUntil: "networkidle" });
await ph.waitForTimeout(2500);
await ph.screenshot({ path: `${out}/hub_p.png`, fullPage: true });
console.log("phone overflow px:", await ph.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth));
await b.close();
console.log("console errors:", errors.length ? errors.slice(0, 5) : "none");
