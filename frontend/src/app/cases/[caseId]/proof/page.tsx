"use client";
/**
 * Proof (step 2), ops-console style: "See it on camera". The selected moment in the big viewer (the same zoom, pan and
 * full screen as the Cameras page) or the 3D hub; every camera on the route in order below it; on the right, docked, what
 * this moment shows in two sentences, the floor plan, "Go look" and the evidence details. Frames are the original
 * recordings; where there is no footage of that exact moment the viewer shows the camera's own view of the place and says
 * so, and the player controls appear only when there is a recording to play.
 */
import dynamic from "next/dynamic";
import { SpoorLoader } from "@/components/brand/SpoorLoader";
import Link from "next/link";
import { use, useEffect, useMemo, useRef, useState } from "react";
import { api, signedUrl, useResource } from "@/lib/api";
import { HUB, camId, scanPoint } from "@/lib/hub";
import type { Journey, MissingMoment, ObservedSegment } from "@/lib/journey";
import type { MediaRow, Site } from "@/lib/types";
import { hms, momentLabel, placeOf, shortPlace } from "@/lib/words";
import { CaseSteps } from "@/components/flow/CaseSteps";
import HubPlan, { ZONE_NAMES } from "@/components/plan/HubPlan";
import { WorkspaceProvider } from "@/components/workspace/context";
import { Viewer } from "@/components/cameras/Viewer";
import "@/app/hub/hub.css";
import "@/app/wall/cameras.css";
import "./proof.css";

const Scene3D = dynamic(() => import("@/components/workspace/Scene3D"), { ssr: false,
  loading: () => <SpoorLoader label="Loading the 3D hub" size={56} fill /> });

interface CaseState { case: { case_id: string; site_id: string; target_description: string; complaint?: string | null } }
interface Possible { objects: { places: { area_id: string; name: string; zone_id: string | null; possible_share: number }[] }[] }
interface Conflicts { objects: { conflicts: { kind: string; divergence_t: string; statement: string; claim: { evidence_ids: string[] } }[] }[] }
interface Tile { key: string; cam: string | null; place: string; t: string; status: string; tone: "seen" | "notseen" | "none" | "wait" | "bad";
  headline: string; body: string; conflict?: string;
  /** a camera sighting: SAM's outlined frames along the track (the player shows the one nearest its time) */
  seen?: ObservedSegment["points"] }

const camName = (hub: string) => hub.replace("_", " ");

