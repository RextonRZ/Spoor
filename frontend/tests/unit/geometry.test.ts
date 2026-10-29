// Unit tests for the frame transform, camera geometry and the trace contract. Run: npm run test:unit
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  DEFAULT_SITE_TO_RENDERER,
  floorFootprint,
  rendererToSite,
  setSiteToRenderer,
  siteToRenderer,
  viewRay,
  pointInPolygon,
} from "../../src/lib/frames.ts";
import { buildTrace, solidNeverBridgesGaps } from "../../src/lib/trace.ts";
import type { ReplayObject, ReplayPoint } from "../../src/lib/types.ts";

test("default matrix equals the backend's SITE_TO_RENDERER (spoor/spatial/frames.py)", () => {
  const src = readFileSync(new URL("../../../backend/src/spoor/spatial/frames.py", import.meta.url), "utf8");
  const m = /SITE_TO_RENDERER = np\.array\((\[\[.*?\]\])\)/.exec(src);
  assert.ok(m, "matrix literal not found in backend source");
  assert.deepEqual(JSON.parse(m[1]), DEFAULT_SITE_TO_RENDERER);
});

test("site Z-up -> renderer Y-up keeps handedness and round-trips", () => {
  assert.deepEqual(siteToRenderer([1, 2, 3]), [1, 3, -2]);
  assert.deepEqual(siteToRenderer([0, 0, 5]), [0, 5, 0]); // up stays up
  const p: [number, number, number] = [12.5, -3, 0.75];
  const back = rendererToSite(siteToRenderer(p));
  back.forEach((v, i) => assert.ok(Math.abs(v - p[i]) < 1e-12));
});

test("setSiteToRenderer rejects reflections and malformed input", () => {
  assert.equal(setSiteToRenderer([[1, 0, 0], [0, 1, 0], [0, 0, -1]]), false);
  assert.equal(setSiteToRenderer([[1, 0], [0, 1]]), false);
  assert.equal(setSiteToRenderer(DEFAULT_SITE_TO_RENDERER), true);
});

const cam = { position_m: [10, 0] as [number, number], height_m: 5, heading_deg: 90, tilt_down_deg: 45,
  hfov_deg: 90, vfov_deg: 60 };

test("camera centre ray follows heading (CCW from east) and tilt", () => {
  const d = viewRay(cam, 0, 0);
  assert.ok(Math.abs(d[0]) < 1e-9);
  assert.ok(Math.abs(d[1] - Math.SQRT1_2) < 1e-9);
  assert.ok(Math.abs(d[2] + Math.SQRT1_2) < 1e-9);
});

test("floor footprint lies in front of the camera and contains the centre-ray hit", () => {
  const poly = floorFootprint(cam);
  assert.ok(poly.every(([, y]) => y > 0));
  assert.ok(pointInPolygon([10, 5], poly)); // centre ray hits the floor 5 m ahead at 45° from 5 m
});

const pt = (t: string, id: string, xy: [number, number] | null): ReplayPoint => ({
  t, observation_id: id, spatial_mode: xy ? "floor_xy" : "image_only", floor_xy_m: xy, zone_id: null,
  uncertainty_radius_m: xy ? 0.3 : null, renderer_xyz_y_up: null,
});

test("solid runs never bridge an unknown interval or an unplaced point", () => {
  const obj: ReplayObject = {
    object_instance_id: "objinst_x", label: "parcel",
    segments: [{
      kind: "observed", style: "solid", camera_id: "cam_a", track_id: "trk_1",
      start: "2026-10-28T06:32:00Z", end: "2026-10-28T06:32:09Z",
      points: [
        pt("2026-10-28T06:32:00Z", "obs_1", [1, 1]),
        pt("2026-10-28T06:32:01Z", "obs_2", [1.2, 1]),
        pt("2026-10-28T06:32:05Z", "obs_3", [3, 1]), // a gap sits between obs_2 and obs_3
        pt("2026-10-28T06:32:06Z", "obs_4", null), // unplaced
        pt("2026-10-28T06:32:07Z", "obs_5", [3.4, 1]),
        pt("2026-10-28T06:32:08Z", "obs_6", [3.6, 1]),
      ],
    }],
    links: [{ kind: "hypothesized", style: "dashed", from: "obs_2", to: "obs_5", start: "2026-10-28T06:32:01Z",
      end: "2026-10-28T06:32:07Z" }],
    gaps: [{ kind: "unknown", style: "grey", start: "2026-10-28T06:32:02Z", end: "2026-10-28T06:32:04Z",
      reason: "not visible", covering_camera_ids: [] }],
  };
  const t = buildTrace(obj);
  assert.deepEqual(t.solid.map((r) => r.points.map((p) => p.observation_id)), [["obs_1", "obs_2"], ["obs_5", "obs_6"]]);
  assert.deepEqual(t.singles.map((p) => p.observation_id), ["obs_3"]);
  assert.deepEqual(t.unplaced.map((p) => p.observation_id), ["obs_4"]);
  assert.equal(t.dashed.length, 1);
  assert.ok(solidNeverBridgesGaps(t));
});
