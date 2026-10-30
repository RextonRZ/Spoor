/**
 * Review pack for block H (journey_view_0030): H2 2D journey + replay, H10 missing moment, H14 case summary, H15 hub
 * dashboard on the REAL no-key stack, and H1 follow-cam on a labelled fixture (names start with "fx_").
 *
 * The H1 fixture is built from real material: the boxes are SAM 3.1 output from the J1 smoke test on CAM_07
 * (backend/scripts/smoke/out/sam_video_*.json, frames 220-229 of the CAM_07 clip), and the pixels are the backend's
 * real crop of those original frames. Only the link between that track and the case is injected (route mock), so every
 * fixture shot carries the yellow TEST FIXTURE banner. Style v2 (?style=v2) is on: it is the direction under review.
 */
import { expect, test, type Page, type Route, type TestInfo } from "@playwright/test";

const isMobile = (info: TestInfo) => info.project.name === "mobile";
const shot = async (page: Page, info: TestInfo, name: string, full = false) => {
  await settled(page);
  await page.screenshot({ path: `review_pack/${info.project.name}/${name}.png`, fullPage: full || isMobile(info) });
};

const CAM07_MEDIA = "media_4e3731fecba75f126b67";
const SAM_BOXES: [number, [number, number, number, number]][] = [
  [220, [678, 262, 704, 288]], [221, [686, 263, 713, 289]], [222, [694, 264, 721, 290]], [223, [703, 265, 730, 290]],
  [224, [712, 265, 740, 291]], [225, [720, 265, 749, 292]], [226, [729, 266, 759, 292]], [227, [738, 267, 767, 293]],
  [228, [747, 267, 777, 293]], [229, [756, 267, 786, 294]],
];
const FIX_BANNER = "TEST FIXTURE: real SAM 3.1 boxes (J1 smoke) on real CAM_07 frames, linked to this case by a route mock. Not case evidence.";
const t0 = Date.parse("2026-10-28T06:32:07.000Z"); // CAM_07 clip start (coverage)
const tOf = (frame: number) => new Date(t0 + frame * 100).toISOString();

/** Before any capture: no loading states left and every visible image decoded (F-style-b review #1). */
async function settled(page: Page) {
  await page.waitForFunction(() => {
    const visible = (el: Element) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < innerHeight; };
    const imgs = [...document.images].filter(visible);
    const loading = [...document.querySelectorAll('[role="status"]')].some((el) => visible(el) && /Loading/i.test(el.textContent ?? ""));
    return !loading && imgs.every((i) => i.complete && i.naturalWidth > 0 && i.dataset.loaded !== undefined || !i.classList.contains("sp-fade") && i.complete && i.naturalWidth > 0);
  }, undefined, { timeout: 45_000 }).catch(() => {});
  await page.waitForTimeout(400);
}

async function role(page: Page, r: "investigator" | "reviewer" | "site_admin") {
  await page.request.post("/api/session", { data: { role: r } });
}
async function caseId(page: Page) {
  const cases = await (await page.request.get("/api/spoor/v1/cases")).json();
  return cases[0].case.case_id as string;
}
async function banner(page: Page, text: string) {
  await page.evaluate((t) => {
    const b = document.createElement("div");
    b.textContent = t;
    b.setAttribute("style", "position:fixed;z-index:9999;top:0;left:50%;transform:translateX(-50%);background:#fbbf24;color:#111;padding:6px 12px;font:600 13px system-ui;border-radius:0 0 8px 8px;max-width:92vw;text-align:center");
    document.body.appendChild(b);
  }, text);
}
async function scrub(page: Page, iso: string) {
  await page.evaluate((ms) => {
    const r = document.querySelector<HTMLInputElement>(".sp-tl-range")!;
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(r, String(ms));
    r.dispatchEvent(new Event("input", { bubbles: true }));
  }, Date.parse(iso));
}
async function openWorkspace(page: Page, id: string) {
  await page.goto(`/cases/${id}?style=v2`);
  await page.getByTestId("replay-play").waitFor({ state: "attached", timeout: 90_000 });
  const sceneTab = page.locator(".sp-ws-tabs").getByRole("button", { name: "Scene", exact: true });
  if (await sceneTab.isVisible()) await sceneTab.click(); // mobile: the plan measures its box only when shown
  await expect(page.locator(".hp-over")).toBeAttached({ timeout: 120_000 });
  await page.waitForTimeout(1500);
}
async function tab(page: Page, info: TestInfo, name: string) {
  if (isMobile(info)) await page.locator(".sp-ws-tabs").getByRole("button", { name, exact: true }).click();
}

test.beforeEach(async ({ page }) => role(page, "investigator"));

