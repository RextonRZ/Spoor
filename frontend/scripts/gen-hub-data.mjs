// Slims assets/hub/hub_spec.json into src/data/hub.generated.json for the 3D scene and the 2D floor plan.
// Only site-plan facts a real site would hand over (walls, doors, zones, machines, scan points, camera mounting plan).
// Never reads evaluator-only files (render_truth.*, flow_truth.json, build/truth/*).
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const specPath = join(root, "..", "assets", "hub", "hub_spec.json");
if (/render_truth|flow_truth|[\/]truth[\/]/.test(specPath)) throw new Error("evaluator-only file");
const fixText = (s) => s.replace(/â€”/g, "—").replace(/â€“/g, "–").replace(/â€™/g, "’").replace(/â€œ|â€\u009d/g, '"')
  .replace(/Ã—/g, "×").replace(/â†’/g, "→");
const clean = (v) => typeof v === "string" ? fixText(v) : Array.isArray(v) ? v.map(clean)
  : v && typeof v === "object" ? Object.fromEntries(Object.entries(v).map(([k, x]) => [k, clean(x)])) : v;
const spec = clean(JSON.parse(readFileSync(specPath, "utf8")));
const pick = (o, keys) => Object.fromEntries(keys.filter((k) => k in o).map((k) => [k, o[k]]));

const hub = {
  source: "assets/hub/hub_spec.json",
  frame: spec.meta.frame,
  name: "CONTOH Express Klang Valley hub (fictional)",
  footage_label: spec.meta.footage_label,
  building: pick(spec.building, ["footprint_m", "eaves_m", "columns", "doors"]),
  zones: spec.zones.map((z) => ({
    id: z.id, name: z.name, kind: z.kind,
    polygons: Array.isArray(z.polygon_m) ? [z.polygon_m] : Object.values(z.polygon_m),
  })),
  blind_corner: pick(spec.blind_corner, ["id", "zone", "polygon", "why"]),
  machines: {
    loop: spec.machines.loop,
    conveyors: spec.machines.conveyors,
    chutes: spec.machines.chutes,
    scan_tunnel: pick(spec.machines.scan_tunnel, ["zone", "box_m", "exit_read_point_m"]),
  },
  fixtures: pick(spec.fixtures, ["benches", "cage_bays", "racks"]),
  walkways: spec.circulation.walkways.map((w) => pick(w, ["id", "rect_m"])),
  // floor-plan language (floorplan_design_0300): forklift lane, zebra crossings and belt crossovers are drawn too
  circulation: {
    forklift_lane: pick(spec.circulation.forklift_lane, ["centreline_m", "width_m"]),
    zebra_crossings: (spec.circulation.zebra_crossings ?? []).map((z) => pick(z, ["id", "rect_m"])),
    crossovers: (spec.circulation.crossovers ?? []).map((x) => pick(x, ["id", "x", "width", "south_stair_y", "north_stair_y"])),
  },
  scan_points: spec.scan_points.map((s) => ({
    ...pick(s, ["id", "device_kind", "zone", "position_m", "clock_domain", "events"]),
    visible_by: (s.visible_by ?? []).map((v) => v.camera),
  })),
  cameras: spec.cameras.map((c) => pick(c, ["id", "zone", "osd_label", "question", "position_m", "height_m",
    "heading_deg", "tilt_down_deg", "hfov_deg", "vfov_deg", "resolution", "fps", "clock_domain", "mount"])),
};
mkdirSync(join(root, "src", "data"), { recursive: true });
writeFileSync(join(root, "src", "data", "hub.generated.json"), JSON.stringify(hub));
console.log(`hub data: ${hub.zones.length} zones, ${hub.cameras.length} cameras, ${hub.scan_points.length} scan points`);
