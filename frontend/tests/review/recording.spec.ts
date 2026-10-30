/**
 * Screen recording of the signature interaction (PRD §19.3) on the real no-key stack, then the trace renderer on a
 * route-mocked TEST FIXTURE (banner visible). Output: Playwright webm, converted by scripts/make-recording.mjs.
 */
import { writeFileSync } from "node:fs";
import { expect, test, type Page } from "@playwright/test";
import { FIXTURE_BANNER, traceFixture } from "../fixtures/trace-fixture";

const CLICK_RING = `
  addEventListener("pointerdown", (e) => {
    const d = document.createElement("div");
    d.style.cssText = "position:fixed;z-index:10000;pointer-events:none;width:28px;height:28px;margin:-14px 0 0 -14px;"
      + "border:3px solid #a99bff;border-radius:50%;left:" + e.clientX + "px;top:" + e.clientY + "px;transition:opacity .6s";
    document.body.appendChild(d);
    setTimeout(() => { d.style.opacity = "0"; }, 350);
    setTimeout(() => d.remove(), 1000);
  }, true);`;

async function caption(page: Page, text: string) {
  await page.evaluate((t) => {
    let c = document.getElementById("rec-caption");
    if (!c) {
      c = document.createElement("div");
      c.id = "rec-caption";
      c.setAttribute("style", "position:fixed;z-index:9998;left:50%;bottom:14px;transform:translateX(-50%);background:rgba(14,16,18,.92);color:#f3f5f7;border:1px solid rgba(226,232,238,.25);padding:7px 14px;border-radius:10px;font:600 14px system-ui;max-width:90vw;text-align:center");
      document.body.appendChild(c);
    }
    c.textContent = t;
  }, text);
}

test("signature interaction", async ({ page }) => {
  test.skip(true, "superseded (F-039): the 2D plan now draws the backend journey, not the replay trace; see journey.spec H1/H2 and journey-recording.spec");
  await page.request.post("/api/session", { data: { role: "investigator" } });
  await page.addInitScript(CLICK_RING);
  const t0 = Date.now(); // the page video starts with the page; cuts below are seconds from here
  const cuts: [number, number][] = [];
  const sec = () => (Date.now() - t0) / 1000;
  const cases = await (await page.request.get("/api/spoor/v1/cases")).json();
  const id = cases[0].case.case_id as string;

  await page.goto("/");
  await caption(page, "No-key mode: real inputs only (synthetic footage, simulated scan log)");
  await page.waitForTimeout(1800);
  await page.getByRole("link", { name: /Where did parcel/ }).first().click();
  let cutFrom = sec() + 0.6;
  await page.getByRole("button", { name: "3D", exact: true }).click({ timeout: 120_000 });
  await page.getByRole("button", { name: "Synthetic hub model" }).click();
  await page.locator('.sp-scene[data-ready="true"]').waitFor({ timeout: 120_000 });
  await page.waitForTimeout(800);
  cuts.push([cutFrom, sec() - 0.3]); // no dead air while the 3D scene loads
  await caption(page, "Where did the parcel go?");
  await page.waitForTimeout(1500);
  await page.getByTestId("where-did-it-go").click();
  await caption(page, "Scene moves to the last confirmed read; the camera that sees it lights up");
  await page.waitForTimeout(3500);
  await caption(page, "Source: the original frame at that time, labelled context, not an observation");
  await page.getByRole("button", { name: "Next frame" }).first().click();
  await page.waitForTimeout(1200);
  await page.getByRole("button", { name: "Next frame" }).first().click();
  await page.waitForTimeout(1500);
  await caption(page, "Earlier scans on the one timeline; clocks flagged unverified");
  await page.locator(".sp-tl-scan").first().click();
  await page.waitForTimeout(2500);
  await page.getByRole("tab", { name: "Agent" }).click();
  await caption(page, "Investigation runs without a language model: real job events over SSE");
  await page.getByTestId("run-investigation").click();
  await expect(page.locator(".sp-answer").first()).toBeVisible({ timeout: 60_000 });
  await page.waitForTimeout(3500);

  // Part 2: trace renderer on a route-mocked fixture (no observations exist without SAM).
  const state = await (await page.request.get(`/api/spoor/v1/cases/${id}/state`)).json();
  const obj = state.objects[0].object;
  await page.route(`**/api/spoor/v1/cases/${id}/replay**`, (r) => r.fulfill({ json: traceFixture(id, obj.object_instance_id, obj.label) }));
  const media = await (await page.request.get(`/api/spoor/v1/sites/${state.case.site_id}/media`)).json();
  const cam07 = media.find((m: { media: { camera_id: string } }) => m.media.camera_id === "cam_CAM_07");
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
  cutFrom = sec();
  await page.reload();
  await page.evaluate((t) => {
    const b = document.createElement("div");
    b.textContent = t;
    b.setAttribute("style", "position:fixed;z-index:9999;top:0;left:50%;transform:translateX(-50%);background:#fbbf24;color:#111;padding:6px 12px;font:600 13px system-ui;border-radius:0 0 8px 8px");
    document.body.appendChild(b);
  }, FIXTURE_BANNER);
  await page.locator('.sp-scene[data-ready="true"]').waitFor({ timeout: 120_000 });
  await page.waitForTimeout(1500); // auto-frame to the trace finishes
  await caption(page, "Green solid = observed; amber dashed = hypothesis; grey = unknown, no path");
  await page.waitForTimeout(300);
  cuts.push([cutFrom, sec() - 0.3]);
  await page.waitForTimeout(3000);
  await page.getByRole("button", { name: "2D journey" }).click();
  await page.waitForTimeout(2000);
  await page.locator('polyline[data-ev="observed"]').first().click({ force: true });
  await caption(page, "Click a segment: its exact source frame opens");
  await page.waitForTimeout(3000);
  await page.getByRole("button", { name: /Unknown interval/ }).click();
  await caption(page, "The unknown interval: solid never bridges it");
  await page.waitForTimeout(2500);
  writeFileSync("test-results/recording-cuts.json", JSON.stringify(cuts));
});
