// Top bar logo check: screen (dark logo) and print emulation (light logo). node scripts/topbar-shot.mjs <outdir>
import { chromium } from "playwright";
const out = process.argv[2];
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
await p.goto("http://localhost:3000/hub", { waitUntil: "networkidle" });
await p.locator("header.tb").screenshot({ path: `${out}/topbar_screen.png` });
await p.emulateMedia({ media: "print" });
await p.locator("header.tb").screenshot({ path: `${out}/topbar_print.png` });
const nat = await p.evaluate(() => [...document.querySelectorAll(".tb-logo")].map((i) => [i.currentSrc.split("/").pop(), i.naturalWidth, getComputedStyle(i).display]));
console.log(JSON.stringify(nat));
await b.close();
