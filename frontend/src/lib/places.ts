/**
 * The hub's places (scanners): plain names, the step each is in a parcel's journey, and the pictures that show where
 * each one is (public/places, made by assets/hub/place_views.py + place_export.py from the hub model).
 *
 * Every scanner belongs to one of the six checkpoints the case shows (checkpoints.ts): 1 Unloaded, 2 Scan tunnel,
 * 3 Into chute, 4 Into bag or cage, 5 Exception store, 6 Loaded on truck. places.json gives, for the whole
 * hub from straight above and for each zone (tilted 3D map, from straight above, eye height), the pixel position of
 * every scanner and the zone outline in a 1600 x 900 picture.
 */
import { useEffect, useState } from "react";

/** A scanner's place in plain words, from its hub_spec id. */
export function placeName(id: string): string {
  const d = id.match(/D\d{2}$/)?.[0];
  const c = id.match(/C\d{2}$/)?.[0];
  if (id.startsWith("SP-DIV-REJECT")) return "Reject chute";
  if (id.startsWith("SP-DIV-") && c) return `Chute ${c}`;
  if (id.startsWith("SP-BAG-") && c) return `Bag scan, chute ${c}`;
  if (id.startsWith("SP-TUNNEL")) return `Scan tunnel, line ${id.endsWith("-B") ? "B" : "A"}`;
  if (id.startsWith("SP-INDUCT")) return `Sorter induct, line ${id.endsWith("-B") ? "B" : "A"}`;
  if (id.startsWith("SP-RFID-") && d) return `Dock ${d} gate`;
  if (id.startsWith("SP-LOAD-") && d) return `Dock ${d} loading`;
  const fixed: Record<string, string> = {
    "SP-IN-N": "Unloading, north door", "SP-IN-S": "Unloading, south door", "SP-CAGE-W": "Cage staging, west",
    "SP-CAGE-E": "Cage staging, east", "SP-STORE-IN": "Exception store door", "SP-BAGOPEN": "Bag opening",
    "SP-REWORK": "Exception bench", "SP-OVERSIZE": "Oversize area",
  };
  return fixed[id] ?? id;
}

export interface Stage { n: number; label: string; how: string; group: string }
/** The six scan checkpoints, numbered and worded exactly as the case shows them (lib/checkpoints.ts), so "checkpoint 3"
 *  means one thing on the map, in a case and on the landing page. Every scanner belongs to one of them. */
export const STAGES: Stage[] = [
  { n: 1, label: "Unloaded", how: "Handheld scan at the door, or as its bag is opened", group: "Unloading" },
  { n: 2, label: "Scan tunnel", how: "Photo, weight and size, then onto the sorter", group: "Tunnel" },
  { n: 3, label: "Into chute", how: "Sorter confirms the drop", group: "Chutes" },
  { n: 4, label: "Into bag or cage", how: "Handheld scan", group: "Bag scans" },
  { n: 5, label: "Exception store", how: "Scan-in at the store door, rework bench or oversize area", group: "Exceptions" },
  { n: 6, label: "Loaded on truck", how: "Cage tag read at the dock gate", group: "Dock scanners" },
];

/** The checkpoint (1..6) a scanner belongs to. */
export function stageOf(id: string): number {
  const by: [string, number][] = [["SP-IN-", 1], ["SP-BAGOPEN", 1], ["SP-INDUCT", 2], ["SP-TUNNEL", 2], ["SP-DIV-", 3],
    ["SP-BAG-", 4], ["SP-CAGE-", 4], ["SP-STORE-IN", 5], ["SP-REWORK", 5], ["SP-OVERSIZE", 5], ["SP-LOAD-", 6], ["SP-RFID-", 6]];
  return by.find(([p]) => id.startsWith(p))?.[1] ?? 5;
}

export const ZONE_LABEL: Record<string, string> = {
  Z01: "Inbound dock", Z02: "Bag opening", Z03: "Induction", Z04: "Scan tunnel", Z05: "Cross-belt sorter",
  Z06: "Chutes + bagging", Z07: "Reject", Z08: "Exception bench", Z09: "Oversize", Z10: "Cage staging",
  Z11: "Exception store", Z12: "Outbound dock", Z13: "Office", Z14: "Truck yard",
};

export interface Pin { x: number; y: number; zone: string; seen?: boolean }
/** where the 3D map picture was taken, in three.js axes (x, z, -y), as public/hub.glb */
export interface Camera3 { position: [number, number, number]; target: [number, number, number]; fov_deg: number }
export interface Picture { image: string; scan_points: Record<string, Pin>; zones: Record<string, number[][][]>; people?: string[]; camera3?: Camera3 }
export interface PlacesGeo {
  frame: number;
  size: [number, number];
  hub_top: Picture & { m_per_px: number };
  zones: Record<string, { name: string; top: Picture; eye?: Picture; map?: Picture }>;
  /** each scanner in site metres (x east, y north, z up) */
  points_m: Record<string, [number, number, number]>;
  /** per scanner, three Blender pictures aimed at it (place_shots.py): tilted 3D map, straight down, eye height */
  pt?: Record<string, { zone: string; tilt?: Shot; top?: Shot; eye?: Shot | null }>;
  /** per scanner, a Blender turntable (place_turn.py): n frames per ring, frames at /places/turn/<id>/<ring>_<kk>.webp,
   *  pins in /places/turn/<id>/turn.json */
  turn?: Record<string, { n: number; rings: string[] }>;
}
/** one turntable: per ring, per frame, the scanner's pixel and the zone's other scanners (1600 x 900 units) */
export interface TurnData { zone: string; n: number; rings: Record<string, { x: number; y: number; mates: Record<string, { x: number; y: number }> }[]> }
/** a picture aimed at one scanner: its pixel (x, y) and the zone's other scanners in view (1600 x 900) */
export interface Shot { image: string; x: number; y: number; mates: Record<string, { x: number; y: number }> }

let cache: Promise<PlacesGeo> | null = null;
/** The pictures and pin positions (one fetch for the whole app); null while loading or if missing. */
export function usePlacesGeo(): PlacesGeo | null {
  const [geo, setGeo] = useState<PlacesGeo | null>(null);
  useEffect(() => {
    let live = true;
    cache ??= fetch("/places/places.json").then((r) => { if (!r.ok) throw new Error(String(r.status)); return r.json(); });
    cache.then((g) => live && setGeo(g), () => { cache = null; });
    return () => { live = false; };
  }, []);
  return geo;
}