export default function ProofPage({ params }: { params: Promise<{ caseId: string }> }) {
  const { caseId } = use(params);
  const st = useResource<CaseState>(`/v1/cases/${caseId}/state`);
  const jr = useResource<Journey>(`/v1/cases/${caseId}/journey`);
  const mr = useResource<MissingMoment>(`/v1/cases/${caseId}/missing-moment`);
  const pr = useResource<Possible>(`/v1/cases/${caseId}/possible-locations`);
  const cr = useResource<Conflicts>(`/v1/cases/${caseId}/conflicts`);
  const sites = useResource<Site[]>("/v1/sites");
  const siteId = st.data?.case.site_id ?? sites.data?.[0]?.site_id;
  const media = useResource<MediaRow[]>(siteId ? `/v1/sites/${siteId}/media` : null);
  const [view, setView] = useState<"video" | "3d">("video");
  const [pick, setPick] = useState<string | null>(null);

  const j = jr.data?.objects[0];
  const mm = mr.data?.objects[0];
  const scans = useMemo(() => j?.scans ?? [], [j]);
  const top = (pr.data?.objects[0]?.places ?? []).find((p) => p.possible_share > 0);
  const conflict = cr.data?.objects[0]?.conflicts[0];
  const coverage = (hub: string, t: string) => (media.data ?? []).find((m) => m.media.camera_id && camId.toHub(m.media.camera_id) === hub
    && m.coverage.some((c) => c.start_utc <= t && t <= c.end_utc));

  // every camera on the route, in order: who watched each scan, then the cameras due next (missing moment)
  const tiles: Tile[] = useMemo(() => {
    const out: Tile[] = [];
    for (const s of scans) {
      const cam = scanPoint(s.station_id ?? s.device_id)?.visible_by[0] ?? null;
      const has = cam ? coverage(cam, s.t) : undefined;
      const label = momentLabel(s.event_kind, s.station_id);
      out.push({ key: s.scan_event_id, cam, place: label, t: s.t, tone: has ? "wait" : "none", status: has ? "Not checked yet" : "No footage",
        headline: `${label} at ${hms(s.t)}.`,
        body: `The ${s.device_kind === "tunnel" ? "scan tunnel" : "sorter"} recorded this. ${cam ? (has ? `${camName(cam)} watches ${placeOf(s.event_kind, s.station_id)}; its frame at this moment is in the player.` : `${camName(cam)} watches ${placeOf(s.event_kind, s.station_id)}, but its footage for this moment isn't in yet.`) : "No camera watches this point."}` });
    }
    for (const r of mm?.expected_next ?? []) {
      const cam = camId.toHub(r.camera_id);
      if (out.some((x) => x.cam === cam)) continue;
      const tone = r.result === "seen" ? "seen" : r.result === "not_seen" ? "notseen" : r.result === "no_footage" ? "none" : "wait";
      const status = r.result === "seen" ? `Seen ${hms(r.predicted_t)}` : r.result === "not_seen" ? "Expected, not seen" : r.result === "no_footage" ? "No footage" : "Not checked yet";
      out.push({ key: r.camera_id, cam, place: r.camera_name.replace(/^CAM_\d+\s*/, "").toLowerCase(), t: r.window.start, tone, status,
        headline: r.result === "not_seen" ? `Should have appeared on ${camName(cam)} by ${hms(r.window.end)}. It didn't.` : `Should appear on ${camName(cam)} at about ${hms(r.predicted_t)}.`,
        body: r.result === "no_footage" ? `${camName(cam)} would show where it went next, but its footage for this moment isn't in yet.` : `${r.how.charAt(0).toUpperCase()}${r.how.slice(1)}.` });
    }
    // where a camera actually saw it: the tracks linked to this parcel (SAM 3.1 follows it from an investigator's box)
    for (const g of j?.segments ?? []) {
      if (g.kind !== "observed") continue;
      const cam = camId.toHub(g.camera_id);
      const secs = Math.max(1, Math.round((Date.parse(g.end) - Date.parse(g.start)) / 1000));
      // opens mid-sighting: at the start the parcel is only just entering the frame
      out.push({ key: g.track_id, cam, place: "seen on camera", t: g.points[g.points.length >> 1]?.t ?? g.start, tone: "seen", status: `Seen ${hms(g.start)}`, seen: g.points,
        headline: `On ${camName(cam)} from ${hms(g.start)} to ${hms(g.end)}.`,
        body: `SAM 3.1 followed this parcel frame by frame for ${secs} s, from the box drawn on it, until it left the camera's view.` });
    }
    out.sort((a, b) => a.t.localeCompare(b.t));
    if (conflict) out.push({ key: "conflict", cam: null, place: "sorter records", t: conflict.divergence_t, tone: "bad", status: "Records disagree",
      headline: "The sorter's times don't fit the belt.", body: `${conflict.statement.replace(/: the records conflict$/, "")}. One of these records is wrong, or the parcel didn't travel on the belt.`, conflict: conflict.statement });
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps -- recomputed when the evidence or the footage list changes
  }, [scans, mm, conflict, media.data, j]);

  const lastKey = tiles.findLast((t) => t.seen)?.key ?? scans.at(-1)?.scan_event_id;
  const sel = tiles.find((t) => t.key === (pick ?? lastKey)) ?? tiles[0];
  const selMedia = sel?.cam ? coverage(sel.cam, sel.t) : undefined;
  const waybill = st.data?.case.target_description.split(" ").at(-1) ?? "";

  return (
    <div className="pf">
      <CaseSteps caseId={caseId} waybill={waybill} page="Proof" here={1} />
      <div className="pf-main">
        <section className="pf-left">
          <div className="pf-bar">
            <div role="group" aria-label="View" className="cm-seg">
              <button type="button" aria-pressed={view === "video"} onClick={() => setView("video")}>Camera view</button>
              <button type="button" aria-pressed={view === "3d"} onClick={() => setView("3d")}>3D hub</button>
            </div>
            {sel && <p className="pf-now">{sel.cam ? camName(sel.cam) : "Records"} · {sel.place} · {hms(sel.t)}</p>}
          </div>
          {view === "3d" ? (
            <div className="pf-3d"><WorkspaceProvider caseId={caseId}><Scene3D /></WorkspaceProvider></div>
          ) : (
            <Player caseId={caseId} tile={sel} media={selMedia} />
          )}

          <div className="pf-strip-head">
            <h2>Every camera on its route, in order</h2>
            <span>Pick one to open it above</span>
          </div>
          <div className="pf-strip">
            {tiles.map((t) => (
              <button key={t.key} type="button" aria-pressed={t.key === sel?.key} onClick={() => setPick(t.key)} className="pf-tile" data-tone={t.tone}>
                <TileThumb tile={t} media={t.cam ? coverage(t.cam, t.t) : undefined} />
                <span className="pf-tile-text">
                  <span className="pf-tile-cam">{t.cam ? camName(t.cam) : "Records"}</span>
                  <span className="pf-tile-place">{t.place}</span>
                  <span className="pf-tile-status">{t.status}</span>
                </span>
              </button>
            ))}
          </div>
        </section>

        <aside className="pf-right">
          {sel && (
            <div className="pf-card">
              <span className="pf-chip" data-tone={sel.tone}>{sel.status}</span>
              <h1 className="pf-card-h">{sel.headline}</h1>
              <p className="pf-card-body">{sel.body}</p>
            </div>
          )}
          <div className="pf-plan">
            <HubPlan label="Floor plan with the parcel's route" journey={j} missing={mm} fit="width" legend={false} quiet
              litCameras={sel?.cam ? [sel.cam] : []} />
          </div>
          <Link className="hb-btn hb-btn-primary pf-go" href={`/cases/${caseId}/search`}>{top ? `Go look: ${shortPlace(top, ZONE_NAMES)}` : "Start a floor search"}</Link>
          <details className="pf-details">
            <summary>Evidence details</summary>
            <p>{selMedia ? `Original recording ${selMedia.media.media_id}, kept unchanged with its fingerprint (SHA-256 ${selMedia.media.sha256.slice(0, 16)}…).`
              : "No recording for this moment yet."} Scan times are the scanners&apos; own clocks, not yet checked against the cameras.
              {sel?.conflict ? ` Records check: ${sel.conflict}.` : ""} Full list in the report appendix.</p>
          </details>
        </aside>
      </div>
    </div>
  );
}

/** A tile's picture: the camera's frame at that moment when the footage exists, else the camera's own view of the place. */
function TileThumb({ tile, media }: { tile: Tile; media?: MediaRow }) {
  const url = useFrame(media?.media.media_id, tile.t);
  const [still, setStill] = useState(true);
  if (tile.tone === "bad") return <span className="pf-tile-none pf-tile-bad">Records disagree</span>;
  // eslint-disable-next-line @next/next/no-img-element
  if (url) return <img src={signedUrl(url)} alt="" className="pf-tile-img" />;
  // eslint-disable-next-line @next/next/no-img-element
  if (tile.cam && still) return <img src={`/cameras/${tile.cam}.jpg`} alt="" className="pf-tile-img pf-tile-still" loading="lazy" onError={() => setStill(false)} />;
  return <span className="pf-tile-none">No camera</span>;
}

function useFrame(mediaId: string | undefined, t: string | undefined): string | null {
  const [url, setUrl] = useState<{ k: string; u: string } | null>(null);
  const k = `${mediaId}|${t}`;
  useEffect(() => {
    if (!mediaId || !t) return;
    let live = true;
    api<{ frame_url: string }>(`/v1/media/${mediaId}/frame-at?time=${encodeURIComponent(t)}`).then((r) => live && setUrl({ k, u: r.frame_url })).catch(() => {});
    return () => { live = false; };
  }, [mediaId, t, k]);
  return url?.k === k ? url.u : null;
}

/** For a sighting: SAM's outlined frame (the annotated copy; the original stays unchanged) nearest the player's time. */
function useOutlined(caseId: string, pts: Tile["seen"], t: string | undefined): string | null {
  const [url, setUrl] = useState<{ k: string; u: string } | null>(null);
  const near = pts?.length && t ? pts.reduce((a, b) => (Math.abs(Date.parse(b.t) - Date.parse(t)) < Math.abs(Date.parse(a.t) - Date.parse(t)) ? b : a)) : null;
  const inside = near && t && Math.abs(Date.parse(near.t) - Date.parse(t)) < 500;
  const k = inside ? near.observation_id : "";
  useEffect(() => {
    if (!k) return;
    let live = true;
    api<{ annotated_frame_url: string }>(`/v1/cases/${caseId}/evidence/${k}`).then((r) => live && setUrl({ k, u: r.annotated_frame_url })).catch(() => {});
    return () => { live = false; };
  }, [caseId, k]);
  return k && url?.k === k ? url.u : null;
}

const PILL_TONE: Record<Tile["tone"], string> = { seen: "seen", notseen: "notseen", none: "none", wait: "none", bad: "none" };

/** The big picture (zoom, pan, full screen). With a recording: the frame at that moment, plus one transport (play, scrub, 1x / 4x).
 *  Without: the camera's view of the place, labelled as not the moment. */
function Player({ caseId, tile, media }: { caseId: string; tile?: Tile; media?: MediaRow }) {
  const cov = media?.coverage[0];
  const [offset, setOffset] = useState(0); // seconds from the moment
  const [speed, setSpeed] = useState(1);
  const [playing, setPlaying] = useState(false);
  const raf = useRef<number | null>(null);
  const t = tile && cov ? new Date(Math.min(Math.max(new Date(tile.t).getTime() + offset * 1000, new Date(cov.start_utc).getTime()), new Date(cov.end_utc).getTime())).toISOString() : tile?.t;
  const plain = useFrame(media?.media.media_id, t);
  const outlined = useOutlined(caseId, tile?.seen, t);
  const url = outlined ?? plain;
  useEffect(() => {
    if (!playing) return;
    raf.current = window.setInterval(() => setOffset((o) => Math.min(10, o + 0.5 * speed)), 500); // stops at the end of the window
    return () => { if (raf.current) window.clearInterval(raf.current); };
  }, [playing, speed]);
  if (tile?.tone === "bad") {
    return <div className="pf-player pf-player-bad"><span className="pf-player-bad-h">{tile.headline}</span><span className="pf-player-bad-b">{tile.body}</span></div>;
  }
  if (!tile?.cam) return <div className="pf-player pf-player-none"><span>No camera watches this moment.</span></div>;
  const cam = tile.cam;
  const hub = HUB.cameras.find((c) => c.id === cam);
  const label = hub ? hub.osd_label.toLowerCase().replace(/^\w/, (c) => c.toUpperCase()).replace(/c(\d{2})-c(\d{2})/, "C$1 to C$2").replace(/(\d{2})-(\d{2})/, "$1 to $2") : "";
  return (
    <>
      <Viewer key={`${cam}|${tile.key}`} id={cam} label={label} image={url ? signedUrl(url) : undefined} at={t ? hms(t) : undefined}
        pill={{ text: url ? (outlined ? "SAM 3.1 · outlined" : tile.status) : `A view of the place · no footage of ${hms(tile.t)} yet`, tone: url ? PILL_TONE[tile.tone] : "none" }} />
      {media && (
        <div className="pf-controls">
          <button type="button" aria-label={playing ? "Pause" : "Play"} className="pf-play" onClick={() => setPlaying((p) => !p)}>
            {playing ? <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><path d="M4 2.5h3v11H4zM9 2.5h3v11H9z" fill="currentColor" /></svg>
              : <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><path d="M4 2.5v11l9-5.5z" fill="currentColor" /></svg>}
          </button>
          <button type="button" aria-label="Back one frame" className="pf-step" onClick={() => setOffset((o) => o - 0.1)}>−1</button>
          <button type="button" aria-label="Forward one frame" className="pf-step" onClick={() => setOffset((o) => o + 0.1)}>+1</button>
          <label htmlFor="scrub" className="sp-sr">Time around this moment</label>
          <input id="scrub" type="range" min={-10} max={10} step={0.1} value={offset} onChange={(e) => setOffset(Number(e.target.value))} />
          <span className="pf-time">{t ? hms(t) : ""}</span>
          <div role="group" aria-label="Speed" className="pf-speed">
            {[1, 4].map((x) => <button key={x} type="button" aria-pressed={speed === x} onClick={() => setSpeed(x)}>{x}×</button>)}
          </div>
        </div>
      )}
    </>
  );
}
