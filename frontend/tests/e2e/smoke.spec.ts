/**
 * Smoke tests on the real no-key stack (backend without model keys, seeded with real inputs only).
 * Run: npm run backend & npm run seed, then npm run test:e2e
 */
import { expect, test, type Page } from "@playwright/test";
import { FIXTURE_BANNER, journeyFixture, traceFixture } from "../fixtures/trace-fixture";

const FORBIDDEN_BRANDS = /\b(DPD|BEUMER|PosLaju|Pos Laju|Skynet|J&T|Ninja Van|FedEx|UPS|DHL|FORTNA)\b/;
const TRUTH = /render_truth|flow_truth|\/truth\//;

async function firstCase(page: Page): Promise<string> {
  const r = await page.request.get("/api/spoor/v1/cases");
  expect(r.ok(), "backend reachable through the proxy (npm run backend, npm run seed)").toBeTruthy();
  const cases = await r.json();
  expect(cases.length, "seeded case exists (npm run seed)").toBeGreaterThan(0);
  return cases[0].case.case_id as string;
}

function watchRequests(page: Page) {
  const urls: string[] = [];
  page.on("request", (r) => urls.push(r.url()));
  return urls;
}

test("backend runs without model keys and the UI says so", async ({ page }) => {
  const caps = await (await page.request.get("/api/spoor/v1/capabilities")).json();
  expect(caps.sam).toBe(false);
  expect(caps.spark).toBe(false);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Cases", exact: true })).toBeVisible();
  await expect(page.getByText("No model keys")).toBeVisible();
  await expect(page.getByText("Off", { exact: true })).toBeVisible();
});

test("cases page lists the seeded case and has no real brands", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("link", { name: /Where did parcel CTX/ })).toBeVisible();
  expect(await page.locator("body").innerText()).not.toMatch(FORBIDDEN_BRANDS);
});

test("signature interaction: last confirmed opens the exact source frame", async ({ page }) => {
  const urls = watchRequests(page);
  const caseId = await firstCase(page);
  await page.goto(`/cases/${caseId}`);
  await page.getByTestId("where-did-it-go").click();
  const source = page.locator("#source-panel");
  await expect(source.getByText("last confirmed", { exact: true })).toBeVisible();
  await expect(source.getByText("Cameras that see this read point")).toBeVisible();
  const img = source.locator(".sp-frame-img img").first();
  await expect(img).toBeVisible();
  await expect.poll(async () => img.evaluate((el: HTMLImageElement) => el.naturalWidth)).toBeGreaterThan(100);
  await expect(source.getByText(/Not an observation/)).toBeVisible();
  // provenance inline: media id and hash prefix
  await expect(source.getByText(/media_[0-9a-f]+/).first()).toBeVisible();
  expect(urls.filter((u) => TRUTH.test(u))).toEqual([]);
  expect(await page.locator("body").innerText()).not.toMatch(FORBIDDEN_BRANDS);
});

test("timeline shows clock-drift warnings for unverified clocks", async ({ page }) => {
  const caseId = await firstCase(page);
  await page.goto(`/cases/${caseId}`);
  const warn = page.locator("summary", { hasText: /clock warning/ });
  await expect(warn).toBeVisible();
  await warn.click();
  await expect(page.getByText(/clock unverified/).first()).toBeVisible();
});

test("agent panel streams real job events and shows the stored answer", async ({ page }) => {
  const caseId = await firstCase(page);
  await page.goto(`/cases/${caseId}`);
  await page.getByRole("tab", { name: "Agent" }).click();
  await expect(page.getByText(/analysis unavailable \(no API key\)/)).toBeVisible();
  await page.getByTestId("run-investigation").click();
  const events = page.getByRole("list", { name: "Job events" }).first();
  await expect(events.getByText("started")).toBeVisible();
  await expect(events.getByText(/investigating/)).toBeVisible();
  await expect(page.locator(".sp-answer").first()).toContainText(/NOT established|Never visibly confirmed|parcel/);
});

test("trace contract on a route-mocked FIXTURE: solid never bridges the grey gap", async ({ page }) => {
  const caseId = await firstCase(page);
  const state = await (await page.request.get(`/api/spoor/v1/cases/${caseId}/state`)).json();
  const obj = state.objects[0].object;
  await page.route(`**/api/spoor/v1/cases/${caseId}/replay**`, (route) =>
    route.fulfill({ json: traceFixture(caseId, obj.object_instance_id, obj.label) }));
  await page.route(`**/api/spoor/v1/cases/${caseId}/journey**`, (route) =>
    route.fulfill({ json: journeyFixture(caseId, obj.object_instance_id, obj.label) }));
  await page.goto(`/cases/${caseId}`);
  await page.evaluate((t) => {
    const b = document.createElement("div");
    b.textContent = t;
    b.setAttribute("style", "position:fixed;z-index:9999;top:0;left:50%;transform:translateX(-50%);background:#fbbf24;color:#111;padding:6px 12px;font:600 13px system-ui;border-radius:0 0 8px 8px");
    document.body.appendChild(b);
  }, FIXTURE_BANNER);
  await page.getByRole("button", { name: "2D journey" }).click();
  const solids = page.locator('[data-ev="observed"]');
  await expect(solids).toHaveCount(2);
  await expect(page.locator('[data-ev="inferred"]')).toHaveCount(0); // a gap is never drawn as a route
  const gap = { start: Date.UTC(2026, 9, 28, 6, 32, 14), end: Date.UTC(2026, 9, 28, 6, 32, 22) };
  for (const el of await solids.all()) {
    const from = Date.parse((await el.getAttribute("data-from"))!);
    const to = Date.parse((await el.getAttribute("data-to"))!);
    expect(from >= gap.end || to <= gap.start, "a solid run must not overlap the unknown interval").toBeTruthy();
  }
  await expect(page.getByRole("button", { name: /Unknown interval/ })).toBeVisible();
});

