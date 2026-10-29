"use client";
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { useResource } from "@/lib/api";
import { scanPoint } from "@/lib/hub";
import { toMs } from "@/lib/time";
import type { SensorEvent } from "@/contracts/generated";
import type {
  Capabilities, CameraRow, CaseState, ClockDomainRow, LastSeenRow, MediaRow, ParcelLookup, Replay, ReportRow, ScanRow,
} from "@/lib/types";

export type TraceMode = "object" | "people" | "all";

export type Selection =
  | { kind: "scan"; scanId: string }
  | { kind: "observation"; observationId: string }
  | { kind: "gap"; start: string; end: string; reason: string }
  | { kind: "camera"; cameraId: string; time: number }
  | null;

export interface FocusRequest {
  id: number;
  site_xy: [number, number] | null; // null = reset to the overview
  radius_m: number;
}

interface Ctx {
  caseId: string;
  siteId: string | null;
  state: ReturnType<typeof useResource<CaseState>>;
  replay: ReturnType<typeof useResource<Replay>>;
  lastSeen: ReturnType<typeof useResource<LastSeenRow[]>>;
  parcel: ReturnType<typeof useResource<ParcelLookup>>;
  cameras: ReturnType<typeof useResource<CameraRow[]>>;
  media: ReturnType<typeof useResource<MediaRow[]>>;
  domains: ReturnType<typeof useResource<ClockDomainRow[]>>;
  siteScans: ReturnType<typeof useResource<{ total: number; scans: ScanRow[] }>>;
  reports: ReturnType<typeof useResource<ReportRow[]>>;
  sensors: ReturnType<typeof useResource<SensorEvent[]>>;
  caps: ReturnType<typeof useResource<Capabilities>>;
  range: { start: number; end: number } | null;
  playhead: number | null;
  setPlayhead: (t: number) => void;
  selection: Selection;
  select: (s: Selection) => void;
  mode: TraceMode;
  setMode: (m: TraceMode) => void;
  focus: FocusRequest;
  focusOn: (xy: [number, number] | null, radius?: number) => void;
  litCameras: string[]; // hub camera ids whose cones are illuminated
  setLitCameras: (ids: string[]) => void;
  reloadAll: () => Promise<void>;
}

const WorkspaceCtx = createContext<Ctx | null>(null);

export function useWorkspace() {
  const c = useContext(WorkspaceCtx);
  if (!c) throw new Error("useWorkspace outside WorkspaceProvider");
  return c;
}

export function WorkspaceProvider({ caseId, children }: { caseId: string; children: ReactNode }) {
  const state = useResource<CaseState>(`/v1/cases/${caseId}/state`);
  const siteId = state.data?.case.site_id ?? null;
  const ident = state.data?.objects[0]?.object.identifiers?.[0] ?? null;
  const replay = useResource<Replay>(`/v1/cases/${caseId}/replay`);
  const lastSeen = useResource<LastSeenRow[]>(`/v1/cases/${caseId}/last-seen`);
  const parcel = useResource<ParcelLookup>(siteId && ident ? `/v1/sites/${siteId}/parcels/${ident.scheme}/${ident.value}` : null);
  const cameras = useResource<CameraRow[]>(siteId ? `/v1/sites/${siteId}/cameras` : null);
  const media = useResource<MediaRow[]>(siteId ? `/v1/sites/${siteId}/media` : null);
  const domains = useResource<ClockDomainRow[]>(siteId ? `/v1/sites/${siteId}/clock-domains` : null);
  const reports = useResource<ReportRow[]>(`/v1/cases/${caseId}/reports`);
  const sensors = useResource<SensorEvent[]>(siteId ? `/v1/sites/${siteId}/sensor-events` : null);
  const caps = useResource<Capabilities>("/v1/capabilities");

  const range = useMemo(() => {
    const w = state.data?.case.window;
    if (w) return { start: toMs(w.start_utc), end: toMs(w.end_utc) };
    const ts: number[] = [];
    media.data?.forEach((m) => m.coverage.forEach((c) => ts.push(toMs(c.start_utc), toMs(c.end_utc))));
    parcel.data?.scans.forEach((s) => ts.push(toMs(s.time)));
    if (!ts.length) return null;
    const lo = Math.min(...ts);
    const hi = Math.max(...ts);
    const pad = Math.max(2000, (hi - lo) * 0.05);
    return { start: lo - pad, end: hi + pad };
  }, [state.data, media.data, parcel.data]);

  const siteScans = useResource<{ total: number; scans: ScanRow[] }>(
    siteId && range ? `/v1/sites/${siteId}/scans?start=${encodeURIComponent(new Date(range.start).toISOString())}`
      + `&end=${encodeURIComponent(new Date(range.end).toISOString())}` : null);

  const [playheadRaw, setPlayhead] = useState<number | null>(null);
  const playhead = playheadRaw ?? range?.start ?? null;
  const [selection, setSelection] = useState<Selection>(null);
  const [mode, setMode] = useState<TraceMode>("object");
  const [focus, setFocus] = useState<FocusRequest>({ id: 0, site_xy: null, radius_m: 30 });
  const [litCameras, setLitCameras] = useState<string[]>([]);

  const focusOn = useCallback((xy: [number, number] | null, radius = 8) => {
    setFocus((f) => ({ id: f.id + 1, site_xy: xy, radius_m: radius }));
  }, []);

  const select = useCallback((s: Selection) => {
    setSelection(s);
    if (s?.kind === "scan") {
      const scan = parcel.data?.scans.find((x) => x.scan_event_id === s.scanId)
        ?? siteScans.data?.scans.find((x) => x.scan_event_id === s.scanId);
      if (scan) {
        setPlayhead(toMs(scan.time));
        const sp = scanPoint(scan.station_id ?? scan.device_id);
        if (sp) setLitCameras(sp.visible_by);
      }
    } else if (s?.kind === "camera") {
      setPlayhead(s.time);
    } else if (s?.kind === "gap") {
      setPlayhead(toMs(s.start));
    }
  }, [parcel.data, siteScans.data]);

  const reloadAll = useCallback(async () => {
    await Promise.all([state.reload(), replay.reload(), lastSeen.reload(), parcel.reload(), reports.reload(),
      cameras.reload(), media.reload()]);
  }, [state, replay, lastSeen, parcel, reports, cameras, media]);

  const value: Ctx = {
    caseId, siteId, state, replay, lastSeen, parcel, cameras, media, domains, siteScans, reports, sensors, caps, range,
    playhead, setPlayhead, selection, select, mode, setMode, focus, focusOn, litCameras, setLitCameras, reloadAll,
  };
  return <WorkspaceCtx.Provider value={value}>{children}</WorkspaceCtx.Provider>;
}

/** Camera clock trust: anchor-fitted syncs with small uncertainty are trusted; anything else is a warning. */
export function clockWarning(sync: CameraRow["clock_sync"]): string | null {
  if (!sync) return "no clock sync: clip cannot be placed on the timeline";
  if (/UNVERIFIED/i.test(sync.method) || sync.anchor_count === 0) {
    return `clock unverified (± ${(sync.uncertainty_ms / 1000).toFixed(1)} s): no anchor event matched yet`;
  }
  if (sync.uncertainty_ms > 1000) return `clock uncertainty ± ${(sync.uncertainty_ms / 1000).toFixed(1)} s`;
  return null;
}
