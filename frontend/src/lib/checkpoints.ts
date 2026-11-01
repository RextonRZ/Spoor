/**
 * The six places a hub scans a parcel, in order: unloaded, scan tunnel, into a chute, into a bag or cage, into the
 * exception store, loaded on a truck. One function for every screen that shows them (the landing page, the case
 * Answer, the 3D hub pins), so they always agree. Everything comes from the case's own scan log (the journey's scans
 * and the records the case derives from container scans); nothing here is typed by hand.
 *
 * A checkpoint is "scanned" (with its time and what the scanner recorded), "missing" (no scan there: shown dashed) or
 * "conflict" (the records put it somewhere the cameras did not: shown red). Whether the cameras saw the parcel at the
 * truck is passed in by the caller, because it needs footage: without it the truck step stays a plain record.
 */
import type { JourneyScan } from "./journey";
import { hms } from "./words";

export type CheckpointId = "unload" | "tunnel" | "chute" | "container" | "store" | "truck";
export type CheckpointState = "scanned" | "missing" | "unscanned" | "conflict";

/** A record the case derives from container scans (GET /conflicts, `records[]`). */
export interface CaseRecord {
  t: string;
  words: string;
  zone_id?: string | null;
  claim?: string;
  container?: string | null;
  event_kind?: string | null;
  station_id?: string | null;
}

export interface ScannerScreen {
  /** cm and kg, as the tunnel recorded them (dims_mm / weight_g); masked barcode; the chute it was sent to */
  length_cm: number | null;
  width_cm: number | null;
  height_cm: number | null;
  weight_kg: number | null;
  barcode: string | null;
  chute: string | null;
  read_ok: boolean;
  photo: string | null;
}

export interface Checkpoint {
  id: CheckpointId;
  /** plain words: "Unloaded", "Scan tunnel", ... */
  label: string;
  /** what a missing scan here means, in plain words ("Not scanned in") */
  none: string;
  /** how it is scanned, in a few words */
  how: string;
  state: CheckpointState;
  t: string | null;
  /** what the record says, in plain words ("Into chute C12", "Into cage RC-760") */
  detail: string | null;
  /** where the scanner is (a hub_spec scan point), for pins on the hub */
  point: string | null;
  screen?: ScannerScreen;
  /** a red step: the records' words and the cameras' words, side by side; an "unscanned" step (no scan, but the
   *  cameras saw it there) carries only the cameras' words */
  records?: string;
  cameras?: string;
}

const STORE = /^LOC-Z11|EXCEPTION/i;
const door = (station?: string | null) => station?.match(/D\d{2}/)?.[0] ?? null;

/** "CTX0951****2767": the barcode on screen, with the middle masked (the case shows it in full where it is needed). */
export function maskBarcode(code: string): string {
  return code.length > 8 ? `${code.slice(0, 4)}${"*".repeat(Math.max(4, code.length - 8))}${code.slice(-4)}` : code;
}

