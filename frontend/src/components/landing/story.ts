/**
 * The landing hero's story, from three sources and nothing typed by hand:
 * - the seeded case (the same API the app reads): the parcel ID, the cage ID, the scan record wording and the
 *   "records vs cameras" sentence;
 * - /landing/landing.json (assets/hub/landing_truth.py + landing_assets.py on the S2 render): which cameras saw the
 *   parcel, when, its box in their frame, the push-in steps and their clips. Blender ground truth, not tracking;
 * - the hub plan (src/data/hub.generated.json, from assets/hub/hub_spec.json): zone names, cameras, the floor plan.
 * Times are the footage's own clock, formatted the way the app formats them (lib/words hms).
 */
import { api } from "@/lib/api";
import { hms, lastScanSentence } from "@/lib/words";
import hub from "@/data/hub.generated.json";
import { ZONE_NAMES } from "@/lib/zones";
import { caseAnswer, type Answer } from "@/lib/answer";
import { buildCheckpoints, type CaseRecord, type Checkpoint } from "@/lib/checkpoints";
import type { JourneyScan } from "@/lib/journey";

export type Box = [number, number, number, number];

export interface LandingStep {
  camera: string;
  seen_f: [number, number];
  clip_f: [number, number];
  event: "picked" | "carried" | "into_blind" | "out_empty";
  video: string;
  poster: string;
  inset?: { video: string; crop: [number, number, number, number] };
}

export interface LandingData {
  story_parcel: string;
  fps: number;
  frames: [number, number];
  t0: string;
  scenario: { picked_t_s: number | null; enters_blind_t_s: number | null; exits_empty_t_s: number | null };
  cameras: { id: string; name: string; seen_frames: number }[];
  camera_xy: Record<string, [number, number]>;
  path: [number, number, number][];
  sightings: { camera: string; t0_s: number; t1_s: number; boxes: Record<string, Box> }[];
  steps: LandingStep[];
  /** the case's moments for the showreel: the steps + coming out of the store without it */
  moments?: LandingStep[];
  /** the S2 look-alike carton where a camera sees it best (ground truth) */
  lookalike?: { object: string; camera: string; frame: number; box: Box; poster: string; t_s: number } | null;
  poster_frame: number;
}

export interface StoryStep extends LandingStep {
  caption: string;
  /** frame -> box, inside this step's clip */
  boxes: Record<number, Box>;
}

export interface Story {
  data: LandingData;
  parcel: string;
  opener: string;
  redLine: string;
  steps: StoryStep[];
  moments: StoryStep[];
  /** cameras with any sighting at all (the search lights these) */
  seen: Set<string>;
  /** case found for this footage (false: the seeded case is from another run, so no case words are shown) */
  matched: boolean;
  /** the case's last scan (where the lead starts) */
  lastScan: { xy: [number, number] | null; words: string } | null;
  /** cameras the case expects could see it next (the missing-moment endpoint) */
  nextCams: string[];
  /** the look-alike the verifier rejects: where it is, and where the real one was at that moment (ground truth) */
  lookalike: { camera: string; clock: string; poster: string; box: Box; realWas: string } | null;
  /** the board's verdict, in the Answer screen's shape. "agent": the case's own answer (lib/answer, the same function
   *  the Answer screen uses), once the agent has a sighting or a find; "footage": until then, what the footage shows
   *  (ground truth of the render + the case's records), never presented as the agent's output */
  verdict: (Answer & { source: "agent" | "footage" }) | null;
  /** the six scan checkpoints (lib/checkpoints) from the case's scan log; the truck step is red when the records put
   *  the parcel on a truck and the footage never shows it at the dock (ground truth of the render) */
  checkpoints: Checkpoint[] | null;
}

