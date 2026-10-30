/**
 * ≤ 30 s screen recording of the journey (block H proof) on the REAL no-key default case: open the case, replay the
 * journey at 4× (scans, amber belt inferences, trail end, "unknown since"), open the missing moment, then the case
 * summary. No fixture. Convert with: node scripts/make-recording.mjs journey-recording review_pack/journey_replay.mp4
 */
import { writeFileSync } from "node:fs";
import { expect, test } from "@playwright/test";

test("journey replay recording (real no-key data)", async ({ page }) => {
  test.setTimeout(240_000);
  const began = Date.now();
  await page.request.post("/api/session", { data: { role: "investigator" } });
  const cases = await (await page.request.get("/api/spoor/v1/cases")).json();
  const id = cases[0].case.case_id as string;
  // warm the pages so the video has no loading dead air
  await page.goto(`/cases/${id}/summary?style=v2`);
  await expect(page.getByTestId("case-answer")).toBeVisible({ timeout: 90_000 });
  await page.goto(`/cases/${id}?style=v2`);
  await expect(page.locator(".hp-over")).toBeAttached({ timeout: 90_000 });
  await page.waitForFunction(() => [...document.images].every((i) => i.complete && i.naturalWidth > 0), undefined, { timeout: 45_000 }).catch(() => {});
  await page.waitForTimeout(1500);
  writeFileSync("test-results/journey-recording-start.txt", String((Date.now() - began) / 1000 - 1));
  await page.getByRole("button", { name: "4×" }).click();
  await page.getByTestId("replay-play").click();
  await expect(page.getByTestId("replay-status")).toContainText("Unknown since", { timeout: 30_000 });
  await page.waitForTimeout(1200);
  await page.getByTestId("tab-moment").click();
  await expect(page.locator(".mm-close img").first()).toBeVisible({ timeout: 30_000 });
  await page.waitForTimeout(2000);
  await page.locator("#source-panel .sp-panel-body").evaluate((el) => el.scrollTo({ top: 900, behavior: "smooth" }));
  await page.waitForTimeout(2000);
  await page.getByTestId("open-summary").click();
  await expect(page.getByTestId("case-answer")).toBeVisible({ timeout: 30_000 });
  await page.waitForTimeout(3000);
  await page.mouse.wheel(0, 600);
  await page.waitForTimeout(2000);
});