export function buildCheckpoints({
  scans,
  records = [],
  barcode = null,
  truckSeen,
  storeSeenAt,
}: {
  scans: JourneyScan[];
  records?: CaseRecord[];
  /** the parcel's own barcode (the case's waybill), shown masked on the scanner screen */
  barcode?: string | null;
  /** did the cameras see the parcel at the truck? true / false from footage; undefined = not checked */
  truckSeen?: boolean;
  /** when the cameras saw it go into the exception store (from footage); undefined = not known */
  storeSeenAt?: string | null;
}): Checkpoint[] {
  const first = (pred: (s: JourneyScan) => boolean) => scans.find(pred);
  const unload = first((s) => s.event_kind === "arrived_facility");
  const tunnel = first((s) => s.event_kind === "tunnel_read" || s.event_kind === "tunnel_no_read");
  const chute = first((s) => s.event_kind === "divert_confirmed");
  const box = first((s) => s.event_kind === "container_add" && !STORE.test(s.container ?? "") && s.station_id !== "SP-STORE-IN");
  const store = first((s) => s.event_kind === "container_add" && (STORE.test(s.container ?? "") || s.station_id === "SP-STORE-IN"));
  const ownTruck = first((s) => s.event_kind === "container_loaded" || s.event_kind === "departed_facility");
  // a parcel inside a cage leaves with the cage: the cage's own gate read is the parcel's truck record
  const cageTruck = records.find((r) => r.event_kind === "container_loaded" || r.event_kind === "departed_facility");

  const chuteId = chute?.sort_destination_actual ?? chute?.station_id?.match(/C\d{2}/)?.[0] ?? null;
  const boxId = box?.container ?? box?.raw_description?.match(/into (\S+)/)?.[1] ?? null;
  const boxKind = /^RC-|cage/i.test(boxId ?? box?.station_id ?? "") || box?.station_id?.startsWith("SP-CAGE") ? "cage" : "bag";

  const cps: Checkpoint[] = [
    {
      id: "unload", label: "Unloaded", none: "No unload scan", how: "Handheld scan at the door", point: unload?.station_id ?? "SP-IN-N",
      state: unload ? "scanned" : "missing", t: unload?.t ?? null, detail: unload ? "Off the truck" : null,
    },
    {
      id: "tunnel", label: "Scan tunnel", none: "Not read at the tunnel", how: "Photo, weight and size", point: tunnel?.station_id ?? "SP-TUNNEL",
      state: tunnel ? "scanned" : "missing", t: tunnel?.t ?? null,
      detail: tunnel ? (tunnel.event_kind === "tunnel_read" ? "Label read" : "Label not read") : null,
      screen: tunnel ? {
        // dims_mm is the tunnel's length, width, height
        length_cm: tunnel.dims_mm ? tunnel.dims_mm[0] / 10 : null,
        width_cm: tunnel.dims_mm ? tunnel.dims_mm[1] / 10 : null,
        height_cm: tunnel.dims_mm ? tunnel.dims_mm[2] / 10 : null,
        weight_kg: tunnel.weight_g != null ? tunnel.weight_g / 1000 : null,
        barcode: tunnel.event_kind === "tunnel_read" && barcode ? maskBarcode(barcode) : null,
        chute: tunnel.sort_destination_assigned ?? chuteId,
        read_ok: tunnel.event_kind === "tunnel_read",
        photo: tunnel.raw_description?.match(/^tunnel photo (\S+\.(?:jpe?g|png))$/i)?.[1] ?? null,
      } : undefined,
    },
    {
      id: "chute", label: "Into chute", none: "No chute scan", how: "Sorter confirms the drop", point: chute?.station_id ?? null,
      state: chute ? "scanned" : "missing", t: chute?.t ?? null,
      // the tunnel assigns a chute; the sorter reports where it went down: say both when they differ
      detail: chute ? (tunnel?.sort_destination_assigned && chuteId && tunnel.sort_destination_assigned !== chuteId
        ? `Down ${chuteId} (assigned ${tunnel.sort_destination_assigned})` : `Chute ${chuteId ?? ""}`.trim()) : null,
    },
    {
      id: "container", label: "Into bag or cage", none: "Not scanned into a bag or cage", how: "Handheld scan", point: box?.station_id ?? null,
      state: box ? "scanned" : "missing", t: box?.t ?? null, detail: box ? `Into ${boxKind} ${boxId ?? ""}`.trim() : null,
    },
    {
      id: "store", label: "Exception store", none: "Not scanned in", how: "Scan-in at the door", point: store?.station_id ?? "SP-STORE-IN",
      state: store ? "scanned" : storeSeenAt ? "unscanned" : "missing", t: store?.t ?? null, detail: store ? "Scanned in" : null,
      // no scan-in, but the footage shows it carried in: the gap the case is about
      cameras: !store && storeSeenAt ? `Cameras: carried in at ${hms(storeSeenAt)}` : undefined,
    },
  ];

  const truckAt = ownTruck?.t ?? cageTruck?.t ?? null;
  const truckDoor = door(ownTruck?.station_id ?? cageTruck?.station_id);
  const truck: Checkpoint = {
    id: "truck", label: "Loaded on truck", none: "No truck scan", how: "Cage tag read at the dock gate",
    point: ownTruck?.station_id ?? cageTruck?.station_id ?? null,
    state: truckAt ? (truckSeen === false ? "conflict" : "scanned") : "missing", t: truckAt,
    detail: truckAt ? `Truck ${truckDoor ?? ""}`.trim() : null,
  };
  if (truck.state === "conflict") {
    truck.records = `Record says loaded on truck ${truckDoor ?? ""}`.trim();
    truck.cameras = "Cameras show it never left";
  } else if (truckAt && truckSeen === undefined) {
    truck.cameras = "Cameras: not checked yet"; // no footage tracked yet: say so, never guess
  }
  cps.push(truck);
  return cps;
}

export const CHECKPOINT_LINE = "Scans tell you where a parcel was at a few moments. Spoor shows what happened in between.";