test("keyboard: skip link and timeline scrubber respond to keys", async ({ page }) => {
  const caseId = await firstCase(page);
  await page.goto(`/cases/${caseId}`);
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to content" })).toBeFocused();
  const scrub = page.getByRole("slider", { name: /Time scrubber/ });
  await scrub.focus();
  const before = await scrub.inputValue();
  await page.keyboard.press("ArrowRight");
  await expect.poll(() => scrub.inputValue()).not.toBe(before);
});

test("operator, graph and report pages load with explicit states", async ({ page }) => {
  const caseId = await firstCase(page);
  await page.goto("/operator");
  await expect(page.getByRole("heading", { name: "Inputs and inspection" })).toBeVisible();
  await expect(page.getByText("unavailable: no API key").first()).toBeVisible();
  await page.goto(`/cases/${caseId}/graph`);
  await expect(page.getByText(/None verified/)).toBeVisible();
  await page.goto(`/cases/${caseId}/report`);
  await expect(page.getByRole("heading", { name: "Versions" })).toBeVisible();
});

test("context playback: play runs the clip, pause lands on an exact original frame, still not an observation", async ({ page }) => {
  const caseId = await firstCase(page);
  await page.goto(`/cases/${caseId}`);
  await page.getByTestId("where-did-it-go").click();
  const frame = page.locator("#source-panel .sp-frame").first();
  const counter = frame.locator(".sp-num").first();
  await expect(counter).toHaveText(/frame \d+ \/ \d+/);
  const selected = Number(/frame (\d+)/.exec((await counter.textContent()) ?? "")![1]);
  await frame.getByTestId("play-clip").click();
  await expect(frame.locator("video")).toBeVisible();
  await expect(frame.getByText(/Context playback around the selected time/)).toBeVisible();
  await expect(frame.getByText(/Not an observation/)).toBeVisible();
  await page.waitForTimeout(2500);
  await frame.getByTestId("pause-clip").click();
  await expect(frame.locator("video")).toHaveCount(0);
  const paused = Number(/frame (\d+)/.exec((await counter.textContent()) ?? "")![1]);
  expect(paused).toBeGreaterThanOrEqual(selected - 31); // pre-roll is 3 s at 10 fps
  const img = frame.locator(".sp-frame-img img").last();
  await expect(img).toHaveAttribute("alt", new RegExp(`frame ${paused}$`));
  await expect.poll(async () => img.evaluate((el: HTMLImageElement) => el.naturalWidth)).toBeGreaterThan(100);
});

test("camera wall: synchronized tiles from imported footage, honest states, no truth requests", async ({ page }) => {
  const urls = watchRequests(page);
  const caseId = await firstCase(page);
  const idx = await (await page.request.get("/api/scenarios")).json();
  expect(JSON.stringify(idx)).not.toMatch(/expected_answer|scenario_card|truth/);
  await page.goto(`/wall?case=${caseId}`);
  await expect(page.getByRole("heading", { name: "Camera wall" })).toBeVisible();
  const videos = page.locator(".sp-wall-tile video");
  await expect(videos.first()).toBeVisible();
  await expect.poll(() => videos.first().evaluate((v: HTMLVideoElement) => v.readyState)).toBeGreaterThan(0);
  await page.getByTestId("wall-play").click();
  await page.waitForTimeout(2000);
  await page.getByTestId("wall-play").click();
  const times = await videos.evaluateAll((vs) => vs.map((v) => (v as HTMLVideoElement).currentTime));
  expect(times[0]).toBeGreaterThan(0.5);
  for (const t of times) expect(Math.abs(t - times[0])).toBeLessThan(0.05); // one wall clock
  if (!idx.found) {
    await page.goto("/wall?scenario=S2");
    await expect(page.getByText(/not written yet|not in the manifest/).first()).toBeVisible();
  }
  expect(urls.filter((u) => TRUTH.test(u))).toEqual([]);
});

test("camera wall: click enlarges one tile, the rest become a strip; click again restores", async ({ page }) => {
  const caseId = await firstCase(page);
  await page.goto(`/wall?case=${caseId}`);
  const tiles = page.locator(".sp-wall-tile");
  await expect(tiles.first()).toBeVisible();
  const n = await tiles.count();
  await tiles.nth(0).click();
  await expect(page.locator(".sp-wall-tile[data-focused]")).toHaveCount(1);
  const big = await tiles.nth(0).boundingBox();
  const small = n > 1 ? await tiles.nth(1).boundingBox() : null;
  if (small) expect(big!.width).toBeGreaterThan(small.width * 1.5);
  await tiles.nth(0).click();
  await expect(page.locator(".sp-wall-tile[data-focused]")).toHaveCount(0);
});
