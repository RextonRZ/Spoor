// The "five moments" section at desktop and phone width, with a case that matches the footage (as landing-board-mock).
import { chromium } from "playwright";
import { readFileSync } from "node:fs";
const out = process.argv[2];
const land = JSON.parse(readFileSync("public/landing/landing.json", "utf8"));
const pid = land.story_parcel;
const KIND = { tunnel_read: "tunnel_read", induct_to_carrier: "inducted", divert_confirm: "divert_confirmed", container_add: "container_add" };
const scans = readFileSync("../assets/hub/build/sim/events_scan_simulated_S2.jsonl", "utf8").split("\n").filter(Boolean)
  .map((l) => JSON.parse(l)).filter((r) => r.parcel_id === pid)
  .map((r) => ({ t: new Date(r.time).toISOString(), event_kind: KIND[r.event] ?? r.event, station_id: r.scan_point,
    raw_description: r.container_id ? `container ${r.container_id}` : r.chute ? `chute ${r.chute}` : "" }));
const b = await chromium.launch();
for (const [name, vp] of [["moments_desktop", { width: 1440, height: 900 }], ["moments_phone", { width: 390, height: 844 }]]) {
  const p = await b.newPage({ viewport: vp, deviceScaleFactor: 2 });
  const json = (route, body) => route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
  await p.route("**/api/spoor/v1/cases", (r) => json(r, [{ case: { case_id: "mock" } }]));
  await p.route("**/api/spoor/v1/cases/mock/journey", (r) => json(r, { objects: [{ label: `parcel ${pid}`, identity_keys: [`carrier_waybill:${pid}`], scans }] }));
  for (const k of ["conflicts", "missing-moment", "possible-locations"]) await p.route(`**/api/spoor/v1/cases/mock/${k}`, (r) => json(r, { objects: [{ conflicts: [], expected_next: [], places: [] }] }));
  await p.route("**/api/spoor/v1/cases/mock/search-tasks", (r) => json(r, { found: null }));
  await p.goto("http://localhost:3000/#case", { waitUntil: "networkidle" });
  await p.locator("#case").scrollIntoViewIfNeeded();
  await p.waitForTimeout(2200);
  const overflow = await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  await p.locator("#case").screenshot({ path: `${out}/${name}.png` });
  console.log(name, "horizontal overflow px:", overflow);
  await p.close();
}
await b.close();
