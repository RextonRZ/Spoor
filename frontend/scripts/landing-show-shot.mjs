// "How Spoor investigates" (the pinned scroll showcase): each step at desktop sizes, one frame mid hand-over, and the
// stacked phone layout. Uses a case that matches the footage (as landing-board-mock); `--real` uses the live API.
import { chromium } from "playwright";
import { readFileSync } from "node:fs";
const out = process.argv[2];
const real = process.argv.includes("--real");
const land = JSON.parse(readFileSync("public/landing/landing.json", "utf8"));
const pid = land.story_parcel;
const KIND = { tunnel_read: "tunnel_read", induct_to_carrier: "inducted", divert_confirm: "divert_confirmed", container_add: "container_add" };
const scans = readFileSync("../assets/hub/build/sim/events_scan_simulated_S2.jsonl", "utf8").split("\n").filter(Boolean)
  .map((l) => JSON.parse(l)).filter((r) => r.parcel_id === pid)
  .map((r) => ({ t: new Date(r.time).toISOString(), event_kind: KIND[r.event] ?? r.event, station_id: r.scan_point,
    raw_description: r.container_id ? `container ${r.container_id}` : r.chute ? `chute ${r.chute}` : "" }));
const b = await chromium.launch();
const errors = [];
const page = async (vp) => {
  const p = await b.newPage({ viewport: vp, deviceScaleFactor: 1 });
  p.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  p.on("pageerror", (e) => errors.push(String(e)));
  if (!real) {
    const json = (route, body) => route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
    await p.route("**/api/spoor/v1/cases", (r) => json(r, [{ case: { case_id: "mock" } }]));
    await p.route("**/api/spoor/v1/cases/mock/journey", (r) => json(r, { objects: [{ label: `parcel ${pid}`, identity_keys: [`carrier_waybill:${pid}`], scans }] }));
    for (const k of ["conflicts", "missing-moment", "possible-locations"]) await p.route(`**/api/spoor/v1/cases/mock/${k}`, (r) => json(r, { objects: [{ conflicts: [], expected_next: [], places: [] }] }));
    await p.route("**/api/spoor/v1/cases/mock/search-tasks", (r) => json(r, { found: null }));
  }
  await p.goto("http://localhost:3000/", { waitUntil: "networkidle" });
  return p;
};
// scroll the track to a fraction of its pinned run
const at = (p, f) => p.evaluate((f) => {
  const t = document.querySelector(".lp-show-track");
  const top = t.getBoundingClientRect().top + window.scrollY;
  window.scrollTo(0, top + (t.offsetHeight - window.innerHeight) * f);
}, f);

for (const [tag, vp] of [["1440", { width: 1440, height: 900 }], ["1280", { width: 1280, height: 720 }]]) {
  const p = await page(vp);
  for (const [i, f] of [0.1, 0.36, 0.61, 0.86].entries()) {
    await at(p, f);
    await p.waitForTimeout(1900);
    await p.screenshot({ path: `${out}/show_${tag}_${i + 1}.png` });
  }
  if (tag === "1440") {
    await at(p, 0.36);
    await p.waitForTimeout(1500);
    await at(p, 0.61);
    await p.waitForTimeout(330); // mid hand-over: 02 -> 03
    await p.screenshot({ path: `${out}/show_1440_mid.png` });
  }
  await p.close();
}
const ph = await page({ width: 390, height: 844 });
for (let y = 0; y < 8; y++) { await ph.evaluate((y) => window.scrollTo(0, document.getElementById("how").offsetTop + y * 400), y); await ph.waitForTimeout(250); }
await ph.waitForTimeout(1200);
const overflow = await ph.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
await ph.locator("#how").screenshot({ path: `${out}/show_phone.png` });
console.log("phone horizontal overflow px:", overflow);
await ph.close();
await b.close();
console.log("console errors:", errors.length ? errors : "none");
