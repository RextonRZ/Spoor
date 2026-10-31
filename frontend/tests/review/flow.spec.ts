/**
 * Review pack for the flow (review/refs/flow): every screen at 1440 x 900 (desktop) and 390 wide (mobile, full page),
 * written to review_pack/flow/{project}_{nn}_{screen}.png. Runs on the S2 demo store.
 */
import { expect, test, type Page } from "@playwright/test";

async function caseId(page: Page) {
  const cases = await (await page.request.get("/api/spoor/v1/cases")).json();
  return cases[0].case.case_id as string;
}

const SHOTS: [string, string, RegExp][] = [
  ["01_hub", "/hub", /attention|on track/], ["02_investigating", "/investigate", /Search map/], ["03_answer", "", /How sure|No scans/],
  ["04_proof", "/proof", /Every camera on its route/], ["05_golook", "/search", /Not here|Send to the floor|Every place|Found\./],
  ["06_report", "/report", /Share report/], ["07_cameras", "/wall", /The whole hub at/], ["08_cases", "/", /Cases/],
];

for (const [name, path, content] of SHOTS) {
  test(name, async ({ page }, info) => {
    const top = path === "/hub" || path === "/wall" || path === "/";
    await page.goto(top ? path : `/cases/${await caseId(page)}${path}`);
    await expect(page.locator("main")).toContainText(content, { timeout: 30_000 });
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(name === "02_investigating" ? 9000 : 1500);
    await page.screenshot({ path: `review_pack/flow/${info.project.name}_${name}.png`, fullPage: info.project.name === "mobile" });
  });
}