type Scan = Record<string, unknown> & { t: string; event_kind: string; station_id?: string | null };
interface JourneyObj { label: string; identity_keys: string[]; scans: Scan[] }
interface Journey { objects: JourneyObj[] }
interface Conflicts { objects: { conflicts: { kind: string; statement: string }[]; records?: CaseRecord[] }[] }
interface Missing { objects: { expected_next: { camera_id: string; predicted_t: string; result?: string | null }[] }[] }
interface Possible { objects: { places: { area_id: string; name: string; zone_id: string | null; possible_share: number }[] }[] }
interface SearchView { found: { name: string; by: string; at: string } | null }

const ZONES = (hub as unknown as { zones: { id: string; name: string; polygons: [number, number][][] }[] }).zones;

function inPoly(x: number, y: number, poly: [number, number][]) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i];
    const [xj, yj] = poly[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

/** the zone at a floor position, in the app's own short name ("exception store", "cage staging") */
export function zoneAt(x: number, y: number): string | null {
  const z = ZONES.find((zz) => zz.polygons.some((p) => inPoly(x, y, p)));
  if (!z) return null;
  const n = ZONE_NAMES[z.id] ?? z.name.replace(/\s*\(.*\)\s*$/, "").trim();
  return n.charAt(0).toLowerCase() + n.slice(1);
}

export function clockAt(d: LandingData, frame: number): string {
  const ms = Date.parse(d.t0) + ((frame - d.frames[0]) / d.fps) * 1000;
  return hms(new Date(ms).toISOString());
}

function pathAt(d: LandingData, t: number): [number, number] | null {
  let best: [number, number, number] | null = null;
  for (const p of d.path) if (!best || Math.abs(p[0] - t) < Math.abs(best[0] - t)) best = p;
  return best ? [best[1], best[2]] : null;
}

function cageOf(scans: Scan[]): string | null {
  for (const s of [...scans].reverse()) {
    const m = JSON.stringify(s).match(/\bRC-\d{3,}\b/);
    if (m) return m[0];
  }
  return null;
}

export async function loadStory(): Promise<Story> {
  const data = (await fetch("/landing/landing.json").then((r) => r.json())) as LandingData;
  const parcel = data.story_parcel;
  let obj: JourneyObj | null = null;
  let caseId: string | null = null;
  // the case's read models: live from the API when it holds this parcel's case, else the snapshot of the same
  // responses saved by scripts/landing-case-snapshot.mjs (so the public page never goes blank on another store)
  let read: (<T>(view: string) => Promise<T>) | null = null;
  try {
    const rows = await api<{ case: { case_id: string } }[]>("/v1/cases");
    for (const r of rows) {
      const j = await api<Journey>(`/v1/cases/${r.case.case_id}/journey`);
      const o = j.objects.find((x) => x.identity_keys.some((k) => k.endsWith(`:${parcel}`)));
      if (o) {
        obj = o;
        caseId = r.case.case_id;
        const id = caseId;
        read = <T,>(view: string) => api<T>(`/v1/cases/${id}/${view}`);
        break;
      }
    }
  } catch {
    obj = null;
  }
  if (!obj) {
    const snap = await fetch("/landing/case.json").then((r) => (r.ok ? r.json() : null)).catch(() => null) as
      { parcel: string; case_id: string; views: Record<string, unknown> } | null;
    const o = snap?.parcel === parcel ? (snap.views.journey as Journey | undefined)?.objects
      .find((x) => x.identity_keys.some((k) => k.endsWith(`:${parcel}`))) : undefined;
    if (snap && o) {
      obj = o;
      caseId = snap.case_id;
      read = async <T,>(view: string) => {
        if (!(view in snap.views)) throw new Error(`no ${view} in the snapshot`);
        return snap.views[view] as T;
      };
    }
  }
  const scans = obj ? [...obj.scans].sort((a, b) => a.t.localeCompare(b.t)) : [];
  let nextCams: string[] = [];
  let agent: Answer | null = null;
  if (read) {
    try {
      const [m, pl, cf, sr] = await Promise.all([
        read<Missing>("missing-moment"),
        read<Possible>("possible-locations"),
        read<{ objects: { conflicts: { statement: string }[] }[] }>("conflicts"),
        read<SearchView>("search-tasks").catch(() => ({ found: null })),
      ]);
      const next = m.objects[0]?.expected_next ?? [];
      nextCams = [...new Set(next.map((e) => e.camera_id.replace(/^cam_/, "")))];
      const lastScan = scans[scans.length - 1];
      agent = caseAnswer({
        ready: true,
        last: lastScan ? { event_kind: lastScan.event_kind, station_id: lastScan.station_id, t: lastScan.t } : undefined,
        next,
        places: (pl.objects[0]?.places ?? []).filter((x) => x.possible_share > 0),
        conflicts: cf.objects[0]?.conflicts ?? [],
        found: sr.found,
        zoneNames: ZONE_NAMES,
      });
    } catch {
      nextCams = [];
    }
  }
  const last = scans[scans.length - 1];
  const cage = cageOf(scans);
  let statement: string | null = null;
  let records: CaseRecord[] = [];
  if (read) {
    try {
      const c = await read<Conflicts>("conflicts");
      statement = c.objects.flatMap((o) => o.conflicts).find((k) => /video|camera/i.test(k.kind))?.statement ?? null;
      records = c.objects[0]?.records ?? [];
    } catch {
      statement = null;
    }
  }
  // did any camera ever see the parcel while it was at the outbound dock? (where the render put it, frame by frame)
  const dock = ZONES.find((z) => z.id === "Z12");
  const seenAtDock = !!dock && data.sightings.some((sg) => Object.keys(sg.boxes).some((f) => {
    const xy = pathAt(data, (Number(f) - data.frames[0]) / data.fps);
    return !!xy && dock.polygons.some((poly) => inPoly(xy[0], xy[1], poly));
  }));
  // when the footage shows it carried into the exception store (the render's own timeline, the same as the moments)
  const into = data.scenario.enters_blind_t_s;
  const storeSeenAt = into != null ? new Date(Date.parse(data.t0) + into * 1000).toISOString() : null;
  const checkpoints = obj
    ? buildCheckpoints({ scans: scans as unknown as JourneyScan[], records, barcode: parcel, truckSeen: seenAtDock, storeSeenAt })
    : null;
  const opener = !last ? "" : cage ? `Scan records: in cage ${cage}.` : `Scan records: ${lastScanSentence(last.event_kind, last.station_id, last.t).replace(/^./, (c) => c.toLowerCase())}`;
  const redLine = statement ?? (cage ? `Records say cage ${cage}. Cameras disagree.` : "Records and cameras disagree.");
  const t = (f: number) => (f - data.frames[0]) / data.fps;
  const storeAt = (() => {
    const b = data.steps.find((x) => x.event === "into_blind");
    const sc0 = data.scenario;
    return b && sc0.enters_blind_t_s != null ? pathAt(data, sc0.enters_blind_t_s) : null;
  })();
  const storeZone = storeAt ? zoneAt(storeAt[0], storeAt[1]) : null;
  const view = (s: LandingStep): StoryStep => {
    const sc = data.scenario;
    const keyF =
      s.event === "picked" && sc.picked_t_s != null ? data.frames[0] + Math.round(sc.picked_t_s * data.fps)
      : s.event === "into_blind" && sc.enters_blind_t_s != null ? data.frames[0] + Math.round(sc.enters_blind_t_s * data.fps)
      : s.event === "out_empty" && sc.exits_empty_t_s != null ? data.frames[0] + Math.round(sc.exits_empty_t_s * data.fps)
      : Math.round((s.clip_f[0] + s.clip_f[1]) / 2);
    const xy = pathAt(data, t(keyF));
    const zone = xy ? zoneAt(xy[0], xy[1]) : null;
    const words =
      s.event === "picked" ? (cage ? `taken out of cage ${cage}` : "taken out of its cage")
      : s.event === "into_blind" ? `into the ${zone ?? "store"}`
      : s.event === "out_empty" ? "comes back out without it"
      // (the zone round the store reaches into the aisle in front of it: before the doorway it is "toward" the store)
      : zone && zone === storeZone ? `carried toward the ${zone}` : `carried through ${zone ?? "the hall"}`;
    const boxes: Record<number, Box> = {};
    for (const sg of data.sightings) {
      if (sg.camera !== s.camera) continue;
      for (const [f, b] of Object.entries(sg.boxes)) {
        const n = Number(f);
        if (n >= s.clip_f[0] && n <= s.clip_f[1]) boxes[n] = b;
      }
    }
    return { ...s, caption: `${clockAt(data, keyF)} · ${words}`, boxes };
  };
  const steps = data.steps.map(view);
  const moments = (data.moments ?? data.steps).map(view);
  const timeOnly = (x: StoryStep) => ({ ...x, caption: x.caption.split(" · ")[0] });
  const look = data.lookalike ?? null;
  let lookalike: Story["lookalike"] = null;
  if (look) {
    const sc = data.scenario;
    const realWas =
      sc.picked_t_s != null && look.t_s < sc.picked_t_s ? "still in its cage"
      : sc.enters_blind_t_s != null && look.t_s < sc.enters_blind_t_s ? "in a person's hands"
      : "out of sight in the store";
    lookalike = { camera: look.camera, clock: clockAt(data, look.frame), poster: look.poster, box: look.box, realWas };
  }
  const lastXY = last && Array.isArray(last.xy) ? (last.xy as [number, number]) : null;
  // the verdict: the agent's own answer once it has seen or found the parcel; until then what the footage shows
  let verdict: Story["verdict"] = null;
  const blindStep = steps.find((x) => x.event === "into_blind");
  const outStep = (data.moments ?? []).find((x) => x.event === "out_empty");
  if (obj && agent && agent.level !== "low") verdict = { ...agent, source: "agent" };
  else if (obj && blindStep) {
    const [time, words] = blindStep.caption.split(" · ");
    const saw = [...new Set(steps.map((x) => x.camera.replace("_", " ")))];
    verdict = {
      source: "footage",
      pill: ["What the footage shows", "ok"],
      head: `${words.charAt(0).toUpperCase()}${words.slice(1)} at ${time}.`,
      why: "",
      level: "medium",
      reasons: [
        ...(last ? [{ text: `Last scan: ${lastScanSentence(last.event_kind, last.station_id, last.t).replace(/^./, (c) => c.toLowerCase())}`, tone: "ok" as const }] : []),
        { text: `Seen on ${saw.join(", ")}.`, tone: "plain" as const },
        ...(outStep ? [{ text: `Back out without it at ${clockAt(data, data.frames[0] + Math.round((data.scenario.exits_empty_t_s ?? 0) * data.fps))}.`, tone: "plain" as const }] : []),
        { text: redLine, tone: "bad" as const },
      ],
    };
  }
  return {
    data,
    lastScan: last ? { xy: lastXY, words: lastScanSentence(last.event_kind, last.station_id, last.t) } : null,
    nextCams,
    lookalike,
    verdict,
    checkpoints,
    parcel: obj ? obj.label.replace(/^parcel\s+/, "") : parcel,
    opener: obj ? opener : "",
    redLine: obj ? redLine : "",
    steps: obj ? steps : steps.map(timeOnly),
    moments: obj ? moments : moments.map(timeOnly),
    seen: new Set(data.sightings.map((s) => s.camera)),
    matched: Boolean(obj),
  };
}

export const HUB = hub as unknown as {
  building: { footprint_m: [number, number] };
  zones: { id: string; name: string; polygons: [number, number][][] }[];
  cameras: { id: string; osd_label?: string; position_m: [number, number] }[];
};
