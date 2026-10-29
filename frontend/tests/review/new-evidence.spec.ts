/**
 * QUEUE F2 (prepared, runs once B3 clips exist): the real §19.3 "new evidence added" flow on the no-key stack.
 * Investigate with the cameras already imported, import one more camera clip in Operator, re-run, show the diff.
 *
 *   SPOOR_NEW_CLIP=<path to CAM_XX.mp4> SPOOR_NEW_CLIP_CAMERA=cam_CAM_11 SPOOR_NEW_CLIP_START=2026-10-28T14:32:07.000 \
 *     npx playwright test --config playwright.review.config.ts --project new-evidence
 */
import { expect, test, type Page } from "@playwright/test";

const CLIP = process.env.SPOOR_NEW_CLIP;
const CAMERA = process.env.SPOOR_NEW_CLIP_CAMERA;
const START = process.env.SPOOR_NEW_CLIP_START ?? "2026-10-28T14:32:07.000";

async function role(page: Page, r: string) {
  await page.request.post("/api/session", { data: { role: r } });
}

async function caption(page: Page, text: string) {
  await page.evaluate((t) => {
    let c = document.getElementById("rec-caption");
    if (!c) {
      c = document.createElement("div");
      c.id = "rec-caption";
      c.setAttribute("style", "position:fixed;z-index:9998;left:50%;bottom:14px;transform:translateX(-50%);background:rgba(14,16,18,.92);color:#f3f5f7;border:1px solid rgba(226,232,238,.25);padding:7px 14px;border-radius:10px;font:600 14px system-ui");
      document.body.appendChild(c);
    }
    c.textContent = t;
  }, text);
}

test("new evidence added: import another camera and re-run", async ({ page }) => {
  test.skip(!CLIP || !CAMERA, "set SPOOR_NEW_CLIP and SPOOR_NEW_CLIP_CAMERA once B3 clips exist");
  await role(page, "investigator");
  const cases = await (await page.request.get("/api/spoor/v1/cases")).json();
  const id = cases[0].case.case_id as string;

  await page.goto(`/cases/${id}`);
  await page.getByRole("tab", { name: "Agent" }).click();
  await caption(page, "Investigation with the footage imported so far");
  await page.getByTestId("run-investigation").click();
  await expect(page.locator(".sp-answer").first()).toBeVisible({ timeout: 60_000 });
  await page.waitForTimeout(2500);

  await role(page, "site_admin");
  await page.goto("/operator");
  await caption(page, `Operator imports ${CAMERA!.replace("cam_", "")}: the camera the case asked for`);
  const form = page.locator("section[aria-labelledby=clip-h]");
  await form.getByLabel("Camera").selectOption(CAMERA!);
  await form.getByLabel("Clip (MP4)").setInputFiles(CLIP!);
  await form.getByLabel("Recording start, camera clock").fill(START);
  await form.getByRole("checkbox").check();
  await form.getByRole("button", { name: "Import the clip" }).click();
  await expect(form.getByText(/Imported media_/)).toBeVisible({ timeout: 120_000 });
  await page.waitForTimeout(1500);

  await role(page, "investigator");
  await page.goto(`/cases/${id}`);
  await page.getByRole("tab", { name: "Agent" }).click();
  await page.getByTestId("run-investigation").click();
  await expect(page.locator(".sp-answer").first()).toBeVisible({ timeout: 60_000 });
  await caption(page, "New evidence added: the revision diff says what changed");
  await expect(page.getByLabel("What changed")).toBeVisible();
  await page.waitForTimeout(4000);
});
