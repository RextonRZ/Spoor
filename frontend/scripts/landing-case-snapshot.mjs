// Saves the landing page's case (the story parcel's case in a seeded store) as public/landing/case.json: the exact
// read-model responses the page would fetch (journey, missing moment, possible places, conflicts, search tasks), so
// the public page shows the same checkpoints, captions and verdict when the app's backend holds another store.
// Re-run after every reseed (the S2 logs change with each hub run).
//   node scripts/landing-case-snapshot.mjs [api=http://127.0.0.1:8010]
import { readFileSync, writeFileSync } from "node:fs";
const API = process.argv[2] ?? "http://127.0.0.1:8010";
const env = Object.fromEntries(readFileSync(".env.local", "utf8").split("\n").filter((l) => l.includes("=") && !l.startsWith("#"))
  .map((l) => [l.slice(0, l.indexOf("=")).trim(), l.slice(l.indexOf("=") + 1).trim()]));
const token = env.SPOOR_TOKEN_SUPERVISOR || env.SPOOR_TOKEN_INVESTIGATOR;
const get = async (p) => {
  const r = await fetch(`${API}${p}`, { headers: { Authorization: `Bearer ${token}` } });
  if (!r.ok) throw new Error(`${p}: ${r.status}`);
  return r.json();
};
const parcel = JSON.parse(readFileSync("public/landing/landing.json", "utf8")).story_parcel;
let found = null;
for (const c of await get("/v1/cases")) {
  const j = await get(`/v1/cases/${c.case.case_id}/journey`);
  if (j.objects.some((o) => o.identity_keys.some((k) => k.endsWith(`:${parcel}`)))) { found = { id: c.case.case_id, journey: j }; break; }
}
if (!found) throw new Error(`no case for ${parcel} at ${API}`);
const views = { journey: found.journey };
for (const v of ["missing-moment", "possible-locations", "conflicts", "search-tasks"]) views[v] = await get(`/v1/cases/${found.id}/${v}`);
const scans = found.journey.objects[0].scans.length;
writeFileSync("public/landing/case.json", JSON.stringify({
  note: "Snapshot of the seeded S2 case's read models (simulated scan log, labelled scan_simulated). Made by scripts/landing-case-snapshot.mjs; not hand-edited.",
  parcel, case_id: found.id, saved_at: new Date().toISOString(), views,
}));
console.log(`case.json: ${parcel}, case ${found.id}, ${scans} scans`);
