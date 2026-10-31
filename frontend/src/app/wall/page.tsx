"use client";
/**
 * Cameras, ported from review/refs/flow/Cameras.dc.html (owner 09:22): every camera at the same instant on one clock
 * (each clip placed by its own clock check), filtered by zone, as a camera wall or in the 3D hub. Frames are the
 * original recordings at that time; a camera with no footage for that instant says so.
 */
import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { api, signedUrl, useResource } from "@/lib/api";
import { HUB, camId } from "@/lib/hub";
import type { MediaRow, Site } from "@/lib/types";
import { hms } from "@/lib/words";
import { WorkspaceProvider } from "@/components/workspace/context";
import "./cameras.css";

const Scene3D = dynamic(() => import("@/components/workspace/Scene3D"), { ssr: false, loading: () => <div className="cm-3d-wait">Loading the 3D hub</div> });

// zones as the prototype groups them (by where each camera looks)
const ZONE_OF: Record<string, "in" | "sort" | "out"> = {
  CAM_01: "in", CAM_02: "in", CAM_03: "in", CAM_18: "in", CAM_04: "sort", CAM_05: "sort", CAM_06: "sort", CAM_07: "sort", CAM_08: "sort",
  CAM_09: "sort", CAM_10: "sort", CAM_11: "sort", CAM_12: "sort", CAM_13: "out", CAM_14: "out", CAM_15: "out", CAM_16: "out", CAM_17: "out", CAM_19: "out",
};
const ZONES: [string, string][] = [["all", "All 19"], ["in", "Inbound"], ["sort", "Sorting"], ["out", "Outbound"]];

interface Inbox { as_of: string | null }
interface Dashboard { cases: { case_id: string; status: string }[] }
interface Missing { objects: { expected_next: { camera_id: string }[] }[] }

const camWords = (osd: string) => osd.toLowerCase().replace(/^\w/, (c) => c.toUpperCase()).replace(/(c\d{2})-(c\d{2})/i, (_, a: string, b: string) => `${a.toUpperCase()} to ${b.toUpperCase()}`)
  .replace(/(\d{2})-(\d{2})/, "$1 to $2");

