// Screenshot the hero's board beat (and a spotlight beat) by phase, not by clock. node scripts/landing-board-shot.mjs <outdir>
import { chromium } from "playwright";
const out = process.argv[2];
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
const warn = [];
p.on("console", (m) => (m.type() === "error" || m.type() === "warning") && warn.push(m.text().slice(0, 160)));
await p.goto("http://localhost:3000/", { waitUntil: "networkidle" });
const at = async (phase, extra, name) => {
  await p.waitForFunction((ph) => document.querySelector(".lp-feed-hero")?.dataset.phase === ph, phase, { timeout: 60000 });
  await p.waitForTimeout(extra);
  await p.screenshot({ path: `${out}/${name}.png` });
};
await at("step", 1800, "spot_step");
await at("red", 2000, "spot_red");
await at("board", 6500, "board");
console.log(JSON.stringify({ warn }));
await b.close();
