// Unit tests for frame-accurate context playback and the camera wall (review 007 #1). Run: npm run test:unit
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  frameAtMediaTime,
  frameUtcMs,
  nearestFrame,
  prerollStart,
  seekTimeFor,
  wallColumns,
  wallLocalTime,
} from "../../src/lib/playback.ts";
import { parseManifest, tileState } from "../../src/lib/scenarios.ts";

const pts10 = Array.from({ length: 300 }, (_, i) => i * 100); // 10 fps, 30 s

test("nearest frame maps media time back to the original's frame index", () => {
  assert.equal(nearestFrame(pts10, 0), 0);
  assert.equal(nearestFrame(pts10, 149), 1);
  assert.equal(nearestFrame(pts10, 151), 2);
  assert.equal(nearestFrame(pts10, 99_999), 299);
  assert.equal(nearestFrame(pts10, -50), 0);
  assert.equal(nearestFrame([], 10), 0);
  // a seek to frame i always reads back as frame i (frame-accurate pause)
  for (const i of [0, 1, 57, 298, 299]) assert.equal(frameAtMediaTime(pts10, seekTimeFor(pts10, i)), i);
});

test("pts with a non-zero first frame are measured from the first frame", () => {
  const pts = [40, 140, 240, 340];
  assert.equal(seekTimeFor(pts, 2), 0.201);
  assert.equal(frameAtMediaTime(pts, 0.2), 2);
});

test("pre-roll starts up to N seconds before the selected frame, never before frame 0", () => {
  assert.equal(prerollStart(pts10, 100, 3), 70);
  assert.equal(prerollStart(pts10, 10, 3), 0);
});

test("frame time on the case timeline = recorded start + pts", () => {
  const t = frameUtcMs({ pts_ms: pts10, start_utc: "2026-10-28T06:32:07.000Z" }, 25);
  assert.equal(new Date(t!).toISOString(), "2026-10-28T06:32:09.500Z");
  assert.equal(frameUtcMs({ pts_ms: pts10, start_utc: null }, 3), null);
});

test("wall sync: clips outside their own span show no footage, grid is 1, 2x2 or 3x3", () => {
  assert.equal(wallLocalTime(5, 2, 30), 3);
  assert.equal(wallLocalTime(1, 2, 30), null);
  assert.equal(wallLocalTime(40, 2, 30), null);
  assert.deepEqual([1, 2, 4, 5, 9].map(wallColumns), [1, 2, 2, 3, 3]);
});

test("manifest parsing keeps inputs only and refuses unsafe ids", () => {
  const items = parseManifest([
    { scenario: "S2", title: "Removal into the blind spot", parcel: "CTX1", subject_kind: "parcel",
      clips: "../../../assets/hub/build/renders/S2", scans: "x.jsonl", clip_start: "2026-10-28T14:32:07+08:00" },
    { scenario: "../S9", title: "bad", clips: "x" },
    { scenario: "S4", title: "Mis-load", parcel: "RC-1", subject_kind: "container", clips: "r/S4" },
  ]);
  assert.deepEqual(items.map((i) => i.scenario), ["S2", "S4"]);
  assert.equal(items[1].subject_kind, "container");
  assert.ok(!("expected_answer" in items[0]));
});

test("tile state: missing render, rendered but not imported, ready; never a stand-in", () => {
  assert.equal(tileState({ exists: false, sha256: null }, undefined), "not_rendered");
  assert.equal(tileState({ exists: true, sha256: "abc" }, undefined), "not_imported");
  assert.equal(tileState({ exists: true, sha256: "abc" }, "media_abc"), "ready");
});
