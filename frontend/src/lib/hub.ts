/**
 * The hub site plan (from assets/hub/hub_spec.json via scripts/gen-hub-data.mjs) and ID mapping to the backend.
 * Backend IDs carry type prefixes: hub "CAM_07" = backend "cam_CAM_07"; hub zone "Z06" = backend "zone_Z06".
 */
import raw from "@/data/hub.generated.json";
import type { MountedCamera } from "./frames";

export interface HubCamera extends MountedCamera {
  id: string;
  zone: string;
  osd_label: string;
  question: string;
  resolution: [number, number];
  fps: number;
  clock_domain: string;
  mount: string;
}

export interface HubZone {
  id: string;
  name: string;
  kind: string;
  polygons: [number, number][][];
}

export interface HubScanPoint {
  id: string;
  device_kind: string;
  zone: string;
  position_m: [number, number, number];
  clock_domain: string;
  events: string;
  visible_by: string[];
}

export interface HubData {
  name: string;
  frame: string;
  footage_label: string;
  building: {
    footprint_m: [number, number];
    eaves_m: number;
    columns: [number, number][];
    doors: { id: string; kind: string; wall: string; centre: [number, number]; width: number; board?: string }[];
  };
  zones: HubZone[];
  blind_corner: { id: string; zone: string; polygon: [number, number][]; why: string };
  machines: {
    loop: { south_y: number; north_y: number; radius: number; west_cx: number; east_cx: number; cy: number;
      deck_height: number };
    conveyors: { id: string; kind: string; path: [number, number][]; height: number; heights?: number[] }[];
    chutes: { id: string; x: number; mouth_y: number; end_y: number; width: number; lip_z?: number }[];
    scan_tunnel: { zone: string; box_m: [number, number, number]; exit_read_point_m: [number, number] };
  };
  fixtures: {
    benches: { name: string; rect_m: [number, number, number, number]; height_m: number }[];
    cage_bays: { id: string; sw_corner_m: [number, number]; size_m: number }[];
    racks: { rect_m: [number, number, number, number]; height_m: number }[];
  };
  walkways: { id: string; rect_m: [number, number, number, number] }[];
  circulation: {
    forklift_lane: { centreline_m: [number, number][]; width_m: number };
    zebra_crossings: { id: string; rect_m: [number, number, number, number] }[];
    crossovers: { id: string; x: number; width: number; south_stair_y: [number, number]; north_stair_y: [number, number] }[];
  };
  scan_points: HubScanPoint[];
  cameras: HubCamera[];
}

export const HUB = raw as unknown as HubData;

export const camId = {
  toBackend: (hubId: string) => `cam_${hubId}`,
  toHub: (backendId: string | null | undefined) => (backendId ?? "").replace(/^cam_/, ""),
};
export const zoneId = {
  toBackend: (hubId: string) => `zone_${hubId}`,
  toHub: (backendId: string | null | undefined) => (backendId ?? "").replace(/^zone_/, "").replace(/_.*$/, ""),
};

export const hubCamera = (backendOrHubId: string) => HUB.cameras.find((c) => c.id === camId.toHub(backendOrHubId));
export const hubZone = (backendOrHubId: string | null | undefined) =>
  HUB.zones.find((z) => z.id === zoneId.toHub(backendOrHubId));
export const scanPoint = (deviceOrStation: string | null | undefined) =>
  HUB.scan_points.find((s) => s.id === deviceOrStation);

/** Polygon centroid (area-weighted) for labels and zone_only markers. */
export function centroid(poly: [number, number][]): [number, number] {
  let a = 0;
  let cx = 0;
  let cy = 0;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const f = poly[j][0] * poly[i][1] - poly[i][0] * poly[j][1];
    a += f;
    cx += (poly[j][0] + poly[i][0]) * f;
    cy += (poly[j][1] + poly[i][1]) * f;
  }
  return a === 0 ? poly[0] : [cx / (3 * a), cy / (3 * a)];
}

/** Hub site extent incl. the yards, for framing views. */
export const HUB_EXTENT = { minX: -18, minY: 0, maxX: 60, maxY: 58 };
