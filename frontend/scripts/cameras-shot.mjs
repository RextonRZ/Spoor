import { chromium } from "playwright";
const out = process.argv[2];
const b = await chromium.launch();
const errors = [];
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
p.on("console", (m) => m.type() === "error" && errors.push(m.text()));
p.on("pageerror", (e) => errors.push(String(e)));
await p.goto("http://localhost:3000/wall", { waitUntil: "networkidle" });
await p.waitForTimeout(2500);
await p.screenshot({ path: `${out}/cams.png` });
// zoom in the viewer: wheel over its centre, then drag
const stage = p.locator(".cv-stage");
const box = await stage.boundingBox();
await p.mouse.move(box.x + box.width * 0.55, box.y + box.height * 0.5);
for (let i = 0; i < 6; i++) { await p.mouse.wheel(0, -240); await p.waitForTimeout(60); }
await p.waitForTimeout(400);
await p.screenshot({ path: `${out}/cams_zoom.png`, clip: { x: box.x - 20, y: box.y - 70, width: box.width + 40, height: box.height + 140 } });
console.log("zoom label:", await p.locator(".cv-zoom").innerText());
await p.locator(".cm-tile").nth(5).click();
await p.waitForTimeout(800);
console.log("dock cam:", await p.locator(".hb-dock .hb-drawer-place").innerText());
const ph = await b.newPage({ viewport: { width: 390, height: 844 } });
await ph.goto("http://localhost:3000/wall", { waitUntil: "networkidle" });
await ph.waitForTimeout(2000);
await ph.screenshot({ path: `${out}/cams_phone.png` });
console.log("phone overflow px:", await ph.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth));
await b.close();
console.log("console errors:", errors.length ? errors.slice(0, 4) : "none");
