// Trust section + closing, desktop and phone (after their reveals).
import { chromium } from "playwright";
const out = process.argv[2];
const b = await chromium.launch();
const errors = [];
for (const [tag, vp] of [["desktop", { width: 1440, height: 900 }], ["phone", { width: 390, height: 844 }]]) {
  const p = await b.newPage({ viewport: vp, deviceScaleFactor: 1 });
  p.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  await p.goto("http://localhost:3000/", { waitUntil: "networkidle" });
  for (const [sel, name] of [["#trust", "trust"], [".lp-closing", "closing"]]) {
    const l = p.locator(sel);
    await l.scrollIntoViewIfNeeded();
    await p.waitForTimeout(2800);
    await l.screenshot({ path: `${out}/${name}_${tag}.png` });
  }
  console.log(tag, "overflow px:", await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth));
  await p.close();
}
await b.close();
console.log("console errors:", errors.length ? errors : "none");
