// Visual check of the hero board with a case that matches the footage, before the S2 case is reseeded: serves the
// S2 subject's real scan lines (build/sim scan log) in place of the API's case responses, for this browser only.
// node scripts/landing-board-mock.mjs <outdir>
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
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
const json = (route, body) => route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
await p.route("**/api/spoor/v1/cases", (r) => json(r, [{ case: { case_id: "mock" } }]));
await p.route("**/api/spoor/v1/cases/mock/journey", (r) => json(r, { objects: [{ label: `parcel ${pid}`, identity_keys: [`carrier_waybill:${pid}`], scans }] }));
await p.route("**/api/spoor/v1/cases/mock/conflicts", (r) => json(r, { objects: [{ conflicts: [] }] }));
await p.route("**/api/spoor/v1/cases/mock/missing-moment", (r) => json(r, { objects: [{ expected_next: [] }] }));
await p.route("**/api/spoor/v1/cases/mock/possible-locations", (r) => json(r, { objects: [{ places: [] }] }));
await p.route("**/api/spoor/v1/cases/mock/search-tasks", (r) => json(r, { found: null }));
await p.goto("http://localhost:3000/", { waitUntil: "networkidle" });
const at = async (phase, extra, name) => {
  await p.waitForFunction((ph) => document.querySelector(".lp-feed-hero")?.dataset.phase === ph, phase, { timeout: 60000 });
  await p.waitForTimeout(extra);
  await p.screenshot({ path: `${out}/${name}.png` });
};
await at("open", 900, "mock_open");
await at("red", 2200, "mock_red");
await at("board", 13500, "mock_board_end");
await b.close();
console.log("ok", scans.length, "scans");
