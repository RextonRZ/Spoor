/**
 * J4 voice notes: the browser converts any recording to the WAV Muse Voice Transcribe accepts (16 kHz, mono, 16-bit
 * PCM) before upload, and without the key the control says so and uploads nothing. The voice routes are mocked only
 * to capture what the browser sends; no transcript is shown or stored.
 */
import { expect, test } from "@playwright/test";

function wav(seconds: number, rate: number, channels: number): Buffer {
  const n = Math.round(seconds * rate);
  const data = Buffer.alloc(n * channels * 2);
  for (let i = 0; i < n; i++) for (let c = 0; c < channels; c++) data.writeInt16LE(Math.round(8000 * Math.sin((2 * Math.PI * 440 * i) / rate)), (i * channels + c) * 2);
  const h = Buffer.alloc(44);
  h.write("RIFF", 0); h.writeUInt32LE(36 + data.length, 4); h.write("WAVE", 8); h.write("fmt ", 12);
  h.writeUInt32LE(16, 16); h.writeUInt16LE(1, 20); h.writeUInt16LE(channels, 22); h.writeUInt32LE(rate, 24);
  h.writeUInt32LE(rate * channels * 2, 28); h.writeUInt16LE(channels * 2, 32); h.writeUInt16LE(16, 34);
  h.write("data", 36); h.writeUInt32LE(data.length, 40);
  return Buffer.concat([h, data]);
}

test.beforeEach(async ({ page }) => { await page.request.post("/api/session", { data: { role: "investigator" } }); });

async function caseId(page: import("@playwright/test").Page) {
  const cases = await (await page.request.get("/api/spoor/v1/cases")).json();
  return cases[0].case.case_id as string;
}

test("voice: a 44.1 kHz stereo file is uploaded as 16 kHz mono 16-bit WAV", async ({ page }) => {
  const id = await caseId(page);
  let body: Buffer | null = null;
  await page.route(`**/api/spoor/v1/cases/${id}/voice`, async (r) => {
    if (r.request().method() === "POST") { body = r.request().postDataBuffer(); return r.fulfill({ status: 201, json: {} }); }
    return r.fulfill({ json: { items: [], available: true, estimate: { usd_per_minute: 0.003 } } });
  });
  await page.goto(`/cases/${id}/summary`);
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Pick a recording" }).click();
  await (await chooser).setFiles({ name: "call.wav", mimeType: "audio/wav", buffer: wav(1.5, 44100, 2) });
  await expect.poll(() => body !== null, { timeout: 20_000 }).toBe(true);
  const buf = body as unknown as Buffer;
  const at = buf.indexOf("RIFF");
  expect(at).toBeGreaterThan(0);
  expect(buf.toString("latin1", at + 8, at + 12)).toBe("WAVE");
  expect([buf.readUInt16LE(at + 22), buf.readUInt32LE(at + 24), buf.readUInt16LE(at + 34)]).toEqual([1, 16000, 16]);
  expect(Math.abs(buf.readUInt32LE(at + 40) / 2 - 1.5 * 16000)).toBeLessThan(400);
  expect(buf.toString("latin1")).toContain('name="kind"');
});

test("voice: without the key the recorder says so and uploads nothing", async ({ page }) => {
  const id = await caseId(page);
  let posted = false;
  page.on("request", (r) => { if (r.method() === "POST" && r.url().endsWith(`/cases/${id}/voice`)) posted = true; });
  await page.goto(`/cases/${id}/summary`);
  await expect(page.getByText("Voice notes need the Model API key")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("button", { name: "Record the complaint call" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Pick a recording" })).toBeDisabled();
  expect(posted).toBe(false);
});