test("H2 2D journey: typed ribbon, scan beads, trail end, replay marker on an inferred stretch", async ({ page }, info) => {
  const id = await caseId(page);
  await openWorkspace(page, id);
  await tab(page, info, "Scene");
  await expect(page.locator('[data-ev="inferred"]')).toHaveCount(2);
  await scrub(page, "2026-10-28T06:32:22.000Z");
  await expect(page.getByTestId("replay-marker")).toHaveAttribute("data-kind", "inferred");
  await expect(page.getByTestId("replay-status")).toContainText("inferred position on the belt route");
  await shot(page, info, "30_h2_journey_inferred");
  await scrub(page, "2026-10-28T06:32:40.000Z");
  await expect(page.getByTestId("replay-marker")).toHaveCount(0); // never a position inside a gap
  await expect(page.getByTestId("replay-status")).toContainText("Unknown since 14:32:31.8");
  await shot(page, info, "30b_h2_journey_unknown_after_last");
});

test("H10 missing moment: frames at the predicted time with the expected place dashed", async ({ page }, info) => {
  const id = await caseId(page);
  await openWorkspace(page, id);
  if (isMobile(info)) await tab(page, info, "Moment"); else await page.getByTestId("tab-moment").click();
  const mm = page.getByTestId("missing-moment");
  await expect(mm).toContainText("Where it should have appeared next");
  await expect(mm.locator(".mm-close img").first()).toBeVisible({ timeout: 30_000 });
  await page.waitForTimeout(1500);
  if (isMobile(info)) await shot(page, info, "31_h10_missing_moment");
  else { await settled(page); await page.locator("#source-panel").screenshot({ path: `review_pack/${info.project.name}/31_h10_missing_moment.png` }); }
});

test("H14 case summary and H15 hub dashboard", async ({ page }, info) => {
  const id = await caseId(page);
  await page.goto(`/cases/${id}/summary?style=v2`);
  await expect(page.getByTestId("case-answer")).toHaveText("Last confirmed at chute C04 · 14:32:31.8 MYT");
  await expect(page.getByTestId("case-status")).toHaveText("Unknown");
  await page.waitForTimeout(2500);
  await shot(page, info, "33_h14_case_summary", true);
  await page.goto("/hub?style=v2");
  await expect(page.getByRole("heading", { name: "Hub dashboard" })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId("inbox-empty").or(page.locator(".hub .sp-table")).first()).toBeVisible();
  await page.waitForTimeout(2500);
  await shot(page, info, "34_h15_hub_home", true);
  // replay 30 min after the log ended (Operator clock): parcels whose next scan never came become stalled
  await page.evaluate(() => localStorage.setItem("spoor-inbox-clock", JSON.stringify({ kind: "log", minutes: 30 })));
  await page.reload();
  await expect(page.getByTestId("inbox-clock")).toContainText("30 min after the last imported scan", { timeout: 60_000 });
  await shot(page, info, "34b_h15_inbox_plus_30_min");
  await page.evaluate(() => localStorage.removeItem("spoor-inbox-clock"));
});

test("H1 follow-cam on a labelled fixture (real SAM boxes, real crops)", async ({ page }, info) => {
  const id = await caseId(page);
  const real = await (await page.request.get(`/api/spoor/v1/cases/${id}/journey`)).json();
  const obj = real.objects[0];
  obj.segments.unshift({
    kind: "observed", start: tOf(220), end: tOf(229), camera_id: "cam_CAM_07", track_id: "trk_fixture_j1",
    evidence_ids: SAM_BOXES.map(([f]) => `obs_fixture_${f}`),
    points: SAM_BOXES.map(([f], k) => ({ t: tOf(f), observation_id: `obs_fixture_${f}`, xy: [35 + k * 0.2, 11] })),
  });
  obj.observed_segments = 1;
  await page.route(`**/api/spoor/v1/cases/${id}/journey`, (r) => r.fulfill({ json: real }));
  await page.route("**/tracks/trk_fixture_j1/crop**", async (r: Route) => {
    const t = Date.parse(new URL(r.request().url()).searchParams.get("t")!);
    const [frame, box] = SAM_BOXES.reduce((b, x) => Math.abs(Date.parse(tOf(x[0])) - t) < Math.abs(Date.parse(tOf(b[0])) - t) ? x : b);
    const crop = await (await page.request.get(`/api/spoor/v1/media/${CAM07_MEDIA}/frames/${frame}/crop?box=${box.join(",")}`)).json();
    await r.fulfill({ json: { ...crop, track_id: "trk_fixture_j1", t: tOf(frame), observed_frames: SAM_BOXES.map(([f]) => f),
      identity: { label: "TEST FIXTURE track", identity_keys: ["carrier_waybill:TESTFIXTURE"],
        association: { status: "human_confirmed", confirmed: true, reason: "TEST FIXTURE", by: "fixture" },
        scans: obj.scans.map((s: { scan_event_id: string; t: string; event_kind: string; raw_code: string; station_id: string }) =>
          ({ scan_event_id: s.scan_event_id, t: s.t, event_kind: s.event_kind, raw_code: s.raw_code, station_id: s.station_id,
            raw_description: (s as { raw_description?: string }).raw_description ?? null })) } } });
  });
  await openWorkspace(page, id);
  await scrub(page, tOf(224));
  await tab(page, info, "Source"); // the follow-cam is the top of the CCTV hero
  const img = page.getByTestId("followcam").locator("img");
  await expect(img).toBeVisible({ timeout: 30_000 });
  await expect.poll(() => img.evaluate((el: HTMLImageElement) => el.complete && el.naturalWidth), { timeout: 30_000 }).toBeGreaterThan(0);
  if (!isMobile(info)) await expect(page.getByTestId("replay-marker")).toHaveAttribute("data-kind", "observed");
  await page.waitForTimeout(1200);
  await banner(page, FIX_BANNER);
  await shot(page, info, "fx_32_h1_followcam");
});

