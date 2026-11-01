import { chromium } from "playwright";
const out = process.argv[2];
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
const id = await (async () => { await p.goto("http://localhost:3000/hub"); return p.evaluate(async () => (await (await fetch("/api/spoor/v1/cases")).json())[0]?.case?.case_id); })();
for (const [name, path] of [["answer", ""], ["proof", "/proof"], ["search", "/search"], ["report", "/report"]]) {
  await p.goto(`http://localhost:3000/cases/${id}${path}`, { waitUntil: "networkidle" });
  await p.waitForTimeout(900);
  await p.screenshot({ path: `${out}/steps_${name}.png`, clip: { x: 240, y: 0, width: 1200, height: 190 } });
}
const ph = await b.newPage({ viewport: { width: 390, height: 844 } });
await ph.goto(`http://localhost:3000/cases/${id}/proof`, { waitUntil: "networkidle" });
await ph.waitForTimeout(900);
await ph.screenshot({ path: `${out}/steps_phone.png`, clip: { x: 0, y: 0, width: 390, height: 260 } });
console.log("phone overflow px:", await ph.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth));
await b.close();
