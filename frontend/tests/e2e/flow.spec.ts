/**
 * The app is the flow in review/refs/flow (owner 09:04/09:22/09:24): Hub, Investigating, Answer, Proof, Go look, Report,
 * Cameras, plus Cases. Every screen: loads without page errors, shows its own content, has no em dash in visible text
 * (design_sprint §J), passes axe WCAG AA (no serious/critical), and has no role switch (one demo user).
 * Runs on whichever store the backend serves (the S2 demo store: `SPOOR_DATA=s2 npm run backend`).
 */
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

async function caseId(page: Page) {
  const cases = await (await page.request.get("/api/spoor/v1/cases")).json();
  return cases[0].case.case_id as string;
}

async function axe(page: Page) {
  const r = await new AxeBuilder({ page }).setLegacyMode(true).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).exclude("canvas").analyze();
  return r.violations.filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => `${v.id}: ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`);
}

const SCREENS: [string, string, RegExp][] = [
  ["Hub", "/hub", /need(s)? attention|Every parcel is on track/],
  ["Cases", "/", /Cases/],
  ["Cameras", "/wall", /The whole hub at/],
  ["Answer", "", /How sure|No scans of this parcel/],
  ["Investigating", "/investigate", /See the answer/], // audited once the run (or its replay) has finished
  ["Proof", "/proof", /Every camera on its route, in order/],
  ["Go look", "/search", /Not here|Send to the floor|Every place checked|Found\. Thank you/],
  ["Report", "/report", /Share report/],
  ["Settings", "/operator", /Settings/],
];

for (const [name, path, content] of SCREENS) {
  test(`${name}: loads, says what it should, no em dash, accessible, one user`, async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message.slice(0, 200)));
    const url = ["Hub", "Cases", "Cameras", "Settings"].includes(name) ? path : `/cases/${await caseId(page)}${path}`;
    await page.goto(url);
    await expect(page.locator("main")).toContainText(content, { timeout: 30_000 });
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(800);
    const text = await page.locator("body").innerText();
    expect(text.split("\n").filter((l) => l.includes("—")), "em dash on screen").toEqual([]);
    expect(text).not.toMatch(/Signed in as|View the demo as|Site admin/);
    expect(await axe(page)).toEqual([]);
    expect(errors).toEqual([]);
  });
}

test("Hub: Investigate leads to the Investigating screen, which streams real run steps", async ({ page }) => {
  await page.goto("/hub");
  const btn = page.getByRole("link", { name: /Investigate|Open case/ }).first();
  await expect(btn).toBeVisible({ timeout: 30_000 });
  await btn.click();
  await expect(page).toHaveURL(/\/cases\/[^/]+(\/investigate)?$/);
  if (page.url().endsWith("/investigate")) {
    await expect(page.locator(".iv-log-row").first()).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText(/Read \d+ scans?\./)).toBeVisible();
  }
});

test("Account menu: one supervisor, Settings, no role switch", async ({ page }) => {
  await page.goto("/hub");
  await page.getByRole("button", { name: "Account menu" }).click();
  const menu = page.getByRole("menu", { name: "Account" });
  await expect(menu).toContainText("Hub supervisor");
  await expect(menu.getByRole("menuitem", { name: "Settings & data" })).toBeVisible();
  expect(await menu.getByRole("menuitemradio").count()).toBe(0);
});

test("Go look: a held voice note is sent as 16 kHz mono 16-bit WAV (route mocked only to capture the upload)", async ({ browser }) => {
  const ctx = await browser.newContext({ permissions: ["microphone"] });
  const page = await ctx.newPage();
  const id = await caseId(page);
  const view = await (await page.request.get(`/api/spoor/v1/cases/${id}/search-tasks`)).json();
  test.skip(!view.tasks?.length || !!view.found, "needs an open search task (run Investigating once)");
  let body: Buffer | null = null;
  await page.route(`**/api/spoor/v1/cases/${id}/voice`, async (r) => {
    if (r.request().method() === "POST") { body = r.request().postDataBuffer(); return r.fulfill({ status: 201, json: {} }); }
    return r.fulfill({ json: { items: [], available: true, estimate: { usd_per_minute: 0.003 } } });
  });
  await page.goto(`/cases/${id}/search`);
  const hold = page.getByRole("button", { name: "Hold to add a voice note" });
  await expect(hold).toBeEnabled({ timeout: 30_000 });
  const box = (await hold.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.waitForTimeout(1500);
  await page.mouse.up();
  await expect.poll(() => body !== null, { timeout: 20_000 }).toBe(true);
  const buf = body as unknown as Buffer;
  const at = buf.indexOf("RIFF");
  expect(at).toBeGreaterThan(0);
  expect([buf.readUInt16LE(at + 22), buf.readUInt32LE(at + 24), buf.readUInt16LE(at + 34)]).toEqual([1, 16000, 16]);
  expect(buf.toString("latin1")).toContain('name="kind"');
  await ctx.close();
});
