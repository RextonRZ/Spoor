/** WCAG 2 AA checks (axe-core) on every surface of the running no-key stack. */
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

async function caseId(page: Page) {
  const cases = await (await page.request.get("/api/spoor/v1/cases")).json();
  return cases[0].case.case_id as string;
}

async function audit(page: Page) {
  const r = await new AxeBuilder({ page }).setLegacyMode(true).withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .exclude("canvas").exclude("iframe").analyze();
  const bad = r.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  return bad.map((v) => `${v.id}: ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`);
}

for (const path of ["/", "/operator", "/wall"]) {
  test(`a11y ${path}`, async ({ page }) => {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    expect(await audit(page)).toEqual([]);
  });
}

for (const sub of ["", "/graph", "/report"]) {
  test(`a11y case${sub || " workspace"}`, async ({ page }) => {
    await page.goto(`/cases/${await caseId(page)}${sub}`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1500);
    expect(await audit(page)).toEqual([]);
  });
}