export default function CamerasPage() {
  const sites = useResource<Site[]>("/v1/sites");
  const site = sites.data?.[0];
  const media = useResource<MediaRow[]>(site ? `/v1/sites/${site.site_id}/media` : null);
  const inbox = useResource<Inbox>(site ? `/v1/sites/${site.site_id}/exceptions?limit=1` : null);
  const dash = useResource<Dashboard>(site ? `/v1/sites/${site.site_id}/dashboard` : null);
  const openCase = dash.data?.cases.find((c) => c.status !== "found")?.case_id;
  const mm = useResource<Missing>(openCase ? `/v1/cases/${openCase}/missing-moment` : null);
  const [zone, setZone] = useState("all");
  const [view, setView] = useState<"wall" | "3d">("wall");

  // the shared clock: the span the imported footage covers, else ±10 min around the end of the scan log
  const span = useMemo(() => {
    const cov = (media.data ?? []).flatMap((m) => m.coverage);
    if (cov.length) return [Math.min(...cov.map((c) => Date.parse(c.start_utc))), Math.max(...cov.map((c) => Date.parse(c.end_utc)))];
    const end = inbox.data?.as_of ? Date.parse(inbox.data.as_of) : null;
    return end ? [end - 600_000, end] : null;
  }, [media.data, inbox.data]);
  const [pos, setPos] = useState<number | null>(null); // ms on the shared clock
  const [playing, setPlaying] = useState(false);
  const t = pos ?? (span ? span[1] - (span[1] - span[0]) * 0.42 : null);
  const tick = useRef<number | null>(null);
  useEffect(() => {
    if (!playing || !span) return;
    tick.current = window.setInterval(() => setPos((p) => Math.min(span[1], (p ?? span[0]) + 500)), 500);
    return () => { if (tick.current) window.clearInterval(tick.current); };
  }, [playing, span]);

  const inCase = new Set((mm.data?.objects[0]?.expected_next ?? []).map((r) => camId.toHub(r.camera_id)));
  const cams = HUB.cameras.filter((c) => zone === "all" || ZONE_OF[c.id] === zone);
  const iso = t !== null ? new Date(t).toISOString() : null;

  return (
    <div className="cm">
      <div className="cm-main">
        <div className="cm-head">
          <div>
            <p className="cm-site">{HUB.cameras.length} cameras · all playing the same moment</p>
            <h1 className="cm-h1">The whole hub at {iso ? hms(iso) : "…"}</h1>
          </div>
          <div className="cm-switches">
            <div role="group" aria-label="Zone" className="cm-seg">
              {ZONES.map(([k, label]) => <button key={k} type="button" aria-pressed={zone === k} onClick={() => setZone(k)}>{label}</button>)}
            </div>
            <div role="group" aria-label="View" className="cm-seg cm-seg-strong">
              <button type="button" aria-pressed={view === "wall"} onClick={() => setView("wall")}>Camera wall</button>
              <button type="button" aria-pressed={view === "3d"} onClick={() => setView("3d")}>3D hub</button>
            </div>
          </div>
        </div>

        <div className="cm-clock">
          <button type="button" aria-label={playing ? "Pause all cameras" : "Play all cameras"} className="cm-play" disabled={!span} onClick={() => setPlaying((p) => !p)}>
            {playing ? <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><path d="M4 2.5h3v11H4zM9 2.5h3v11H9z" fill="currentColor" /></svg>
              : <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><path d="M4 2.5v11l9-5.5z" fill="currentColor" /></svg>}
          </button>
          <label htmlFor="t" className="sp-sr">Time for every camera</label>
          <input id="t" type="range" min={span?.[0] ?? 0} max={span?.[1] ?? 1} step={100} value={t ?? 0} disabled={!span} onChange={(e) => setPos(Number(e.target.value))} />
          <span className="cm-time">{iso ? hms(iso) : ""}</span>
          <span className="cm-note">Each clip placed by its own clock check</span>
        </div>

        {view === "wall" ? (
          <div className="cm-grid">
            {cams.map((c) => {
              const m = iso ? (media.data ?? []).find((x) => x.media.camera_id && camId.toHub(x.media.camera_id) === c.id && x.coverage.some((v) => v.start_utc <= iso && iso <= v.end_utc)) : undefined;
              return (
                <div key={c.id} className="cm-tile">
                  <TileFrame mediaId={m?.media.media_id} t={iso} label={`${c.id} ${c.osd_label}`} />
                  <div className="cm-tile-foot">
                    <span className="cm-tile-text"><span className="cm-tile-id">{c.id.replace("_", " ")}</span><span className="cm-tile-name">{camWords(c.osd_label)}</span></span>
                    {inCase.has(c.id) && openCase && <Link href={`/cases/${openCase}/proof`} className="cm-incase">In a case</Link>}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="cm-3d">{openCase ? <WorkspaceProvider caseId={openCase}><Scene3D /></WorkspaceProvider> : <div className="cm-3d-wait">No open case to centre the 3D hub on.</div>}</div>
        )}
      </div>
    </div>
  );
}

function TileFrame({ mediaId, t, label }: { mediaId?: string; t: string | null; label: string }) {
  const [url, setUrl] = useState<{ k: string; u: string } | null>(null);
  const k = `${mediaId}|${t}`;
  useEffect(() => {
    if (!mediaId || !t) return;
    let live = true;
    const id = window.setTimeout(() => {
      api<{ frame_url: string }>(`/v1/media/${mediaId}/frame-at?time=${encodeURIComponent(t)}`).then((r) => live && setUrl({ k, u: r.frame_url })).catch(() => {});
    }, 150); // scrubbing: ask once the thumb rests
    return () => { live = false; window.clearTimeout(id); };
  }, [mediaId, t, k]);
  // eslint-disable-next-line @next/next/no-img-element
  if (mediaId && url?.k === k) return <img src={signedUrl(url.u)} alt={label} className="cm-img" />;
  return <span className="cm-none">{mediaId ? "Loading" : "No footage for this moment"}</span>;
}
