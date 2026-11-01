// The closing section (hub backdrop) at desktop and phone width.
import { chromium } from "playwright";
const out = process.argv[2];
const b = await chromium.launch();
const errors = [];
for (const [name, vp] of [["closing_desktop", { width: 1440, height: 900 }], ["closing_phone", { width: 390, height: 844 }]]) {
  const p = await b.newPage({ viewport: vp, deviceScaleFactor: 1 });
  p.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  await p.goto("http://localhost:3000/", { waitUntil: "networkidle" });
  const s = p.locator(".lp-closing");
  await s.scrollIntoViewIfNeeded();
  await p.waitForTimeout(2600);
  const overflow = await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  await s.screenshot({ path: `${out}/${name}.png` });
  console.log(name, "overflow px:", overflow);
  await p.close();
}
await b.close();
console.log("console errors:", errors.length ? errors : "none");