test("H5 records vs video: real lanes, and the red pin on a labelled fixture", async ({ page }, info) => {
  const id = await caseId(page);
  await page.goto(`/cases/${id}/summary?style=v2`);
  const rv = page.getByTestId("records-vs-video");
  await expect(rv).toContainText("no confirmed track yet", { timeout: 60_000 });
  await settled(page);
  await rv.screenshot({ path: `review_pack/${info.project.name}/35_h5_records_vs_video.png` });
  const real = await (await page.request.get(`/api/spoor/v1/cases/${id}/conflicts`)).json();
  const o = real.objects[0];
  o.video = [{ start: "2026-10-28T06:32:38.000Z", end: "2026-10-28T06:32:44.000Z", camera_id: "cam_CAM_19" }];
  o.records.push({ t: "2026-10-28T06:32:35.000Z", words: "RC-864 container loaded at SP-LOAD-D07", zone_id: "zone_Z12", evidence_id: "scan_fixture", claim: "departure" }); // S2 card: RC-864 -> D07
  o.conflicts = [{ kind: "departure", divergence_t: "2026-10-28T06:32:38.000Z",
    statement: "fixture", claim: { t: "2026-10-28T06:32:35.000Z", zone_id: "zone_Z12", words: "RC-864 container loaded at SP-LOAD-D07" },
    observation: { t: "2026-10-28T06:32:38.000Z", camera_id: "cam_CAM_19", zone_id: "zone_Z11" } }];
  o.note = null;
  await page.route(`**/api/spoor/v1/cases/${id}/conflicts`, (r) => r.fulfill({ json: real }));
  await page.reload();
  await expect(rv).toContainText("1 disagreement", { timeout: 60_000 });
  await banner(page, "TEST FIXTURE: the sighting and the conflict are route-mocked to show the red pin. Not case evidence.");
  await settled(page);
  await rv.screenshot({ path: `review_pack/${info.project.name}/fx_35b_h5_records_vs_video_conflict.png` });
});

test("H11 camera moment: the cameras around the break point at one instant", async ({ page }, info) => {
  const id = await caseId(page);
  await openWorkspace(page, id);
  if (isMobile(info)) await tab(page, info, "Cameras"); else await page.getByTestId("tab-cameras").click();
  const g = page.getByTestId("camera-grid");
  await expect(g).toContainText("on every camera", { timeout: 60_000 });
  await expect(g.locator(".cg-tile img").first()).toBeVisible({ timeout: 30_000 });
  if (isMobile(info)) await shot(page, info, "36_h11_camera_moment");
  else { await settled(page); await page.locator("#source-panel").screenshot({ path: `review_pack/${info.project.name}/36_h11_camera_moment.png` }); }
});

test("H12 floor search checklist (task + found state route-mocked from the real computed places)", async ({ page }, info) => {
  const id = await caseId(page);
  const poss = await (await page.request.get(`/api/spoor/v1/cases/${id}/possible-locations`)).json();
  const places = poss.objects[0].places.filter((p: { possible_share: number }) => p.possible_share > 0).slice(0, 4)
    .map((p: { area_id: string; name: string; zone_id: string | null; evidence_for: string[] }) => ({ area_id: p.area_id, name: p.name, zone_id: p.zone_id, why: p.evidence_for }));
  const task = { search_task_id: "srch_fixture", created_by: "investigator_01", created_at: "2026-10-31T05:00:00Z", places,
    outcomes: [{ area_id: places[0].area_id, outcome: "not_found", recorded_by: "investigator_01", recorded_at: "2026-10-28T07:10:00Z" }] }; // after the event (15:10 MYT)
  await page.route(`**/api/spoor/v1/cases/${id}/search-tasks`, (r) => r.fulfill({ json: { status: "searching", found: null,
    not_here: [places[0].area_id], tasks: [task] } }));
  await page.goto(`/cases/${id}/search?style=v2`);
  await expect(page.getByRole("button", { name: "Found it here" }).first()).toBeVisible({ timeout: 60_000 });
  await banner(page, "TEST FIXTURE: search task and outcome route-mocked (no outcome was written to the case).");
  await shot(page, info, "fx_37_h12_search_checklist", true);
});
