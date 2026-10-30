/**
 * TEST FIXTURE for the trace renderer (C4). Used ONLY by Playwright through route interception, never by the app
 * runtime: the no-key backend has no observations, so this payload exercises green / amber / grey drawing.
 * Every screenshot that uses it carries an injected "TEST FIXTURE" banner.
 */
import type { Replay } from "../../src/lib/types";

export function traceFixture(caseId: string, objectId: string, label: string): Replay {
  const t = (s: number) => new Date(Date.UTC(2026, 9, 28, 6, 32, 10) + s * 1000).toISOString();
  const pt = (s: number, id: string, x: number, y: number) => ({
    t: t(s), observation_id: id, spatial_mode: "floor_xy", floor_xy_m: [x, y] as [number, number], zone_id: "zone_Z05",
    uncertainty_radius_m: 0.4, renderer_xyz_y_up: [x, 0, -y] as [number, number, number],
  });
  return {
    case_id: caseId,
    contract: "TEST FIXTURE",
    objects: [{
      object_instance_id: objectId,
      label,
      segments: [
        { kind: "observed", style: "solid", camera_id: "cam_CAM_07", track_id: "trk_fixture_a", start: t(0), end: t(4),
          points: [pt(0, "obs_fixture_1", 30.5, 11), pt(1, "obs_fixture_2", 33, 11), pt(2, "obs_fixture_3", 35.5, 11),
            pt(4, "obs_fixture_4", 40, 11)] },
        { kind: "observed", style: "solid", camera_id: "cam_CAM_10", track_id: "trk_fixture_b", start: t(12), end: t(14),
          points: [pt(12, "obs_fixture_5", 47.1, 19.8), pt(13, "obs_fixture_6", 47.1, 20.4), pt(14, "obs_fixture_7", 47.1, 20.9)] },
      ],
      links: [{ kind: "hypothesized", style: "dashed", from: "obs_fixture_4", to: "obs_fixture_5", start: t(4), end: t(12) }],
      gaps: [{ kind: "unknown", style: "grey", start: t(4), end: t(12), reason: "TEST FIXTURE: not visible on any camera",
        covering_camera_ids: [] }],
    }],
  };
}

export const FIXTURE_BANNER = "TEST FIXTURE: route-mocked trace to show the renderer. Not case evidence.";

/** The same fixture as a backend /journey payload (H2 renders the backend-typed journey in the 2D view). */
export function journeyFixture(caseId: string, objectId: string, label: string) {
  const r = traceFixture(caseId, objectId, label).objects[0];
  const observed = r.segments.map((s) => ({
    kind: "observed" as const, start: s.start, end: s.end, camera_id: s.camera_id, track_id: s.track_id,
    evidence_ids: s.points.map((p) => p.observation_id),
    points: s.points.map((p) => ({ t: p.t, observation_id: p.observation_id, xy: p.floor_xy_m })),
  }));
  const g = r.gaps[0];
  return {
    case_id: caseId, plan_id: "plan_fixture", contract: "TEST FIXTURE", needs: [],
    objects: [{
      object_instance_id: objectId, label, identity_keys: [], scans: [], observed_segments: observed.length,
      segments: [observed[0], { kind: "gap", start: g.start, end: g.end, reason: "unobserved", note: g.reason,
        covering_camera_ids: [], after: "obs_fixture_4", before: "obs_fixture_5", evidence_ids: [] }, observed[1]],
      last_confirmed: { kind: "observation", evidence_id: "obs_fixture_7", t: observed[1].end, xy: [47.1, 20.9],
        camera_id: "cam_CAM_10", on_conveyor: null, station_id: null, event_kind: null },
    }],
  };
}
