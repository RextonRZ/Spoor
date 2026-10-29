/**
 * Review pack: one screenshot per surface and state, per viewport (frontend/review_pack/<project>/NN_name.png).
 * Runs against the real no-key stack. Fixture screenshots (names start with "fx_") use a route-mocked trace and carry
 * a visible TEST FIXTURE banner.
 */
import { expect, test, type Page, type TestInfo } from "@playwright/test";
import { FIXTURE_BANNER, traceFixture } from "../fixtures/trace-fixture";

const isMobile = (info: TestInfo) => info.project.name === "mobile";

async function shot(page: Page, info: TestInfo, name: string, full = false) {
  await page.waitForTimeout(400);
  await page.screenshot({ path: `review_pack/${info.project.name}/${name}.png`, fullPage: full || isMobile(info) });
}

/** Desktop shows every pane at once, so pane states are captured as element shots (one file per distinct state). */
async function shotPane(page: Page, info: TestInfo, name: string, selector: string) {
  if (isMobile(info)) return shot(page, info, name);
  await page.waitForTimeout(400);
  await page.locator(selector).first().screenshot({ path: `review_pack/${info.project.name}/${name}.png` });
}

async function role(page: Page, r: "investigator" | "reviewer" | "site_admin") {
  await page.request.post("/api/session", { data: { role: r } });
}

async function caseId(page: Page) {
  const cases = await (await page.request.get("/api/spoor/v1/cases")).json();
  return cases[0].case.case_id as string;
}

async function waitScene(page: Page) {
  const scene = page.locator(".sp-scene");
  if (await scene.waitFor({ state: "attached", timeout: 30_000 }).then(() => true, () => false)) {
    await page.locator('.sp-scene[data-ready="true"]').waitFor({ state: "attached", timeout: 120_000 }).catch(() => {});
  }
  await page.waitForTimeout(2500);
}

async function mobileTab(page: Page, info: TestInfo, name: string) {
  if (isMobile(info)) await page.locator(".sp-ws-tabs").getByRole("button", { name, exact: true }).click();
}

async function banner(page: Page) {
  await page.evaluate((t) => {
    const b = document.createElement("div");
    b.textContent = t;
    b.setAttribute("style", "position:fixed;z-index:9999;top:0;left:50%;transform:translateX(-50%);background:#fbbf24;color:#111;padding:6px 12px;font:600 13px system-ui;border-radius:0 0 8px 8px;max-width:92vw;text-align:center");
    document.body.appendChild(b);
  }, FIXTURE_BANNER);
}

test.beforeEach(async ({ page }) => role(page, "investigator"));

test("cases", async ({ page }, info) => {
  await page.goto("/");
  await expect(page.getByRole("link", { name: /Where did parcel/ })).toBeVisible();
  await shot(page, info, "01_cases", true);
});

test("workspace: overview, last confirmed, plan, people mode, timeline, frame step", async ({ page }, info) => {
  const id = await caseId(page);
  await page.goto(`/cases/${id}`);
  await waitScene(page);
  await shot(page, info, "02_workspace_3d_overview");
  await mobileTab(page, info, "Case");
  await page.getByTestId("where-did-it-go").click();
  await mobileTab(page, info, "Scene");
  await waitScene(page);
  await shot(page, info, "03_workspace_3d_last_confirmed");
  await mobileTab(page, info, "Source");
  await expect(page.locator(".sp-frame-img img").first()).toBeVisible();
  await page.waitForTimeout(1500);
  await shotPane(page, info, "04_source_context_frame", "#source-panel");
  await page.getByRole("button", { name: "Next frame" }).first().click();
  await page.waitForTimeout(1500);
  await shotPane(page, info, "05_source_frame_stepped", "#source-panel");
  await mobileTab(page, info, "Scene");
  await page.getByRole("button", { name: "2D plan" }).click();
  await shot(page, info, "06_workspace_2d_plan");
  await mobileTab(page, info, "Case");
  await page.getByRole("button", { name: "People (anonymous)" }).click();
  await mobileTab(page, info, "Scene");
  await shot(page, info, "07_trace_people_mode");
  await mobileTab(page, info, "Case");
  await page.getByRole("button", { name: "Object", exact: true }).click();
  await shotPane(page, info, "08_case_overview", ".sp-ws-left");
  await mobileTab(page, info, "Timeline");
  await page.locator("summary", { hasText: /clock warning/ }).click();
  await shotPane(page, info, "09_timeline_clock_warnings", ".sp-ws-time");
});

test("agent panel: real job events and answer", async ({ page }, info) => {
  const id = await caseId(page);
  await page.goto(`/cases/${id}`);
  if (isMobile(info)) await mobileTab(page, info, "Agent");
  else await page.getByRole("tab", { name: "Agent" }).click();
  await shot(page, info, "10_agent_before_run");
  await page.getByTestId("run-investigation").click();
  await expect(page.locator(".sp-answer").first()).toBeVisible({ timeout: 60_000 });
  await shot(page, info, "11_agent_after_run");
});

test("evidence graph", async ({ page }, info) => {
  const id = await caseId(page);
  await page.goto(`/cases/${id}/graph`);
  await expect(page.getByText(/None verified/)).toBeVisible();
  await page.locator("[data-node]").first().click();
  await shot(page, info, "12_evidence_graph", true);
});

test("report: draft by investigator, approval by reviewer", async ({ page }, info) => {
  const id = await caseId(page);
  await page.goto(`/cases/${id}/report`);
  await page.getByRole("button", { name: "Export a new draft" }).click();
  await expect(page.getByText(/Draft exported/)).toBeVisible();
  await expect(page.locator("iframe[title='Report preview']")).toBeVisible();
  await page.waitForTimeout(1000);
  await shot(page, info, "13_report_draft", true);
  await role(page, "reviewer");
  await page.reload();
  await page.getByRole("button", { name: "Approve this draft" }).click();
  await expect(page.getByText(/Approved\. Report hash/)).toBeVisible();
  await page.waitForTimeout(1000);
  await shot(page, info, "14_report_approved", true);
});

test("operator page as site admin", async ({ page }, info) => {
  await role(page, "site_admin");
  await page.goto("/operator");
  await expect(page.getByRole("heading", { name: "Inputs and inspection" })).toBeVisible();
  await expect(page.getByText(/unavailable: no API key/).first()).toBeVisible();
  await page.waitForTimeout(1500);
  await shot(page, info, "15_operator", true);
});

test("FIXTURE: trace renderer with observed, hypothesis and unknown", async ({ page }, info) => {
  const id = await caseId(page);
  const state = await (await page.request.get(`/api/spoor/v1/cases/${id}/state`)).json();
  const obj = state.objects[0].object;
  const media = await (await page.request.get(`/api/spoor/v1/sites/${state.case.site_id}/media`)).json();
  const cam07 = media.find((m: { media: { camera_id: string } }) => m.media.camera_id === "cam_CAM_07");
  await page.route(`**/api/spoor/v1/cases/${id}/replay**`, (r) => r.fulfill({ json: traceFixture(id, obj.object_instance_id, obj.label) }));
  await page.route(`**/api/spoor/v1/cases/${id}/evidence/obs_fixture_*`, async (r) => {
    const fa = await (await page.request.get(`/api/spoor/v1/media/${cam07.media.media_id}/frame-at?time=2026-10-28T06:32:12.000Z`)).json();
    await r.fulfill({ json: {
      observation: { observation_id: "obs_fixture_3", source_type: "video", camera_id: "cam_CAM_07", label: "TEST FIXTURE parcel",
        source_frame: { media_id: cam07.media.media_id, frame_index: fa.frame_index, pts_ms: fa.pts_ms,
          normalized_utc: "2026-10-28T06:32:12.000Z", time_uncertainty_ms: 5000 },
        bbox_xyxy_px: null, quality_flags: [], provenance: null, confidence_raw: null, confidence_calibrated: null },
      invalidated: false, estimate: { spatial_mode: "floor_xy", floor_xy_m: [35.5, 11], uncertainty_radius_m: 0.4,
        zone_id: "zone_Z05", method: "TEST FIXTURE" },
      media: { media_id: cam07.media.media_id, sha256: cam07.media.sha256, kind: "original", flags: [] },
      frame_url: fa.frame_url, annotated_frame_url: fa.frame_url, asset_label: "original" } });
  });
  await page.goto(`/cases/${id}`);
  await banner(page);
  await waitScene(page);
  await shot(page, info, "fx_16_trace_3d");
  await mobileTab(page, info, "Scene");
  await page.getByRole("button", { name: "2D plan" }).click();
  await shot(page, info, "fx_17_trace_plan");
  await page.locator('polyline[data-ev="observed"]').first().click({ force: true });
  await mobileTab(page, info, "Source");
  await expect(page.getByText(/Observed · TEST FIXTURE/)).toBeVisible();
  await page.waitForTimeout(1500);
  await shotPane(page, info, "fx_18_segment_source", "#source-panel");
  await mobileTab(page, info, "Timeline");
  await page.getByRole("button", { name: /Unknown interval/ }).click();
  await shotPane(page, info, "fx_19_timeline_gap", ".sp-ws-time");
});

test("camera wall (review 007 #1): synchronized case footage, and the honest state before scenario renders exist", async ({ page }, info) => {
  const id = await caseId(page);
  await page.goto(`/wall?case=${id}`);
  const videos = page.locator(".sp-wall-tile video");
  await expect(videos.first()).toBeVisible();
  await expect.poll(() => videos.first().evaluate((v: HTMLVideoElement) => v.readyState)).toBeGreaterThan(1);
  await page.getByTestId("wall-play").click();
  await page.waitForTimeout(3000);
  await page.getByTestId("wall-play").click();
  await page.waitForTimeout(800);
  await shot(page, info, "20_camera_wall");
  await page.goto("/wall?scenario=S2");
  await expect(page.getByText(/not written yet|not in the manifest|Renders not produced yet/).first()).toBeVisible();
  await shot(page, info, "21_camera_wall_no_renders");
});

test("source panel context playback (review 007 #1)", async ({ page }, info) => {
  const id = await caseId(page);
  await page.goto(`/cases/${id}`);
  await mobileTab(page, info, "Case");
  await page.getByTestId("where-did-it-go").click();
  await mobileTab(page, info, "Source");
  const frame = page.locator("#source-panel .sp-frame").first();
  await expect(frame.locator(".sp-frame-img img")).toBeVisible();
  await frame.getByTestId("play-clip").click();
  await expect(frame.locator("video")).toBeVisible();
  await page.waitForTimeout(2500);
  await shotPane(page, info, "22_source_context_playing", "#source-panel");
  await frame.getByTestId("pause-clip").click();
  await expect(frame.locator(".sp-frame-img img").last()).toBeVisible();
  await page.waitForTimeout(1500);
  await shotPane(page, info, "23_source_paused_exact_frame", "#source-panel");
});

test("operator evaluation: headline source and caveat (review 007 #4)", async ({ page }, info) => {
  await role(page, "site_admin");
  await page.goto("/operator");
  const head = page.getByTestId("eval-headline-source");
  await expect(head).toBeVisible();
  await head.scrollIntoViewIfNeeded();
  await page.waitForTimeout(600);
  const panel = page.locator("section[aria-labelledby='ev-h']");
  if (isMobile(info)) await shot(page, info, "24_operator_evaluation_headline");
  else await panel.screenshot({ path: `review_pack/${info.project.name}/24_operator_evaluation_headline.png` });
});
